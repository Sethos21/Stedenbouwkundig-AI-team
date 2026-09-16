# Milestone 2C — architectuurinventarisatie

Datum: 16 september 2026. Repository: \\BERNHEZE-DC01\gebruikers$\seth\Documents\Codex Desktop\AI ontwerpteam. HEAD: **c03098f — Milestone 2B.1 - review findings resolved**.

Dit document onderscheidt huidige implementatie, ontbrekende functionaliteit en voorstellen. De werkboom was aanvankelijk schoon. Alleen dit rapport wordt gewijzigd. Geen implementatie, packages, databasewijziging, commit of push.

Onderzoek: code, configuratie, fixtures, tests en bewijsdocumenten gelezen; twee databases via SQLite mode=ro geïnspecteerd. Geen applicatie-CLI gestart: ook leescommando's construeren Store en schrijven auditexport. Geen tests uitgevoerd omdat de architectuur uit code/tests vastgesteld kon worden en er geen codewijziging is. Historische 114/114 tests zijn geen verse testrun. Openbare technische documentatie geraadpleegd; geen GIS-features gedownload, credentials gebruikt of integraties geactiveerd. Bronpaden hieronder zijn relatief aan src/bvc_ai/, tenzij anders vermeld.

## 1. Executive summary

**GO WITH CONDITIONS** voor een beperkt A02-importproof. Revision-gates, stale propagation, transactionele audit en afzonderlijke Human Approval zijn bruikbaar. Algemene GIS-validatie, externe bronimport en reproduceerbare snapshots ontbreken.

- DesignObject.geometry_ref bestaat als str maar verwijst naar synthetische coördinaten in task.geometry_registry.
- SQLite heeft alleen tasks en audit. Geometrie, revisions, findings en reviews zijn geneste taak-JSON.
- EXISTING_VALIDATED is nu rolgebonden TESTDATA, geen algemene topologische validatie.
- A02 kent legacy-inventarisatie en synthetische M2B-registratie, geen officiële GIS-fetch.
- Replay bewijst herhalen op dezelfde database zonder duplicatie, geen reconstructie uit bronbytes.
- Advies: **JSON-geometrie met expliciete CRS in afzonderlijke immutable records binnen dezelfde SQLite**, plus raw responses voor replay. Geen BGT-geometrieën in het steeds herschreven taakdocument.

Bewijs: domain/design.py::DesignObject, application/design_workflow.py::create/step, infrastructure/store.py::Store, scripts/validate_milestone_2b.py::main.

**Statusafwijking:** runtime/GIS-001 is al APPROVED met human approval, terwijl AGENTS.md uitgaat van wachten op de mens. Dit onderzoek heeft geen besluit gemaakt/veranderd. De M2B-demo wacht wel zonder approval. Historie behouden en 2C-opslag isoleren.

## 2. Repository architecture

| Laag | Concrete bestanden/symbols |
|---|---|
| Legacy domein | domain/models.py: Task, SourceReference, AgentOutput, Review, Approval, AuditEvent. domain/policies.py: statusmachine, validate_output, K00Policy. |
| Ontwerpdomein | domain/design.py: DesignObject, AgentTask, Finding, ReviewResult, RevisionDependency, Handoff, DecisionRequest, HumanDecision, STEPS/current_output. |
| Validatie | domain/design_validation.py::validate_proposal; domain/design_verification.py::rectangle/resolution_evidence. |
| Orchestration | application/workflow.py::Workflow; application/design_workflow.py::DesignWorkflow. |
| Human Approval | application/approval.py::HumanApprovalService; capability via vertrouwde CLI/isolated tests. |
| Agents | agents/provider.py::AIProvider/DeterministicTestProvider, design_mock.py::design_proposal, openai_provider.py::OpenAIProvider, factory.py, smoke.py. Geen acht aparte agentmodules. |
| Adapters | adapters/repositories.py: DocumentRepository/GISAdapter en mocks; design_presentation.py::DesignPresentation. |
| Persistence/audit | infrastructure/store.py::Store; SQLite en JSONL-projectie. |
| Composition root | cli/main.py::main, bvc_ai.py, bvc-ai.ps1. |
| Configuratie | config/agents.json: zeven legacy-rollen, A01/A02/A07 actief. M2B apart acht rollen in domain/design.py::ROLES/STEPS; A08 niet in legacy-config. |
| Fixtures/tests | examples/gis-001.json, design-test-001.json; vier tests/test_*.py-modules, run_tests.py/test.ps1; scripts/validate_milestone_2b.py. |
| Runtime/documentatie | runtime/, .tools/python/test-runs/validation-runs (Git ignored); docs/ en docs/reviews/. |

