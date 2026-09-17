# Milestone 2C — Fase 1: source contracts en opslag

Baseline: master / e66b322be68eeb35eb19e32c182a9d4799bdc608.
Scope: document 11 v0.1 hoofdstuk 19, uitsluitend Fase 1.
Geen commit, live fetch, dependency-installatie of wijziging aan historische runtime.
Dit is geen eindvalidatie van Milestone 2C.

## Contracten

domain/sources.py bevat frozen dataclasses SourceSnapshot, SourceFeature,
GeometryRecord, RawResponse, SourcePage, CRSMetadata, FetchExtent en
RevisionBinding. Geneste JSON-payloads zijn immutable strings; lineage en
axis-order zijn tuples. ImportStatus bevat STAGING, VALIDATING, COMPLETE,
FAILED en INCOMPLETE. PointInTimeConsistency is onafhankelijk van completeness.

GeometryRecord bewaart intern type/coordinates JSON met expliciete CRS,
axis-order, dimensie, units en CRS-evidence. Dit heet geen RFC7946 GeoJSON.
GeometryRole onderscheidt SOURCE, DERIVED, PROJECT, ANALYSIS,
TESTCASE_ONLY_ANALYSIS en POLICY geometry. FetchExtent is een afzonderlijk
contract met BBOX, CRS en verwijzing naar analysis geometry. Analyse verleent
geen ontwerpbevoegdheid. Een SourceFeature verwijst alleen naar SOURCE_GEOMETRY.

RawResponse controleert SHA-256 tegen exacte bytes. Geometry- en manifesthashes
en canonicalization_version zijn verplichte velden; berekening en semantische
validatie hiervan horen in Fase 2. De test-hashes zijn uitdrukkelijk test-only.
Er is nog geen topologievalidator, CRS-transformatie of completeness-validator.
De huidige contracten zijn expliciet 2D; geen impliciete Z-interpretatie.

## SQLite

Store initialiseert source_schema.migrate op zijn bestaande connectie.
PRAGMA user_version=0 (legacy of leeg) migreert naar 1 met BEGIN IMMEDIATE.
DDL en user_version committen samen; een fout rolt beide terug. Onbekende
versies falen gesloten. Nogmaals openen is idempotent. foreign_keys en
recursive_triggers zijn per Store-connectie ingeschakeld.

Bestaande tasks(id,body) en audit(seq,body) blijven byte-identiek behouden.
De migratie is uitsluitend op tijdelijke testdatabases uitgevoerd; bestaande
runtime is niet geopend. Bij later openen van een bestaande Store zal de
additieve migratie automatisch plaatsvinden. Geen destructieve down-migration.

| Tabel | Identity / relaties |
|---|---|
| geometry_records | PK geometry_ref; structurele hash, canonicalisatieversie, rol, record-JSON inclusief geometrie/CRS/provenance |
| geometry_lineage | PK geometry_ref + parent_geometry_ref; beide FK naar geometry_records |
| raw_responses | PK raw_response_hash; BLOB body |
| source_snapshots | PK snapshot_id; unique provider/dataset/collection/canonicalization_version/manifesthash; FK analysis_geometry_ref |
| source_pages | PK snapshot_id/page_number; FK snapshot + raw response; transportmetadata in record-JSON |
| source_features | PK snapshot_id/source_id; FK geometry_ref + samengestelde FK naar pagina; bronversie/properties/provenance in record-JSON |
| source_revision_bindings | PK task_id/revision_id; unique task_id/snapshot_id; FK task + snapshot |

Een feature-ID is uniek binnen een snapshot van één collection. Bronversies
kunnen tussen snapshots verschillen; ontbreken van provider-versie wordt
expliciet als null bewaard, geen verzonnen versie. Snapshot-identiteit moet in
Fase 2 scope/actualiteitsvraag/inhoud opnemen in de manifesthash.

UPDATE, DELETE en vervanging van bestaande identities worden door triggers
geblokkeerd, inclusief REPLACE via alternatieve unique keys. Bestaande refs
kunnen geen nieuwe inhoud krijgen. Identieke inserts via SourceStore zijn
no-ops; conflicterende inserts falen. Na revisionbinding blokkeren triggers
ook nieuwe snapshotleden. FK-relaties hebben geen cascaderende verwijdering.

SourceStore gebruikt uitsluitend Store.db. Schrijven vereist een expliciete
caller-transactie, zonder eigen commit of rollback. Zo kunnen bronarchief,
taak/revision en success-audit later in één service-transactie worden verbonden.
De tests bewijzen rollback van deze opslagbouwstenen samen, niet de nog
ongebouwde promotieketen.

## Provenance, revisions en lifecycle

SourceSnapshot bewaart provider/dataset/collection/endpoint, requestparameters,
FetchExtent, request/response CRS, temporele vraag, retrieval start/eind,
aantallen, manifesthash, parser/validator/canonicalisatieversie en provenance.
Een COMPLETE-declaratie is geen bewijs van provider point-in-time consistency.

