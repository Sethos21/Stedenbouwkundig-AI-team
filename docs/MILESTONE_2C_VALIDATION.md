# Milestone 2C - final validation en closure

Validatiedatum: 25 september 2026. Scope: uitsluitend Fase 7, beoordeling van
Fase 1 t/m 6 als een samenhangende MINIMAL_PROOF-keten. De aanduiding
"Fase 16" in de afsluitopdracht wordt gelezen als Fase 1 t/m 6.
Dit document sluit de technische milestone af binnen de hieronder beschreven
vertrouwensgrenzen; het kent geen menselijke projectgoedkeuring toe.

## Baseline en bewijsmethode

De geaccepteerde Fase 6-commit is zonder history rewrite of force push via
fast-forward naar master gebracht. Voor de Fase 7-validatie is exact gecontroleerd:

`master == origin/master == remote refs/heads/master == e38669791748dbd9e8a5f3d899c632c4ae9ed6de`.

Reviewbranch: `milestone-2c-final-review`. Master blijft daarna ongewijzigd.
De uitgesloten untracked items `Stedenbouwkundig-AI-team/` en
`phase3b-review.diff` zijn niet geopend, gewijzigd, verwijderd of gestaged.
Git-status is uitsluitend met `--untracked-files=no` gelezen; inhoudelijke
zoekopdrachten zijn beperkt tot expliciete projectcode, tests en documenten.

Deze validatie combineert code-inspectie, de bestaande regressietests en het
geaccepteerde Fase 6-livebewijs. Geen nieuwe live PDOK-call, dependency,
functionaliteit, productiefix of wijziging aan de tests. Er is geen
regressieprobleem aangetoond dat een reproducerende test of fix vereist.
Uitsluitend dit afsluitingsdocument wordt gecommit. Lokale verificatielogs en
hulpmiddelen staan onder ignored `.tools/`.

| Fase | Geaccepteerde implementatie | Bewijs |
|---|---|---|
| 1 | `64ce340` immutable bronopslag | [Fase 1](milestone-2c-phase1.md), storagetests |
| 2 | `818531d` CRS, geometry, hashing, completeness | [Fase 2](milestone-2c-phase2.md), validationtests |
| 3A | `26990f0` PDOK-parser en raw capture | [Fase 3A](milestone-2c-phase3a.md) |
| 3B | `30c9c86` bounded fetching/pagination | [Fase 3B](milestone-2c-phase3b.md) |
| 3C | `241e21a` failure/security | [Fase 3C](milestone-2c-phase3c.md) |
| 4 | `7ca3396` trusted source import | [Fase 4](milestone-2c-phase4.md) |
| 5 | `729fb76` offline replay | [Fase 5](milestone-2c-phase5.md) |
| 6 | `e386697` live Mastenbroekweg proof | [Fase 6](milestone-2c-phase6.md), [compact livebewijs](milestone-2c-phase6-proof.json) |

De historische faseverslagen beschrijven hun toenmalige beperkingen. Fase 6
voegt expliciete live opt-in toe aan de eerder bewust TESTDATA-only Fase 4/5;
het standaard TESTDATA-pad blijft ongewijzigd begrensd. De finale suite toetst
de volledige geaccepteerde implementatie, niet alleen het laatste faseverschil.

## Keten en trustgrenzen

1. `FetchExtent` en `PDOKBGTAdapter.build_request` leggen de query expliciet vast.
   De echte `PDOKLiveGetTransport` accepteert alleen HTTPS GET naar de vaste
   PDOK pand-path met de Mastenbroekweg-bbox, RD, JSON-FG en limit 1000; alleen
   een cursor is aanvullend toegestaan. URL en parameterparen moeten overeenkomen.
2. Het transport begrenst de totale caller-tijd inclusief DNS/TLS/headers/body
   en de bytes tijdens body-read. Redirects worden niet gevolgd. Geen cookies,
   credentials, sessiestaat, proxyconfiguratie of arbitrary-URL fetch.
3. Elke teruggegeven response wordt voor parsing gecaptured met exacte bodybytes,
   hash, status, headerparen, request en retrievaltijden. Errorresponses blijven
   evidence. Onderbroken transport zonder complete response verzint geen capture.
