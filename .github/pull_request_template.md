## Summary

Describe the contract or behavior changed by this PR.

## Verification

- [ ] `python3 configs/check_public_repo.py`
- [ ] `python3 configs/pcbknowledge_workflow.py config`
- [ ] `python3 configs/pcbknowledge_workflow.py build`
- [ ] `python3 configs/pcbknowledge_workflow.py test`
- [ ] `python3 configs/pcbknowledge_agent.py validate`

## Open-source boundary

- [ ] No production `knowledge/**` records or `evidence/**` originals are included.
- [ ] No credentials, tokens, private keys, internal endpoints, customer data, or confidential logs are included.
- [ ] New fixtures are synthetic or have an explicit redistribution basis documented in the PR.
- [ ] Code/schema/policy changes are not mixed with a knowledge-data publication commit.

## Contract impact

- [ ] No Source / Entity / Fact / EvidenceAnchor schema change, or the schema/tests/docs are updated together.
- [ ] No Agent privilege expansion, or the security/review boundary change is explicitly documented and reviewed.
