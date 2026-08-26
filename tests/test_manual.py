from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from howto_agent import InstructionManual, ManualDefinitionError, RecipeRegistry, UiMap


ROOT = Path(__file__).resolve().parents[1]
MANUAL_PATH = ROOT / "knowledge" / "open-webui-instruction-manual.md"
UI_MAP_PATH = ROOT / "knowledge" / "ui-map.yaml"
RECIPE_DIRECTORY = ROOT / "knowledge" / "recipes"


class InstructionManualTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.manual = InstructionManual.from_markdown(MANUAL_PATH)
        cls.ui_map = UiMap.from_yaml(UI_MAP_PATH)
        cls.recipes = RecipeRegistry.from_directory(
            RECIPE_DIRECTORY,
            ui_map=cls.ui_map,
        )

    def test_loads_metadata_and_addressable_sections(self) -> None:
        self.assertEqual(self.manual.metadata["id"], "open_webui_instruction_manual")

        section = self.manual.get_section("what-is-open-webui")
        self.assertIsNotNone(section)
        assert section is not None
        self.assertIn("browser interface", section.markdown)

    def test_extracts_semantic_references(self) -> None:
        self.assertIn("model-picker", self.manual.ui_references)
        self.assertIn("hello-world-demo", self.manual.recipe_references)

    def test_all_manual_references_resolve(self) -> None:
        self.manual.validate_references(
            allowed_targets=self.ui_map.target_ids,
            allowed_recipes=self.recipes.recipe_ids,
        )

    def test_metadata_is_a_defensive_copy(self) -> None:
        metadata = self.manual.metadata
        metadata["id"] = "changed"

        self.assertEqual(
            self.manual.metadata["id"],
            "open_webui_instruction_manual",
        )

    def test_rejects_unknown_manual_references(self) -> None:
        manual = self._load_temporary_manual(
            """---
id: invalid
title: Invalid
version: 1-draft
status: draft
---

# Invalid

## Section

See [ui:not-registered] and [recipe:not-registered].
"""
        )

        with self.assertRaisesRegex(
            ManualDefinitionError,
            "unknown UI references.*unknown recipe references",
        ):
            manual.validate_references(
                allowed_targets=self.ui_map.target_ids,
                allowed_recipes=self.recipes.recipe_ids,
            )

    def test_rejects_duplicate_section_slugs(self) -> None:
        with self.assertRaisesRegex(
            ManualDefinitionError,
            "duplicate manual section ID",
        ):
            self._load_temporary_manual(
                """---
id: invalid
title: Invalid
version: 1-draft
status: draft
---

# Invalid

## Same heading

First.

## Same heading!

Second.
"""
            )

    @staticmethod
    def _load_temporary_manual(contents: str) -> InstructionManual:
        with TemporaryDirectory() as directory:
            path = Path(directory) / "manual.md"
            path.write_text(contents, encoding="utf-8")
            return InstructionManual.from_markdown(path)


if __name__ == "__main__":
    unittest.main()

