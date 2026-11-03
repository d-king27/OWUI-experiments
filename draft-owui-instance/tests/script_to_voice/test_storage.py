import tempfile
import unittest
from fastapi.testclient import TestClient
from script_to_voice.storage import Repository, NotFound, Conflict
from script_to_voice.service.app import create_app


class StorageTests(unittest.TestCase):
    def test_restart_ownership_and_paths(self):
        with tempfile.TemporaryDirectory() as d:
            r=Repository(d)
            a=r.store_bytes('a','p',b'hello','text/plain','../safe.txt')
            r=Repository(d)
            self.assertEqual(r.artifact_path(a['id'],'a')[1].read_bytes(),b'hello')
            with self.assertRaises(NotFound): r.artifact_path(a['id'],'b')
            r.put('artifact',{**a,'stored_path':'../../secret'},replace=True)
            with self.assertRaises(NotFound): r.artifact_path(a['id'],'a')
            r.save_session('a','chat',{'project':'p'},0)
            with self.assertRaises(Conflict): r.save_session('a','chat',{},0)
            self.assertEqual(r.session('b','chat'),(0,{}))
            with r.connect() as db:
                self.assertEqual(db.execute('PRAGMA user_version').fetchone()[0],3)
                self.assertEqual(db.execute('PRAGMA journal_mode').fetchone()[0],'wal')

    def test_private_api_auth_and_restart(self):
        with tempfile.TemporaryDirectory() as d:
            token='test-token-'*4
            with TestClient(create_app(Repository(d),token)) as c:
                self.assertEqual(c.post('/v1/projects',json={'title':'test'}).status_code,401)
                h={'Authorization':'Bearer '+token,'X-STV-Owner':'alice'}
                p=c.post('/v1/projects',json={'title':'test'},headers=h).json()
                self.assertEqual(c.get('/v1/projects/'+p['id'],headers={**h,'X-STV-Owner':'bob'}).status_code,404)
                self.assertNotIn(token,c.get('/health').text)
            with TestClient(create_app(Repository(d),token)) as c:
                self.assertEqual(c.get('/v1/projects/'+p['id'],headers=h).json()['title'],'test')
