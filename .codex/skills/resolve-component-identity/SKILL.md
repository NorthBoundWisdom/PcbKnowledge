---
name: resolve-component-identity
description: Resolve and create exact Git-native Manufacturer, Component, and Package entity identities from verified raw names and MPNs. Use when a knowledge-ingestion task needs stable entity IDs, when matching a component or package, or when an Agent must report exact, unknown, or conflicting identity without fuzzy inference.
---

# Resolve Component Identity

Preserve raw identity strings and use normalized keys only for exact lookup.

## Resolve before creating

Resolve the manufacturer first:

```bash
python3 configs/pcbknowledge_agent.py entity resolve-manufacturer --name '<raw-manufacturer-name>'
```

Interpret `result` literally:

- `EXACT`: use the single returned entity ID.
- `UNKNOWN`: keep the identity unknown unless an authorized source or the user explicitly confirms the raw value.
- `CONFLICT`: stop and report every candidate. Never select a winner by similarity.

After resolving the manufacturer, resolve the component and package independently:

```bash
python3 configs/pcbknowledge_agent.py entity resolve-component \
  --manufacturer-id '<manufacturer-id>' \
  --mpn '<raw-mpn>'

python3 configs/pcbknowledge_agent.py entity resolve-package --name '<raw-package-name>'
```

Never infer package, silicon revision, orderable part, or family from an MPN suffix.

## Create verified unknown identities

Create only when the raw identity is explicit in an authorized source or supplied by the user. Use stable business keys based on confirmed identity, not task timestamps or filesystem paths:

```bash
python3 configs/pcbknowledge_agent.py entity create-manufacturer \
  --idempotency-key 'manufacturer:<exact-raw-name>' \
  --name '<exact-raw-name>'

python3 configs/pcbknowledge_agent.py entity create-component \
  --idempotency-key 'component:<manufacturer-id>:<exact-raw-mpn>' \
  --manufacturer-id '<manufacturer-id>' \
  --mpn '<exact-raw-mpn>'

python3 configs/pcbknowledge_agent.py entity create-package \
  --idempotency-key 'package:<exact-raw-package-name>' \
  --name '<exact-raw-package-name>'
```

Add `--family` only when the source states it. Re-run the exact resolver after creation and use only an `EXACT` result. Treat `CONFLICT` from create as evidence that another identity already owns the normalized key; do not create variants to bypass it.

## Boundaries

- Preserve capitalization, punctuation, and suffixes in raw fields.
- Do not merge near matches or fill unknown identity from model memory.
- Do not approve, reject, delete authority, stage, commit, or push.
