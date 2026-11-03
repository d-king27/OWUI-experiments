import tempfile
import unittest
from script_to_voice.contracts import *
from script_to_voice.providers.fakes import FakePlanners,FakeVoiceProvider
from script_to_voice.service.workflow import Workflow,SelectRequest,PlanRequest
from script_to_voice.storage import Repository
from .test_parsing import parsed


class CountingPlanner(FakePlanners):
    model='test'
    def __init__(self): super().__init__(IntentProposal(operation='select',scope='character',character='MIRA')); self.calls=[]
    async def interpret(self,request,revision,prior=None):
        self.calls.append('intent'); return self.intent
    async def propose(self,request):
        self.calls.append('cast')
        return CastingProposal(assignments=tuple(CastAssignment(character_id=c,voice_id=request['voice_ids'][i],origin='catalog') for i,c in enumerate(request['character_ids'])))
    async def annotate(self,request):
        self.calls.append('direction'); return DirectionProposal(annotations=())


class PlannerWorkflowTests(unittest.IsolatedAsyncioTestCase):
    async def test_paid_work_is_cached_inspection_is_free_and_missing_cast_blocks_first(self):
        with tempfile.TemporaryDirectory() as d:
            repo=Repository(d); r=parsed(); repo.put('revision',r)
            planner=CountingPlanner(); w=Workflow(repo,FakeVoiceProvider(),planner)
            request=SelectRequest(revision_id=r.id,query='Please choose every line Mira speaks')
            selected=await w.select('a','p',request)
            await w.select('a','p',request)
            self.assertEqual(planner.calls,['intent'])
            await w.casting.proposals(r,selected,plan=False)
            self.assertEqual(planner.calls,['intent'])
            await w.casting.proposals(r,selected); await w.casting.proposals(r,selected)
            self.assertEqual(planner.calls,['intent','cast'])
            with self.assertRaises(ValueError): await w.plan('a','p',PlanRequest(selection_id=selected.id))
            self.assertNotIn('direction',planner.calls)
            await w.casting.assign(r,r.characters[0].id,'mock-1',1)
            first=await w.plan('a','p',PlanRequest(selection_id=selected.id))
            count=len(planner.calls)
            self.assertEqual(first,await w.plan('a','p',PlanRequest(selection_id=selected.id)))
            self.assertEqual(len(planner.calls),count)
