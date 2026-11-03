"""Offline large-script review definitions; not run during UX implementation."""
import unittest
import io
import zipfile

from script_to_voice.contracts import Annotation, Cast, CastAssignment, DirectionPlan
from script_to_voice.directing.compiler import compile_plan
from script_to_voice.parsing import parse_fdx
from script_to_voice.selection import parse_command, resolve
from script_to_voice.service.direction_review import detail_page, full_report, package_bytes, ready_message


class DirectionReviewTests(unittest.TestCase):
    def fixture(self):
        paragraphs=[]
        for scene in range(30):
            paragraphs.append(f'<Paragraph Type="Scene Heading" Number="{scene}A"><Text>EXT. LOCATION {scene} - NIGHT</Text></Paragraph>')
            for line in range(20):
                paragraphs.append(f'<Paragraph Type="Character"><Text>ROLE {line%12}</Text></Paragraph>')
                paragraphs.append(f'<Paragraph Type="Dialogue"><Text>Scene {scene}, exact source line {line}. 🌙</Text></Paragraph>')
        revision=parse_fdx(('<FinalDraft><Content>'+''.join(paragraphs)+'</Content></FinalDraft>').encode(),
                           'full.fdx',owner_id='owner',project_id='project',original_file_id='fdx')
        selection=resolve(revision,parse_command('select all',revision),'all')
        direction=DirectionPlan(id='direction',owner_id='owner',project_id='project',selection_id=selection.id,
                selection_version=selection.version,cast_version=1,version=1,
                annotations=tuple(Annotation(element_id=eid,offset=0,tag='whispering',origin='user')
                                  for eid in selection.selected_ids[:3]))
        return revision,selection,direction

    def test_package_retains_all_six_hundred_lines_without_an_inline_summary(self):
        revision,selection,direction=self.fixture()
        cast=Cast(id='cast',owner_id=revision.owner_id,project_id=revision.project_id,revision_id=revision.id,version=1,
                  assignments=tuple(CastAssignment(character_id=c.id,voice_id='v'+c.id) for c in revision.characters))
        plan=compile_plan(revision,selection,cast,direction)
        text=ready_message()
        self.assertLess(len(text),200)
        self.assertNotIn('ROLE',text)
        self.assertNotIn('By scene',text)
        data=package_bytes(revision,selection,direction,plan)
        self.assertEqual(data,package_bytes(revision,selection,direction,plan))
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            self.assertEqual(set(archive.namelist()),{'README.txt','line-direction.txt','render-plan.json'})
            report=archive.read('line-direction.txt').decode('utf-8')
            self.assertEqual(report,full_report(revision,selection,direction))
            self.assertEqual(archive.read('render-plan.json').decode('utf-8'),plan.model_dump_json(indent=2))
        lines=[e for e in revision.elements if e.id in selection.selected_ids]
        positions=[report.index(e.original_text) for e in lines]
        self.assertEqual(positions,sorted(positions))
        self.assertTrue(all(report.count(e.original_text)==1 for e in lines))

    def test_detail_pagination_and_scope_do_not_expand_selection(self):
        revision,selection,direction=self.fixture()
        first,next_offset=detail_page(revision,selection,direction,scope='character',value='ROLE 0')
        second,offset=detail_page(revision,selection,direction,scope='character',value='ROLE 0',offset=next_offset)
        self.assertEqual(next_offset,20)
        self.assertEqual(offset,40)
        self.assertIn('more direction',first)
        self.assertNotIn('**ROLE 1**',first)
        self.assertNotEqual(first,second)
        scene,_=detail_page(revision,selection,direction,scope='scene',value='29A')
        self.assertIn('Scene 29, exact source line 19.',scene)
        self.assertNotIn('Scene 28, exact source line',scene)
        restricted=selection.model_copy(update={'selected_ids':selection.selected_ids[:20]})
        with self.assertRaises(ValueError):
            detail_page(revision,restricted,direction,scope='scene',value='29A')
