import base64
import tempfile
import unittest
from script_to_voice.storage import Repository,Conflict,NotFound
from script_to_voice.providers.fakes import FakeVoiceProvider
from script_to_voice.providers.elevenlabs import ProviderError
from script_to_voice.service.workflow import Workflow,PlanRequest,JobRequest
from script_to_voice.service.app import ChatRequest,ImportFile
from .test_parsing import FIXTURE


class JobTests(unittest.IsolatedAsyncioTestCase):
    async def test_owned_polling_result_is_read_only_and_exposes_completed_downloads(self):
        with tempfile.TemporaryDirectory() as d:
            repo,provider,workflow,chat=await self.setup_workflow(d)
            await chat('plan')
            queued=await chat('generate')
            ident=queued['job']['id']
            self.assertEqual(queued['job']['completed'],0)
            for _ in range(3):
                self.assertEqual(workflow.job_result('a',ident)['job']['status'],'queued')
            self.assertEqual(provider.calls,[])
            with self.assertRaises(NotFound): workflow.job_result('b',ident)
            await workflow.jobs.tick(); await workflow.jobs.tick()
            result=workflow.job_result('a',ident)
            self.assertEqual(result['job']['status'],'completed')
            self.assertEqual(result['job']['completed'],result['job']['total'])
            self.assertTrue(any(a['mime']=='audio/mpeg' for a in result['artifacts']))
            calls=len(provider.calls)
            workflow.job_result('a',ident)
            self.assertEqual(len(provider.calls),calls)

    async def test_transient_retry_cannot_expand_authorized_budget(self):
        with tempfile.TemporaryDirectory() as d:
            repo,p,w,chat=await self.setup_workflow(d)
            await chat('select scene 12A'); await chat('plan'); await chat('generate')
            ident=repo.session('a','chat')[1]['job_id']; calls=[]
            async def unavailable(chunk): calls.append(chunk.id); raise ProviderError('transient','Unavailable')
            p.render=unavailable
            await w.jobs.tick()
            with repo.connect(immediate=True) as db: db.execute('UPDATE chunks SET retry_at=0 WHERE job=?',(ident,))
            await w.jobs.tick()
            self.assertEqual(len(calls),1)
            self.assertEqual(w.jobs.status('a',ident)['chunks'][0]['error'],'budget_exhausted')

    async def setup_workflow(self,d):
        repo=Repository(d); provider=FakeVoiceProvider(); w=Workflow(repo,provider)
        async def chat(text,files=[]): return await w.chat('a',ChatRequest(chat_id='chat',message=text,files=files))
        await chat('import',[ImportFile(file_id='fdx',filename='test.fdx',original_base64=base64.b64encode(FIXTURE.read_bytes()).decode())])
        await chat('select all')
        for character,voice in [('MIRA','mock-1'),('JONAH','mock-2'),('GUARD (NORTH)','mock-3')]:
            await chat(f'cast {character} as {voice}')
        await chat('confirm cast')
        return repo,provider,w,chat

    async def test_complete_workflow_duplicate_restart_download_and_timing(self):
        with tempfile.TemporaryDirectory() as d:
            repo,p,w,chat=await self.setup_workflow(d)
            await chat('plan'); self.assertEqual(p.calls,[])
            await chat('generate'); ident=repo.session('a','chat')[1]['job_id']
            await chat('generate'); self.assertEqual(repo.session('a','chat')[1]['job_id'],ident)
            await w.jobs.tick()
            self.assertEqual(sum(c['status']=='completed' for c in w.jobs.status('a',ident)['chunks']),1)
            w=Workflow(Repository(d),p)
            await w.jobs.tick()
            job=w.jobs.status('a',ident)
            self.assertEqual(job['status'],'completed')
            self.assertEqual(len(p.calls),2)
            assets=[a for a in repo.list('artifact','a') if a.get('job_id')==ident]
            self.assertEqual({a['mime'] for a in assets},{'audio/mpeg','application/json'})
            audio=next(a for a in assets if a['mime']=='audio/mpeg')
            self.assertGreater(len(repo.artifact_path(audio['id'],'a')[1].read_bytes()),1000)
            with self.assertRaises(NotFound): repo.artifact_path(audio['id'],'b')
            with self.assertRaises(NotFound): w.jobs.status('b',ident)
            first_chunk=job['chunks'][0]['chunk']
            calls=len(p.calls)
            await w.chat('a',ChatRequest(chat_id='chat',message=f'regenerate chunk {first_chunk} with restrained'))
            revised=repo.session('a','chat')[1]['job_id']
            self.assertNotEqual(revised,ident)
            await w.jobs.tick()
            self.assertEqual(w.jobs.status('a',revised)['status'],'completed')
            self.assertEqual(len(p.calls),calls+1)
            self.assertEqual(w.jobs.status('a',ident)['status'],'completed')
            with repo.connect(immediate=True) as db:
                db.execute("UPDATE jobs SET status='partial_failed' WHERE id=?",(ident,))
            calls=len(p.calls)
            w.jobs.retry('a',ident,())
            await w.jobs.tick()
            self.assertEqual(w.jobs.status('a',ident)['status'],'completed')
            self.assertEqual(len(p.calls),calls)

    async def test_rate_limit_backoff_retains_attempt_history(self):
        with tempfile.TemporaryDirectory() as d:
            repo,p,w,chat=await self.setup_workflow(d)
            await chat('plan'); await chat('generate'); ident=repo.session('a','chat')[1]['job_id']; original=p.render
            async def limited(chunk): raise ProviderError('rate_limit','Limit',30)
            p.render=limited
            await w.jobs.tick()
            job=w.jobs.status('a',ident)
            limited_chunk=job['chunks'][0]
            self.assertEqual(limited_chunk['status'],'pending')
            self.assertGreater(limited_chunk['retry_at'],__import__('time').time()+25)
            self.assertEqual(job['attempts'][0]['error'],'rate_limit')
            p.render=original
            with repo.connect(immediate=True) as db: db.execute('UPDATE chunks SET retry_at=0 WHERE job=?',(ident,))
            await w.jobs.tick(); await w.jobs.tick()
            self.assertEqual(w.jobs.status('a',ident)['status'],'completed')

    async def test_auth_stops_cancel_retry_and_uncertain_restart(self):
        with tempfile.TemporaryDirectory() as d:
            repo,p,w,chat=await self.setup_workflow(d)
            await chat('plan'); await chat('generate'); ident=repo.session('a','chat')[1]['job_id']
            original=p.render; calls=[]
            async def rejected(chunk): calls.append(chunk.id); raise ProviderError('authentication','Rejected')
            p.render=rejected
            await w.jobs.tick()
            self.assertEqual(len(calls),1); self.assertEqual(w.jobs.status('a',ident)['status'],'failed')
            failed=tuple(c['chunk'] for c in w.jobs.status('a',ident)['chunks'])
            w.jobs.retry('a',ident,failed); p.render=original
            await w.jobs.tick(); w.jobs.cancel('a',ident); await w.jobs.tick()
            self.assertEqual(w.jobs.status('a',ident)['status'],'cancelled')
            # Simulate a request accepted just before a worker process died.
            with repo.connect(immediate=True) as db:
                db.execute("UPDATE jobs SET status='running',lease_until=0,cancel=0 WHERE id=?",(ident,))
                db.execute("UPDATE chunks SET status='running' WHERE job=? AND status='pending'",(ident,))
            await w.jobs.tick()
            uncertain=tuple(c['chunk'] for c in w.jobs.status('a',ident)['chunks'] if c['status']=='ambiguous')
            self.assertTrue(uncertain)
            with self.assertRaises(Conflict): w.jobs.retry('a',ident,uncertain)
