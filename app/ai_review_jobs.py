"""Version-bound review scheduling, idempotent across tabs and automatic triggers."""
import hashlib
import json
import logging

from .ai_review import prepare_review, fingerprint
from .store import Conflict, dumps, now, uid


def submit_review(pipeline, content_id, version, owner_id, request_key):
    store = pipeline.store
    key = hashlib.sha256(dumps([owner_id, request_key]).encode()).hexdigest()

    def previous(db):
        row = db.execute('''SELECT r.*,j.status FROM ai_review_requests r
            JOIN jobs j ON j.id=r.job_id WHERE r.request_key=? AND r.owner_id=?''', (key,owner_id)).fetchone()
        if row and (row['content_id'] != content_id or row['version'] != version):
            raise Conflict('重复请求标识对应不同参数')
        return {'job_id':row['job_id'],'status':row['status'],'reused':True} if row else None

    with store.connect() as db:
        old = previous(db)
        if old:
            return old
    current = store.one('SELECT version FROM contents WHERE id=?', (content_id,))
    if not current or current['version'] != version:
        raise Conflict('内容已更新，请刷新后重新审核。')
    frozen = prepare_review(store, content_id, version)
    if frozen['owner_id'] != owner_id:
        raise ValueError('材料不属于当前账号。')
    created = False
    with store.connect() as db:
        db.execute('BEGIN IMMEDIATE')
        old = previous(db)
        if old:
            return old
        row = db.execute('''SELECT c.* FROM contents c JOIN course_owners o ON o.course_id=c.course_id
            WHERE c.id=? AND o.user_id=?''', (content_id,owner_id)).fetchone()
        if not row or row['version'] != version:
            raise Conflict('内容已更新，请刷新后重新审核。')
        if any(fingerprint(json.loads(row[field])) != frozen[field+'_sha256'] for field in ('asset','sources','config')):
            raise Conflict('内容已更新，请刷新后重新审核。')
        active = db.execute('''SELECT j.id,j.status FROM jobs j JOIN job_owners o ON o.job_id=j.id
            WHERE j.kind='review_content' AND j.status IN ('queued','running') AND o.user_id=?
            AND json_extract(j.payload,'$.content_id')=? AND json_extract(j.payload,'$.version')=?
            ORDER BY j.created_at DESC LIMIT 1''', (owner_id,content_id,version)).fetchone()
        if active:
            job_id, status = active['id'], active['status']
        else:
            if row['status'] != 'draft':
                raise Conflict('当前版本已确认，无需重复审核。')
            pending = db.execute('''SELECT count(*) FROM jobs j JOIN job_owners o ON o.job_id=j.id
                WHERE o.user_id=? AND j.status IN ('queued','running')''', (owner_id,)).fetchone()[0]
            if pending >= store.max_pending_jobs_per_account:
                raise Conflict('当前账号等待或执行中的任务已达上限，请等待完成或取消部分任务。')
            job_id, status, stamp = uid(), 'queued', now()
            db.execute('INSERT INTO jobs VALUES(?,?,?,?,?,?,?,?,?)',
                (job_id,'ai-review:'+job_id,'review_content',dumps(frozen),status,None,None,stamp,stamp))
            db.execute('INSERT INTO job_owners VALUES(?,?)', (job_id,owner_id))
            created = True
        db.execute('INSERT INTO ai_review_requests VALUES(?,?,?,?,?)', (key,owner_id,content_id,version,job_id))
        db.execute('DELETE FROM content_auto_review_errors WHERE content_id=? AND version=?', (content_id,version))
    if created:
        pipeline.enqueue(job_id)
    return {'job_id':job_id,'status':status,'reused':not created}


def schedule_automatic_review(pipeline, content_id, version, *, owner_id=None, origin_job_id=None):
    """A review problem must not turn a saved material into a failed generation."""
    try:
        if owner_id is None:
            owner = pipeline.store.one('SELECT user_id FROM job_owners WHERE job_id=?', (origin_job_id,))
            if not owner:
                raise ValueError('自动审核任务没有有效账号。')
            owner_id = owner['user_id']
        return submit_review(pipeline, content_id, version, owner_id,
                             f'automatic:{origin_job_id or "save"}:{content_id}:{version}')
    except Exception as exc:
        reason = str(exc) if isinstance(exc,(ValueError,Conflict)) else '自动 AI 审核未能启动，请手动重试。'
        try:
            pipeline.store.execute('''INSERT INTO content_auto_review_errors VALUES(?,?,?,?)
                ON CONFLICT(content_id,version) DO UPDATE SET message=excluded.message,created_at=excluded.created_at''',
                (content_id,version,reason[:500],now()))
        except Exception:
            logging.getLogger(__name__).warning('Could not record automatic review scheduling failure')
        return {'status':'failed','error':reason[:500]}
