"""Downloadable direction review. No model or voice-provider calls."""
import io
import zipfile

from script_to_voice.contracts import DirectionPlan


def load_direction(repo, owner, plan):
    for record in repo.list('direction',owner,plan.project_id):
        direction=repo.typed(DirectionPlan,'direction',record['id'],owner)
        if direction.semantic_hash()==plan.direction_hash:
            return direction
    raise ValueError('Saved line direction could not be loaded; ask the administrator to check this project')


def selected_lines(revision, selection):
    ids=set(selection.selected_ids)
    return [e for e in revision.elements if e.id in ids]


def tags_by_line(direction):
    tags={}
    for annotation in direction.annotations:
        tags.setdefault(annotation.element_id,set()).add(annotation.tag)
    return tags


def delivery(tags):
    return ', '.join(sorted(tags)) if tags else 'natural delivery; no additional direction'


def ready_message():
    return 'Your direction package is ready. Your original dialogue is unchanged; no audio has been generated.'


def full_report(revision, selection, direction):
    lines=selected_lines(revision,selection); tags=tags_by_line(direction)
    names={c.id:c.name for c in revision.characters}; scenes={s.id:s for s in revision.scenes}
    report=[revision.title,'Line direction — full selected-dialogue breakdown',
            f'{len(lines)} selected dialogue lines. Original words and order retained.',
            'Line numbers below refer to this selection. No delivery notes means natural delivery.','']
    previous=None
    for index,line in enumerate(lines,1):
        if line.scene_id!=previous:
            scene=scenes[line.scene_id]
            report.extend(['',f'SCENE {scene.number} — {scene.heading}',''])
            previous=line.scene_id
        report.extend([f'{index}. {names[line.character_id]} — {delivery(tags.get(line.id,()))}',line.original_text,''])
    return '\n'.join(report)


def package_bytes(revision, selection, direction, plan):
    readme=('DIRECTION PACKAGE\n\n'
            'Open line-direction.txt to review all selected dialogue and delivery notes.\n'
            'render-plan.json contains optional technical request and source-mapping details.\n\n'
            'No audio has been generated. Return to the chat to request changes, '
            'or reply generate when you are ready to create audio using ElevenLabs credits.\n'
            'If you change the selected dialogue, cast or direction, prepare and review a new package.\n')
    if plan.warnings: readme+='\nPreparation notes:\n'+'\n'.join('- '+warning for warning in plan.warnings)+'\n'
    buffer=io.BytesIO()
    with zipfile.ZipFile(buffer,'w') as package:
        for filename,text in (('README.txt',readme),('line-direction.txt',full_report(revision,selection,direction)),
                              ('render-plan.json',plan.model_dump_json(indent=2))):
            # Stable metadata makes re-downloading an unchanged package byte-identical.
            info=zipfile.ZipInfo(filename,date_time=(1980,1,1,0,0,0))
            package.writestr(info,text.encode('utf-8'),compress_type=zipfile.ZIP_DEFLATED)
    return buffer.getvalue()


def detail_page(revision, selection, direction, *, scope='all', value='', offset=0):
    lines=list(enumerate(selected_lines(revision,selection),1)); tags=tags_by_line(direction)
    title='Selected dialogue'
    if scope=='scene':
        available=[s for s in revision.scenes if any(e.scene_id==s.id for _,e in lines)]
        found=[s for s in available if value.casefold() in (s.number.casefold(),s.id.casefold(),s.heading.casefold())]
        if not found: found=[s for s in available if value.casefold() in s.heading.casefold()]
        if len(found)!=1:
            raise ValueError('Please specify one selected scene: '+', '.join(s.number+' — '+s.heading for s in found or available))
        lines=[(i,e) for i,e in lines if e.scene_id==found[0].id]
        title='Scene '+found[0].number+' — '+found[0].heading
    elif scope=='character':
        available=[c for c in revision.characters if any(e.character_id==c.id for _,e in lines)]
        found=[c for c in available if value.casefold() in {c.name.casefold(),*(a.casefold() for a in c.aliases)}]
        if len(found)!=1: raise ValueError('Please specify one selected character: '+', '.join(c.name for c in available))
        lines=[(i,e) for i,e in lines if e.character_id==found[0].id]
        title=found[0].name
    names={c.id:c.name for c in revision.characters}
    page=lines[offset:offset+20]
    if not page: raise ValueError('There are no more lines in this view. Request another scene or character, or direction summary')
    parts=['**'+title+'**',f'Showing {offset+1}–{offset+len(page)} of {len(lines)} lines in this view.']
    for index,line in page:
        excerpt=line.original_text if len(line.original_text)<=240 else line.original_text[:240]+'… [full line in download]'
        parts.append(f'- {index}. **{names[line.character_id]}** — {delivery(tags.get(line.id,()))}: {excerpt}')
    if offset+len(page)<len(lines): parts.append('Reply **more direction** for the next twenty lines.')
    parts.append('Read-only view. Nothing has been generated or changed.')
    return '\n\n'.join(parts),offset+len(page)