Patroon: gelaagd, met ports-and-adapters via Protocol. Applicatieservices gebruiken rechtstreeks store.db/_save; geen volledige repository-onafhankelijke unit-of-work of distributed runtime.

## 3. Current geometry model

DesignObject heeft geometry_ref: str, geometry_status: str, revision_id: str, source_basis: list, created_by, properties en review/findingrefs. Frozen dataclasses zijn niet diep immutable; nested lists/dicts blijven muteerbaar en persistence gebruikt dictionaries.

DesignWorkflow.create kopieert examples/design-test-001.json::geometry_registry naar tasks.body. Records zoals fixture/boundary bevatten kind=source, source_status=TESTDATA, crs=SYNTHETIC_LOCAL_METRES en vier XY-paren. Design-records hebben kind=design.

Dit is eigen JSON, geen GeoJSON: geen geometry type, geneste polygonringen of expliciete ringsluiting. Geen WKT/WKB/BLOB-geometrie of externe geometrybestanden. MockGISAdapter heeft daarnaast een losse K00-placeholder met geometry=None, niet de ontwerpopslag.

Geen geometryhash, CRS-transformatie/register, spatial index of generieke parser. Polygon/MultiPolygon/LineString/Point worden niet als GIS-types ondersteund; rechthoekvlakken zijn geen algemene Polygon-implementatie.

Operaties: DesignWorkflow._apply berekent DEVELOPMENT_FIELD-oppervlakte met shoelace en capaciteit int(area/10000*density). Geen holes, multipart, topologie of algemene CRS-eenhedencontrole. design_verification.rectangle controleert uitsluitend vier eindige asparallelle design/TESTDATA-punten in synthetische meters. resolution_evidence controleert twee exacte A04/A05-fixtureregels en vrije stroken; onbekende gevallen leveren geen bewijs. Geen algemene clipping/intersection/buffer/union/repair.

validate_proposal controleert schema/rol/objecttype/ref/source_basis; 200.000 is de limiet op geserialiseerde proposal-lengte, geen GIS-importbudget.

Immutability:
- K00Policy.authorize weigert niet-read op genormaliseerd K00; andere writes alleen origin/classification=derived. MockGISAdapter.register_layer past dit toe, reads geven kopieën.
- validate_proposal eist alleen bij A02 EXISTING_VALIDATED/source-ref, andere objectschrijvers PROPOSED/design-ref. A01/reviews schrijven geen objecten.
- _apply voegt revision-specifieke objecten toe; providers krijgen contextkopieën; DesignPresentation.update weigert en audit writes.

Dit beschermt applicatieroutes, niet directe SQL/vertrouwde Python. Geen immutable registry-API/hash/SQL-trigger. Een oude ref anders invullen verandert historische geometrie zonder revision. Nieuwe geometrie moet daarom een nieuwe ref krijgen. Tests: test_a03_cannot_write_existing en test_presentation_cannot_modify_source_or_geometry in test_design_workflow.py.

## 4. SQLite/persistence model

Schema bevestigd uit Store.__init__ en beide runtime-databases:

| Tabel | Kolommen | Relaties/constraints |
|---|---|---|
| tasks | id TEXT PRIMARY KEY, body TEXT NOT NULL | Geen FK/JSON-check; geen afzonderlijke expliciete NOT NULL op id. |
| audit | seq INTEGER PRIMARY KEY, body TEXT NOT NULL | Geen FK naar tasks of aparte taak/tijdindex. |

Geen aparte revision/object/source/geometry/provenancetabellen. Relaties zijn JSON: active_revisions, outputs[].revision_id/input_revisions, objects[].revision_id/geometry_ref/source_basis, dependencies, reviews, finding_history, handoffs. Audit koppelt via body.task_id/details.

