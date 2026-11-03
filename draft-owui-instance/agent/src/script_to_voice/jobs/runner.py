import asyncio
import json
import os
import time
import uuid
from script_to_voice.contracts import RenderPlan,digest
from script_to_voice.storage import NotFound,Conflict
from script_to_voice.providers.elevenlabs import ProviderError
from script_to_voice.audio.assembly import assemble


class Jobs:
    def __init__(self,repo,provider): self.repo=repo; self.provider=provider

    def enqueue(self,owner,plan_id,plan_hash,key,budget):
        plan=self.repo.typed(RenderPlan,'plan',plan_id,owner)
        if plan.semantic_hash()!=plan_hash: raise Conflict('Plan hash changed')
        if plan.estimated_characters>budget or budget>int(os.environ.get('STV_MAX_JOB_CHARACTERS','20000')):
            raise ValueError('Plan exceeds its authorized character budget')
        with self.repo.connect(immediate=True) as db:
            old=db.execute('SELECT * FROM jobs WHERE owner=? AND idem=?',(owner,key)).fetchone()
            if old:
                if old['plan_hash']!=plan_hash or old['budget']!=budget: raise Conflict('Submission key reused for another plan or budget')
                return dict(old)
            ident=uuid.uuid4().hex
            db.execute('INSERT INTO jobs(id,owner,plan_id,plan_hash,idem,budget,status,created) VALUES(?,?,?,?,?,?,?,?)',
                       (ident,owner,plan_id,plan_hash,key,budget,'queued',time.time()))
            for index,c in enumerate(plan.chunks):
                db.execute('INSERT INTO chunks(job,chunk,ordinal,status) VALUES(?,?,?,?)',(ident,c.id,index,'pending'))
        return self.status(owner,ident)

    def status(self,owner,ident):
        with self.repo.connect() as db:
            job=db.execute('SELECT * FROM jobs WHERE id=? AND owner=?',(ident,owner)).fetchone()
            if not job: raise NotFound('Job unavailable')
            chunks=[dict(r) for r in db.execute('SELECT * FROM chunks WHERE job=? ORDER BY ordinal',(ident,))]
            attempts=[dict(r) for r in db.execute('SELECT * FROM attempts WHERE job=? ORDER BY created',(ident,))]
        return {**dict(job),'chunks':chunks,'attempts':attempts}

    def cancel(self,owner,ident):
        self.status(owner,ident)
        with self.repo.connect(immediate=True) as db:
            db.execute("UPDATE jobs SET cancel=1,status=CASE WHEN status='queued' THEN 'cancelled' ELSE status END WHERE id=? AND owner=?",(ident,owner))
        return self.status(owner,ident)

    def retry(self,owner,ident,chunk_ids,allow_ambiguous=False):
        job=self.status(owner,ident)
        if job['status'] in ('queued','running'): raise Conflict('Job is still active')
        failed={c['chunk']:c for c in job['chunks'] if c['status'] in ('failed','ambiguous')}
        assembly_retry=not chunk_ids and all(c['status']=='completed' for c in job['chunks']) and job['status']=='partial_failed'
        if not assembly_retry and (not chunk_ids or not set(chunk_ids)<=set(failed)): raise ValueError('Choose failed chunk IDs explicitly')
        if any(failed[c]['status']=='ambiguous' for c in chunk_ids) and not allow_ambiguous:
            raise Conflict('Inspect provider history and explicitly accept duplicate billing risk before retrying uncertain work')
        with self.repo.connect(immediate=True) as db:
            for c in chunk_ids:
                db.execute("UPDATE chunks SET status='pending',retry_at=0,error=NULL WHERE job=? AND chunk=?",(ident,c))
            db.execute("UPDATE jobs SET status='queued',cancel=0,lease=NULL,lease_until=NULL WHERE id=?",(ident,))
        return self.status(owner,ident)

    async def tick(self):
        now=time.time(); lease=uuid.uuid4().hex
        with self.repo.connect(immediate=True) as db:
            # A crashed accepted request is uncertain, never blindly replayed.
            for old in db.execute("SELECT id FROM jobs WHERE status='running' AND lease_until<?",(now,)).fetchall():
                db.execute("UPDATE chunks SET status='ambiguous',error='worker_interrupted' WHERE job=? AND status='running'",(old['id'],))
                db.execute("UPDATE attempts SET outcome='ambiguous',error='worker_interrupted' WHERE job=? AND outcome='started'",(old['id'],))
                db.execute("UPDATE jobs SET status='queued',lease=NULL WHERE id=?",(old['id'],))
            row=db.execute("SELECT * FROM jobs WHERE status='queued' ORDER BY created LIMIT 1").fetchone()
            if not row: return False
            job=dict(row)
            if job['cancel']:
                db.execute("UPDATE jobs SET status='cancelled' WHERE id=?",(job['id'],)); return True
            db.execute("UPDATE jobs SET status='running',lease=?,lease_until=? WHERE id=?",(lease,now+300,job['id']))
        plan=self.repo.typed(RenderPlan,'plan',job['plan_id'],job['owner'])
        state=self.status(job['owner'],job['id'])
        pending=next((c for c in state['chunks'] if c['status']=='pending' and c['retry_at']<=now),None)
        if pending:
            chunk=plan.chunks[pending['ordinal']]; attempt=uuid.uuid4().hex; number=pending['attempts']+1
            costs={c.id:sum(len(i.text) for i in c.request.inputs) for c in plan.chunks}
            # Conservatively reserve possibly billable attempts, even when usage metadata is absent.
            # Explicit provider rejection (e.g. 429/401) does not consume the speech envelope.
            spent=sum(costs[a['chunk']] for a in state['attempts']
                      if a['outcome'] in ('started','succeeded','ambiguous') or a['error']=='transient')
            if spent+costs[chunk.id]>job['budget']:
                with self.repo.connect(immediate=True) as db:
                    db.execute("UPDATE chunks SET status='failed',error='budget_exhausted' WHERE job=? AND status='pending'",(job['id'],))
                    db.execute("UPDATE jobs SET status='partial_failed',lease=NULL,lease_until=NULL WHERE id=? AND lease=?",(job['id'],lease))
                return True
            with self.repo.connect(immediate=True) as db:
                db.execute("UPDATE chunks SET status='running',attempts=? WHERE job=? AND chunk=?",(number,job['id'],chunk.id))
                db.execute('INSERT INTO attempts(id,job,chunk,number,payload_hash,outcome,created) VALUES(?,?,?,?,?,?,?)',
                           (attempt,job['id'],chunk.id,number,digest(chunk.request.provider_body()),'started',time.time()))
            try:
                result=await self.provider.render(chunk)
                # Validate decodability before accepting success; retain raw timing and source maps.
                _,durations=await asyncio.to_thread(assemble,[result.audio])
                asset=self.repo.store_bytes(job['owner'],plan.project_id,result.audio,result.mime,
                    chunk.id+('.wav' if result.mime=='audio/wav' else '.mp3'),duration=durations[0],
                    timing=result.timing,fragments=[f.model_dump(mode='json') for f in chunk.fragments],take_id=attempt)
                with self.repo.connect(immediate=True) as db:
                    db.execute("UPDATE chunks SET status='completed',asset=?,error=NULL WHERE job=? AND chunk=?",(asset['id'],job['id'],chunk.id))
                    db.execute("UPDATE attempts SET outcome='succeeded',request_id=?,usage=? WHERE id=?",(result.request_id,result.usage,attempt))
            except Exception as exc:
                kind=exc.kind if isinstance(exc,ProviderError) else 'ambiguous'
                retry=kind in ('rate_limit','transient') and number<3
                delay=max(2**number,getattr(exc,'retry_after',0))
                with self.repo.connect(immediate=True) as db:
                    db.execute('UPDATE chunks SET status=?,error=?,retry_at=? WHERE job=? AND chunk=?',
                        ('pending' if retry else 'ambiguous' if kind=='ambiguous' else 'failed',kind,time.time()+delay,job['id'],chunk.id))
                    db.execute('UPDATE attempts SET outcome=?,error=? WHERE id=?',('ambiguous' if kind=='ambiguous' else 'failed',kind,attempt))
                    if kind in ('authentication','permission','configuration'):
                        db.execute("UPDATE chunks SET status='failed',error=? WHERE job=? AND status='pending'",(kind,job['id']))
        state=self.status(job['owner'],job['id'])
        statuses=[c['status'] for c in state['chunks']]
        status='cancelled' if state['cancel'] else 'queued' if 'pending' in statuses else 'completed' if all(s=='completed' for s in statuses) else 'partial_failed' if 'completed' in statuses else 'failed'
        if status=='completed':
            try:
                data=[self.repo.artifact_path(c['asset'],job['owner'])[1].read_bytes() for c in state['chunks']]
                audio,durations=await asyncio.to_thread(assemble,data)
                final=self.repo.store_bytes(job['owner'],plan.project_id,audio,'audio/mpeg','script-to-voice.mp3',job_id=job['id'],duration=sum(durations),take_id=job['id'])
                cues=[]; offset=0
                for c,duration in zip(state['chunks'],durations):
                    cues.append({'chunk_id':c['chunk'],'artifact_id':c['asset'],'start_seconds':offset,'duration':duration,
                                 'timing':self.repo.get('artifact',c['asset'],job['owner']).get('timing')})
                    offset+=duration
                cue=self.repo.store_bytes(job['owner'],plan.project_id,json.dumps(cues).encode(),'application/json','cue-sheet.json',job_id=job['id'])
            except Exception:
                status='partial_failed'
        with self.repo.connect(immediate=True) as db:
            db.execute('UPDATE jobs SET status=?,lease=NULL,lease_until=NULL WHERE id=? AND lease=?',(status,job['id'],lease))
        return True


async def main():
    from script_to_voice.storage import Repository
    from script_to_voice.service.workflow import Workflow
    repo=Repository(os.environ.get('STV_DATA_ROOT','/data')); workflow=Workflow(repo)
    jobs=Jobs(repo,workflow.provider)
    while True:
        await jobs.tick()
        await asyncio.sleep(1)


if __name__=='__main__': asyncio.run(main())
