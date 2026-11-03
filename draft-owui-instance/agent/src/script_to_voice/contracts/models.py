from __future__ import annotations

import hashlib
import json
from typing import Annotated, Literal
from pydantic import BaseModel, ConfigDict, Field, model_validator

Id = Annotated[str, Field(min_length=1, max_length=200)]
Positive = Annotated[int, Field(ge=1)]


class Contract(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True, frozen=True)
    schema_version: Literal[1] = 1

    def semantic_hash(self) -> str:
        return digest(self.model_dump(mode='json', exclude={'created_at'}))


def digest(value) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False,
                                     separators=(',', ':')).encode()).hexdigest()


class Owned(Contract):
    id: Id
    owner_id: Id
    created_at: float = 0.0


class Project(Owned):
    title: str


class TextRun(Contract):
    text: str
    style: str = ''


class SourceSpan(Contract):
    paragraph: Positive
    xpath: str


class ScriptElement(Contract):
    id: Id
    scene_id: Id
    ordinal: int = Field(ge=0)
    kind: Literal['scene_heading', 'character', 'dialogue', 'parenthetical', 'action', 'unknown']
    original_text: str
    search_text: str
    character_id: Id | None = None
    dialogue_block_id: Id | None = None
    parenthetical_ids: tuple[Id, ...] = ()
    source_span: SourceSpan
    runs: tuple[TextRun, ...] = ()


class Scene(Contract):
    id: Id
    number: str
    heading: str
    location: str = ''
    time_of_day: str = ''


class Character(Contract):
    id: Id
    name: str
    aliases: tuple[str, ...] = ()


class ScriptRevision(Owned):
    project_id: Id
    script_id: Id
    original_file_id: Id
    original_hash: str
    parser_version: str = 'fdx-1'
    title: str
    language: str = 'en'
    scenes: tuple[Scene, ...]
    elements: tuple[ScriptElement, ...]
    characters: tuple[Character, ...]
    warnings: tuple[str, ...] = ()

    @model_validator(mode='after')
    def references(self):
        elements = {e.id: e for e in self.elements}
        scenes = {s.id for s in self.scenes}
        characters = {c.id for c in self.characters}
        if len(elements) != len(self.elements) or len(scenes) != len(self.scenes) or len(characters) != len(self.characters):
            raise ValueError('Duplicate source IDs')
        if [e.ordinal for e in self.elements] != sorted({e.ordinal for e in self.elements}):
            raise ValueError('Source ordinals must be unique and ordered')
        for e in self.elements:
            if e.scene_id not in scenes or (e.character_id and e.character_id not in characters):
                raise ValueError('Foreign source reference')
            if e.kind == 'dialogue' and not e.character_id:
                raise ValueError('Dialogue must have a character')
            for pid in e.parenthetical_ids:
                p = elements.get(pid)
                if not p or p.kind != 'parenthetical' or p.dialogue_block_id != e.dialogue_block_id or p.ordinal >= e.ordinal:
                    raise ValueError('Invalid parenthetical reference')
        return self


class Selection(Owned):
    project_id: Id
    revision_id: Id
    selected_ids: tuple[Id, ...]
    context_ids: tuple[Id, ...] = ()
    query: str
    version: Positive

    def validate_source(self, revision: ScriptRevision):
        require_scope(self, revision)
        if self.revision_id != revision.id:
            raise ValueError('Foreign revision')
        expected = tuple(e.id for e in revision.elements if e.kind == 'dialogue' and e.id in self.selected_ids)
        if self.selected_ids != expected or not set(self.context_ids) <= {e.id for e in revision.elements}:
            raise ValueError('Invalid or unordered selection IDs')
        if set(self.context_ids) & set(self.selected_ids):
            raise ValueError('Context must be separate from speech')


def require_scope(a, b):
    if a.owner_id != b.owner_id or a.project_id != b.project_id:
        raise ValueError('Foreign project or owner')


class CharacterProfile(Contract):
    character_id: Id
    evidence_ids: tuple[Id, ...]
    voice_brief: str = ''
    uncertain_traits: tuple[str, ...] = ()
    selected_line_count: int = Field(ge=0)


class CastAssignment(Contract):
    character_id: Id
    voice_id: Id
    origin: Literal['selected', 'catalog', 'designed'] = 'selected'
    locked: bool = True
    evidence_ids: tuple[Id, ...] = ()
    audition_status: Literal['pending', 'passed', 'failed'] = 'pending'
    model_id: Literal['eleven_v4'] = 'eleven_v4'


class Cast(Owned):
    project_id: Id
    revision_id: Id
    version: Positive
    assignments: tuple[CastAssignment, ...] = ()

    @model_validator(mode='after')
    def unique(self):
        if len({a.character_id for a in self.assignments}) != len(self.assignments):
            raise ValueError('Duplicate cast assignment')
        return self


Tag = Literal['whispering', 'shouting', 'hesitant', 'restrained', 'laughing', 'pause']


class Annotation(Contract):
    element_id: Id
    offset: int = Field(ge=0)
    tag: Tag
    evidence_ids: tuple[Id, ...] = ()
    origin: Literal['source', 'user', 'inferred'] = 'source'


