import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";
import { fileURLToPath, pathToFileURL } from "node:url";
import path from "node:path";


const TEST_DIRECTORY = path.dirname(fileURLToPath(import.meta.url));
const EXTENSION_DIRECTORY = path.resolve(
  TEST_DIRECTORY,
  "../../openwebui/guide-extension",
);
await import(pathToFileURL(path.join(EXTENSION_DIRECTORY, "recipe-runner.js")));

const api = globalThis.HowToGuideRecipeRunner;
const UI_MAP = JSON.parse(
  readFileSync(path.join(EXTENSION_DIRECTORY, "ui-map.json"), "utf8"),
);
const RECIPES = JSON.parse(
  readFileSync(path.join(EXTENSION_DIRECTORY, "recipes.json"), "utf8"),
);


class FakeDocument {
  constructor() {
    this.listeners = new Map();
  }

  addEventListener(type, listener) {
    const listeners = this.listeners.get(type) || [];
    listeners.push(listener);
    this.listeners.set(type, listeners);
  }

  removeEventListener(type, listener) {
    this.listeners.set(
      type,
      (this.listeners.get(type) || []).filter((candidate) => candidate !== listener),
    );
  }

  dispatchKey(key) {
    const event = { key };
    for (const listener of this.listeners.get("keydown") || []) listener(event);
  }
}


class FakeClassList {
  constructor() {
    this.values = new Set();
  }
  add(value) {
    this.values.add(value);
  }
  remove(value) {
    this.values.delete(value);
  }
  contains(value) {
    return this.values.has(value);
  }
}


class FakeElement {
  constructor({ text = "", attributes = {}, contenteditable = false } = {}) {
    this.textContent = text;
    this.attributes = new Map(Object.entries(attributes));
    this.isContentEditable = contenteditable;
    this.disabled = false;
    this.hidden = false;
    this.classList = new FakeClassList();
    this.clickCount = 0;
    this.events = [];
  }
  getAttribute(name) {
    return this.attributes.get(name) ?? null;
  }
  setAttribute(name, value) {
    this.attributes.set(name, String(value));
  }
  removeAttribute(name) {
    this.attributes.delete(name);
  }
  getClientRects() {
    return this.hidden ? [] : [{}];
  }
  click() {
    this.clickCount += 1;
  }
  focus() {
    this.focused = true;
  }
  dispatchEvent(event) {
    this.events.push(event.type);
    return true;
  }
  scrollIntoView() {
    this.scrolled = true;
  }
}


class SelectorDocument {
  constructor(selectors, allElements) {
    this.selectors = selectors;
    this.allElements = allElements;
  }
  querySelectorAll(selector) {
    if (selector === "[data-howto-guide-highlight='true']") {
      return this.allElements.filter(
        (element) => element.getAttribute("data-howto-guide-highlight") === "true",
      );
    }
    return this.selectors.get(selector) || [];
  }
  getElementById() {
    return null;
  }
  execCommand() {
    return false;
  }
}


function clone(value) {
  return JSON.parse(JSON.stringify(value));
}


function fakeStatusView(events) {
  return {
    start: (title) => events.push(["start", title]),
    step: (stepId) => events.push(["step", stepId]),
    finish: (status, message) => events.push(["finish", status, message]),
    remove: () => events.push(["remove"]),
  };
}


function successfulActions(events) {
  return {
    checkPrecondition: async (condition) => {
      events.push(["precondition", condition.check, condition.target]);
      return true;
    },
    runStep: async (step) => events.push(["action", step.id]),
    clearHighlights: () => events.push(["clear"]),
  };
}


function setup({
  actions,
  confirmRecipe = async () => true,
  uiMap = clone(UI_MAP),
  recipeAsset = clone(RECIPES),
} = {}) {
  const document = new FakeDocument();
  const events = [];
  const telemetry = [];
  const runner = api.createRecipeRunner({
    document,
    location: { origin: "http://localhost:3000" },
    uiMap,
    recipeAsset,
    actions: actions || successfulActions(events),
    statusView: fakeStatusView(events),
    confirmRecipe,
    emitTelemetry: (name, fields = {}) => telemetry.push({ name, ...fields }),
  });
  return { document, events, runner, telemetry };
}


