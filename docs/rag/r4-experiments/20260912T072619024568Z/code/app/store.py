import sqlite3
import json
import uuid
from datetime import datetime, timezone
from contextlib import contextmanager


def uid(): return uuid.uuid4().hex

def now(): return datetime.now(timezone.utc).isoformat()

def dumps(obj): return json.dumps(obj, ensure_ascii=False, allow_nan=False)

SCHEMA = '''
CREATE TABLE IF NOT EXISTS courses(id TEXT PRIMARY KEY,name TEXT NOT NULL,created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS documents(id TEXT PRIMARY KEY,course_id TEXT NOT NULL REFERENCES courses(id),name TEXT NOT NULL,sha256 TEXT NOT NULL,status TEXT NOT NULL,pages INTEGER NOT NULL,created_at TEXT NOT NULL,UNIQUE(course_id,sha256));
CREATE TABLE IF NOT EXISTS chunks(id TEXT PRIMARY KEY,document_id TEXT NOT NULL REFERENCES documents(id),page INTEGER NOT NULL,text TEXT NOT NULL,vector TEXT,embedding_signature TEXT);
CREATE TABLE IF NOT EXISTS chunk_metadata(chunk_id TEXT PRIMARY KEY REFERENCES chunks(id) ON DELETE CASCADE,metadata TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS document_chunking(document_id TEXT PRIMARY KEY REFERENCES documents(id),configuration TEXT NOT NULL,updated_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS jobs(id TEXT PRIMARY KEY,request_key TEXT UNIQUE NOT NULL,kind TEXT NOT NULL,payload TEXT NOT NULL,status TEXT NOT NULL,result TEXT,error TEXT,created_at TEXT NOT NULL,updated_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS contents(id TEXT PRIMARY KEY,course_id TEXT NOT NULL REFERENCES courses(id),job_id TEXT NOT NULL,version INTEGER NOT NULL DEFAULT 1,status TEXT NOT NULL,asset TEXT NOT NULL,sources TEXT NOT NULL,config TEXT NOT NULL,created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS revisions(content_id TEXT NOT NULL,version INTEGER NOT NULL,asset TEXT NOT NULL,created_at TEXT NOT NULL,PRIMARY KEY(content_id,version));
CREATE TABLE IF NOT EXISTS media(id TEXT PRIMARY KEY,content_id TEXT NOT NULL REFERENCES contents(id),version INTEGER NOT NULL,kind TEXT NOT NULL,path TEXT NOT NULL,mime TEXT NOT NULL,status TEXT NOT NULL,metadata TEXT NOT NULL,created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS evaluations(id TEXT PRIMARY KEY,content_id TEXT NOT NULL,version INTEGER NOT NULL,metrics TEXT NOT NULL,created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS calls(id TEXT PRIMARY KEY,job_id TEXT,capability TEXT NOT NULL,model TEXT NOT NULL,status TEXT NOT NULL,usage TEXT NOT NULL,created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS job_evidence(job_id TEXT PRIMARY KEY REFERENCES jobs(id),evidence TEXT NOT NULL,updated_at TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS ix_chunks_document ON chunks(document_id);
'''

class Conflict(Exception): pass

