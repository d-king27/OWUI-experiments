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

## Install the Open WebUI Guide Function

`install-howto-function.ps1` uses the administrator Function API verified against Open WebUI v0.11.0. It requires PowerShell 7.

Start Open WebUI first. Sign in as an administrator, create an API key, then keep that key outside source control and create and enable the Function:

```powershell
docker compose up -d
$env:OPEN_WEBUI_API_KEY = "<admin-api-key>"
./scripts/install-howto-function.ps1
```

Options:

- `-BaseUrl http://localhost:3000` changes the Open WebUI origin.
- `-ApiKey $env:OPEN_WEBUI_API_KEY` supplies the required administrator bearer credential instead of reading it from the environment automatically.
- `-NoEnable` creates or verifies the Function without enabling it.
- `-Update` explicitly replaces a stored Function when its name or source differs.
- PowerShell's standard `-WhatIf` previews create, update, and enable operations after the read-only checks.

The Compose baseline sets `ENABLE_API_KEYS=true`, but an administrator must still create the credential in Open WebUI. `WEBUI_AUTH=false` does not make administrator Function routes anonymous. The installer fails before making a request when no key is supplied, then calls the administrator-only Function list endpoint. Invalid or unauthorized keys therefore stop the script instead of being interpreted as a missing Function. Existing source is normalized only for line endings before comparison. It is never overwritten unless `-Update` is present, and the key is never printed.

The Function database stores a copy of `howto_pipe.py`; re-run with `-Update` after changing that file. Changes to the mounted domain package and knowledge are picked up when the Function module or container is reloaded.
