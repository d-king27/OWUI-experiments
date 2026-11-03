"""Persist proposed casting separately from confirmed character assignments."""
import re
from urllib.parse import parse_qs, urlsplit

from script_to_voice.contracts import CastAssignment, ScriptRevision, Selection


def voice_reference(value):
    value=value.strip().strip('`<>')
    if value.startswith(('https://','http://')):
        url=urlsplit(value)
        if url.scheme!='https' or url.hostname not in {'elevenlabs.io','www.elevenlabs.io','app.elevenlabs.io'} or url.username or url.password or url.port not in (None,443):
            raise ValueError('Please provide an ElevenLabs HTTPS voice link or the voice ID itself')
        query=parse_qs(url.query)
        ids=query.get('voiceId',[])+query.get('voice_id',[])
        parts=url.path.strip('/').split('/')
        if not ids and len(parts)>=4 and parts[-3]=='share': ids=[parts[-1]]
        if not ids and len(parts)>=2 and parts[-2]=='voices': ids=[parts[-1]]
        if len(ids)!=1:
            raise ValueError('This link does not identify one voice. Please copy its voice ID from ElevenLabs')
        value=ids[0]
    if not re.fullmatch(r'[A-Za-z0-9_-]{1,128}',value):
        raise ValueError('Please provide a voice ID or an ElevenLabs voice link, without extra text')
    return value


def mapping_lines(message, revision):
    """Accept exact source names, one per line; never fetch a supplied URL."""
    manual=re.fullmatch(r'cast\s+(.+?)\s+as\s+(.+)',message.strip(),re.I)
    if manual: lines=[(manual[1],manual[2])]
    else:
        if re.match(r'^(?:select|find|single scene|single character|scene|character|use|direct|design|save)\b',message.strip(),re.I):
            return None
        lines=[]
        for line in message.strip().splitlines():
            match=re.fullmatch(r'\s*(?:-\s+)?(.+?)\s*[:=]\s*(.+?)\s*',line)
            if not match: return None
            lines.append((match[1],match[2]))
    if not lines: return None
    rows=[]
    for name,reference in lines:
        name=name.strip().strip('`')
        found=[c for c in revision.characters if name.casefold() in {c.name.casefold(),*(a.casefold() for a in c.aliases)}]
        if len(found)!=1:
            raise ValueError('Please use one exact character name: '+', '.join(c.name for c in revision.characters))
        rows.append({'character_id':found[0].id,'voice_id':voice_reference(reference),'origin':'selected'})
    if len({r['character_id'] for r in rows})!=len(rows):
        raise ValueError('Please provide only one voice line per character')
    return rows


def current_draft(state, revision, selection, cast):
    draft=state.get('cast_review')
    if draft and (draft['revision_id'],draft['selection_id'],draft['base_version'])==(revision.id,selection.id,cast.version):
        return draft
    return None


class CastReview:
    def __init__(self, repo, casting):
        self.repo=repo; self.casting=casting

    def context(self, owner, state):
        if not state.get('selection_id'): raise ValueError('Please select dialogue before reviewing voices')
        revision=self.repo.typed(ScriptRevision,'revision',state['revision_id'],owner)
        selection=self.repo.typed(Selection,'selection',state['selection_id'],owner)
        selection.validate_source(revision)
        if not selection.selected_ids: raise ValueError('Please select some dialogue before reviewing voices')
        required={e.character_id for e in revision.elements if e.id in selection.selected_ids}
        return revision,selection,self.casting.latest(revision),required

    def store(self, owner, state, draft):
        version,current=self.repo.session(owner,state['chat_id'])
        if current.get('revision_id')!=draft['revision_id'] or current.get('selection_id')!=draft['selection_id']:
            raise ValueError('Selected dialogue changed; please review voices for the new selection')
        current['cast_review']=draft
        current.pop('prepared_plan_id',None)
        self.repo.save_session(owner,state['chat_id'],current,version)

    async def propose(self, owner, state, *, refresh=False):
        r,s,cast,required=self.context(owner,state)
        old=current_draft(state,r,s,cast)
        if old and not refresh: return old
        result=await self.casting.proposals(r,s)
        voices={v['voice_id']:v for v in result['shortlist']}
        rows=[{**a,'voice_name':voices.get(a['voice_id'],{}).get('name',a['voice_id'])}
              for a in result['proposals']]
        # Explicit user choices survive a request to refresh creative suggestions.
        overrides=[a for a in (old or {}).get('rows',[]) if a.get('origin') in ('selected','designed')]
        rows=[a for a in rows if a['character_id'] not in {v['character_id'] for v in overrides}]+overrides
        draft={'revision_id':r.id,'selection_id':s.id,'base_version':cast.version,'rows':rows}
        self.store(owner,state,draft)
        return draft

    async def stage(self, owner, state, rows):
        r,s,cast,required=self.context(owner,state)
        if any(row['character_id'] not in required for row in rows):
            raise ValueError('Please provide voices only for characters in the current dialogue selection')
        validated=[]
        for row in rows:
            voice=await self.casting.validate_voice(r,row['voice_id'])
            validated.append({**row,'voice_name':voice.name})
        old=current_draft(state,r,s,cast)
        retained=[a for a in (old or {}).get('rows',[]) if a['character_id'] not in {v['character_id'] for v in rows}]
        draft={'revision_id':r.id,'selection_id':s.id,'base_version':cast.version,'rows':retained+validated}
        self.store(owner,state,draft)
        return draft

    async def confirm(self, owner, state):
        r,s,cast,required=self.context(owner,state)
        draft=current_draft(state,r,s,cast)
        if not draft:
            raise ValueError('That casting review is no longer current. Please request review cast and check the latest list')
        assigned={a.character_id for a in cast.assignments}
        if required-assigned-{a['character_id'] for a in draft['rows']}:
            raise ValueError('Some selected characters still need a proposed voice; provide their voice IDs before confirming')
        if not draft['rows']: raise ValueError('There are no voice changes to confirm')
        assignments=tuple(CastAssignment(character_id=a['character_id'],voice_id=a['voice_id'],
                                        origin=a.get('origin','selected')) for a in draft['rows'])
        result=await self.casting.assign_many(r,assignments,cast.version)
        version,current=self.repo.session(owner,state['chat_id'])
        current.pop('cast_review',None); current.pop('prepared_plan_id',None)
        self.repo.save_session(owner,state['chat_id'],current,version)
        return result
