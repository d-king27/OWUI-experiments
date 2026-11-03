import base64,json
import unittest
import httpx
from script_to_voice.contracts import *
from script_to_voice.providers.elevenlabs import ElevenLabs,ProviderError
from script_to_voice.providers.fakes import tone_wav


def chunk(text='Hello'):
    return CompiledChunk(id='c',scene_id='s',request=DialogueRequest(inputs=(DialogueInput(voice_id='v',text=text),)),fragments=())


class ProviderTests(unittest.IsolatedAsyncioTestCase):
    async def test_payload_models_pagination_design_and_save(self):
        calls=[]
        def respond(req):
            calls.append(req)
            self.assertEqual(req.headers['xi-api-key'],'private')
            if req.url.path=='/v1/models': data=[{'model_id':'eleven_v4','can_do_text_to_speech':True}]
            elif req.url.path=='/v2/voices': data={'voices':[{'voice_id':'v','name':'Voice'}],'has_more':True,'next_page_token':'next'}
            elif req.url.path=='/v1/text-to-voice/design': data={'previews':[{'generated_voice_id':'preview','audio_base_64':base64.b64encode(tone_wav()).decode(),'media_type':'audio/wav'}]}
            elif req.url.path=='/v1/text-to-voice': data={'voice_id':'saved','name':'Saved'}
            else: data={'audio_base64':base64.b64encode(tone_wav()).decode(),'voice_segments':[{'dialogue_input_index':0,'voice_id':'v'}]}
            return httpx.Response(200,json=data,headers={'request-id':'rid'})
        p=ElevenLabs(transport=httpx.MockTransport(respond),key='private',live_enabled=True)
        page=await p.list_voices('old'); self.assertEqual(page.next_cursor,'next')
        self.assertEqual(calls[0].url.params['next_page_token'],'old')
        result=await p.render(chunk()); self.assertEqual(result.request_id,'rid')
        self.assertEqual(json.loads(calls[-1].content),chunk().request.provider_body())
        previews=await p.design_previews(VoiceDesignRequest(voice_description='A warm measured narrator voice',text='Hello world. '*10))
        self.assertEqual((await p.save_preview(previews[0].generated_voice_id,'New','Description')).voice_id,'saved')
        self.assertNotIn('private',str(chunk().model_dump()))

    async def test_errors_no_retries_and_live_gate(self):
        for code,kind in [(401,'authentication'),(403,'permission'),(422,'validation'),(429,'rate_limit'),(503,'transient')]:
            count=[]
            def respond(req): count.append(1); return httpx.Response(code,json={'secret':'private'},headers={'Retry-After':'3'})
            p=ElevenLabs(transport=httpx.MockTransport(respond),key='private')
            with self.assertRaises(ProviderError) as e: await p.list_voices()
            self.assertEqual(e.exception.kind,kind); self.assertEqual(len(count),1)
            self.assertNotIn('private',str(e.exception))
        p=ElevenLabs(key='private',live_enabled=False)
        with self.assertRaises(ProviderError): await p.design_previews(VoiceDesignRequest(voice_description='A warm measured narrator voice',text='Hello world. '*10))
        with self.assertRaises(ProviderError): await p.render(chunk('x'*2001))
        with self.assertRaises(ValueError): DialogueRequest(inputs=(DialogueInput(voice_id='v',text='hi'),),speed=2)

    async def test_ambiguous_timeout(self):
        def respond(req): raise httpx.ReadTimeout('sensitive')
        p=ElevenLabs(transport=httpx.MockTransport(respond),key='key',live_enabled=True); p.models_checked=True
        with self.assertRaises(ProviderError) as e: await p.render(chunk())
        self.assertEqual(e.exception.kind,'ambiguous')
