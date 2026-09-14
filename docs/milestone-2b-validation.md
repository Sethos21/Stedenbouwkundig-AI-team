# Milestone 2B — validatierapport

Validatie: 2026-09-14T10:35:51.571235+00:00. Uitsluitend synthetische TESTDATA.

## Basis en resultaat

- Fase 0: master, clean working tree, 57/57 bestaande tests geslaagd. Git rapporteerde c0ee3225cf9f6ab3873fc93195b479fa3fb7b7a7; de gebruiker bevestigde deze bedoelde Milestone-2A-basis na de gemelde hashafwijking.
- Definitieve suite: **99/99 tests geslaagd** (57 bestaande + 42 nieuwe), **44,105 seconden**, exitcode 0.
- Bestaande tests/test_runtime.py, tests/test_openai_provider.py en config/agents.json zijn ongewijzigd; git diff --exit-code bevestigde dit.
- De eerste ontwikkelruns vonden een syntaxfout en later twee falende tests door een escape-fout in de tokencontrole. Deze zijn hersteld; de volledige suite is daarna opnieuw groen uitgevoerd.
- Geen commit, reset, squash of wijziging van bestaande commits uitgevoerd.

## End-to-end

| Controle | Resultaat |
|---|---|
| Project/task | DESIGN-TEST-001 |
| Workflowstate | AWAITING_HUMAN_APPROVAL |
| Bronstatus | TESTDATA; volledig synthetisch lokaal model |
| Iteration count | 1 |
| A07 | PASS_WITH_FINDINGS |
| human_approval | null |
| Stale reviews | 0 |
| Audit event count | 31 |
| Objecten | 11; 5 bronobjecten en 6 voorgestelde ontwerpobjecten |
| Reviews | 4; alle op A03_INTEGRATION/v1 met exacte inputrevisies |
| Beslispakketten | 1 |
| Herhaalde CLI-demo | Exact dezelfde state en audit, geen duplicaten |
| Historisch behoud | 7 bestanden voor/na byte-identiek via SHA-256; inclusief runtime/state.sqlite3 en runtime/audit.jsonl |

Open findings: INFO=0, MINOR=0, MAJOR=2, CRITICAL=0.
De A04- en A05-findings zijn door hun eigenaar opgelost met verwijzing naar de integratie. Het indicatieve geluidrisico en de gemeentelijke onderzoeksvraag blijven MAJOR/OPEN. Geen risicoacceptatie of menselijk besluit op de demonstratie uitgevoerd.

## Actieve revisies en agentoutput

| Stap | Actieve revision |
|---|---|
| A01_START | A01_START/v1 |
| A02 | A02/v1 |
| A06 | A06/v1 |
| A08_GATE | A08_GATE/v1 |
| A03_HYPOTHESIS | A03_HYPOTHESIS/v1 |
| A04 | A04/v1 |
| A05 | A05/v1 |
| A03_INTEGRATION | A03_INTEGRATION/v1 |
| A04_REVIEW | A04_REVIEW/v1 |
| A05_REVIEW | A05_REVIEW/v1 |
| A08_REVIEW | A08_REVIEW/v1 |
| A07 | A07/v1 |
| A01_PACKAGE | A01_PACKAGE/v1 |

| Agent | Geleverde output |
|---|---|
| A01 | Startcoördinatie en beslispakket: twee varianten, vakreviews, open findings, risico, onzekerheden, historie en expliciete menselijke vraag |
| A02 | Projectgrens, immutable synthetische watergang, drie bronzones; EXISTING_VALIDATED met TESTDATA-herkomst |
| A06 | HARD_CONSTRAINT voor watergang, STEERING voor groenverbinding, UNCERTAIN voor functiemenging |
| A08 | Screening van 13 thema’s, indicatief ENVIRONMENTAL_RISK, MAJOR ruimtelijke finding; herreview houdt onderzoek open |
| A03 | Compacte en lineaire hypothese (167 en 35 afgeleide woningen); integratie met verschoven veld (95), centrale ruimte en findingverwerking |
| A04 | PROPOSED LANDSCAPE_STRUCTURE, landschappelijke finding en revision-bound review |
| A05 | PROPOSED_ACCESS, mobiliteitsfinding en revision-bound review |
| A07 | Inhoudelijke indieningsreview PASS_WITH_FINDINGS; onderzoek en parkeeronderbouwing ontbreken |

## Verplichte negatieve controles

