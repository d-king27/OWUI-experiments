(function exposeGuideBridge(globalScope) {
  "use strict";

  const CTA_SELECTOR = "[data-howto-guide-cta='true']";
  const DIALOG_SELECTOR = "[data-howto-guide-dialog='true']";
  const TELEMETRY_EVENT = "howto-guide:telemetry";
  const LAUNCH_RECIPE_ID = "launch-getting-started";
  let recipeRequestHandler = null;

  function createGuideBridge(options) {
    const document = options.document;
    const location = options.location;
    const MutationObserver = options.MutationObserver;
    const CustomEvent = options.CustomEvent;
    const loadUiMap = options.loadUiMap;
    const requestRecipe = options.requestRecipe;
    const emitTelemetry = options.emitTelemetry || (() => {});

    let observer = null;
    let uiMap = null;
    let stopped = false;
    let ctaWasShown = false;

    async function start() {
      uiMap = await loadUiMap();
      validateUiMap(uiMap);
      if (!uiMap.allowed_origins.includes(location.origin)) {
        return false;
      }

      ensureGettingStartedCta();
      observer = new MutationObserver(ensureGettingStartedCta);
      observer.observe(document.documentElement, {
        childList: true,
        subtree: true,
      });
      return true;
    }

    function stop() {
      stopped = true;
      observer?.disconnect();
      observer = null;
      document.querySelector(CTA_SELECTOR)?.remove();
      closeConfirmation();
    }

    function ensureGettingStartedCta() {
      if (stopped || document.querySelector(CTA_SELECTOR)) {
        return;
      }

      const host = resolveTarget("navigation-actions");
      if (!host) {
        return;
      }

      const button = document.createElement("button");
      button.type = "button";
      button.className = "howto-guide__cta";
      button.dataset.howtoGuideCta = "true";
      button.setAttribute("aria-haspopup", "dialog");
      button.textContent = "Getting started";
      button.addEventListener("click", showGettingStartedConfirmation);
      host.appendChild(button);

      if (!ctaWasShown) {
        ctaWasShown = true;
        emitTelemetry("guide_cta_shown");
      }
    }

    function showGettingStartedConfirmation() {
      closeConfirmation();

      const dialog = document.createElement("dialog");
      dialog.className = "howto-guide__dialog";
      dialog.dataset.howtoGuideDialog = "true";
      dialog.setAttribute("aria-modal", "true");

      const titleId = "howto-guide-dialog-title";
      const bodyId = "howto-guide-dialog-body";
      dialog.setAttribute("aria-labelledby", titleId);
      dialog.setAttribute("aria-describedby", bodyId);

      const title = document.createElement("h2");
      title.id = titleId;
      title.className = "howto-guide__dialog-title";
      title.textContent = "Start a new guide chat?";

      const body = document.createElement("p");
      body.id = bodyId;
      body.textContent =
        "Your current chat will not be changed. After you confirm, the guide will open a new chat and send the visible Getting Started prompt.";

      const status = document.createElement("p");
      status.className = "howto-guide__status";
      status.setAttribute("role", "alert");
      status.setAttribute("aria-live", "polite");

      const actions = document.createElement("div");
      actions.className = "howto-guide__dialog-actions";

      const cancelButton = document.createElement("button");
      cancelButton.type = "button";
      cancelButton.className = "howto-guide__button howto-guide__button--secondary";
      cancelButton.textContent = "Cancel";
      cancelButton.addEventListener("click", cancelConfirmation);

      const confirmButton = document.createElement("button");
      confirmButton.type = "button";
      confirmButton.className = "howto-guide__button howto-guide__button--primary";
      confirmButton.textContent = "Start guide";
      confirmButton.addEventListener("click", async () => {
        confirmButton.disabled = true;
        status.textContent = "";
        try {
          const accepted = await requestRecipe({
            version: 1,
            recipe: LAUNCH_RECIPE_ID,
            source: "cta",
          });
          if (!accepted) {
            status.textContent =
              "The Open WebUI Guide is unavailable. Ask an administrator to install the guide Function and enable its Guide Bridge recipe runner.";
            emitTelemetry("guide_cta_unavailable");
            return;
          }
          emitTelemetry("guide_cta_started");
          closeConfirmation();
        } catch (_error) {
          status.textContent =
            "The Open WebUI Guide could not be started. Your current chat was not changed.";
          emitTelemetry("guide_cta_unavailable");
        } finally {
          confirmButton.disabled = false;
        }
      });

      actions.appendChild(cancelButton);
      actions.appendChild(confirmButton);
      dialog.appendChild(title);
      dialog.appendChild(body);
      dialog.appendChild(status);
      dialog.appendChild(actions);
      dialog.addEventListener("cancel", (event) => {
        event.preventDefault();
        cancelConfirmation();
      });
      document.body.appendChild(dialog);

      if (typeof dialog.showModal === "function") {
        dialog.showModal();
      } else {
        dialog.setAttribute("open", "");
      }
      cancelButton.focus();
    }

    function cancelConfirmation() {
      emitTelemetry("guide_cta_cancelled");
      closeConfirmation();
      document.querySelector(CTA_SELECTOR)?.focus();
    }

    function closeConfirmation() {
      const dialog = document.querySelector(DIALOG_SELECTOR);
      if (!dialog) {
        return;
      }
      if (typeof dialog.close === "function" && dialog.open) {
        dialog.close();
      }
      dialog.remove();
    }

    function resolveTarget(targetId) {
      const target = uiMap.targets[targetId];
      if (!target) {
        return null;
      }

      for (const locator of target.locators) {
        const candidates = resolveLocator(locator).filter(isVisible);
        if (candidates.length === 1) {
          return candidates[0];
        }
      }
      return null;
    }

    function resolveLocator(locator) {
      if (locator.kind === "css" || locator.kind === "css_fallback") {
        return Array.from(document.querySelectorAll(locator.selector));
      }
      if (locator.kind !== "role") {
        return [];
      }

      const roleSelector = roleToSelector(locator.role);
      const namePattern = compileNamePattern(locator.name_pattern);
      return Array.from(document.querySelectorAll(roleSelector)).filter((element) =>
        namePattern.test(accessibleName(element)),
      );
    }

    function isVisible(element) {
      if (element.hidden || element.getAttribute("aria-hidden") === "true") {
        return false;
      }
      if (typeof element.getClientRects !== "function") {
        return true;
      }
      return element.getClientRects().length > 0;
    }

    function accessibleName(element) {
      const labelledBy = element.getAttribute("aria-labelledby");
      if (labelledBy) {
        const text = labelledBy
          .split(/\s+/)
          .map((id) => document.getElementById(id)?.textContent || "")
          .join(" ")
          .trim();
        if (text) {
          return text;
        }
      }
      return (
        element.getAttribute("aria-label") ||
        element.getAttribute("title") ||
        element.textContent ||
        ""
      ).trim();
    }

    return {
      start,
      stop,
      ensureGettingStartedCta,
      showGettingStartedConfirmation,
      resolveTarget,
    };
  }

  function roleToSelector(role) {
    const nativeRoles = {
      button: "button,[role='button']",
      link: "a[href],[role='link']",
      navigation: "nav,[role='navigation']",
      textbox: "textarea,input:not([type]),input[type='text'],[role='textbox']",
    };
    return nativeRoles[role] || `[role='${cssEscape(role)}']`;
  }

  function compileNamePattern(source) {
    const ignoreCase = source.startsWith("(?i)");
    return new RegExp(ignoreCase ? source.slice(4) : source, ignoreCase ? "i" : "");
  }

  function cssEscape(value) {
    if (globalScope.CSS?.escape) {
      return globalScope.CSS.escape(value);
    }
    return String(value).replace(/['\\]/g, "\\$&");
  }

  function validateUiMap(uiMap) {
    if (
      !uiMap ||
      uiMap.schema_version !== 1 ||
      !Array.isArray(uiMap.allowed_origins) ||
      !uiMap.targets ||
      !uiMap.targets["navigation-actions"]
    ) {
      throw new Error("Unsupported or incomplete Guide Bridge UI map.");
    }
  }

  function registerRecipeRunner(handler) {
    if (typeof handler !== "function") {
      throw new TypeError("Guide Bridge recipe runner must be a function.");
    }
    if (recipeRequestHandler) {
      throw new Error("A Guide Bridge recipe runner is already registered.");
    }
    recipeRequestHandler = handler;
    return () => {
      if (recipeRequestHandler === handler) {
        recipeRequestHandler = null;
      }
    };
  }

  async function requestRegisteredRecipe(request) {
    if (
      !request ||
      request.version !== 1 ||
      request.recipe !== LAUNCH_RECIPE_ID ||
      request.source !== "cta" ||
      !recipeRequestHandler
    ) {
      return false;
    }
    const safeRequest = Object.freeze({
      version: 1,
      recipe: LAUNCH_RECIPE_ID,
      source: "cta",
    });
    return (await recipeRequestHandler(safeRequest)) === true;
  }

  globalScope.HowToGuideBridge = Object.freeze({
    CTA_SELECTOR,
    DIALOG_SELECTOR,
    LAUNCH_RECIPE_ID,
    TELEMETRY_EVENT,
    createGuideBridge,
    registerRecipeRunner,
    requestRegisteredRecipe,
  });
})(globalThis);
