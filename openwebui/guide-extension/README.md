# Open WebUI Guide Bridge

This directory is an unpacked Manifest V3 browser extension for the local proof of concept. It adds one persistent **Getting started** button to a semantic Open WebUI navigation target and presents an accessible confirmation before requesting any automation.

## Install for local development

1. Start the pinned Open WebUI Compose service at `http://localhost:3000` or `http://127.0.0.1:3000`.
2. Open `chrome://extensions` in Chrome or `edge://extensions` in Edge.
3. Enable **Developer mode**.
4. Choose **Load unpacked** and select this `openwebui/guide-extension` directory.
5. Reload Open WebUI after changing extension files.

The manifest requests no browser permissions and runs only on the two loopback origins above. To reset it, remove the unpacked extension from the browser's extension page; no Open WebUI data is changed.

## Ticket 6 behaviour

- `bridge.js` validates the generated UI map, enforces its origin allow-list, and resolves the `navigation-actions` target without accepting selectors from chat output.
- A `MutationObserver` restores the CTA after client-side navigation while preventing duplicates.
- The confirmation uses a native `dialog`, moves initial focus to **Cancel**, supports Escape through the dialog's cancel event, and restores CTA focus after cancellation.
- Confirming makes one allow-listed, versioned request for `launch-getting-started` through the extension-isolated `registerRecipeRunner` API.
- Only one runner can register, and the bridge accepts only an exact version 1 CTA request for that recipe. Without a runner, the dialog stays open and explains that the guide is unavailable. No navigation, click, typing, or submission is attempted.
- Privacy-conscious lifecycle signals are local `howto-guide:telemetry` events containing only an event name and schema version.

The consent-gated recipe runner and directive-driven highlights are deliberately not part of this ticket.

## Development checks

The DOM contract uses Node's built-in test runner and has no npm dependencies:

```powershell
node --test tests/browser/guide-bridge.test.mjs
```

The normal Python suite also validates the manifest and runs this contract when Node.js is available.

The canonical UI map remains `knowledge/ui-map.yaml`. Regenerate the checked-in browser asset after changing it:

```powershell
python scripts/build-guide-assets.py
```
