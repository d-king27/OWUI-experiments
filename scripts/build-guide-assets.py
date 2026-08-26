"""Validate the canonical UI map and generate the Guide Bridge JSON asset."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[1]
AGENT_SOURCE = PROJECT_ROOT / "agent" / "src"
DEFAULT_SOURCE = PROJECT_ROOT / "knowledge" / "ui-map.yaml"
DEFAULT_OUTPUT = PROJECT_ROOT / "openwebui" / "guide-extension" / "ui-map.json"

sys.path.insert(0, str(AGENT_SOURCE))

from howto_agent import UiMap  # noqa: E402 - local source path is intentional


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


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument(
        "--check",
        action="store_true",
        help="exit unsuccessfully when the generated asset is absent or stale",
    )
    args = parser.parse_args()

    current = build_asset(args.source, args.output, check=args.check)
    if args.check and not current:
        print(f"Guide UI asset is stale: {args.output}", file=sys.stderr)
        return 1
    if not args.check:
        print(f"Generated {args.output} from {args.source}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

