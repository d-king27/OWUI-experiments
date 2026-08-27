import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";
import { fileURLToPath, pathToFileURL } from "node:url";
import path from "node:path";


const TEST_DIRECTORY = path.dirname(fileURLToPath(import.meta.url));
const BRIDGE_PATH = path.resolve(
  TEST_DIRECTORY,
  "../../openwebui/guide-extension/bridge.js",
);
await import(pathToFileURL(BRIDGE_PATH));
await import(
  pathToFileURL(path.join(path.dirname(BRIDGE_PATH), "recipe-runner.js"))
);

const api = globalThis.HowToGuideBridge;
const runnerApi = globalThis.HowToGuideRecipeRunner;
const FULL_UI_MAP = JSON.parse(
  readFileSync(path.join(path.dirname(BRIDGE_PATH), "ui-map.json"), "utf8"),
);
const RECIPES = JSON.parse(
  readFileSync(path.join(path.dirname(BRIDGE_PATH), "recipes.json"), "utf8"),
);


class FakeEvent {
  constructor(type, options = {}) {
    this.type = type;
    this.cancelable = Boolean(options.cancelable);
    this.defaultPrevented = false;
  }

  preventDefault() {
    if (this.cancelable || this.type === "cancel") {
      this.defaultPrevented = true;
    }
  }
}


class FakeEventTarget {
  constructor() {
    this.listeners = new Map();
  }

  addEventListener(type, listener) {
    const listeners = this.listeners.get(type) || [];
    listeners.push(listener);
    this.listeners.set(type, listeners);
  }

  dispatchEvent(event) {
    for (const listener of this.listeners.get(event.type) || []) {
      listener.call(this, event);
    }
    return !event.defaultPrevented;
  }
}


class FakeElement extends FakeEventTarget {
  constructor(tagName, document) {
    super();
    this.tagName = tagName.toUpperCase();
    this.ownerDocument = document;
    this.parentNode = null;
    this.children = [];
    this.attributes = new Map();
    this.dataset = {};
    this.className = "";
    this.textContent = "";
    this.hidden = false;
    this.disabled = false;
    this.open = false;
    this.id = "";
  }

  appendChild(child) {
    child.parentNode = this;
    this.children.push(child);
    return child;
  }

  remove() {
    if (!this.parentNode) return;
    this.parentNode.children = this.parentNode.children.filter(
      (child) => child !== this,
    );
    this.parentNode = null;
  }

  setAttribute(name, value) {
    this.attributes.set(name, String(value));
  }

  getAttribute(name) {
    return this.attributes.get(name) ?? null;
  }

  getClientRects() {
    return this.hidden ? [] : [{}];
  }

  focus() {
    this.ownerDocument.activeElement = this;
  }

  showModal() {
    this.open = true;
  }

  close() {
    this.open = false;
  }

  querySelector(selector) {
    return this.querySelectorAll(selector)[0] || null;
  }

  querySelectorAll(selector) {
    const selectors = selector.split(",").map((part) => part.trim());
    const matches = [];
    for (const child of this.children) {
      if (selectors.some((candidate) => matchesSelector(child, candidate))) {
        matches.push(child);
      }
      matches.push(...child.querySelectorAll(selector));
    }
    return [...new Set(matches)];
  }
}


class FakeDocument {
  constructor() {
    this.listeners = new Map();
    this.activeElement = null;
    this.documentElement = new FakeElement("html", this);
    this.body = new FakeElement("body", this);
    this.documentElement.appendChild(this.body);
  }

  createElement(tagName) {
    return new FakeElement(tagName, this);
  }

  querySelector(selector) {
    return this.documentElement.querySelector(selector);
  }

  querySelectorAll(selector) {
    return this.documentElement.querySelectorAll(selector);
  }

  getElementById(id) {
    return this.querySelectorAll("*").find((element) => element.id === id) || null;
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
}


class FakeMutationObserver {
  static instances = [];

  constructor(callback) {
    this.callback = callback;
    this.disconnected = false;
    FakeMutationObserver.instances.push(this);
  }

  observe() {}

  disconnect() {
    this.disconnected = true;
  }

