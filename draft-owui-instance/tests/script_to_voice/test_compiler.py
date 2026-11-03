import unittest
from script_to_voice.contracts import *
from script_to_voice.directing import make_direction
from script_to_voice.directing.compiler import compile_plan
from script_to_voice.selection import resolve,parse_command
from .test_parsing import parsed


class CompilerTests(unittest.TestCase):
    def test_full_script_fixture_complete_ordered_coverage(self):
        from script_to_voice.parsing import parse_fdx
        paragraphs=[]
        for scene in range(30):
            paragraphs.append(f'<Paragraph Type="Scene Heading" Number="{scene}A"><Text>EXT. LOCATION {scene} - NIGHT</Text></Paragraph>')
            for line in range(20):
                paragraphs.append(f'<Paragraph Type="Character"><Text>ROLE {line%12}</Text></Paragraph>')
                paragraphs.append(f'<Paragraph Type="Dialogue"><Text>Scene {scene}, exact source line {line}. 🌙</Text></Paragraph>')
        original=('<FinalDraft><Content>'+''.join(paragraphs)+'</Content></FinalDraft>').encode()
        r=parse_fdx(original,'full.fdx',owner_id='a',project_id='full',original_file_id='f')
        s=resolve(r,parse_command('select all',r),'full script')
        c=Cast(id='cast',owner_id='a',project_id='full',revision_id=r.id,version=1,
            assignments=tuple(CastAssignment(character_id=x.id,voice_id='v'+x.id) for x in r.characters))
        plan=compile_plan(r,s,c,make_direction(r,s,c))
        fragments=[f for ch in plan.chunks for f in ch.fragments]
        self.assertEqual(len(s.selected_ids),600)
        self.assertEqual([f.element_id for f in fragments],list(s.selected_ids))
        self.assertEqual(len(plan.chunks),60)

    def build(self,text=None):
        r=parsed()
        if text is not None:
            line=next(e for e in r.elements if e.kind=='dialogue')
            r=r.model_copy(update={'elements':tuple(e.model_copy(update={'original_text':text}) if e.id==line.id else e for e in r.elements)})
        s=resolve(r,parse_command('select all',r),'all')
        c=Cast(id='c',owner_id=r.owner_id,project_id=r.project_id,revision_id=r.id,version=1,
               assignments=tuple(CastAssignment(character_id=x.id,voice_id='voice-'+x.id) for x in r.characters))
        return r,s,c,make_direction(r,s,c)

    def test_boundaries_unicode_huge_and_coverage(self):
        for n in (1999,2000,2001,12000):
            r,s,c,d=self.build('🌙'*n)
            p=compile_plan(r,s,c,d)
            self.assertEqual(p,compile_plan(r,s,c,d))
            self.assertTrue(all(sum(len(i.text) for i in ch.request.inputs)<=2000 for ch in p.chunks))
            first=s.selected_ids[0]
            fragments=[f for ch in p.chunks for f in ch.fragments if f.element_id==first]
            self.assertEqual(''.join(next(e for e in r.elements if e.id==first).original_text[f.start:f.end] for f in fragments),'🌙'*n)

    def test_stale_missing_empty_and_scene_boundaries(self):
        r,s,c,d=self.build()
        p=compile_plan(r,s,c,d)
        self.assertEqual(len({ch.scene_id for ch in p.chunks}),2)
        with self.assertRaises(ValueError): compile_plan(r,s,c.model_copy(update={'version':2}),d)
        with self.assertRaises(ValueError): compile_plan(r,s,c.model_copy(update={'assignments':()}),d)
        empty=s.model_copy(update={'selected_ids':()})
        with self.assertRaises(ValueError): compile_plan(r,empty,c,d)

    def test_eleven_voices_and_discontiguous_selection(self):
        r,s,c,d=self.build()
        source=next(e for e in r.elements if e.kind=='dialogue')
        characters=tuple(Character(id=f'char-{i}',name=f'ROLE {i}') for i in range(11))
        elements=tuple(source.model_copy(update={'id':f'line-{i}','ordinal':i,'character_id':f'char-{i}',
            'parenthetical_ids':(),'original_text':f'Line {i}.'}) for i in range(11))
        r=r.model_copy(update={'characters':characters,'elements':elements})
        s=resolve(r,parse_command('select all',r),'all')
        c=c.model_copy(update={'assignments':tuple(CastAssignment(character_id=x.id,voice_id='v'+x.id) for x in characters)})
        d=make_direction(r,s,c); p=compile_plan(r,s,c,d)
        self.assertEqual(len(p.chunks),2)
        self.assertTrue(all(len({i.voice_id for i in ch.request.inputs})<=10 for ch in p.chunks))
        s=s.model_copy(update={'selected_ids':('line-0','line-10')})
        d=make_direction(r,s,c); p=compile_plan(r,s,c,d)
        self.assertEqual([f.element_id for ch in p.chunks for f in ch.fragments],['line-0','line-10'])
