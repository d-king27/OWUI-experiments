import os
import unittest
import sys
import types
from unittest.mock import AsyncMock, patch
import httpx
from openwebui.functions.script_to_voice_pipe import Pipe


class PipeTests(unittest.IsolatedAsyncioTestCase):
    async def test_native_progress_follows_saved_job_and_delivers_audio_without_resubmission(self):
        events=[]; calls=[]
        async def emitter(event): events.append(event)
        def result(status,completed=0,artifacts=None):
            return {'message':'Your audio is ready' if status=='completed' else 'Generating audio',
                    'job':{'id':'job-a','status':status,'completed':completed,'total':2},'artifacts':artifacts or []}
        states=[result('running'),result('running',1),result('completed',2,[{'id':'audio','filename':'take.mp3','mime':'audio/mpeg'}])]
        def respond(request):
            calls.append(request)
            if request.method=='POST': return httpx.Response(200,json=result('queued'))
            if request.url.path.endswith('/result'): return httpx.Response(200,json=states.pop(0))
            if request.url.path=='/v1/artifacts/audio/content': return httpx.Response(200,content=b'mock-audio')
            raise AssertionError(request.url)
        helper=types.ModuleType('openwebui.functions.script_to_voice_files')
        helper.register_output=AsyncMock(return_value={'url':'/api/v1/files/audio-file/content'})
        with patch.dict(os.environ,{'STV_ENABLED':'true','STV_SERVICE_TOKEN':'secret-'*5}), \
             patch.dict(sys.modules,{'openwebui.functions.script_to_voice_files':helper}):
            text=await Pipe(transport=httpx.MockTransport(respond),poll_interval=0).pipe(
                {'messages':[{'role':'user','content':'generate'}]},__user__={'id':'a'},__event_emitter__=emitter)
        self.assertIn('<audio>/api/v1/files/audio-file/content</audio>',text)
        self.assertIn('[Download take.mp3]',text)
        self.assertEqual(sum(r.method=='POST' for r in calls),1)
        self.assertTrue(all(r.headers['X-STV-Owner']=='a' for r in calls))
        self.assertTrue(any('1 of 2' in e['data']['description'] and not e['data']['done'] for e in events))
        self.assertTrue(events[-1]['data']['done'])
        self.assertEqual(events[-1]['data']['description'],'Audio ready')

    async def test_watch_timeout_keeps_job_saved_and_closes_indicator(self):
        emitter=AsyncMock(); calls=[]
        def respond(request):
            calls.append(request)
            return httpx.Response(200,json={'message':'Queued','artifacts':[],
                'job':{'id':'job-a','status':'queued','completed':0,'total':1}})
        with patch.dict(os.environ,{'STV_ENABLED':'true','STV_SERVICE_TOKEN':'secret-'*5}):
            text=await Pipe(transport=httpx.MockTransport(respond),watch_seconds=0).pipe(
                {'messages':[{'role':'user','content':'generate'}]},__user__={'id':'a'},__event_emitter__=emitter)
        self.assertIn('background',text)
        self.assertIn('status',text)
        self.assertEqual(len(calls),1)
        self.assertTrue(emitter.call_args.args[0]['data']['done'])

    async def test_emitter_failure_is_optional_and_failure_outcome_stops_animation(self):
        queued={'message':'Queued','artifacts':[],'job':{'id':'job-a','status':'queued','completed':0,'total':1}}
        calls=[]
        def respond(request):
            calls.append(request)
            return httpx.Response(200,json=queued if request.method=='POST' else
                {'message':'Generation needs attention','artifacts':[],
                 'job':{'id':'job-a','status':'failed','completed':0,'total':1}})
        with patch.dict(os.environ,{'STV_ENABLED':'true','STV_SERVICE_TOKEN':'secret-'*5}):
            text=await Pipe(transport=httpx.MockTransport(respond)).pipe(
                {'messages':[{'role':'user','content':'generate'}]},__user__={'id':'a'},
                __event_emitter__=AsyncMock(side_effect=RuntimeError('Channel disconnected')))
            self.assertIn('status',text)
            self.assertEqual(len(calls),1)
            emitter=AsyncMock()
            text=await Pipe(transport=httpx.MockTransport(respond),poll_interval=0).pipe(
                {'messages':[{'role':'user','content':'status'}]},__user__={'id':'a'},__event_emitter__=emitter)
        self.assertIn('needs attention',text)
        self.assertEqual(emitter.call_args.args[0]['data'],{'description':'Audio generation needs attention','done':True})

    async def test_optional_emitter_identity_background_and_payload(self):
        calls=[]
        def respond(request):
            calls.append(request)
            return httpx.Response(200,json={'message':'Mock job ready','artifacts':[]})
        pipe=Pipe(transport=httpx.MockTransport(respond))
        with patch.dict(os.environ,{'STV_ENABLED':'true','STV_SERVICE_TOKEN':'secret-'*5}):
            body={'messages':[{'role':'user','content':'status'}]}
            self.assertIn('identity',await pipe.pipe(body))
            self.assertEqual(await pipe.pipe(body,__task__='title',__user__={'id':'a'}),'Script to Voice')
            self.assertEqual(calls,[])
            result=await pipe.pipe(body,__user__={'id':'a'},__metadata__={'user_prompt':'status'})
            self.assertEqual(result,'Mock job ready')
            self.assertEqual(calls[0].headers['X-STV-Owner'],'a')
            self.assertNotIn('tool_calls',result)

    async def test_missing_configuration(self):
        with patch.dict(os.environ,{'STV_ENABLED':'true','STV_SERVICE_TOKEN':''}):
            self.assertIn('configured',await Pipe().pipe({},__user__={'id':'a'}))
