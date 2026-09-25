# Milestone 2C - Fase 4: trusted source import

## Baseline en afbakening

De geaccepteerde Fase 3C-commit is met een fast-forward naar master gebracht en
zonder force push gepubliceerd. Voor implementatie expliciet gecontroleerd:
master == origin/master == remote master ==
241e21aafee2a8d8ae5220906225d686eb0c74db.

Uitsluitend PDOK pand MINIMAL_PROOF met synthetische TESTDATA en fake transport.
Geen nieuwe dependencies, schema, opslagmodel, hashingregels of validators.
Geen live requests, replay, extra collecties, URBAN_BASE, GIS-export of Fase 5.
Geen Human Approval-wijzigingen; de echte runtime/GIS-001 is niet aangeraakt.
De uitgesloten untracked items zijn niet gelezen, gewijzigd of toegevoegd.

## Service en bestaande bouwstenen

Nieuw: application/source_import.py::SourceImportService.import_source.
De trusted caller levert Store, GetTransport, expliciete collectionmetadata,
taak-ID, snapshot-ID en FetchExtent. De analysis geometry moet reeds als bestaand
GeometryRecord geregistreerd zijn. De taak gebruikt het bestaande ONTWERPLUS_2B-
contract en heeft een actuele A01_START-output. Geen nieuwe taak-/revisionsoort.

De service construeert zelf de bestaande PDOKBGTAdapter; callers leveren geen
willekeurige geparste bundels of providerpromotievoorstellen aan. De adapter
behoudt zijn read-only grens en krijgt geen Store of capability.

Hergebruik:

- PDOKBGTAdapter.fetch, CapturedResponse en de bestaande begrensde parser;
- SourceSnapshot, SourceFeature, GeometryRecord, RawResponse, SourcePage,
  FetchExtent en RevisionBinding;
- source_hashing voor inhoudelijke manifestidentiteit;
- validate_geometry_record en validate_completeness;
- SourceStore op de bestaande Store.db met immutable SQL-guards;
- DesignWorkflow._gate, inputs en _apply; _apply gebruikt ongewijzigd _invalidate;
- Store._save en Store.event voor dezelfde transactionele taak-/auditopslag.

De service roept geen AIProvider aan. Zij maakt na validatie alleen
EXISTING_FEATURE-objecten met bronrefs, snapshotverwijzing en TESTDATA-markering.
Geen projectgrens wordt uit de technische analysis geometry afgeleid.
Imported geometry blijft in geometry_records; de synthetische geometry_registry
wordt niet uitgebreid of herschreven. K00Policy wordt toegepast op de objectregistratie.

## Capability en promotion

Constructie vereist de private identity-capability
_A02_SOURCE_IMPORT_CAPABILITY, volgens hetzelfde bestaande capabilitypatroon als
de vertrouwde servicegrens. Een actorstring zoals A02 is geen capability.
Providers, DesignSession en de adapter krijgen dit object of de service niet.
Dit is de bestaande trusted-Python-grens, geen sandbox voor kwaadwillende plugins.

Alleen deze nieuwe trusted route registreert geimporteerde refs als
EXISTING_VALIDATED. De bestaande synthetische A02-providerroute blijft intact;
haar proposalvalidator weigert geimporteerde refs omdat die niet in de
synthetische registry staan. Geen verruiming van providerbevoegdheden.

Fase 4 accepteert bewust alleen expliciet TESTDATA in taak, analyse en responses.
EXISTING_VALIDATED benoemt hier de technische validatie binnen de synthetische
proof; het verandert TESTDATA niet in echte brondata. UNVALIDATED_PROVIDER_RESPONSE
wordt in deze afgebakende fase geweigerd, niet stilzwijgend omgelabeld.
Er is geen nieuwe CLI/live-ingang en geen human capability gebruikt.

## Evidence en atomiciteit

De bestaande adapter legt ontvangen bytes in CapturedResponse vast voordat hij
parset. Fetch en parsing vinden buiten de publicatietransactie plaats.
Na fetch bewaart een aparte evidence-transactie uitsluitend RawResponse-records
plus een staged auditevent met request-/responseheaders, parameters, origin,
tijden, hashes en het fetchmanifest. Ook retryfouten en partial captures blijven
zo beschikbaar. Dit is onbetrouwbaar bewijs, geen gedeeltelijk vertrouwd archief.

Daarna controleert de service fetchstatus VALIDATING, expliciete exhaustion en
het ontbreken van failure markers. Page/capture-, feature-, geometry- en CRS-
provenance moeten aansluiten. De snapshot krijgt een berekend inhoudelijk manifest.

In een enkele BEGIN IMMEDIATE-publicatietransactie:

1. taak opnieuw lezen en tegen de toestand voor fetch controleren;
2. bestaande A02-gate en completeness-validatie uitvoeren;
3. gevalideerde geometrie en COMPLETE snapshot met pages/features immutable opslaan;
4. het werkelijke archief teruglezen en provenance/completeness opnieuw controleren;
5. A02-objecten/revision registreren via bestaande _apply, inclusief stale propagation;
6. dezelfde revision via RevisionBinding aan de snapshot binden;
7. taak, expliciete statusovergangen en succes-audit samen committen.

Elke fout rolt alle publicatiemutaties terug. Er blijft geen nieuwe gedeeltelijke
snapshot, geometrybundle, promotion, binding of stale-mutatie staan. Eerder
opgeslagen immutable historie blijft intact. Alleen raw evidence en attempt-audit
mogen blijven staan. Na rollback volgt een aparte source_import_failed-audit.

