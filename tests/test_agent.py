from __future__ import annotations

import unittest
from pathlib import Path

from howto_agent import HowToAgent, ProcessDefinitionError


PROCESS_PATH = (
    Path(__file__).resolve().parents[1]
    / "agent"
    / "process_definition.example.yaml"
)


class HowToAgentTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.agent = HowToAgent.from_yaml(PROCESS_PATH)

    def test_loads_process_and_returns_overview(self) -> None:
        overview = self.agent.get_process_overview()

        self.assertEqual(overview["id"], "explain_hello_world_baseline")
        self.assertEqual(overview["step_count"], 4)
        self.assertEqual(overview["steps"][0]["id"], "understand_the_goal")

    def test_gets_known_step(self) -> None:
        step = self.agent.get_step("trace_the_request")

        self.assertIsNotNone(step)
        self.assertEqual(step["title"], "Trace the request path")

    def test_gets_next_step(self) -> None:
        step = self.agent.get_next_step("trace_the_request")

        self.assertIsNotNone(step)
        self.assertEqual(step["id"], "run_the_chat_test")

    def test_unknown_step_returns_none(self) -> None:
        self.assertIsNone(self.agent.get_step("not_a_step"))
        self.assertIsNone(self.agent.get_next_step("not_a_step"))

    def test_final_step_has_no_next_step(self) -> None:
        self.assertIsNone(self.agent.get_next_step("verify_the_result"))

    def test_returned_steps_do_not_mutate_the_process(self) -> None:
        step = self.agent.get_step("understand_the_goal")
        assert step is not None
        step["title"] = "Changed externally"

        unchanged_step = self.agent.get_step("understand_the_goal")
        self.assertIsNotNone(unchanged_step)
        self.assertEqual(
            unchanged_step["title"], "Understand what the baseline demonstrates"
        )

    def test_duplicate_step_ids_are_rejected(self) -> None:
        process = {
            "id": "duplicate_test",
            "name": "Duplicate test",
            "description": "Invalid example.",
            "steps": [
                {"id": "same", "title": "One", "description": "First."},
                {"id": "same", "title": "Two", "description": "Second."},
            ],
        }

        with self.assertRaisesRegex(ProcessDefinitionError, "duplicate step id"):
            HowToAgent(process)


if __name__ == "__main__":
    unittest.main()
