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
await import(pathToFileURL(path.join(EXTENSION_DIRECTORY, "directive-renderer.js")));

const api = globalThis.HowToGuideDirectiveRenderer;
const UI_MAP = JSON.parse(
  readFileSync(path.join(EXTENSION_DIRECTORY, "ui-map.json"), "utf8"),
);
const RECIPES = JSON.parse(
  readFileSync(path.join(EXTENSION_DIRECTORY, "recipes.json"), "utf8"),
);


class FakeClassList {
  constructor(element) {
    this.element = element;
  }
  values() {
    return new Set(this.element.className.split(/\s+/).filter(Boolean));
  }
  add(value) {
    const values = this.values();
    values.add(value);
    this.element.className = [...values].join(" ");
  }
  remove(value) {
    const values = this.values();
    values.delete(value);
    this.element.className = [...values].join(" ");
  }
  contains(value) {
    return this.values().has(value);
  }
}


class FakeElement {
  constructor(tagName, document) {
    this.tagName = tagName.toUpperCase();
    this.ownerDocument = document;
    this.children = [];
    this.parentNode = null;
    this.attributes = new Map();
    this.dataset = {};
    this.className = "";
    this.classList = new FakeClassList(this);
    this.textContent = "";
    this.hidden = false;
    this.disabled = false;
    this.listeners = new Map();
  }
  appendChild(child) {
    child.parentNode = this;
    this.children.push(child);
    return child;
  }
  insertAdjacentElement(position, element) {
    assert.equal(position, "afterend");
    const siblings = this.parentNode.children;
    const index = siblings.indexOf(this);
    element.parentNode = this.parentNode;
    siblings.splice(index + 1, 0, element);
    return element;
  }
  closest(selector) {
    let current = this;
    while (current) {
      if (matchesSelector(current, selector)) return current;
      current = current.parentNode;
    }
    return null;
  }
  setAttribute(name, value) {
    this.attributes.set(name, String(value));
  }
  getAttribute(name) {
    return this.attributes.get(name) ?? null;
  }
  removeAttribute(name) {
    this.attributes.delete(name);
  }
  remove() {
    if (!this.parentNode) return;
    this.parentNode.children = this.parentNode.children.filter(
      (child) => child !== this,
    );
    this.parentNode = null;
  }
  getBoundingClientRect() {
    return { left: 20, top: 30, width: 160, height: 32 };
  }
  getClientRects() {
    return this.hidden ? [] : [{}];
  }
  scrollIntoView() {
    this.scrolled = true;
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
  querySelectorAll(selector) {
    const matches = [];
    for (const child of this.children) {
      if (selector.split(",").some((part) => matchesSelector(child, part.trim()))) {
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
    this.body = new FakeElement("body", this);
  }
  createElement(tagName) {
    return new FakeElement(tagName, this);
  }
  querySelectorAll(selector) {
    return this.body.querySelectorAll(selector);
  }
  getElementById() {
    return null;
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
    for (const listener of this.listeners.get("keydown") || []) {
      listener({ key });
    }
  }
}


class FakeMutationObserver {
  static instances = [];
  constructor(callback) {
    this.callback = callback;
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
  if (selector === "pre") return element.tagName === "PRE";
  if (selector === "button") return element.tagName === "BUTTON";
  if (selector === ".chat-assistant pre code.language-owui-action") {
    return (
      element.tagName === "CODE" &&
      element.classList.contains("language-owui-action") &&
      element.closest("pre") !== null &&
      element.closest(".chat-assistant") !== null
    );
  }
  if (selector === ".chat-assistant pre code[data-language='owui-action']") {
    return (
      element.tagName === "CODE" &&
      element.getAttribute("data-language") === "owui-action" &&
      element.closest("pre") !== null &&
      element.closest(".chat-assistant") !== null
    );
  }
  if (selector === ".chat-assistant pre code[data-lang='owui-action']") {
    return (
      element.tagName === "CODE" &&
      element.getAttribute("data-lang") === "owui-action" &&
      element.closest("pre") !== null &&
      element.closest(".chat-assistant") !== null
    );
  }
  if (selector === ".chat-assistant .language-owui-action .cm-content") {
    return (
      element.classList.contains("cm-content") &&
      element.closest(".language-owui-action") !== null &&
      element.closest(".chat-assistant") !== null
    );
  }
  if (selector === "button[aria-haspopup='listbox']") {
    return (
      element.tagName === "BUTTON" &&
      element.getAttribute("aria-haspopup") === "listbox"
    );
  }
  if (selector === "[data-howto-guide-highlight='true']") {
    return element.getAttribute("data-howto-guide-highlight") === "true";
  }
  if (selector === "[data-howto-guide-highlight-overlay='true']") {
    return element.dataset.howtoGuideHighlightOverlay === "true";
  }
  if (selector.startsWith(".")) {
    return element.classList.contains(selector.slice(1));
  }
  return false;
}


function addDirective(document, payload) {
  const wrapper = document.createElement("div");
  wrapper.className = "chat-assistant";
  const pre = document.createElement("pre");
  const code = document.createElement("code");
  code.className = "language-owui-action";
  code.textContent = payload;
  pre.appendChild(code);
  wrapper.appendChild(pre);
  document.body.appendChild(wrapper);
  return { code, pre, wrapper };
}


function addUserDirective(document, payload) {
  const directive = addDirective(document, payload);
  directive.wrapper.className = "chat-user";
  return directive;
}


function addCodeMirrorDirective(document, payload, messageClass = "chat-assistant") {
  const wrapper = document.createElement("div");
  wrapper.className = messageClass;
  const component = document.createElement("div");
  component.className = "relative flex flex-col";
  const languageBlock = document.createElement("div");
  languageBlock.className = "language-owui-action";
  const editor = document.createElement("div");
  editor.className = "cm-editor";
  const content = document.createElement("div");
  content.className = "cm-content";
  content.setAttribute("role", "textbox");
  content.textContent = payload;
  editor.appendChild(content);
  languageBlock.appendChild(editor);
  component.appendChild(languageBlock);
  wrapper.appendChild(component);
  document.body.appendChild(wrapper);
  return { component, content, languageBlock, wrapper };
}


function setup() {
  FakeMutationObserver.instances = [];
  const document = new FakeDocument();
  const picker = document.createElement("button");
  picker.setAttribute("aria-haspopup", "listbox");
  picker.setAttribute("aria-label", "Selected model: Open WebUI Guide");
  document.body.appendChild(picker);
  const recipeRequests = [];
  const renderer = api.createDirectiveRenderer({
    document,
    location: { origin: "http://localhost:3000" },
    MutationObserver: FakeMutationObserver,
    uiMap: JSON.parse(JSON.stringify(UI_MAP)),
    recipeAsset: JSON.parse(JSON.stringify(RECIPES)),
    recipeRuntime: {
      requestWithConfirmation: async (recipe) => {
        recipeRequests.push(recipe);
        return { status: "completed", recipe };
      },
    },
    schedule: () => 1,
    cancelSchedule: () => {},
  });
  return { document, picker, recipeRequests, renderer };
}


function findButton(document, label) {
  return document
    .querySelectorAll("button")
    .find((button) => button.textContent === label);
}


async function flushAsyncListener() {
  await new Promise((resolve) => setTimeout(resolve, 0));
}


test("accepts only exact versioned highlight and message-recipe contracts", () => {
  const uiMap = JSON.parse(JSON.stringify(UI_MAP));
  const recipes = new Map(RECIPES.recipes.map((recipe) => [recipe.id, recipe]));

  assert.deepEqual(
    api.parseDirective(
      '{"version":1,"kind":"highlight","requires_confirmation":false,"target":"model-picker"}',
      uiMap,
      recipes,
    ),
    {
      version: 1,
      kind: "highlight",
      requires_confirmation: false,
      target: "model-picker",
    },
  );
  assert.throws(
    () =>
      api.parseDirective(
        '{"version":1,"kind":"highlight","requires_confirmation":false,"target":"unknown"}',
        uiMap,
        recipes,
      ),
    /Highlight is invalid/,
  );
  assert.throws(
    () =>
      api.parseDirective(
        '{"version":1,"kind":"run_recipe","requires_confirmation":true,"recipe":"launch-getting-started"}',
        uiMap,
        recipes,
      ),
    /Recipe directive is invalid/,
  );
  assert.throws(
    () =>
      api.parseDirective(
        '{"version":1,"kind":"highlight","requires_confirmation":false,"target":"model-picker","selector":"body"}',
        uiMap,
        recipes,
      ),
    /contract is invalid/,
  );
});


test("replaces a valid block once and Show me highlights the semantic target", () => {
  const { document, picker, renderer } = setup();
  const { pre } = addDirective(
    document,
    '{"version":1,"kind":"highlight","requires_confirmation":false,"target":"model-picker"}',
  );

  assert.equal(renderer.start(), true);
  for (const observer of FakeMutationObserver.instances) observer.trigger();
  findButton(document, "Show me").dispatchEvent({ type: "click" });

  assert.equal(pre.hidden, true);
  assert.equal(document.querySelectorAll(".howto-guide__directive").length, 1);
  assert.equal(picker.classList.contains("howto-guide__highlight"), true);
  assert.equal(picker.scrolled, true);
  assert.equal(
    document.querySelectorAll("[data-howto-guide-highlight-overlay='true']").length,
    1,
  );
  assert.match(
    document.querySelectorAll(".howto-guide__directive-status")[0].textContent,
    /Highlighted:/,
  );

  document.dispatchKey("Escape");
  assert.equal(picker.classList.contains("howto-guide__highlight"), false);
  assert.equal(
    document.querySelectorAll("[data-howto-guide-highlight-overlay='true']").length,
    0,
  );
  renderer.stop();
});


test("replaces the CodeMirror transport emitted by Open WebUI v0.11", () => {
  const { document, picker, renderer } = setup();
  const { component, content } = addCodeMirrorDirective(
    document,
    '{"version":1,"kind":"highlight","requires_confirmation":false,"target":"model-picker"}',
  );

  assert.equal(renderer.start(), true);
  findButton(document, "Show me").dispatchEvent({ type: "click" });

  assert.equal(component.hidden, true);
  assert.equal(content.dataset.howtoDirectiveProcessed, "true");
  assert.equal(document.querySelectorAll(".howto-guide__directive").length, 1);
  assert.equal(picker.classList.contains("howto-guide__highlight"), true);
  renderer.stop();
});


test("malformed and unknown blocks remain visible and inert", () => {
  const { document, renderer } = setup();
  const malformed = addDirective(document, "not json");
  const unsupported = addDirective(
    document,
    '{"version":1,"kind":"inspect","requires_confirmation":false,"target":"model-picker"}',
  );

  renderer.start();

  assert.equal(malformed.pre.hidden, false);
  assert.equal(unsupported.pre.hidden, false);
  assert.equal(malformed.code.dataset.howtoDirectiveInvalid, "true");
  assert.equal(unsupported.code.dataset.howtoDirectiveInvalid, "true");
  assert.equal(document.querySelectorAll(".howto-guide__directive").length, 0);
  renderer.stop();
});


test("valid-looking directives in user messages remain inert", () => {
  const { document, renderer } = setup();
  const userDirective = addUserDirective(
    document,
    '{"version":1,"kind":"run_recipe","requires_confirmation":true,"recipe":"hello-world-demo"}',
  );

  renderer.start();

  assert.equal(userDirective.pre.hidden, false);
  assert.equal(document.querySelectorAll(".howto-guide__directive").length, 0);
  renderer.stop();
});


test("valid-looking CodeMirror directives in user messages remain inert", () => {
  const { document, renderer } = setup();
  const userDirective = addCodeMirrorDirective(
    document,
    '{"version":1,"kind":"highlight","requires_confirmation":false,"target":"model-picker"}',
    "chat-user",
  );

  renderer.start();

  assert.equal(userDirective.component.hidden, false);
  assert.equal(document.querySelectorAll(".howto-guide__directive").length, 0);
  renderer.stop();
});


test("a partial streamed directive is retried only after its text changes", () => {
  const { document, renderer } = setup();
  const streamed = addDirective(document, '{"version":1');
  renderer.start();
  assert.equal(streamed.pre.hidden, false);
  assert.equal(streamed.code.dataset.howtoDirectiveInvalid, "true");

  for (const observer of FakeMutationObserver.instances) observer.trigger();
  assert.equal(document.querySelectorAll(".howto-guide__directive").length, 0);

  streamed.code.textContent =
    '{"version":1,"kind":"highlight","requires_confirmation":false,"target":"model-picker"}';
  for (const observer of FakeMutationObserver.instances) observer.trigger();

  assert.equal(streamed.pre.hidden, true);
  assert.equal(streamed.code.dataset.howtoDirectiveProcessed, "true");
  assert.equal(streamed.code.dataset.howtoDirectiveInvalid, undefined);
  assert.equal(document.querySelectorAll(".howto-guide__directive").length, 1);
  renderer.stop();
});


test("Run example delegates only hello-world-demo to runner confirmation", async () => {
  const { document, recipeRequests, renderer } = setup();
  addDirective(
    document,
    '{"version":1,"kind":"run_recipe","requires_confirmation":true,"recipe":"hello-world-demo"}',
  );
  renderer.start();

  findButton(document, "Run example").dispatchEvent({ type: "click" });
  await flushAsyncListener();

  assert.deepEqual(recipeRequests, ["hello-world-demo"]);
  assert.match(
    document.querySelectorAll(".howto-guide__directive-status")[0].textContent,
    /completed/i,
  );
  renderer.stop();
});


test("an ambiguous semantic target produces an inert user-visible error", () => {
  const { document, renderer } = setup();
  const secondPicker = document.createElement("button");
  secondPicker.setAttribute("aria-haspopup", "listbox");
  secondPicker.setAttribute("aria-label", "Selected model: hello-world");
  document.body.appendChild(secondPicker);
  addDirective(
    document,
    '{"version":1,"kind":"highlight","requires_confirmation":false,"target":"model-picker"}',
  );
  renderer.start();

  findButton(document, "Show me").dispatchEvent({ type: "click" });

  assert.match(
    document.querySelectorAll(".howto-guide__directive-status")[0].textContent,
    /not available/,
  );
  assert.equal(
    document.querySelectorAll("[data-howto-guide-highlight='true']").length,
    0,
  );
  renderer.stop();
});
