# Milestone 2C - Fase 6: live Mastenbroekweg MINIMAL_PROOF

## Baseline en scope

Fase 5 is via fast-forward naar master gebracht, zonder force push of history
rewrite. Daarna zijn master, origin/master en remote refs/heads/master exact
geverifieerd als `729fb763033a942e4cb8b2c48affa2a4702aca35`.
Werkbranch: `milestone-2c-phase6-review`. Master blijft op die baseline.
De twee uitgesloten untracked items zijn niet geopend of gewijzigd.

Uitsluitend Mastenbroekweg 2, 6006 PT Weert, Nederland; pand-collectie van
`https://api.pdok.nl/lv/bgt/ogc/v1/collections/pand/items`.
BBOX EPSG:28992: `176492.301,360605.561,176992.301,361105.561`.
Door de gebruiker geleverd officieel BAG-centroid RD:
`POINT(176742.301 360855.561)`; geen BAG-fetch of BAG-import uitgevoerd.
Purpose: `MILESTONE_2C_MINIMAL_PROOF`.
Geometrierol: `TESTCASE_ONLY_ANALYSIS_GEOMETRY`, herkomst `USER_SUPPLIED_TESTCASE`.
Dit is geen ProjectGeometry, eigendomsgrens, kadastrale grens, ontwerpgrens of
beleidsgrens. Geen nieuwe afhankelijkheden, collecties of Fase 7.

## Implementatie

- `adapters/pdok_live.py`: standaardbibliotheek HTTPSConnection, uitsluitend GET
  met TLS-certificaatcontrole, vaste host/path/bbox/RD/JSON-FG/limit en eventueel
  een cursor. URL en querymetadata moeten overeenkomen. Geen proxies uit de
  omgeving, credentials, cookies, sessies, redirects of decompressie. Exacte
  bodybytes, headerparen, status en UNVALIDATED_PROVIDER_RESPONSE blijven behouden.
  Bytecap tijdens read1, totale caller-deadline inclusief DNS/TLS/headers/body,
  socket-timeouts en socket-shutdown bij timeout. Content-Length wordt indien
  aanwezig tegen werkelijk gelezen bytes gecontroleerd.
- `application/live_source_validation.py`: expliciete testcasecontrole,
  requestscope/chain, raw hashes en bytegelijkheid, origin, opnieuw parsen met de
  ongewijzigde Phase 3-parser en vergelijken van pages/features/geometries.
  Aanwezige numberMatched mag querycompleteness niet tegenspreken.
- `application/source_import.py`: default blijft de Fase 4 TESTDATA-gate.
  Alleen de trusted capability met expliciet `live_mastenbroekweg=True` opent
  het vaste liveprofiel. Bestaande staging, completeness, immutable opslag,
  archive-readback, transactie, K00-policy, A02-binding en audit blijven leidend.
- `application/design_workflow.py`: de interne _apply ontvangt uitsluitend een
  bronlabel van de vertrouwde caller, standaard TESTDATA. Dat label wordt in
  A02-output, objectregistratie en stap-audit behouden. Geen approval-logica of
  providerparameter toegevoegd; geen bevoegdheid naar agents/providers verplaatst.
- `application/source_replay.py`: herkent het expliciete liveprofiel en controleert
  dezelfde testcase, scope, raw bytes en origin. Bestaande parser, completeness,
  manifestvergelijking en archivevergelijking blijven in gebruik.
- `scripts/live_mastenbroekweg.py`: afzonderlijke opt-in, eigen runtime-map per run,
  bestaande SourceImportService en daarna socket-/DNS-geblokkeerde replay plus
  reconstructie naar een tweede, taakvrije database. Controleert raw bytes,
  geometrie, provenance, records en manifest op gelijkheid. Geen tweede importpad.

Uitvoeren, uitsluitend expliciet:

```powershell
& ./.tools/source-venv/Scripts/python.exe -B scripts/live_mastenbroekweg.py --live-mastenbroekweg
```

De normale `test.ps1` ontdekt alleen netwerkloze tests en voert dit script niet uit.
De nieuwe tests blokkeren sockets/DNS en gebruiken stubs of synthetische
provider-origin evidence. Die testbodies zijn geen echte PDOK-brondata.
Live raw responses en databases blijven onder ignored `runtime/`; alleen een
compact metadatarapport wordt gecommit.

## Interpretatie en grenzen