class Pronunciation(Contract):
    element_id: Id
    start: int = Field(ge=0)
    end: Positive
    replacement: str = Field(min_length=1, max_length=200)


class DirectionPlan(Owned):
    project_id: Id
    selection_id: Id
    selection_version: Positive
    cast_version: Positive
    version: Positive
    annotations: tuple[Annotation, ...] = ()
    pronunciations: tuple[Pronunciation, ...] = ()
    director_model: str = 'source-parentheticals'
    prompt_version: str = 'direction-1'


class ProviderCapabilities(Contract):
    version: str = 'eleven-v4-dialogue-2026-11-02-conservative'
    model_id: Literal['eleven_v4'] = 'eleven_v4'
    endpoint: Literal['/v1/text-to-dialogue/with-timestamps'] = '/v1/text-to-dialogue/with-timestamps'
    max_characters: int = Field(default=2000, ge=32, le=2000)
    max_voices: int = Field(default=10, ge=1, le=10)
    output_format: Literal['mp3_44100_128'] = 'mp3_44100_128'
    timing: bool = True
    ipa: bool = False
    stitching: bool = False
    supported_settings: tuple[str, ...] = ()


class DialogueInput(Contract):
    voice_id: Id
    text: str = Field(min_length=1)


class DialogueRequest(Contract):
    model_id: Literal['eleven_v4'] = 'eleven_v4'
    inputs: tuple[DialogueInput, ...] = Field(min_length=1)

    def provider_body(self):
        return {'model_id': self.model_id, 'inputs': [{'voice_id': i.voice_id, 'text': i.text} for i in self.inputs]}


class Fragment(Contract):
    element_id: Id
    character_id: Id
    start: int = Field(ge=0)
    end: Positive
    input_index: int = Field(ge=0)
    rendered_start: int = Field(ge=0)
    rendered_end: int = Field(ge=0)


class CompiledChunk(Contract):
    id: Id
    scene_id: Id
    request: DialogueRequest
    fragments: tuple[Fragment, ...]


class RenderPlan(Owned):
    project_id: Id
    revision_id: Id
    selection_id: Id
    selection_hash: str
    cast_hash: str
    direction_hash: str
    capabilities: ProviderCapabilities
    chunks: tuple[CompiledChunk, ...] = Field(min_length=1)
    estimated_characters: int = Field(gt=0)
    warnings: tuple[str, ...] = ()


class RenderJob(Owned):
    project_id: Id
    plan_id: Id
    plan_hash: str
    max_characters: Positive
    idempotency_key: Id
    status: Literal['queued', 'running', 'completed', 'partial_failed', 'failed', 'cancelled'] = 'queued'
    cancellation_requested: bool = False


class RenderAttempt(Owned):
    job_id: Id
    chunk_id: Id
    attempt_number: Positive
    payload_hash: str
    provider_request_id: str | None = None
    outcome: Literal['started', 'succeeded', 'failed', 'ambiguous']
    error_class: str | None = None
    usage: int | None = None


class AudioAsset(Owned):
    project_id: Id
    content_hash: str
    stored_path: str
    mime: str
    duration: float = Field(gt=0)
    take_id: Id
    fragments: tuple[Fragment, ...] = ()
    timing: dict = Field(default_factory=dict)
    owui_file_id: str | None = None


class IntentProposal(Contract):
    operation: Literal['inspect', 'select', 'refine'] = 'inspect'
    scope: Literal['none', 'script', 'character', 'scene', 'text', 'filter', 'ids'] = 'none'
    character: str | None = Field(default=None,description='For character scope use one supplied canonical character name or character ID; otherwise null.')
    scene: str | None = Field(default=None,description='For scene scope use one production scene number, heading description or supplied scene ID. Time/location-only requests use scope filter.')
    text: str | None = None
    location: str | None = None
    time_of_day: str | None = None
    ids: tuple[Id, ...] = Field(default=(),description='Dialogue element IDs ONLY, and only for scope ids. Never put character or scene IDs here. For character/scene/filter/text/script/none scopes return an empty array.')
    preceding: int = Field(default=0, ge=0, le=20)


class CastingProposal(Contract):
    assignments: tuple[CastAssignment, ...]


class DirectionProposal(Contract):
    annotations: tuple[Annotation, ...]


class Voice(Contract):
    voice_id: Id
    name: str
    labels: dict[str, str] = Field(default_factory=dict)


class VoicePage(Contract):
    voices: tuple[Voice, ...]
    next_cursor: str | None = None


class VoiceDesignRequest(Contract):
    voice_description: str = Field(min_length=20, max_length=1000)
    text: str = Field(min_length=100, max_length=1000)
    model_id: Literal['eleven_ttv_v3', 'eleven_multilingual_ttv_v2'] = 'eleven_ttv_v3'


class VoicePreview(Contract):
    generated_voice_id: Id
    audio_base64: str
    mime: str = 'audio/mpeg'


class ProviderAudioResult(Contract):
    audio: bytes
    mime: str = 'audio/mpeg'
    request_id: str | None = None
    timing: dict = Field(default_factory=dict)
    usage: int | None = None
