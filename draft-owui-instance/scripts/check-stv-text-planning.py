"""Capped live Claude planning through local OWUI; synthetic script and mocked speech only."""
from pathlib import Path
import re
import sys
import uuid
import httpx

sys.stdout.reconfigure(encoding='utf-8')
root=Path(__file__).resolve().parents[1]
with httpx.Client(base_url='http://127.0.0.1:3000',timeout=120) as client:
    auth=client.post('/api/v1/auths/signin',json={'email':'','password':''}); auth.raise_for_status()
    client.headers['Authorization']='Bearer '+auth.json()['token']
    data=(root/'tests/script_to_voice/fixtures/two_speakers.fdx').read_bytes()
    upload=client.post('/api/v1/files/',params={'process':'false'},files={'file':('text-planner-acceptance.fdx',data,'application/xml')})
    upload.raise_for_status(); file=upload.json(); chat='stv-text-'+uuid.uuid4().hex
    def ask(prompt):
        response=client.post('/api/chat/completions',json={'model':'script_to_voice','stream':False,'chat_id':chat,
            'messages':[{'role':'user','content':prompt}],'files':[{'type':'file','id':file['id'],'file':file}]})
        response.raise_for_status(); result=response.json()['choices'][0]['message']['content']
        print(prompt+': '+result[:600]); return result
    assert 'Imported' in ask('Use this script')
    assert 'Selected 3 lines' in ask('Please choose every line spoken by Mira.')
    assert 'Selected 2 lines' in ask('Keep just those in scenes set at night.')
    assert 'Suggested for MIRA' in ask('suggest voices')
    first=ask('planner budget')
    assert 'choose a voice' in ask('cast')
    assert ask('planner budget')==first,'Cast inspection invoked inference'
    for name,voice in [('MIRA','mock-1'),('JONAH','mock-2'),('GUARD (NORTH)','mock-3')]:
        assert 'Assigned' in ask(f'cast {name} as {voice}')
    assert 'Selected 5 lines' in ask('select all')
    plan=ask('plan'); assert 'Plan: 2 chunks' in plan,plan
    link=re.search(r'\]\((/api/v1/files/[^)]+)\)',plan)
    assert link
    document=client.get(link[1]); document.raise_for_status(); plan_data=document.json()
    assert len(plan_data['chunks'])==2
    assert any(a['text'].startswith('[whispering]') for c in plan_data['chunks'] for a in c['request']['inputs'])
    before=ask('planner budget'); assert 'Plan: 2 chunks' in ask('plan')
    assert ask('planner budget')==before,'Cached plan invoked inference'
    inspect=ask('Who are the characters and how many scenes are there?')
    assert 'MIRA' in inspect and 'JONAH' in inspect and '2 scenes' in inspect
    assert 'No render job' in ask('status')
    print('PASS: live Claude intent, follow-up, cast proposal, bounded direction, exact-source plan, cache reuse and no render job')
