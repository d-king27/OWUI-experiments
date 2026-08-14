# Agent package

This directory contains the framework-independent How-To Agent domain logic.

The package will load a small process definition, expose process and step lookups, and later coordinate conversational progress through that process. It must not depend on Open WebUI internals, allowing the UI integration to remain a thin adapter.

Planned content:

- `src/howto_agent/` - Python package for process-domain logic
- `system_prompt.md` - initial conversational behavior instructions
- `process_definition.example.yaml` - example process structure
