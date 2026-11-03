"""Offline regression definitions for the guided journey; not run during UX deployment."""
import base64
import tempfile
import unittest
from unittest.mock import AsyncMock

from script_to_voice.providers.fakes import FakePlanners, FakeVoiceProvider
from script_to_voice.service.app import ChatRequest, ImportFile
from script_to_voice.service.workflow import Workflow
from script_to_voice.storage import Repository
from .test_parsing import FIXTURE


class JourneyTests(unittest.IsolatedAsyncioTestCase):
    def request(self, message, files=None):
        return ChatRequest(chat_id='journey', message=message, files=files or [])

    def file(self, ident='fdx'):
        return ImportFile(file_id=ident, filename='test.fdx',
                          original_base64=base64.b64encode(FIXTURE.read_bytes()).decode())

    async def test_navigation_does_not_dispatch_or_import_attached_files(self):
        with tempfile.TemporaryDirectory() as directory:
            repo=Repository(directory)
            planner=FakePlanners(); planner.interpret=AsyncMock(side_effect=AssertionError('Unexpected inference'))
            provider=FakeVoiceProvider(); provider.list_voices=AsyncMock(side_effect=AssertionError('Unexpected catalog'))
            workflow=Workflow(repo, provider, planner)
            for command in ('hello', 'help', 'what next', 'I picked the wrong model'):
                result=await workflow.chat('owner', self.request(command, [self.file()]))
                self.assertTrue(result['message'])
            self.assertEqual(repo.list('project', 'owner'), [])
            self.assertEqual(provider.calls, [])
            planner.interpret.assert_not_awaited()
            provider.list_voices.assert_not_awaited()

    async def test_plan_gate_stale_cast_and_selection_recovery(self):
        with tempfile.TemporaryDirectory() as directory:
            repo=Repository(directory); provider=FakeVoiceProvider()
            planner=FakePlanners(); planner.annotate=AsyncMock(wraps=planner.annotate)
            workflow=Workflow(repo, provider, planner)
            async def chat(command, files=None):
                return await workflow.chat('owner', self.request(command, files))
            self.assertIn('Step 2', (await chat('import', [self.file()]))['message'])
            self.assertIn('Step 3', (await chat('select all'))['message'])
            premature=await chat('generate')
            self.assertIn('proceed with line direction first', premature['message'])
            self.assertNotIn('job_id', repo.session('owner', 'journey')[1])
            for character, voice in [('MIRA','mock-1'), ('JONAH','mock-2'), ('GUARD (NORTH)','mock-3')]:
                await chat(f'cast {character} as {voice}')
            await chat('confirm cast')
            self.assertIn('Step 4', (await chat('help'))['message'])
            ready=await chat('yes')
            self.assertIn('direction package is ready', ready['message'])
            self.assertIn('Step 5', ready['message'])
            self.assertNotIn('By character',ready['message'])
            self.assertIn('direction-package.zip',[a['filename'] for a in ready['artifacts']])
            planned_calls=planner.annotate.await_count
            self.assertGreater(planned_calls, 0)
            await chat('show direction for character MIRA')
            await chat('direction summary')
            await chat('yes')
            self.assertEqual(planner.annotate.await_count,planned_calls)
            await chat('cast MIRA as mock-4')
            self.assertIn('confirm', (await chat('generate'))['message'])
            self.assertNotIn('job_id', repo.session('owner', 'journey')[1])
            await chat('confirm cast')
            await chat('plan')
            planned_calls=planner.annotate.await_count
            self.assertIn('Step 6', (await chat('generate'))['message'])
            self.assertEqual(planner.annotate.await_count, planned_calls)
            self.assertEqual(provider.calls, [])  # No worker is run in this test.
            self.assertIn('Step 2', (await chat('wrong selection'))['message'])
            state=repo.session('owner', 'journey')[1]
            self.assertNotIn('selection_id', state)
            self.assertNotIn('prepared_plan_id', state)
            self.assertIn('job_id', state)  # Navigation does not silently cancel work.

    async def test_new_file_batch_and_empty_selection_do_not_expand_scope(self):
        with tempfile.TemporaryDirectory() as directory:
            repo=Repository(directory); workflow=Workflow(repo, FakeVoiceProvider(), FakePlanners())
            result=await workflow.chat('owner', self.request('import', [self.file('one'), self.file('two')]))
            self.assertIn('one new FDX', result['message'])
            self.assertEqual(repo.list('project', 'owner'), [])
            await workflow.chat('owner', self.request('import', [self.file()]))
            await workflow.chat('owner', self.request('select all'))
            empty=await workflow.chat('owner', self.request('find "not present anywhere"'))
            self.assertIn('Selected 0 lines', empty['message'])
            self.assertIn('Step 2', empty['message'])

    async def test_plain_language_scope_choices_and_follow_ups_are_grounded_and_free(self):
        with tempfile.TemporaryDirectory() as directory:
            repo=Repository(directory); provider=FakeVoiceProvider(); planner=FakePlanners()
            planner.interpret=AsyncMock(side_effect=AssertionError('Menu should not use inference'))
            workflow=Workflow(repo, provider, planner)
            async def chat(message, files=None):
                return await workflow.chat('owner', self.request(message, files))
            imported=await chat('import', [self.file()])
            self.assertIn('Please specify one of the following', imported['message'])
            self.assertIn('A single scene', imported['message'])
            self.assertIn('Which scene', (await chat('a single scene'))['message'])
            self.assertIn('12A', (await chat('scenes'))['message'])
            scene=await chat('the rooftop at night')
            self.assertIn('Selected 3 lines', scene['message'])
            self.assertNotIn('selection_choice', repo.session('owner', 'journey')[1])
            self.assertIn('Which character', (await chat('single character'))['message'])
            await chat('Not a real character')
            state=repo.session('owner', 'journey')[1]
            self.assertEqual(state['selection_choice'], 'character')
            self.assertNotIn('selection_id', state)
            self.assertIn('Selected 3 lines', (await chat('Mira'))['message'])
            self.assertIn('Selected 5 lines', (await chat('entire script'))['message'])
            self.assertIn('Selected 2 lines', (await chat('single scene: 14'))['message'])
            self.assertIn('Selected 3 lines', (await chat('single character: MIRA'))['message'])
            await chat('single scene')
            unclear=await chat('the scene about a missing submarine')
            self.assertIn('Please specify one scene', unclear['message'])
            self.assertNotIn('selection_id', repo.session('owner', 'journey')[1])
            self.assertIn('Selected 5 lines', (await chat('entire script'))['message'])
            self.assertEqual(provider.calls, [])
            planner.interpret.assert_not_awaited()
