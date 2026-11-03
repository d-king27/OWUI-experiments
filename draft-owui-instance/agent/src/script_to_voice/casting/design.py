import base64
import time
import uuid
from script_to_voice.contracts import *
from script_to_voice.storage import Conflict


class DesignService:
    def __init__(self,repo,provider,casting):
        self.repo=repo; self.provider=provider; self.casting=casting

    async def previews(self,revision,character_id,request,key):
        if character_id not in {c.id for c in revision.characters}: raise ValueError('Unknown character')
        action='design:'+key
        cached=self.repo.claim_action(revision.owner_id,action,digest([revision.id,character_id,request.semantic_hash()]))
        if cached is not None: return cached
        if len(self.repo.list('voice_preview',revision.owner_id,revision.project_id))>=9:
            raise ValueError('Project preview cap reached (9 candidates)')
        previews=await self.provider.design_previews(request)
        result=[]
        for preview in previews:
            try: audio=base64.b64decode(preview.audio_base64,validate=True)
            except ValueError: raise ValueError('Invalid preview audio') from None
            asset=self.repo.store_bytes(revision.owner_id,revision.project_id,audio,preview.mime,
                                       'voice-preview.wav' if preview.mime=='audio/wav' else 'voice-preview.mp3')
            record=dict(id=uuid.uuid4().hex,owner_id=revision.owner_id,project_id=revision.project_id,
                revision_id=revision.id,character_id=character_id,generated_voice_id=preview.generated_voice_id,
                artifact_id=asset['id'],description=request.voice_description,model_id=request.model_id,
                text=request.text,created_at=time.time(),expires_at=time.time()+3600)
            self.repo.put('voice_preview',record); result.append(record)
        self.repo.complete_action(revision.owner_id,action,result)
        return result

    async def save(self,revision,preview_id,name,key):
        preview=self.repo.get('voice_preview',preview_id,revision.owner_id)
        if preview['revision_id']!=revision.id: raise ValueError('Preview belongs to another revision')
        # Deduplicate by candidate as well as action key. An uncertain provider save must never be repeated blindly.
        candidate_action='save-preview:'+preview_id
        cached=self.repo.claim_action(revision.owner_id,candidate_action,digest([preview_id,name]))
        if cached is not None: return cached
        if time.time()>preview['expires_at']: raise ValueError('Preview expired; explicitly request new previews')
        voice=await self.provider.save_preview(preview['generated_voice_id'],name,preview['description'])
        saved=dict(id=uuid.uuid4().hex,owner_id=revision.owner_id,project_id=revision.project_id,
                   preview_id=preview_id,voice_id=voice.voice_id,name=name,action_key=key)
        # Saving a provider voice is separate from confirming a character assignment.
        self.repo.put('saved_voice',saved)
        self.repo.complete_action(revision.owner_id,candidate_action,saved)
        return saved
