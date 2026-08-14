# Open WebUI integration

This directory is reserved for Open WebUI-specific infrastructure notes and source-controlled adapters.

Open WebUI is the interaction layer for this project. Agent and process-domain logic belongs in `agent/`, not inside Open WebUI itself. The project will use the official container and will not fork or modify Open WebUI unless a later experiment demonstrates a compelling need.

## Local container

The root Compose file runs the official image pinned through `WEBUI_DOCKER_TAG`. It maps host port 3000 on the loopback interface to Open WebUI's container port 8080 and persists application data in the `howto-agent-open-webui-data` Docker volume.

The container can reach services running on the host through `host.docker.internal`. Automatic installation of Python dependencies declared by Function frontmatter is disabled for this experimental environment.

Authentication is disabled for the local baseline. This is safe only because the published port is restricted to `127.0.0.1`. Enabling authentication later requires recreating the data volume.

## Baseline chat provider

Compose starts a small internal `hello-provider` service alongside Open WebUI. It advertises one model named `hello-world` and returns a fixed response to every chat request. This proves the UI-to-provider request path works before agent behavior or paid credentials are introduced.

The implementation is in [`mock_provider/server.py`](mock_provider/server.py) and uses only the Python standard library. It is not intended for deployment or extension into the future agent.

## Connecting a model provider

The committed baseline configures the internal Hello World provider automatically. When replacing it with a real provider, enable authentication as appropriate and use **Admin Panel -> Settings -> Connections** or update the initial environment configuration on a fresh volume.

### OpenAI

Add an OpenAI connection with base URL `https://api.openai.com/v1` and a least-privilege API key.

### Another OpenAI-compatible API

Add a connection using the provider's OpenAI-compatible `/v1` base URL and credentials. Model availability and optional API features depend on that provider's compatibility.

### Ollama on the host

Ollama is deliberately not provisioned by this Compose project. If Ollama is already running on the host, configure its URL as:

```text
http://host.docker.internal:11434
```

It can be added as a separate Compose service later if an experiment requires a reproducible local model runtime.

## Persistent configuration

Many Open WebUI connection settings are stored in its application database after the first launch. Later environment-variable changes may not override values already saved there. Prefer the Admin Panel for connection changes after initial setup.

Do not commit provider keys or the local `.env` file.
