# Milestone 2B.1 — validatierapport

Datum: 2026-09-15  
Basis: herstelronde op commit `60e852c`  
Scope: uitsluitend F1, F2, F3 en F4 uit de technische review. Milestone 2C is niet gestart.

## Resultaat

De vier reviewbevindingen zijn opgelost en regressietests slagen. De volledige suite is opnieuw uitgevoerd met **114/114 tests geslaagd** in 54,903 seconden. De actuele broncode is tijdens de testrun niet gewijzigd; het validatiebewijs bevat de Git-HEAD en een SHA-256-manifest van de geteste bronbestanden.

## Wijzigingen per finding

### F1 — aantoonbare specialistische finding-resolutie

`src/bvc_ai/domain/design_verification.py` bevat een kleine, gesloten verificatielaag voor de huidige synthetische fixture. Zij controleert geregistreerde TESTDATA-rechthoeken, CRS, geometry-status, exacte specialistische objecten, geïntegreerde objecten, actieve revisies en de relevante vrije strook:

- A04: de oostelijke groenstrook blijft vrij;
- A05: de zuidelijke toegangszone blijft vrij.

Providertekst is geen bewijs. Alleen wanneer de verificatiefunctie een revision-bound bewijsrecord oplevert, mag de juiste specialist zijn finding `RESOLVED` vastleggen. Onbekende findings, gewijzigde conflicterende geometrie of ontbrekende specialistobjecten blijven OPEN of falen de reviewvalidatie. Er is geen algemene GIS-engine toegevoegd.

Het bewijsrecord wordt opgeslagen in `finding_history` en in het `finding_resolved`-auditevent. Het bevat onder meer de integratierevisie, inputrevisies, gecontroleerde objecten, geometriebegrenzingen en specialistobject-ID’s.

### F2 — foutaudit na rollback van menselijke transacties

`HumanApprovalService` vangt nu alle uitzonderingen rond approval- en risk-besluiten. De beslissingstransactie verlaat eerst de transactiescope en rolt volledig terug. Daarna wordt, zolang opslag/audit beschikbaar is, één afzonderlijke `human_decision_failed`-audit geschreven met gesaneerde foutinformatie. Een fout in die tweede audittransactie wordt niet verborgen en kan geen gedeeltelijke beslissing opleveren.

### F3 — eenduidige variantreferenties en lineage

`decision_variants()` zet lokale hypothese-ID’s om naar geregistreerde `DesignObject`-ID’s zoals `A03_HYPOTHESIS/v1/compact`. Het DecisionPackage bevat nu:

- `variant_id`;
- `hypothesis_revision_id`;
- rechtstreeks resolveerbare `object_ids`;
- `integration_revision_id`;
- `integrated_object_ids`.

Integratie valideert dat de gekozen variant uit de actuele hypothese komt. Geïntegreerde objecten dragen dezelfde variant- en hypotheseobjectreferenties in hun properties.

### F4 — actuele testrun en codeversie

`scripts/validate_milestone_2b.py` voert voor elk bewijs eerst de actuele volledige `test.ps1` uit. Het script accepteert geen lege, falende of nul-tests-uitvoer, vergelijkt de broncode-identiteit vóór en na de testrun en slaat Git-HEAD, bronmanifest, testtijdstippen, exitcode, aantal tests, looptijd en loghash op. Daarna draait het een nieuwe geïsoleerde synthetische demo tweemaal en controleert replay-identiteit.

Een oud `milestone-2b-tests.txt`-bestand wordt niet meer als nieuwe testuitvoering gebruikt.

## Nieuwe regressietests

`tests/test_milestone_2b1.py` bevat 20 gerichte tests:

- F1: oorspronkelijke/conflicterende geometrie, geforceerde tekstuele resolutie, onbekende finding, ontbrekend specialistobject en opgeslagen verificatiebewijs;
- F2: rollback/audit voor APPROVED, REJECTED en ACCEPTED_RISK, fout na success-audit en onbeschikbare foutaudit;
- F3: resolveerbare DecisionPackage-referenties, hypothese-lineage, afwijzing van oude variantreferenties en iteratielimietpakket;
- F4: oud succeslog, actuele codebinding, codewijziging tijdens testrun en ongeldige testuitvoer.

## Volledige validatie

- Testsuite: **114/114 OK**.
- Synthetische demo: `DESIGN-TEST-001`.
- Eindstatus: `AWAITING_HUMAN_APPROVAL`.
- Integraties: 1.
- A07: `PASS_WITH_FINDINGS`.
- Human approval: `null`.
- Audit-events: 31.
- Replay: exact identiek, zonder duplicaten.
- SQLite-integriteitscontrole: `ok`.
- Canonieke SQLite-audit en JSONL-export: gelijk.
- Alle objecten: `source_status=TESTDATA`.
- Specialistische resoluties: twee, beide met geometrie- en revisiebewijs.
- Historische runtime-/documentbestanden: ongewijzigd volgens hashcontrole.

De bijgewerkte bewijsbestanden zijn `docs/milestone-2b-tests.txt`, `docs/milestone-2b-result.json`, `docs/milestone-2b-audit.jsonl` en `docs/milestone-2b-integrity.json`.

## Behouden grenzen en resterende beperkingen

De bestaande Human Approval-, provider-, K00-, TESTDATA-, provenance-, audit-, idempotentie-, stale-review- en state-machinegrenzen zijn behouden. De verificatie is bewust beperkt tot de huidige synthetische rechthoekfixture. Zij is geen algemene geometrie-engine en ondersteunt geen echte GIS-bronnen, formeel milieuonderzoek, verkeersmodellering, multi-hostconcurrentie of productie-authenticatie. Menselijke identiteit blijft de bestaande lokale vertrouwensgrens.
