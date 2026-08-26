(function exposeGuideRecipeRunner(globalScope) {
  "use strict";

  const SUPPORTED_ACTIONS = new Set([
    "click",
    "wait_for_target",
    "choose_option",
    "type_fixed_text",
    "wait_for_text",
    "highlight",
  ]);
  const INTERACTIVE_ACTIONS = new Set(["click", "choose_option", "type_fixed_text"]);
  const ACTION_CAPABILITIES = {
    click: "click",
    choose_option: "choose_option",
    type_fixed_text: "type",
    wait_for_text: "wait_for_text",
    highlight: "highlight",
  };
  const ALLOWED_STEP_KEYS = new Set([
    "id",
    "action",
    "target",
    "timeout_ms",
    "value",
    "match",
    "clear_existing",
    "duration_ms",
  ]);
  const CONTRACTS = Object.freeze({
    "launch-getting-started": Object.freeze([
      ["open_new_chat", "click", "new-chat"],
      ["wait_for_model_picker", "wait_for_target", "model-picker"],
      ["open_model_picker", "click", "model-picker"],
      ["select_guide", "choose_option", "model-picker", "Open WebUI Guide"],
      [
        "enter_starter_prompt",
        "type_fixed_text",
        "message-composer",
        "Start the getting started tour",
      ],
      ["submit_starter_prompt", "click", "send-button"],
      ["wait_for_guide_response", "wait_for_target", "assistant-message"],
    ]),
    "hello-world-demo": Object.freeze([
      ["open_model_picker", "click", "model-picker"],
      ["select_hello_world", "choose_option", "model-picker", "hello-world"],
      [
        "enter_test_message",
        "type_fixed_text",
        "message-composer",
        "Test the connection",
      ],
      ["submit_test_message", "click", "send-button"],
      [
        "verify_fixed_response",
        "wait_for_text",
        "assistant-message",
        "Hello, world! The baseline chat connection is working.",
      ],
      ["highlight_result", "highlight", "assistant-message"],
      ["reopen_model_picker", "click", "model-picker"],
      ["restore_guide", "choose_option", "model-picker", "Open WebUI Guide"],
    ]),
  });
  const PRECONDITION_CONTRACTS = Object.freeze({
    "launch-getting-started": Object.freeze([
      ["target_available", "new-chat"],
      ["target_available", "model-picker"],
      ["option_available", "model-picker", "Open WebUI Guide"],
      ["target_available", "message-composer"],
    ]),
    "hello-world-demo": Object.freeze([
      ["selected_option", "model-picker", "Open WebUI Guide"],
      ["option_available", "model-picker", "hello-world"],
      ["target_available", "message-composer"],
    ]),
  });

  class RecipeRunnerError extends Error {
    constructor(category, message) {
      super(message);
      this.name = "RecipeRunnerError";
      this.category = category;
    }
  }

  function createRecipeRunner(options) {
    const document = options.document;
    const location = options.location;
    const uiMap = validateUiMap(options.uiMap);
    const recipes = validateRecipeAsset(options.recipeAsset, uiMap);
    const actions =
      options.actions ||
      createDomRecipeActions({
        document,
        uiMap,
        schedule: options.schedule,
        cancelSchedule: options.cancelSchedule,
      });
    const statusView =
      options.statusView || createStatusView(document, options.schedule);
    const confirmRecipe =
      options.confirmRecipe || ((recipe) => showRecipeConfirmation(document, recipe));
    const emitTelemetry = options.emitTelemetry || (() => {});
    const schedule = options.schedule || globalScope.setTimeout.bind(globalScope);
    const cancelSchedule =
      options.cancelSchedule || globalScope.clearTimeout.bind(globalScope);

    let activeController = null;
    let activePromise = null;

    const cancelOnEscape = (event) => {
      if (event.key !== "Escape" || !activeController) return;
      activeController.abort("user_cancelled");
      actions.clearHighlights();
    };
    document.addEventListener("keydown", cancelOnEscape, true);

    function handleConfirmedRequest(request) {
      if (
        !request ||
        request.version !== 1 ||
        request.source !== "cta" ||
        request.recipe !== "launch-getting-started" ||
        activeController
      ) {
        return false;
      }
      startRecipe(request.recipe);
      return true;
    }

    async function requestWithConfirmation(recipeId) {
      const recipe = recipes.get(recipeId);
      if (!recipe || activeController) {
        return { status: "unavailable", recipe: recipeId };
      }
      const confirmed = await confirmRecipe(recipe);
      if (!confirmed) {
        return { status: "cancelled_before_start", recipe: recipeId };
      }
      return startRecipe(recipeId);
    }

    function startRecipe(recipeId) {
      if (activeController) {
        return Promise.resolve({ status: "busy", recipe: recipeId });
      }
      const recipe = recipes.get(recipeId);
      if (!recipe || !recipe.allowed_origins.includes(location.origin)) {
        return Promise.resolve({ status: "unavailable", recipe: recipeId });
      }

      activePromise = executeRecipe(recipe).finally(() => {
        activePromise = null;
      });
      return activePromise;
    }

    async function executeRecipe(recipe) {
      const controller = new AbortController();
      activeController = controller;
      const totalTimer = schedule(
        () => controller.abort("total_timeout"),
        recipe.limits.total_timeout_ms,
      );
      statusView.start(recipe.title);
      emitTelemetry("guide_recipe_started", recipe.id);

      try {
        for (const precondition of recipe.preconditions) {
          assertNotAborted(controller.signal);
          const available = await actions.checkPrecondition(
            precondition,
            recipe.limits.default_step_timeout_ms,
            controller.signal,
          );
          if (!available) {
            throw new RecipeRunnerError(
              "precondition_failed",
              `Recipe precondition failed: ${precondition.check}`,
            );
          }
        }

        for (const step of recipe.steps) {
          assertNotAborted(controller.signal);
          statusView.step(step.id);
          await actions.runStep(
            step,
            step.timeout_ms || recipe.limits.default_step_timeout_ms,
            controller.signal,
          );
        }

        const message = recipe.on_success?.message || "Guide recipe completed.";
        statusView.finish("completed", message);
        emitTelemetry("guide_recipe_completed", recipe.id);
        return { status: "completed", recipe: recipe.id };
      } catch (error) {
        actions.clearHighlights();
        if (controller.signal.aborted && controller.signal.reason === "user_cancelled") {
          statusView.finish("cancelled", recipe.on_cancel.message);
          emitTelemetry("guide_recipe_cancelled", recipe.id);
          return { status: "cancelled", recipe: recipe.id };
        }

        const category =
          controller.signal.aborted && controller.signal.reason === "total_timeout"
            ? "total_timeout"
            : error instanceof RecipeRunnerError
              ? error.category
              : "unexpected_error";
        statusView.finish("failed", recipe.on_failure.message);
        emitTelemetry("guide_recipe_failed", recipe.id, category);
        return { status: "failed", recipe: recipe.id, category };
      } finally {
        cancelSchedule(totalTimer);
        activeController = null;
      }
    }

    function cancel() {
      if (!activeController) return false;
      activeController.abort("user_cancelled");
      actions.clearHighlights();
      return true;
    }

    function whenIdle() {
      return activePromise || Promise.resolve(null);
    }

    function dispose() {
      cancel();
      document.removeEventListener("keydown", cancelOnEscape, true);
      statusView.remove();
    }

    return Object.freeze({
      cancel,
      dispose,
      handleConfirmedRequest,
      requestWithConfirmation,
      startRecipe,
      whenIdle,
    });
  }

  function validateUiMap(uiMap) {
    if (
      !uiMap ||
      uiMap.schema_version !== 1 ||
      uiMap.target_open_webui_version !== "v0.11.0" ||
      !Array.isArray(uiMap.allowed_origins) ||
      !uiMap.targets
    ) {
      throw new RecipeRunnerError("invalid_ui_map", "Unsupported Guide UI map.");
    }
    return deepFreeze(uiMap);
  }

  function validateRecipeAsset(asset, uiMap) {
    if (
      !asset ||
      asset.schema_version !== 1 ||
      asset.id !== "open_webui_poc_recipe_registry" ||
      !Array.isArray(asset.recipes)
    ) {
      throw new RecipeRunnerError("invalid_recipe_asset", "Unsupported recipe asset.");
    }
    if (asset.recipes.length !== Object.keys(CONTRACTS).length) {
      throw new RecipeRunnerError("invalid_recipe_asset", "Unexpected recipe count.");
    }

    const recipes = new Map();
    for (const recipe of asset.recipes) {
      validateRecipe(recipe, uiMap);
      if (recipes.has(recipe.id)) {
        throw new RecipeRunnerError("invalid_recipe_asset", "Duplicate recipe ID.");
      }
      recipes.set(recipe.id, deepFreeze(recipe));
    }
    for (const recipeId of Object.keys(CONTRACTS)) {
      if (!recipes.has(recipeId)) {
        throw new RecipeRunnerError("invalid_recipe_asset", "Required recipe missing.");
      }
    }
    return recipes;
  }

  function validateRecipe(recipe, uiMap) {
    const contract = CONTRACTS[recipe?.id];
    const preconditionContract = PRECONDITION_CONTRACTS[recipe?.id];
    if (
      !contract ||
      !preconditionContract ||
      recipe.schema_version !== 1 ||
      recipe.requires_confirmation !== true ||
      !Array.isArray(recipe.allowed_origins) ||
      !recipe.allowed_origins.length ||
      recipe.allowed_origins.some((origin) => !uiMap.allowed_origins.includes(origin)) ||
      !recipe.limits ||
      recipe.limits.cancel_key !== "Escape" ||
      !isBoundedInteger(recipe.limits.total_timeout_ms, 1, 60000) ||
      !isBoundedInteger(recipe.limits.default_step_timeout_ms, 1, 15000) ||
      !Array.isArray(recipe.preconditions) ||
      recipe.preconditions.length !== preconditionContract.length ||
      !Array.isArray(recipe.steps) ||
      recipe.steps.length !== contract.length ||
      recipe.on_failure?.action !== "stop" ||
      recipe.on_cancel?.action !== "stop"
    ) {
      throw new RecipeRunnerError("invalid_recipe", `Invalid recipe: ${recipe?.id}`);
    }

    for (const [index, condition] of recipe.preconditions.entries()) {
      validatePrecondition(condition, uiMap);
      const expected = preconditionContract[index];
      if (
        condition.check !== expected[0] ||
        condition.target !== expected[1] ||
        (expected[2] === undefined
          ? condition.value !== undefined
          : condition.value !== expected[2])
      ) {
        throw new RecipeRunnerError("invalid_recipe", "Unexpected precondition.");
      }
    }
    recipe.steps.forEach((step, index) => {
      const expected = contract[index];
      if (
        Object.keys(step).some((key) => !ALLOWED_STEP_KEYS.has(key)) ||
        step.id !== expected[0] ||
        step.action !== expected[1] ||
        step.target !== expected[2] ||
        (expected[3] === undefined ? step.value !== undefined : step.value !== expected[3]) ||
        (step.action === "type_fixed_text" && step.clear_existing !== true) ||
        (["choose_option", "wait_for_text"].includes(step.action) &&
          step.match !== "exact") ||
        !SUPPORTED_ACTIONS.has(step.action) ||
        (step.timeout_ms !== undefined && !isBoundedInteger(step.timeout_ms, 1, 15000)) ||
        (step.duration_ms !== undefined && !isBoundedInteger(step.duration_ms, 1, 10000))
      ) {
        throw new RecipeRunnerError("invalid_recipe", `Invalid recipe step: ${step.id}`);
      }
      validateTargetAction(uiMap, step.target, step.action);
    });
  }

  function validatePrecondition(condition, uiMap) {
    if (
      !condition ||
      !["target_available", "option_available", "selected_option"].includes(
        condition.check,
      ) ||
      !uiMap.targets[condition.target] ||
      (["option_available", "selected_option"].includes(condition.check) &&
        !["Open WebUI Guide", "hello-world"].includes(condition.value))
    ) {
      throw new RecipeRunnerError("invalid_recipe", "Invalid recipe precondition.");
    }
    if (condition.check === "option_available") {
      validateTargetAction(uiMap, condition.target, "click");
    }
  }

  function validateTargetAction(uiMap, targetId, action) {
    const target = uiMap.targets[targetId];
    const capability = ACTION_CAPABILITIES[action];
    if (!target || (capability && !target.capabilities.includes(capability))) {
      throw new RecipeRunnerError("invalid_recipe", "Recipe capability mismatch.");
    }
    if (
      INTERACTIVE_ACTIONS.has(action) &&
      !String(target.verification).startsWith("verified_")
    ) {
      throw new RecipeRunnerError(
        "unverified_interactive_target",
        `Interactive target is not verified: ${targetId}`,
      );
    }
  }

  function createDomRecipeActions(options) {
    const document = options.document;
    const uiMap = options.uiMap;
    const schedule = options.schedule || globalScope.setTimeout.bind(globalScope);
    const cancelSchedule =
      options.cancelSchedule || globalScope.clearTimeout.bind(globalScope);

    async function checkPrecondition(condition, timeoutMs, signal) {
      if (condition.check === "target_available") {
        return Boolean(resolveTarget(condition.target));
      }
      if (condition.check === "selected_option") {
        const picker = resolveTarget(condition.target);
        return Boolean(picker && selectedOption(picker) === condition.value);
      }
      if (condition.check === "option_available") {
        return inspectOption(condition.target, condition.value, timeoutMs, signal);
      }
      return false;
    }

    async function runStep(step, timeoutMs, signal) {
      assertNotAborted(signal);
      switch (step.action) {
        case "click": {
          const target = requireInteractiveTarget(step.target);
          target.click();
          return;
        }
        case "wait_for_target":
          await waitFor(() => resolveTarget(step.target), timeoutMs, signal, schedule, cancelSchedule);
          return;
        case "choose_option":
          await chooseOption(step.value, timeoutMs, signal);
          return;
        case "type_fixed_text":
          typeFixedText(requireInteractiveTarget(step.target), step.value, step.clear_existing);
          return;
        case "wait_for_text":
          await waitFor(
            () => {
              const target = resolveTarget(step.target);
              if (!target) return null;
              return normalizeText(target.textContent) === normalizeText(step.value)
                ? target
                : null;
            },
            timeoutMs,
            signal,
            schedule,
            cancelSchedule,
          );
          return;
        case "highlight": {
          const target = resolveTarget(step.target);
          if (!target) throw new RecipeRunnerError("target_missing", step.target);
          clearHighlights();
          target.classList.add("howto-guide__highlight");
          target.setAttribute("data-howto-guide-highlight", "true");
          target.scrollIntoView({ behavior: "smooth", block: "center" });
          schedule(() => clearHighlights(), step.duration_ms || 5000);
          return;
        }
        default:
          throw new RecipeRunnerError("unsupported_action", step.action);
      }
    }

    function resolveTarget(targetId) {
      const definition = uiMap.targets[targetId];
      if (!definition) return null;
      for (const locator of definition.locators) {
        const matches = resolveLocator(locator).filter(isVisible);
        if (
          definition.resolution?.allow_multiple &&
          definition.resolution?.selection === "last_visible_match" &&
          matches.length
        ) {
          return matches[matches.length - 1];
        }
        if (matches.length === 1) return matches[0];
      }
      return null;
    }

    function resolveLocator(locator) {
      if (locator.kind === "css" || locator.kind === "css_fallback") {
        return Array.from(document.querySelectorAll(locator.selector));
      }
      if (locator.kind !== "role") return [];
      const pattern = compileNamePattern(locator.name_pattern);
      return Array.from(document.querySelectorAll(roleToSelector(locator.role))).filter(
        (element) => pattern.test(accessibleName(document, element)),
      );
    }

    function requireInteractiveTarget(targetId) {
      const target = resolveTarget(targetId);
      if (!target) throw new RecipeRunnerError("target_missing", targetId);
      if (target.disabled || target.getAttribute("aria-disabled") === "true") {
        throw new RecipeRunnerError("target_disabled", targetId);
      }
      return target;
    }

    async function inspectOption(targetId, value, timeoutMs, signal) {
      const picker = requireInteractiveTarget(targetId);
      const alreadyOpen = visibleOptions().length > 0;
      if (!alreadyOpen) picker.click();
      try {
        return Boolean(
          await waitFor(
            () => findExactOption(value),
            timeoutMs,
            signal,
            schedule,
            cancelSchedule,
            true,
          ),
        );
      } finally {
        if (!alreadyOpen) {
          picker.dispatchEvent(
            createKeyboardEvent("keydown", { key: "Escape", bubbles: true }),
          );
        }
      }
    }

    async function chooseOption(value, timeoutMs, signal) {
      const option = await waitFor(
        () => findExactOption(value),
        timeoutMs,
        signal,
        schedule,
        cancelSchedule,
      );
      option.click();
    }

    function findExactOption(value) {
      const matches = visibleOptions().filter(
        (option) => normalizeText(accessibleName(document, option)) === normalizeText(value),
      );
      return matches.length === 1 ? matches[0] : null;
    }

    function visibleOptions() {
      return Array.from(document.querySelectorAll("[role='option']")).filter(isVisible);
    }

    function selectedOption(picker) {
      const label = picker.getAttribute("aria-label") || "";
      const match = label.match(/^Selected model:\s*(.+)$/i);
      return normalizeText(match ? match[1] : picker.textContent);
    }

    function typeFixedText(element, value, clearExisting) {
      element.focus();
      if (element.isContentEditable || element.getAttribute("contenteditable") === "true") {
        if (clearExisting) element.textContent = "";
        const inserted =
          typeof document.execCommand === "function" &&
          document.execCommand("insertText", false, value);
        if (!inserted) {
          element.textContent = value;
          element.dispatchEvent(
            createInputEvent("input", {
              bubbles: true,
              data: value,
              inputType: "insertText",
            }),
          );
        }
      } else if ("value" in element) {
        if (clearExisting) element.value = "";
        element.value = value;
        element.dispatchEvent(
          createInputEvent("input", {
            bubbles: true,
            data: value,
            inputType: "insertText",
          }),
        );
      } else {
        throw new RecipeRunnerError("target_not_editable", "message-composer");
      }
      const current = element.isContentEditable
        ? element.textContent
        : "value" in element
          ? element.value
          : "";
      if (normalizeText(current) !== normalizeText(value)) {
        throw new RecipeRunnerError("type_failed", "Fixed text was not applied.");
      }
    }

    function clearHighlights() {
      for (const element of document.querySelectorAll("[data-howto-guide-highlight='true']")) {
        element.classList.remove("howto-guide__highlight");
        element.removeAttribute("data-howto-guide-highlight");
      }
    }

    return Object.freeze({ checkPrecondition, clearHighlights, resolveTarget, runStep });
  }

  function createStatusView(document, schedule = globalScope.setTimeout.bind(globalScope)) {
    let element = null;
    let title = "";
    function ensure() {
      if (element) return element;
      element = document.createElement("div");
      element.className = "howto-guide__runner-status";
      element.dataset.howtoGuideRunnerStatus = "true";
      element.setAttribute("role", "status");
      element.setAttribute("aria-live", "polite");
      document.body.appendChild(element);
      return element;
    }
    return Object.freeze({
      start(recipeTitle) {
        title = recipeTitle;
        ensure().textContent = `${title} is running. Press Escape to stop.`;
      },
      step(stepId) {
        ensure().textContent = `${title} is running: ${stepId}. Press Escape to stop.`;
      },
      finish(status, message) {
        const statusElement = ensure();
        statusElement.dataset.status = status;
        statusElement.textContent = message;
        schedule(() => {
          statusElement.remove();
          if (element === statusElement) element = null;
        }, 5000);
      },
      remove() {
        element?.remove();
        element = null;
      },
    });
  }

  function showRecipeConfirmation(document, recipe) {
    return new Promise((resolve) => {
      const dialog = document.createElement("dialog");
      dialog.className = "howto-guide__dialog";
      dialog.dataset.howtoGuideRecipeConfirmation = "true";
      dialog.setAttribute("aria-modal", "true");

      const title = document.createElement("h2");
      title.className = "howto-guide__dialog-title";
      title.textContent = recipe.confirmation.title;
      const body = document.createElement("p");
      body.textContent = recipe.confirmation.body;
      const actions = document.createElement("div");
      actions.className = "howto-guide__dialog-actions";
      const cancel = document.createElement("button");
      cancel.type = "button";
      cancel.className = "howto-guide__button howto-guide__button--secondary";
      cancel.textContent = recipe.confirmation.cancel_label;
      const confirm = document.createElement("button");
      confirm.type = "button";
      confirm.className = "howto-guide__button howto-guide__button--primary";
      confirm.textContent = recipe.confirmation.confirm_label;

      let settled = false;
      const finish = (value) => {
        if (settled) return;
        settled = true;
        dialog.remove();
        resolve(value);
      };
      cancel.addEventListener("click", () => finish(false));
      confirm.addEventListener("click", () => finish(true));
      dialog.addEventListener("cancel", (event) => {
        event.preventDefault();
        finish(false);
      });
      actions.appendChild(cancel);
      actions.appendChild(confirm);
      dialog.appendChild(title);
      dialog.appendChild(body);
      dialog.appendChild(actions);
      document.body.appendChild(dialog);
      if (typeof dialog.showModal === "function") dialog.showModal();
      else dialog.setAttribute("open", "");
      cancel.focus();
    });
  }

  async function waitFor(
    check,
    timeoutMs,
    signal,
    schedule,
    cancelSchedule,
    returnNullOnTimeout = false,
  ) {
    const deadline = Date.now() + timeoutMs;
    while (Date.now() <= deadline) {
      assertNotAborted(signal);
      const result = check();
      if (result) return result;
      await abortableDelay(50, signal, schedule, cancelSchedule);
    }
    if (returnNullOnTimeout) return null;
    throw new RecipeRunnerError("step_timeout", "Recipe step timed out.");
  }

  function abortableDelay(milliseconds, signal, schedule, cancelSchedule) {
    return new Promise((resolve, reject) => {
      if (signal.aborted) {
        reject(new RecipeRunnerError("cancelled", "Recipe was cancelled."));
        return;
      }
      const timer = schedule(() => {
        signal.removeEventListener("abort", onAbort);
        resolve();
      }, milliseconds);
      const onAbort = () => {
        cancelSchedule(timer);
        reject(new RecipeRunnerError("cancelled", "Recipe was cancelled."));
      };
      signal.addEventListener("abort", onAbort, { once: true });
    });
  }

  function assertNotAborted(signal) {
    if (signal.aborted) {
      throw new RecipeRunnerError("cancelled", "Recipe was cancelled.");
    }
  }

  function roleToSelector(role) {
    const nativeRoles = {
      button: "button,[role='button']",
      link: "a[href],[role='link']",
      navigation: "nav,[role='navigation']",
      textbox: "textarea,input[type='text'],[role='textbox']",
    };
    return nativeRoles[role] || `[role='${String(role).replace(/['\\]/g, "\\$&")}']`;
  }

  function compileNamePattern(source) {
    const ignoreCase = source.startsWith("(?i)");
    return new RegExp(ignoreCase ? source.slice(4) : source, ignoreCase ? "i" : "");
  }

  function accessibleName(document, element) {
    const labelledBy = element.getAttribute("aria-labelledby");
    const labelledText = labelledBy
      ? labelledBy
          .split(/\s+/)
          .map((id) => document.getElementById(id)?.textContent || "")
          .join(" ")
          .trim()
      : "";
    return (
      labelledText ||
      element.getAttribute("aria-label") ||
      element.getAttribute("title") ||
      element.textContent ||
      ""
    );
  }

  function isVisible(element) {
    return (
      !element.hidden &&
      element.getAttribute("aria-hidden") !== "true" &&
      (typeof element.getClientRects !== "function" || element.getClientRects().length > 0)
    );
  }

  function normalizeText(value) {
    return String(value || "").replace(/\s+/g, " ").trim();
  }

  function isBoundedInteger(value, minimum, maximum) {
    return Number.isInteger(value) && value >= minimum && value <= maximum;
  }

  function createInputEvent(type, options) {
    const EventType = globalScope.InputEvent || globalScope.Event;
    return new EventType(type, options);
  }

  function createKeyboardEvent(type, options) {
    const EventType = globalScope.KeyboardEvent || globalScope.Event;
    const event = new EventType(type, options);
    if (!("key" in event)) {
      Object.defineProperty(event, "key", { value: options.key });
    }
    return event;
  }

  function deepFreeze(value) {
    if (!value || typeof value !== "object" || Object.isFrozen(value)) return value;
    Object.freeze(value);
    for (const nested of Object.values(value)) deepFreeze(nested);
    return value;
  }

  globalScope.HowToGuideRecipeRunner = Object.freeze({
    RecipeRunnerError,
    createDomRecipeActions,
    createRecipeRunner,
    validateRecipeAsset,
  });
})(globalThis);
