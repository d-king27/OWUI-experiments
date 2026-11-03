"""
title: Script to Voice
author: OWUI experiments
version: 0.3.0
required_open_webui_version: 0.11.0
description: Source-faithful script selection, casting and durable audio production.
"""
from __future__ import annotations
import os
import asyncio
from urllib.parse import quote
import httpx


class Pipe:
    def __init__(self, *, transport=None, poll_interval=2, watch_seconds=180):
        self.name='Script to Voice'
        self.transport=transport
        self.poll_interval=max(0,float(poll_interval))
        self.watch_seconds=max(0,float(watch_seconds))

    @staticmethod
    async def emit_status(emitter, description, *, done=False):
        if not callable(emitter): return False
        try:
            await emitter({'type':'status','data':{'description':description,'done':done}})
            return True
        except Exception:
            # The optional UI channel must not invalidate a saved job or its files.
            return False

    async def watch_job(self,client,result,emitter):
        deadline=asyncio.get_running_loop().time()+self.watch_seconds
        last_description=None
        while result.get('job',{}).get('status') in ('queued','running'):
            job=result['job']
            description=('Stopping future audio parts…' if job.get('cancellation_requested') else
                f'Generating audio… {job["completed"]} of {job["total"]} parts ready')
            if description!=last_description:
                if not await self.emit_status(emitter,description):
                    return {**result,'message':'Your audio job is saved. Live progress disconnected; send status to check it. Do not resend generate.'}
                last_description=description
            remaining=deadline-asyncio.get_running_loop().time()
            if remaining<=0:
                return {**result,'message':'Your audio is still being generated in the background. Send **status** to resume progress and retrieve it. Do not resend generate.'}
            await asyncio.sleep(min(self.poll_interval,remaining))
            try:
                response=await client.get('/v1/render-jobs/'+quote(job['id'],safe='')+'/result',timeout=10)
                response.raise_for_status()
                updated=response.json()
                progress=updated.get('job') if isinstance(updated,dict) else None
                if (not isinstance(progress,dict) or progress.get('id')!=job['id']
                    or progress.get('status') not in ('queued','running','completed','cancelled','failed','partial_failed')
                    or not isinstance(updated.get('message'),str)):
                    raise ValueError('Invalid progress response')
                result=updated
            except (httpx.HTTPError,ValueError):
                return {**result,'message':'The progress connection was interrupted. Your saved audio job is unaffected; send **status** after reconnecting. Do not resend generate.'}
        return result

    async def pipe(self, body: dict, __user__: dict | None = None, __request__=None,
                   __metadata__: dict | None = None, __files__: list | None = None,
                   __task__: str | None = None, __event_emitter__=None):
        metadata=__metadata__ or {}
        if __task__ or metadata.get('task'):
            return 'Script to Voice'
        if not __user__ or not __user__.get('id'):
            return 'Script to Voice needs a signed-in user identity.'
        if os.environ.get('STV_ENABLED','false').lower()!='true':
            return 'Script to Voice is disabled. Ask the administrator to enable its service.'
        token=os.environ.get('STV_SERVICE_TOKEN','')
        if len(token)<24:
            return 'Script to Voice needs its private service connection configured.'
        prompt=metadata.get('user_prompt')
        if not isinstance(prompt,str):
            prompt=next((m.get('content','') for m in reversed(body.get('messages',[])) if m.get('role')=='user'),'')
        if isinstance(prompt,list):
            prompt='\n'.join(p.get('text','') for p in prompt if p.get('type')=='text')
        if not isinstance(prompt,str) or not prompt.strip():
            prompt='Use attached script' if __files__ else 'help'
        chat_id=metadata.get('chat_id') or 'api-default'
        headers={'Authorization':'Bearer '+token,'X-STV-Owner':__user__['id']}
        progress_started=False
        final_status='Ready'
        try:
            progress_started=await self.emit_status(__event_emitter__,'Working on your Script to Voice request…')
            async with httpx.AsyncClient(base_url=os.environ.get('STV_SERVICE_URL','http://script-to-voice:8000'),
                                         headers=headers,timeout=60,transport=self.transport) as client:
                imports=[]; unsupported=[]
                # Leaving the workflow must work even when a mistaken file is still attached.
                leaving=prompt.strip().casefold().rstrip('.!?') in {
                    'wrong model','i picked the wrong model','i chose the wrong model','i selected the wrong model'}
                asking_help=prompt.strip().casefold().rstrip('.!?') in {
                    'help','start','what next','next','hello','hi','what can you do','how does this work'}
                for file in ([] if leaving or asking_help else (__files__ or [])):
                    file_id=file.get('id') or file.get('file',{}).get('id')
                    if not file_id:
                        continue
                    from openwebui.functions.script_to_voice_files import original_file
                    filename,data=await original_file(file_id,__user__)
                    if not filename.lower().endswith('.fdx'):
                        unsupported.append(filename)
                        continue
                    import base64
                    imports.append({'file_id':file_id,'filename':filename,'original_base64':base64.b64encode(data).decode()})
                if unsupported:
                    final_status='An original FDX attachment is needed'
                    return ('**Step 1 of 6 · Upload script**\n'
                            'This workflow needs an original Final Draft **.fdx** file. '
                            'Remove the other attachments and attach one FDX. PDF, DOCX and pasted text cannot replace it. '
                            'No import, planning or generation was requested; your saved work is retained.\n\n'
                            'If you chose Script to Voice by mistake, send `wrong model` or choose another model at the top of the chat.')
                response=await client.post('/v1/chat',json={'chat_id':chat_id,'message':prompt,'files':imports})
                if response.status_code>=400:
                    final_status='The request needs attention'
                    result=response.json()
                    return result.get('message','Script to Voice could not complete this request.')+(
                        '\n\nTry `help` for the guided steps. If you had a render running, try `status` after reconnecting. '
                        'Do not repeat a paid request after a timeout without checking its outcome.')
                result=response.json()
                if progress_started and result.get('job',{}).get('status') in ('queued','running'):
                    result=await self.watch_job(client,result,__event_emitter__)
                job_status=result.get('job',{}).get('status')
                if job_status=='completed': final_status='Audio ready'
                elif job_status in ('failed','partial_failed'): final_status='Audio generation needs attention'
                elif job_status=='cancelled': final_status='Audio generation cancelled'
                elif job_status in ('queued','running'):
                    final_status='Audio continues in the background'
                    if not progress_started:
                        result['message']+=' Send status to retrieve the saved job and its audio.'
                text=result['message']
                if progress_started and result.get('artifacts'):
                    await self.emit_status(__event_emitter__,'Preparing your player and downloads…' if job_status else 'Preparing your download…')
                for artifact in result.get('artifacts',[]):
                    content=await client.get('/v1/artifacts/'+artifact['id']+'/content')
                    content.raise_for_status()
                    from openwebui.functions.script_to_voice_files import register_output
                    output=await register_output(__request__,__user__,content.content,artifact['filename'],artifact['mime'])
                    url=output['url']
                    text+=f'\n\n[Download {artifact["filename"]}]({url}?attachment=true)'
                    if artifact['mime'].startswith('audio/'):
                        # v0.11.0 HTMLToken takes the URL from the tag body, not src.
                        text+=f'\n\n<div>\n<audio>{url}</audio>\n</div>\n'
                return text
        except (httpx.HTTPError,ValueError):
            final_status='The request needs attention'
            return ('Script to Voice is unavailable or the attachment/request could not be validated. '
                    'Check that the attachment is your original FDX, or ask the administrator to check the service. '
                    'Saved jobs remain available; try `status` after reconnecting. '
                    'Do not repeat voice design, audition or generation after a timeout without checking its outcome. '
                    'To leave this workflow, choose another model at the top of the chat.')
        except asyncio.CancelledError:
            final_status='Chat wait stopped; the saved audio job can continue'
            raise
        finally:
            if progress_started:
                await self.emit_status(__event_emitter__,final_status,done=True)
