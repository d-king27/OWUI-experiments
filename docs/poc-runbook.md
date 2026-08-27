# Open WebUI Guide PoC runbook

This runbook is the single setup, verification, limitation, and reset reference for the Open WebUI Guide proof of concept. It targets the Compose-pinned Open WebUI `v0.11.0` build and loopback origins only.

## Prerequisites

- Docker Desktop using Linux containers and Docker Compose v2.
- PowerShell 7 for the administrator Function installer.
- Chrome or Edge with permission to load a local unpacked extension.
- Python 3.11+ and Node.js when running the automated checks.

Never commit `.env`, administrator API keys, provider keys, or copied Open WebUI data.

## Start the local baseline

From the repository root, create the local configuration and replace the placeholder secret:

```powershell
Copy-Item .env.example .env
python -c "import secrets; print(secrets.token_hex(32))"
docker compose up -d
docker compose ps
```

Open <http://localhost:3000>. Select `hello-world`, send any message, and confirm the fixed response:

```text
Hello, world! The baseline chat connection is working.
```

This provider is a connectivity fixture, not a language model or agent.

## Install the selectable guide

The primary PoC path requires no Open WebUI API key:

1. Copy the complete contents of `openwebui/functions/howto_pipe.py`.
2. Open **Admin Panel → Functions** in Open WebUI. Some layouts expose this under **Workspace → Functions**.
3. Create a Function with ID `open_webui_guide` and name **Open WebUI Guide**.
4. Paste the source, save it, and enable its **Active** toggle.
5. Reload the chat and select **Open WebUI Guide**.

The mounted domain and knowledge files supply everything imported by the Function. The full no-key walkthrough is [Start the Open WebUI Guide PoC without an API key](getting-started-without-api-key.md).

An administrator API key is needed only for the optional automated installer:

```powershell
$env:OPEN_WEBUI_API_KEY = "<admin-api-key>"
./scripts/install-howto-function.ps1
```

The installer is idempotent. It refuses to replace differing stored source unless `-Update` is supplied explicitly. Select **Open WebUI Guide** in the model picker and ask `What is Open WebUI?` before installing the browser adapter.

## Install the local Guide Bridge

1. Open `chrome://extensions` or `edge://extensions`.
2. Enable **Developer mode**.
3. Choose **Load unpacked** and select `openwebui/guide-extension`.
4. Reload the Open WebUI tab after every extension code change.

The extension requests no browser permissions and matches only `http://localhost:3000/*` and `http://127.0.0.1:3000/*`.

## Automated verification

Run the repository and browser contracts:

```powershell
uv run python -m unittest discover -s tests
node --test tests/browser/*.test.mjs
uv run python scripts/build-guide-assets.py --check
```

The Python suite also invokes the browser contracts when Node.js is available. The YAML UI map and recipes are canonical; generated JSON must remain unchanged in check mode.

For an isolated responsive and keyboard check using the production extension JavaScript and CSS, serve the repository and open the visual fixture:

```powershell
python -m http.server 8877 --bind 127.0.0.1
```

Open <http://127.0.0.1:8877/tests/browser/fixtures/guide-extension-visual.html>. This fixture shortens recipe timings and replaces page-changing actions; it verifies presentation and interaction boundaries, not Open WebUI integration.

## Acceptance walkthrough

Perform this walkthrough after any Open WebUI or browser-extension upgrade:

1. Confirm **Open WebUI Guide** and `hello-world` are both visible to the current user.
2. Confirm exactly one **Getting started** CTA is visible after initial load and client-side navigation.
3. Open the CTA confirmation with the keyboard. Initial focus must be on **Cancel**; Escape and **Cancel** must close it, restore CTA focus, and leave the current URL, draft, and messages unchanged.
4. Confirm **Start guide**. A new chat must open, **Open WebUI Guide** must be selected, and the visible `Start the getting started tour` prompt must be submitted once.
5. Ask each minimum question: what Open WebUI is, how to use it, what a model is, which chat choices are available, and for a workable example.
6. Confirm chat choices match the current user's model picker rather than a hard-coded list.
7. Use **Show me** for every supported target. The page must scroll to one unambiguous target and show both an outline and a **Guide target** label; Escape clears it.
8. Choose **Run example**, then cancel. No model selection, typing, submission, or navigation may occur.
9. Run the example after confirmation. It must submit `Test the connection` once, match the exact fixed Hello World response, highlight it, and restore **Open WebUI Guide**.
10. Press Escape during each source-controlled step. No later click, typing, submission, or model change may run.
11. Confirm malformed, unknown, user-message, missing-target, and ambiguous directives remain visible or fail with a local status and never execute.

