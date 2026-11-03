from __future__ import annotations

import unittest

from howto_agent import (
    AgentReply,
    ChatChoice,
    GuideContext,
    GuideTrigger,
    GuideTriggerError,
    UiDirective,
    normalize_trigger,
    validate_directive,
)


class GuideTriggerTests(unittest.TestCase):
    def test_normalizes_visible_starter_message(self) -> None:
        trigger = normalize_trigger("  Start the getting started tour!  ")

        self.assertEqual(
            trigger,
            GuideTrigger(intent="getting_started", source="model"),
        )

    def test_normalizes_structured_cta_trigger(self) -> None:
        trigger = normalize_trigger(
            {
                "version": 1,
                "intent": "getting_started",
                "source": "cta",
                "parameters": {"entry": "navigation"},
            }
        )

        self.assertIsNotNone(trigger)
        assert trigger is not None
        self.assertEqual(trigger.source, "cta")
        self.assertEqual(trigger.parameters["entry"], "navigation")

    def test_unrelated_text_is_not_a_trigger(self) -> None:
        self.assertIsNone(normalize_trigger("What is a model?"))

    def test_trigger_parameters_are_copied_and_read_only(self) -> None:
        parameters = {"entry": "navigation"}
        trigger = GuideTrigger(
            intent="getting_started",
            source="cta",
            parameters=parameters,
        )
        parameters["entry"] = "changed"

        self.assertEqual(trigger.parameters["entry"], "navigation")
        with self.assertRaises(TypeError):
            trigger.parameters["entry"] = "changed"  # type: ignore[index]

    def test_rejects_unsupported_trigger_fields(self) -> None:
        invalid_values = (
            {"intent": "unknown", "source": "cta", "version": 1},
            {"intent": "getting_started", "source": "unknown", "version": 1},
            {"intent": "getting_started", "source": "cta", "version": 2},
        )

        for value in invalid_values:
            with self.subTest(value=value):
                with self.assertRaises(GuideTriggerError):
                    normalize_trigger(value)


class GuideContractTests(unittest.TestCase):
    def test_context_accepts_user_visible_choices(self) -> None:
        context = GuideContext(
            visible_chat_choices=(
                ChatChoice(id="hello-world", name="Hello World", kind="model"),
                ChatChoice(
                    id="open-webui-guide",
                    name="Open WebUI Guide",
                    kind="agent",
                ),
            )
        )

        self.assertEqual(len(context.visible_chat_choices), 2)

    def test_unavailable_catalog_may_include_an_error(self) -> None:
        context = GuideContext(
            catalog_available=False,
            catalog_error="model catalog unavailable",
        )

        self.assertFalse(context.catalog_available)

    def test_run_recipe_directive_requires_confirmation(self) -> None:
        with self.assertRaisesRegex(ValueError, "require confirmation"):
            UiDirective(kind="run_recipe", recipe="hello-world-demo")

    def test_reply_normalizes_directives_to_a_tuple(self) -> None:
        directive = UiDirective(kind="highlight", target="model-picker")
        reply = AgentReply(markdown="Choose a model.", directives=[directive])

        self.assertEqual(reply.directives, (directive,))

    def test_registry_validation_rejects_unknown_references(self) -> None:
        directive = UiDirective(kind="highlight", target="not-registered")

        with self.assertRaisesRegex(ValueError, "unknown UI target"):
            validate_directive(
                directive,
                allowed_targets={"model-picker"},
                allowed_recipes={"hello-world-demo"},
            )


if __name__ == "__main__":
    unittest.main()

