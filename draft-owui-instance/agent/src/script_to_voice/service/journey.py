"""Chat guidance derived from saved domain state, without provider calls."""
import time
import re
from urllib.parse import urlencode
from script_to_voice.contracts import IntentProposal, RenderPlan, ScriptRevision, Selection
from script_to_voice.selection import Clarification
from script_to_voice.service.cast_review import current_draft


HELP_COMMANDS = {'help', 'start', 'what next', 'next', 'hello', 'hi',
                 'what can you do', 'what can you do?', 'how does this work', 'how does this work?'}
WRONG_MODEL_COMMANDS = {'wrong model', 'i picked the wrong model', 'i chose the wrong model',
                        'i selected the wrong model'}

WELCOME = (
    'Script to Voice turns dialogue from an original Final Draft **.fdx** file into audio.\n\n'
    'Upload FDX → Select dialogue → Cast characters → Line direction → Generate → Listen/download.\n\n'
    'Send `help` or `what next` at any point. `scripts` lists your saved projects. '
    'Planning may use Claude credit; voice design, auditions and generation use ElevenLabs credit. '
    'Nothing is generated just by asking for help.'
)

WRONG_MODEL = (
    'Selected Script to Voice by mistake? Open the model selector at the top of the chat '
    'and choose the model you intended, such as **Open WebUI Guide**. '
    'For general chat, choose a configured chat model. You do not need to upload a script.\n\n'
    'Your saved scripts and audio remain available. Switching models does not cancel a queued '
    'render: if you started one here, send `status` or `cancel` in Script to Voice before switching. '
    'Cancellation stops future work; an accepted provider request may still finish.'
)


def code(value):
    return '`' + str(value).replace('`', '').replace('\n', ' ').replace('\r', ' ') + '`'


def voice_link(voice_id):
    if voice_id.startswith(('mock-','preview-')) or not re.fullmatch(r'[A-Za-z0-9_-]{1,128}',voice_id):
        return code(voice_id)
    return '['+voice_id+'](https://elevenlabs.io/app/voice-library?'+urlencode({'voiceId':voice_id})+')'


def selection_choice(query, revision, pending=None):
    """Resolve the plain-language selection menu against source metadata, without inference."""
    q=query.strip().rstrip('.!?')
    normalized=' '.join(q.casefold().split()).rstrip(':').strip()
    if normalized in ('entire script','the entire script','whole script','the whole script'):
        return IntentProposal(operation='select',scope='script'),None
    for scope in ('scene','character'):
        if normalized in (scope,'single '+scope,'a single '+scope,'a '+scope):
            return None,scope
    match=re.fullmatch(r'(?:(?:select|use)\s+)?(?:a\s+)?(?:single\s+)?(scene|character)(?:\s*:\s*|\s+)(.+)',q,re.I)
    scope=match[1].casefold() if match else pending
    value=(match[2] if match else q).strip().strip('"“”')
    if scope=='scene':
        found=[s for s in revision.scenes if value.casefold() in (s.number.casefold(),s.id.casefold(),s.heading.casefold())]
        if not found:
            words=set(re.findall(r'\w+',value.casefold()))-{
                'a','an','the','scene','where','with','at','in','on','of','and','is','set','takes','place','please'}
            found=[s for s in revision.scenes if words and words<=set(re.findall(r'\w+',
                   (s.heading+' '+s.location+' '+s.time_of_day).casefold()))]
        if len(found)!=1:
            raise Clarification('Please specify one scene by its number or a clearer location/time description. '+
                                'Available scenes: '+', '.join(s.number+' — '+s.heading for s in found or revision.scenes))
        return IntentProposal(operation='select',scope='scene',scene=found[0].id),None
    if scope=='character':
        found=[c for c in revision.characters if value.casefold() in
               {c.id.casefold(),c.name.casefold(),*(a.casefold() for a in c.aliases)}]
        if len(found)!=1:
            raise Clarification('Please specify one character by name: '+', '.join(c.name for c in revision.characters))
        return IntentProposal(operation='select',scope='character',character=found[0].id),None
    return None,None


