# MEPPEL_GENERALIZATION_TEST

Technical result: **PASS_WITH_FINDINGS**. Delivery result: **BLOCKED** (push only). Baseline `4598666`, branch
`test/meppel-ke-borgerlaan-4`. The branch was created from the local accepted
Milestone-2D work baseline. Remote master was observed at
`8e1275681387c468bbcb798c9331ee800c38a2e8`; no merge or master write was performed.

Seth explicitly authorized this work on 30 September 2026. The Locatieserver is
used only to resolve an address and derive a technical analysis extent. It does
not replace BAG/BGT as the source of GIS facts. No new milestone was executed.

## Address and analysis

- address_resolution: PASS, exactly one result, `numFoundExact=true`, full normalized address match.
- official_address: **K.E. Borgerlaan 4, 7942HC Meppel**.
- official_identifiers: Locatieserver `adr-b7e0379b6c6d66cbe6de4e2dc7de2ecb`,
  nummeraanduiding `0119200000011044`, adresseerbaar object `0119010000011488`.
- coordinate_source: official Locatieserver `centroide_rd` field, raw response archived.
- coordinates: **208874.379, 524096.822**; coordinate_crs: **EPSG:28992** (RD New).
- analysis_geometry: bbox **208624.379, 523846.822, 209124.379, 524346.822**.
  Deterministic axis-aligned square, source coordinate +/-250 metres per axis.
  Native RD, no transformation. This preserves the Mastenbroekweg proof's 500 x 500 m scope.
- Geometry role: `TESTCASE_ONLY_ANALYSIS_GEOMETRY`. This is **not** an ownership,
  cadastral, policy, project or design boundary.

The independently fetched BAG verblijfsobject with feature ID
`e46c6c18-7d0a-596c-8e2c-1c38b45e9abc` has `identificatie=0119010000011488`
and `hoofdadres_identificatie=0119200000011044`. Both match the address response
literally; this is not a spatially inferred or synthesized relation.

## Existing source chain

collections_requested and collections_completed: all eight existing contracts.

| Collection | Source objects |
| --- | ---: |
| BAG/pand | 378 |
| BAG/verblijfsobject | 302 |
| BGT/begroeidterreindeel | 218 |
| BGT/onbegroeidterreindeel | 115 |
| BGT/ondersteunendwegdeel | 22 |
| BGT/pand | 335 |
| BGT/waterdeel | 41 |
| BGT/wegdeel | 497 |
| Total | 1908 |

- source_objects: **1908**.
- source_basis_complete: **true**, A02 revision `A02/v8`; all query scopes validated.
- relations_resolved: **332**, using the existing official-attribute resolver.
- relations_unresolved: **3** literal BGT `bag_pnd=0000000000000000` references.
- records_without_official_reference: the existing resolver labels **680** BAG
  records `NO_OFFICIAL_REFERENCE_AVAILABLE`, but this is **not** evidence that
  all 680 lack references in the source. The live API supplies `pand.href` and
  `verblijfsobject.href`, whereas the existing resolver reads `pand` and
  `verblijfsobject`. **525** BAG records carry **614** nonempty official href
  references that the resolver does not process. **155** BAG pand records have
  no nonempty official verblijfsobject.href reference. These findings remain
  explicit; no guessed/inverse relation or source edit was introduced.
- replay: **PASS**, source snapshots and address response revalidated offline.
- reconstruction: **PASS**, exact raw bytes, geometry, features, pages and
  snapshots reconstructed in separate task-free storage. No trusted bindings
  or workflow tasks created by reconstruction.
- human_approval: **none**. No APPROVED or REJECTED assigned; real runtime/GIS-001
  left untouched and waiting for the human. No A03-A06 activation.

Source-basis SHA-256:
`5a26f286f6d1d5533c8a555a8bb543b1c63f88142601f7a40ba9b456c438fbe8`.
Query completeness is not a point-in-time consistency guarantee.

## Changes and tests

production_code_changes: added the closed address adapter, raw/hash/provenance
replay, generic deterministic address analysis, validated bbox scope in the
existing transport/import/replay, an explicit live address CLI and an offline
review CLI. The trusted import capability, K00 policy, approval service,
providers and workflow decision logic were not changed.

