# MH2029-601T ferrite-bead condition review

Five small original annotations concern exact Bourns MH2029-601T, not the
similarly named MH2029-601Y. The slice addresses RF impedance versus DC loss,
thermal current rating versus hot operation, and incomplete filter evidence.

## Actual evidence and rights

- Official source: https://www.bourns.com/docs/Product-Datasheets/MH2029-T.pdf
- Download: 659,479 bytes, four PDF pages; SHA-256
  `359f5ab799d0f9d03b15a0b886e6b29818ee134304c104cebd79db1aeb5041c9`.
- Electrical revision is `REV. 09/23` on PDF page 3. The separate legal notice
  on page 4 is `K2540 05/26R`; it is not a new electrical revision.
- Collector `agent:/root/finish_bpw34_stage/curate_ferrite_conditions`
  inspected rendered pages 1-3 and read legal page 4 before factual processing.
  Page 1 supplies the exact model row, package and current-rating basis;
  page 2 the exact model's Z/R/X plot; page 3 revision and series packaging.
- No open license or source-redistribution permission is claimed. The legal
  notice requires application-specific judgment and warns that laboratory
  characteristics may not transfer to actual applications. No explicit ban on
  these limited original factual annotations was identified. No table, figure,
  vendor prose or source PDF is reproduced. Actual originals, extracted text
  and page images remain local and untracked.

## Source distinctions and unknowns

The impedance row specifies 100 MHz / 60 mV under the 25 C table header;
60 mV is not silently labeled RMS or peak, and a DC-bias value is not invented.
The DC-resistance maximum is separate from RF impedance and is not a
full-temperature bound. The stated current rating uses a 40 C maximum rise;
neither operating-temperature range nor that rating establishes permitted
current at an arbitrary hot ambient or board mounting.

The frequency plot labels Z, R and X, but does not explicitly identify a
min/typ/max classification or DC bias. No curve points are digitized, no curve
is upgraded to a guarantee, and R(f) is not the DC resistance. Full filter
attenuation, supply resonance, thermal margin and actual loading remain
application questions. Three complete warnings preserve these distinctions.

## Independent review

Draft JSON SHA-256:
`5cf18b09ed831d225b9bff3265be63ae981f27dd3c012f9f26b17102c0f5aac2`.

Independent reviewer `agent:/root/finish_bpw34_stage/curate_ferrite_conditions/review_ferrite_source` accepted at `2026-10-29T00:12:59.652283+00:00` after independently recomputing the real PDF hash and size and inspecting rendered pages 1-3 plus legal page 4. All five full facts and all three warnings were reviewed. No numeric or engineering-condition corrections were needed. One locator correction sets `printed_page` to null because the source pages have no printed numbers; explicit physical PDF page locators remain.

Final accepted JSON SHA-256: `775888fa8e72583c65aa350d63ded06002a7142246db64ff92d976f7c936137b`.

Acceptance is Agent review under owner delegation, not canonical, human or circuit approval. Full integration and exact published-commit CI remain separate gates.