| Database | Status | Taak-JSON UTF-8 | Inhoud |
|---|---|---:|---|
| runtime/state.sqlite3 | GIS-001: APPROVED | 2.516 bytes | 1 output, 0 objecten/geometrieën, 24 events. |
| runtime/milestone-2b/state.sqlite3 | DESIGN-TEST-001: AWAITING_HUMAN_APPROVAL | 51.255 bytes | 13 outputs, 11 objecten/geometrieën, 31 events, geen approval. |

Beide: journal_mode=delete, user_version=0. Interpreter CPython 3.12.14, SQLite-library 3.53.1. Een UNC-URI-poging faalde vóór openen; relatieve file:-URI met mode=ro werkte. Dit is runtimehistorie, geen nieuwe validatie.

Store maakt map/schema met CREATE TABLE IF NOT EXISTS, timeout=10, DELETE-journaling. Geen migrationsframework/schema-versioning. _save upsert de hele taak. events(task_id) leest alles en filtert in Python.

DesignWorkflow.step doet providerwerk vóór transactie, daarna BEGIN IMMEDIATE, herlezing/idempotentiecontrole en task != before. State/success-audit committen samen; fouten rollen terug, daarna aparte step_failed-audit. Als die opslag ook faalt, geen gegarandeerd foutrecord. HumanApprovalService gebruikt hetzelfde rollback-eerst-principe. Legacy Workflow.run heeft meerdere transacties; RUNNING-crashrecovery ontbreekt.

Idempotentie: task.idempotency met SHA-256 van step/actor/aangeboden expected_inputs. Bij None ontbreken werkelijke revisions in fingerprint, al worden ze bij succes opgeslagen. Oude key is replay van oude opdracht, geen nieuwe import. Human-idempotentie apart. Geen feature-deduplicatie/source-versionconstraint.

Referential integrity is applicatielogica: geen FK, foreign_keys=ON, array-ID-uniqueness of immutable triggers. Audit niet cryptografisch gekoppeld. Tests: test_transaction_failure_after_writes_rolls_back_audit_and_domain, test_two_store_conflict_cannot_commit_stale_proposal en F2-tests in test_milestone_2b1.py.

## 5. Existing dependencies

Python met PowerShell-launchers, JSON en SQL via Python. README vereist Python 3.12+; lokaal 3.12.14. Geen applicatie-pyproject/requirements/lockfile/package.json aangetroffen buiten tooling. Geen package-installatie nodig volgens README. .tools/uv-cache is toolingartefact, geen bewijs van actief uv-applicatieproject.

Aanwezig: sqlite3, json, hashlib.sha256, http.client.HTTPSConnection, dataclasses/enums, math.isfinite, unittest/unittest.mock/tempfile/subprocess. Validatie is eigen code. INVENTORY_SCHEMA/REVIEW_SCHEMA zijn dictionaries, geen algemene lokale schema-validator.

Niet aangetroffen als projectdependency of ondersteuning: Shapely, pyproj, PROJ, GEOS, GDAL/OGR, Turf, SpatiaLite, GeoPackage-tooling, GeoJSON-parser, WKT/WKB-codec, CRS-transformatie, requests/httpx, jsonschema, Pydantic. JSON-parsing is geen GIS-validatie. Dit is geen machinebrede software-inventarisatie.

## 6. Provenance/audit/replay

SourceReference: source_id/label/source_type/source_status/location/geometry_origin als strings. URL/datasetnaam passen in vrije tekst; endpoint/bronversie/snapshot niet getypeerd. Legacy accepteert alleen fixture/TESTDATA. VERIFIED_SOURCE bestaat als enum, geen werkende externe validatieroute.

AgentOutput bewaart input_refs/source_refs/type/status/agent/timestamp/output_version. Workflow.run audit source_registered. M2B gebruikt source_basis-registerrefs en input_revisions. Geen provenance_ref/SourceSnapshot of exacte externe bronstandbinding.

Providerherkomst is tekst in recommendations/findings. _apply audit object/revisionmetadata, geen onafhankelijk gehashte brongeometrie; audit alleen reconstrueert register niet volledig.

scripts/validate_milestone_2b.py::main draait dezelfde demo tweemaal op dezelfde database. create/run laten actuele stappen staan: idempotent hervatten, geen event sourcing of lege-opslagreplay. now()-tijdstempels variëren tussen nieuwe runs. code_identity/run_current_tests bindt HEAD/bronmanifest/testlog, geen GIS-bronbytes.

