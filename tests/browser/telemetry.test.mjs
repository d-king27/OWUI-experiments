import assert from "node:assert/strict";
import test from "node:test";
import { fileURLToPath, pathToFileURL } from "node:url";
import path from "node:path";


const TEST_DIRECTORY = path.dirname(fileURLToPath(import.meta.url));
const EXTENSION_DIRECTORY = path.resolve(
  TEST_DIRECTORY,
  "../../openwebui/guide-extension",
);
await import(pathToFileURL(path.join(EXTENSION_DIRECTORY, "telemetry.js")));

const api = globalThis.HowToGuideTelemetry;


class FakeCustomEvent {
  constructor(type, options) {
    this.type = type;
    this.detail = options.detail;
  }
}


test("emits only allow-listed local lifecycle fields", () => {
  const events = [];
  const emit = api.createTelemetryEmitter({
    scope: { dispatchEvent: (event) => events.push(event) },
    CustomEvent: FakeCustomEvent,
    eventName: "howto-guide:telemetry",
  });

  emit("guide_cta_shown");
  emit("guide_recipe_failed", {
    recipe: "hello-world-demo",
    step: "verify_fixed_response",
    category: "step_timeout",
  });

  assert.deepEqual(
    events.map(({ type, detail }) => ({ type, detail })),
    [
      {
        type: "howto-guide:telemetry",
        detail: { name: "guide_cta_shown", version: 1 },
      },
      {
        type: "howto-guide:telemetry",
        detail: {
          name: "guide_recipe_failed",
          version: 1,
          recipe: "hello-world-demo",
          step: "verify_fixed_response",
          category: "step_timeout",
        },
      },
    ],
  );
});


test("rejects message, DOM, credential, and arbitrary metadata", () => {
  for (const fields of [
    { message: "chat content" },
    { selector: "#password" },
    { api_key: "secret" },
    { recipe: "arbitrary-recipe" },
  ]) {
    assert.throws(
      () => api.validateEvent("guide_recipe_started", fields),
      /unsupported/i,
    );
  }
  assert.throws(
    () =>
      api.validateEvent("guide_recipe_failed", {
        recipe: "hello-world-demo",
        category: "raw exception text",
      }),
    /failure category/i,
  );
  assert.throws(
    () => api.validateEvent("unknown_event"),
    /unsupported/i,
  );
});