4. De bestaande JSON-FG-parser controleert HTTP/mediatype, expliciete CRS,
   FeatureCollection, feature-identiteit, place-geometrie en aantallen. Vervolgens
   controleren de bestaande validators geometrie, structurele hash en CRS.
   Geen coordinate-inference, transformatie of geometrische reparatie.
5. De adapter levert bij succes VALIDATING en pagination-exhaustion, geen
   COMPLETE-publicatie of EXISTING_VALIDATED. Fouten leveren geen bruikbare
   gedeeltelijke featurebundle. Next-links en retries blijven begrensd.
6. Alleen de trusted `SourceImportService`, met object-identieke
   `_A02_SOURCE_IMPORT_CAPABILITY`, stage't raw evidence en valideert provenance.
   Live opt-in vereist de exacte testcasegeometrie en oorspronkelijke
   UNVALIDATED_PROVIDER_RESPONSE. Raw bytes/hash, requestscope en chain worden
   gecontroleerd en opnieuw geparst; mapping moet overeenkomen. Completeness
   controleert aantallen, referenties, raw data, manifest en volledige paginaketen.
7. Binnen de bestaande publicatietransactie volgt een nieuwe taakgate, controle
   op gelijktijdige taakwijziging, immutable opslag en volledige archive-readback.
   Pas daarna ontstaan afgeleide A02-objecten met EXISTING_VALIDATED, revision,
   binding en succes-audit. COMPLETE alleen is onvoldoende. Rollback omvat ook
   revision/binding/stale-mutaties; eerder vastgelegde raw evidence mag blijven.
8. Gewijzigde bronnen gebruiken nieuwe snapshot/revision-identiteiten en de
   bestaande stale-route. Eerdere specialistoutputs en bronhistorie blijven
   behouden; reviews blijven aan de beoordeelde revision gekoppeld.
9. `SourceReplayService` leest vastgelegde evidence en gebruikt dezelfde parser
   zonder fetch. Raw/hash/manifest en volledige records/provenance worden
   vergeleken. Reconstructie naar lege opslag maakt alleen bronarchiefrecords;
   geen taak, DesignObject, active revision, binding, audit of promotion-capability.

De promotie-invariant betreft **geimporteerde brongeometrie**. Het bestaande
synthetische Ontwerplus-fixturepad gebruikt eveneens de enum EXISTING_VALIDATED,
maar accepteert alleen geregistreerde synthetische refs en blijft TESTDATA.
Dat is geen tweede route om PDOK-geometrie te promoveren: de bestaande negatieve
providertest probeert juist zo'n geimporteerde ref en wordt geweigerd. Een losse
statusstring of provider-actornaam verleent geen capability.

K00 wordt niet gewijzigd; de import registreert uitsluitend afgeleide objecten
via K00Policy. HumanApprovalService en de vertrouwde CLI houden hun afzonderlijke
human capability. Providers ontvangen geen Store, source-importcapability,
human capability, shell/filesystem- of approvaltool. Tests simuleren menselijke
besluiten uitsluitend in geisoleerde tijdelijke opslag. De echte demo
`runtime/GIS-001` wordt niet uitgevoerd of goedgekeurd.

## Traceability-matrix

Componentpaden zijn relatief aan `src/bvc_ai/`. Testbestanden zijn relatief aan
`tests/`; genoemde methoden zijn bestaande uitvoerbare tests. PASS geldt voor
de volledige finale regressie en, bij livebewijs, de geaccepteerde Fase 6-run.

