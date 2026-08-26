# Guide Bridge UI automation security

The Guide Bridge recipe runner is narrow, local proof-of-concept automation. It is not a general browser-control interface and does not execute selectors, scripts, text, or recipes supplied by a model.

## Trust boundaries

- The server Pipe may request only a semantic target or source-controlled recipe ID. Browser code treats that output as untrusted.
- `knowledge/ui-map.yaml` and `knowledge/recipes/*.yaml` are canonical, reviewed source. The build script validates them and creates `ui-map.json` and `recipes.json` for the extension.
- The extension validates both generated assets again. It accepts only schema version 1, Open WebUI v0.11.0, the two loopback origins, the two known recipe IDs, exact ordered actions, and exact fixed values.
- Mutating actions require a target whose locator was verified against the pinned Open WebUI version.
- The page cannot register or invoke the runner through a DOM event. Handoff uses a private extension-world API with one registered runner.
- Directive discovery is scoped to fenced `owui-action` blocks inside the pinned assistant-message container. Identical blocks in user messages are ignored.
- The renderer accepts only exact version 1 `highlight` and `run_recipe` shapes. Unknown keys, kinds, targets, recipes, confirmation flags, oversized payloads, and malformed JSON remain visible but inert.

## Consent and execution

The CTA confirmation covers `launch-getting-started`. Other recipe entry points use the runner-owned native confirmation dialog. Cancellation before confirmation performs no recipe action.

While a recipe is active:

- A fixed status indicator names the source-controlled recipe and tells the user that Escape stops it.
- Only `click`, `choose_option`, `type_fixed_text`, `wait_for_target`, `wait_for_text`, and `highlight` are recognized.
- Text and option values must exactly match the checked-in recipe contract.
- Preconditions run before the first recipe step. Missing or ambiguous targets and options fail closed.
- Each wait has a bounded timeout and the whole recipe has a maximum duration.
- Escape aborts the active wait and prevents every subsequent click, selection, type, or submission.
- Failures and cancellation clear active highlights and do not run restoration actions.
- Only coarse event name, recipe ID, step-independent error category, and schema version may enter local telemetry events.
- Highlight controls resolve semantic IDs through the source-generated UI map, scroll the unique target into view, identify it in visible status text, and clear on Escape or timeout.

The runner never targets authentication, accounts, administration, deletion, uploads, provider settings, passwords, or credentials.

## Review checklist

When Open WebUI or a recipe changes:

1. Inspect every mutating locator against the pinned build without executing the recipe.
2. Update the canonical YAML and its target-specific verification state.
3. Regenerate both browser assets with `python scripts/build-guide-assets.py`.
4. Review the generated diff, especially action order and fixed values.
5. Run the Python and browser contract suites.
6. Manually verify confirmation, narrow viewport layout, success, missing-option failure, timeout, and Escape between every pair of steps.

If any interactive locator is unverified or ambiguous, the extension must remain unloaded or the affected recipe must remain unavailable.
