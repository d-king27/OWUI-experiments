import concurrent.futures
import tempfile
import unittest
from unittest.mock import patch
import httpx
from script_to_voice.storage import Repository
from script_to_voice.contracts import Project
from script_to_voice.providers.budget import PlannerBudget,BudgetError
from script_to_voice.providers.planning import TextPlanner,PlannerError
from .test_parsing import parsed


def ledger(repo,**kwargs):
    return PlannerBudget(repo,pricing_model='test-model',input_rate='1',output_rate='5',**kwargs)


class BudgetTests(unittest.TestCase):
    def test_restart_and_atomic_shared_cap(self):
        with tempfile.TemporaryDirectory() as d:
            repo=Repository(d); b=ledger(repo,total='0.10')
            def reserve(_):
                try: b.reserve('test-model','hello'); return True
                except BudgetError: return False
            with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
                self.assertEqual(sum(pool.map(reserve,range(8))),2)
            status=ledger(Repository(d),total='0.10').status()
            self.assertEqual(status['remaining_usd'],0)
            self.assertEqual(status['requests_reserved'],2)

    def test_rates_model_size_and_cost_fail_closed(self):
        with tempfile.TemporaryDirectory() as d:
            repo=Repository(d)
            for b,model,text in [(PlannerBudget(repo),'test-model','hi'),(ledger(repo),'other-model','hi'),
                                 (ledger(repo),'test-model','🌙'*5000),
                                 (ledger(repo,per_request='0.001'),'test-model','hi')]:
                with self.assertRaises(BudgetError): b.reserve(model,text)
            self.assertEqual(ledger(repo).status()['requests_reserved'],0)

    def test_migration_preserves_existing_objects(self):
        with tempfile.TemporaryDirectory() as d:
            repo=Repository(d); repo.put('project',Project(id='p',owner_id='a',title='Existing'))
            with repo.connect() as db: db.execute('PRAGMA user_version=1')
            repo=Repository(d)
            self.assertEqual(repo.get('project','p','a')['title'],'Existing')
            with repo.connect() as db: self.assertEqual(db.execute('PRAGMA user_version').fetchone()[0],3)


class PlannerBudgetTests(unittest.IsolatedAsyncioTestCase):
    async def test_repair_is_a_second_reservation_and_is_blocked_before_send(self):
        with tempfile.TemporaryDirectory() as d:
            calls=[]
            def respond(req):
                calls.append(req)
                return httpx.Response(200,json={'choices':[{'message':{'content':'bad JSON'}}]})
            b=ledger(Repository(d),total='0.05')
            planner=TextPlanner('https://test/v1','test-model',key='secret',budget=b,transport=httpx.MockTransport(respond))
            with self.assertRaises(PlannerError) as e: await planner.interpret('find',parsed())
            self.assertIn('allowance exhausted',str(e.exception))
            self.assertEqual(len(calls),1)
            self.assertEqual(b.status()['reserved_usd'],0.05)

    async def test_timeout_reservation_is_retained_and_live_default_is_disabled(self):
        with tempfile.TemporaryDirectory() as d:
            b=ledger(Repository(d))
            def timeout(req): raise httpx.ReadTimeout('private')
            planner=TextPlanner('https://test/v1','test-model',key='secret',budget=b,transport=httpx.MockTransport(timeout))
            with self.assertRaises(PlannerError): await planner.interpret('find',parsed())
            self.assertEqual(b.status()['requests_reserved'],1)
            with patch.dict('os.environ',{'STV_LLM_ENABLED':'false'}):
                with self.assertRaises(PlannerError) as e:
                    await TextPlanner('https://test/v1','test-model',key='secret').interpret('find',parsed())
            self.assertIn('disabled',str(e.exception))
