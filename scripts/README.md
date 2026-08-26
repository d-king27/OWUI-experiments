# Development scripts

Cross-platform-friendly helper scripts for starting, stopping, and inspecting the local environment will live here.

The public developer interface will remain the root `Makefile`, with direct Docker Compose commands documented for environments where GNU Make is unavailable.

## Guide assets

`build-guide-assets.py` validates `knowledge/ui-map.yaml` through the domain package and generates `openwebui/guide-extension/ui-map.json`:

```powershell
python scripts/build-guide-assets.py
```

Use check mode in CI to detect an absent or stale generated asset without changing it:

```powershell
python scripts/build-guide-assets.py --check
```

The YAML file is canonical. Do not edit the generated JSON by hand.
