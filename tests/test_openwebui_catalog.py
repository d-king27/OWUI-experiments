from __future__ import annotations

from types import SimpleNamespace
import unittest

from openwebui.functions.catalog import (
    CatalogBindings,
    CatalogUnavailable,
    visible_chat_choices,
)


class FakeUsers:
    def __init__(self, user) -> None:
        self.user = user
        self.requested_ids: list[str] = []

    async def get_user_by_id(self, user_id: str):
        self.requested_ids.append(user_id)
        return self.user


class OpenWebUICatalogTests(unittest.IsolatedAsyncioTestCase):
    async def test_returns_effective_user_filtered_chat_choices(self) -> None:
        user = SimpleNamespace(id="user-1", role="user")
        users = FakeUsers(user)
        captured: dict[str, object] = {}

        async def get_all_models(request, *, user):
            captured["request"] = request
            captured["all_user"] = user
            return [
                {
                    "id": "duplicate",
                    "name": "Old name",
                    "object": "model",
                },
                {
                    "id": "legacy-filter",
                    "name": "Filter",
                    "pipeline": {"type": "filter"},
                },
                {
                    "id": "duplicate",
                    "name": "Current name",
                    "object": "model",
                },
                {
                    "id": "guide",
                    "name": "Open WebUI Guide",
                    "pipe": {"type": "pipe"},
                },
                {
                    "id": "custom",
                    "name": "Custom choice",
                    "preset": True,
                },
                {"id": "unclassified", "name": "Unclassified"},
                {"name": "Missing ID"},
            ]

        async def get_filtered_models(models, filtered_user):
            captured["effective_models"] = models
            captured["filtered_user"] = filtered_user
            return models

        request = object()
        choices = await visible_chat_choices(
            request,
            {"id": "user-1"},
            bindings=CatalogBindings(
                users=users,
                get_all_models=get_all_models,
                get_filtered_models=get_filtered_models,
            ),
        )

        self.assertEqual(users.requested_ids, ["user-1"])
        self.assertIs(captured["request"], request)
        self.assertIs(captured["all_user"], user)
        self.assertIs(captured["filtered_user"], user)
        self.assertEqual(
            [model["id"] for model in captured["effective_models"]],
            ["duplicate", "guide", "custom", "unclassified"],
        )
        self.assertEqual(
            [(choice.id, choice.name, choice.kind) for choice in choices],
            [
                ("duplicate", "Current name", "model"),
                ("guide", "Open WebUI Guide", "agent"),
                ("custom", "Custom choice", "custom_model"),
                ("unclassified", "Unclassified", "unknown"),
            ],
        )

    async def test_returns_only_models_retained_by_access_filter(self) -> None:
        user = SimpleNamespace(id="user-1", role="user")

        async def get_all_models(request, *, user):
            return [
                {"id": "allowed", "name": "Allowed", "object": "model"},
                {"id": "denied", "name": "Denied", "object": "model"},
            ]

        async def get_filtered_models(models, filtered_user):
            return [model for model in models if model["id"] == "allowed"]

        choices = await visible_chat_choices(
            object(),
            {"id": "user-1"},
            bindings=CatalogBindings(
                users=FakeUsers(user),
                get_all_models=get_all_models,
                get_filtered_models=get_filtered_models,
            ),
        )

        self.assertEqual([choice.id for choice in choices], ["allowed"])

    async def test_rejects_missing_user_context(self) -> None:
        with self.assertRaisesRegex(CatalogUnavailable, "user ID"):
            await visible_chat_choices(
                object(),
                {},
                bindings=CatalogBindings(
                    users=FakeUsers(None),
                    get_all_models=self._unused,
                    get_filtered_models=self._unused,
                ),
            )

    async def test_wraps_internal_catalog_errors_without_leaking_details(self) -> None:
        async def get_all_models(request, *, user):
            raise RuntimeError("secret database detail")

        with self.assertRaises(CatalogUnavailable) as caught:
            await visible_chat_choices(
                object(),
                {"id": "user-1"},
                bindings=CatalogBindings(
                    users=FakeUsers(SimpleNamespace(id="user-1", role="user")),
                    get_all_models=get_all_models,
                    get_filtered_models=self._unused,
                ),
            )

        self.assertNotIn("secret database", str(caught.exception))

    @staticmethod
    async def _unused(*args, **kwargs):
        raise AssertionError("binding should not be called")


if __name__ == "__main__":
    unittest.main()