Nodig voor externe reproduceerbaarheid: endpoint/dataset/collection, query/BBOX/CRS, peildatum, request/response-CRS, headers/media type, fetchinterval, pagina/cursors, raw bytes/hashes, feature-ID/versie/validiteit/properties, geometryhash, parser/validator/canonicalisatieversie en transformatiepipeline. Volledigheid binnen queryscope onderscheiden van gegarandeerde consistente datasetstand. Query/ophaaltijd alleen onvoldoende.

## 7. Revision/stale model

_apply maakt <step>/v<n>; inputs combineert directe STEPS-afhankelijkheden en transitieve revisions. Historie blijft, active_revisions kiest actueel.

_invalidate markeert oude/afhankelijke outputs stale, verwijdert actieve refs, vult stale_reviews en audit dependencies_invalidated. RESOLVED-findings worden OPEN als hun oplossende review stale is, met history/event. Geen algemene finding-stalevlag; verplichtingen blijven. ACCEPTED_RISK wordt niet automatisch heropend.

current_output controleert actuele inputs; check_design_approval actuele integratie/pakket/reviews. Tests: test_a02_revision_stales_downstream_retains_history en test_upstream_change_reopens_stale_resolutions.

Nieuwe brongeometrie past als nieuwe snapshot + A02-revision + geometry_ref. In-place registrywijziging is onzichtbaar. Snapshot immutable aan A02-output binden; bestaande transitieve dependencies hergebruiken. Invalidatie is grof op stapniveau. _gate weigert heruitvoering van APPROVED/REJECTED: latere bronupdates vragen nieuwe taak/projectversie of expliciet vervolgbeleid, nooit besluitmutatie.

## 8. Current A02 implementation

Legacy: AIProvider.inventory(brief, revision_points), gis-001-fixture plus vorige A07-findings. Gesloten payload sources/missing_data/geometry_uncertainties/k00_discrepancies/recommendations. policies.validate_output eist TESTDATA. Workflow: A01 → A02 → A07 exacte output_version → mens.

M2B: AIProvider.design_step met contextkopie/register/input_revisions. design_mock.design_proposal('A02') levert projectgrens/watergang/drie bronzones met fixture-refs. Alleen SOURCE_TYPES/EXISTING_VALIDATED. Na A01_START; voedt A06/A08_GATE/A03_HYPOTHESIS en transitief downstream.

Geen officiële fetch/topologie/CRS-transformatie/promotie. Mock kiest refs, geen coördinaten. OpenAIProvider.design_step weigert M2B; inventory genereert tekst en kopieert bronitems lokaal terug.

Aansluiting: vertrouwde application/source_import.py::SourceImportService onder A02 met aparte read-only adapter buiten AIProvider. Providers krijgen beperkte refs/data, geen opslag/promotiecapability. GISAdapter.register_layer is derived-writecontract, geen officiële importgrens.

## 9. External API infrastructure

OpenAIProvider._request is enige werkende netwerkadapter: vaste HTTPS-host/POST, sockettimeout default 30/maximaal 120 seconden, maximaal 1.000.000 antwoordbytes, verbinding sluiten, envelopevalidatie/gesaneerde fouten. Geen retries/rate-limiter/cache/rawarchief/pagination/conditional GET/responsehash. 429 alleen gemeld.

Transport buiten domein; geen read-only GIS-client. Neem patroon/tests over, niet OpenAI-authenticatie/requestcode. test_openai_provider.py mockt HTTPSConnection en test errors/timeout/oversize/malformed/incomplete JSON.

2C vereist begrensde GET/pagination, gecontroleerde next-links, page/feature/byte/tijdbudget, retrybeleid, rawopslag en volledigheid. Geen netwerk in domain of GIS-fetch via LLM.

## 10. Test architecture

| Soort | Bestaand | 2C |
|---|---|---|
| Unit/domein | test_runtime.py status/K00; test_design_workflow.py schema/rollen; test_milestone_2b1.py verificatie/lineage. | Parser, CRS/axis-order, hash, promotiebeleid. |
| Integratie/SQLite | Echte Store, deterministische/gemuteerde providers; rollback/twee Store-conflict/F2-tests. | Fake transport + echte geïsoleerde SQLite; fouten tussen staging/promotie/audit. |
| CLI/E2E | test_cli_demo_isolated_repeatable_and_no_approval; test_cli_human_routes_only_in_isolated_storage. | Geïsoleerde import/replay/stale, echte runtime intact. |
| Audit/replay | test_all_steps_idempotent_including_package, A02-stale-tests, validatiescript. | Lege-opslagreplay, corrupt/missing bytes, manifesthash. |
| HTTP | unittest.mock in test_openai_provider.py. | Cursorcyclus, 429/5xx/timeout, CRS, incomplete pagina. |

