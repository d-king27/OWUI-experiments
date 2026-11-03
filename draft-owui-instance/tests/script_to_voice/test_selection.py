import unittest
from script_to_voice.contracts import *
from script_to_voice.selection import resolve,parse_command,Clarification
from .test_parsing import parsed


class SelectionTests(unittest.TestCase):
    def test_complete_exact_and_empty(self):
        r=parsed()
        s=resolve(r,parse_command("all Mira's lines",r),'mira')
        self.assertEqual(len(s.selected_ids),3)
        one=resolve(r,IntentProposal(operation='select',scope='text',text='Then we go.'),'text')
        self.assertEqual(len(one.selected_ids),1)
        empty=resolve(r,IntentProposal(operation='select',scope='text',text='not present'),'empty')
        self.assertEqual(empty.selected_ids,())
        with self.assertRaises(Clarification): resolve(r,IntentProposal(),'question')
        with self.assertRaises(ValueError): resolve(r,IntentProposal(operation='select',scope='ids',ids=('invented',)),'bad')

    def test_scene_refine_ambiguity_and_context(self):
        r=parsed(); s=resolve(r,parse_command('select all',r),'all')
        night=resolve(r,parse_command('only night scenes',r),'night',s)
        self.assertEqual(len(night.selected_ids),3)
        self.assertFalse(set(night.selected_ids)&set(night.context_ids))
        self.assertEqual(len(resolve(r,parse_command('select scene 12A',r),'12A').selected_ids),3)
        r=r.model_copy(update={'scenes':tuple(s.model_copy(update={'heading':'EXT. ROOF'}) for s in r.scenes)})
        with self.assertRaises(Clarification): resolve(r,IntentProposal(operation='select',scope='scene',scene='roof'),'roof')
        with self.assertRaises(ValueError): night.validate_source(parsed('b'))

    def test_reload_two_users_two_scripts(self):
        import tempfile,asyncio,base64
        from script_to_voice.storage import Repository
        from script_to_voice.service.workflow import Workflow
        from script_to_voice.service.app import ChatRequest,ImportFile
        from .test_parsing import FIXTURE
        with tempfile.TemporaryDirectory() as d:
            repo=Repository(d); w=Workflow(repo)
            f=ImportFile(file_id='f',filename='test.fdx',original_base64=base64.b64encode(FIXTURE.read_bytes()).decode())
            for owner in ('a','b'):
                asyncio.run(w.chat(owner,ChatRequest(chat_id='same',message='import',files=[f])))
                asyncio.run(w.chat(owner,ChatRequest(chat_id='same',message='select all')))
            w=Workflow(Repository(d))
            result=asyncio.run(w.chat('a',ChatRequest(chat_id='same',message='only night scenes')))
            self.assertIn('Selected 3 lines',result['message'])
            a=repo.session('a','same')[1]; b=repo.session('b','same')[1]
            self.assertNotEqual(a['project_id'],b['project_id'])
            second=f.model_copy(update={'file_id':'second'})
            asyncio.run(w.chat('a',ChatRequest(chat_id='same',message='import',files=[second])))
            self.assertEqual(len(repo.list('revision','a')),2)
            self.assertEqual(repo.list('job','a'),[])
