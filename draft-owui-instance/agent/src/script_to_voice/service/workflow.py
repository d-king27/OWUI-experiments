from __future__ import annotations
import base64
import hashlib
import uuid
import re
from fastapi import Depends
from script_to_voice.contracts import *
from script_to_voice.parsing import parse_fdx
from script_to_voice.service.app import ImportFile, ChatRequest
from script_to_voice.selection import resolve,parse_command,Clarification
from script_to_voice.service.journey import HELP_COMMANDS, WRONG_MODEL_COMMANDS, WELCOME, WRONG_MODEL, guidance, selection_choice, voice_link
from script_to_voice.service.cast_review import CastReview, current_draft, mapping_lines
from script_to_voice.service.direction_review import load_direction, ready_message, package_bytes, detail_page


class SelectRequest(Contract):
    revision_id: str
    query: str
    prior_selection_id: str | None = None
    proposal: IntentProposal | None = None


class CastRequest(Contract):
    revision_id: str
    voice_id: str
    expected_version: int
    locked: bool = True


class SelectionReference(Contract):
    selection_id: str


class AuditionRequest(Contract):
    revision_id: str
    character_id: str
    voice_id: str


class DesignRequest(Contract):
    revision_id: str
    character_id: str
    request: VoiceDesignRequest
    idempotency_key: str


class SaveDesignRequest(Contract):
    revision_id: str
    preview_id: str
    name: str
    idempotency_key: str


class PlanRequest(Contract):
    selection_id: str
    overrides: tuple[Annotation,...] = ()


class ReconcileRequest(Contract):
    source_revision_id: str
    target_revision_id: str
    expected_cast_version: int


class JobRequest(Contract):
    plan_id: str
    plan_hash: str
    idempotency_key: str
    max_characters: int


class RetryRequest(Contract):
    chunk_ids: tuple[str,...]
    accept_duplicate_billing_risk: bool = False


