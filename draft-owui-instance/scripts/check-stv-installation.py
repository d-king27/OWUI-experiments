"""Local auth-disabled instance only. Credentials stay in process memory."""
import os
from pathlib import Path
import subprocess
import httpx

ROOT=Path(__file__).resolve().parents[1]
with httpx.Client(base_url='http://127.0.0.1:3000',timeout=60) as client:
    auth=client.post('/api/v1/auths/signin',json={'email':'','password':''})
    auth.raise_for_status()
    token=auth.json()['token']
    env={**os.environ,'OPEN_WEBUI_API_KEY':token}
    for _ in range(2):
        subprocess.run(['pwsh','-NoProfile','-File',str(ROOT/'scripts/install-script-to-voice-function.ps1'),
                        '-BaseUrl','http://127.0.0.1:3000','-Update'],env=env,check=True)
    client.headers['Authorization']='Bearer '+token
    models=client.get('/api/models'); models.raise_for_status()
    ids={m['id'] for m in models.json()['data']}
    assert {'script_to_voice','open_webui_guide'}<=ids,ids
    for model,prompt in [('script_to_voice','help'),('open_webui_guide','What is Open WebUI?')]:
        result=client.post('/api/chat/completions',json={'model':model,'stream':False,
                           'messages':[{'role':'user','content':prompt}]})
        result.raise_for_status()
        content=result.json()['choices'][0]['message']['content']
        assert content and 'not configured' not in content,content
        print(model+': '+content[:180])
    print('PASS: two models, repeat installer, ordinary non-streaming API invocation')