TemporaryDirectory onder .tools/test-runs, Store gesloten; unittest-discovery via run_tests.py/test.ps1. Geen aparte pytest-laagindeling. Netwerkloze suite; fixtures/providers deterministisch, wall-clock timestamps niet.

Latere fixtures: Point/LineString/Polygon/MultiPolygon/holes, null/empty/invalid, niet-eindig, onbekende CRS, dubbele/conflicterende versies, bronupdates/incomplete pagination. Synthetisch blijft TESTDATA; opgenomen echte responses houden echte provenance en offline context. Live smoke opt-in buiten test.ps1. Historisch 114/114 in docs/reviews/MILESTONE_2B1_VALIDATION.md; niet opnieuw gedraaid. Validatiescript schrijft meerdere bewijsbestanden en is daarom nu niet uitgevoerd.

## 11. GIS integration risks

| Risico | Beheersing |
|---|---|
| Grote geometrie/veel features | _save herschrijft taak, context deepcopies; aparte records/compacte context/budgetten. |
| SQLite/SMB | Eén writer, korte promotietransactie, fetch daarbuiten; DELETE garandeert geen betrouwbare netwerklocking. |
| JSON/binary | WKB lost taak-herschrijven/bronversies niet op; eerst records scheiden, later meten. Geen benchmark uitgevoerd. |
| Hashing | sort_keys dekt ringstart/orientatie/multipart/-0/precision/CRS niet. Raw-, structurele en topologische identiteit scheiden. |
| CRS/floats | Axis-order/eenheden bewijzen; niet raden. Pipeline/engine/gridversies pinnen; geen stilzwijgende rounding/repair. |
| Pagination | Limiet met next = incomplete; cursorcyclus/fout nooit complete; scope vastleggen. |
| Historische BGT | ID of geometryhash alleen onvoldoende versie-identiteit; peildatum/beëindigde objecten/versievelden vastleggen. |
| Bronupdates tijdens fetch | Laatste pagina geen bewijs consistente datasetversie; fetchinterval/bronversie en onzekerheid bewaren. |
| Duplicaten | Manifesthash/feature-versionconstraints; zelfde import geen revisionstorm. |
| Partial import/transacties | Staging mag blijven; active/validated pas na checks. Promotie/revision/stale/audit atomisch. |
| Stale/accepted risks | Nieuwe refs/revision; eerdere ACCEPTED_RISK-herbeoordeling ontwerpen. |
| Auditvolume | events/export leest alles; refs/manifests loggen, niet telkens geometrie dupliceren. |
| Human Approval/K00 | Bronvalidatie geen APPROVED; geen human capability of afgezwakte K00-policy. |
| Latere rasters | BGT-vectorproof is geen AHN/luchtfoto-contract; uitstellen. |

