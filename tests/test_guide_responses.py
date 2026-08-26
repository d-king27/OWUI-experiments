from __future__ import annotations

from pathlib import Path
import unittest

from howto_agent import (
    AgentConfigurationError,
    ChatChoice,
    GuideContext,
    GuideIntent,
    HowToAgent,
    UiMap,
    route_guide_input,
)


ROOT = Path(__file__).resolve().parents[1]
PROCESS_PATH = ROOT / "agent" / "process_definition.example.yaml"
MANUAL_PATH = ROOT / "knowledge" / "open-webui-instruction-manual.md"
UI_MAP_PATH = ROOT / "knowledge" / "ui-map.yaml"
RECIPE_DIRECTORY = ROOT / "knowledge" / "recipes"


class GuideRouterTests(unittest.TestCase):
    def test_routes_minimum_supported_questions(self) -> None:
        cases = {
            "What is Open WebUI?": GuideIntent.WHAT_IS_OPEN_WEBUI,
            "How do I use it?": GuideIntent.HOW_TO_USE,
            "What is a model?": GuideIntent.WHAT_IS_A_MODEL,
            "What agents do I have access to?": GuideIntent.LIST_CHAT_CHOICES,
            "Give me a workable example": GuideIntent.WORKABLE_EXAMPLE,
        }

        for message, expected in cases.items():
            with self.subTest(message=message):
                self.assertEqual(route_guide_input(message).intent, expected)

    def test_routes_structured_getting_started_trigger(self) -> None:
        match = route_guide_input(
            {
                "version": 1,
                "intent": "getting_started",
                "source": "cta",
                "parameters": {},
            }
        )

        self.assertEqual(match.intent, GuideIntent.GETTING_STARTED)

    def test_routes_documented_highlight_phrases(self) -> None:
        cases = {
            "Show me where I select a model": "model-picker",
            "Highlight the message box": "message-composer",
            "Where do I type?": "message-composer",
            "Where will the answer appear?": "assistant-message",
            "Show me the send button": "send-button",
        }

        for message, expected_target in cases.items():
            with self.subTest(message=message):
                match = route_guide_input(message)
                self.assertEqual(match.intent, GuideIntent.HIGHLIGHT_TARGET)
                self.assertEqual(match.target, expected_target)


class GroundedGuideResponseTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.agent = HowToAgent.from_content_files(
            process_path=PROCESS_PATH,
            manual_path=MANUAL_PATH,
            ui_map_path=UI_MAP_PATH,
            recipe_directory=RECIPE_DIRECTORY,
        )

    def test_answers_what_open_webui_is_from_the_manual(self) -> None:
        reply = self.agent.respond("What is Open WebUI?")

        self.assertIn("browser interface", reply.markdown)
        self.assertIn("not itself the model", reply.markdown)
        self.assertEqual(reply.directives, ())

    def test_answers_how_to_use_it_and_offers_the_model_picker(self) -> None:
        reply = self.agent.respond("How do I use it?")

        self.assertIn("basic chat workflow", reply.markdown)
        self.assertEqual(reply.directives[0].kind, "highlight")
        self.assertEqual(reply.directives[0].target, "model-picker")

    def test_explains_models_and_agents(self) -> None:
        reply = self.agent.respond("What is a model?")

        self.assertIn("underlying system", reply.markdown)
        self.assertIn("An agent is a configured experience", reply.markdown)

    def test_lists_only_runtime_chat_choices(self) -> None:
        context = GuideContext(
            visible_chat_choices=(
                ChatChoice(
                    id="research-guide",
                    name="Research Guide",
                    kind="agent",
                ),
                ChatChoice(id="model-a", name="Model A", kind="model"),
            )
        )

        reply = self.agent.respond(
            "What agents do I have access to?",
            context=context,
        )

        self.assertIn("Research Guide", reply.markdown)
        self.assertIn("Model A", reply.markdown)
        self.assertNotIn("hello-world", reply.markdown)
        self.assertEqual(reply.directives[0].target, "model-picker")

    def test_does_not_expose_catalog_error_details(self) -> None:
        reply = self.agent.respond(
            "Which models are available?",
            context=GuideContext(
                catalog_available=False,
                catalog_error="secret internal connection detail",
            ),
        )

        self.assertIn("can't verify", reply.markdown)
        self.assertNotIn("secret internal", reply.markdown)

    def test_escapes_runtime_choice_metadata_in_markdown(self) -> None:
        reply = self.agent.respond(
            "Which agents are available?",
            context=GuideContext(
                visible_chat_choices=(
                    ChatChoice(
                        id="unsafe`id",
                        name="Unsafe *name*",
                        kind="unknown",
                    ),
                )
            ),
        )

        self.assertIn(r"Unsafe \*name\*", reply.markdown)
        self.assertIn("unsafe&#96;id", reply.markdown)

    def test_offers_the_registered_workable_example(self) -> None:
        reply = self.agent.respond("Give me a workable example")

        self.assertIn("smallest working chat flow", reply.markdown)
        self.assertEqual(reply.directives[0].kind, "run_recipe")
        self.assertEqual(reply.directives[0].recipe, "hello-world-demo")
        self.assertTrue(reply.directives[0].requires_confirmation)

    def test_starts_the_tour_at_the_first_grounded_step(self) -> None:
        reply = self.agent.respond("Start the getting started tour")

        self.assertIn("Step 1", reply.markdown)
        self.assertIn("browser interface", reply.markdown)
        self.assertIn("underlying system", reply.markdown)
        self.assertEqual(reply.directives[0].target, "model-picker")

    def test_highlight_response_uses_ui_map_description(self) -> None:
        reply = self.agent.respond("Where do I type?")
        target = UiMap.from_yaml(UI_MAP_PATH).get_target("message-composer")
        assert target is not None

        self.assertIn(target["description"], reply.markdown)
        self.assertEqual(reply.directives[0].target, "message-composer")

    def test_unknown_question_fails_groundedly(self) -> None:
        reply = self.agent.respond("How do I configure an enterprise SSO provider?")

        self.assertIn("does not contain enough information", reply.markdown)
        self.assertEqual(reply.directives, ())

    def test_process_only_agent_rejects_guide_responses(self) -> None:
        process_only_agent = HowToAgent.from_yaml(PROCESS_PATH)

        with self.assertRaisesRegex(
            AgentConfigurationError,
            "guide responses require",
        ):
            process_only_agent.respond("What is Open WebUI?")


if __name__ == "__main__":
    unittest.main()