UNVALIDATED_PROVIDER_RESPONSE beschrijft blijvend de oorspronkelijke transport-
herkomst; EXISTING_VALIDATED ontstaat afzonderlijk, pas na trusted validatie.
De workflowcontext en A01-start zijn expliciet TESTDATA-scaffolding in een
geisoleerde proof-database. A02-output en objecten dragen hun echte provider-origin;
de analysegeometrie is door de gebruiker aangeleverd. De echte demo runtime/GIS-001
wordt niet gebruikt of goedgekeurd. Geen human approval of vervolgagents uitgevoerd.

Collectionmetadata zijn de door de caller opgegeven bestaande RD-contractverwachting,
geen live opgehaalde collectionmetadata. Werkelijk ontvangen CRS-bewijs komt uit
Content-Crs en coordRefSys; er wordt niets uit locatie of coordinaten afgeleid.

Completeness betreft de begrensde query en volledige vervolgketen. Een historische
peildatum of atomaire point-in-time consistentie wordt niet geclaimd:
NOT_GUARANTEED blijft behouden. Het huidige liveprofiel vereist dat vervolgrequests
alle vaste scopeparameters behouden; een afwijkend providercontract faalt gesloten.

De totale caller-deadline kan ook bij vastgelopen OS-DNS terugkeren. Een daemon-
worker kan dan nog op OS-DNS wachten, maar controleert annulering voor de GET.
Dit is geen procesisolatie voor kwaadwillende Python-plugins. Lokale Python-code,
TLS-stack en opgeslagen lokale evidence vallen onder de bestaande vertrouwensgrens.

## Verificatie

Gericht: 85 tests PASS, inclusief 18 nieuwe transport/live-origin tests en bestaande
TESTDATA-import/replay-regressies. Fakes testen onder meer bytecap/deadline,
redirects, scope, afwijkende providerstructuur, originrelabeling, gewijzigde mapping,
raw bytes, pagination/retry, immutable herimport en offline replay.

Definitieve regressie en live resultaten: zie het aanvullende bewijs hieronder.

Volledige regressie: `./test.ps1`, 427/427 PASS, 58.149 s, exitcode 0.
Projectlokaal testlog: `.tools/phase6-regression.txt`.

## Live resultaat

PASS, 2026-09-25T13:45:41.264675+00:00 (UTC).
Het volledige compacte bewijs staat in [milestone-2c-phase6-proof.json](milestone-2c-phase6-proof.json),
inclusief exacte request-URL en auditmetadata.

- HTTP 200; Content-Type `application/vnd.ogc.fg+json`.
- Content-Crs `<http://www.opengis.net/def/crs/EPSG/0/28992>`;
  root coordRefSys `http://www.opengis.net/def/crs/EPSG/0/28992`.
- JSON-FG FeatureCollection, 1 pagina, 241 features, numberReturned 241,
  geen next-link, 279431 ontvangen bytes.
- Raw SHA-256: `6510926f1a7fb81797f328c63f392c3a6e9fc2c76b7bd06245d723ad4cc92e11`.
- Snapshot: `phase6/mastenbroekweg/20260925T134541264675Z`.
- Snapshot manifest SHA-256: `375076580961948a1f165941746b86ac48ce50f386172a9f0d8c2afefa658172`.
- A02 revision: `A02/v1`; trusted audit `source_import_completed`,
  VALIDATING -> COMPLETE, query_scope_complete=true, EXISTING_VALIDATED.
- Offline replay en reconstructie: PASS, socketconstructie/connectie/DNS geblokkeerd;
  alle raw bytes/hashes, manifest, pages, features, geometrie en provenance gelijk.
- Lokaal origineel en replayarchief:
  `runtime/phase6-live/20260925T134541264675Z/` (ignored, niet gecommit).

De eerdere uitsluitend transport/parser-contractpreflight om 13:37:40 UTC was
ook succesvol (241 features). Die preflight maakte geen snapshot of A02-binding.
De bovenstaande import is het doorslaggevende end-to-end bewijs.
241 is een observatie, geen fixture of hardgecodeerde verwachte broncount.
Het Phase 3A-3C parsercontract is ongewijzigd gebleven.

`git diff --check` en staged `git diff --cached --check`: PASS.
Er worden uitsluitend Fase 6-code/tests/docs gecommit; geen providerpayloads.
Na push van de reviewbranch: geen merge, geen verdere masterwijziging, geen Fase 7.
