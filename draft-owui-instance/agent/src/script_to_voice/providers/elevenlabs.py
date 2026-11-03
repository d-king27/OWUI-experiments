from __future__ import annotations
import base64
import os
from email.utils import parsedate_to_datetime
from datetime import datetime,timezone
import httpx
from script_to_voice.contracts import *


class ProviderError(ValueError):
    def __init__(self,kind,message,retry_after=0):
        super().__init__(message)
        self.kind=kind
        self.retry_after=retry_after


class ElevenLabs:
    def __init__(self, *, transport=None, key=None, live_enabled=None, capabilities=None):
        self.transport=transport; self.key=key; self.live_enabled=live_enabled
        self.capabilities=capabilities or ProviderCapabilities()
        self.models_checked=False

    @staticmethod
    def _require_live_id(value):
        if value.startswith(('mock-','preview-')):
            raise ProviderError('configuration','This ID belongs to an earlier mock test. Choose a real account voice or generate new live previews.')

    async def _request(self,method,path,*,body=None,params=None,paid=False):
        if paid and not (self.live_enabled if self.live_enabled is not None else os.environ.get('STV_LIVE_ENABLED')=='true'):
            raise ProviderError('configuration','Live generation is disabled; enable it only after approving a budget')
        key=self.key if self.key is not None else os.environ.get('ELEVENLABS_API_KEY','')
        if not key: raise ProviderError('configuration','Configure the server-side ElevenLabs API key')
        try:
            async with httpx.AsyncClient(base_url='https://api.elevenlabs.io',transport=self.transport,
                                         timeout=httpx.Timeout(90,connect=10),headers={'xi-api-key':key}) as client:
                async with client.stream(method,path,json=body,params=params) as response:
                    if response.status_code>=400:
                        code=response.status_code
                        kind={401:'authentication',403:'permission',404:'unavailable',409:'conflict',422:'validation',429:'rate_limit'}.get(code,
                              'transient' if code>=500 else 'validation')
                        delay=0
                        if response.headers.get('Retry-After'):
                            value=response.headers['Retry-After']
                            try: delay=max(0,float(value))
                            except ValueError:
                                try: delay=max(0,(parsedate_to_datetime(value)-datetime.now(timezone.utc)).total_seconds())
                                except Exception: pass
                        raise ProviderError(kind,{'authentication':'ElevenLabs rejected the API key',
                            'permission':'ElevenLabs denied this operation; check key permissions and voice slots',
                            'unavailable':'Voice or preview unavailable; select a replacement or create new previews',
                            'conflict':'ElevenLabs could not save the voice; check voice slots and preview state',
                            'validation':'ElevenLabs rejected this request; inspect the saved plan',
                            'rate_limit':'ElevenLabs rate limit reached',
                            'transient':'ElevenLabs is temporarily unavailable'}[kind],delay)
                    data=bytearray()
                    async for chunk in response.aiter_bytes():
                        data.extend(chunk)
                        if len(data)>90*1024*1024: raise ProviderError('validation','Provider response exceeds the size limit')
                    import json
                    try: payload=json.loads(data)
                    except ValueError: raise ProviderError('validation','Provider returned invalid JSON') from None
                    return payload,response.headers
        except httpx.ConnectTimeout:
            raise ProviderError('transient','Provider connection timed out') from None
        except (httpx.ReadTimeout,httpx.WriteTimeout,httpx.RemoteProtocolError):
            raise ProviderError('ambiguous' if paid else 'transient','Provider outcome is uncertain; inspect the account before retrying') from None
        except httpx.HTTPError:
            raise ProviderError('ambiguous' if paid else 'transient','Provider transport failed; inspect the account before retrying') from None

    async def verify_models(self):
        data,_=await self._request('GET','/v1/models')
        if not isinstance(data,list) or not any(m.get('model_id')=='eleven_v4' and m.get('can_do_text_to_speech') for m in data):
            raise ProviderError('configuration','This account has not reported eleven_v4 speech support; no fallback was used')
        self.models_checked=True
        return data

    @staticmethod
    def _voice(data):
        try: return Voice(voice_id=data['voice_id'],name=data['name'],labels=data.get('labels') or {})
        except Exception: raise ProviderError('validation','Provider returned an invalid voice') from None

    async def list_voices(self,cursor=None):
        params={'page_size':100}
        if cursor: params['next_page_token']=cursor
        data,_=await self._request('GET','/v2/voices',params=params)
        try: return VoicePage(voices=tuple(self._voice(v) for v in data['voices']),next_cursor=data.get('next_page_token') if data.get('has_more') else None)
        except (KeyError,TypeError): raise ProviderError('validation','Provider returned an invalid voice catalog') from None

    async def get_voice(self,voice_id):
        self._require_live_id(voice_id)
        from urllib.parse import quote
        data,_=await self._request('GET','/v1/voices/'+quote(voice_id,safe=''))
        return self._voice(data)

    async def design_previews(self,request):
        # Revalidate even when callers used model_copy (which intentionally skips validation).
        request=VoiceDesignRequest.model_validate_json(request.model_dump_json())
        body=request.model_dump(exclude={'schema_version'})
        data,_=await self._request('POST','/v1/text-to-voice/design',body=body,paid=True)
        try:
            previews=tuple(VoicePreview(generated_voice_id=p['generated_voice_id'],audio_base64=p['audio_base_64'],mime=p['media_type']) for p in data['previews'])
            if not 1<=len(previews)<=3: raise ValueError()
            return previews
        except Exception: raise ProviderError('validation','Provider returned invalid voice previews') from None

    async def save_preview(self,generated_voice_id,name,description):
        self._require_live_id(generated_voice_id)
        data,_=await self._request('POST','/v1/text-to-voice',body={'voice_name':name,'voice_description':description,
                                      'generated_voice_id':generated_voice_id},paid=True)
        return self._voice(data)

    async def render(self,chunk):
        request=DialogueRequest.model_validate_json(chunk.request.model_dump_json())
        for item in request.inputs:
            self._require_live_id(item.voice_id)
        if sum(len(i.text) for i in request.inputs)>self.capabilities.max_characters or len({i.voice_id for i in request.inputs})>self.capabilities.max_voices:
            raise ProviderError('validation','Compiled request exceeds the verified endpoint limits')
        if not self.models_checked: await self.verify_models()
        data,headers=await self._request('POST',self.capabilities.endpoint,body=request.provider_body(),
                                        params={'output_format':self.capabilities.output_format},paid=True)
        try:
            audio=base64.b64decode(data['audio_base64'],validate=True)
            if not audio or len(audio)>64*1024*1024: raise ValueError()
            timing={k:data.get(k) for k in ('alignment','normalized_alignment','voice_segments')}
            for segment in timing.get('voice_segments') or []:
                index=segment['dialogue_input_index']
                if type(index)!=int or not 0<=index<len(request.inputs) or segment['voice_id']!=request.inputs[index].voice_id:
                    raise ValueError()
            usage=headers.get('character-cost')
            return ProviderAudioResult(audio=audio,request_id=headers.get('request-id'),timing=timing,usage=int(usage) if usage else None)
        except Exception: raise ProviderError('ambiguous','Provider returned unusable audio or timing; generation may have been billed') from None
