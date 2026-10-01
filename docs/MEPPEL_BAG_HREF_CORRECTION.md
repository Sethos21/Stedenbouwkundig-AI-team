# MEPPEL_BAG_HREF_CORRECTION

Result: **PASS_WITH_FINDINGS**. Start HEAD:
`a5ec4b324dc4a8e03408b45456e7b0d0228eee70`.
Branch: `test/meppel-ke-borgerlaan-4`.
Master baseline remains `1ea26e723c20b63a07b6012c1f67f604828d434b`.

## Evidence and supported relation forms

Only the existing committed Meppel ZIP was used. No live fetch was performed.
The package SHA-256 and every member hash were checked. Raw BAG pages, also
checked against their stored SHA-256, contain:

| Source | Literal field | Records with nonempty references | References |
| --- | --- | ---: | ---: |
| BAG/pand | `verblijfsobject.href` | 223 | 312 |
| BAG/verblijfsobject | `pand.href` | 302 | 302 |
| Total | | 525 | 614 |

The exact href routes are the existing contracts' HTTPS item endpoints:
`https://api.pdok.nl/kadaster/bag/ogc/v2/collections/verblijfsobject/items/{id}`
and `https://api.pdok.nl/kadaster/bag/ogc/v2/collections/pand/items/{id}`.
Every nonempty href is a string in an array. The other 155 BAG pand records have
an explicit null `verblijfsobject.href` value.

## Minimal resolver change

Only production file `src/bvc_ai/application/source_basis.py` changes.
The read-only resolver accepts those two literal fields and exact routes from
the unchanged contracts. IDs are read verbatim from the final URL segment and
matched to feature IDs within the correct BAG collection. BAG registration
identifiers remain separate; there is no fallback from feature ID to registration
ID and no URL fetch, decoding, coordinate matching, inverse generation or LLM.

Existing `pand`/`verblijfsobject` attributes remain supported. When an attribute
and href array assert the same target set, one relation per identity is emitted,
with both original fields/references retained. Different asserted sets block the
whole group as `CONFLICTING_OFFICIAL_REFERENCES`; neither side is preferred.

Wrong types, missing IDs, incorrect endpoints, credentials, query/fragment,
encoded/traversal paths and malformed nonempty hrefs produce uncertainty and
block the relation group, including fallback to an otherwise valid attribute.
Null means no assertion, matching the captured source representation. An explicit
empty array asserts an empty set. No usable references yields
`NO_OFFICIAL_REFERENCE_AVAILABLE`. Unknown targets remain `UNRESOLVED`, duplicate
target identities remain `AMBIGUOUS`. BGT all-zero sentinels always remain unresolved.

K00, Human Approval, trusted A02 capability, promotion, source immutability,
hashing algorithms, TESTDATA separation, eight source contracts, address
resolution and `docs/BAG_API_SECRET_SETUP.md` are unchanged. `BAG_API_KEY` was not
read or used. No BAG API Individuele Bevragingen integration or new milestone.

## Meppel results

| Requested measure | Actual result |
| --- | --- |
| href_records_examined | 525 |
| href_references_examined | 614 |
| href_references_validly_processed | 614 |
| href_relations_resolved | 604 |
| relations_resolved_total | 936 = 332 existing BGT + 604 BAG href |
| remaining_unresolved_relations | 13 = 10 BAG href + 3 BGT sentinels |
| records_without_usable_official_relation | 155, with no nonempty valid reference |
| bgt_sentinel_relations | 3, all UNRESOLVED, no target selected |
| synthetic_relations_created | 0 |
| replay / reconstruction | PASS / PASS, network blocked |

"Usable official reference" means a syntactically valid literal source reference;
it does not imply that its target is present in the snapshot. Counting records
with **no resolved target** instead gives 167 across the three relation-bearing
collections. The distinction avoids hiding unresolved references inside a missing
reference count. The other five BGT collections do not assert these relation types.

The 10 BAG references point to verblijfsobjects absent from the archived query
results; the cause is not inferred and no extra objects were fetched. The 155 null
references and three BGT zero references are unchanged source findings.

## Offline validation and review evidence

The existing archive was copied into fresh isolated local storage. Sockets,
connects and DNS were blocked throughout revalidation. All eight source snapshots
were reparsed and exactly reconstructed (raw bytes, geometry, features, pages and
snapshot manifests). No task or trusted binding was created by reconstruction.
The copied source database remained byte-identical after verification. Human
approval remains absent.

The new derived basis differs from the original **only** in `relations`,
`uncertainties` and the consequent `basis_hash`. All source records, source
identities, provenance, query scopes, active revisions and snapshots are unchanged.
The hashing implementation is unchanged. The original report and ZIP remain intact.
The original exact-basis verifier will correctly reject comparing the new relation
view to the historical report; use the dedicated correction revalidator below.

- Original basis: `5a26f286f6d1d5533c8a555a8bb543b1c63f88142601f7a40ba9b456c438fbe8`.
- New derived basis: `8a5a3b511a308ec0e4079b7e8d843d340237ab5b1200cce4f864cf0c42ba21a0`.
- [Offline revalidation and unresolved references](evidence/meppel-bag-href/offline-revalidation.json).
- [Complete derived relation projection](evidence/meppel-bag-href/relation-projection.json).
- [Targeted tests](evidence/meppel-bag-href/targeted-tests.txt): 48 PASS,
  including 16 new href tests and existing BAG, source basis, address and
  Mastenbroekweg proof regressions.
- [Full test.ps1 regression](evidence/meppel-bag-href/full-regression.txt): **484 PASS**, 88.073 seconds.

Reproduce without network or credentials:

```powershell
& ./.tools/source-venv/Scripts/python.exe -B scripts/revalidate_bag_href.py
```

A new `runtime/2d-live/bag-href-*` folder contains the isolated source copy,
reconstruction, complete derived basis and validation report. No original
archive or historical evidence is overwritten.

Remaining limitations: targets absent from the stored source set are not fetched;
null and sentinel references are not repaired; no point-in-time guarantee exists.
Only conservative literal item IDs composed of ASCII letters, digits, hyphens and
underscores are accepted in hrefs. An unsupported future URL/ID shape remains an
uncertainty rather than being normalized or guessed.

Final commit/push, full regression, diff and secret-scan outcomes are supplied in
the final execution report. No master merge or master commit is performed.
