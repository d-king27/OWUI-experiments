# Start the Open WebUI Guide PoC without an API key

This guide starts and installs the complete local proof of concept without an Open WebUI API key, an OpenAI key, a paid account, or an actual language model.

The local environment contains two deterministic chat choices:

- `hello-world` is a fixed connectivity provider that always returns the same response.
- **Open WebUI Guide** is a rule-based Pipe backed by the repository instruction manual.

The Function is installed manually through the Open WebUI administrator interface. The API-key installer is optional automation and is not used by this guide.

## Requirements

- Docker Desktop running Linux containers.
- Docker Compose v2 or later (`docker compose version`).
- Chrome or Edge if you want to test the unpacked Guide Bridge extension.
- A local copy of this repository.

Python, Node.js, an LLM subscription, and an Open WebUI cloud account are not required for the main walkthrough. Python and Node.js are only needed for the optional developer test suite.

## 1. Create the local configuration

Open PowerShell in the repository root:

```powershell
Copy-Item .env.example .env
```

Generate a local secret with PowerShell:

```powershell
$secretBytes = [byte[]]::new(32)
[Security.Cryptography.RandomNumberGenerator]::Fill($secretBytes)
[Convert]::ToHexString($secretBytes).ToLowerInvariant()
```

Copy the printed value. Open `.env` and replace:

```text
WEBUI_SECRET_KEY=replace-with-a-long-random-value
```

with:

```text
WEBUI_SECRET_KEY=<your-generated-value>
```

Keep `.env` outside source control. The default configuration disables authentication and exposes port 3000 only on the local loopback interface.

## 2. Start the local services

```powershell
docker compose up -d
docker compose ps
```

Wait until `hello-provider` is healthy and `open-webui` is running. The first Open WebUI image download can take several minutes.

If a service does not start, inspect its logs:

```powershell
docker compose logs hello-provider
docker compose logs open-webui
```

## 3. Verify the fixed provider

Open <http://localhost:3000>.

1. Select `hello-world` in the model picker if it is not already selected.
2. Send any message.
3. Confirm the response is exactly:

```text
Hello, world! The baseline chat connection is working.
```

This confirms Open WebUI can exchange a chat request with the local provider. It does not demonstrate LLM reasoning.

## 4. Install Open WebUI Guide manually

No API key is required for this step.

1. In the repository, open `openwebui/functions/howto_pipe.py` and copy the entire file.
2. In Open WebUI, open **Admin Panel → Functions**. Some layouts expose this under **Workspace → Functions**.
3. Choose **Create**.
4. Enter:

   ```text
   ID: open_webui_guide
   Name: Open WebUI Guide
   Description: Grounded onboarding guide backed by source-controlled content.
   ```

5. Paste the complete `howto_pipe.py` source into the Function editor.
6. Save the Function.
7. Enable its **Active** toggle.
8. Return to a new chat and reload the page if necessary.

The Compose configuration has already mounted the supporting `agent`, `knowledge`, and `openwebui` directories read-only inside the container. The pasted Function imports those mounted modules; no package download or model provider is needed.

If the Functions administration screen is unavailable, confirm that you are using the local administrator view and that the Compose service has finished starting. You do not need to create an account on `openwebui.com`.

## 5. Test the deterministic guide

Select **Open WebUI Guide** from the model picker and send these prompts one at a time:

```text
What is Open WebUI?
How do I use it?
What is a model?
What agents do I have access to?
Give me a workable example
```

Expected behavior:

- Answers are grounded in `knowledge/open-webui-instruction-manual.md`.
- The available-chat-choices answer is obtained from the current Open WebUI catalogue.
- The workable example includes a validated `owui-action` block.
- An unsupported question returns a bounded “not enough information” response.

Before installing the browser extension, `owui-action` blocks appear as ordinary fenced JSON. That is expected.

## 6. Install the Getting started browser extension

The unpacked extension is only the PoC browser adapter. Your planned organisational implementation can move this CTA into the organisation-owned welcome page.

1. Open `chrome://extensions` in Chrome or `edge://extensions` in Edge.
2. Enable **Developer mode**.
3. Choose **Load unpacked**.
4. Select the repository directory `openwebui/guide-extension`.
5. Reload <http://localhost:3000>.

The extension requests no browser permissions and runs only on the two configured loopback origins.

## 7. Test the Getting started flow

1. Confirm exactly one **Getting started** button is present.
2. Open it and choose **Cancel**. The current chat must remain unchanged and focus must return to the CTA.
3. Open it again and choose **Start guide**.
4. Confirm a new chat opens, **Open WebUI Guide** is selected, and `Start the getting started tour` is submitted.
5. Choose **Show me** in the guide response and confirm the model picker receives an outline and **Guide target** label.
6. Ask `Give me a workable example` and choose **Run example**.
7. Cancel once and confirm no UI action occurs.
8. Run it again and confirm it selects `hello-world`, submits the fixed test, highlights the exact response, and restores **Open WebUI Guide**.
9. Press Escape during a recipe and confirm no later action runs.

## Optional: run developer checks

These checks require Python 3.11+, `uv`, and Node.js:

```powershell
uv run python -m unittest discover -s tests
node --test tests/browser/*.test.mjs
uv run python scripts/build-guide-assets.py --check
```

## Stop or reset

Stop the services without deleting Open WebUI data:

```powershell
docker compose down
```

Remove only the browser adapter from the Chrome or Edge extensions page. This does not change Open WebUI data.

Disable or delete **Open WebUI Guide** from the Functions administration page to remove only the selectable guide.

> **Destructive full reset:** `docker compose down -v` permanently deletes the local Open WebUI volume, including chats, settings, API keys, Functions, and uploaded data.

## What the Open WebUI API key was for

`scripts/install-howto-function.ps1` uses an administrator Open WebUI API key to create or update the Function through an HTTP endpoint. It is a deployment convenience, not a runtime requirement for the guide.

For this walkthrough, manual installation replaces that automated request. No Open WebUI API key is created or supplied.
