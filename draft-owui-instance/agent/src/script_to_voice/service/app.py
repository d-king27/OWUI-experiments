from __future__ import annotations
import hmac
import os
import uuid
from fastapi import FastAPI, Header, Depends, Request
from fastapi.responses import JSONResponse, FileResponse
from script_to_voice.contracts import Contract, Project
from script_to_voice.storage import Repository, NotFound, Conflict


class CreateProject(Contract):
    title: str


class ImportFile(Contract):
    file_id: str
    filename: str
    original_base64: str


class ChatRequest(Contract):
    chat_id: str
    message: str
    files: list[ImportFile] = []


def create_app(repository=None, token=None, workflow=None):
    repository = repository or Repository(os.environ.get('STV_DATA_ROOT','/data'))
    token = token if token is not None else os.environ.get('STV_SERVICE_TOKEN','')
    if len(token) < 24:
        raise RuntimeError('Configure STV_SERVICE_TOKEN with at least 24 characters')
    app = FastAPI(title='Script to Voice', docs_url=None, redoc_url=None)
    app.state.repository = repository

    def identity(authorization: str = Header(default=''), x_stv_owner: str = Header(default='')):
        if not hmac.compare_digest(authorization, 'Bearer '+token) or not x_stv_owner or len(x_stv_owner)>200:
            from fastapi import HTTPException
            raise HTTPException(401, 'Service authentication required')
        return x_stv_owner

    @app.exception_handler(ValueError)
    async def value_error(request, exc):
        code = 404 if isinstance(exc,NotFound) else 409 if isinstance(exc,Conflict) else 422
        # Domain exceptions must contain only controlled messages, never provider bodies.
        return JSONResponse(status_code=code,content={'code':{404:'not_found',409:'conflict',422:'invalid_request'}[code],
                           'message':str(exc), 'correlation_id':uuid.uuid4().hex})

    @app.exception_handler(Exception)
    async def unknown_error(request, exc):
        return JSONResponse(status_code=500,content={'code':'internal_error','message':'Operation failed; inspect server configuration',
                                                    'correlation_id':uuid.uuid4().hex})

    @app.get('/health')
    def health():
        return {'status':'ok','speech_mode':'mock' if os.environ.get('STV_MOCK','true').lower()=='true' else 'live',
                'speech_key_configured':bool(os.environ.get('ELEVENLABS_API_KEY'))}

    @app.post('/v1/projects')
    def create_project(body: CreateProject, owner=Depends(identity)):
        return repository.put('project',Project(id=uuid.uuid4().hex,owner_id=owner,title=body.title))

    @app.get('/v1/projects/{ident}')
    def get_project(ident: str, owner=Depends(identity)):
        return repository.get('project',ident,owner)

    @app.get('/v1/artifacts/{ident}/content')
    def artifact(ident: str, owner=Depends(identity)):
        meta,path = repository.artifact_path(ident,owner)
        return FileResponse(path,media_type=meta['mime'],filename=meta['filename'])

    if workflow is None:
        from .workflow import Workflow
        workflow=Workflow(repository)
    workflow.register(app,identity)
    return app
