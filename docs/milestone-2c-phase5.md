# Milestone 2C - Fase 5: offline replay

## Baseline en scope

Master is zonder force push/history rewrite fast-forwarded naar de geaccepteerde
Fase 4-commit. Voor implementatie gecontroleerd:
master == origin/master == remote master ==
7ca3396ad268fc07b809ac1cc66cc1d70a479b2c.

Alleen TESTDATA/pand MINIMAL_PROOF. Geen live netwerk, transportimplementatie,
nieuwe dependencies, promotie, Human Approval-wijzigingen of Fase 6.
De twee uitgesloten untracked items zijn niet gelezen of gewijzigd.

## Beschikbare evidence en bestaande contracten

Fase 4 bewaart voldoende input voor de afgebakende proof:

- SourceSnapshot: collectionmetadata, queryscope, requestparameters,
  parser-/validator-/canonicalisatieversie, manifest en retrievalinterval;
- de reeds geregistreerde analysis GeometryRecord;
- source_import_staged-audit: originele request-URL en parameterparen (ook dubbele
  parameters), responseheaders/status/origin, retrievaltijden en fetchmanifest;
- RawResponse: exacte bytes van succesvolle en foutresponses;
- SourcePage, SourceFeature en GeometryRecord: de te vergelijken archiefrecords.

De oorspronkelijke succesvolle capture-set wordt op snapshot-ID en opgeslagen
retrievalinterval geselecteerd. Een latere identieke herimport overschrijft deze
metadata niet. Ontbrekende capture-evidence of raw bytes worden niet aangevuld.
Het opgeslagen fetchmanifest reist mee in ReplayEvidence. Aantal captures,
ontvangen bytes, request-URL, HTTP-status en raw hash worden per poging getoetst.
Zo faalt ook ontbrekende retry-evidence als alle succesvolle pagina's nog bestaan.
Dit randgeval is eerst met een falende test gereproduceerd en daarna uitsluitend
in de nieuwe replayservice gecorrigeerd; bestaande Fase 4-code is ongewijzigd.

## Nieuwe service

application/source_replay.py bevat SourceReplayService:

- evidence(snapshot_id) leest uitsluitend opgeslagen input;
- reconstruct(evidence) bouwt pages/features/sourcegeometries opnieuw uit raw bytes;
- verify(snapshot_id) vergelijkt de reconstructie volledig met het bestaande archief;
- reconstruct_into(evidence, target) schrijft uitsluitend bronarchiefrecords in
  een aparte replay-doelopslag, transactioneel en idempotent.

ReplayEvidence is een frozen inputbundel van bestaande contracten en capture-
evidence, geen nieuw opslag- of validatiemodel. ReplayResult bevat bestaande
SourceSnapshot/SourcePage/SourceFeature/GeometryRecord/RawResponse-records.

Dezelfde PDOKBGTAdapter._parse wordt gebruikt met transport=None. fetch en
fetch_page worden niet aangeroepen. De bestaande continuationcontrole wordt
hergebruikt voor next-links; paginanummers worden zoals bij fetch toegewezen.
validate_completeness controleert de gereconstrueerde bundel, geometrie/CRS,
refs, aantallen, paginaketen en manifest. snapshot_manifest_hash en de bestaande
geometry/raw hashing blijven ongewijzigd. Geen tweede parser of validator.

Headers/timeouts voor een uitgaand HTTP-request worden niet gereconstrueerd:
ze zijn geen parserinput en replay doet geen HTTP-request. De parsercontext
gebruikt uitsluitend opgeslagen URL, parameterparen, response en retrievaltijden.
Transportwachttijden of retrybudgetten worden niet opnieuw uitgevoerd; ontvangen
retryfouten blijven raw evidence. Alleen HTTP 200-pagina's worden geparst.

## Gelijkheid, determinisme en provenance

verify vergelijkt alle dataclassvelden van pages/features/geometries, inclusief
JSON-provenance, CRS-evidence, IDs, bronproperties en opgeslagen geometrie.
RawResponse valideert de opgeslagen hash tegen de exacte bytes opnieuw.
De parser berekent geometry_structural_hash opnieuw; completeness en replay
berekenen snapshot_manifest_hash opnieuw. Geen opgeslagen geometryhash wordt
als vervanging voor parsing aanvaard.

