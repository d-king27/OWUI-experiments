import json
import tempfile
import unittest
import httpx
from script_to_voice.providers.anthropic import AnthropicPlanner,provider_schema
from script_to_voice.providers.planning import PlannerError
from script_to_voice.contracts import IntentProposal
from script_to_voice.storage import Repository
from .test_planner_budget import ledger
from .test_parsing import parsed


def response(raw='{"operation":"select","scope":"character","character":"MIRA"}',stop='end_turn',model='test-model'):
    return {'model':model,'stop_reason':stop,'content':[{'type':'text','text':raw}],
            'usage':{'input_tokens':100,'output_tokens':30}}


class AnthropicTests(unittest.IsolatedAsyncioTestCase):
    async def test_followup_scene_filter_normalizes_without_expanding_selection(self):
        from script_to_voice.selection import resolve,parse_command
        r=parsed(); prior=resolve(r,parse_command('all Mira lines',r),'Mira')
        calls=[]
        def reply(req):
            calls.append(json.loads(req.content))
            return httpx.Response(200,json=response('{"operation":"select","scope":"scene","time_of_day":"NIGHT"}'))
        p=AnthropicPlanner('https://api.anthropic.com/v1','test-model',key='private',transport=httpx.MockTransport(reply))
        proposal=await p.interpret('Keep just those in scenes set at night',r,prior)
        self.assertEqual(proposal.scope,'filter')
        selected=resolve(r,proposal,'night',prior)
        self.assertEqual(len(selected.selected_ids),2)
        self.assertLessEqual(set(selected.selected_ids),set(prior.selected_ids))
        self.assertEqual(json.loads(calls[0]['messages'][0]['content'])['active_selection_ids'],list(prior.selected_ids))

    async def test_returned_character_id_is_exactly_resolved(self):
        from script_to_voice.selection import resolve
        r=parsed(); mira=next(c for c in r.characters if c.name=='MIRA')
        def reply(req):
            return httpx.Response(200,json=response(json.dumps({'operation':'select','scope':'character','character':mira.id})))
        p=AnthropicPlanner('https://api.anthropic.com/v1','test-model',key='private',transport=httpx.MockTransport(reply))
        proposal=await p.interpret('Select Mira',r)
        self.assertEqual(len(resolve(r,proposal,'Mira').selected_ids),3)

    async def test_native_payload_usage_and_source_validation(self):
        with tempfile.TemporaryDirectory() as d:
            b=ledger(Repository(d)); calls=[]
            def reply(req):
                calls.append(req); return httpx.Response(200,json=response(),headers={'request-id':'r'})
            p=AnthropicPlanner('https://api.anthropic.com/v1','test-model',key='private',budget=b,transport=httpx.MockTransport(reply))
            result=await p.interpret('Find every line Mira speaks',parsed())
            self.assertEqual(result.character,'MIRA')
            body=json.loads(calls[0].content)
            self.assertEqual(calls[0].url.path,'/v1/messages')
            self.assertEqual(calls[0].headers['x-api-key'],'private')
            self.assertEqual(calls[0].headers['anthropic-version'],'2023-06-01')
            self.assertNotIn('Authorization',calls[0].headers)
            self.assertNotIn('tools',body); self.assertNotIn('response_format',body)
            self.assertEqual(body['output_config']['format']['type'],'json_schema')
            self.assertEqual(b.status()['requests_with_reported_usage'],1)
            self.assertEqual(b.status()['reported_usage_estimate_usd'],0.00025)
            self.assertEqual(b.status()['reserved_usd'],0.05)

    async def test_refusal_truncation_model_mismatch_and_http_do_not_retry(self):
        for kind in ('refusal','max_tokens','mismatch',401,403,429,500):
            calls=[]
            def reply(req):
                calls.append(req)
                if isinstance(kind,int): return httpx.Response(kind,json={'private':'sensitive'})
                return httpx.Response(200,json=response(stop=kind if kind!='mismatch' else 'end_turn',model='other' if kind=='mismatch' else 'test-model'))
            p=AnthropicPlanner('https://api.anthropic.com/v1','test-model',key='private',transport=httpx.MockTransport(reply))
            with self.assertRaises(PlannerError) as error: await p.interpret('find',parsed())
            self.assertEqual(len(calls),1)
            self.assertNotIn('sensitive',str(error.exception))

    async def test_malformed_repair_and_unknown_ids(self):
        calls=[]
        def reply(req):
            calls.append(req); return httpx.Response(200,json=response('bad JSON' if len(calls)==1 else '{"operation":"select","scope":"ids","ids":["invented"]}'))
        p=AnthropicPlanner('https://api.anthropic.com/v1','test-model',key='private',transport=httpx.MockTransport(reply))
        with self.assertRaises(PlannerError): await p.interpret('find',parsed())
        self.assertEqual(len(calls),2)

    async def test_timeout_keeps_reservation_and_stops(self):
        with tempfile.TemporaryDirectory() as d:
            b=ledger(Repository(d))
            def reply(req): raise httpx.ReadTimeout('private')
            p=AnthropicPlanner('https://api.anthropic.com/v1','test-model',key='private',budget=b,transport=httpx.MockTransport(reply))
            with self.assertRaises(PlannerError): await p.interpret('find',parsed())
            self.assertEqual(b.status()['requests_reserved'],1)
            self.assertEqual(b.status()['requests_with_reported_usage'],0)

    def test_schema_bounds_remain_local(self):
        original=IntentProposal.model_json_schema(); simplified=provider_schema(original)
        self.assertEqual(original['properties']['preceding']['maximum'],20)
        self.assertNotIn('maximum',simplified['properties']['preceding'])
        self.assertIn('20',simplified['properties']['preceding']['description'])
        self.assertFalse(simplified['additionalProperties'])
