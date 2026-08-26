(function exposeGuideDirectiveRenderer(globalScope) {
  "use strict";

  const CODE_SELECTOR = [
    ".chat-assistant pre code.language-owui-action",
    ".chat-assistant pre code[data-language='owui-action']",
    ".chat-assistant pre code[data-lang='owui-action']",
  ].join(",");
  const SAFE_ID_PATTERN = /^[a-z0-9]+(?:-[a-z0-9]+)*$/;
  const MESSAGE_RECIPE_IDS = new Set(["hello-world-demo"]);
  const DIRECTIVE_KEYS = new Set([
    "version",
    "kind",
    "target",
    "recipe",
    "requires_confirmation",
  ]);

  class DirectiveError extends Error {
    constructor(category, message) {
      super(message);
      this.name = "DirectiveError";
      this.category = category;
    }
  }

  function createDirectiveRenderer(options) {
    const document = options.document;
    const location = options.location;
    const MutationObserver = options.MutationObserver;
    const uiMap = validateUiMap(options.uiMap);
    const recipes = validateRecipes(options.recipeAsset);
    const recipeRuntime = options.recipeRuntime;
    if (typeof recipeRuntime?.requestWithConfirmation !== "function") {
      throw new DirectiveError("missing_recipe_runtime", "Recipe runtime is unavailable.");
    }
    const emitTelemetry = options.emitTelemetry || (() => {});
    const schedule = options.schedule || globalScope.setTimeout.bind(globalScope);
    const cancelSchedule =
      options.cancelSchedule || globalScope.clearTimeout.bind(globalScope);

    let observer = null;
    let highlightTimer = null;
    let stopped = false;
    const attemptedText = new WeakMap();

    function start() {
      if (!uiMap.allowed_origins.includes(location.origin)) return false;
      scan();
      observer = new MutationObserver(scan);
      observer.observe(document.body, {
        childList: true,
        subtree: true,
        characterData: true,
      });
      document.addEventListener("keydown", clearOnEscape, true);
      return true;
    }

    function stop() {
      stopped = true;
      observer?.disconnect();
      observer = null;
      document.removeEventListener("keydown", clearOnEscape, true);
      clearHighlight();
    }

    function scan() {
      if (stopped) return;
      for (const code of document.querySelectorAll(CODE_SELECTOR)) {
        if (code.dataset.howtoDirectiveProcessed === "true") continue;
        const text = code.textContent;
        if (attemptedText.get(code) === text) continue;
        attemptedText.set(code, text);
        try {
          const directive = parseDirective(text, uiMap, recipes);
          renderControl(code, directive);
          code.dataset.howtoDirectiveProcessed = "true";
          delete code.dataset.howtoDirectiveInvalid;
          emitTelemetry("guide_directive_shown");
        } catch (error) {
          code.dataset.howtoDirectiveInvalid = "true";
          const category =
            error instanceof DirectiveError ? error.category : "unexpected_error";
          console.warn(`Open WebUI Guide directive remained inert (${category}).`);
        }
      }
    }

    function renderControl(code, directive) {
      const rawBlock = code.closest("pre");
      if (!rawBlock?.parentNode) {
        throw new DirectiveError("missing_transport_container", "Directive has no pre.");
      }

      const container = document.createElement("div");
      container.className = "howto-guide__directive";
      container.dataset.howtoGuideDirective = "true";
      container.dataset.kind = directive.kind;

      const button = document.createElement("button");
      button.type = "button";
      button.className = "howto-guide__button howto-guide__button--directive";
      button.textContent = directive.kind === "highlight" ? "Show me" : "Run example";

      const status = document.createElement("span");
      status.className = "howto-guide__directive-status";
      status.setAttribute("role", "status");
      status.setAttribute("aria-live", "polite");

      if (directive.kind === "highlight") {
        button.addEventListener("click", () => {
          try {
            highlightTarget(directive.target);
            status.textContent = `Highlighted: ${uiMap.targets[directive.target].description}`;
          } catch (_error) {
            status.textContent = "That Open WebUI control is not available on this page.";
          }
        });
      } else {
        button.addEventListener("click", async () => {
          button.disabled = true;
          status.textContent = "";
          try {
            const outcome = await recipeRuntime.requestWithConfirmation(
              directive.recipe,
            );
            status.textContent = outcomeMessage(outcome);
          } catch (_error) {
            status.textContent = "The example could not be started safely.";
          } finally {
            button.disabled = false;
          }
        });
      }

      container.appendChild(button);
      container.appendChild(status);
      rawBlock.hidden = true;
      rawBlock.setAttribute("aria-hidden", "true");
      rawBlock.insertAdjacentElement("afterend", container);
    }

    function highlightTarget(targetId) {
      const target = resolveTarget(document, uiMap, targetId);
      if (!target) {
        throw new DirectiveError("target_unavailable", "Target is unavailable.");
      }
      clearHighlight();
      target.classList.add("howto-guide__highlight");
      target.setAttribute("data-howto-guide-highlight", "true");
      target.scrollIntoView({ behavior: "smooth", block: "center" });
      highlightTimer = schedule(clearHighlight, 5000);
      return target;
    }

    function clearHighlight() {
      if (highlightTimer !== null) {
        cancelSchedule(highlightTimer);
        highlightTimer = null;
      }
      for (const target of document.querySelectorAll(
        "[data-howto-guide-highlight='true']",
      )) {
        target.classList.remove("howto-guide__highlight");
        target.removeAttribute("data-howto-guide-highlight");
      }
    }

    function clearOnEscape(event) {
      if (event.key === "Escape") clearHighlight();
    }

    return Object.freeze({ clearHighlight, scan, start, stop });
  }

  function parseDirective(text, uiMap, recipes) {
    if (typeof text !== "string" || text.length > 2048) {
      throw new DirectiveError("invalid_transport", "Directive text is invalid.");
    }
    let directive;
    try {
      directive = JSON.parse(text);
    } catch (_error) {
      throw new DirectiveError("invalid_json", "Directive JSON is invalid.");
    }
    if (
      !directive ||
      Array.isArray(directive) ||
      typeof directive !== "object" ||
      Object.keys(directive).some((key) => !DIRECTIVE_KEYS.has(key)) ||
      directive.version !== 1
    ) {
      throw new DirectiveError("invalid_contract", "Directive contract is invalid.");
    }

    if (directive.kind === "highlight") {
      if (
        directive.requires_confirmation !== false ||
        !SAFE_ID_PATTERN.test(directive.target || "") ||
        directive.recipe !== undefined ||
        !uiMap.targets[directive.target]?.capabilities.includes("highlight")
      ) {
        throw new DirectiveError("invalid_highlight", "Highlight is invalid.");
      }
    } else if (directive.kind === "run_recipe") {
      if (
        directive.requires_confirmation !== true ||
        !SAFE_ID_PATTERN.test(directive.recipe || "") ||
        directive.target !== undefined ||
        !MESSAGE_RECIPE_IDS.has(directive.recipe) ||
        !recipes.has(directive.recipe)
      ) {
        throw new DirectiveError("invalid_recipe", "Recipe directive is invalid.");
      }
    } else {
      throw new DirectiveError("unsupported_kind", "Directive kind is unsupported.");
    }
    return Object.freeze({ ...directive });
  }

  function validateUiMap(uiMap) {
    if (
      !uiMap ||
      uiMap.schema_version !== 1 ||
      uiMap.target_open_webui_version !== "v0.11.0" ||
      !Array.isArray(uiMap.allowed_origins) ||
      !uiMap.targets
    ) {
      throw new DirectiveError("invalid_ui_map", "Unsupported UI map.");
    }
    return uiMap;
  }

  function validateRecipes(asset) {
    const allowedRecipeIds = new Set(["hello-world-demo", "launch-getting-started"]);
    if (
      !asset ||
      asset.schema_version !== 1 ||
      asset.id !== "open_webui_poc_recipe_registry" ||
      !Array.isArray(asset.recipes) ||
      asset.recipes.length !== allowedRecipeIds.size
    ) {
      throw new DirectiveError("invalid_recipe_asset", "Unsupported recipes.");
    }
    const recipes = new Map();
    for (const recipe of asset.recipes) {
      if (
        !recipe ||
        !SAFE_ID_PATTERN.test(recipe.id || "") ||
        !allowedRecipeIds.has(recipe.id) ||
        recipes.has(recipe.id) ||
        recipe.requires_confirmation !== true
      ) {
        throw new DirectiveError("invalid_recipe_asset", "Invalid recipe entry.");
      }
      recipes.set(recipe.id, recipe);
    }
    if ([...allowedRecipeIds].some((recipeId) => !recipes.has(recipeId))) {
      throw new DirectiveError("invalid_recipe_asset", "Required recipe is missing.");
    }
    return recipes;
  }

  function resolveTarget(document, uiMap, targetId) {
    const definition = uiMap.targets[targetId];
    if (!definition) return null;
    for (const locator of definition.locators) {
      const matches = resolveLocator(document, locator).filter(isVisible);
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

  function resolveLocator(document, locator) {
    if (locator.kind === "css" || locator.kind === "css_fallback") {
      return Array.from(document.querySelectorAll(locator.selector));
    }
    if (locator.kind !== "role") return [];
    const pattern = compileNamePattern(locator.name_pattern);
    return Array.from(document.querySelectorAll(roleToSelector(locator.role))).filter(
      (element) => pattern.test(accessibleName(document, element)),
    );
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

  function outcomeMessage(outcome) {
    const messages = {
      completed: "The example completed.",
      cancelled: "The example was stopped.",
      cancelled_before_start: "The example was cancelled before it started.",
      failed: "The example stopped safely before any later action.",
      busy: "Another guide action is already running.",
      unavailable: "The example is not available on this page.",
    };
    return messages[outcome?.status] || "The example could not be started safely.";
  }

  globalScope.HowToGuideDirectiveRenderer = Object.freeze({
    CODE_SELECTOR,
    DirectiveError,
    createDirectiveRenderer,
    parseDirective,
  });
})(globalThis);
