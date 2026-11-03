from script_to_voice.contracts import *


def compile_plan(revision,selection,cast,direction,capabilities=None):
    capabilities=capabilities or ProviderCapabilities()
    selection.validate_source(revision)
    require_scope(selection,cast); require_scope(selection,direction)
    if not selection.selected_ids: raise ValueError('Cannot render an empty selection')
    if cast.revision_id!=revision.id or direction.selection_id!=selection.id or direction.selection_version!=selection.version or direction.cast_version!=cast.version:
        raise ValueError('Plan dependencies are stale')
    if direction.pronunciations: raise ValueError('Pronunciation substitutions are disabled until provider capability verification')
    voices={a.character_id:a.voice_id for a in cast.assignments}
    elements={e.id:e for e in revision.elements}
    tags={eid:[] for eid in selection.selected_ids}
    for a in direction.annotations:
        a=Annotation.model_validate_json(a.model_dump_json())
        if a.element_id not in tags or a.offset>len(elements[a.element_id].original_text) or not set(a.evidence_ids)<=set(elements):
            raise ValueError('Invalid direction references')
        tags[a.element_id].append(a)
    chunks=[]; inputs=[]; mappings=[]; scene=None; count=0; warnings=[]
    def flush():
        nonlocal inputs,mappings,count
        if inputs:
            request=DialogueRequest(inputs=tuple(inputs))
            chunks.append(CompiledChunk(id='chunk_'+digest([scene,request.provider_body(),[f.model_dump() for f in mappings]]),
                scene_id=scene,request=request,fragments=tuple(mappings)))
        inputs=[]; mappings=[]; count=0
    for eid in selection.selected_ids:
        e=elements[eid]; voice=voices.get(e.character_id)
        if not voice: raise ValueError('Missing cast for a selected character')
        if not e.original_text: raise ValueError('Empty source dialogue cannot be rendered')
        if '[' in e.original_text or ']' in e.original_text:
            warnings.append('Literal bracketed source text is retained; audition its interpretation before production.')
        if scene!=e.scene_id: flush(); scene=e.scene_id
        start=0
        def render(end):
            result=[]
            annotations=sorted(tags[eid],key=lambda a:(a.offset,a.tag))
            for pos in range(start,end):
                result.extend('['+a.tag+'] ' for a in annotations if a.offset==pos)
                result.append(e.original_text[pos])
            if end==len(e.original_text): result.extend('['+a.tag+'] ' for a in annotations if a.offset==end)
            return ''.join(result)
        while start<len(e.original_text):
            if inputs and (count>=capabilities.max_characters or len({i.voice_id for i in inputs}|{voice})>capabilities.max_voices): flush()
            budget=capabilities.max_characters-count
            lo=start; hi=min(len(e.original_text),start+budget)
            while lo<hi:
                mid=(lo+hi+1)//2
                if len(render(mid))<=budget: lo=mid
                else: hi=mid-1
            end=lo
            if end==start:
                if inputs: flush(); continue
                raise ValueError('Direction tags exceed the chunk character budget')
            if end<len(e.original_text):
                boundary=e.original_text.rfind(' ',start,end)
                if boundary>start+(end-start)//2: end=boundary+1
            rendered=render(end)
            index=len(inputs)
            inputs.append(DialogueInput(voice_id=voice,text=rendered))
            mappings.append(Fragment(element_id=eid,character_id=e.character_id,start=start,end=end,input_index=index,
                                     rendered_start=0,rendered_end=len(rendered)))
            count+=len(rendered); start=end
            if start<len(e.original_text): flush()
    flush()
    # Independently prove contiguous, once-only coverage in selected source order.
    coverage=[f for c in chunks for f in c.fragments]
    expected=[]
    for eid in selection.selected_ids:
        fs=[f for f in coverage if f.element_id==eid]
        cursor=0
        for f in fs:
            if f.start!=cursor or f.end<=f.start: raise ValueError('Source coverage gap or duplication')
            cursor=f.end
        if cursor!=len(elements[eid].original_text): raise ValueError('Source coverage incomplete')
        expected.extend(fs)
    if coverage!=expected: raise ValueError('Source order changed')
    payload=[selection.semantic_hash(),cast.semantic_hash(),direction.semantic_hash(),capabilities.semantic_hash(),[c.id for c in chunks]]
    return RenderPlan(id='plan_'+digest(payload),owner_id=revision.owner_id,project_id=revision.project_id,revision_id=revision.id,
        selection_id=selection.id,selection_hash=selection.semantic_hash(),cast_hash=cast.semantic_hash(),direction_hash=direction.semantic_hash(),
        capabilities=capabilities,chunks=tuple(chunks),estimated_characters=sum(len(i.text) for c in chunks for i in c.request.inputs),warnings=tuple(set(warnings)))
