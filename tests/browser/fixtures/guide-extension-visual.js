(async function startGuideVisualFixture() {
  "use strict";

  const extensionRoot = "../../../openwebui/guide-extension";
  const [uiMap, recipeAsset] = await Promise.all(
    ["ui-map.json", "recipes.json"].map(async (name) => {
      const response = await fetch(`${extensionRoot}/${name}`);
      if (!response.ok) throw new Error(`Unable to load ${name}.`);
      return response.json();
    }),
  );
  const telemetryList = document.querySelector("#telemetry");
  const emitTelemetry = HowToGuideTelemetry.createTelemetryEmitter({
    scope: globalThis,
    CustomEvent,
    eventName: HowToGuideBridge.TELEMETRY_EVENT,
  });
  addEventListener(HowToGuideBridge.TELEMETRY_EVENT, (event) => {
    const item = document.createElement("li");
    item.textContent = JSON.stringify(event.detail);
    telemetryList.appendChild(item);
  });

  const schedule = (callback, milliseconds) =>
    setTimeout(callback, Math.min(milliseconds, 100));
  const runner = HowToGuideRecipeRunner.createRecipeRunner({
    document,
    location: { origin: "http://localhost:3000" },
    uiMap,
    recipeAsset,
    emitTelemetry,
    schedule,
    actions: {
      checkPrecondition: async () => true,
      runStep: async () => new Promise((resolve) => schedule(resolve, 25)),
      clearHighlights: () => {},
    },
  });
  HowToGuideBridge.registerRecipeRunner(runner.handleConfirmedRequest);

  const renderer = HowToGuideDirectiveRenderer.createDirectiveRenderer({
    document,
    location: { origin: "http://localhost:3000" },
    MutationObserver,
    uiMap,
    recipeAsset,
    recipeRuntime: runner,
    emitTelemetry,
  });
  renderer.start();

  const bridge = HowToGuideBridge.createGuideBridge({
    document,
    location: { origin: "http://localhost:3000" },
    MutationObserver,
    CustomEvent,
    loadUiMap: async () => uiMap,
    requestRecipe: HowToGuideBridge.requestRegisteredRecipe,
    emitTelemetry,
  });
  await bridge.start();
})();
