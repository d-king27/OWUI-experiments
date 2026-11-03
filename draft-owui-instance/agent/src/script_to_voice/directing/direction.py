import re
from script_to_voice.contracts import *

TAGS=('whispering','shouting','hesitant','restrained','laughing','pause')


def make_direction(revision,selection,cast,*,overrides=(),inferred=(),version=1):
    selection.validate_source(revision)
    require_scope(selection,cast)
    if cast.revision_id!=revision.id: raise ValueError('Foreign cast revision')
    elements={e.id:e for e in revision.elements}
    annotations=[]
    for eid in selection.selected_ids:
        line=elements[eid]
        for pid in line.parenthetical_ids:
            for tag in TAGS:
                if re.search(r'\b'+tag+r'\b',elements[pid].original_text,re.I):
                    annotations.append(Annotation(element_id=eid,offset=0,tag=tag,evidence_ids=(pid,),origin='source'))
    # User direction takes precedence at a given line/offset; explicit source beats inference.
    for annotation in (*inferred,*overrides):
        annotation=Annotation.model_validate_json(annotation.model_dump_json())
        if annotation.element_id not in selection.selected_ids: raise ValueError('Direction refers to unselected dialogue')
        if annotation.offset>len(elements[annotation.element_id].original_text): raise ValueError('Direction offset exceeds source')
        if not set(annotation.evidence_ids)<=set(elements): raise ValueError('Unknown direction evidence')
        if annotation.origin=='inferred' and not annotation.evidence_ids: raise ValueError('Inferred direction requires evidence')
        same=lambda a: a.element_id==annotation.element_id and a.offset==annotation.offset
        if annotation.origin=='user': annotations=[a for a in annotations if not same(a)]
        elif any(same(a) for a in annotations): continue
        annotations.append(annotation)
    annotations=tuple(sorted(set(annotations),key=lambda a:(elements[a.element_id].ordinal,a.offset,a.tag)))
    return DirectionPlan(id='direction_'+digest([selection.id,cast.semantic_hash(),[a.model_dump() for a in annotations],version]),
        owner_id=revision.owner_id,project_id=revision.project_id,selection_id=selection.id,
        selection_version=selection.version,cast_version=cast.version,version=version,annotations=annotations)
