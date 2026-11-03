from pathlib import Path
import unittest
from script_to_voice.parsing import parse_fdx

FIXTURE=Path(__file__).parent/'fixtures/two_speakers.fdx'


def parsed(owner='a',project='p'):
    return parse_fdx(FIXTURE.read_bytes(),'two.fdx',owner_id=owner,project_id=project,original_file_id='file')


class ParserTests(unittest.TestCase):
    def test_import_duplicate_and_second_script(self):
        import tempfile,base64
        from script_to_voice.storage import Repository
        from script_to_voice.service.workflow import Workflow
        from script_to_voice.service.app import ImportFile
        from script_to_voice.contracts import Project
        with tempfile.TemporaryDirectory() as d:
            r=Repository(d); w=Workflow(r)
            r.put('project',Project(id='p',owner_id='a',title='test'))
            f=ImportFile(file_id='f',filename='a.fdx',original_base64=base64.b64encode(FIXTURE.read_bytes()).decode())
            first=w.import_script('a','p',f)
            self.assertEqual(first,w.import_script('a','p',f.model_copy(update={'file_id':'f2'})))
            changed=FIXTURE.read_bytes().replace(b'Then we go.',b'Wait here.')
            second=w.import_script('a','p',f.model_copy(update={'original_base64':base64.b64encode(changed).decode()}))
            self.assertNotEqual(first.id,second.id)
            self.assertEqual(len(r.list('revision','a','p')),2)

    def test_provenance_runs_aliases_parentheticals(self):
        r=parsed()
        self.assertEqual(r,parsed())
        self.assertEqual(r.scenes[0].number,'12A')
        lines=[e for e in r.elements if e.kind=='dialogue']
        self.assertEqual(lines[0].original_text,'Channel one is clear. 🌙')
        self.assertEqual(len(lines[0].parenthetical_ids),1)
        self.assertEqual(len(lines[1].parenthetical_ids),2)
        self.assertEqual(lines[0].character_id,lines[3].character_id)
        self.assertEqual(len(r.characters),3)
        self.assertNotEqual(r.id,parsed(project='other').id)
        self.assertNotEqual(r.elements[0].id,parsed(project='other').elements[0].id)

    def test_reject_bad_empty_entities(self):
        for content in [b'not xml',b'<FinalDraft>',b'<FinalDraft><Content/></FinalDraft>',
                        b'<!DOCTYPE x [<!ENTITY y SYSTEM "file:///secret">]><FinalDraft><Content>&y;</Content></FinalDraft>']:
            with self.assertRaises(ValueError):
                parse_fdx(content,'bad.fdx',owner_id='a',project_id='p',original_file_id='f')