class Store:
    def __init__(self, directory):
        directory.mkdir(parents=True, exist_ok=True)
        self.path = directory / 'studio.sqlite3'
        with self.connect() as db:
            db.execute('PRAGMA journal_mode=WAL')
            db.executescript(SCHEMA)
            # Additive migration: retain existing courses, drafts and call history.
            columns={row['name'] for row in db.execute('PRAGMA table_info(calls)')}
            for name,kind in [('duration_ms','INTEGER'),('http_status','INTEGER'),('response_model','TEXT')]:
                if name not in columns:db.execute(f'ALTER TABLE calls ADD COLUMN {name} {kind}')

    @contextmanager
    def connect(self):
        db = sqlite3.connect(self.path, timeout=10)
        db.row_factory = sqlite3.Row
        db.execute('PRAGMA foreign_keys=ON')
        try:
            yield db
            db.commit()
        except Exception:
            db.rollback()
            raise
        finally: db.close()

    def all(self, sql, args=()):
        with self.connect() as db: return [dict(r) for r in db.execute(sql,args).fetchall()]
    def one(self, sql, args=()):
        rows=self.all(sql,args);return rows[0] if rows else None
    def execute(self, sql, args=()):
        with self.connect() as db: return db.execute(sql,args).rowcount

    @staticmethod
    def decode_chunk(row):
        row = dict(row)
        value = row.pop('chunk_metadata_json', None)
        try:
            metadata = json.loads(value) if value else {}
        except (TypeError, ValueError):
            metadata = {}
        row['metadata'] = metadata if isinstance(metadata, dict) else {}
        return row

    def document_chunks(self, document_id):
        return [self.decode_chunk(row) for row in self.all('''
            SELECT c.*,m.metadata AS chunk_metadata_json FROM chunks c
            LEFT JOIN chunk_metadata m ON m.chunk_id=c.id
            WHERE c.document_id=? ORDER BY c.page,c.rowid''', (document_id,))]

    def chunking_configuration(self, document_id):
        row = self.one('SELECT configuration FROM document_chunking WHERE document_id=?', (document_id,))
        if not row: return None
        try: return json.loads(row['configuration'])
        except (TypeError, ValueError): return None

    @staticmethod
    def save_chunks(db, document_id, chunks, configuration, *, signature=None):
        """Caller owns the transaction; side tables keep old six-column rows readable."""
        db.executemany('INSERT INTO chunks VALUES(?,?,?,?,?,?)',
            [(c['id'], document_id, c['page'], c['text'],
              dumps(c['vector']) if 'vector' in c else None, signature) for c in chunks])
        db.executemany('INSERT INTO chunk_metadata VALUES(?,?)',
            [(c['id'], dumps(c.get('metadata', {}))) for c in chunks])
        db.execute('''INSERT INTO document_chunking VALUES(?,?,?)
            ON CONFLICT(document_id) DO UPDATE SET configuration=excluded.configuration,updated_at=excluded.updated_at''',
            (document_id, dumps(configuration), now()))

    def save_job_evidence(self, job_id, evidence):
        self.execute('INSERT INTO job_evidence VALUES(?,?,?) ON CONFLICT(job_id) DO UPDATE SET evidence=excluded.evidence,updated_at=excluded.updated_at',
                     (job_id,dumps(evidence),now()))

    def calls_for_job(self, job_id):
        from .providers import safe_usage
        rows=self.all('SELECT capability,model,status,usage,created_at,duration_ms,http_status,response_model FROM calls WHERE job_id=? ORDER BY created_at',(job_id,))
        for row in rows:
            # Older databases may contain unfiltered upstream usage metadata.
            try:row['usage']=safe_usage(json.loads(row['usage']))
            except (TypeError,ValueError):row['usage']={}
        return rows

    def job(self, key, kind, payload):
        encoded=dumps(payload)
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            old=db.execute('SELECT * FROM jobs WHERE request_key=?',(key,)).fetchone()
            if old:
                if old['kind']!=kind or old['payload']!=encoded: raise Conflict('重复请求标识对应不同参数')
                return dict(old),False
            row=dict(id=uid(),request_key=key,kind=kind,payload=encoded,status='queued',result=None,error=None,created_at=now(),updated_at=now())
            db.execute('INSERT INTO jobs VALUES(:id,:request_key,:kind,:payload,:status,:result,:error,:created_at,:updated_at)',row)
            return row,True

    def reserve_call(self, job_id, capability, model, limit):
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            date=now()[:10]
            count=db.execute('SELECT count(*) FROM calls WHERE substr(created_at,1,10)=?',(date,)).fetchone()[0]
            if count>=limit: raise ValueError('今日 API 调用次数已达到本地上限；次日 UTC 重置或调整配置。')
            call_id=uid()
            db.execute('INSERT INTO calls(id,job_id,capability,model,status,usage,created_at) VALUES(?,?,?,?,?,?,?)',(call_id,job_id,capability,model,'started','{}',now()))
            return call_id
