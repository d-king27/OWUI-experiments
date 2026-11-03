"""Version-isolated access to the current user's Open WebUI model catalog."""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass
from typing import Any

from howto_agent import ChatChoice, ChatChoiceKind


GetAllModels = Callable[..., Awaitable[list[dict[str, Any]]]]
GetFilteredModels = Callable[..., Awaitable[list[dict[str, Any]]]]


class CatalogUnavailable(RuntimeError):
    """Raised when the adapter cannot obtain a trustworthy user catalog."""


@dataclass(frozen=True, slots=True)
class CatalogBindings:
    """Open WebUI internals isolated for version upgrades and unit tests."""

    users: Any
    get_all_models: GetAllModels
    get_filtered_models: GetFilteredModels


def load_openwebui_bindings() -> CatalogBindings:
    """Import the model APIs verified against Open WebUI v0.11.0."""

    try:
        from open_webui.models.users import Users
        from open_webui.utils.models import get_all_models, get_filtered_models
    except ImportError as error:
        raise CatalogUnavailable(
            "Open WebUI v0.11.0 catalog bindings are unavailable"
        ) from error

    return CatalogBindings(
        users=Users,
        get_all_models=get_all_models,
        get_filtered_models=get_filtered_models,
    )


async def visible_chat_choices(
    request: Any,
    user_payload: Mapping[str, Any],
    *,
    bindings: CatalogBindings | None = None,
) -> tuple[ChatChoice, ...]:
    """Return the same effective, access-filtered choices visible to one user."""

    if request is None:
        raise CatalogUnavailable("Open WebUI request context is unavailable")
    if not isinstance(user_payload, Mapping):
        raise CatalogUnavailable("Open WebUI user context is unavailable")

    user_id = user_payload.get("id")
    if not isinstance(user_id, str) or not user_id.strip():
        raise CatalogUnavailable("Open WebUI user ID is unavailable")

    adapter = bindings or load_openwebui_bindings()
    try:
        user = await adapter.users.get_user_by_id(user_id)
        if user is None:
            raise CatalogUnavailable("Open WebUI user could not be resolved")

        all_models = await adapter.get_all_models(request, user=user)
        effective_models = _effective_models(all_models)
        filtered_models = await adapter.get_filtered_models(effective_models, user)
    except CatalogUnavailable:
        raise
    except Exception as error:
        raise CatalogUnavailable(
            "Open WebUI model catalog could not be loaded"
        ) from error

    if not isinstance(filtered_models, list):
        raise CatalogUnavailable("Open WebUI returned an invalid filtered catalog")

    choices = []
    for model in filtered_models:
        choice = _to_chat_choice(model)
        if choice is not None:
            choices.append(choice)
    return tuple(choices)


def _effective_models(models: Any) -> list[dict[str, Any]]:
    """Mirror the effective-model normalization performed by ``GET /api/models``."""

    if not isinstance(models, list):
        raise CatalogUnavailable("Open WebUI returned an invalid model catalog")

    effective: dict[str, dict[str, Any]] = {}
    for raw_model in models:
        if not isinstance(raw_model, Mapping):
            continue

        pipeline = raw_model.get("pipeline")
        if isinstance(pipeline, Mapping) and pipeline.get("type") == "filter":
            continue

        model_id = raw_model.get("id")
        if not isinstance(model_id, str) or not model_id.strip():
            continue
        effective[model_id] = dict(raw_model)

    return list(effective.values())


def _to_chat_choice(model: Any) -> ChatChoice | None:
    if not isinstance(model, Mapping):
        return None

    model_id = model.get("id")
    if not isinstance(model_id, str) or not model_id.strip():
        return None

    raw_name = model.get("name", model_id)
    name = raw_name if isinstance(raw_name, str) and raw_name.strip() else model_id
    return ChatChoice(
        id=model_id,
        name=name,
        kind=_classify_chat_choice(model),
    )


def _classify_chat_choice(model: Mapping[str, Any]) -> ChatChoiceKind:
    if model.get("pipe") is not None:
        return "agent"

    info = model.get("info")
    if model.get("preset") is True or (
        isinstance(info, Mapping) and info.get("base_model_id") is not None
    ):
        return "custom_model"

    if model.get("object") == "model":
        return "model"
    return "unknown"
