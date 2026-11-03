"""Mock-only local auth-disabled OWUI acceptance. Never prints session credentials."""
from pathlib import Path
import re
import time
import uuid
import sys
import httpx

sys.stdout.reconfigure(encoding='utf-8')

root=Path(__file__).resolve().parents[1]
with httpx.Client(base_url='http://127.0.0.1:3000',timeout=120) as client:
    response=client.post('/api/v1/auths/signin',json={'email':'','password':''}); response.raise_for_status()
    client.headers['Authorization']='Bearer '+response.json()['token']
    upload=client.post('/api/v1/files/',params={'process':'false'},files={'file':('acceptance.fdx',(root/'tests/script_to_voice/fixtures/two_speakers.fdx').read_bytes(),'application/xml')})
    upload.raise_for_status(); file=upload.json()
    chat='stv-acceptance-'+uuid.uuid4().hex
    def ask(message):
        response=client.post('/api/chat/completions',json={'model':'script_to_voice','stream':False,'chat_id':chat,
            'messages':[{'role':'user','content':message}], 'files':[{'type':'file','id':file['id'],'file':file}]})
        response.raise_for_status()
        text=response.json()['choices'][0]['message']['content']
        print(message+': '+text[:240]); return text
    assert 'Imported' in ask('Use the attached script')
    assert 'Selected 5 lines' in ask('select all')
    for name,voice in [('MIRA','mock-1'),('JONAH','mock-2'),('GUARD (NORTH)','mock-3')]:
        assert 'Assigned' in ask(f'cast {name} as {voice}')
    previews=ask('design voice for MIRA: A calm measured expressive conversational voice')
    candidate=re.search(r'`([0-9a-f]{32})`',previews)
    assert candidate,previews
    assert 'Saved voice' in ask('save voice '+candidate[1]+' as Acceptance voice')
    assert 'Audition ready' in ask('audition MIRA')
    assert 'Plan:' in ask('plan')
    assert 'Queued job' in ask('generate')
    for _ in range(30):
        status=ask('status')
        if ': completed.' in status: break
        time.sleep(1)
    assert ': completed.' in status,status
    links=re.findall(r'\]\((/api/v1/files/[^)]+)\)',status)
    assert links,status
    for link in links:
        response=client.get(link); response.raise_for_status(); assert response.content
        response=client.get(link,headers={'Range':'bytes=0-31'})
        assert response.status_code==206,response.status_code
        assert len(response.content)==32
    print('PASS: OWUI import, full selection, existing/designed cast, audition, plan, multi-chunk job, registered/ranged downloads')
