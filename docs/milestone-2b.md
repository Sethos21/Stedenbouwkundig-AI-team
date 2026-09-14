# Milestone 2B — Ontwerplus

Uitsluitend synthetische TESTDATA. Geen echte locatie, formeel specialistisch onderzoek of externe calls. De kaart/presentatie is een afgeleide weergave van het ruimtelijke model, nooit geometrische bronwaarheid.

## Reproduceren

Vanuit de projectmap:

```powershell
.\test.ps1
.\bvc-ai.ps1 demo design-test-001
.\bvc-ai.ps1 --data runtime/milestone-2b design-report DESIGN-TEST-001
.\bvc-ai.ps1 --data runtime/milestone-2b status DESIGN-TEST-001
.\bvc-ai.ps1 --data runtime/milestone-2b audit DESIGN-TEST-001
```

De demo kiest altijd de submap `milestone-2b` onder `--data` (standaard `runtime`). Leescommando's en `resume` gebruiken de expliciet opgegeven opslagmap. Herhaling van de voltooide demo is een no-op: geen nieuwe objecten, findings, reviews, beslisvragen of auditevents. Voor een zelfstandige nieuwe demonstratie kan `--data .tools/mijn-test` worden gebruikt; ook daar komt de submap `milestone-2b`.

`demo design-test-001` weigert `--provider openai`. De OpenAI-adapter heeft een expliciet niet-ondersteunde `design_step`, zonder netwerkcall. De bestaande Milestone-2A inventory/review-route blijft beschikbaar en ongewijzigd in gedrag.

## Architectuur en rolcontext

De bestaande `Workflow`, `config/agents.json`, GIS-statusmachine en 57 bestaande tests behouden hun Milestone-1/2A-semantiek. `DesignWorkflow` biedt uitsluitend binnen `ONTWERPLUS_2B` de acht rollen aan. Providers ontvangen kopieën van voorstelcontext en inputrevisies, geen Store, sessie, capability, shell of tools. De enige methode op een `DesignSession` is het aanbieden van een rolgebonden stap.

`domain/design.py` bevat AgentTask, Handoff, DesignObject, Finding, ReviewResult, DecisionRequest, RevisionDependency en HumanDecision. `design_validation.py` bewaakt een gesloten voorstelschema; runtime-identiteit, revisions, status, object-ID's en capaciteit worden door domein/application-code bepaald. Geen databasewijziging of migratie van historische taken is nodig: de bestaande JSON-taakopslag en SQLite-audit worden hergebruikt.

| Stap | Verplichte actuele invoer | Roloutput |
|---|---|---|
| A01_START | Geen | Coördinatie |
| A02 | A01_START | Synthetische grens, watergang en drie bronzones |
| A06 | A02 | HARD_CONSTRAINT, STEERING, UNCERTAIN |
| A08_GATE | A02, A06 | Alle 13 milieuthema's, indicatief risico en MAJOR finding |
| A03_HYPOTHESIS | A02, A06, A08_GATE | Twee ruimtelijk verschillende varianten |
| A04 | A03_HYPOTHESIS | Landschapsobject en finding |
| A05 | A03_HYPOTHESIS | Toegangsobject en finding |
| A03_INTEGRATION | Hypothese, A04, A05 | Nieuwe revision, ontwerpobjecten en findingverwerking |
| A04_REVIEW, A05_REVIEW, A08_REVIEW | Exacte integratie plus transitive inputrevisies | Vakreview |
| A07 | Alle drie voldoende actuele vakreviews | Gemeentelijke review en inhoudelijke finding |
| A01_PACKAGE | Actuele voldoende A07-review | Beslispakket; AWAITING_HUMAN_APPROVAL |

A04 en A05 hebben geen onderlinge uitvoeringsafhankelijkheid. Beide uitvoervolgordes worden getest. Integratie eist actuele output van beide op dezelfde hypothese en upstream basis. Parallelle callers kunnen voorstellen onafhankelijk voorbereiden; commitconflicten worden geweigerd en geaudit. De deterministische demonstratie voert de takken sequentieel uit. Er is geen multi-host scheduler toegevoegd.

## Geometrie en findings

Geometrie staat in een lokale synthetische metrische fixture. Providers mogen alleen naar deze geregistreerde modelgeometrie verwijzen. PNG/JPG/PDF en onbekende refs kunnen niet worden geregistreerd. A02 schrijft uitsluitend versiegebonden bronobjecten met EXISTING_VALIDATED én source_status TESTDATA: dit is geen officiële validatie van echte bronnen. Bestaande objectrecords worden nooit gewijzigd. A03 schrijft uitsluitend PROPOSED ruimtelijke ontwerpobjecten, A04 landschappelijke en A05 mobiliteitsobjecten. A01, A06, A07 en A08 mogen geen geometrie schrijven. K00Policy wordt bij objectregistratie toegepast; K00 blijft gelockt.

Capaciteit volgt uit polygonoppervlak maal een expliciete dichtheidsaanname; een provider mag geen capaciteit invoeren. Compacte hypothese: 41.800 m² × 40/ha = 167 woningen (naar beneden afgerond). Lineaire hypothese: 14.000 m² × 25/ha = 35. Integratie: 23.800 m² × 40/ha = 95. Dit zijn uitsluitend synthetische scenario-uitkomsten.

