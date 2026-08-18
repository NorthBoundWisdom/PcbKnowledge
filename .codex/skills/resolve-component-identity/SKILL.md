---
name: resolve-component-identity
description: Resolve and create exact Manufacturer, Component, and Package identities inside one explicitly selected PcbKnowledge workspace. Use when matching an MPN or package without fuzzy inference.
---

# Resolve Component Identity

Preserve raw identity strings, use normalized keys only for exact lookup, and operate only on the workspace selected by the task.

## Validate the target workspace

```bash
python3 configs/pcbknowledge_workspace.py validate '<workspace>'
```

Never infer another repository if validation fails.

## Resolve before creating

Resolve the manufacturer first:

```bash
python3 configs/pcbknowledge_agent.py --repo '<workspace>' entity resolve-manufacturer --name '<raw-manufacturer-name>'
```

Interpret `result` literally:

- `EXACT`: use the single returned entity ID.
- `UNKNOWN`: preserve the unknown unless an authorized source or the user explicitly confirms the raw value.
- `CONFLICT`: stop and report every candidate. Never select a winner by similarity.

Resolve component and package independently:

```bash
python3 configs/pcbknowledge_agent.py --repo '<workspace>' entity resolve-component \
  --manufacturer-id '<manufacturer-id>' \
  --mpn '<raw-mpn>'

python3 configs/pcbknowledge_agent.py --repo '<workspace>' entity resolve-package --name '<raw-package-name>'
```

Never infer package, silicon revision, orderable part, or family from an MPN suffix.

## Create verified unknown identities

Create only when the raw identity is explicit in an authorized source or supplied by the user:

```bash
python3 configs/pcbknowledge_agent.py --repo '<workspace>' entity create-manufacturer \
  --idempotency-key 'manufacturer:<exact-raw-name>' \
  --name '<exact-raw-name>'

python3 configs/pcbknowledge_agent.py --repo '<workspace>' entity create-component \
  --idempotency-key 'component:<manufacturer-id>:<exact-raw-mpn>' \
  --manufacturer-id '<manufacturer-id>' \
  --mpn '<exact-raw-mpn>'

python3 configs/pcbknowledge_agent.py --repo '<workspace>' entity create-package \
  --idempotency-key 'package:<exact-raw-package-name>' \
  --name '<exact-raw-package-name>'
```

Add `--family` only when the source states it. Re-run the exact resolver after creation and use only an `EXACT` result. Treat `CONFLICT` from create as evidence that another identity already owns the normalized key.

## Boundaries

- Stop on `INVALID_WORKSPACE`; do not redirect to `.` or another sibling repository.
- Preserve capitalization, punctuation, and suffixes in raw fields.
- Do not merge near matches or fill unknown identity from model memory.
- Do not approve, reject, delete authority, stage, commit, or push.