  trigger() {
    if (!this.disconnected) this.callback([]);
  }
}


function matchesSelector(element, selector) {
  if (selector === "*") return true;
  if (selector.startsWith(".")) {
    return element.className.split(/\s+/).includes(selector.slice(1));
  }
  if (selector === "[data-howto-guide-cta='true']") {
    return element.dataset.howtoGuideCta === "true";
  }
  if (selector === "[data-howto-guide-dialog='true']") {
    return element.dataset.howtoGuideDialog === "true";
  }
  const roleMatch = selector.match(/^\[role='([^']+)'\]$/);
  if (roleMatch) return element.getAttribute("role") === roleMatch[1];
  const tagAttributeMatch = selector.match(/^([a-z]+)\[([^=]+)='([^']+)'\]$/);
  if (tagAttributeMatch) {
    return (
      element.tagName === tagAttributeMatch[1].toUpperCase() &&
      element.getAttribute(tagAttributeMatch[2]) === tagAttributeMatch[3]
    );
  }
  if (selector === "a[href]") {
    return element.tagName === "A" && element.getAttribute("href") !== null;
  }
  if (selector.startsWith("input")) return element.tagName === "INPUT";
  return element.tagName === selector.toUpperCase();
}


function uiMap() {
  return {
    schema_version: 1,
    allowed_origins: ["http://localhost:3000"],
    targets: {
      "navigation-actions": {
        locators: [
          { kind: "css", selector: "nav" },
          {
            kind: "role",
            role: "navigation",
            name_pattern: "(?i)new chat",
          },
        ],
      },
    },
  };
}


function setup({ requestRecipe = async () => false, withNavigation = true } = {}) {
  FakeMutationObserver.instances = [];
  const document = new FakeDocument();
  if (withNavigation) {
    const navigation = document.createElement("nav");
    navigation.setAttribute("aria-label", "New Chat navigation");
    document.body.appendChild(navigation);
  }
  const telemetry = [];
  const bridge = api.createGuideBridge({
    document,
    location: { origin: "http://localhost:3000" },
    MutationObserver: FakeMutationObserver,
    CustomEvent: FakeEvent,
    loadUiMap: async () => uiMap(),
    requestRecipe,
    emitTelemetry: (name) => telemetry.push(name),
  });
  return { bridge, document, telemetry };
}


function findButton(document, label) {
  return document
    .querySelectorAll("button")
    .find((button) => button.textContent === label);
}


async function flushAsyncListener() {
  await new Promise((resolve) => setTimeout(resolve, 0));
}


test("injects exactly one CTA across repeated mutations", async () => {
  const { bridge, document, telemetry } = setup();
  assert.equal(await bridge.start(), true);

  for (const observer of FakeMutationObserver.instances) observer.trigger();
  bridge.ensureGettingStartedCta();

  assert.equal(document.querySelectorAll(api.CTA_SELECTOR).length, 1);
  assert.deepEqual(telemetry, ["guide_cta_shown"]);
});


test("waits for the semantic navigation target to appear", async () => {
  const { bridge, document } = setup({ withNavigation: false });
  await bridge.start();
  assert.equal(document.querySelector(api.CTA_SELECTOR), null);

  const navigation = document.createElement("nav");
  navigation.setAttribute("aria-label", "New Chat navigation");
  document.body.appendChild(navigation);
  for (const observer of FakeMutationObserver.instances) observer.trigger();

  assert.ok(document.querySelector(api.CTA_SELECTOR));
});


test("cancelling the confirmation changes no page state and restores focus", async () => {
  const { bridge, document, telemetry } = setup();
  await bridge.start();
  const cta = document.querySelector(api.CTA_SELECTOR);
  cta.dispatchEvent(new FakeEvent("click"));

  assert.ok(document.querySelector(api.DIALOG_SELECTOR));
  findButton(document, "Cancel").dispatchEvent(new FakeEvent("click"));

  assert.equal(document.querySelector(api.DIALOG_SELECTOR), null);
  assert.equal(document.activeElement, cta);
  assert.deepEqual(telemetry, ["guide_cta_shown", "guide_cta_cancelled"]);
});


test("an unhandled recipe request fails visibly and keeps the dialog open", async () => {
  const { bridge, document, telemetry } = setup();
  await bridge.start();
  document.querySelector(api.CTA_SELECTOR).dispatchEvent(new FakeEvent("click"));
  findButton(document, "Start guide").dispatchEvent(new FakeEvent("click"));
  await flushAsyncListener();

  assert.ok(document.querySelector(api.DIALOG_SELECTOR));
  assert.match(document.querySelector("[role='alert']").textContent, /unavailable/i);
  assert.deepEqual(telemetry, ["guide_cta_shown", "guide_cta_unavailable"]);
});


test("an accepted handoff passes only the allow-listed launch recipe", async () => {
  const requests = [];
  const { bridge, document, telemetry } = setup({
    requestRecipe: async (request) => {
      requests.push(request);
      return true;
    },
  });
  await bridge.start();
  document.querySelector(api.CTA_SELECTOR).dispatchEvent(new FakeEvent("click"));
  findButton(document, "Start guide").dispatchEvent(new FakeEvent("click"));
  await flushAsyncListener();

  assert.deepEqual(requests, [
    { version: 1, recipe: "launch-getting-started", source: "cta" },
  ]);
  assert.equal(document.querySelector(api.DIALOG_SELECTOR), null);
  assert.deepEqual(telemetry, ["guide_cta_shown", "guide_cta_started"]);
});


test("the CTA confirmation runs the complete validated launch recipe", async () => {
  const steps = [];
  const expectedSteps = RECIPES.recipes.find(
    (recipe) => recipe.id === "launch-getting-started",
  ).steps.map((step) => step.id);
  let signalRunCompleted;
  const runCompleted = new Promise((resolve) => {
    signalRunCompleted = resolve;
  });
  const runnerDocument = new FakeDocument();
  const runner = runnerApi.createRecipeRunner({
    document: runnerDocument,
    location: { origin: "http://localhost:3000" },
    uiMap: JSON.parse(JSON.stringify(FULL_UI_MAP)),
    recipeAsset: JSON.parse(JSON.stringify(RECIPES)),
    actions: {
      checkPrecondition: async () => true,
      runStep: async (step) => {
        steps.push(step.id);
        if (steps.length === expectedSteps.length) signalRunCompleted();
      },
      clearHighlights: () => {},
    },
    statusView: {
      start: () => {},
      step: () => {},
      finish: () => {},
      remove: () => {},
    },
    emitTelemetry: () => {},
  });
  const unregister = api.registerRecipeRunner(runner.handleConfirmedRequest);
  const { bridge, document } = setup({
    requestRecipe: api.requestRegisteredRecipe,
  });

  await bridge.start();
  document.querySelector(api.CTA_SELECTOR).dispatchEvent(new FakeEvent("click"));
  findButton(document, "Start guide").dispatchEvent(new FakeEvent("click"));
  await runCompleted;
  await flushAsyncListener();

  assert.deepEqual(steps, expectedSteps);
  assert.equal(document.querySelector(api.DIALOG_SELECTOR), null);

  unregister();
  runner.dispose();
});


test("does not install outside the UI map origin allow-list", async () => {
  const { document } = setup();
  const bridge = api.createGuideBridge({
    document,
    location: { origin: "https://example.com" },
    MutationObserver: FakeMutationObserver,
    CustomEvent: FakeEvent,
    loadUiMap: async () => uiMap(),
    requestRecipe: async () => false,
  });

  assert.equal(await bridge.start(), false);
  assert.equal(document.querySelector(api.CTA_SELECTOR), null);
});


test("the private runner boundary accepts only the exact CTA recipe", async () => {
  const requests = [];
  const unregister = api.registerRecipeRunner(async (request) => {
    requests.push(request);
    return true;
  });

  assert.throws(
    () => api.registerRecipeRunner(async () => true),
    /already registered/,
  );
  assert.equal(
    await api.requestRegisteredRecipe({
      version: 1,
      recipe: "launch-getting-started",
      source: "cta",
    }),
    true,
  );
  assert.equal(
    await api.requestRegisteredRecipe({
      version: 1,
      recipe: "hello-world-demo",
      source: "cta",
    }),
    false,
  );
  assert.deepEqual(requests, [
    { version: 1, recipe: "launch-getting-started", source: "cta" },
  ]);
  assert.ok(Object.isFrozen(requests[0]));

  unregister();
  assert.equal(
    await api.requestRegisteredRecipe({
      version: 1,
      recipe: "launch-getting-started",
      source: "cta",
    }),
    false,
  );
});
