# Third-party notices

PcbKnowledge vendors narrowly scoped third-party runtime assets only when they are required for deterministic local behavior. Vendored assets remain subject to their upstream licenses.

## PDF.js

- Project: PDF.js / `pdfjs-dist`
- Upstream: Mozilla
- Version: `6.2.108`
- Build: `legacy`
- License: Apache License 2.0
- Release tag: `v6.2.108`
- NPM package: `pdfjs-dist@6.2.108`
- Package SHA-1: `1e0ce0f4b3a034f953dbbe2334ab01fbddf0eb30`
- Package integrity: `sha512-YxFb+SQcodN2rnX9Tn3dHYlqfb7NjlzzfONPpJd+AKoKtUjEdevTfbC07d5TcczzOK6261auRkP/M8OBHs9vFQ==`

PcbKnowledge vendors only the legacy display-layer module, its worker, and the upstream license. It does not vendor the generic PDF.js viewer UI, CMaps, WASM modules, or standard-font assets in P0.3b.

The exact committed file SHA-256 values are recorded in `src/pcbknowledge/git_native/static/vendor/pdfjs/6.2.108/vendor-manifest.json` and independently pinned by `src/pcbknowledge/git_native/pdfjs_vendor.py`. CI runs `python configs/check_pdfjs_vendor.py`; runtime server startup also validates the same bytes before exposing the evidence viewer.

Upstream references:

- https://github.com/mozilla/pdf.js/releases/tag/v6.2.108
- https://www.npmjs.com/package/pdfjs-dist/v/6.2.108

The full Apache-2.0 license text distributed with PDF.js is retained at `src/pcbknowledge/git_native/static/vendor/pdfjs/6.2.108/LICENSE`.
