from __future__ import annotations

import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from howto_agent import AgentReply, ChatChoice, HowToAgent, UiDirective
from openwebui.functions.howto_pipe import (
    Pipe,
    extract_user_prompt,
    render_reply_with_directives,
)


ROOT = Path(__file__).resolve().parents[1]


def build_agent() -> HowToAgent:
    return HowToAgent.from_content_files(
        process_path=ROOT / "agent" / "process_definition.example.yaml",
        manual_path=ROOT / "knowledge" / "open-webui-instruction-manual.md",
        ui_map_path=ROOT / "knowledge" / "ui-map.yaml",
        recipe_directory=ROOT / "knowledge" / "recipes",
    )


class HowToPipeTests(unittest.IsolatedAsyncioTestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.agent = build_agent()

    async def test_pipe_is_selectable_by_name_and_answers_without_an_llm(self) -> None:
        catalog_calls = 0

        async def catalog_loader(request, user):
            nonlocal catalog_calls
            catalog_calls += 1
            return ()

        pipe = Pipe(agent=self.agent, catalog_loader=catalog_loader)
        response = await pipe.pipe(
            {
                "model": "open-webui-guide",
                "messages": [{"role": "user", "content": "What is a model?"}],
                "stream": True,
            },
            __user__={"id": "user-1"},
            __request__=object(),
        )

        self.assertEqual(pipe.name, "Open WebUI Guide")
        self.assertIn("underlying system", response)
        self.assertEqual(catalog_calls, 0)
        self.assertNotIn("tool_calls", response)

    async def test_prefers_unwrapped_metadata_prompt(self) -> None:
        pipe = Pipe(agent=self.agent)
        response = await pipe.pipe(
            {
                "messages": [
                    {
                        "role": "user",
                        "content": "Wrapped source material that is not the prompt",
                    }
                ]
            },
            __metadata__={"user_prompt": "What is Open WebUI?"},
        )

        self.assertIn("browser interface", response)
        self.assertNotIn("does not contain enough", response)

    async def test_loads_runtime_catalog_only_for_availability_question(self) -> None:
        request = object()
        seen: dict[str, object] = {}

        async def catalog_loader(received_request, received_user):
            seen["request"] = received_request
            seen["user"] = received_user
            return (
                ChatChoice(
                    id="research-guide",
                    name="Research Guide",
                    kind="agent",
                ),
            )

        pipe = Pipe(agent=self.agent, catalog_loader=catalog_loader)
        response = await pipe.pipe(
            {
                "messages": [
                    {"role": "user", "content": "Which agents are available?"}
                ]
            },
            __user__={"id": "user-1", "role": "user"},
            __request__=request,
        )

        self.assertIs(seen["request"], request)
        self.assertEqual(seen["user"], {"id": "user-1", "role": "user"})
        self.assertIn("Research Guide", response)
        self.assertIn('"target":"model-picker"', response)

    async def test_catalog_failure_returns_grounded_runtime_fallback(self) -> None:
        async def catalog_loader(request, user):
            raise RuntimeError("secret internal detail")

        pipe = Pipe(agent=self.agent, catalog_loader=catalog_loader)
        response = await pipe.pipe(
            {
                "messages": [
                    {"role": "user", "content": "Which models are available?"}
                ]
            },
            __user__={"id": "user-1"},
            __request__=object(),
        )

        self.assertIn("can't verify", response)
        self.assertNotIn("secret internal", response)

    async def test_invalid_catalog_values_fail_closed(self) -> None:
        async def catalog_loader(request, user):
            return ("not a ChatChoice",)

        pipe = Pipe(agent=self.agent, catalog_loader=catalog_loader)
        response = await pipe.pipe(
            {
                "messages": [
                    {"role": "user", "content": "Which models are available?"}
                ]
            },
            __user__={"id": "user-1"},
            __request__=object(),
        )

        self.assertIn("can't verify", response)

    async def test_missing_content_keeps_function_loadable(self) -> None:
        with TemporaryDirectory() as directory:
            pipe = Pipe(content_root=directory)
            response = await pipe.pipe(
                {"messages": [{"role": "user", "content": "What is a model?"}]}
            )

        self.assertIn("not configured correctly", response)

    async def test_missing_user_message_returns_supported_topics(self) -> None:
        response = await Pipe(agent=self.agent).pipe({"messages": []})

        self.assertIn("couldn't find a user message", response)
        self.assertIn("workable example", response)

    async def test_unsafe_transport_identifier_fails_closed(self) -> None:
        class UnsafeAgent:
            def respond(self, prompt, *, context):
                return AgentReply(
                    markdown="Unsafe directive.",
                    directives=(
                        UiDirective(kind="highlight", target="bad```target"),
                    ),
                )

        response = await Pipe(agent=UnsafeAgent()).pipe(  # type: ignore[arg-type]
            {"messages": [{"role": "user", "content": "What is a model?"}]}
        )

        self.assertIn("not configured correctly", response)
        self.assertNotIn("bad```target", response)

    def test_extracts_last_user_text_from_multimodal_content(self) -> None:
        prompt = extract_user_prompt(
            {
                "messages": [
                    {"role": "user", "content": "Older question"},
                    {"role": "assistant", "content": "Older answer"},
                    {
                        "role": "user",
                        "content": [
                            {"type": "image_url", "image_url": {"url": "x"}},
                            {"type": "text", "text": "What is a model?"},
                        ],
                    },
                ]
            }
        )

        self.assertEqual(prompt, "What is a model?")

    def test_serializes_highlight_directive_deterministically(self) -> None:
        rendered = render_reply_with_directives(
            AgentReply(
                markdown="Choose a model.",
                directives=(
                    UiDirective(kind="highlight", target="model-picker"),
                ),
            )
        )
        payload_text = rendered.split("```owui-action\n", 1)[1].split("\n```", 1)[0]

        self.assertEqual(
            json.loads(payload_text),
            {
                "kind": "highlight",
                "requires_confirmation": False,
                "target": "model-picker",
                "version": 1,
            },
        )

    def test_serializes_confirmation_gated_recipe(self) -> None:
        rendered = render_reply_with_directives(
            AgentReply(
                markdown="Try the example.",
                directives=(
                    UiDirective(
                        kind="run_recipe",
                        recipe="hello-world-demo",
                        requires_confirmation=True,
                    ),
                ),
            )
        )

        self.assertIn('"recipe":"hello-world-demo"', rendered)
        self.assertIn('"requires_confirmation":true', rendered)


if __name__ == "__main__":
    unittest.main()
