# Backup and restore baseline

This document defines the target recovery contract; the checked-in Compose stack does not by itself constitute a qualified backup system.

## Permanent assets

Back up PostgreSQL, SeaweedFS original objects, approved Keycloak realm configuration, and versioned deployment configuration as one recovery set. Parsed blocks, thumbnails, FTS/vector indexes, caches, and summaries are derived and must be rebuildable.

The P0 production target is pgBackRest full/differential backups with continuous WAL archival for PITR, a daily `pg_dump` for selective/cross-version recovery, and daily SeaweedFS volume snapshots. Restore an automated backup into an isolated environment weekly and run a human disaster-recovery exercise monthly.

## Fail-closed restore order

1. Select a mutually compatible database/WAL, object snapshot, application revision, and configuration set.
2. Restore into an isolated network with external notifications, model providers, and agent access disabled.
3. Apply only the migrations belonging to the selected application revision.
4. Verify database constraints and audit continuity before allowing object access.
5. Recompute SHA-256 for a random sample of original objects and compare database identities.
6. Open evidence anchors for sampled published records and verify page/bbox/source revision.
7. Rebuild derived indexes from permanent assets and run retrieval/permission golden cases.
8. Record versions, timestamps, counts, hashes, commands, exit codes, and failures in the recovery receipt.
9. Promote the environment only after an authorized operator approves the receipt.

An object without a matching digest, a published record without accessible evidence, a gap in required audit history, or a failed permission test blocks promotion. The recovery process never fabricates a replacement object or silently drops the record.

## Deletion

The local scripts never delete volumes automatically. Legal/contractual deletion requires dependency impact analysis followed by tombstone plus approved physical or cryptographic erasure. Preserve an audit receipt without retaining prohibited content.
