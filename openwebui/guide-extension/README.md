# Open WebUI Guide Bridge

This directory is an unpacked Manifest V3 browser extension for the local proof of concept. It adds one persistent **Getting started** button to a semantic Open WebUI navigation target and presents an accessible confirmation before requesting any automation.

## Install for local development

1. Start the pinned Open WebUI Compose service at `http://localhost:3000` or `http://127.0.0.1:3000`.
2. Open `chrome://extensions` in Chrome or `edge://extensions` in Edge.
3. Enable **Developer mode**.
4. Choose **Load unpacked** and select this `openwebui/guide-extension` directory.
5. Reload Open WebUI after changing extension files.

The manifest requests no browser permissions and runs only on the two loopback origins above. To reset it, remove the unpacked extension from the browser's extension page; no Open WebUI data is changed.

## CTA and recipe-runner behaviour

- `bridge.js` validates the generated UI map, enforces its origin allow-list, and resolves the `navigation-actions` target without accepting selectors from chat output.
- A `MutationObserver` restores the CTA after client-side navigation while preventing duplicates.
- The confirmation uses a native `dialog`, moves initial focus to **Cancel**, supports Escape through the dialog's cancel event, and restores CTA focus after cancellation.
- Confirming makes one allow-listed, versioned request for `launch-getting-started` through the extension-isolated `registerRecipeRunner` API.
- Only one runner can register, and the bridge accepts only an exact version 1 CTA request for that recipe. Without a valid runner, the dialog stays open and explains that the guide is unavailable. No navigation, click, typing, or submission is attempted.
- Privacy-conscious lifecycle signals are local `howto-guide:telemetry` events containing only an event name and schema version.

`recipe-runner.js` independently validates `ui-map.json` and `recipes.json`, including the pinned Open WebUI version, local origins, exact recipe IDs, action order, fixed text and options, time bounds, target capabilities, and interactive-locator verification state. It implements all allow-listed actions, preflights every recipe, displays progress, and stops without further UI actions when Escape is pressed.

The CTA runs `launch-getting-started` after confirmation when **Open WebUI Guide** is installed and visible in the model picker. `directive-renderer.js` watches only assistant-message `owui-action` blocks, retries partial streamed JSON when its text changes, and replaces a valid block with **Show me** or **Run example**. Highlighting requires no confirmation; the Hello World runner always presents its source-controlled confirmation first. Malformed, unknown, user-authored, missing-target, and ambiguous directives remain inert.

See [UI automation security](../../docs/ui-automation-security.md) for the complete boundary and review checklist.

## Development checks

The DOM contract uses Node's built-in test runner and has no npm dependencies:

```powershell
node --test tests/browser/guide-bridge.test.mjs tests/browser/recipe-runner.test.mjs
```

The normal Python suite also validates the manifest and runs this contract when Node.js is available.

The canonical inputs remain `knowledge/ui-map.yaml` and `knowledge/recipes/*.yaml`. Regenerate both checked-in browser assets after changing either:

```powershell
python scripts/build-guide-assets.py
```
