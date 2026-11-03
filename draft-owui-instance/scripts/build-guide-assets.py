"""Validate canonical guide content and generate Guide Bridge JSON assets."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[1]
AGENT_SOURCE = PROJECT_ROOT / "agent" / "src"
DEFAULT_SOURCE = PROJECT_ROOT / "knowledge" / "ui-map.yaml"
DEFAULT_OUTPUT = PROJECT_ROOT / "openwebui" / "guide-extension" / "ui-map.json"
DEFAULT_RECIPE_SOURCE = PROJECT_ROOT / "knowledge" / "recipes"
DEFAULT_RECIPE_OUTPUT = (
    PROJECT_ROOT / "openwebui" / "guide-extension" / "recipes.json"
)

sys.path.insert(0, str(AGENT_SOURCE))

from howto_agent import RecipeRegistry, UiMap  # noqa: E402 - local path is intentional


def build_asset(source: Path, output: Path, *, check: bool = False) -> bool:
    """Generate the JSON asset, or check that the existing asset is current."""

    ui_map = UiMap.from_yaml(source)
    rendered = json.dumps(ui_map.to_dict(), indent=2, ensure_ascii=False) + "\n"

    if check:
        try:
            current = output.read_text(encoding="utf-8")
        except OSError:
            return False
        return current == rendered

    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(rendered, encoding="utf-8", newline="\n")
    return True


def build_recipe_asset(
    source: Path,
    ui_map_source: Path,
    output: Path,
    *,
    check: bool = False,
) -> bool:
    """Generate the independently validated browser recipe registry asset."""

    ui_map = UiMap.from_yaml(ui_map_source)
    registry = RecipeRegistry.from_directory(source, ui_map=ui_map)
    definition = {
        "schema_version": 1,
        "id": "open_webui_poc_recipe_registry",
        "recipes": [recipe.to_dict() for recipe in registry.recipes],
    }
    rendered = json.dumps(definition, indent=2, ensure_ascii=False) + "\n"

    if check:
        try:
            current = output.read_text(encoding="utf-8")
        except OSError:
            return False
        return current == rendered

    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(rendered, encoding="utf-8", newline="\n")
    return True


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--recipe-source", type=Path, default=DEFAULT_RECIPE_SOURCE)
    parser.add_argument("--recipe-output", type=Path, default=DEFAULT_RECIPE_OUTPUT)
    parser.add_argument(
        "--check",
        action="store_true",
        help="exit unsuccessfully when the generated asset is absent or stale",
    )
    args = parser.parse_args()

    ui_map_current = build_asset(args.source, args.output, check=args.check)
    recipes_current = build_recipe_asset(
        args.recipe_source,
        args.source,
        args.recipe_output,
        check=args.check,
    )
    if args.check and (not ui_map_current or not recipes_current):
        if not ui_map_current:
            print(f"Guide UI asset is stale: {args.output}", file=sys.stderr)
        if not recipes_current:
            print(f"Guide recipe asset is stale: {args.recipe_output}", file=sys.stderr)
        return 1
    if not args.check:
        print(f"Generated {args.output} from {args.source}")
        print(f"Generated {args.recipe_output} from {args.recipe_source}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
