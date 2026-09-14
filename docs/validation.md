# Milestone 1 — validatie

Oorspronkelijke validatie uitgevoerd op 10 september 2026 in de opgegeven UNC-projectmap.
Actuele taak- en git-status gecontroleerd op 11 september 2026 bij de start van Milestone 2A.

## Resultaten

- Python 3.12.14, standaardbibliotheek, geen externe runtimepackages.
- Volledige suite: **35 tests geslaagd**, 17,587 seconden; exitcode 0.
- Eerste run ontdekte drie Windows-codepagefouten in CLI-uitvoer. De CLI schrijft nu expliciet UTF-8; de volledige suite is daarna opnieuw uitgevoerd en geslaagd.
- GIS-001 is na de tests uitgevoerd in runtime/state.sqlite3.
- Actuele eindstatus: **APPROVED**. De oorspronkelijke workflow stopte op AWAITING_HUMAN_APPROVAL; daarna volgde het afzonderlijke menselijke besluit.
- Review: **SUFFICIENT**, uitsluitend voor de synthetische demonstratie.
- human_approval: **aanwezig**, human_actor **Seth**, decision **APPROVED**, timestamp **2026-09-10T15:28:45.072834+00:00**, notes leeg.
- Vier bronreferenties, alle **TESTDATA**; geen echte downloads, geometrie of ontwerp.
- Snapshot: [gis-001-result.json](gis-001-result.json).
- Historisch auditbewijs vóór goedkeuring: [gis-001-audit.jsonl](gis-001-audit.jsonl), bewust ongewijzigd. De canonieke runtime/state.sqlite3 en de overeenkomende runtime/audit.jsonl bevatten aanvullend het human_approved-event van Seth op 2026-09-10T15:28:45.074834+00:00.
- De blijvende demo is expliciet goedgekeurd door de menselijke actor Seth. Het bijgewerkte resultaatsnapshot is alleen-lezen uit de actuele database overgenomen; geen besluit opnieuw uitgevoerd en geen historische auditdata gewijzigd.

## Dekking gevraagde controles

| Eis | Bewijs in tests/test_runtime.py |
|---|---|
| A01 roept A02 aan | test_a01_calls_a02_then_a07 |
| Provenance | test_provenance_is_complete_and_testdata |
| A07 review | test_review_sufficient_and_bound_to_version |
| Voldoende review → wachten | test_demo_stops_before_human_approval |
| Geen agent kan APPROVED zetten | test_all_seven_agents_cannot_approve_or_reject |
| RUNNING → APPROVED verboden | test_running_to_approved_is_denied_even_to_human_route |
| Alleen menselijke service | test_service_cannot_be_constructed_by_agent; test_agent_session_has_no_human_service |
| Approvalaudit | test_human_service_approval_is_audited |
| TESTDATA blijft TESTDATA | test_testdata_cannot_be_reclassified_as_verified; test_verified_source_inside_fixture_output_is_denied |
| K00 immutable | test_k00_cannot_be_written_regenerated_or_modified |
| A02 geen design-output | test_a02_cannot_register_design |
| GIS-001 wacht | test_demo_stops_before_human_approval |
| Expliciete CLI-route kan goedkeuren | test_cli_manual_approval_in_isolated_test_store |
| Ongeldige/herhaalde besluiten | test_duplicate_approval_preserves_first_decision; test_unknown_task_and_invalid_decision_are_rejected |

Aanvullend getest: alle statusparen, afwijzing, verplichte actor, alle agentnamen als verboden menselijke actor, revisiepunten en versiebehoud, providerfouten, kwaadaardig APPROVED-reviewverdict, inactieve rollen, ontbrekende output, ontbrekende/verouderde review, bronreferentiemismatch, persistentie tussen Store-instanties, JSONL-export, lees-CLI, projectpadbegrenzing en kopiegedrag van mocks.

## Garantie en beperkingen

Binnen de geleverde runtime kan agentoutput geen definitief besluit veroorzaken. Definitieve workflowovergangen worden altijd geweigerd; de provider heeft geen approval-tool of capability. De positieve approvaltests simuleren een expliciete CLI-/serviceaanroep uitsluitend in tijdelijke testopslag.

Dit bewijst geen bescherming tegen iemand die Python-code of databasebestanden rechtstreeks wijzigt, een onbetrouwbare plugin laadt of de CLI buiten deze runtime aan een agent beschikbaar stelt. Productie-authenticatie en procesisolatie zijn bewust niet gebouwd. Een opgegeven menselijke naam is lokaal niet geverifieerd.

De netwerkmap ondersteunt deze geteste sequentiële uitvoering. Multi-hostconcurrentie, SMB-uitval en automatische crashrecovery zijn niet gevalideerd. audit.jsonl is een herbouwbare export; SQLite bevat de canonieke transactionele audit.

## Technische keuzes en afwijkingen

- Namespace src/bvc_ai met de gevraagde lagen, ter voorkoming van modulebotsingen.
- Canonieke opslag en audit in SQLite; leesbare auditexport in JSONL.
- CLI gebruikt status/review/audit rechtstreeks, zonder extra geneste subcommando's.
- Python was niet aanwezig en is binnen .tools geïnstalleerd. uv kon geen verkorte versielink op de share maken; de launcher gebruikt de werkende interpreter rechtstreeks. Geen globale Pythonregistratie of Git-configuratie gewijzigd.
- Geen integraties of onderdelen buiten Milestone 1 toegevoegd.
- Milestone 1 is gecommit: 8245141cb44d3922011f82f317320eb22fe7dcc2, 'Milestone 1 - basis AI ontwerpteam', 10 september 2026 om 17:33:29 +0200. Branch master was schoon bij de start van Milestone 2A. De nieuwe Milestone-2A-wijzigingen zijn nog niet gecommit.

## Oorspronkelijk vervolgadvies en Milestone 2A

Werk eerst de geauthenticeerde menselijke beslisroute en rechten uit. Voeg daarna één read-only officiële bronadapter toe, met expliciete bronlicentie, herkomst, actualiteit, CRS-controles en K00-integriteitscontrole. Koppel pas daarna een echte AI-provider via AIProvider, zonder approval- of shelltools.

Milestone 2A is vervolgens expliciet beperkt tot een optionele OpenAI-provider, zonder authenticatie of bronintegraties. Zie [milestone-2a.md](milestone-2a.md) voor de actuele uitbreiding en validatie. De bovengenoemde 35 tests en looptijd zijn historische M1-resultaten.