| Eis | Test in tests/test_design_workflow.py (tenzij anders vermeld) |
|---|---|
| A03 vóór A08 | test_a03_before_environment_gate_denied |
| A03 wijzigt EXISTING_VALIDATED | test_a03_cannot_write_existing |
| A04/A05 stale review | test_a04_a05_stale_review_denied |
| Integratie zonder A04/A05 | test_integration_requires_both_specialists |
| Open CRITICAL A08 | test_critical_environment_finding_blocks_downstream |
| A07 schrijft ontwerp | test_a07_cannot_mutate_design_objects |
| A01 schrijft geometrie | test_a01_cannot_write_specialist_geometry |
| Provider APPROVED | test_provider_approved_and_accepted_risk_denied; test_approval_token_in_free_text_is_denied |
| Vierde cyclus | test_fourth_cycle_escalates_without_objects; test_approval_at_iteration_limit_is_denied_and_audited |
| A02 maakt reviews stale | test_a02_revision_stales_downstream_retains_history |
| Review N geeft N+1 niet vrij | test_old_review_cannot_release_new_revision |
| Presentatie wijzigt bron/geometriestatus | test_presentation_cannot_modify_source_or_geometry; test_k00_and_raster_registration_denied |
| Malformed output atomair geweigerd | test_malformed_provider_no_partial_state |
| Weigering geaudit | test_missing_input_failure_audit_identifies_gate; fails_unchanged-helper controleert state en exact één foutaudit |
| Bestaande securitytests | Alle 57 tests in test_runtime.py en test_openai_provider.py ongewijzigd geslaagd |

Aanvullend: A08 via menselijke route en legacy-route geweigerd; workflowgebonden activatie; omgekeerde A04/A05-volgorde en revisiemismatch; onafhankelijke branch behouden; heropenen bij stale resolutie; tweede herstelcyclus; reviewvervanging geweigerd; providerexception; foutinjectie na SQL-write; tweede-Store-conflict; idempotentie van alle stappen inclusief beslispakket; geïsoleerde menselijke CLI-besluiten en behoud eerste besluit.

## Architectuurkeuzes en bestanden

De Ontwerplus is een aparte context met rolgebonden stappen en transitive revision dependencies. State en succesaudit committen atomair met BEGIN IMMEDIATE; fouten rollen terug vóór een afzonderlijke foutaudit. Idempotency keys binden request en resultaatrevision. HumanApprovalService blijft de enige menselijke beslisroute. Zie [uitwerking](milestone-2b.md).

Gewijzigde bestaande bestanden:

- README.md: ingang naar Ontwerplus en bewijs.
- src/bvc_ai/agents/provider.py: design_step op AIProvider en deterministische implementatie.
- src/bvc_ai/agents/openai_provider.py: expliciete weigering van Ontwerplus-aanroepen.
- src/bvc_ai/application/approval.py: A08-afwijzing, actuele designgates, menselijke risicoacceptatie en optionele idempotentie.
- src/bvc_ai/cli/main.py: geïsoleerde demo, rapportage, resume-dispatch en menselijke risicoacceptatie.

Nieuwe bestanden:

- src/bvc_ai/domain/design.py en design_validation.py: domeinobjecten, afhankelijkheden, gates en voorstelvalidatie.
- src/bvc_ai/application/design_workflow.py: acht-agent uitvoering, transacties, revisies, iteraties en beslispakket.
- src/bvc_ai/agents/design_mock.py: synthetische specialistische voorstellen en reviews.
- src/bvc_ai/adapters/design_presentation.py: alleen-lezen presentatiegrens.
- examples/design-test-001.json: synthetisch geometrisch model.
- tests/test_design_workflow.py: 42 nieuwe tests.
- scripts/validate_milestone_2b.py: reproduceerbare CLI- en bewijsvalidatie.
- docs/milestone-2b.md, milestone-2b-validation.md, milestone-2b-tests.txt, milestone-2b-result.json, milestone-2b-audit.jsonl en milestone-2b-integrity.json: documentatie en bewijs.

Runtimebestanden staan uitsluitend in runtime/milestone-2b; tijdelijke uitvoer en implementatiehulpen uitsluitend onder .tools. Beide mappen blijven volgens de bestaande .gitignore buiten Git. Historische M1/2A-auditbestanden zijn niet herschreven.

## Resterende beperkingen en uitgesloten werk

Dit bewijst de deterministische workflow op een synthetische fixture. Het is geen formeel milieuonderzoek, algemene ruimtelijke constraintsolver of validatie van echte brongeometrie. Specialistische inhoud is TESTDATA. De bestaande lokale Python-/CLI-capabilitygrens blijft gelden; kwaadwillende plugins, productie-identiteitscontrole, multi-host SMB-uitvoering en opslaguitval zijn niet afgedekt. Bij iteratielimiet blijft menselijk vervolg nodig; geen automatische reset of vierde ontwerprun.

Niet geïmplementeerd: echte PDOK/BGT/BAG/BRK, QGIS, Google Drive runtime-integratie, websearch, Autodesk Forma, verkeersmodellen, kaartgeneratie, dashboard, productie-authenticatie, deployment, echte Mastenbroekweg-data of Milestone 2C.

## Bewijsbestanden

- [Volledige testuitvoer](milestone-2b-tests.txt)
- [Eindstate en rapportage](milestone-2b-result.json)
- [Audit snapshot](milestone-2b-audit.jsonl)
- [SHA-256 en herhaalbaarheidsbewijs](milestone-2b-integrity.json)
