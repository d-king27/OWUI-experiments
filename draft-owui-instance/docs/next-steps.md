# Next steps

## Experiment sequence

1. Get Open WebUI running locally with persistent data.
2. Connect one OpenAI-compatible LLM provider.
3. Test the initial system prompt manually.
4. Define one real-world how-to process.
5. Implement explicit process-state tracking.
6. Create a minimal Open WebUI Pipe Function adapter.
7. Add grounded knowledge retrieval.
8. Add narrowly scoped tool or API execution.
9. Persist incomplete process state when evidence shows it is needed.
10. Evaluate whether a more sophisticated agent framework is justified.

The minimal Pipe in step 6 now exists in source with reproducible read-only container mounts and an idempotent administrator installer. Its imports and mounted content have been verified in the pinned running container. An administrator still needs to create an API key and run the installer before the local UI exposes the guide as a selectable Function.

The Open WebUI Guide PoC is implemented through Ticket 9. The Guide Bridge injects a deduplicated local CTA, runs independently validated consent-gated recipes, and replaces valid assistant `owui-action` blocks with **Show me** and **Run example** controls. Cross-component browser contracts, every-step Escape coverage, a responsive visual fixture, a privacy-constrained local telemetry boundary, and a consolidated [PoC runbook](poc-runbook.md) now cover the final hardening scope.

The next decision is whether the experiment justifies a production path. Before that decision, run the documented live acceptance walkthrough with the intended browser fleet and record any Open WebUI upgrade drift.

Broader task understanding and model recommendations are deliberately benched for the current PoC. The proposed follow-on is documented in [Next phase: Anthropic-backed task planning](next-phase-anthropic-task-planning.md): connect Anthropic first, then introduce a constrained planner, organization-owned capability profiles, a spreadsheet-help vertical slice, and finally the native welcome-page CTA.

## Questions to answer through experimentation

- Should process state live in conversation context or an external store?
- How should the agent determine that a step is complete?
- How much of the workflow should be deterministic versus LLM-driven?
- How should branching processes be represented?
- How should supporting documentation be retrieved?
- When should the agent call a tool instead of instructing the user?
- How should a user resume an incomplete process?
- How tightly should the implementation integrate with Open WebUI?

## First recommended experiment

Give one model the initial system prompt and one realistic process definition. Run a small scripted set of conversations that start at different points in the process, then assess whether the model consistently identifies the current step and recommends one appropriate next action. Use the results to design deterministic state tracking before building the adapter.
