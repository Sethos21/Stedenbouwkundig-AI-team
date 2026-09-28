# Release 1 - Fase 1: Project Shell & Projectstatus

Baseline: `65dcc27d38b4a3c2a5462f6c39380eb1685b6893` (afgesloten Milestone 2C).
Reviewbranch: `release1-phase1-project-shell`. Geen merge naar master.

## Architectuur en scope

Een project is een zelfstandige identiteit naast bestaande taken. `Project` is
immutable in Python en bevat een gegenereerd `PRJ-<uuid4>` ID, naam, UTC-timestamps,
status en optioneel onderzoekstype, adres en vrije locatietekst. Dezelfde naam mag
bij meerdere projecten voorkomen; identiteit hangt niet af van naam of locatie.
Locatietekst is gebruikersinvoer, geen geocoding, geometrie of gevalideerde bron.
De optionele velden worden bij creatie opgegeven; een metadata-editor is niet gebouwd.

`ProjectRepository` gebruikt de bestaande `Store`/SQLite-verbinding en voegt pas bij
projectgebruik twee eigen tabellen toe: `projects` en `project_audit`. Bestaande
taken, audittabel, source-schema/migratieversie en bronarchieven blijven intact.
Het projectschema wordt idempotent aangemaakt; er is geen nieuwe dependency.
`project-audit` leest de canonieke projectaudit; de bestaande `audit.jsonl` blijft
uitsluitend de bestaande taakauditprojectie.

`ProjectService` verzorgt create/load en gewone statusovergangen. Schrijfacties
gebruiken BEGIN IMMEDIATE: projectstatus en bijbehorende audit worden samen
gecommit. Een fout draait de wijziging terug, waarna een afzonderlijke audit de
blokkade of fout vastlegt. Een opslagstoring kan ook die failure-audit verhinderen;
er volgt dan geen succesvolle publicatie. Caller-transacties worden geweigerd en
niet overgenomen. Audithistorie is beschermd tegen UPDATE, DELETE en REPLACE.

## Kleine statusmachine

| Huidig | Toegestaan vervolg |
|---|---|
| PROJECT_AANGEMAAKT | INTAKE_IN_UITVOERING |
| INTAKE_IN_UITVOERING | ONDERZOEK_IN_UITVOERING |
| ONDERZOEK_IN_UITVOERING | GEREED_VOOR_BEOORDELING |
| GEREED_VOOR_BEOORDELING | ONDERZOEK_IN_UITVOERING of menselijke ONDERZOEK_VRIJGEGEVEN_VOOR_ONTWERP |
| ONDERZOEK_VRIJGEGEVEN_VOOR_ONTWERP | Geen |

Terugsturen voor aanvullend onderzoek is mogelijk zonder extra status. Overslaan,
onbekende statussen, herhaalde overgangen en wijzigen na vrijgave worden geweigerd.
Iedere gewone overgang vraagt een reden. De service gebruikt een vaste actor en
neemt geen menselijke identiteit, capability of human-flag van de caller aan.

De statusmachine registreert uitsluitend de levenscyclus. GEREED_VOOR_BEOORDELING
is in deze fase geen bewijs dat een toekomstige Research Gate is geslaagd.
Er is geen agent aangesloten; een latere A01-koppeling kan de gewone route gebruiken
zodra de volgende fase de inhoudelijke gatevoorwaarden en ownership specificeert.

## Menselijke grens

De enige aanvullende wijziging aan bestaande beslisarchitectuur is
`HumanApprovalService.release_project`, noodzakelijk om de nieuwe menselijke
projectbeslissing bij dezelfde vertrouwde beslisroute te houden. De bestaande
`decide`-route voor taken en reviews blijft ongewijzigd.

Alleen de vertrouwde CLI composeert deze service met de bestaande object-identieke
human capability. De methode vereist GEREED_VOOR_BEOORDELING, een niet-lege menselijke
actor en reden; A01-A08 worden geweigerd. De gewone projectservice weigert vrijgave
altijd. Een naam of providertekst verleent geen bevoegdheid. De audit bewaart
project-ID, actor, tijd, vorige/nieuwe status, reden en TRUSTED_HUMAN_CLI-herkomst.
Vrijgave start geen ontwerpworkflow en keurt geen bestaande taak of bron goed.

Providers krijgen geen projectservice, repository, Store, CLI, tools of capability.
K00Policy, review ownership, revision/stale en source/provenance blijven intact.
Zoals voorheen zijn lokale Python-code, filesystem en CLI vertrouwd: dit is geen
sandbox of authenticatie voor externe callers of kwaadwillende plugins.

## CLI

Gebruik de bestaande `bvc-ai.ps1` launcher. Voorbeelden (uitsluitend handmatig;
geen echte demo of gebruikersproject is tijdens de bouw aangemaakt/vrijgegeven):

```powershell
./bvc-ai.ps1 project-create "Mijn project"
./bvc-ai.ps1 project-show PRJ-<id>
./bvc-ai.ps1 project-transition PRJ-<id> INTAKE_IN_UITVOERING --reason "Intake gestart"
./bvc-ai.ps1 project-transition PRJ-<id> ONDERZOEK_IN_UITVOERING --reason "Onderzoek gestart"
./bvc-ai.ps1 project-transition PRJ-<id> GEREED_VOOR_BEOORDELING --reason "Ter beoordeling"
./bvc-ai.ps1 project-audit PRJ-<id>
# Alleen een expliciet besluit van de mens via de vertrouwde CLI:
./bvc-ai.ps1 project-release PRJ-<id> --actor "Menselijke naam" --reason "Besluitmotivering"
```

`project-create` accepteert optioneel `--research-type`, `--address`, `--location`.
`--data` blijft beperkt tot opslag binnen de projectmap. Projectcommando's maken
geen provider aan en voeren geen netwerkcalls uit.

## Verificatie

Gerichte tests in `tests/test_projects.py` controleren unieke identiteit, optionele
velden, create/load, heropenen, status/audit-persistence, de overgangsmatrix,
terugsturen, capabilityweigering, agentidentiteiten, menselijke vrijgave,
auditrollback, immutable audit, foutieve invoer en de CLI in tijdelijke opslag
onder `.tools/test-runs`. Menselijke besluiten in tests zijn uitsluitend simulaties
in die geisoleerde opslag; runtime/GIS-001 blijft ongemoeid.

Resultaten (28 september 2026):

- Targeted: 11/11 PASS, 12.247 s, exitcode 0; src-importvolgorde gelijk aan run_tests.py.
- Volledig: `./test.ps1`, 438/438 PASS (427 bestaande + 11 nieuwe), 72.674 s, exitcode 0.
- Volledige suite met de bestaande projectlokale socket-auditguard via PYTHONPATH;
  geen live providercall. Log: `.tools/release1-phase1-regression.txt` (ignored).
- `git diff --check` en `git diff --cached --check`: PASS.

## Aandachtspunten volgende fase

Koppel toekomstige gegevens via project-ID; bouw nu geen tabellen voor percelen,
documenten, brondata, bevindingen of onderzoeksvragen vooruit. Specificeer Research
Gate en binding aan de beoordeelde onderzoeksversie voordat een inhoudelijke
onderzoeksworkflow wordt aangesloten. Metadatawijzigingen en eventuele heropening
na vrijgave hebben later expliciete regels nodig. De huidige vrijgavestatus is
terminaal; er bestaat geen stilzwijgende reset of automatische ontwerpstart.

Geen kaart/UI, luchtfoto, geocoding, nieuwe bronnen, perceelselectie, specialistische
agents, A03, presentatiegeneratie of volgende fase gebouwd.