| Requirement / invariant | Implementatiecomponent | Relevante bestaande tests / bewijs | Resultaat | Resterende beperking |
|---|---|---|---|---|
| Immutable source storage | `infrastructure/source_schema.py`, `source_store.py` | `test_source_storage.py`: `test_immutable_sql_guards_including_replace_all_tables`, `test_bound_snapshot_membership_cannot_be_extended`, `test_roundtrip_and_reopen` | PASS | Vertrouwde lokale SQLite/filesystemomgeving |
| Raw evidence | `domain/sources.py:RawResponse`, `adapters/pdok_bgt.py` | `test_source_storage.py`: `test_raw_bytes_verified_and_blob`, `test_corrupt_raw_on_read_is_rejected`; `test_pdok_bgt_security.py`: `test_capture_exists_before_parser_is_entered` | PASS | Geen fictieve complete body bij transportonderbreking |
| Structural hashing | `domain/source_hashing.py` | `test_source_validation.py`: `test_canonical_known_bytes_and_raw_sha256`, `test_precision_not_silently_rounded_in_hash`, `test_ring_rotation_changes_structural_identity` | PASS | Structurele identiteit, geen topologische equivalentie |
| Parsing/providercontract | `adapters/pdok_bgt.py:_parse` | `test_pdok_bgt_security.py`: `test_featurecollection_crs_and_count_failures`, `test_bad_feature_after_valid_feature_drops_mapping`; Fase 6-livebewijs | PASS | Smal JSON-FG place-profiel; geen contractaanpassing |
| CRS validation / geen gokken | `domain/geometry_validation.py`, `adapters/pdok_bgt.py` | `test_source_validation.py`: `test_missing_crs`, `test_axis_order_swapped`, `test_small_numbers_do_not_trigger_inference`; `test_source_import.py`: `test_insufficient_crs_evidence_fails` | PASS | Alleen native 2D RD; fout gelabelde getallen niet altijd detecteerbaar |
| Geometry validation / geen repair | `domain/geometry_validation.py` | `test_source_validation.py`: `test_self_intersection`, `test_unclosed_ring`, `test_source_is_not_rewritten`, `test_invalid_source_is_not_repaired` | PASS | GEOS binary64-topologie |
| Provenance validation | `application/source_import.py`, `live_source_validation.py` | `test_source_import.py`: `test_invalid_feature_and_geometry_provenance_rejected`; `test_live_source_import.py`: `test_changed_capture_metadata_or_raw_rejected`, `test_live_reparse_rejects_changed_mapping` | PASS | TLS en lokale Python-code/evidence zijn vertrouwd |
| Pagination | `adapters/pdok_bgt.py:fetch` | `test_pdok_bgt_fetch.py`: `test_multi_page_and_manifest`, `test_continuation_cycle`; `test_live_source_import.py`: `test_live_multipage_and_retry_replay` | PASS | Live next-request moet vaste queryscope behouden |
| Next-link security / geen arbitrary URL | `adapters/pdok_bgt.py:_continuation`, `pdok_live.py:validate_live_request` | `test_pdok_bgt_security.py`: `test_forbidden_continuations_never_reach_transport`; `test_pdok_live.py`: `test_scope_and_metadata_rejected_before_connection` | PASS | Alleen vaste PDOK pand-scope |
| Budgets/timeouts | `adapters/pdok_bgt.py:FetchBudgets`, `pdok_live.py` | `test_pdok_bgt_security.py`: `test_exact_terminal_and_pending_budget_boundaries`, `test_request_deadline_includes_successful_parsing`; `test_pdok_live.py`: `test_byte_cap_during_read`, `test_total_deadline_including_blocked_connect_and_body` | PASS | OS-DNS-worker kan na caller-timeout nog wachten |
| Retry/failure behavior | `adapters/pdok_bgt.py:fetch` | `test_pdok_bgt_security.py`: `test_all_retryable_statuses_have_bounded_attempts_and_raw_evidence`, `test_transport_errors_after_partial_page_are_not_retried`, `test_redirects_and_unexpected_status_never_retried_or_followed` | PASS | Retry-After HTTP-date niet ondersteund |
| Query completeness / incomplete nooit trusted | `domain/source_validation.py`, `application/source_import.py` | `test_source_validation.py`: `test_unresolved_next`, `test_missing_feature`, `test_unproven_page_chain`; `test_source_import.py`: `test_incomplete_fetch_never_promotes_and_retains_partial_evidence` | PASS | Provider kan onbekende data/next-links weglaten |
| Geen point-in-timeclaim | `domain/source_validation.py`, `application/source_import.py` | `test_source_validation.py`: `test_not_guaranteed_never_upgraded`; `test_source_storage.py`: `test_consistency_is_independent_from_completeness` | PASS | NOT_GUARANTEED blijft behouden |
| Trusted promotion / adapter heeft geen capability | `application/source_import.py`, `domain/design_validation.py` | `test_source_import.py`: `test_only_trusted_capability_can_construct_service`, `test_provider_cannot_promote_imported_geometry`, `test_reused_archive_is_revalidated_not_trusted_by_complete_label` | PASS | Betreft import; bestaand TESTDATA-fixturelabel apart beschreven |
| Atomicity | `application/source_import.py`, `infrastructure/store.py` | `test_source_import.py`: `test_failure_during_each_persistence_stage_rolls_back`, `test_failure_after_binding_rolls_back_promotion_revision_and_binding`, `test_success_audit_failure_rolls_back_every_trusted_write` | PASS | Raw staging staat bewust buiten publicatietransactie |
| Idempotence | `application/source_import.py:_existing` | `test_source_import.py`: `test_identical_reimport_reuses_immutable_records_and_revision`, `test_conflicting_reimport_fails_without_overwriting_history`; `test_live_source_import.py`: `test_live_reimport_noop_and_archive_immutable` | PASS | Elke poging mag eigen audit hebben |
| Revision binding | `infrastructure/source_store.py:_bind_revision`, `application/source_import.py` | `test_source_storage.py`: `test_binding_requires_existing_a02_revision`; `test_source_import.py`: `test_archive_and_binding_survive_reopen`, `test_binding_without_publication_evidence_is_not_a_noop` | PASS | Historische binding niet stilzwijgend heractiveerbaar |
| Stale propagation / reviewversie | `application/design_workflow.py:_invalidate` via source import | `test_source_import.py`: `test_new_snapshot_reuses_stale_propagation_and_preserves_history`, `test_failed_replacement_rolls_back_stale_and_previous_active_revision` | PASS | Geen nieuwe downstream ontwerpfunctionaliteit |
| Audit | `application/source_import.py`, `infrastructure/store.py` | `test_source_import.py`: `test_success_audit_transition_chain_is_explicit`, `test_failure_audit_unavailable_still_rolls_back_trusted_state` | PASS | Bij opslagstoring niet alle evidence duurzaam te garanderen |
| Offline replay / geen fetch | `application/source_replay.py` | `test_source_replay.py`: `test_successful_offline_replay_uses_existing_parser_no_fetch`, `test_exact_raw_bytes_and_deterministic_hashes`, `test_pages_features_geometries_and_provenance_equal` | PASS | Vereist opgeslagen raw, metadata en passende parserversie |
| Empty-storage reconstruction / geen promotion | `application/source_replay.py:reconstruct_into` | `test_source_replay.py`: `test_empty_storage_reconstruction_and_idempotent_repeat`, `test_reconstruction_does_not_read_original_storage`, `test_original_cannot_be_used_as_replay_target`, `test_target_failure_rolls_back` | PASS | Alleen archief, geen runtimebesluit of A02-binding |
| Live provider proof | `scripts/live_mastenbroekweg.py` | Geaccepteerd `docs/milestone-2c-phase6-proof.json`; `test_live_source_import.py`: `test_explicit_live_origin_import_and_offline_replay` | PASS | Een gedateerde waarneming, geen actuele nieuwe fetch |
| Networkless regression | `test.ps1`, `run_tests.py`; aparte opt-in livescript | Volledige 427 tests; aanvullende auditguard-run inclusief CLI-subprocessen | PASS | Python socket-auditguard, geen OS-/native-code-sandbox |
| Human Approval boundary | `application/approval.py`, `cli/main.py`, `domain/policies.py` | `test_runtime.py`: `test_agent_cannot_embed_approval`, `test_agent_session_has_no_human_service`; `test_design_workflow.py`: `test_a08_and_all_agents_denied_human_route`, `test_provider_approved_and_accepted_risk_denied`, `test_cli_human_routes_only_in_isolated_storage` | PASS | Vertrouwde lokale CLI; externe authenticatie buiten scope |
| K00 boundary | `domain/policies.py:K00Policy`, source import | `test_runtime.py`: `test_k00_cannot_be_written_regenerated_or_modified`; `test_design_workflow.py`: `test_k00_and_raster_registration_denied` | PASS | Registratie afgeleid; geen wijziging aan K00 |
| TESTDATA/provider separation | `adapters/source_transport.py`, source import/replay, live validation | `test_live_source_import.py`: `test_default_gate_rejects_provider_origin`, `test_live_gate_rejects_testdata_origin`, `test_replay_rejects_origin_relabel_and_bytes` | PASS | Workflow/A01-scaffolding blijft TESTDATA, A02 heeft echte origin |

