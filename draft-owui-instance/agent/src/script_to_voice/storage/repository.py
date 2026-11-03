from __future__ import annotations
from contextlib import contextmanager
import hashlib
import json
from pathlib import Path
import sqlite3
import uuid


class NotFound(ValueError):
    pass


class Conflict(ValueError):
    pass


class Repository:
    """Owner-scoped objects and atomic session updates; no provider I/O in transactions."""
    def __init__(self, root):
        self.root = Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        self.artifacts = self.root / 'artifacts'
        self.artifacts.mkdir(exist_ok=True)
        self.database = self.root / 'stv.sqlite3'
        with self.connect() as db:
            db.execute('PRAGMA journal_mode=WAL')
            version = db.execute('PRAGMA user_version').fetchone()[0]
            if version > 3:
                raise RuntimeError('Database is newer than this application')
            db.executescript('''
                CREATE TABLE IF NOT EXISTS objects (
                    id TEXT PRIMARY KEY, owner TEXT NOT NULL, kind TEXT NOT NULL,
                    project TEXT, body TEXT NOT NULL);
                CREATE INDEX IF NOT EXISTS objects_owner ON objects(owner,kind,project);
                CREATE TABLE IF NOT EXISTS sessions (
                    owner TEXT NOT NULL, chat TEXT NOT NULL, version INTEGER NOT NULL,
                    body TEXT NOT NULL, PRIMARY KEY(owner,chat));
                CREATE TABLE IF NOT EXISTS jobs (
                    id TEXT PRIMARY KEY, owner TEXT NOT NULL, plan_id TEXT NOT NULL,
                    plan_hash TEXT NOT NULL, idem TEXT NOT NULL, budget INTEGER NOT NULL,
                    status TEXT NOT NULL, cancel INTEGER NOT NULL DEFAULT 0,
                    lease TEXT, lease_until REAL, created REAL NOT NULL,
                    UNIQUE(owner,idem));
                CREATE TABLE IF NOT EXISTS chunks (
                    job TEXT NOT NULL, chunk TEXT NOT NULL, ordinal INTEGER NOT NULL,
                    status TEXT NOT NULL, asset TEXT, attempts INTEGER NOT NULL DEFAULT 0,
                    retry_at REAL NOT NULL DEFAULT 0, error TEXT,
                    PRIMARY KEY(job,chunk));
                CREATE TABLE IF NOT EXISTS attempts (
                    id TEXT PRIMARY KEY, job TEXT NOT NULL, chunk TEXT NOT NULL,
                    number INTEGER NOT NULL, payload_hash TEXT NOT NULL,
                    outcome TEXT NOT NULL, request_id TEXT, error TEXT, usage INTEGER,
                    created REAL NOT NULL);
                CREATE TABLE IF NOT EXISTS actions (
                    owner TEXT NOT NULL, key TEXT NOT NULL, payload_hash TEXT NOT NULL,
                    status TEXT NOT NULL, body TEXT, PRIMARY KEY(owner,key));
                CREATE TABLE IF NOT EXISTS planner_budget (
                    id TEXT PRIMARY KEY, model TEXT NOT NULL, reserved INTEGER NOT NULL CHECK(reserved>=0),
                    created REAL NOT NULL);
                CREATE TABLE IF NOT EXISTS planner_usage (
                    reservation TEXT PRIMARY KEY, outcome TEXT NOT NULL, input_tokens INTEGER,
                    output_tokens INTEGER, estimated_microdollars INTEGER, request_id TEXT,
                    elapsed REAL NOT NULL, stop_reason TEXT);
                PRAGMA user_version=3;
            ''')

    @contextmanager
    def connect(self, immediate=False):
        db = sqlite3.connect(self.database, timeout=15)
        db.row_factory = sqlite3.Row
        db.execute('PRAGMA foreign_keys=ON')
        try:
            if immediate:
                db.execute('BEGIN IMMEDIATE')
            yield db
            db.commit()
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    def put(self, kind, value, *, replace=False):
        body = value.model_dump(mode='json') if hasattr(value, 'model_dump') else value
        with self.connect(immediate=True) as db:
            old = db.execute('SELECT owner,kind,body FROM objects WHERE id=?', (body['id'],)).fetchone()
            if old:
                if old['owner'] != body['owner_id'] or old['kind'] != kind:
                    raise NotFound('Object unavailable')
                if not replace and json.loads(old['body']) != body:
                    raise Conflict('Immutable artifact already exists')
            db.execute('INSERT INTO objects VALUES(?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET body=excluded.body',
                       (body['id'], body['owner_id'], kind, body.get('project_id'), json.dumps(body)))
        return body

    def claim_action(self, owner, key, payload_hash):
        with self.connect(immediate=True) as db:
            old=db.execute('SELECT * FROM actions WHERE owner=? AND key=?',(owner,key)).fetchone()
            if old:
                if old['payload_hash']!=payload_hash: raise Conflict('Action key was reused with different parameters')
                if old['status']!='completed': raise Conflict('Action outcome uncertain or still running; inspect before retrying')
                return json.loads(old['body'])
            db.execute('INSERT INTO actions VALUES(?,?,?,?,?)',(owner,key,payload_hash,'started',None))
        return None

    def complete_action(self,owner,key,result):
        with self.connect(immediate=True) as db:
            db.execute('UPDATE actions SET status=?,body=? WHERE owner=? AND key=?',
                       ('completed',json.dumps(result),owner,key))

    def get(self, kind, ident, owner):
        with self.connect() as db:
            row = db.execute('SELECT body FROM objects WHERE id=? AND owner=? AND kind=?', (ident,owner,kind)).fetchone()
        if not row:
            raise NotFound('Object unavailable')
        return json.loads(row['body'])

    def list(self, kind, owner, project=None):
        with self.connect() as db:
            rows = db.execute('SELECT body FROM objects WHERE owner=? AND kind=? AND (? IS NULL OR project=?) ORDER BY rowid',
                              (owner,kind,project,project)).fetchall()
        return [json.loads(r['body']) for r in rows]

    def typed(self, cls, kind, ident, owner):
        return cls.model_validate_json(json.dumps(self.get(kind, ident, owner)))

    def session(self, owner, chat):
        with self.connect() as db:
            row = db.execute('SELECT version,body FROM sessions WHERE owner=? AND chat=?',(owner,chat)).fetchone()
        return (row['version'],json.loads(row['body'])) if row else (0,{})

    def save_session(self, owner, chat, body, expected):
        with self.connect(immediate=True) as db:
            row = db.execute('SELECT version FROM sessions WHERE owner=? AND chat=?',(owner,chat)).fetchone()
            if (row['version'] if row else 0) != expected:
                raise Conflict('Session changed; retry using current state')
            db.execute('INSERT INTO sessions VALUES(?,?,?,?) ON CONFLICT(owner,chat) DO UPDATE SET version=excluded.version,body=excluded.body',
                       (owner,chat,expected+1,json.dumps(body)))

    def store_bytes(self, owner, project, data, mime, filename, **metadata):
        if len(data) > 64*1024*1024:
            raise ValueError('Artifact exceeds 64 MiB limit')
        sha = hashlib.sha256(data).hexdigest()
        path = self.artifacts / sha
        if not path.exists():
            temp = self.artifacts / (uuid.uuid4().hex+'.tmp')
            temp.write_bytes(data)
            temp.replace(path)
        body = dict(id=uuid.uuid4().hex, owner_id=owner, project_id=project,
                    content_hash=sha, stored_path=sha, mime=mime, filename=Path(filename).name,
                    size=len(data), **metadata)
        self.put('artifact', body)
        return body

    def artifact_path(self, ident, owner):
        body = self.get('artifact',ident,owner)
        relative = body['stored_path']
        if len(relative) != 64 or any(c not in '0123456789abcdef' for c in relative):
            raise NotFound('Artifact unavailable')
        path = (self.artifacts / relative).resolve()
        if path.parent != self.artifacts or not path.is_file():
            raise NotFound('Artifact unavailable')
        return body,path