test("executes the exact launch recipe after the private confirmed handoff", async () => {
  const { events, runner, telemetry } = setup();

  assert.equal(
    runner.handleConfirmedRequest({
      version: 1,
      recipe: "launch-getting-started",
      source: "cta",
    }),
    true,
  );
  const outcome = await runner.whenIdle();

  assert.deepEqual(outcome, {
    status: "completed",
    recipe: "launch-getting-started",
  });
  assert.deepEqual(
    events.filter(([kind]) => kind === "action").map(([, id]) => id),
    [
      "open_new_chat",
      "wait_for_model_picker",
      "open_model_picker",
      "select_guide",
      "enter_starter_prompt",
      "submit_starter_prompt",
      "wait_for_guide_response",
    ],
  );
  assert.deepEqual(
    telemetry.map(({ name }) => name),
    ["guide_recipe_started", "guide_recipe_completed"],
  );
  runner.dispose();
});


test("fails all preconditions before executing the first recipe step", async () => {
  const events = [];
  const actions = successfulActions(events);
  actions.checkPrecondition = async (condition) => {
    events.push(["precondition", condition.check]);
    return condition.check !== "option_available";
  };
  const { runner, telemetry } = setup({ actions });

  const outcome = await runner.startRecipe("launch-getting-started");

  assert.deepEqual(outcome, {
    status: "failed",
    recipe: "launch-getting-started",
    category: "precondition_failed",
  });
  assert.equal(events.some(([kind]) => kind === "action"), false);
  assert.equal(telemetry.at(-1).category, "precondition_failed");
  runner.dispose();
});


test("Escape aborts an active step and no later action runs", async () => {
  const events = [];
  let signalStepStarted;
  const stepStarted = new Promise((resolve) => {
    signalStepStarted = resolve;
  });
  const actions = successfulActions(events);
  actions.runStep = async (step, _timeout, signal) => {
    events.push(["action", step.id]);
    signalStepStarted();
    await new Promise((_resolve, reject) => {
      signal.addEventListener("abort", () => reject(new Error("aborted")), {
        once: true,
      });
    });
  };
  const { document, runner, telemetry } = setup({ actions });

  const run = runner.startRecipe("launch-getting-started");
  await stepStarted;
  document.dispatchKey("Escape");
  const outcome = await run;

  assert.deepEqual(outcome, {
    status: "cancelled",
    recipe: "launch-getting-started",
  });
  assert.deepEqual(
    events.filter(([kind]) => kind === "action").map(([, id]) => id),
    ["open_new_chat"],
  );
  assert.equal(events.filter(([kind]) => kind === "clear").length >= 1, true);
  assert.equal(telemetry.at(-1).name, "guide_recipe_cancelled");
  runner.dispose();
});


test("Escape stops before every later step in both source-controlled recipes", async () => {
  for (const recipe of RECIPES.recipes) {
    for (const [cancelIndex, expectedStep] of recipe.steps.entries()) {
      const events = [];
      let signalStepStarted;
      const stepStarted = new Promise((resolve) => {
        signalStepStarted = resolve;
      });
      const actions = successfulActions(events);
      actions.runStep = async (step, _timeout, signal) => {
        events.push(["action", step.id]);
        if (step.id !== expectedStep.id) return;
        signalStepStarted();
        await new Promise((_resolve, reject) => {
          signal.addEventListener("abort", () => reject(new Error("aborted")), {
            once: true,
          });
        });
      };
      const { document, runner } = setup({ actions });

      const run = runner.startRecipe(recipe.id);
      await stepStarted;
      document.dispatchKey("Escape");
      const outcome = await run;

      assert.equal(outcome.status, "cancelled", `${recipe.id}:${expectedStep.id}`);
      assert.deepEqual(
        events.filter(([kind]) => kind === "action").map(([, id]) => id),
        recipe.steps.slice(0, cancelIndex + 1).map((step) => step.id),
        `${recipe.id}:${expectedStep.id}`,
      );
      runner.dispose();
    }
  }
});


test("the total timeout aborts a stalled precondition", async () => {
  const recipeAsset = clone(RECIPES);
  recipeAsset.recipes.find(
    (recipe) => recipe.id === "launch-getting-started",
  ).limits.total_timeout_ms = 10;
  const events = [];
  const actions = successfulActions(events);
  actions.checkPrecondition = async (_condition, _timeout, signal) =>
    new Promise((_resolve, reject) => {
      signal.addEventListener("abort", () => reject(new Error("timed out")), {
        once: true,
      });
    });
  const { runner, telemetry } = setup({ actions, recipeAsset });

  const outcome = await runner.startRecipe("launch-getting-started");

  assert.deepEqual(outcome, {
    status: "failed",
    recipe: "launch-getting-started",
    category: "total_timeout",
  });
  assert.equal(events.some(([kind]) => kind === "action"), false);
  assert.equal(telemetry.at(-1).category, "total_timeout");
  runner.dispose();
});


