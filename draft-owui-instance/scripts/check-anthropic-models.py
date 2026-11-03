"""Read-only Claude model access check; never prints credential or provider error bodies."""
import json
from pathlib import Path
import httpx

root=Path(__file__).resolve().parents[1]
settings=dict(line.split('=',1) for line in (root/'.env').read_text().splitlines()
              if '=' in line and not line.lstrip().startswith('#'))
key=settings.get('STV_LLM_API_KEY','').strip().strip('"').strip("'")
if not key: raise SystemExit('Configure STV_LLM_API_KEY securely first')
headers={'x-api-key':key,'anthropic-version':'2023-06-01'}
if settings.get('STV_LLM_WORKSPACE_ID'): headers['anthropic-workspace-id']=settings['STV_LLM_WORKSPACE_ID'].strip()
with httpx.Client(base_url='https://api.anthropic.com/v1',headers=headers,timeout=30) as client:
    response=client.get('/models',params={'limit':100})
    print('HTTP status:',response.status_code)
    if response.is_success:
        data=response.json()
        print(json.dumps({'models':[{k:m.get(k) for k in ('id','display_name','capabilities')} for m in data.get('data',[])],
                          'has_more':data.get('has_more',False)},indent=2))
