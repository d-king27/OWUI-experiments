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
