(async function startGuideBridge() {
  "use strict";

  const api = globalThis.HowToGuideBridge;
  const telemetryApi = globalThis.HowToGuideTelemetry;
  const runnerApi = globalThis.HowToGuideRecipeRunner;
  const rendererApi = globalThis.HowToGuideDirectiveRenderer;
  if (!api || !telemetryApi || !runnerApi || !rendererApi) {
    return;
  }

  async function loadAsset(name) {
    const response = await fetch(chrome.runtime.getURL(name));
    if (!response.ok) {
      throw new Error(`Unable to load Guide Bridge asset ${name} (${response.status}).`);
    }
    return response.json();
  }

  let uiMap;
  let recipeAsset;
  try {
    [uiMap, recipeAsset] = await Promise.all([
      loadAsset("ui-map.json"),
      loadAsset("recipes.json"),
    ]);
  } catch (error) {
    console.warn("Open WebUI Guide Bridge could not load its assets.", error);
    return;
  }

  const emitTelemetry = telemetryApi.createTelemetryEmitter({
    scope: globalThis,
    CustomEvent,
    eventName: api.TELEMETRY_EVENT,
  });

  let runner;
  try {
    runner = runnerApi.createRecipeRunner({
      document,
      location,
      uiMap,
      recipeAsset,
      emitTelemetry,
    });
  } catch (error) {
    console.warn("Open WebUI Guide recipe runner could not start.", error);
    return;
  }
  api.registerRecipeRunner(runner.handleConfirmedRequest);
  globalThis.HowToGuideRecipeRuntime = Object.freeze({
    cancel: runner.cancel,
    requestWithConfirmation: runner.requestWithConfirmation,
  });

  let renderer;
  try {
    renderer = rendererApi.createDirectiveRenderer({
      document,
      location,
      MutationObserver,
      uiMap,
      recipeAsset,
      recipeRuntime: runner,
      emitTelemetry,
    });
    renderer.start();
  } catch (error) {
    console.warn("Open WebUI Guide directive renderer could not start.", error);
  }

  const bridge = api.createGuideBridge({
    document,
    location,
    MutationObserver,
    CustomEvent,
    loadUiMap: async () => uiMap,
    requestRecipe: api.requestRegisteredRecipe,
    emitTelemetry,
  });

  try {
    await bridge.start();
  } catch (error) {
    console.warn("Open WebUI Guide Bridge could not start.", error);
  }
})();