class Workflow:
    def __init__(self, repository, provider=None, planner=None):
        self.repo=repository
        import os
        from script_to_voice.providers.fakes import FakeVoiceProvider
        from script_to_voice.providers.elevenlabs import ElevenLabs
        from script_to_voice.casting import CastingService
        self.provider=provider or (FakeVoiceProvider() if os.environ.get('STV_MOCK','true').lower()=='true' else ElevenLabs())
        self.casting=CastingService(repository,self.provider)
        self.cast_review=CastReview(repository,self.casting)
        from script_to_voice.casting.design import DesignService
        self.design=DesignService(repository,self.provider,self.casting)
        from script_to_voice.jobs.runner import Jobs
        self.jobs=Jobs(repository,self.provider)
        self.planner=planner
        if planner is None and os.environ.get('STV_LLM_MODEL'):
            from script_to_voice.providers.planning import TextPlanner
            from script_to_voice.providers.budget import PlannerBudget
            from script_to_voice.providers.anthropic import AnthropicPlanner
            provider=os.environ.get('STV_LLM_PROVIDER','openai-compatible')
            if provider not in ('anthropic','openai-compatible'): raise ValueError('Unsupported text planner provider')
            planner_type=AnthropicPlanner if provider=='anthropic' else TextPlanner
            self.planner=planner_type(os.environ.get('STV_LLM_BASE_URL',''),os.environ['STV_LLM_MODEL'],
                                     budget=PlannerBudget.from_environment(repository))
        self.casting.planner=self.planner

    async def select(self,owner,project_id,body):
        revision=self.repo.typed(ScriptRevision,'revision',body.revision_id,owner)
        if revision.project_id!=project_id: raise ValueError('Foreign project')
        prior=self.repo.typed(Selection,'selection',body.prior_selection_id,owner) if body.prior_selection_id else None
        proposal=body.proposal or parse_command(body.query,revision)
        if proposal.operation=='inspect' and self.planner:
            cache_id='intent_'+digest([revision.id,body.query,list(prior.selected_ids) if prior else [],
                                      getattr(self.planner,'model','fake'),'intent-2'])
            cached=next((c for c in self.repo.list('intent_cache',owner,project_id) if c['id']==cache_id),None)
            if cached:
                import json
                proposal=IntentProposal.model_validate_json(json.dumps(cached['proposal']))
            else:
                proposal=await self.planner.interpret(body.query,revision,prior)
                self.repo.put('intent_cache',{'id':cache_id,'owner_id':owner,'project_id':project_id,
                                             'proposal':proposal.model_dump(mode='json')})
            if proposal.operation=='inspect':
                raise Clarification(f'{revision.title}: {len(revision.scenes)} scenes. Characters: '+
                    ', '.join(c.name for c in revision.characters)+'. Ask for a character, scene or exact phrase to select dialogue.')
        selection=resolve(revision,proposal,body.query,prior)
        self.repo.put('selection',selection)
        return selection

    def revision(self,owner,project_id,revision_id):
        revision=self.repo.typed(ScriptRevision,'revision',revision_id,owner)
        if revision.project_id!=project_id: raise ValueError('Foreign project')
        return revision

    async def plan(self,owner,project_id,body):
        from script_to_voice.directing import make_direction
        from script_to_voice.directing.compiler import compile_plan
        selection=self.repo.typed(Selection,'selection',body.selection_id,owner)
        revision=self.revision(owner,project_id,selection.revision_id)
        cast=self.casting.latest(revision)
        required={e.character_id for e in revision.elements if e.id in selection.selected_ids}
        if required-{a.character_id for a in cast.assignments}:
            raise ValueError('Assign voices for every selected character before preparing direction')
        cache_id='direction-cache_'+digest([selection.semantic_hash(),cast.semantic_hash(),
            [a.model_dump(mode='json') for a in body.overrides],getattr(self.planner,'model','source-only'),'beat-1'])
        cached=next((c for c in self.repo.list('direction_cache',owner,project_id) if c['id']==cache_id),None)
        if cached:
            direction=self.repo.typed(DirectionPlan,'direction',cached['direction_id'],owner)
            plan=compile_plan(revision,selection,cast,direction)
            self.repo.put('plan',plan)
            return plan
        inferred=[]
        if self.planner:
            selected=set(selection.selected_ids)
            beats=[]
            # Bounded beats with adjacent context; selection IDs remain authoritative.
            for scene in revision.scenes:
                elements=[e for e in revision.elements if e.scene_id==scene.id]
                for start in range(0,len(elements),20):
                    beat=elements[start:start+20]
                    targets={e.id for e in beat if e.id in selected}
                    if not targets: continue
                    context=elements[max(0,start-4):start+24]
                    payload={'selected_ids':sorted(targets),
                        'elements':[{k:e.model_dump(mode='json')[k] for k in ('id','kind','original_text','character_id','dialogue_block_id','parenthetical_ids')}
                                    for e in context],'evidence_ids':[e.id for e in context]}
                    beat_id='beat_'+digest([cache_id,payload])
                    cached_beat=next((c for c in self.repo.list('beat_cache',owner,project_id) if c['id']==beat_id),None)
                    beats.append((payload,targets,beat_id,cached_beat))
            budget=getattr(self.planner,'budget',None)
            if budget:
                needed=sum(cached is None for _,_,_,cached in beats)
                available=budget.status()['remaining_usd']
                if needed*budget.per_request>round(available*1000000):
                    raise ValueError(f'Direction needs {needed} uncached requests beyond the remaining demo allowance; select a shorter scene')
            for payload,targets,beat_id,cached_beat in beats:
                    if cached_beat:
                        import json
                        result=DirectionProposal.model_validate_json(json.dumps(cached_beat['proposal']))
                    else:
                        result=await self.planner.annotate(payload)
                    for a in result.annotations:
                        if a.element_id not in targets: raise ValueError('Planner directed unselected or out-of-beat dialogue')
                        if not a.evidence_ids: raise ValueError('Inferred direction requires source evidence')
                        inferred.append(a.model_copy(update={'origin':'inferred'}))
                    if not cached_beat:
                        self.repo.put('beat_cache',{'id':beat_id,'owner_id':owner,'project_id':project_id,'proposal':result.model_dump(mode='json')})
        direction=make_direction(revision,selection,cast,overrides=body.overrides,inferred=tuple(inferred))
        self.repo.put('direction',direction)
        self.repo.put('direction_cache',{'id':cache_id,'owner_id':owner,'project_id':project_id,'direction_id':direction.id})
        plan=compile_plan(revision,selection,cast,direction)
        self.repo.put('plan',plan)
        return plan

    def enqueue(self,owner,body):
        plan=self.repo.typed(RenderPlan,'plan',body.plan_id,owner)
        revision=self.revision(owner,plan.project_id,plan.revision_id)
        if self.casting.latest(revision).semantic_hash()!=plan.cast_hash: raise ValueError('Cast changed; prepare a new plan')
        return self.jobs.enqueue(owner,body.plan_id,body.plan_hash,body.idempotency_key,body.max_characters)

    @staticmethod
    def job_progress(job):
        return {'id':job['id'],'status':job['status'],'completed':sum(c['status']=='completed' for c in job['chunks']),
                'total':len(job['chunks']),'cancellation_requested':bool(job['cancel'])}

    def job_result(self,owner,ident):
        job=self.jobs.status(owner,ident)
        progress=self.job_progress(job)
        status=job['status']
        if status=='completed':
            message='**Your audio is ready.** Use the player below or download the audio.'
        elif status=='cancelled':
            message='Audio generation was cancelled. Completed work remains saved; an already accepted provider request may still finish.'
        elif status in ('failed','partial_failed'):
            if any(c['status']=='ambiguous' for c in job['chunks']):
                message='Audio generation needs attention: a provider request has an uncertain outcome. Check provider history with the administrator before retrying.'
            elif any(c.get('error') in ('authentication','permission','configuration') for c in job['chunks']):
                message='Audio generation stopped. Ask the administrator to check the ElevenLabs key, permissions and configuration before retrying.'
            elif any(c.get('error')=='budget_exhausted' for c in job['chunks']):
                message='Audio generation stopped at the authorized usage limit. Completed work remains saved; no extra usage was authorized.'
            else:
                message='Audio generation needs attention. Completed work remains saved. Send status to inspect the job before retrying failed parts.'
        elif progress['cancellation_requested']:
            message='Stopping future audio parts. An already accepted provider request may still finish.'
        else:
            message='Generating your audio. Progress and the player will appear automatically while this chat waits.'
        assets=[]
        if status not in ('queued','running'):
            plan=self.repo.typed(RenderPlan,'plan',job['plan_id'],owner)
            assets=[a for a in self.repo.list('artifact',owner,plan.project_id) if a.get('job_id')==ident]
        return {'message':message,'artifacts':assets,'job':progress}

    def direction_package(self,owner,revision,selection,direction,plan):
        artifact=self.repo.store_bytes(owner,revision.project_id,package_bytes(revision,selection,direction,plan),
                                       'application/zip','direction-package.zip')
        return {'message':ready_message(),'artifacts':[artifact]}

    def direction_chat(self,owner,state,message):
        if not state.get('prepared_plan_id') or not state.get('selection_id'):
            raise ValueError('Please proceed with line direction first, then inspect its summary or details')
        r=self.revision(owner,state['project_id'],state['revision_id'])
        selection=self.repo.typed(Selection,'selection',state['selection_id'],owner)
        plan=self.repo.typed(RenderPlan,'plan',state['prepared_plan_id'],owner)
        cast=self.casting.latest(r)
        draft=current_draft(state,r,selection,cast)
        if plan.selection_id!=selection.id or plan.cast_hash!=cast.semantic_hash() or (draft and draft['rows']):
            raise ValueError('The selected dialogue or cast changed. Complete casting and proceed with line direction again')
        direction=load_direction(self.repo,owner,plan)
        q=message.strip()
        if q.casefold() in ('direction package','download direction package','direction summary'):
            return self.direction_package(owner,r,selection,direction,plan)
        if q.casefold()=='more direction':
            view=state.get('direction_view',{})
            if view.get('plan_id')!=plan.id: raise ValueError('Please choose a scene or character to inspect before asking for more direction')
            scope,value,offset=view['scope'],view['value'],view['offset']
        else:
            match=re.fullmatch(r'show direction for (scene|character)\s+(.+)',q,re.I)
            scope,value,offset=(match[1].casefold(),match[2].strip(),0) if match else ('all','',0)
        text,next_offset=detail_page(r,selection,direction,scope=scope,value=value,offset=offset)
        version,current=self.repo.session(owner,state['chat_id'])
        current['direction_view']={'plan_id':plan.id,'scope':scope,'value':value,'offset':next_offset}
        self.repo.save_session(owner,state['chat_id'],current,version)
        return {'message':text,'artifacts':[]}

    async def cast_chat(self,owner,state,message):
        r=self.revision(owner,state['project_id'],state['revision_id'])
        cast=self.casting.latest(r)
        q=message.strip()
        if q.casefold() in ('direction package','download direction package','direction summary','show direction','more direction') or re.fullmatch(r'show direction for (scene|character)\s+.+',q,re.I):
            return self.direction_chat(owner,state,q)
        confirm=re.fullmatch(r'confirm cast[.!?]?',q,re.I)
        if confirm:
            await self.cast_review.confirm(owner,state)
            return {'message':'Casting confirmed and saved. No audio has been generated.','artifacts':[]}
        if q.casefold().startswith('confirm cast '):
            return {'message':'Please double-check the latest casting list, then simply reply **confirm cast**. No code is needed.','artifacts':[]}
        if q.casefold()=='discard cast changes':
            v,current=self.repo.session(owner,state['chat_id']); current.pop('cast_review',None)
            self.repo.save_session(owner,state['chat_id'],current,v)
            return {'message':'Unconfirmed casting changes discarded. Previously confirmed voices are retained.','artifacts':[]}
        if q.casefold().rstrip('.!?') in ('yes','ok','okay','confirm','no','none','not yet','none of them','accept suggestions') and state.get('cast_review',{}).get('rows'):
            return {'message':'Please double-check the character-to-voice list below and use its exact confirmation phrase. A general yes does not apply casting.','artifacts':[]}
        if state.get('cast_review') and re.search(r'\balready cast\b',q,re.I):
            return {'message':'Please provide the existing voice IDs or ElevenLabs links as CHARACTER: VOICE_ID, one character per line. I will update the review before you confirm.','artifacts':[]}
        reconcile=re.fullmatch(r'reuse cast from revision (\S+)',q,re.I)
        if reconcile:
            source=self.revision(owner,r.project_id,reconcile[1])
            source_names={c.id:c.name for c in source.characters}; target_names={c.id:c.name for c in r.characters}
            _,_,_,required=self.cast_review.context(owner,state)
            rows=[{'character_id':a.character_id,'voice_id':a.voice_id,'origin':'selected'}
                  for a in self.casting.latest(source).assignments if a.character_id in required
                  and source_names.get(a.character_id)==target_names.get(a.character_id)
                  and a.character_id not in {v.character_id for v in cast.assignments}]
            if not rows: raise ValueError('No missing selected roles have an exact earlier character assignment to review')
            await self.cast_review.stage(owner,state,rows)
            return {'message':'Earlier exact character assignments added to the casting review. Please check them before confirming; new auditions remain explicit.','artifacts':[]}
        regenerate=re.fullmatch(r'regenerate chunk (\S+) with (whispering|shouting|hesitant|restrained|laughing|pause)',q,re.I)
        if regenerate:
            if state.get('cast_review',{}).get('rows'): raise ValueError('Please confirm or discard the pending casting changes before requesting a revised take')
            if not state.get('job_id'): raise ValueError('Generate a job before revising a chunk')
            previous=self.jobs.status(owner,state['job_id'])
            if previous['status']!='completed': raise ValueError('Finish or resolve the earlier job before revising it')
            old=self.repo.typed(RenderPlan,'plan',previous['plan_id'],owner)
            chosen=next((c for c in old.chunks if c.id==regenerate[1]),None)
            if chosen is None: raise ValueError('Choose a chunk ID from job status')
            overrides=tuple(Annotation(element_id=eid,offset=0,tag=regenerate[2].lower(),origin='user')
                            for eid in dict.fromkeys(f.element_id for f in chosen.fragments))
            plan=await self.plan(owner,r.project_id,PlanRequest(selection_id=old.selection_id,overrides=overrides))
            job=self.enqueue(owner,JobRequest(plan_id=plan.id,plan_hash=plan.semantic_hash(),
                idempotency_key=digest([previous['id'],plan.semantic_hash(),'pickup']),max_characters=plan.estimated_characters))
            reusable={c['chunk']:c['asset'] for c in previous['chunks'] if c['status']=='completed' and c['chunk']!=chosen.id}
            # Reuse only byte-identical compiled requests and source mappings, under the same owner.
            with self.repo.connect(immediate=True) as db:
                for chunk in plan.chunks:
                    if chunk.id in reusable:
                        db.execute("UPDATE chunks SET status='completed',asset=? WHERE job=? AND chunk=? AND status='pending'",
                                   (reusable[chunk.id],job['id'],chunk.id))
            v,current=self.repo.session(owner,state['chat_id']); current['job_id']=job['id']; current['prepared_plan_id']=plan.id
            self.repo.save_session(owner,state['chat_id'],current,v)
            result=self.job_result(owner,job['id'])
            result['message']+=' Unchanged parts reuse their earlier audio; the earlier take remains saved.'
            return result
        direct=re.fullmatch(r'direct (.+?) (whispering|shouting|hesitant|restrained|laughing|pause)',q,re.I)
        if direct:
            if not state.get('selection_id'): raise ValueError('Select dialogue first')
            s=self.repo.typed(Selection,'selection',state['selection_id'],owner)
            character=next((c for c in r.characters if c.name.casefold()==direct[1].casefold()),None)
            if not character: raise ValueError('Specify an exact character name')
            overrides=[Annotation(element_id=e.id,offset=0,tag=direct[2].lower(),origin='user').model_dump(mode='json')
                       for e in r.elements if e.id in s.selected_ids and e.character_id==character.id]
            v,current=self.repo.session(owner,state['chat_id'])
            current['direction_overrides']=overrides
            current.pop('prepared_plan_id',None)
            self.repo.save_session(owner,state['chat_id'],current,v)
            return {'message':f'Direction saved for {len(overrides)} selected lines. Reply proceed to prepare the updated line direction.','artifacts':[]}
        direction_confirm=q.casefold().rstrip('.!?') in ('proceed','proceed with line direction','confirm line direction')
        if q.casefold().rstrip('.!?') in ('no','not yet'):
            return {'message':'Okay. This reply starts no new line direction or audio. Your work stays saved; reply proceed when you are ready.','artifacts':[]}
        if q.casefold().rstrip('.!?')=='yes' and state.get('selection_id'):
            selected=self.repo.typed(Selection,'selection',state['selection_id'],owner)
            required={e.character_id for e in r.elements if e.id in selected.selected_ids}
            if not required or required-{a.character_id for a in cast.assignments}:
                return {'message':'Please finish selecting dialogue and confirming the cast before proceeding with line direction.','artifacts':[]}
            if state.get('prepared_plan_id'):
                existing=self.repo.typed(RenderPlan,'plan',state['prepared_plan_id'],owner)
                if existing.selection_id==selected.id and existing.cast_hash==cast.semantic_hash():
                    return self.direction_chat(owner,state,'direction package')
            direction_confirm=True
        if direction_confirm or q.casefold() in ('plan','prepare','generate','generate this selection','status','cancel','retry failed'):
            command='plan' if direction_confirm else q.casefold()
            if command in ('status','cancel','retry failed'):
                if not state.get('job_id'): return {'message':'No render job in this chat yet.','artifacts':[]}
                if command=='cancel': self.jobs.cancel(owner,state['job_id'])
                job=self.jobs.status(owner,state['job_id'])
                if command=='retry failed':
                    ids=tuple(c['chunk'] for c in job['chunks'] if c['status']=='failed')
                    job=self.jobs.retry(owner,state['job_id'],ids)
                assets=[a for a in self.repo.list('artifact',owner,r.project_id) if a.get('job_id')==job['id']]
                return {'message':f'Job `{job["id"]}`: {job["status"]}. '+
                    f'{sum(c["status"]=="completed" for c in job["chunks"])}/{len(job["chunks"])} chunks complete. '+
                    ('Mock audio is a test tone.' if __import__('os').environ.get('STV_MOCK','true')=='true' else '')+
                    (' Uncertain attempts require provider-history review before explicit API retry.' if any(c['status']=='ambiguous' for c in job['chunks']) else '')+
                    '\nChunks: '+', '.join('`'+c['chunk']+'` ('+c['status']+')' for c in job['chunks']),
                    'artifacts':assets,'job':self.job_progress(job)}
            if not state.get('selection_id'): raise ValueError('Select dialogue before preparing audio')
            selected=self.repo.typed(Selection,'selection',state['selection_id'],owner)
            draft=current_draft(state,r,selected,cast)
            if draft and draft['rows']: raise ValueError('Please double-check and confirm the proposed cast before preparing or generating audio')
            if command in ('generate','generate this selection'):
                if not state.get('prepared_plan_id'):
                    raise ValueError('Please proceed with line direction first and review it before authorizing audio generation')
                plan=self.repo.typed(RenderPlan,'plan',state['prepared_plan_id'],owner)
                if plan.selection_id!=state['selection_id'] or plan.cast_hash!=cast.semantic_hash():
                    raise ValueError('Selection or cast changed. Reply proceed to prepare and review the updated line direction')
                job=self.enqueue(owner,JobRequest(plan_id=plan.id,plan_hash=plan.semantic_hash(),idempotency_key=plan.semantic_hash(),max_characters=plan.estimated_characters))
                v,current=self.repo.session(owner,state['chat_id'])
                current['job_id']=job['id']; self.repo.save_session(owner,state['chat_id'],current,v)
                return self.job_result(owner,job['id'])
            import json
            overrides=tuple(Annotation.model_validate_json(json.dumps(a)) for a in state.get('direction_overrides',[]))
            plan=await self.plan(owner,r.project_id,PlanRequest(selection_id=state['selection_id'],overrides=overrides))
            v,current=self.repo.session(owner,state['chat_id'])
            current['prepared_plan_id']=plan.id
            self.repo.save_session(owner,state['chat_id'],current,v)
            if command in ('plan','prepare'):
                selection=self.repo.typed(Selection,'selection',state['selection_id'],owner)
                direction=load_direction(self.repo,owner,plan)
                return self.direction_package(owner,r,selection,direction,plan)
        design_match=re.fullmatch(r'design voice for (.+?):\s*(.+)',q,re.I|re.S)
        if design_match:
            character=next((c for c in r.characters if c.name.casefold()==design_match[1].casefold()),None)
            if not character: raise ValueError('Specify the exact character name')
            excerpt=' '.join(e.original_text for e in r.elements if e.kind=='dialogue' and e.character_id==character.id)
            text=(excerpt+' ')*max(1,101//max(1,len(excerpt))+1)
            request=VoiceDesignRequest(voice_description=design_match[2],text=text[:1000])
            previews=await self.design.previews(r,character.id,request,digest([r.id,q]))
            return {'message':'Voice previews ready. Save only your chosen candidate with `save voice PREVIEW_ID as NAME`:\n'+
                '\n'.join('`'+p['id']+'`' for p in previews),
                'artifacts':[self.repo.get('artifact',p['artifact_id'],owner) for p in previews]}
        save_match=re.fullmatch(r'save voice (\S+) as (.+)',q,re.I)
        if save_match:
            saved=await self.design.save(r,save_match[1],save_match[2],digest([r.id,q]))
            preview=self.repo.get('voice_preview',save_match[1],owner)
            await self.cast_review.stage(owner,state,[{'character_id':preview['character_id'],
                                            'voice_id':saved['voice_id'],'origin':'designed'}])
            return {'message':f'Saved voice `{saved["voice_id"]}` to the account and added it to the casting review. It is not assigned until you confirm.', 'artifacts':[]}
        if q.casefold() in ('voices','refresh voices'):
            voices=await self.casting.catalog(refresh=q.casefold().startswith('refresh'))
            return {'message':'Available voices:\n'+ '\n'.join(f'- {v.name}: {voice_link(v.voice_id)}' for v in voices),'artifacts':[]}
        if q.casefold() in ('cast','suggest voices','review cast'):
            if not state.get('selection_id'): raise ValueError('Select dialogue before casting')
            selection=self.repo.typed(Selection,'selection',state['selection_id'],owner)
            required={e.character_id for e in r.elements if e.id in selection.selected_ids}
            if required-{a.character_id for a in cast.assignments} or state.get('cast_review'):
                await self.cast_review.propose(owner,state,refresh=q.casefold()=='suggest voices')
                return {'message':'Please review the proposed casting below. Nothing is assigned until you confirm.','artifacts':[]}
            names={c.id:c.name for c in r.characters}
            return {'message':'Confirmed cast:\n'+'\n'.join(f'- {names[a.character_id]}: {voice_link(a.voice_id)}'
                            for a in cast.assignments if a.character_id in required),'artifacts':[]}
        rows=mapping_lines(q,r)
        if rows is not None:
            await self.cast_review.stage(owner,state,rows)
            return {'message':'Your voice choices are ready for review. Please double-check the updated list before confirming.','artifacts':[]}
        if re.fullmatch(r'cast\s+.+',q,re.I):
            raise ValueError('Please provide a character-to-voice line such as CHARACTER: VOICE_ID or an ElevenLabs voice link')
        match=re.fullmatch(r'(audition)\s+(.+?)(?:\s+as\s+(\S+))?',q,re.I)
        if not match: return None
        found=[c for c in r.characters if match[2].casefold() in {c.name.casefold(),*(a.casefold() for a in c.aliases)}]
        if len(found)!=1: raise ValueError('Specify one character: '+', '.join(c.name for c in r.characters))
        character=found[0]
        voice=match[3] or next((a.voice_id for a in cast.assignments if a.character_id==character.id),None)
        if not voice: raise ValueError('Assign a voice before auditioning')
        audition=await self.casting.audition(r,character.id,voice)
        import os
        return {'message':'Audition ready.'+(' Mock mode returns a test tone, not speech.' if os.environ.get('STV_MOCK','true')=='true' else ''),'artifacts':[self.repo.get('artifact',audition['artifact_id'],owner)]}

    def import_script(self, owner, project_id, file):
        self.repo.get('project',project_id,owner)
        if len(file.original_base64)>12*1024*1024:
            raise ValueError('Script exceeds the 8 MiB import limit')
        try: data=base64.b64decode(file.original_base64,validate=True)
        except Exception: raise ValueError('Invalid file encoding') from None
        checksum=hashlib.sha256(data).hexdigest()
        for old in self.repo.list('revision',owner,project_id):
            if old['original_hash']==checksum:
                return ScriptRevision.model_validate_json(__import__('json').dumps(old))
        revision=parse_fdx(data,file.filename,owner_id=owner,project_id=project_id,original_file_id=file.file_id)
        self.repo.store_bytes(owner,project_id,data,'application/xml',file.filename,source_file_id=file.file_id)
        self.repo.put('revision',revision)
        return revision

    async def chat(self, owner, body):
        # These local navigation routes must never reach either paid planner or voice provider.
        if body.message.strip().casefold().rstrip('.!?') in WRONG_MODEL_COMMANDS:
            return {'message':WRONG_MODEL,'artifacts':[]}
        try:
            result=await self._chat(owner,body)
            if result.pop('_prepare_cast',False):
                _,selected_state=self.repo.session(owner,body.chat_id)
                r,s,cast,required=self.cast_review.context(owner,selected_state)
                if required-{a.character_id for a in cast.assignments}:
                    try:
                        await self.cast_review.propose(owner,selected_state)
                    except ValueError as exc:
                        result['message']+='\n\nVoice suggestions could not be prepared: '+str(exc)+'. Your dialogue selection is retained.'
        except ValueError as exc:
            # Chat recovery is conversational; the typed domain/API routes retain their HTTP errors.
            result={'message':str(exc)+'\n\nRequest stopped. Check the requirement below before trying again. '
                    'If a provider action timed out, do not blindly repeat it; ask the administrator to inspect its saved action/history.',
                    'artifacts':[]}
        _,state=self.repo.session(owner,body.chat_id)
        try:
            next_step=guidance(self,owner,state)
        except ValueError:
            next_step='The saved chat context could not be loaded. Send `scripts` and explicitly reopen your project, or ask the administrator for help. Do not repeat a paid action to recover its response.'
        result['message']+='\n\n---\n\n'+next_step
        return result

    async def _chat(self, owner, body):
        version,state=self.repo.session(owner,body.chat_id)
        q=body.message.strip().casefold().rstrip('.!?')
        if q in HELP_COMMANDS:
            return {'message':WELCOME,'artifacts':[]}
        imported=[]
        known=state.get('imported_files',{})
        if sum(file.file_id not in known for file in body.files)>1:
            raise ValueError('Attach one new FDX at a time so the active script is unambiguous')
        for file in body.files:
            if file.file_id in known:
                continue
            project=Project(id=uuid.uuid4().hex,owner_id=owner,title=file.filename)
            self.repo.put('project',project)
            revision=self.import_script(owner,project.id,file)
            state.update(project_id=project.id,revision_id=revision.id)
            for key in ('selection_id','selection_choice','cast_review','direction_overrides','prepared_plan_id','job_id'): state.pop(key,None)
            known[file.file_id]=revision.id
            imported.append(revision)
        state['imported_files']=known
        state['chat_id']=body.chat_id
        self.repo.save_session(owner,body.chat_id,state,version)
        if imported:
            r=imported[-1]
            return {'message':f'Imported **{r.title}**: {len(r.scenes)} scenes, {len(r.characters)} characters. '+
                    'The attachment is the source; your accompanying message has not selected or generated audio.', 'artifacts':[]}
        if q in ('wrong script','change script'):
            return {'message':'Attach the correct original FDX and send `Use attached script`, or send `scripts` to choose a saved project. '+
                    'The current script is kept until you choose another. Existing render jobs are not cancelled by switching scripts; use `cancel` first if needed.',
                    'artifacts':[]}
        if q in ('wrong selection','change selection','clear selection'):
            for key in ('selection_id','selection_choice','cast_review','direction_overrides','prepared_plan_id'): state.pop(key,None)
            self.repo.save_session(owner,body.chat_id,state,version+1)
            return {'message':'Selection and its direction overrides cleared. Your script, saved cast and audio are retained. '+
                    'An existing render job keeps running unless you send `cancel`.', 'artifacts':[]}
        if q in ('scenes','characters') and state.get('revision_id'):
            r=self.revision(owner,state['project_id'],state['revision_id'])
            rows=(['- '+s.number+': '+s.heading for s in r.scenes] if q=='scenes' else ['- '+c.name for c in r.characters])
            return {'message':q.capitalize()+':\n'+'\n'.join(rows),'artifacts':[]}
        if body.message.strip().lower()=='planner budget':
            from script_to_voice.providers.budget import PlannerBudget
            budget=PlannerBudget.from_environment(self.repo).status()
            return {'message':f'Text-planning allowance: ${budget["allowance_usd"]:.2f}; reserved: ${budget["reserved_usd"]:.2f}; remaining: ${budget["remaining_usd"]:.2f}. '+
                f'Per request: ${budget["per_request_usd"]:.2f}. Reported-token cost estimate: ${budget["reported_usage_estimate_usd"]:.6f}. '+
                'Reservations are conservative allowances, not measured provider charges.','artifacts':[]}
        if body.message.strip().lower()=='scripts':
            return {'message':'Saved projects:\n'+'\n'.join(f'- {p["title"]}: `use project {p["id"]}`' for p in self.repo.list('project',owner)), 'artifacts':[]}
        use=re.fullmatch(r'use project (\S+)',body.message.strip(),re.I)
        if use:
            self.repo.get('project',use[1],owner)
            revisions=self.repo.list('revision',owner,use[1])
            if not revisions: raise ValueError('Project has no imported script')
            state.update(project_id=use[1],revision_id=revisions[-1]['id'])
            for key in ('selection_id','selection_choice','cast_review','direction_overrides','prepared_plan_id','job_id'): state.pop(key,None)
            self.repo.save_session(owner,body.chat_id,state,version+1)
            return {'message':'Loaded saved script. Select dialogue to continue.','artifacts':[]}
        if state.get('project_id') and body.message.strip().lower()=='revisions':
            return {'message':'Saved revisions:\n'+'\n'.join('`'+r['id']+'` '+r['title'] for r in self.repo.list('revision',owner,state['project_id'])),'artifacts':[]}
        use_revision=re.fullmatch(r'use revision (\S+)',body.message.strip(),re.I)
        if use_revision and state.get('project_id'):
            revision=self.revision(owner,state['project_id'],use_revision[1]); state['revision_id']=revision.id
            for key in ('selection_id','selection_choice','cast_review','direction_overrides','prepared_plan_id','job_id'): state.pop(key,None)
            self.repo.save_session(owner,body.chat_id,state,version+1)
            return {'message':'Loaded revision. Select dialogue; reuse an earlier cast only with an explicit reuse command.','artifacts':[]}
        if state.get('revision_id'):
            result=await self.cast_chat(owner,state,body.message)
            if result is not None: return result
            try:
                r=self.revision(owner,state['project_id'],state['revision_id'])
                # Existing exact commands still work; menu replies and follow-ups need no model call.
                proposal=parse_command(body.message,r)
                proposal,waiting=selection_choice(body.message,r,
                    state.get('selection_choice') if proposal.operation=='inspect' else None)
                if waiting:
                    for key in ('selection_id','cast_review','direction_overrides','prepared_plan_id'): state.pop(key,None)
                    state['selection_choice']=waiting
                    self.repo.save_session(owner,body.chat_id,state,version+1)
                    rows=([s.number+' — '+s.heading for s in r.scenes] if waiting=='scene' else [c.name for c in r.characters])
                    return {'message':('Which scene would you like?' if waiting=='scene' else 'Which character would you like?')+
                            '\n\n'+'\n'.join('- '+row for row in rows),'artifacts':[]}
                selection=await self.select(owner,state['project_id'],SelectRequest(revision_id=state['revision_id'],query=body.message,
                                                   prior_selection_id=state.get('selection_id'),proposal=proposal))
            except Clarification as exc:
                return {'message':str(exc),'artifacts':[]}
            state['selection_id']=selection.id
            state.pop('selection_choice',None)
            state.pop('cast_review',None)
            state.pop('direction_overrides',None)
            state.pop('prepared_plan_id',None)
            self.repo.save_session(owner,body.chat_id,state,version+1)
            r=self.repo.typed(ScriptRevision,'revision',state['revision_id'],owner)
            names={c.id:c.name for c in r.characters}
            lines=[e for e in r.elements if e.id in selection.selected_ids]
            preview='\n'.join(f'- **{names[e.character_id]}**: '+
                (e.original_text if len(e.original_text)<=240 else e.original_text[:240]+'… [preview shortened]')+
                f' (`{e.id}`)' for e in lines[:10])
            return {'message':f'Selected {len(selection.selected_ids)} lines, in script order.\n\n'+preview+
                    (f'\n\nShowing the first 10 of {len(lines)} selected lines; all {len(lines)} remain selected.' if len(lines)>10 else '')+
                    ('\n\nNo dialogue matched. Your previous selection has been replaced by this empty selection; choose again.' if not selection.selected_ids else ''),
                    'artifacts':[],'_prepare_cast':bool(selection.selected_ids)}
        return {'message':WELCOME, 'artifacts':[]}

    def register(self,app,identity):
        @app.post('/v1/projects/{project_id}/cast/reconcile')
        async def reconcile(project_id: str,body: ReconcileRequest,owner=Depends(identity)):
            return await self.casting.reconcile(self.revision(owner,project_id,body.source_revision_id),
                self.revision(owner,project_id,body.target_revision_id),body.expected_cast_version)
        @app.post('/v1/projects/{project_id}/render-plans')
        async def plan(project_id: str,body: PlanRequest,owner=Depends(identity)):
            return await self.plan(owner,project_id,body)

        @app.get('/v1/render-plans/{ident}')
        def get_plan(ident: str,owner=Depends(identity)):
            return self.repo.get('plan',ident,owner)

        @app.post('/v1/render-jobs',status_code=202)
        def enqueue(body: JobRequest,owner=Depends(identity)):
            return self.enqueue(owner,body)

        @app.get('/v1/render-jobs/{ident}')
        def status(ident: str,owner=Depends(identity)):
            return self.jobs.status(owner,ident)

        @app.get('/v1/render-jobs/{ident}/result')
        def render_result(ident: str,owner=Depends(identity)):
            return self.job_result(owner,ident)

        @app.post('/v1/render-jobs/{ident}/cancel')
        def cancel(ident: str,owner=Depends(identity)):
            return self.jobs.cancel(owner,ident)

        @app.post('/v1/render-jobs/{ident}/retry')
        def retry(ident: str,body: RetryRequest,owner=Depends(identity)):
            return self.jobs.retry(owner,ident,body.chunk_ids,body.accept_duplicate_billing_risk)

        @app.post('/v1/projects/{project_id}/voice-design/previews')
        async def previews(project_id: str,body: DesignRequest,owner=Depends(identity)):
            return await self.design.previews(self.revision(owner,project_id,body.revision_id),body.character_id,body.request,body.idempotency_key)

        @app.post('/v1/projects/{project_id}/voice-design/save')
        async def save_design(project_id: str,body: SaveDesignRequest,owner=Depends(identity)):
            return await self.design.save(self.revision(owner,project_id,body.revision_id),body.preview_id,body.name,body.idempotency_key)

        @app.get('/v1/voices')
        async def voices(cursor: str | None=None,owner=Depends(identity)):
            return await self.provider.list_voices(cursor)

        @app.post('/v1/projects/{project_id}/cast/proposals')
        async def proposals(project_id: str,body: SelectionReference,owner=Depends(identity)):
            s=self.repo.typed(Selection,'selection',body.selection_id,owner)
            r=self.revision(owner,project_id,s.revision_id)
            return await self.casting.proposals(r,s)

        @app.put('/v1/projects/{project_id}/cast/{character_id}')
        async def assign(project_id: str,character_id: str,body: CastRequest,owner=Depends(identity)):
            return await self.casting.assign(self.revision(owner,project_id,body.revision_id),character_id,
                                            body.voice_id,body.expected_version,locked=body.locked)

        @app.post('/v1/projects/{project_id}/cast/auditions')
        async def audition(project_id: str,body: AuditionRequest,owner=Depends(identity)):
            return await self.casting.audition(self.revision(owner,project_id,body.revision_id),body.character_id,body.voice_id)

        @app.post('/v1/projects/{project_id}/selections')
        async def select(project_id: str,body: SelectRequest,owner=Depends(identity)):
            try: return await self.select(owner,project_id,body)
            except Clarification as exc: return {'clarification':str(exc)}

        @app.post('/v1/projects/{project_id}/scripts')
        def import_file(project_id: str, body: ImportFile, owner=Depends(identity)):
            return self.import_script(owner,project_id,body)

        @app.post('/v1/chat')
        async def chat(body: ChatRequest, owner=Depends(identity)):
            return await self.chat(owner,body)
