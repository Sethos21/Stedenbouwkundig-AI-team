# Statusmachine en workflow

| Huidige status | Toegestane volgende status |
|---|---|
| DRAFT | READY, BLOCKED, FAILED |
| READY | RUNNING, BLOCKED, FAILED |
| RUNNING | SPECIALIST_COMPLETE, BLOCKED, FAILED |
| SPECIALIST_COMPLETE | REVIEW_PENDING, BLOCKED, FAILED |
| REVIEW_PENDING | REVIEWED, READY (revisie), BLOCKED, FAILED |
| REVIEWED | AWAITING_HUMAN_APPROVAL, BLOCKED, FAILED |
| AWAITING_HUMAN_APPROVAL | APPROVED of REJECTED, uitsluitend HumanApprovalService |
| BLOCKED | READY |
| FAILED | READY |
| APPROVED | Geen |
| REJECTED | Geen |

Bijkomende guards: specialist-output is verplicht voor specialist completion en reviewaanvraag; een voldoende review is verplicht voor REVIEWED en de menselijke wachtstatus. A01 coördineert normale overgangen. Ook A01 kan nooit definitief beslissen.

1. A01 maakt GIS-001 uit de fixture, met DRAFT → READY.
2. A01 wijst A02 toe en start RUNNING.
3. A02 inventariseert vier synthetische bronregisteritems. Outputvalidatie bewaakt schema, provenance en TESTDATA.
4. A01 controleert output, zet SPECIALIST_COMPLETE → REVIEW_PENDING en wijst A07 toe.
5. A07 geeft SUFFICIENT of INSUFFICIENT, nooit APPROVED.
6. Onvoldoende: concrete punten bewaren, revision_requested auditen, terug naar READY. resume levert een nieuwe outputversie.
7. Voldoende: A01 zet REVIEWED → AWAITING_HUMAN_APPROVAL en stopt.
8. Een afzonderlijk menselijk CLI-besluit kan APPROVED of REJECTED zetten. Elk herhaald of ongeldig besluit wordt geweigerd en geaudit.

Alle outputversies blijven bestaan. Reviews verwijzen naar een outputversie. Human approval staat op de taak, met tijdstip en actor; eerdere agentoutput wordt niet achteraf als door een agent goedgekeurd herschreven.
