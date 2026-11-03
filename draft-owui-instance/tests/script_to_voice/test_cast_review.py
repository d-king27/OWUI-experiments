"""Offline casting-review regressions. Not executed during user-led UX iteration."""
import base64
import tempfile
import unittest
from unittest.mock import AsyncMock

from script_to_voice.contracts import CastAssignment, CastingProposal
from script_to_voice.providers.fakes import FakePlanners, FakeVoiceProvider
from script_to_voice.service.app import ChatRequest, ImportFile
from script_to_voice.service.cast_review import voice_reference
from script_to_voice.service.workflow import Workflow
from script_to_voice.storage import Repository
from .test_parsing import FIXTURE


class ProposedPlanner(FakePlanners):
    async def propose(self, request):
        return CastingProposal(assignments=tuple(CastAssignment(character_id=cid,
                   voice_id=request['voice_ids'][i],origin='catalog') for i,cid in enumerate(request['character_ids'])))


class CastReviewTests(unittest.IsolatedAsyncioTestCase):
    async def setup_review(self, directory):
        repo=Repository(directory); provider=FakeVoiceProvider(); planner=ProposedPlanner()
        planner.propose=AsyncMock(wraps=planner.propose)
        workflow=Workflow(repo,provider,planner)
        async def chat(message):
            return await workflow.chat('owner',ChatRequest(chat_id='review',message=message))
        file=ImportFile(file_id='fdx',filename='test.fdx',original_base64=base64.b64encode(FIXTURE.read_bytes()).decode())
        await workflow.chat('owner',ChatRequest(chat_id='review',message='import',files=[file]))
        return repo,provider,planner,workflow,chat

    async def test_default_proposals_updates_and_exact_confirmation(self):
        with tempfile.TemporaryDirectory() as directory:
            repo,provider,planner,w,chat=await self.setup_review(directory)
            response=await chat('select all')
            self.assertIn('Proposed casting',response['message'])
            self.assertIn('Mock voice 1',response['message'])
            self.assertIn('Are any of these characters already cast?',response['message'])
            state=repo.session('owner','review')[1]; r=w.revision('owner',state['project_id'],state['revision_id'])
            self.assertEqual(w.casting.latest(r).assignments,())
            await chat('help'); await chat('cast')
            self.assertEqual(planner.propose.await_count,1)
            await chat('yes')
            self.assertEqual(w.casting.latest(r).assignments,())
            await chat('MIRA: https://elevenlabs.io/app/voice-library?voiceId=mock-4\nJONAH: mock-5')
            self.assertEqual(w.casting.latest(r).assignments,())
            # Validate the whole group before any confirmed assignment is written.
            removed=provider.voices.pop('mock-5')
            await chat('confirm cast')
            self.assertEqual(w.casting.latest(r).assignments,())
            provider.voices['mock-5']=removed
            confirmed=await chat('confirm cast')
            self.assertIn('Step 4',confirmed['message'])
            cast=w.casting.latest(r)
            self.assertEqual(cast.version,2)
            self.assertEqual(len(cast.assignments),3)
            names={c.id:c.name for c in r.characters}
            self.assertEqual({names[a.character_id]:a.voice_id for a in cast.assignments},
                             {'MIRA':'mock-4','JONAH':'mock-5','GUARD (NORTH)':'mock-3'})
            self.assertEqual(provider.calls,[])

    async def test_cast_version_change_invalidates_review_and_generated_save_is_unassigned(self):
        with tempfile.TemporaryDirectory() as directory:
            repo,provider,planner,w,chat=await self.setup_review(directory)
            await chat('select all')
            state=repo.session('owner','review')[1]; r=w.revision('owner',state['project_id'],state['revision_id'])
            await w.casting.assign(r,r.characters[0].id,'mock-4',1)
            stale=await chat('confirm cast')
            self.assertIn('no longer current',stale['message'])
            self.assertEqual(w.casting.latest(r).version,2)
            self.assertEqual(len(w.casting.latest(r).assignments),1)
            await chat('single character'); await chat('MIRA')
            state=repo.session('owner','review')[1]; r=w.revision('owner',state['project_id'],state['revision_id'])
            await chat('design voice for MIRA: A calm measured conversational voice')
            preview=repo.list('voice_preview','owner',r.project_id)[0]
            await chat('save voice '+preview['id']+' as Chosen')
            self.assertEqual(w.casting.latest(r).assignments[0].voice_id,'mock-4')
            await chat('confirm cast')
            self.assertEqual(w.casting.latest(r).assignments[0].origin,'designed')
            self.assertEqual(provider.calls.count('save'),1)

    def test_voice_links_are_parsed_without_following_them(self):
        self.assertEqual(voice_reference('https://elevenlabs.io/app/voice-library?voiceId=abc123'),'abc123')
        self.assertEqual(voice_reference('https://elevenlabs.io/app/voice-lab/share/public/abc123'),'abc123')
        for value in ('https://example.com/voices/abc','https://elevenlabs.io.evil.test/voices/abc',
                      'https://elevenlabs.io/app/voice-library','https://elevenlabs.io/?voiceId=one&voiceId=two'):
            with self.assertRaises(ValueError): voice_reference(value)
