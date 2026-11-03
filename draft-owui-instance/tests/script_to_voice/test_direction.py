import unittest
from script_to_voice.contracts import *
from script_to_voice.directing import make_direction
from script_to_voice.selection import resolve,parse_command
from .test_parsing import parsed


class DirectionTests(unittest.TestCase):
    def test_source_evidence_sparse_override_and_unicode(self):
        r=parsed(); s=resolve(r,parse_command('select all',r),'all')
        cast=Cast(id='c',owner_id=r.owner_id,project_id=r.project_id,revision_id=r.id,version=1)
        plan=make_direction(r,s,cast)
        self.assertTrue(any(a.tag=='whispering' and a.evidence_ids for a in plan.annotations))
        self.assertFalse(any(a.element_id==s.selected_ids[2] for a in plan.annotations))
        changed=make_direction(r,s,cast,overrides=(Annotation(element_id=s.selected_ids[0],offset=0,tag='restrained',origin='user'),),version=2)
        self.assertEqual([a.tag for a in changed.annotations if a.element_id==s.selected_ids[0]],['restrained'])
        self.assertNotEqual(plan.id,changed.id)
        with self.assertRaises(ValueError): Annotation(element_id='x',offset=0,tag='[rewrite everything]')
        with self.assertRaises(ValueError): make_direction(r,s,cast,overrides=(Annotation(element_id=s.selected_ids[0],offset=999,tag='pause'),))
        self.assertEqual(r,parsed())
