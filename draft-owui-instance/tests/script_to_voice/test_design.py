import tempfile
import unittest
from script_to_voice.contracts import VoiceDesignRequest
from script_to_voice.storage import Repository,Conflict
from script_to_voice.casting import CastingService
from script_to_voice.casting.design import DesignService
from script_to_voice.providers.fakes import FakeVoiceProvider
from .test_parsing import parsed


class DesignTests(unittest.IsolatedAsyncioTestCase):
    async def test_chosen_candidate_restart_dedup_and_preview_rejection(self):
        with tempfile.TemporaryDirectory() as d:
            repo=Repository(d); p=FakeVoiceProvider(); cast=CastingService(repo,p); service=DesignService(repo,p,cast); r=parsed()
            request=VoiceDesignRequest(voice_description='A calm measured conversational voice',text='A project excerpt for a voice preview. '*4)
            previews=await service.previews(r,r.characters[0].id,request,'one')
            self.assertEqual(len(previews),3)
            self.assertEqual(previews,await service.previews(r,r.characters[0].id,request,'one'))
            with self.assertRaises(ValueError): await cast.assign(r,r.characters[0].id,previews[0]['generated_voice_id'],1)
            saved=await service.save(r,previews[1]['id'],'Chosen','save')
            service=DesignService(Repository(d),p,CastingService(Repository(d),p))
            self.assertEqual(saved,await service.save(r,previews[1]['id'],'Chosen','different-click'))
            self.assertEqual(p.calls.count('save'),1)
            self.assertEqual(service.casting.latest(r).assignments,())
            await service.casting.assign(r,r.characters[0].id,saved['voice_id'],1,origin='designed')
            self.assertEqual(service.casting.latest(r).assignments[0].origin,'designed')

    async def test_uncertain_save_never_repeated(self):
        with tempfile.TemporaryDirectory() as d:
            repo=Repository(d); p=FakeVoiceProvider(); r=parsed(); service=DesignService(repo,p,CastingService(repo,p))
            previews=await service.previews(r,r.characters[0].id,VoiceDesignRequest(voice_description='A calm measured conversational voice',text='A project excerpt for a voice preview. '*4),'one')
            async def uncertain(*args): raise TimeoutError('uncertain')
            p.save_preview=uncertain
            with self.assertRaises(TimeoutError): await service.save(r,previews[0]['id'],'Chosen','save')
            with self.assertRaises(Conflict): await service.save(r,previews[0]['id'],'Chosen','save-again')
