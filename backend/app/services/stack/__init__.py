"""Stack auto-configuration: read existing app configs, then wire the apps.

- ``configs``  reads API keys / ports from the apps' own config files
               (appdata folder mounted read-only into the container).
- ``probe``    finds a URL where each app answers, validated with its key.
- ``wiring``   builds an idempotent plan (Prowlarr apps, download clients,
               Bazarr links, ArrMada services) and applies it.
"""
