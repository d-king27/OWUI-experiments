# Hello World provider

This is a deliberately tiny OpenAI-compatible development provider. It exposes one model, `hello-world`, and always returns a fixed response:

```text
Hello, world! The baseline chat connection is working.
```

Its only purpose is to validate the Open WebUI model selector and chat request path before any agent or real model provider is introduced. It uses only the Python standard library and is not an agent, LLM, or production service.

The provider is reachable only on the internal Compose network. Open WebUI is the sole intended client.
