"""Read-only subscription/model/catalog checks. Never prints keys or generates audio."""
import json
import os
from pathlib import Path
from datetime import datetime, timezone
import httpx

ROOT=Path(__file__).resolve().parents[1]


def main():
    settings={}
    for line in (ROOT/'.env').read_text(encoding='utf-8-sig').splitlines():
        if '=' in line and not line.lstrip().startswith('#'):
            name,value=line.split('=',1)
            settings[name.strip()]=value.strip().strip('"').strip("'")
    key=os.environ.get('ELEVENLABS_API_KEY') or settings.get('ELEVENLABS_API_KEY')
    if not key:
        print(json.dumps({'configured':False})); return
    summary={'checked_at':datetime.now(timezone.utc).isoformat(),'read_only':True,'checks':{}}
    with httpx.Client(base_url='https://api.elevenlabs.io',headers={'xi-api-key':key},timeout=30) as client:
        for name,path,params in [('subscription','/v1/user/subscription',None),
                                 ('models','/v1/models',None),('voices','/v2/voices',{'page_size':100})]:
            try:
                response=client.get(path,params=params)
            except httpx.HTTPError:
                summary['checks'][name]={'error':'network_error'}; continue
            result={'http_status':response.status_code}
            if response.is_success:
                try: data=response.json()
                except ValueError:
                    summary['checks'][name]={'error':'invalid_response'}; continue
                if name=='subscription':
                    fields=('tier','status','character_count','character_limit','next_character_count_reset_unix',
                            'max_credit_limit_extension','can_extend_character_limit','allowed_to_extend_character_limit',
                            'voice_slots_used','voice_limit','professional_voice_slots_used','professional_voice_limit')
                    result.update({k:data.get(k) for k in fields})
                    used=data.get('character_count'); limit=data.get('character_limit')
                    if isinstance(used,int) and isinstance(limit,int): result['remaining_reported_quota']=max(0,limit-used)
                    reset=data.get('next_character_count_reset_unix')
                    if isinstance(reset,(int,float)): result['reset_utc']=datetime.fromtimestamp(reset,timezone.utc).isoformat()
                elif name=='models':
                    result['model_count']=len(data)
                    result['speech_models']=[{k:m.get(k) for k in ('model_id','can_do_text_to_speech',
                        'maximum_text_length_per_request','token_cost_factor','model_rates')}
                        for m in data if m.get('model_id') in ('eleven_v4','eleven_v3','eleven_ttv_v3','eleven_multilingual_ttv_v2')]
                else:
                    result.update(returned_voice_count=len(data.get('voices',[])),has_more=data.get('has_more',False))
            else:
                # Never echo provider error bodies or request headers.
                result['error']='permission_or_authentication' if response.status_code in (401,403) else 'request_failed'
            summary['checks'][name]=result
    print(json.dumps(summary,indent=2))


if __name__=='__main__': main()
