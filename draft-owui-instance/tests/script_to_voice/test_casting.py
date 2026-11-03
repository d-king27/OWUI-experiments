import tempfile
import unittest
from script_to_voice.casting import CastingService
from script_to_voice.storage import Repository,Conflict
from script_to_voice.providers.fakes import FakeVoiceProvider
from script_to_voice.selection import resolve,parse_command
from .test_parsing import parsed


class CastingTests(unittest.IsolatedAsyncioTestCase):
    async def test_explicit_revision_reconciliation_preserves_target_and_rejects_foreign(self):
        from script_to_voice.parsing import parse_fdx
        from .test_parsing import FIXTURE
        with tempfile.TemporaryDirectory() as d:
            repo=Repository(d); c=CastingService(repo,FakeVoiceProvider()); source=parsed()
            target=parse_fdx(FIXTURE.read_bytes().replace(b'Then we go.',b'Wait here.'),'revision.fdx',
                owner_id=source.owner_id,project_id=source.project_id,original_file_id='new')
            await c.assign(source,source.characters[0].id,'mock-1',1)
            await c.assign(source,source.characters[1].id,'mock-2',2)
            await c.assign(target,target.characters[0].id,'mock-3',1)
            result=await c.reconcile(source,target,2)
            cast=c.latest(target)
            assignments={a.character_id:a for a in cast.assignments}
            self.assertEqual(assignments[target.characters[0].id].voice_id,'mock-3')
            self.assertEqual(assignments[target.characters[1].id].voice_id,'mock-2')
            self.assertEqual(len(result['reused_character_ids']),1)
            self.assertEqual(assignments[target.characters[1].id].audition_status,'pending')
            with self.assertRaises(ValueError): await c.reconcile(parsed('other'),target,cast.version)
            with self.assertRaises(Conflict): await c.reconcile(source,target,1)

    async def test_persistent_manual_cast_all_roles_and_audition(self):
        with tempfile.TemporaryDirectory() as d:
            repo=Repository(d); p=FakeVoiceProvider(); c=CastingService(repo,p); r=parsed()
            s=resolve(r,parse_command('select all',r),'all')
            proposals=await c.proposals(r,s)
            self.assertEqual(len(proposals['pending']),3)
            self.assertEqual(c.latest(r).assignments,())
            a=await c.assign(r,r.characters[0].id,'mock-1',1)
            c=CastingService(Repository(d),p)
            a=await c.assign(r,r.characters[1].id,'mock-2',a.version)
            self.assertEqual(a.assignments[0].voice_id,'mock-1'); self.assertTrue(a.assignments[0].locked)
            with self.assertRaises(ValueError): await c.assign(r,r.characters[2].id,'missing',a.version)
            with self.assertRaises(Conflict): await c.assign(r,r.characters[2].id,'mock-3',1)
            first=await c.audition(r,r.characters[0].id,'mock-1')
            self.assertEqual(first,await c.audition(r,r.characters[0].id,'mock-1'))
            self.assertEqual(len(p.calls),1)
            p.voices.pop('mock-1')
            self.assertNotIn('mock-1',{v.voice_id for v in await c.catalog(refresh=True)})
            with self.assertRaises(ValueError): await c.assign(r,r.characters[0].id,'mock-1',a.version)
