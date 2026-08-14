# Open WebUI How-To Agent

An experimental development environment for building a conversational process-guidance agent on top of Open WebUI.

The project is intentionally small and modular. Open WebUI provides the interaction layer, while process orchestration, prompts, process definitions, and supporting knowledge remain source controlled and independent of Open WebUI internals.

## Current status

The repository foundation and a working local Open WebUI baseline are in place. A deterministic development provider exposes a `hello-world` model so the chat UI can be tested without credentials or a real LLM. The agent package remains an empty boundary: no agent behavior, extensions, or custom tools are loaded into Open WebUI.

## Architecture

```text
Browser
   |
   v
Open WebUI
   |
   v
Hello World provider

Later:

Open WebUI -> real LLM provider

Future:

Open WebUI
   |
   v
How-To Agent adapter
   |
   +-- Process engine
   +-- Knowledge
   +-- Tools and APIs
```

## Repository layout

| Path | Purpose |
| --- | --- |
| `agent/` | Framework-independent agent and process-domain logic |
| `openwebui/` | Open WebUI infrastructure, baseline provider, and future adapters |
| `knowledge/` | Supporting process documentation, kept separate from process structure |
| `scripts/` | Local development helper commands |
| `tests/` | Automated tests for the agent package |
| `docs/` | Architecture decisions and the experiment roadmap |

## Getting started

Requirements:

- Docker Desktop with Linux containers
- Docker Compose v2 or later

Create local configuration in PowerShell:

```powershell
Copy-Item .env.example .env
python -c "import secrets; print(secrets.token_hex(32))"
```

Replace the placeholder `WEBUI_SECRET_KEY` in `.env` with the generated value, then start the baseline:

```powershell
docker compose up -d
```

Open <http://localhost:3000>, select the `hello-world` model if it is not already selected, and send any message. The response should be:

```text
Hello, world! The baseline chat connection is working.
```

Authentication is disabled for this local baseline, and port 3000 is bound to the loopback interface rather than the local network. Changing authentication mode later requires a fresh Open WebUI data volume.

View logs or stop the service without deleting its data:

```powershell
docker compose logs -f open-webui
docker compose down
```

> **Destructive reset:** `docker compose down -v` permanently deletes the local Open WebUI volume, including accounts, chats, settings, and uploaded data.

The Hello World provider is a disposable connectivity check, not an agent or LLM. See [Open WebUI integration](openwebui/README.md) for replacing it with a real model provider.

## Design principles

- Prefer the official Open WebUI container over a source fork.
- Keep domain logic outside Open WebUI extension code.
- Keep process structure separate from explanatory knowledge.
- Add frameworks and infrastructure only when experiments demonstrate a need.
- Treat all Open WebUI Functions and Tools as trusted server-side code.