Alle findings bevatten eigenaar, severity, revision en inputrevisies. Ze ontstaan OPEN. Een specialist kan bij eigen review UNRESOLVED of BLOCKED vastleggen; resolutie vereist eigenaarschap en een verwerking in de exacte integratierevision. Elke statuswijziging wordt geaudit en in finding_history bewaard. A03 kan verwerking voorstellen maar geen eigen resolutie van specialistische findings toekennen. OPEN/UNRESOLVED/BLOCKED CRITICAL findings blokkeren downstream gates. Onzekerheden en RESEARCH_REQUIRED blijven expliciet zichtbaar, nooit impliciete toestemming.

## Revisies en iteraties

Elke output heeft een unieke `stap/vN` revision. Afhankelijkheden bevatten de volledige upstream closure. Een wijziging invalideert alleen afhankelijke actieve outputs en reviews. Historische outputs, objecten en reviews blijven behouden; stale markeringen staan apart. Een resolutie die op een stale review rust, heropent de finding met audit. De volgende integratie ontvangt deze heropende verplichting. Een bestaande review kan niet op dezelfde integratie door een ander verdict worden vervangen; daarvoor is een nieuwe integratierevision nodig.

REVISE stuurt naar A03_INTEGRATION. Maximaal drie integraties worden automatisch gecommit per ontwerpbesluit (inclusief de eerste integratie). De vierde aanvraag roept geen ontwerp-provider aan en maakt geen ontwerpobjecten. Ze commit uitsluitend de expliciete overgang REQUIRES_HUMAN_DECISION met beslisvraag en iteratielimietaudit. De teller wordt niet door upstream wijzigingen gereset. Er is geen automatische voortzetting voorbij deze grens.

## Transacties, idempotentie en audit

1. Lees een consistente taaksnapshot, toets gates en verzamel exacte inputrevisies.
2. Laat de provider buiten de schrijftransactie een voorstel maken op kopieën; valideer de gehele output.
3. Start BEGIN IMMEDIATE en controleer dat de taak nog exact overeenkomt met de gebruikte snapshot.
4. Commit alle domeinmutaties, findinghistorie, dependencies, idempotencyregistratie en succesaudit in één SQLite-transactie.
5. Bij fouten: rollback van de gehele stap; vervolgens één afzonderlijke audittransactie voor step_failed. Gate- en schemafouten krijgen een concrete reden. Provider-/opslagfoutdetails worden niet ongefilterd opgeslagen.

Een key is taakgebonden. De requestfingerprint bindt stap, actor en aangeboden expected_inputs. Replay van dezelfde succesvolle key levert de actuele taak zonder een nieuwe providercall of mutatie. Een andere request onder dezelfde key wordt geweigerd. Wie bewust een nieuwe revisie wil, gebruikt een nieuwe key en kan expected_inputs meegeven; bestaande keys zijn replays, ook wanneer upstream later is veranderd. Resultaatrevision en gebruikte inputrevisies worden bij de key bewaard. Dezelfde strategie geldt optioneel voor menselijke besluiten via een aparte human_idempotency-registratie. De bestaande legacy-regel dat herhaalde menselijke besluiten zonder key worden geweigerd blijft intact.

SQLite is canoniek; audit.jsonl is de herbouwbare projectie. Foutinjectie ná de SQL-statewrite bewijst rollback van zowel domeinwrites als succesaudit. Een tweede Store die tijdens provideruitvoering de taak wijzigt veroorzaakt een geauditeerde conflictweigering.

## Menselijke route

HumanApprovalService blijft de enige ingang voor APPROVED, REJECTED en ACCEPTED_RISK. A01 tot en met A08 worden ook daar als menselijke actor geweigerd. De lokale CLI composeert de bestaande capability; providers krijgen deze nooit. Goedkeuring vereist de menselijke wachtstatus en alle actuele revision-bound reviews. Menselijke risicoacceptatie vereist een concrete finding en motivering; ze maakt een bestaand beslispakket stale zodat het opnieuw moet worden samengesteld. Historische menselijke beslissingen worden nooit overschreven.

De CLI ondersteunt `accept-risk <task_id> <finding_id> --actor <mens> --reason <motivering>` en optioneel `--idempotency-key`. Goedkeuren/afwijzen gebruikt de bestaande CLI-route. Deze routes zijn uitsluitend in geïsoleerde tests uitgevoerd. DESIGN-TEST-001 blijft onbeoordeeld door een mens.

## Bewijs en grenzen

Zie [validatierapport](milestone-2b-validation.md), [eindstate](milestone-2b-result.json), [audit](milestone-2b-audit.jsonl) en [testuitvoer](milestone-2b-tests.txt). `scripts/validate_milestone_2b.py` voert de CLI-demo tweemaal uit, verifieert idempotentie, wachtstatus, TESTDATA, auditprojectie en ongewijzigde historische bestanden, en genereert snapshots plus integriteitsbewijs.

De fixture is een begrensd synthetisch ruimtelijk model; er is geen algemene geometrie-engine, verkeersberekening, regelgevingsinterpretatie of formeel milieuonderzoek. De deterministische specialistische oordelen demonstreren de workflow. Vertrouwde Python-code en lokale CLI-identiteit zijn dezelfde procesinterne grens als voorheen; geen bescherming tegen kwaadwillende Python-plugins of rechtstreekse databasebewerking. Multi-host SMB-concurrentie, uitval van de opslag en productie-authenticatie zijn niet gevalideerd. Bij opslaguitval kan ook de afzonderlijke foutaudit mislukken; die fout wordt doorgegeven.

Niet geïmplementeerd: PDOK, BGT, BAG, BRK, QGIS, Google Drive runtime, websearch, Autodesk Forma, verkeersmodellen, kaartgeneratie, dashboard, productie-authenticatie, deployment, echte Mastenbroekweg-data of Milestone 2C. Geen Git-commit uitgevoerd.
