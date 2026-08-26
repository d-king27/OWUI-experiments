from __future__ import annotations

import json
from pathlib import Path
import shutil
import subprocess
import unittest


ROOT = Path(__file__).resolve().parents[1]
EXTENSION = ROOT / "openwebui" / "guide-extension"


class GuideExtensionManifestTests(unittest.TestCase):
    def test_manifest_is_local_origin_only_and_has_no_permissions(self) -> None:
        manifest = json.loads((EXTENSION / "manifest.json").read_text(encoding="utf-8"))

        self.assertEqual(manifest["manifest_version"], 3)
        self.assertNotIn("permissions", manifest)
        content_script = manifest["content_scripts"][0]
        self.assertEqual(
            set(content_script["matches"]),
            {
                "http://localhost:3000/*",
                "http://127.0.0.1:3000/*",
            },
        )
        self.assertEqual(content_script["js"], ["bridge.js", "content.js"])
        self.assertEqual(content_script["css"], ["guide.css"])

    def test_every_declared_extension_asset_exists(self) -> None:
        manifest = json.loads((EXTENSION / "manifest.json").read_text(encoding="utf-8"))
        assets = [
            *manifest["content_scripts"][0]["js"],
            *manifest["content_scripts"][0]["css"],
            *manifest["web_accessible_resources"][0]["resources"],
        ]

        self.assertTrue(assets)
        for asset in assets:
            with self.subTest(asset=asset):
                self.assertTrue((EXTENSION / asset).is_file())


@unittest.skipUnless(shutil.which("node"), "Node.js is required")
class GuideExtensionDomTests(unittest.TestCase):
    def test_dom_contract(self) -> None:
        result = subprocess.run(
            [
                "node",
                "--test",
                str(ROOT / "tests" / "browser" / "guide-bridge.test.mjs"),
            ],
            cwd=ROOT,
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main()
