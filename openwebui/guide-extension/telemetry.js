(function exposeGuideTelemetry(globalScope) {
  "use strict";

  const EVENT_NAMES = new Set([
    "guide_cta_shown",
    "guide_cta_started",
    "guide_cta_cancelled",
    "guide_cta_unavailable",
    "guide_directive_shown",
    "guide_recipe_started",
    "guide_recipe_completed",
    "guide_recipe_cancelled",
    "guide_recipe_failed",
  ]);
  const RECIPE_EVENTS = new Set([
    "guide_recipe_started",
    "guide_recipe_completed",
    "guide_recipe_cancelled",
    "guide_recipe_failed",
  ]);
  const RECIPE_IDS = new Set(["launch-getting-started", "hello-world-demo"]);
  const FAILURE_CATEGORIES = new Set([
    "precondition_failed",
    "target_missing",
    "target_disabled",
    "target_not_editable",
    "type_failed",
    "step_timeout",
    "total_timeout",
    "unsupported_action",
    "unexpected_error",
  ]);
  const SAFE_STEP_PATTERN = /^[a-z0-9]+(?:_[a-z0-9]+)*$/;

  function createTelemetryEmitter(options) {
    const scope = options.scope || globalScope;
    const CustomEvent = options.CustomEvent || globalScope.CustomEvent;
    const eventName = options.eventName;
    if (
      !scope ||
      typeof scope.dispatchEvent !== "function" ||
      typeof CustomEvent !== "function" ||
      typeof eventName !== "string" ||
      !eventName
    ) {
      throw new TypeError("Guide telemetry requires a local event boundary.");
    }

    return function emitTelemetry(name, fields = {}) {
      const detail = validateEvent(name, fields);
      scope.dispatchEvent(new CustomEvent(eventName, { detail }));
      return detail;
    };
  }

  function validateEvent(name, fields = {}) {
    if (!EVENT_NAMES.has(name) || !isPlainObject(fields)) {
      throw new TypeError("Unsupported Guide telemetry event.");
    }
    const allowedKeys = new Set();
    if (RECIPE_EVENTS.has(name)) allowedKeys.add("recipe");
    if (name === "guide_recipe_failed") {
      allowedKeys.add("category");
      allowedKeys.add("step");
    }
    if (Object.keys(fields).some((key) => !allowedKeys.has(key))) {
      throw new TypeError("Guide telemetry contains unsupported fields.");
    }
    if (RECIPE_EVENTS.has(name) && !RECIPE_IDS.has(fields.recipe)) {
      throw new TypeError("Guide telemetry contains an unsupported recipe.");
    }
    if (
      name === "guide_recipe_failed" &&
      !FAILURE_CATEGORIES.has(fields.category)
    ) {
      throw new TypeError("Guide telemetry contains an unsupported failure category.");
    }
    if (
      fields.step !== undefined &&
      !SAFE_STEP_PATTERN.test(fields.step)
    ) {
      throw new TypeError("Guide telemetry contains an unsafe step ID.");
    }
    return Object.freeze({ name, version: 1, ...fields });
  }

  function isPlainObject(value) {
    return Boolean(
      value &&
        typeof value === "object" &&
        !Array.isArray(value) &&
        Object.getPrototypeOf(value) === Object.prototype,
    );
  }

  globalScope.HowToGuideTelemetry = Object.freeze({
    createTelemetryEmitter,
    validateEvent,
  });
})(globalThis);