SQLite waarschuwt voor netwerkfilesystemgedrag; sluit aan op README/docs/architecture.md. [SQLite network caveats](https://www.sqlite.org/useovernet.html).
PDOK documenteert historie, peildatum, cursorpagination en maximaal 1.000 features per bevraging. Dit zijn contractvoorwaarden, niet alleen optimalisaties. [PDOK BGT-documentatie](https://www.pdok.nl/ogc-apis/-/article/basisregistratie-grootschalige-topografie-bgt-).

## 12. Storage strategy comparison

Architectuurafweging, geen benchmark. Elk formaat vraagt provenance/versies/validatie.

| Optie | Wijziging/onderhoud/tests/portability | Determinisme/hash | Performance/GIS/QGIS | Audit/replay |
|---|---|---|---|---|
| A JSON/GeoJSON in SQLite | Kleinste json/sqlite3-aansluiting; inspecteerbaar; aparte records nodig. | Canonicalisatie/CRS/schema expliciet. | Meer parse/bytes; geen spatial query. QGIS via export. | Eén transactie mogelijk, raw apart. |
| B WKT in SQLite | Extra codec/validator; leesbaar; CRS apart. | Precision/writer/ringvolgorde vastleggen. | Geen index/engine; QGIS via WKT-export. | Snapshotstructuur/raw blijven nodig. |
| C WKB/BLOB in SQLite | Bytes ondersteund, codec/engine ontbreekt; minder inspecteerbaar. | Endianness/dimensie/variant/CRS/normalisatie. | Kansrijk grotere volumes; BLOB nog geen GIS-laag. | Codec/roundtrip deel bewijs; één DB. |
| D SpatiaLite | Native extensie/deployment/testmatrix, groter onderhoud. | Engine/serializer/CRS pinnen. | Spatial SQL/indexen/GIS-integratie. | Meer schema/extensie-afhankelijkheid. |
| E aparte GeoPackage | Extra bestand/writercontract; tooling ontbreekt. | Encoding/schema/writer vastleggen. | Goede latere QGIS-inspectie/uitwisseling. | Cross-file herstel; eenvoudiger als export. |

**Advies A:** type/coordinates met expliciete CRS in versiegebonden records, niet tasks.body. Kleine schemauitbreiding gerechtvaardigd. Raw responses als BLOB is archivering, niet C als geometryformaat.

RD-data intern geometrie-JSON noemen, geen standaard RFC 7946 GeoJSON: die gebruikt WGS84. Ontvangen formaat/CRS behouden, export expliciet. [RFC 7946](https://www.rfc-editor.org/info/rfc7946/).
GeoPackage vereist eigen ruimtelijke metadata/encoding; SQLite met WKB is niet automatisch GeoPackage. [OGC GeoPackage](https://www.geopackage.org/spec140/). SpatiaLite brengt ruimtelijke functies/GEOS/PROJ-integratie. [SpatiaLite functies](https://gaia-gis.it/gaia-sins/spatialite-sql-latest.html).

Geen F aanbevolen: geen aanleiding voor PostGIS/objectstore/service. C later bij gemeten problemen of eenvoudiger engine-integratie. QGIS geen runtimevereiste.

## 13. Recommended architecture

Voorgestelde, nog niet bestaande namen:

| Component | Plaats/verantwoordelijkheid |
|---|---|
| SourceSnapshot/SourceFeature/GeometryRecord | domain/sources.py: immutable responsebundel/featureversie/geometrie; queryscope/pagina-manifest/completeness/validatorbewijs. |
| SourceAdapter | adapters/source_adapter.py naast GISAdapter; alleen lezen, geen Store/approval/promotie. |
| PDOKBGTAdapter | adapters/pdok_bgt.py: GET/pagination/budgetten/transportmetadata. |
| SourceImportService | application/source_import.py: vertrouwde A02 staging/validatie/promotie/revision. |
| Geometry/CRS-validator | domain/geometry_validation.py voor regels; engine/CRS-adapter apart indien nodig. Geen LLM/repair. |
| Source/geometry-opslag | infrastructure/source_store.py op dezelfde Store-connectie/transactie; raw/JSON/IDs/hashes. |
| Integratie | Gerichte DesignWorkflow/validate_proposal-snapshotbinding; CLI import/replay zonder human capability. |

Feature-identiteit: dataset/collection/object-ID plus bronversie of snapshotversie. GeometryRecord: CRS/dimensie/encoding/schema/hash/immutable inhoud. Snapshot verwijst naar raw pages/features; A02-output naar snapshot. SourceReference blijft leesbaar bronregister, geen vervanger.

Scheid FetchExtent/BBOX, ProjectGeometry, AnalysisGeometry. Clipping/transformatie produceert derived record met input-ref/bewerkingsprovenance; bron intact. Analysegeometrie is niet automatisch PROPOSED ontwerp; derived-analysissemantiek bepalen. Technische A02-promotie is geen menselijke/projectmatige goedkeuring. EXISTING_VALIDATED benoemt checks, niet juridische waarheid of projecttoebehoren.

## 14. Minimal Proof voorstel

Eén geïsoleerde taak, kleine BBOX, één collection (hoogstens twee), expliciete peildatum/historie. Geen andere bronnen/clipping/GIS-suite.

1. Query/CRS/peildatum en page/feature/byte/tijdbudget vastleggen; actueel API-contract/conformance controleren. PDOK vermeldt RD; exacte parameters/headers nog bewijzen.
2. GET buiten transactie; raw bytes/hashes/requestmetadata/pagina-cursors in staging. Next-links binnen broncontract.
3. Alle pagina's; budget met next = incomplete, geen promotie. BBOX zo nodig verkleinen; eerste N geen complete stand.
4. Feature-ID/versie/properties/geometrie parsen; response-CRS/type bewijzen. Liefst native RD; label toevoegen is geen transformatie.
5. Geometrieën binnen type-scope valideren. Invalid/null/unsupported blokkeert eerste complete proof. Polygon-topologie vraagt bewezen engine; JSON/finitechecks alleen onvoldoende.
6. Raw-, structurele geometry- en manifesthash berekenen met canonicalisatieversie; geen topologische equivalentieclaim.
7. Records/complete snapshot/A02-revision/invalidatie/success-audit atomisch publiceren; K00/TESTDATA behouden.
8. Offline lege-opslagreplay: dezelfde mapping/hashes/inhoudelijke validatie, timestamps apart. Zelfde-opslagreplay zonder duplicaten/revisions.
9. Fouttests: tweede pagina, duplicate/conflicting version, corrupt bytes, CRS, invalid geometry, promotiefout. Geen active partial snapshot; foutaudit zolang opslag beschikbaar.
10. Netwerkloos: gewijzigde snapshot → A02-revision/stale reviews; oude geometrie leesbaar, approval intact. Downstream teststub volstaat, geen live extra agentactivering.

Acceptatie: volledige kleine queryscope reproduceerbaar/valide/foutbestendig, niet alleen werkende HTTP. Volledigheid en punt-in-tijdconsistentie apart; zonder bronversiegarantie geen consistente gehele BGT-stand claimen.

## 15. Conflictcheck

Conflict = bestaand contract verhindert direct hergebruik; gap = ontbreekt, geen bewezen corruptie.

| Principe | Bevinding |
|---|---|
| Alleen A02 officiële bronpromotie | Rolgrens aanwezig. Conflict: validate_output alleen TESTDATA, forbidden blokkeert VERIFIED_SOURCE, defaults/_apply/report TESTDATA. Vertrouwde aparte route nodig, geen providerverruiming. |
| Downstream EXISTING_VALIDATED intact | Conform huidige rol/ref/append-routes; gap: registry niet verzegeld. |
| BBOX technisch | Gap; geen code die BBOX tot projectgrens maakt. |
| Project/Analysis apart | Gap; PROJECT_BOUNDARY wel, analyseconcept niet. |
| Brongeometrie intact | Providerroute wijzigt register niet; gap raw-immutability/hash. |
| Clipping derived | Gap: geen clipping/lineage. |
| Bronupdates revisions | A02-rerun conform; gap snapshotdetectie, in-place update ongeschikt. |
| Reviews stale | Conform nieuwe A02-revision/getest; bytes zonder revision onzichtbaar, ACCEPTED_RISK niet heropend. |
| Incomplete nooit complete | Gap completeness; huidige refcontrole onvoldoende voor echte promotie. |
| Geen LLM-aanvulling | Conform geregistreerde refs/OpenAI-tekst/design geweigerd; missing geometry blokkerend houden. |
| Human Approval intact | Conform service/capability/gates, geen productie-authenticatie. |

Werkelijk adapterconflict: GISAdapter.register_layer/K00Policy weigert niet-derived writes. Officiële bron via die route faalt. Apart sourcecontract; bron niet derived noemen, K00 niet afzwakken.
Scope-incompatibiliteit: create hard gekoppeld aan DESIGN-TEST-001/fixture-equality; CLI-design mock-only. Echte import niet als demo uitvoeren. Acht M2B-rollen zijn aparte context, geen opdracht A03–A06 te activeren.
Operationele afwijking: runtime/GIS-001 reeds APPROVED tegenover wachtinstructie. Behouden en isoleren, geen terugzetactie.

## 16. Concrete files/modules likely to change in 2C

- domain/models.py en design.py: provenance/snapshotbinding/echte broncontext, bestaande reviewsemantiek behouden.
- domain/design_validation.py: vertrouwde gevalideerde refs, gesloten providerrechten.
- application/design_workflow.py: broncontext/A02-binding, compacte context; synthetische area/capacity afschermen.
- infrastructure/store.py: schemaversie/migratie/gedeelde transactie voor aparte records.
- cli/main.py: geïsoleerde import/replay.
- adapters/design_presentation.py alleen bij echte contextweergave: TESTDATA-hardcoding contextbewust, writes verboden.
- Nieuwe modules §13, bronfixtures/tests; dependencymanifest/lockstrategie na enginekeuze.
- Milestone-documentatie/AGENTS-scope voor latere fetch expliciteren; historische bewijzen behouden.

## 17. Files/modules that should NOT change

- application/approval.py en human capability/identiteitsgrens.
- policies.K00Policy en legacy TESTDATA-regel niet afzwakken.
- agents/openai_provider.py/factory.py/smoke.py: geen GIS-import via AI.
- design_mock.py, design_verification.py, bestaande examples als synthetische baseline.
- Reviewownership/check_design_approval/iteratielimiet/stale-semantiek niet herontwerpen.
- config/agents.json: geen extra legacy-rollen activeren.
- runtime/**, approvals/audit, historische docs/milestone-2b-*, GIS-resultaten en MILESTONE_2B1_VALIDATION.md.
- Globale Git-config/andere projecten/financiële rapportagetool.

Latere gerichte wijzigingen behouden deze invarianten. Nu uitsluitend dit rapport.

## 18. Open decisions for GPT architect/regisseur

**Tien architectuurbeslissingen**:
1. Opslagcontract: A/aparte records, unique constraints/migratieversie.
2. Validatie-engine/dependencies: bewezen topologie/types; geen zelfgebouwde GIS-engine.
3. CRS: EPSG:28992/axis-order/dimensie/native RD; wanneer transformatie/gepinde pipeline.
4. Hash/canonicalisatie: raw/geometry/manifest/numeriek/volgorde/versie, structureel eerst.
5. Snapshot/bronversie: scope, complete versus consistent, historische ID/peildatum.
6. Import lifecycle: staging/failure/complete, retry/budget/resume/deduplicatie/atomiciteit.
7. A02/status: vertrouwde service/bewijs, geen providerpromotie/TESTDATA-herlabeling.
8. Ruimtelijke rollen: FetchExtent/ProjectGeometry/AnalysisGeometry, derived versus PROPOSED.
9. Updates: nieuwe snapshot nieuwe revision, dezelfde no-op; ACCEPTED_RISK/vervolg na definitief besluit.
10. Replay/deployment: lege opslag versus idempotentie, timestamps/single-writer/SMB/QGIS-export.

Grotendeels architect/regisseurwerk; niet elk punt vraagt gebruikersinput.

## 19. Questions that genuinely require Seth/user input

Geen antwoord nodig voor deze inventarisatie. Voor volgende opdracht:
1. Welk proefgebied als BBOX en is daarnaast een vastgestelde projectgrens beschikbaar?
2. Welke gebruiksvraag bepaalt collection/bronstand: actueel of historische peildatum? Architect kan technische budgetten voorstellen.
3. Mag de volgende milestone echte PDOK-read-only fetches en zo nodig projectlokale GIS-dependencies toevoegen, met behoud van demo's en zonder overige integraties? Dit onderzoek verleent die implementatieruimte niet.

Geen vraag om GIS-001 opnieuw te beslissen; nieuwe geïsoleerde 2C-opslag.

## 20. Final recommendation: GO WITH CONDITIONS

**GO WITH CONDITIONS** voor afgebakend A02-importproof. Bruikbare revision/audit/approvalbasis; brononderdelen lokaal toevoegen.

Voor acceptatie: echte broncontext, complete snapshots/immutable refs/raw-provenance, provideronafhankelijke geometry/CRS-validatie die gesloten faalt, atomische promotie/revision/stale/audit, offline replay/failure/duplicate-tests en behoud K00/approvals/TESTDATA/single-writer.

Storage: **JSON-geometrie met expliciete CRS in afzonderlijke immutable SQLite-records**, raw responses als bytes. Grootste risico: gedeeltelijke/veranderende import als complete gevalideerde bronstand publiceren zonder duurzame geometry/revisionbinding. Tien architectuurbeslissingen, drie latere gebruikersvragen.

Na schrijven stopt de opdracht. Geen GIS-code, databasewijziging, packages, commit of push.