## Geaccepteerd livebewijs

Bron: [Fase 6 compact bewijs](milestone-2c-phase6-proof.json), onderdeel van
geaccepteerde commit `e38669791748dbd9e8a5f3d899c632c4ae9ed6de`.
Het bewijs is in Fase 7 gelezen en op onderlinge consistentie beoordeeld, niet
opnieuw live gegenereerd. De opgeslagen rapportage en het geaccepteerde script
bewijzen ook netwerkgeblokkeerde replay en herbouw naar een tweede lege database.

| Onderdeel | Waarneming van de geaccepteerde run |
|---|---|
| Datum/tijd | 25 september 2026, `2026-09-25T13:45:41.264675+00:00` |
| Locatie | Mastenbroekweg 2, 6006 PT Weert, Nederland |
| Collection / endpoint | `pand`; `https://api.pdok.nl/lv/bgt/ogc/v1/collections/pand/items` |
| BBOX EPSG:28992 | `176492.301,360605.561,176992.301,361105.561` |
| HTTP / formaat | 200 / JSON-FG FeatureCollection; `application/vnd.ogc.fg+json` |
| Content-Crs | `<http://www.opengis.net/def/crs/EPSG/0/28992>` |
| coordRefSys | `http://www.opengis.net/def/crs/EPSG/0/28992` |
| Pagina's / features / numberReturned | 1 / 241 / 241 |
| Next-link / bytes | Geen / 279431 |
| Snapshot ID | `phase6/mastenbroekweg/20260925T134541264675Z` |
| Trusted promotion / revision | PASS; EXISTING_VALIDATED; `A02/v1` |
| Audit | `source_import_completed`, VALIDATING -> COMPLETE, query_scope_complete=true |
| Offline replay / empty-storage reconstruction | PASS; raw/geometry/provenance/manifest gelijk; socket/DNS geblokkeerd |
| Point-in-time consistency | NOT_GUARANTEED |