hardcoded_assumptions_removed: fixed Mastenbroekweg bbox/provenance for new
address-driven runs and the location-specific import opt-in naming. The legacy
Mastenbroekweg helper, runner and regression tests remain compatible. There is
no Meppel-specific production logic or coordinate fixture.

The runtime allowlist adds only HTTPS GET
`https://api.pdok.nl/bzk/locatieserver/search/v3_1/free`. Fixed BAG/address filters,
2 result rows, one request, no retry/redirect, 128 KiB, 20 seconds total request
deadline. Native address parsing requires street, number, postcode and city;
unsupported input, mismatches, ambiguity, malformed/partial responses, missing
RD points, unexpected CRS/source, and network/budget errors fail closed.
No score-based selection or fuzzy/synonym fallback is performed.

- targeted_tests: **37 PASS**, including 15 address/generalization tests,
  existing transport, live import and Mastenbroekweg proof regressions.
- full_regression: **PASS**, `test.ps1`, **468 tests**, final run 99.576 seconds.
- diff_check: `git diff --check` and staged diff check performed before commit;
  exact result recorded in the accompanying machine-readable summary.
- Independent offline re-verification with the final parser: **PASS**.
  Socket creation, connects and DNS are blocked during replay/reconstruction.
- CLI approval tests run using the existing isolated test storage; all synthetic
  responses in targeted tests are explicitly fixtures, never live evidence.

## Evidence and independent review

- evidence_location: `runtime/2d-live/20260930T080816485246Z`.
- Portable live evidence: [meppel-live-evidence.zip](evidence/meppel-contract/meppel-live-evidence.zip).
  Contains the exact source SQLite archive, raw address response, address
  provenance, original live report, source basis, verification report and a
  per-file SHA-256 manifest. ZIP members were read back and hash-checked.
- [Package and member hashes](evidence/meppel-contract/meppel-live-evidence-sha256.json).
- [Official endpoint contract](evidence/meppel-contract/address-contract.json)
  and [captured official API documentation](evidence/meppel-contract/official-contract.zip).
- [Targeted test log](evidence/meppel-contract/targeted-tests.txt),
  [full regression log](evidence/meppel-contract/full-regression.txt),
  [offline verification](evidence/meppel-contract/offline-verification.txt),
  [all requested report fields](evidence/meppel-contract/summary.json).

To review offline, extract the evidence ZIP into a **new** folder under
`runtime/2d-live/`, then run from the project root:

```powershell
& ./.tools/source-venv/Scripts/python.exe -B scripts/verify_address_proof.py --directory runtime/2d-live/review-meppel
```

A new isolated reconstruction folder is created. No fetch or approval occurs.
The source archive contains TESTDATA workflow scaffolding and separately
identified real provider responses; the scaffolding is not presented as source data.

To run a new explicitly opted-in live proof:

```powershell
& ./.tools/source-venv/Scripts/python.exe -B scripts/live_address_2d.py --live-address --address 'K.E. Borgerlaan 4, 7942 HC Meppel, Nederland'
```

remaining_limitations: conservative complete-address input; no source
point-in-time guarantee; unchanged BAG .href relation mapping limitation;
only the eight previously allowed collections; local Python and files remain
trusted (not a sandbox against malicious plugins). Process isolation and
authentication are prerequisites for future external callers/plugins.

commit: the containing Git commit (`git log -1 --format=%H -- docs/MEPPEL_GENERALIZATION_TEST.md`).
implementation_commit: `66082993c75f37b56e50c53f4d017606bd4d6dda`.
pushed: **false**. Automatic approval review rejected `git push -u origin
test/meppel-ke-borgerlaan-4`: it requires explicit authorization for exporting
project code and live evidence to `https://github.com/Sethos21/Stedenbouwkundig-AI-team.git`,
which it did not consider a verified trusted destination. The configured remote
was checked read-only; GitHub CLI is unavailable, so visibility/ownership
permissions could not be independently verified. No workaround or alternate
upload was attempted. All implementation, test and evidence work is committed;
only push awaits approval for that destination and payload. No master merge.