SourcePage koppelt iedere ontvangen pagina aan raw bytes en bewaart URL,
requestparameters, HTTP-status, media type, headers, response-CRS,
retrievaltijd, cursor en next-link. Gelijke raw bytes mogen worden gedeeld;
request/retrieval-provenance blijft afzonderlijk per snapshot/pagina.

SourceFeature koppelt bron-ID/versie, properties en provenance aan snapshot,
pagina en geometry_ref. Afgeleide geometrieën hebben bestaande parent refs
plus operationele lineage; ze overschrijven brongeometrie niet.
De adapter/validator moet later betekenis en betrouwbaarheid van provenance
bewijzen; niet-lege JSON alleen is geen bronvalidatie.

RevisionBinding verwijst naar een bestaande A02-revision in tasks.body.
Omdat revisions nu JSON zijn en geen SQL-tabel hebben, verifieert de interne
_bind_revision methode A02/eigen taak in Python; SQL verifieert de task-FK.
Er komt geen parallel revisionmodel. Definitief APPROVED/REJECTED wordt geweigerd.
Binding vereist COMPLETE plus overeenkomende archiefaantallen en geen laatste
next-link; de volledige validatie/capabilitygrens blijft voor Fase 2/4.

De store is interne, vertrouwde infrastructuur. Zij wordt niet aangeboden aan
providers, CLI of downstream agents. Zij kent geen promote-methode en kent
geen EXISTING_VALIDATED toe. Archieflezers bewijzen geen bronwaarheid.
ImportStatus beschrijft contractwaarden, geen geïmplementeerde lifecycle-service.
Immutable snapshots worden niet in-place van STAGING naar COMPLETE omgezet;
de latere service moet importpogingen/staging scheiden van de uiteindelijke
immutable snapshotpublicatie. Voeg geen UPDATE-uitzondering aan deze records toe.

Idempotentie in deze fase betekent exacte recordherhaling. Een toekomstige
herimport moet een bestaand inhoudelijk manifest hergebruiken vóór insert;
verschillende retrievalmetadata bij dezelfde identity stil overschrijven is
bewust verboden. Geen bewijs van end-to-end herimport/replay in Fase 1.

## Testdata en dependencies

tests/fixtures/source_archive.json is expliciet synthetische TESTDATA met
SYNTHETIC_LOCAL_METRES, geen PDOK/BAG-response en geen Mastenbroekweg-geometrie.
De bestaande fixtures en TESTDATA-route zijn ongewijzigd.
Geen nieuwe dependencies nodig voor dataclasses/json/sqlite3/hashlib/unittest.
Voor Fase 2 blijven Shapely==2.1.2 en numpy==2.2.6 vastgesteld; niet geïnstalleerd.

De geaccepteerde latere live proofscope blijft:
TESTCASE_ONLY_ANALYSIS_GEOMETRY, EPSG:28992,
BBOX 176492.301,360605.561,176992.301,361105.561, collection pand.
Afgeleid uit officiële PDOK Locatieserver centroide_rd
POINT(176742.301 360855.561), BAG adresseerbaar object 0988010000013261,
nummeraanduiding 0988200000042440, plus/min 250 m.
Seth keurde deze technische scope goed op 2026-09-16. Dit is geen runtime
HumanApproval, project-/ontwerp-/eigendoms-/kadastrale-/beleidsgrens.
Geen Locatieserver-productieadapter toegevoegd.

## Verificatie

Zie tests/test_source_storage.py: migratie uit legacy, heropening, rollback DDL,
toekomstige schemaweigering, immutable records/REPLACE, foreign keys,
raw bytes/hash, identityconflicten, lineage, rolonderscheid, revisionbinding,
incomplete archieven, afgesloten historische besluiten en gezamenlijke rollback.
De volledige suite loopt via test.ps1; tests schrijven alleen in geïsoleerde
.tools/test-runs. K00, HumanApprovalService, reviewownership, check_design_approval,
iteratielimiet, stale/revisionsemantiek en historische bewijzen zijn niet gewijzigd.

Fase 2 blijft afhankelijk van expliciete GO. Niet gebouwd: HTTP/pagination,
adapter, SourceImportService, promotie, live import, volledige validators,
replay, URBAN_BASE. Bestaande single-host/SQLite-netwerksharebeperkingen blijven.


## Uitgevoerde resultaten (2026-09-16)

- Afzonderlijke Fase-1 unittest-discovery: 25 tests, OK (1.207 s).
- Definitieve volledige test.ps1-run: 139 tests, OK (54.924 s), exitcode 0.
- Samenstelling: 114 bestaande regressietests + 25 nieuwe Fase-1 tests.
- git diff --check: geslaagd; alleen Git's bestaande LF/CRLF-normalisatiewaarschuwing.
- Oordeel: GO voor Fase 2 na expliciete opdracht. Geen commit/push/installatie.
- HEAD blijft e66b322be68eeb35eb19e32c182a9d4799bdc608.
