# Understanding the Hello World baseline

## Purpose

The Hello World baseline is a deliberately small connectivity test. It proves that a user can send a message through Open WebUI, that Open WebUI can call an OpenAI-compatible provider, and that the provider's response can be rendered in the chat interface.

The expected response is:

```text
Hello, world! The baseline chat connection is working.
```

## What the baseline does not prove

The response is fixed. No language model interprets the message, no agent chooses an action, and no knowledge is retrieved. A successful response therefore does not demonstrate reasoning, process-state tracking, retrieval, memory, or tool execution.

## Request path

```text
User message
    |
    v
Open WebUI
    |
    v
hello-provider /v1/chat/completions
    |
    v
Fixed Hello World response
    |
    v
Open WebUI chat
```

The `hello-provider` service advertises one model named `hello-world`. It implements only the small portion of the OpenAI Chat Completions API needed by this experiment.

## Running the check

1. Start the environment with `docker compose up -d`.
2. Open `http://localhost:3000`.
3. Confirm that `hello-world` is the selected model.
4. Send any message.
5. Check that the expected fixed response appears.

The content of the user's message does not affect the result. That predictability makes failures easier to attribute to container startup, model discovery, networking, API compatibility, or UI rendering.

## Interpreting the result

If the fixed response appears, the UI and provider connection are working. The next experimental boundary is to replace the fixed provider behavior with a thin adapter that can call the source-controlled `HowToAgent` domain logic.

If the response does not appear, check the Docker service status and logs before changing agent code:

```powershell
docker compose ps
docker compose logs hello-provider open-webui
```
