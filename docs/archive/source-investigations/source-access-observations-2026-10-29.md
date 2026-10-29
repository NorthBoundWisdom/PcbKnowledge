# Source-access observations — 2026-10-29

Status: investigation record; independently reviewed within the limits below. These are narrow
observations supporting a conservative collection stop, not legal advice or a
legal determination. They do not change repository policy, source schemas,
existing acceptance receipts or historical knowledge records.

Collector: `agent:/root/finish_bpw34_stage/curate_ferrite_conditions`.
All observation times below are UTC on 2026-10-29.

## Vishay: website-level restriction discovered before LED ingestion

At approximately 01:37, the official product page
<https://www.vishay.com/en/product/83006/> was read to locate current source and
legal links for a possible TLHR4400 LED slice. Its footer linked the website
terms at <https://www.vishay.com/doc?47140=>. The web tool returned the six-page
terms, effective July 1, 2025, with status 07/2025.

- Section 3, physical PDF page 1, limits content use and reproduction to
  authorized purposes.
- Section 4, physical PDF page 2, describes a limited personal-use license and
  additional restrictions on commercial exploitation.
- Section 6, physical PDF pages 2–3, includes a restriction on automated access,
  including monitoring or copying. This was the decisive collection stop.

The ordinary product disclaimer was also read at
<https://www.vishay.com/docs/91000/disclaimer.pdf>, revision January 1, 2026.
Its application-suitability and intellectual-property disclaimers did not
replace the separate website terms. Checking only that product disclaimer would
have missed the website-level restriction.

Actual coverage: a search exposed incidental product snippets; the official
product page, product disclaimer and website terms were read through the web
tool. The requested electrical datasheet was **not downloaded or opened for
factual collection**, and no LED facts were drafted. No alternate host, cached
electrical copy or distributor copy was pursued after the restriction was found.
No local original bytes were retained for these legal pages: their byte counts
and SHA-256 hashes are `NOT_VERIFIED`. The web text view is an observation, not
byte-verified source evidence.

Future automated manufacturer-content retrieval requires applicable
authorization for the intended access and use; none was established in this
investigation. This observation is not a retroactive adjudication of previous
Vishay batches, which remain unchanged.

## Littelfuse: public-curation scope not established

At approximately 01:09, an alternative one-time-fuse candidate in the 0451
family was screened. The official terms URL was
<https://www.littelfuse.com/legal/website-terms-of-use>. Initial web text views
of the English and German legal pages had little or no readable text. A normal
HTTP request to the English terms page succeeded with status 200, and its
embedded English legal text was inspected. There was no access-denial bypass.

- Clause 3 restricts public distribution of information and copying or transfer
  without permission.
- Clause 5 limits the stated download permission to noncommercial personal use
  and describes written-permission requirements for publication/storage/transfer.

Those terms did not establish permission for the proposed public knowledge-base
collection. Collection stopped without downloading or processing the electrical
PDF. Incidental search snippets were not converted into accepted facts.

Actual local legal HTML receipt:

- Bytes: `167192`.
- SHA-256: `cd889106ecce245b115c4dcce43a3732de50d9cef2a6d60874f75f2322548993`.
- The original remains local and untracked; it is not included in this repository
  or a package. A document revision/effective date was not established.

The official product-disclaimer URL
<https://www.littelfuse.com/disclaimer-electronics> redirected to
<https://www.littelfuse.com/legal/product-disclaimer>, but the web tool returned
no readable body. No substantive product-disclaimer review is claimed.
No written permission applicable to the proposed public-curation use was found;
this is an unresolved access/use prerequisite, not a legal conclusion about all
possible uses of Littelfuse information.

## TI SLVA689: prior blocker distinguished from current observations

The supervising task reported an already-established restriction for TI
application resources and instructed that it must not be reopened through an
assumption of prior TI authorization. This record does not independently
reconstruct that earlier investigation or its evidence.

During the bounded candidate assessment at approximately 01:07, the web tool
read <https://www.ti.com/lit/pdf/slva689> and returned SLVA689A, revised October
2026, six pages. The legal notice on physical PDF page 6 limited resource use to
TI-product application development and restricted other reproduction/display.
An earlier `/lit/an/slva689/slva689.pdf` web request had failed with an unspecified
fetch status; the tool did not identify that result as an HTTP 403.

The assessment did not download local PDF bytes, create an intake draft or
publish derived knowledge. On confirmation of the prior blocker, investigation
stopped; no further route or source copy was pursued. Local byte count and
SHA-256 are `NOT_VERIFIED`. Search/open text had exposed candidate engineering
content, but it is not an accepted source batch or a permission clearance.

## Scope and review boundary

These observations record why three candidate paths did not proceed. They do
not establish an open license, grant permission, weaken the repository source
boundary, or authorize future retries. No electrical source originals or legal
page copies are committed. Historical records and existing review decisions are
unchanged. Independent review of this small record is separate from any legal
opinion or manufacturer authorization.

## Independent record review

Reviewer: `agent:/root/finish_bpw34_stage/prepare_ferrite_replay`.
Review time: `2026-10-29T01:41:49.510693+00:00`.

The reviewer independently recomputed the retained Littelfuse legal HTML byte
count and SHA-256 above and parsed its embedded English clauses 3 and 5. Their
limited paraphrases in this record are supported by those local bytes. The
reviewer did not independently verify the HTTP response, retrieval chronology,
absence of other retrievals, or any remote page's current contents.

Vishay and TI entries remain attributed collector reports of web-tool text
observations, not independently reconstructed or byte-verified source evidence.
No new network retrieval was performed for this review. No electrical PDF was
opened, copied or reassessed. The distinction between the supervising task's
prior TI blocker and the collector's later observation is retained explicitly.

The reviewer also checked the linked TODO source-access-prerequisites summary
for consistency. This review accepts the bounded investigation record, not a
legal determination, manufacturer permission, new policy, source acceptance or
retroactive reassessment of historical batches.
