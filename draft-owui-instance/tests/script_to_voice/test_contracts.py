import unittest
from pydantic import ValidationError
from script_to_voice.contracts import *


def revision():
    return ScriptRevision(id='r', owner_id='alice', project_id='p', script_id='s',
        original_file_id='f', original_hash='hash', title='Two voices',
        scenes=(Scene(id='scene', number='12A', heading='EXT. ROOF - NIGHT'),),
        characters=(Character(id='m', name='MIRA'), Character(id='j', name='JONAH')),
        elements=tuple(ScriptElement(id=f'e{i}', scene_id='scene', ordinal=i, kind='dialogue',
            original_text=t, search_text=t.casefold(), character_id=c,
            source_span=SourceSpan(paragraph=i+1, xpath=f'/Content/Paragraph[{i+1}]'))
            for i, (t,c) in enumerate([('Channel one is clear.', 'm'), ('Then we go.', 'j')])) )


class ContractsTests(unittest.TestCase):
    def test_roundtrip_and_hash(self):
        r = revision()
        self.assertEqual(r, ScriptRevision.model_validate_json(r.model_dump_json()))
        self.assertEqual(r.semantic_hash(), r.model_copy(update={'created_at': 99.0}).semantic_hash())
        with self.assertRaises(ValidationError):
            r.title = 'changed'

    def test_strict_and_foreign_ids(self):
        with self.assertRaises(ValidationError):
            IntentProposal(rewrite='bad')
        with self.assertRaises(ValidationError):
            IntentProposal(preceding='2')
        r = revision()
        s = Selection(id='sel', owner_id='alice', project_id='p', revision_id='r',
                      selected_ids=('e0',), query='first', version=1)
        s.validate_source(r)
        for changes in ({'selected_ids':('unknown',)}, {'owner_id':'bob'},
                        {'selected_ids':('e1','e0')}, {'context_ids':('e0',)}):
            with self.assertRaises(ValueError):
                s.model_copy(update=changes).validate_source(r)
        with self.assertRaises(ValidationError):
            ScriptRevision.model_validate_json(r.model_copy(update={'characters':()}).model_dump_json())

    def test_provider_body_excludes_internal_metadata(self):
        req=DialogueRequest(inputs=(DialogueInput(voice_id='v', text='Hello'),))
        self.assertEqual(req.provider_body(), {'model_id':'eleven_v4','inputs':[{'voice_id':'v','text':'Hello'}]})
