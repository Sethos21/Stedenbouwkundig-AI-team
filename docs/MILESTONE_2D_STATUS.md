# Milestone 2D - hervatbare voortgang

Datum: 29 september 2026.
Werkbranch: milestone-2d-work.
Baseline: 03051103ddec842b2be3b6d6aa0aa5553b7444cc.
Geaccepteerde 2C closure: 65dcc27d38b4a3c2a5462f6c39380eb1685b6893.
Huidige fase: 2D-4 afgerond; uitvoering gestopt op expliciet TOKEN/CAPACITY CONTROL-verzoek.
Geen BLOCKED of open DECISION_REQUIRED. Geen automatische voortzetting in deze sessie.

## Checkpoints en teststatus

| Fase | Status | Fasecommit | Verificatie |
|---|---|---|---|
| 2D-1 | PASS | a54ccc4498701b01a7c073fdc1d433980cda6396 | test.ps1 427/427 PASS, 65.154 s |
| 2D-2 | PASS | 399cfc34888ef45f2543d4ed397124a7d0dadc45 | Targeted 9/9; test.ps1 436/436 PASS, 60.746 s |
| 2D-3 | PASS | b982a52825167318a6babcf3891113e8de56f2a8 | Targeted 14/14; test.ps1 441/441 PASS, 63.629 s |
| 2D-4 | PASS | Commit die dit statusbestand vastlegt: Milestone 2D-4 - A02 source basis checkpoint | Targeted 22/22, 14.423 s; test.ps1 449/449 PASS, 95.810 s |
| 2D-5 | NOT_STARTED | Geen | Geen live featureproof uitgevoerd |
| 2D-6 | NOT_STARTED | Geen | Geen finale validatie of guard-run uitgevoerd |

De eigen checkpoint-SHA is niet in zijn eigen commit ingebed. Bepaal hem bij
hervatting met `git log -1 --format=%H -- docs/milestone-2d-phase4.md` en controleer
commitonderwerp, branch en werkboom. De SHA wordt ook in het checkpoint-eindrapport
gegeven. Alle genoemde testruns eindigden met exitcode 0.
`git diff --check` en staged diffcheck: PASS.

## Afgerond

- 2D-1: inventarisatie 2C-hergebruik; contractselectie zes BGT-collecties en twee
  BAG-collecties; officiele metadata/schema-inspectie, 11 vaste requests HTTP 200.
  Geen featuredata opgehaald. Besluiten en AGENTS.md-uitzondering vastgelegd.
- 2D-2: gesloten bronprofielen; dezelfde bounded parser/fetch/import/replayketen
  voor pand, wegdeel, ondersteunendwegdeel, waterdeel, begroeidterreindeel en
  onbegroeidterreindeel. Bestaand 2C-profiel blijft default en reproduceerbaar.
- 2D-3: BAG pand (Polygon) en verblijfsobject (Point) via dezelfde keten;
  afzonderlijke identiteiten/provenance; officiele relaties als bronattributen.
  Decimal-integercheck met failing test gereproduceerd en minimaal gecorrigeerd.
- 2D-4: actuele A02 source_set, verifieerbare immutable bronleden en originele
  importbindings; alleen trusted SourceImportService publiceert de samengestelde
  actuele A02-revisie. Vervanging van een collectie gebruikt bestaande stale-route.
  SourceBasisService levert read-only machine-readable bronbeeld, samenvatting,
  raw/geometry/snapshot/revisionrefs en onzekerheden bij niet opgeloste of
  conflicterende officiele relaties. CLI source-basis weigert stale revisies.
  Targeted tests omvatten complete/partiele bronset, CLI, readonly, relaties,
  idempotence, replacement, historie/stale, atomic rollback en tampering.

Faseverslagen: docs/milestone-2d-phase1-source-contract.md en
milestone-2d-phase2.md, milestone-2d-phase3.md, milestone-2d-phase4.md.
Testlogs: .tools/2d-phase1-regression.txt t/m .tools/2d-phase4-regression.txt;
gerichte logs .tools/2d-phase2-targeted.txt t/m .tools/2d-phase4-targeted.txt.
De fase-4 volledige suite was al gestart voor het stopverzoek en is afgerond;
er is na het verzoek geen nieuwe testsuite gestart.

## Besluiten Seth (afgehandeld)