Wanneer evidence- of auditopslag zelf faalt, wordt niets gepubliceerd.
SourceImportError houdt het FetchResult met in-memory captures beschikbaar;
evidence kan bij een opslagstoring uiteraard niet duurzaam worden gegarandeerd.
Een reeds geopende callertransactie wordt geweigerd zonder die te committen of
terug te rollen. De service is geen nested-transaction API.

## Idempotentie en conflicten

De bestaande manifestidentiteit bepaalt archiefhergebruik. Retrievaltijden en
HTTP Date veranderen de inhoudelijke identiteit niet. De oorspronkelijke
immutable retrievalmetadata worden behouden; de nieuwe poging krijgt eigen audit.

Een identiek manifest onder dezelfde of een nieuwe aangevraagde snapshot-ID
hergebruikt de bestaande snapshot. Bij een actuele bestaande binding met passende
A02-publicatie-evidence blijft de bestaande revision staan: geen revisionstorm of
stale-mutatie. Dit is een domein-no-op, niet een audit-no-op.

Dezelfde snapshot-ID met ander manifest faalt expliciet. Immutable geometry-
conflicten falen ook. Hergebruik slaat provenance/completeness nooit over.
Een COMPLETE-label of losse binding zonder passende A02-output en idempotency-
evidence verleent geen trusted status. Een historische/stale binding wordt niet
stilzwijgend gereactiveerd; dit respecteert de bestaande unique(task,snapshot)-grens.
Nieuwe broninhoud gebruikt een nieuwe snapshot-ID en maakt een nieuwe A02-revision.

## Bewijs door tests

38 nieuwe netwerkloze tests in tests/test_source_import.py, met echte SQLite in
projectlokale TemporaryDirectory onder .tools/test-runs. Socketconstructie,
create_connection en DNS zijn gedurende iedere nieuwe test geblokkeerd.

- Minimale, lege en multipage-import met retry-evidence; duurzame heropening.
- Identieke herimport, nieuwe aangevraagde ID en gewijzigde retrievaltijd/HTTP Date.
- Conflicterende snapshotidentiteit en immutable geometry-identiteit.
- Incomplete fetch, false exhaustion, failure marker, verkeerde fetchstatus.
- Ongeldige CRS, geometrie, mapped hash, provenance en onvoldoende CRS-evidence.
- Ongeldige completeness en expliciet negatief validatorresultaat.
- Hergebruik met kapot archief, ontbrekende publicatie-evidence of verkeerde provenance.
- Injecties na geometry-, snapshot-, page- en feature-write, na revisionbinding
  en na succes-audit; alle trusted tabellen en tasks.body blijven exact gelijk.
- Failure voor promotion, tijdens evidence-opslag en bij onbeschikbare failure-audit.
- Capabilityweigering, providerweigering voor geimporteerde refs en gesloten taakgates.
- Gelijktijdige taakwijziging tijdens fetch blokkeert publicatie.
- Nieuwe snapshot bindt A02/v2, bewaart A02/v1 en maakt afhankelijke A07-review
  stale via de bestaande route; resolved finding wordt heropend met audit.
- Mislukte vervanging behoudt de oude actieve revision en volledige immutable historie.
- Expliciete STAGING -> VALIDATING -> COMPLETE-auditketen en failure-audit.

## Resterende beperkingen

Dit is een netwerkloze TESTDATA-proof, geen live PDOK- of Mastenbroekweg-bewijs.
Point-in-time blijft NOT_GUARANTEED. Completeness heeft de bestaande betekenis:
consistentie van de geparste querybundel, referenties, aantallen en paginaketen;
een door de provider stilzwijgend weggelaten next-link is geen detecteerbare garantie.

De bestaande synchrone transportgrens, single-host SQLite/netwerksharebeperkingen,
trusted Python en geometrische binary64-topologie blijven gelden.
Er is geen nieuwe procesisolatie, authenticatie, concurrencyarchitectuur of
consumenten-UI gebouwd. Downstream ontwerpberekeningen blijven buiten deze proof.
Geen fase 5 replay of fase 6 live transport toegevoegd.

## Verificatie

Targeted commando:

```powershell
& ./.tools/source-venv/Scripts/python.exe -B -c "import run_tests, unittest; loader=unittest.defaultTestLoader; suite=unittest.TestSuite([loader.discover('tests', pattern='test_source*.py'), loader.discover('tests', pattern='test_pdok_bgt*.py')]); result=unittest.TextTestRunner(verbosity=1).run(suite); raise SystemExit(not result.wasSuccessful())"
```

Targeted: 266/266 PASS, 7.802 s (inclusief 38 nieuwe Fase 4-tests).

Volledige regressie: ./test.ps1, 380/380 PASS, 51.136 s, exitcode 0.
Git diff --check en controle van de staged diff: PASS.
Alle tests NETWORKLESS; geen nieuwe dependencies of runtimewrites buiten de
geisoleerde projectlokale testopslag.

Reviewbranch: milestone-2c-phase4-review, vanaf de geaccepteerde master.
Exact nieuwe bestanden: src/bvc_ai/application/source_import.py,
tests/test_source_import.py en docs/milestone-2c-phase4.md.
Geen bestaande productiecode gewijzigd. Geen merge, verdere masterwijziging of
start van Fase 5.