Raw SHA-256:
`6510926f1a7fb81797f328c63f392c3a6e9fc2c76b7bd06245d723ad4cc92e11`.

Snapshot manifest SHA-256:
`375076580961948a1f165941746b86ac48ce50f386172a9f0d8c2afefa658172`.

De exacte geencodeerde request-URL staat in het compacte bewijs. **241 is een
waarneming van deze run, geen permanente verwachting of hardgecodeerde broncount.**
De herkomst blijft UNVALIDATED_PROVIDER_RESPONSE; dat is de oorspronkelijke
transportclassificatie, onderscheiden van de na trusted validatie toegekende
geometriestatus EXISTING_VALIDATED.

De analyse-bbox heeft uitsluitend rol TESTCASE_ONLY_ANALYSIS_GEOMETRY en purpose
MILESTONE_2C_MINIMAL_PROOF. Het door de gebruiker opgegeven BAG-centroid
`POINT(176742.301 360855.561)` is context, geen nieuwe BAG-import. De bbox is geen
ProjectGeometry, eigendoms-, kadastrale, ontwerp- of beleidsgrens.

## Finale regressie en netwerkcontrole

Reguliere uitvoering: `./test.ps1`; 427 tests, 58.276 s, exitcode 0, OK.
Log: `.tools/phase7-regression.txt`. De bestaande tests gebruiken projectlokale
geisoleerde opslag; CLI-approvaltests raken de echte demo niet.

De normale runner ontdekt alleen `tests/test_*.py`. Het livescript staat onder
`scripts/` en vereist expliciet `--live-mastenbroekweg`. PDOK-transportunittests
mocken HTTPSConnection; import/replay/securitytests blokkeren socket/DNS en
gebruiken uitsluitend synthetische evidence. De oudere OpenAI-tests gebruiken
ook een fake HTTP-transport. Er zijn geen installaties/downloads in test.ps1.

Aanvullend is exact dezelfde `./test.ps1` uitgevoerd met een projectlokale
`sitecustomize.py`, via tijdelijk PYTHONPATH, die een CPython-audithook installeert:
ieder `socket.*` event wordt gelogd en met RuntimeError geweigerd. De bestaande
CLI-subprocessen erven deze omgeving. De guard registreert bij startup per proces
INSTALLED; PYTHONPATH wordt na uitvoering hersteld. De kern van de guard is:

```python
def deny_network(event, args):
    if event.startswith('socket.'):
        record('BLOCKED', event)
        raise RuntimeError('PHASE7_NETWORKLESS: ' + event)
sys.addaudithook(deny_network)
record('INSTALLED')
```

