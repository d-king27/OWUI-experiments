from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

import yaml

from howto_agent import ContentDefinitionError, RecipeRegistry, UiMap


ROOT = Path(__file__).resolve().parents[1]
UI_MAP_PATH = ROOT / "knowledge" / "ui-map.yaml"
RECIPE_DIRECTORY = ROOT / "knowledge" / "recipes"
BUILD_SCRIPT_PATH = ROOT / "scripts" / "build-guide-assets.py"
RECIPE_ASSET_PATH = ROOT / "openwebui" / "guide-extension" / "recipes.json"


class UiMapAndRecipeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.ui_map = UiMap.from_yaml(UI_MAP_PATH)
        cls.registry = RecipeRegistry.from_directory(
            RECIPE_DIRECTORY,
            ui_map=cls.ui_map,
        )

    def test_loads_semantic_ui_targets(self) -> None:
        self.assertIn("model-picker", self.ui_map.target_ids)
        self.assertIn("getting-started-cta", self.ui_map.target_ids)
        self.assertEqual(
            self.ui_map.to_dict()["verification"]["state"],
            "interactive_targets_verified",
        )

    def test_loads_allow_listed_recipes(self) -> None:
        self.assertEqual(
            self.registry.recipe_ids,
            {"hello-world-demo", "launch-getting-started"},
        )

        hello_world = self.registry.get("hello-world-demo")
        self.assertIsNotNone(hello_world)
        assert hello_world is not None
        self.assertTrue(hello_world.requires_confirmation)
        self.assertEqual(hello_world.steps[0].action, "click")
        self.assertEqual(hello_world.steps[-1].id, "restore_guide")

    def test_recipe_definitions_are_defensive_copies(self) -> None:
        recipe = self.registry.get("hello-world-demo")
        assert recipe is not None
        definition = recipe.to_dict()
        definition["steps"][0]["target"] = "changed"

        self.assertEqual(recipe.steps[0].target, "model-picker")
        self.assertEqual(recipe.to_dict()["steps"][0]["target"], "model-picker")

    def test_rejects_unknown_recipe_actions(self) -> None:
        invalid = self._recipe_definition("hello-world-demo")
        invalid["steps"][0]["action"] = "execute_javascript"

        with self.assertRaisesRegex(ContentDefinitionError, "unsupported action"):
            self._load_only_recipe(invalid)

    def test_rejects_unknown_recipe_targets(self) -> None:
        invalid = self._recipe_definition("hello-world-demo")
        invalid["steps"][0]["target"] = "admin-password"

        with self.assertRaisesRegex(ContentDefinitionError, "unknown target"):
            self._load_only_recipe(invalid)

    def test_mutating_recipe_requires_confirmation(self) -> None:
        invalid = self._recipe_definition("hello-world-demo")
        invalid["requires_confirmation"] = False

        with self.assertRaisesRegex(ContentDefinitionError, "requires confirmation"):
            self._load_only_recipe(invalid)

    def test_build_script_generates_current_json_asset(self) -> None:
        specification = importlib.util.spec_from_file_location(
            "build_guide_assets",
            BUILD_SCRIPT_PATH,
        )
        assert specification is not None and specification.loader is not None
        module = importlib.util.module_from_spec(specification)
        specification.loader.exec_module(module)

        with TemporaryDirectory() as directory:
            output = Path(directory) / "ui-map.json"
            self.assertTrue(module.build_asset(UI_MAP_PATH, output))
            self.assertEqual(
                json.loads(output.read_text(encoding="utf-8")),
                self.ui_map.to_dict(),
            )
            self.assertTrue(module.build_asset(UI_MAP_PATH, output, check=True))

    def test_build_script_generates_current_recipe_asset(self) -> None:
        specification = importlib.util.spec_from_file_location(
            "build_guide_assets_recipes",
            BUILD_SCRIPT_PATH,
        )
        assert specification is not None and specification.loader is not None
        module = importlib.util.module_from_spec(specification)
        specification.loader.exec_module(module)

        with TemporaryDirectory() as directory:
            output = Path(directory) / "recipes.json"
            self.assertTrue(
                module.build_recipe_asset(
                    RECIPE_DIRECTORY,
                    UI_MAP_PATH,
                    output,
                )
            )
            expected = {
                "schema_version": 1,
                "id": "open_webui_poc_recipe_registry",
                "recipes": [recipe.to_dict() for recipe in self.registry.recipes],
            }
            self.assertEqual(
                json.loads(output.read_text(encoding="utf-8")),
                expected,
            )
            self.assertTrue(
                module.build_recipe_asset(
                    RECIPE_DIRECTORY,
                    UI_MAP_PATH,
                    output,
                    check=True,
                )
            )
            self.assertEqual(
                json.loads(RECIPE_ASSET_PATH.read_text(encoding="utf-8")),
                expected,
            )

    def _recipe_definition(self, recipe_id: str) -> dict:
        recipe = self.registry.get(recipe_id)
        assert recipe is not None
        return recipe.to_dict()

    def _load_only_recipe(self, definition: dict) -> RecipeRegistry:
        with TemporaryDirectory() as directory:
            path = Path(directory) / "invalid.yaml"
            path.write_text(yaml.safe_dump(definition), encoding="utf-8")
            return RecipeRegistry.from_directory(directory, ui_map=self.ui_map)


if __name__ == "__main__":
    unittest.main()
