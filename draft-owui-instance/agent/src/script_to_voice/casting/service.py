import json
import time
import uuid
from script_to_voice.contracts import *
from script_to_voice.storage import Conflict


class CastingService:
    def __init__(self,repo,provider,planner=None):
        self.repo=repo; self.provider=provider
        self.planner=planner
        self.catalog_cache=None; self.catalog_time=0

    def latest(self,revision):
        casts=[c for c in self.repo.list('cast',revision.owner_id,revision.project_id) if c['revision_id']==revision.id]
        if casts: return Cast.model_validate_json(json.dumps(casts[-1]))
        return Cast(id='cast_'+digest([revision.id,1]),owner_id=revision.owner_id,project_id=revision.project_id,
                    revision_id=revision.id,version=1)

    def profiles(self,revision,selection):
        selection.validate_source(revision)
        lines=[e for e in revision.elements if e.id in selection.selected_ids]
        return tuple(CharacterProfile(character_id=c.id,evidence_ids=tuple(e.id for e in lines if e.character_id==c.id),
            selected_line_count=sum(e.character_id==c.id for e in lines),
            uncertain_traits=('Age, accent and vocal quality are creative choices unless explicitly stated in source.',))
            for c in revision.characters if any(e.character_id==c.id for e in lines))

    async def catalog(self,refresh=False):
        if not refresh and self.catalog_cache is not None and time.time()-self.catalog_time<300:
            return self.catalog_cache
        voices=[]; cursor=None; seen=set()
        for _ in range(100):
            page=await self.provider.list_voices(cursor)
            voices.extend(page.voices)
            if not page.next_cursor: break
            if page.next_cursor in seen: raise ValueError('Voice catalog pagination repeated; refresh later')
            cursor=page.next_cursor; seen.add(cursor)
        else: raise ValueError('Voice catalog exceeds local page limit')
        self.catalog_cache=tuple(voices); self.catalog_time=time.time()
        return self.catalog_cache

    async def assign(self,revision,character_id,voice_id,expected,*,locked=True,origin='selected'):
        return await self.assign_many(revision,(CastAssignment(character_id=character_id,voice_id=voice_id,
                                      locked=locked,origin=origin),),expected)

    async def validate_voice(self,revision,voice_id):
        # Preview IDs are never sent for speech. Availability lookup is mandatory, even with cached catalog.
        previews=self.repo.list('voice_preview',revision.owner_id,revision.project_id)
        if voice_id in {p['generated_voice_id'] for p in previews} or voice_id.startswith('preview-'):
            raise ValueError('Save a chosen preview before assigning its speech voice')
        return await self.provider.get_voice(voice_id)

    async def assign_many(self,revision,assignments,expected):
        if not assignments: raise ValueError('No assignments to confirm')
        if len({a.character_id for a in assignments})!=len(assignments): raise ValueError('Duplicate character assignment')
        for assignment in assignments:
            if assignment.character_id not in {c.id for c in revision.characters}: raise ValueError('Unknown character')
            await self.validate_voice(revision,assignment.voice_id)
        old=self.latest(revision)
        if old.version!=expected: raise Conflict('Cast changed; refresh before assigning')
        confirmed=tuple(a.model_copy(update={'evidence_ids':tuple(e.id for e in revision.elements
                            if e.kind=='dialogue' and e.character_id==a.character_id)}) for a in assignments)
        new=Cast(id='cast_'+digest([revision.id,old.version+1]),owner_id=revision.owner_id,project_id=revision.project_id,
            revision_id=revision.id,version=old.version+1,assignments=tuple(a for a in old.assignments
                            if a.character_id not in {v.character_id for v in confirmed})+confirmed)
        self.repo.put('cast',new)
        return new

    async def reconcile(self,source,target,expected):
        require_scope(source,target)
        current=self.latest(target)
        if current.version!=expected: raise Conflict('Target cast changed; refresh before reuse')
        previous=self.latest(source)
        source_names={c.id:c.name for c in source.characters}
        target_names={c.id:c.name for c in target.characters}
        assignments={a.character_id:a for a in current.assignments}
        added=[]; skipped=[]
        for assignment in previous.assignments:
            cid=assignment.character_id
            if cid in assignments or cid not in target_names or source_names.get(cid)!=target_names[cid]:
                skipped.append(cid); continue
            await self.provider.get_voice(assignment.voice_id)
            assignments[cid]=assignment.model_copy(update={'audition_status':'pending',
                'evidence_ids':tuple(e.id for e in target.elements if e.kind=='dialogue' and e.character_id==cid)})
            added.append(cid)
        new=Cast(id='cast_'+digest([target.id,current.version+1]),owner_id=target.owner_id,
                 project_id=target.project_id,revision_id=target.id,version=current.version+1,assignments=tuple(assignments.values()))
        self.repo.put('cast',new)
        return {'cast':new.model_dump(mode='json'),'reused_character_ids':added,'skipped_character_ids':skipped,
                'explanation':'Only exact stable character identities were reused. Current target assignments were preserved; new auditions remain pending.'}

    async def proposals(self,revision,selection,plan=True):
        profiles=self.profiles(revision,selection); cast=self.latest(revision); voices=await self.catalog()
        assigned={a.character_id for a in cast.assignments}
        proposed=()
        pending=[p for p in profiles if p.character_id not in assigned]
        if self.planner and plan and pending:
            excerpts=[]
            for p in pending:
                lines=[e for e in revision.elements if e.id in p.evidence_ids][:2]
                excerpts.extend({'id':e.id,'character_id':e.character_id,'original_text':e.original_text} for e in lines)
            request={'profiles':[p.model_dump(mode='json') for p in pending],
                'characters':[c.model_dump(mode='json') for c in revision.characters if c.id in {p.character_id for p in pending}],
                'character_ids':[p.character_id for p in pending], 'voice_ids':[v.voice_id for v in voices[:12]],
                'voices':[v.model_dump(mode='json') for v in voices[:12]],'evidence_elements':excerpts,
                'existing_cast':cast.model_dump(mode='json')}
            cache_id='cast-proposal_'+digest([revision.id,request,getattr(self.planner,'model','fake'),'casting-2'])
            cached=next((c for c in self.repo.list('casting_cache',revision.owner_id,revision.project_id) if c['id']==cache_id),None)
            result=CastingProposal.model_validate_json(json.dumps(cached['proposal'])) if cached else await self.planner.propose(request)
            existing={a.character_id:a for a in cast.assignments}
            if len({a.character_id for a in result.assignments})!=len(result.assignments):
                raise ValueError('Casting planner proposed duplicate characters')
            for a in result.assignments:
                if a.character_id not in {p.character_id for p in pending} or a.voice_id not in {v.voice_id for v in voices[:12]}:
                    raise ValueError('Casting planner proposed an unselected role or unavailable voice')
                if a.character_id in existing and existing[a.character_id].locked and existing[a.character_id].voice_id!=a.voice_id:
                    raise ValueError('Casting planner attempted to replace a locked voice')
                if not set(a.evidence_ids)<={e.id for e in revision.elements}: raise ValueError('Casting planner proposed unknown evidence')
            proposed=tuple(a.model_copy(update={'origin':'catalog'}) for a in result.assignments)
            if not cached:
                self.repo.put('casting_cache',{'id':cache_id,'owner_id':revision.owner_id,'project_id':revision.project_id,'proposal':result.model_dump(mode='json')})
        return {'profiles':[p.model_dump(mode='json') for p in profiles], 'cast':cast.model_dump(mode='json'),
                'proposals':[a.model_dump(mode='json') for a in proposed],
                'pending':[p.character_id for p in profiles if p.character_id not in assigned],
                'shortlist':[v.model_dump(mode='json') for v in voices[:12]],
                'explanation':'Catalog candidates are creative options. Select a voice for each pending role; no automatic assignment was made.'}

    async def audition(self,revision,character_id,voice_id):
        await self.provider.get_voice(voice_id)
        line=next((e for e in revision.elements if e.kind=='dialogue' and e.character_id==character_id),None)
        if not line: raise ValueError('Character has no dialogue to audition')
        if len(line.original_text)>500: raise ValueError('Choose a shorter excerpt (up to 500 characters) for this audition')
        key='audition_'+digest([revision.id,character_id,voice_id,line.id])
        cached=self.repo.claim_action(revision.owner_id,key,digest([revision.id,character_id,voice_id,line.id]))
        if cached is not None: return cached
        matches=[a for a in self.repo.list('audition',revision.owner_id,revision.project_id) if a['id']==key]
        if matches:
            if matches[0]['status']!='completed': raise Conflict('Audition outcome uncertain; inspect it before requesting another take')
            return matches[0]
        # One cached excerpt per voice and at most three new auditions per revision.
        if len(self.repo.list('audition',revision.owner_id,revision.project_id))>=3:
            raise ValueError('Project audition cap reached (3); use the normal render workflow')
        record=dict(id=key,owner_id=revision.owner_id,project_id=revision.project_id,status='started',voice_id=voice_id,
                    model_id='eleven_v4',element_id=line.id)
        self.repo.put('audition',record)
        result=await self.provider.render(CompiledChunk(id=key,scene_id=line.scene_id,
            request=DialogueRequest(inputs=(DialogueInput(voice_id=voice_id,text=line.original_text),)),fragments=()))
        asset=self.repo.store_bytes(revision.owner_id,revision.project_id,result.audio,result.mime,'audition.wav' if result.mime=='audio/wav' else 'audition.mp3',timing=result.timing)
        record.update(status='completed',artifact_id=asset['id'])
        self.repo.put('audition',record,replace=True)
        self.repo.complete_action(revision.owner_id,key,record)
        return record