Guard en proceslogs: `.tools/phase7-network-guard/`; suite-log:
`.tools/phase7-networkless-regression.txt`. Deze extra uitvoering beantwoordt de
expliciete NETWORKLESS-vraag; zij verruimt geen product- of testfunctionaliteit.
De guard is geen sandbox tegen kwaadwillende Python/native code en blokkeert
niet het door Windows afgehandelde filesystemverkeer naar de projectshare.

Aanvullende guard-run: **427 tests, 57.039 s, exitcode 0, OK**.
Guard geladen in **18 Python-processen**, **0 socketpogingen**.
Daarmee is NETWORKLESS bevestigd voor deze volledige suite, inclusief haar
Python CLI-subprocessen. Geen live providerrequest uitgevoerd tijdens Fase 7.

`git diff --check` en `git diff --cached --check`: PASS.
De code en tests blijven exact gelijk aan de geaccepteerde Fase 6-baseline.

## Resterende bekende beperkingen en afsluitbesluit

- Dit is de beperkte PDOK BGT pand MINIMAL_PROOF. Geen generieke GIS-import,
  productiegeschiktheid, nieuwe collectie, ontwerpfunctionaliteit of volgende
  milestone wordt vrijgegeven. Bestaande regressietests voor andere rollen
  activeren die rollen niet in de echte projectruntime.
- Querycompleteness is consistentie van de ontvangen querybundel en vervolgketen,
  geen onafhankelijke garantie dat de provider niets heeft weggelaten en geen
  historische of atomaire point-in-time snapshot. NOT_GUARANTEED blijft expliciet.
- Collectionmetadata zijn de door de caller opgegeven RD-contractverwachting,
  geen live opgehaalde metadata. De response bevestigde RD via Content-Crs en
  coordRefSys. Semantisch fout gelabelde coordinaten zijn niet altijd aantoonbaar
  uit alleen hun numerieke waarden; daarom wordt CRS nooit geraden.
- Hashing bewaart exacte decimale structurele identiteit; topologievalidatie
  gebruikt Shapely/GEOS binary64. Geen automatische repair of CRS-transformatie.
  Ondersteuning blijft beperkt tot de bestaande 2D-geometrietypen.
- De live proof gebruikt TESTDATA-workflow/A01-scaffolding, een expliciet door de
  gebruiker opgegeven testcasegeometrie en echte A02-provider-evidence. Legacy
  presentatie/ontwerpflows zijn geen in deze milestone gevalideerde consumenten
  van live bronnen. Origin en geometry-status moeten afzonderlijk worden gelezen.
- Python-code, TLS-stack, lokale bestanden en de lokale CLI zijn vertrouwd.
  Capabilities beschermen de reguliere interfaces, niet tegen kwaadwillende
  Python-plugins of een beheerder die code/databasebestanden wijzigt. Voor zulke
  plugins of externe callers zijn procesisolatie en authenticatie vereist.
- De caller-timeout is begrensd; een daemon-worker kan nog op OS-DNS wachten en
  controleert annulering voor de GET. Geen procesisolatie of nieuwe concurrency-
  architectuur. Bestaande single-host SQLite-/netwerksharebeperkingen blijven.
- Duurzame failure-evidence kan bij een opslagstoring niet gegarandeerd worden;
  trusted publicatie blijft dan achterwege en beschikbare captures blijven in de
  exception. Retry-After HTTP-date en afwijkende live vervolgscope falen gesloten.
- Offline reproductie vereist de vastgelegde raw bodies, capturemetadata,
  analysegeometrie en passende parser/validator. Het compacte Git-rapport bevat
  hashes/metadata, niet de volledige providerpayload. De geaccepteerde originele
  en gereconstrueerde archieven staan lokaal onder
  `runtime/phase6-live/20260925T134541264675Z/` en zijn niet opnieuw live opgebouwd.

Geen open blocker binnen de overeengekomen scope. De volledige regressie is groen,
de architectuurinvarianten zijn intact binnen de expliciete vertrouwensgrenzen,
Fase 1 t/m 6 vormt een coherente keten en het geaccepteerde livebewijs blijft geldig
als bewijs van de gedateerde run. De reviewbranch wordt uitsluitend ter beoordeling
gepusht; geen merge, verdere masterwijziging of volgende milestone.

MILESTONE_2C: PASS