test("runner-owned confirmation can cancel without executing actions", async () => {
  const { events, runner } = setup({ confirmRecipe: async () => false });

  const outcome = await runner.requestWithConfirmation("hello-world-demo");

  assert.deepEqual(outcome, {
    status: "cancelled_before_start",
    recipe: "hello-world-demo",
  });
  assert.equal(events.length, 0);
  runner.dispose();
});


test("rejects arbitrary fixed text and unverified interactive targets", () => {
  const arbitraryText = clone(RECIPES);
  arbitraryText.recipes.find(
    (recipe) => recipe.id === "hello-world-demo",
  ).steps.find((step) => step.id === "enter_test_message").value = "arbitrary";

  assert.throws(
    () => setup({ recipeAsset: arbitraryText }),
    /Invalid recipe step/,
  );

  const unverifiedMap = clone(UI_MAP);
  unverifiedMap.targets["send-button"].verification = "required";
  assert.throws(
    () => setup({ uiMap: unverifiedMap }),
    /Interactive target is not verified/,
  );
});


test("rejects missing safety preconditions and unknown recipe requests", async () => {
  const missingPrecondition = clone(RECIPES);
  missingPrecondition.recipes.find(
    (recipe) => recipe.id === "launch-getting-started",
  ).preconditions = [];
  assert.throws(() => setup({ recipeAsset: missingPrecondition }), /Invalid recipe/);

  const { runner } = setup();
  assert.equal(
    runner.handleConfirmedRequest({
      version: 1,
      recipe: "hello-world-demo",
      source: "cta",
    }),
    false,
  );
  assert.deepEqual(await runner.startRecipe("unknown"), {
    status: "unavailable",
    recipe: "unknown",
  });
  runner.dispose();
});


test("DOM actions resolve verified targets, fixed values, options, and highlights", async () => {
  const newChat = new FakeElement({ attributes: { "aria-label": "New Chat" } });
  const picker = new FakeElement({
    text: "Open WebUI Guide",
    attributes: { "aria-label": "Selected model: Open WebUI Guide" },
  });
  const composer = new FakeElement({
    attributes: { contenteditable: "true" },
    contenteditable: true,
  });
  const send = new FakeElement();
  const option = new FakeElement({
    text: "hello-world",
    attributes: { role: "option" },
  });
  const assistant = new FakeElement({
    text: "Hello, world! The baseline chat connection is working.",
  });
  const allElements = [newChat, picker, composer, send, option, assistant];
  const selectors = new Map([
    ["a[href],[role='link']", [newChat]],
    ["button[aria-haspopup='listbox']", [picker]],
    ["#chat-input[contenteditable='true']", [composer]],
    ["form button[type='submit']", [send]],
    ["[role='option']", [option]],
    [".chat-assistant .markdown-prose", [assistant]],
    ["[data-message-role='assistant']", [assistant]],
    ["[data-role='assistant']", []],
  ]);
  const document = new SelectorDocument(selectors, allElements);
  const actions = api.createDomRecipeActions({
    document,
    uiMap: clone(UI_MAP),
  });
  const controller = new AbortController();

  await actions.runStep(
    { action: "click", target: "new-chat" },
    100,
    controller.signal,
  );
  await actions.runStep(
    {
      action: "type_fixed_text",
      target: "message-composer",
      value: "Start the getting started tour",
      clear_existing: true,
    },
    100,
    controller.signal,
  );
  await actions.runStep(
    { action: "choose_option", target: "model-picker", value: "hello-world" },
    100,
    controller.signal,
  );
  await actions.runStep(
    { action: "highlight", target: "assistant-message", duration_ms: 100 },
    100,
    controller.signal,
  );

  assert.equal(newChat.clickCount, 1);
  assert.equal(composer.textContent, "Start the getting started tour");
  assert.deepEqual(composer.events, ["input"]);
  assert.equal(option.clickCount, 1);
  assert.equal(assistant.classList.contains("howto-guide__highlight"), true);
  assert.equal(
    assistant.getAttribute("data-howto-guide-highlight-label"),
    "Guide target",
  );
  assert.equal(assistant.scrolled, true);
  assert.equal(
    await actions.checkPrecondition(
      { check: "selected_option", target: "model-picker", value: "Open WebUI Guide" },
      100,
      controller.signal,
    ),
    true,
  );
  actions.clearHighlights();
  assert.equal(assistant.classList.contains("howto-guide__highlight"), false);
  assert.equal(assistant.getAttribute("data-howto-guide-highlight-label"), null);
});