De analysis geometry is reeds expliciete lokale input en wordt niet uit PDOK
of een BBOX verzonnen. Zij wordt opnieuw gevalideerd en blijft gelijk. Deze
proof gebruikt de bestaande zelfstandige TESTCASE_ONLY_ANALYSIS_GEOMETRY,
zonder extra afleidings-/clippingketen.

## Lege doelopslag en geen promotion

De tests maken een nieuwe lege Store onder .tools/test-runs. Vervolgens bouwen
ze RawResponse, GeometryRecord, SourceSnapshot, SourcePage en SourceFeature op
uit ReplayEvidence, met dezelfde immutable SourceStore-methoden. Sourcegeometrie
wordt daadwerkelijk opnieuw geparst, niet uit de opgeslagen features gekopieerd.
De reconstructie kan na het lezen van de input zonder verdere originele DB-reads.

De COMPLETE-declaratie wordt als archiefmetadata gekopieerd; zoals in het bestaande
SourceStore-contract geeft dit op zichzelf geen EXISTING_VALIDATED-status.
Geen tasks, DesignObjects, RevisionBindings, active revisions of audit worden in
de doelopslag aangemaakt. Een doel met taken/bindings wordt geweigerd. De echte
Fase 4-opslag kan daardoor niet als replay-doel gebruikt worden.

Een herhaalde reconstructie geeft identieke records en schrijft geen duplicaten.
Doelconflicten en fouten tijdens writes rollen de gehele doeltransactie terug.
De oorspronkelijke opslag wordt alleen gelezen, ook bij falende replay; iedere
nieuwe test vergelijkt de volledige SQLite-dump voor en na de replay.

## Foutgevallen en grenzen

De tests dekken ontbrekende raw/capture-evidence, corrupte bytes, raw hash mismatch,
body/raw-conflict, malformed JSON met geldige bytehash, manifest mismatch,
geometry hash mismatch, CRS-/origin-/provenance-conflicten, gewijzigde features,
verkeerde requests, ontbrekende eindpagina en verwisselde paginavolgorde.
Fouten geven geen gedeeltelijk replayresultaat of nieuwe trusted state.

Alle sockets, DNS en create_connection zijn geblokkeerd tijdens de nieuwe tests.
Een extra test verbiedt fetch/fetch_page en telt de aanroepen van de bestaande parser.

Dit bewijst reconstructie van opgeslagen TESTDATA, geen authenticiteit van echte
providerdata. Het archief/audit is vertrouwde lokale input, geen cryptografisch
ondertekende bron. Gecoördineerde herschrijving van alle evidence valt buiten de
bestaande trusted-Python-grens. Point-in-time blijft NOT_GUARANTEED.
Er is geen live-proof, exportformaat, replay-CLI of nieuwe promotion-route.
Het gereconstrueerde doel bevat bronrecords; ReplayEvidence blijft de afzonderlijke
input voor herhaling, zonder de originele taak-/auditgeschiedenis te klonen.

## Verificatie

Projectlokale Python -B met import run_tests voor dezelfde src-path.
Targeted discovery: test_source*.py plus test_pdok_bgt*.py.
Volledige regressie: ./test.ps1.

Nieuwe replaytests: 29. Definitieve targeted run: 295/295 PASS, 13.652 s.
De tests schrijven alleen in geisoleerde projectlokale tijdelijke opslag en
bewaken originele archive-state via een volledige SQLite-dumpvergelijking.

Definitieve volledige regressie: ./test.ps1, 409/409 PASS, 57.798 s, exitcode 0.
Git diff --check en staged diff --check: PASS.

Reviewbranch: milestone-2c-phase5-review. Exact drie nieuwe bestanden:
src/bvc_ai/application/source_replay.py, tests/test_source_replay.py en dit rapport.
Geen bestaande productiecode gewijzigd. Master blijft op de geaccepteerde Fase 4-
commit. Geen merge of start van Fase 6.