1. Beperkte Milestone-2D-uitzondering: read-only officiele PDOK BGT/BAG-
   contractinspectie, begrensde live fetches binnen vooraf vastgelegde officiele
   endpoints/scopes, lokale raw evidence/hashes/provenance/validatiebewijs,
   expliciete live opt-in voor live proof. Alleen noodzakelijk netwerkverkeer.
   Geen productiecredentials, cloudwrites, arbitrary URL/netwerk, andere externe
   integraties, niet toegestane bronnen of omzeiling van trustgrenzen.
   Geen nieuwe toestemming nodig voor afzonderlijke fetches binnen deze scope.
2. BAG pand EN verblijfsobject: gebouwcontext plus gebruiksdoelen, oppervlakten,
   adressen en pandrelaties. Afzonderlijke officiele objecten, eigen identiteit en
   provenance; geen synthetische bronwaarheid of door LLM afgeleide relaties.
3. Technische collectiekeuzes zelfstandig maken wanneer zij rechtstreeks uit
   officiele semantiek en het vastgestelde A02-doel volgen zonder nieuwe bron,
   dependency, capability, veiligheidsgrens of doeluitbreiding. Geen automatische
   beslisgate. Echte wijzigingen in productgedrag/scope/architectuur/bronautoriteit/
   veiligheidsgrenzen blijven onder de orchestratorgates vallen.
4. TOKEN/CAPACITY CONTROL: huidige stap afronden en committen, geen nieuwe fase
   starten; na dit checkpoint stoppen. Hervatting vereist een nieuwe opdracht.

## Openstaand en bekende beperkingen

- 2D-5: opt-in end-to-end live proofscript nog niet gebouwd; echte actuele features
  van alle acht collecties nog niet opgehaald/gevalideerd. Geen live-PASS claim.
  Te bewijzen: complete actuele A02-bronbasis, exacte captures/hashes/provenance,
  offline replay en lege-opslagreconstructie, compact machine-readable proof.
- 2D-6: finale traceability/architectuurvalidatie, volledige netwerkgeblokkeerde
  regressie, MILESTONE_2D_VALIDATION.md, final-reviewbranch en push nog niet gedaan.
- Contractbewijs .tools/2d-contracts/ met exacte bytes; compact metadata/hashbewijs
  docs/milestone-2d-contract-inspection.json is gecommit. Geen nieuwe dependencies.
- Alleen vaste testcasebbox Mastenbroekweg in RD; geen point-in-timegarantie,
  volledige BGT-vlakdekking, ontwerp-, beleids- of eigendomsconclusies. Relaties
  buiten de bbox blijven onopgelost; geen automatische follow-upfetch of repair.
- Workflow/A01-context blijft TESTDATA-scaffolding; echte provider-origin wordt
  apart behouden. Huidige testbodies zijn synthetisch, ook bij provider-originlabels.
- Bestaande Python/CLI/filesystem-vertrouwensgrens blijft; geen sandbox voor
  kwaadwillende plugins of externe callers. Geen Human Approval of A03-A06 gestart.
- master en origin/master niet gewijzigd na de toegestane protocolbaseline;
  Release 1-reviewbranch niet geintegreerd. Geen push van dit werkcheckpoint.
  Stedenbouwkundig-AI-team/ en phase3b-review.diff volledig ongemoeid.

## Eerstvolgende concrete actie bij hervatten

Lees AGENTS.md, MILESTONE_2D_ORCHESTRATOR.md en deze status; verifieer het huidige
2D-4-checkpoint op milestone-2d-work. Start daarna uitsluitend 2D-5: bouw een
expliciet opt-in Mastenbroekweg-proofscript op de bestaande trusted importservice,
acht gesloten bronprofielen en SourceBasisService. Gebruik dezelfde geaccepteerde
bbox, lokale unieke proofopslag en TESTDATA-scaffolding; raak runtime/GIS-001 niet.
Voeg gerichte networkless controles toe voor nieuw scriptgedrag en voer dan de
begrensde live proof plus netwerkgeblokkeerde replay/reconstructie uit. Behandel
echte nieuwe contractafwijkingen fail-closed en volgens protocol. Herhaal geen
reeds geslaagde fase zonder concrete regressieaanwijzing. Ga alleen na 2D-5 PASS
verder naar 2D-6 en push uiteindelijk milestone-2d-final-review zonder mastermerge.