def guidance(workflow, owner, state):
    """Read only owned objects. Never infer intent, fetch a catalog or prepare audio."""
    footer = '\n\nUse `help` for the journey or `wrong model` to leave this workflow.'
    if not state.get('revision_id'):
        return ('**Step 1 of 6 · Upload script**\n'
                'Attach the original **.fdx** file using the chat attachment control and send it '
                '(with `Use attached script` if the composer needs a message). '
                'PDF, DOCX and pasted text cannot replace the FDX original. '
                'To resume saved work, send `scripts`.') + footer
    r = workflow.repo.typed(ScriptRevision, 'revision', state['revision_id'], owner)
    source = '**Active script:** ' + code(r.title) + '\n\n'
    selection = (workflow.repo.typed(Selection, 'selection', state['selection_id'], owner)
                 if state.get('selection_id') else None)
    if state.get('selection_choice') or not selection or not selection.selected_ids:
        if state.get('selection_choice')=='scene':
            prompt=('Please specify the scene number, or describe its location/time using the scene list above. '
                    'I will select dialogue from that single scene. '
                    'To choose a different scope, reply **entire script** or **single character**.')
        elif state.get('selection_choice')=='character':
            prompt=('Please specify the character by name using the list above. '
                    'I will select that character’s dialogue throughout the script. '
                    'To choose a different scope, reply **entire script** or **single scene**.')
        else:
            prompt=('Please specify one of the following:\n\n'
                    '- **Entire script** — reply “entire script”.\n'
                    '- **A single scene** — reply “single scene”; I’ll help you describe or specify it.\n'
                    '- **A single character** — reply “single character”; I’ll ask for the character’s name.\n\n'
                    'Only dialogue from your chosen scope will be spoken.')
        return source + '**Step 2 of 6 · Select dialogue**\n\n' + prompt + footer
    cast = workflow.casting.latest(r)
    required = {e.character_id for e in r.elements if e.id in selection.selected_ids}
    assigned = {a.character_id for a in cast.assignments}
    missing = [c.name for c in r.characters if c.id in required - assigned]
    draft=current_draft(state,r,selection,cast)
    scope = f'**Selection:** {len(selection.selected_ids)} lines, {len(required)} characters.\n\n'
    if missing or (draft and draft['rows']):
        proposed={a['character_id']:a for a in (draft or {}).get('rows',[])}
        confirmed={a.character_id:a for a in cast.assignments}
        rows=[]
        for character in r.characters:
            if character.id not in required: continue
            if character.id in proposed:
                a=proposed[character.id]
                rows.append('- **'+character.name+'** → '+code(a.get('voice_name',a['voice_id']))+
                            ' ('+voice_link(a['voice_id'])+', proposed)')
            elif character.id in confirmed:
                rows.append('- **'+character.name+'** → '+voice_link(confirmed[character.id].voice_id)+' (already confirmed; retained)')
            else:
                rows.append('- **'+character.name+'** → no suggested voice available yet')
        prompt=('Missing voices: '+', '.join(code(n) for n in missing)+'.\n\n' if missing else
                'Voice changes awaiting your confirmation.\n\n')
        prompt+='**Proposed casting**\n\n'+'\n'.join(rows)+'\n\n'
        complete=not (required-assigned-set(proposed))
        if draft and draft['rows'] and complete:
            prompt+='Please double-check every character and voice above. When the list is correct, reply **confirm cast**. These changes are not applied until you confirm.\n\n'
        else:
            prompt+='Please provide a voice for each unresolved character before confirming. No new casting has been applied.\n\n'
        saved = {v['preview_id'] for v in workflow.repo.list('saved_voice', owner, r.project_id)}
        previews = [p for p in workflow.repo.list('voice_preview', owner, r.project_id)
                    if p['revision_id'] == r.id and p['character_id'] in required - assigned
                    and p['id'] not in saved and p.get('expires_at', 0) > time.time()]
        if previews:
            prompt+='You also have unsaved previews. Listen in the preview response, then save your chosen candidate with `save voice PREVIEW_ID as NAME`; saving uses an account voice slot and adds it to this review, without assigning it.\n\n'
        example=next(c.name for c in r.characters if c.id in required)
        prompt+='Are any of these characters already cast? If so, provide their voice IDs or ElevenLabs links, one line per character, for example '+code(example+': VOICE_ID')+'.'
        return source+scope+'**Step 3 of 6 · Review casting**\n\n'+prompt
    plan = (workflow.repo.typed(RenderPlan, 'plan', state['prepared_plan_id'], owner)
            if state.get('prepared_plan_id') else None)
    if not plan or plan.selection_id != selection.id or plan.cast_hash != cast.semantic_hash():
        return source + scope + ('**Step 4 of 6 · Line direction**\n\n'
            'Your cast is confirmed. Would you like to proceed with line direction? '
            'I’ll suggest how the selected dialogue should be delivered, such as tone and pauses, '
            'while keeping the original words unchanged.\n\n'
            'Reply **yes** or **proceed** to continue. This may use Claude credit; no audio is generated at this stage.') + footer
    job = workflow.jobs.status(owner, state['job_id']) if state.get('job_id') else None
    if not job or job['plan_id'] != plan.id:
        return ('**Step 5 of 6 · Review direction package**\n\n'
                'Download **direction-package.zip** and open **line-direction.txt** to review it. '
                'When you’re happy with the direction, reply **generate** to create the audio. '
                'Audio generation uses ElevenLabs credits.')
    status = job['status']
    if status == 'completed':
        action = ('Send `status` to retrieve the player, MP3 and cue-sheet downloads. '
                  'Listen for wording, order and character identity. Keep earlier takes when requesting a revised chunk.')
    elif any(c['status'] == 'ambiguous' for c in job['chunks']):
        action = ('Send `status` and inspect provider history with the administrator before retrying an uncertain attempt. '
                  'Do not start another generation to work around uncertainty: it may charge twice.')
    elif status in ('failed', 'partial_failed'):
        action = ('Send `status` to inspect completed/failed chunks. Resolve the reported cause first; '
                  '`retry failed` explicitly retries failed chunks and may use more credit. Successful chunks are retained.')
    elif status == 'cancelled' or job.get('cancel'):
        action = ('Cancellation was requested. Send `status` to inspect retained chunks. '
                  'An already accepted provider request may still finish. Ask the administrator before resuming cancelled work.')
    else:
        action = ('Audio is being generated. In the live chat, progress updates and the player appear automatically. '
                  'If the chat wait ends or you reconnect, send `status` to resume checking this saved job. '
                  'Send `cancel` to stop future parts; do not resend generation to recover a lost response.')
    return source + scope + f'**Step 6 of 6 · Listen/download or recover · {status}**\n' + action + footer
