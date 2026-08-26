(async function startGuideBridge() {
  "use strict";

  const api = globalThis.HowToGuideBridge;
  if (!api) {
    return;
  }

  const bridge = api.createGuideBridge({
    document,
    location,
    MutationObserver,
    CustomEvent,
    loadUiMap: async () => {
      const response = await fetch(chrome.runtime.getURL("ui-map.json"));
      if (!response.ok) {
        throw new Error(`Unable to load Guide Bridge UI map (${response.status}).`);
      }
      return response.json();
    },
    requestRecipe: api.requestRegisteredRecipe,
    emitTelemetry: (name) => {
      globalThis.dispatchEvent(
        new CustomEvent(api.TELEMETRY_EVENT, {
          detail: { name, version: 1 },
        }),
      );
    },
  });

  try {
    await bridge.start();
  } catch (error) {
    console.warn("Open WebUI Guide Bridge could not start.", error);
  }
})();
