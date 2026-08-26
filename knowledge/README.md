# Knowledge

This directory will contain supporting documentation that helps the agent explain a process.

Process structure and supporting knowledge are related but separate:

- A process definition answers: **What steps exist, and in what order?**
- Knowledge documents answer: **What does a step mean, why does it work this way, and what does the user need to know?**

Future experiments may upload these documents to an Open WebUI Knowledge Base, index them in a retrieval layer, or query them directly through an agent tool. This initial project does not implement retrieval-augmented generation.

`example-process.md` explains the Hello World connectivity process represented by `agent/process_definition.example.yaml`.

## How-To Agent proof-of-concept drafts

The initial Ticket 2 content is available for refinement before the loaders and browser bridge are implemented:

- `open-webui-instruction-manual.md` - grounded starter content and supported tour behaviour.
- `ui-map.yaml` - semantic UI target registry with explicitly provisional locator candidates.
- `recipes/launch-getting-started.yaml` - consent-gated CTA launch sequence.
- `recipes/hello-world-demo.yaml` - consent-gated connectivity demonstration.

The UI map is marked `verification.state: not_run`. Its locator candidates must be verified against the Compose-pinned Open WebUI build before interactive recipe actions are enabled.