## Responsive and accessibility matrix

Use at least these PoC viewports; they are verification targets, not a general browser support promise:

| Viewport | Checks |
| --- | --- |
| 1024 × 768 | CTA does not cover native navigation controls; dialog remains centred and bounded; runner status does not obscure the composer. |
| 390 × 844 | Navigation wraps without horizontal overflow; dialog actions are full-width; all controls remain reachable at 200% zoom. |

At both sizes verify:

- Tab order follows CTA, confirmation controls, directive controls, and native page controls logically.
- Focus has a visible three-pixel outline.
- Both dialogs have an accessible name and description, start on **Cancel**, close with Escape, and restore focus.
- Status changes use polite live regions; failures use an alert.
- Highlighting includes the text label **Guide target**, so colour is not the only cue.
- Reduced-motion mode disables smooth highlight scrolling.
- Windows High Contrast or forced-colours mode retains a visible highlight and focus indicator.

Record the Open WebUI version, browser/version, operating system, viewport, result, and issue link for each manual run. Do not record chat text, page content, credentials, or user-entered values.

### Repository verification record — 2026-08-26

The production scripts, generated assets, and CSS were loaded through the visual fixture in the Codex in-app Chromium browser on Windows:

- **1024 × 768 — passed:** exactly one CTA and one directive control rendered; the confirmation had an accessible name and description; initial focus was **Cancel**; the model picker received the **Guide target** attribute; no browser warnings or errors were reported.
- **390 × 844 — passed:** no horizontal overflow; the CTA and dialog remained inside the viewport; both confirmation actions rendered at full available width; initial focus was **Cancel**; cancelling removed the dialog and restored CTA focus.
- **Automated contracts — passed:** the integrated CTA-to-runner flow, every-step Escape behavior, directive failure cases, telemetry field allow-list, and generated assets were verified.

An operator must still repeat the live acceptance walkthrough with the unpacked extension in each intended Chrome/Edge version. Screen-reader output, 200% zoom, and operating-system forced-colours rendering are browser-fleet release checks and were not represented by the in-app test surface.

## Local observability

The browser adapter emits `howto-guide:telemetry` as a local `CustomEvent`. Nothing in this repository stores or transmits these events. The client validator permits only:

| Event | Additional fields |
| --- | --- |
| `guide_cta_shown`, `guide_cta_started`, `guide_cta_cancelled`, `guide_cta_unavailable` | none |
| `guide_directive_shown` | none |
| `guide_recipe_started`, `guide_recipe_completed`, `guide_recipe_cancelled` | allow-listed recipe ID |
| `guide_recipe_failed` | allow-listed recipe ID, source-controlled step ID when a step had started, and coarse error category |

For a temporary local review, attach a listener in the Open WebUI developer console before exercising the flow:

```javascript
window.addEventListener("howto-guide:telemetry", ({ detail }) => {
  console.info("Guide lifecycle", detail);
});
```

Do not add chat text, DOM text, selectors, credentials, user-entered values, or raw exception messages. `guide_question_answered` is intentionally not emitted in this PoC: the deterministic Pipe has no configured telemetry sink, and the browser adapter cannot safely infer server-side intent. Add it only with an explicit server-side privacy and retention design.

## Limitations

- The UI map is pinned to Open WebUI `v0.11.0`; an upgrade requires locator inspection and a new verification record.
- The unpacked extension is a local PoC distribution mechanism, not a production deployment model.
- The Pipe is deterministic and grounded in repository content; it is not a general support agent.
- The visual fixture does not prove live Open WebUI integration. Use it alongside the acceptance walkthrough.
- Events are ephemeral and local; there is no analytics collector, persistence, user identity, or cross-session correlation.
- Automatic extension installation and administrator API-key creation are intentionally out of scope.

## Stop, remove, or reset

Non-destructive stop; the named Open WebUI volume remains:

```powershell
docker compose down
```

Remove only the browser adapter by choosing **Remove** for **Open WebUI Guide Bridge** on the browser extension page. Reload Open WebUI; no Open WebUI data is changed.

Disable or delete only the selectable guide from **Workspace → Functions** in Open WebUI. Revoke the administrator API key from the Open WebUI account settings when it is no longer needed. These are deliberate administrator actions; the installer does not delete Functions.

For a clean local reinstallation, remove the unpacked extension, delete or disable the guide Function, and restart the Compose services. Preserve the volume unless application data itself must be discarded.

> **Destructive full reset:** `docker compose down -v` permanently deletes the named local Open WebUI volume, including accounts, chats, settings, API keys, installed Functions, and uploaded data. It cannot be recovered by this repository.

After a full reset, repeat this runbook from **Start the local baseline**.
