"""Only this adapter and the Pipe know Open WebUI internals (pinned v0.11.0)."""
import asyncio
import io
from pathlib import Path

MAX_ORIGINAL_BYTES = 8*1024*1024


async def original_file(file_id, user_payload):
    from open_webui.models.files import Files
    from open_webui.storage.provider import Storage
    owner = user_payload.get('id')
    if not owner:
        raise ValueError('Sign in to access script files')
    record = await Files.get_file_by_id(file_id)
    if not record or record.user_id != owner or not record.path:
        raise ValueError('Script file unavailable to this user')
    path = Path(await asyncio.to_thread(Storage.get_file, record.path))
    if path.stat().st_size > MAX_ORIGINAL_BYTES:
        raise ValueError('Script exceeds the 8 MiB import limit')
    data = await asyncio.to_thread(path.read_bytes)
    if len(data)>MAX_ORIGINAL_BYTES:
        raise ValueError('Script exceeds the 8 MiB import limit')
    return record.filename,data


async def register_output(request, user_payload, data, filename, mime):
    from fastapi import UploadFile
    from starlette.datastructures import Headers
    from open_webui.models.users import Users
    from open_webui.routers.files import upload_file_handler
    if len(data)>64*1024*1024:
        raise ValueError('Output exceeds the 64 MiB delivery limit')
    user = await Users.get_user_by_id(user_payload['id'])
    if not user:
        raise ValueError('User unavailable')
    upload=UploadFile(file=io.BytesIO(data),filename=Path(filename).name,headers=Headers({'content-type':mime}))
    try:
        result=await upload_file_handler(request,file=upload,metadata={'script_to_voice':True},
            process=False,process_in_background=False,user=user,background_tasks=None,db=None)
    finally:
        await upload.close()
    ident=result['id'] if isinstance(result,dict) else result.id
    return {'id':ident,'url':f'/api/v1/files/{ident}/content'}
