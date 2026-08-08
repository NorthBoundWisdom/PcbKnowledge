# Compose layout

The canonical Compose model is the root `compose.yaml`; service-specific configuration lives under `deploy/`. Keep local development behavior in that file so `docker compose config` and CI validate the same deployment path. Production overlays must pin images by digest and may not weaken authentication or required configuration.
