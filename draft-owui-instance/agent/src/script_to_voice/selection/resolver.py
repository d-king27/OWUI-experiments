import re
from script_to_voice.contracts import *


class Clarification(ValueError):
    pass


def parse_command(query: str, revision: ScriptRevision) -> IntentProposal:
    """Documented deterministic commands for mock mode; not general language inference."""
    q=query.strip(); lower=q.casefold()
    if lower in ('whole script','entire script','select all','use the entire script','select script'):
        return IntentProposal(operation='select',scope='script')
    m=re.fullmatch(r'(?:select|find|use)\s+scene\s+(.+)',q,re.I)
    if m: return IntentProposal(operation='select',scope='scene',scene=m[1].strip())
    m=re.fullmatch(r'(?:find|select)\s+(?:text\s+)?["“](.+)["”]',q,re.I)
    if m: return IntentProposal(operation='select',scope='text',text=m[1])
    m=re.fullmatch(r'(?:find|select|use)?\s*(?:all\s+)?(.+?)(?:[\'’]s)?\s+lines',q,re.I)
    if m: return IntentProposal(operation='select',scope='character',character=m[1].strip())
    m=re.fullmatch(r'(?:only|filter)\s+(?:the\s+)?(.+?)\s+scenes',q,re.I)
    if m: return IntentProposal(operation='refine',scope='filter',time_of_day=m[1])
    m=re.fullmatch(r'(?:select|find)\s+location\s+(.+)',q,re.I)
    if m: return IntentProposal(operation='select',scope='filter',location=m[1])
    m=re.fullmatch(r'(?:select|find)\s+line\s+([\w-]+)',q,re.I)
    if m: return IntentProposal(operation='select',scope='ids',ids=(m[1],))
    if lower=='include the preceding exchange':
        return IntentProposal(operation='refine',scope='filter',preceding=1)
    return IntentProposal()


def resolve(revision: ScriptRevision, proposal: IntentProposal, query: str, prior: Selection | None=None) -> Selection:
    if prior: prior.validate_source(revision)
    lines=[e for e in revision.elements if e.kind=='dialogue']
    scenes={s.id:s for s in revision.scenes}
    if proposal.operation=='inspect' or proposal.scope=='none':
        raise Clarification('Choose script, character, scene or exact text; inspection does not select audio.')
    if proposal.operation=='refine':
        if prior is None: raise Clarification('Select some dialogue before refining it.')
        candidates=[e for e in lines if e.id in prior.selected_ids]
    else:
        candidates=lines
    if proposal.scope=='character' and not proposal.character:
        raise ValueError('Character selection requires a name')
    if proposal.character:
        name=proposal.character.casefold()
        found=[c for c in revision.characters if name in {c.id.casefold(),c.name.casefold(),*(a.casefold() for a in c.aliases)}]
        if len(found)!=1:
            raise Clarification('Specify a unique character: '+', '.join(c.name for c in revision.characters))
        candidates=[e for e in candidates if e.character_id==found[0].id]
    if proposal.scope=='scene' and not proposal.scene:
        raise ValueError('Scene selection requires a production number or description')
    if proposal.scene:
        name=proposal.scene.casefold()
        found=[s for s in revision.scenes if s.number.casefold()==name or s.id==proposal.scene]
        if not found: found=[s for s in revision.scenes if name in s.heading.casefold()]
        if len(found)!=1:
            raise Clarification('Specify a scene number: '+', '.join(s.number+' '+s.heading for s in found or revision.scenes))
        candidates=[e for e in candidates if e.scene_id==found[0].id]
    if proposal.scope=='text' and not proposal.text:
        raise ValueError('Text search requires nonempty text')
    if proposal.text:
        needle=' '.join(proposal.text.casefold().split())
        candidates=[e for e in candidates if needle in e.search_text]
    if proposal.scope=='ids':
        if not set(proposal.ids)<={e.id for e in lines}: raise ValueError('Planner returned unknown dialogue IDs')
        candidates=[e for e in candidates if e.id in proposal.ids]
    if proposal.time_of_day:
        candidates=[e for e in candidates if proposal.time_of_day.casefold() in scenes[e.scene_id].time_of_day.casefold()]
    if proposal.location:
        candidates=[e for e in candidates if proposal.location.casefold() in scenes[e.scene_id].location.casefold()]
    chosen={e.id for e in candidates}
    if proposal.preceding:
        for i,e in enumerate(lines):
            if e.id in chosen:
                chosen.update(p.id for p in lines[max(0,i-proposal.preceding):i] if p.scene_id==e.scene_id)
    selected=tuple(e.id for e in lines if e.id in chosen)
    selected_scenes={e.scene_id for e in lines if e.id in chosen}
    context=tuple(e.id for e in revision.elements if e.scene_id in selected_scenes and e.id not in chosen)
    version=(prior.version+1) if prior else 1
    selection=Selection(id='selection_'+digest([revision.id,selected,version,query]),owner_id=revision.owner_id,
        project_id=revision.project_id,revision_id=revision.id,selected_ids=selected,context_ids=context,query=query,version=version)
    selection.validate_source(revision)
    return selection
