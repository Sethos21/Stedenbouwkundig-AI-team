# Milestone 2D - hervatbare voortgang

Datum: 29 september 2026.
Baseline: 03051103ddec842b2be3b6d6aa0aa5553b7444cc.
Geaccepteerde 2C closure: 65dcc27d38b4a3c2a5462f6c39380eb1685b6893.
Werkbranch: milestone-2d-work. Huidige fase: 2D-4 voorbereiding.
Baseline geverifieerd; Release 1-reviewbranch niet geintegreerd.

| Fase | Status | Fasecommit | Tests |
|---|---|---|---|
| 2D-1 | PASS | a54ccc4498701b01a7c073fdc1d433980cda6396 | 427/427 PASS, 65.154 s |
| 2D-2 | PASS | 399cfc3 | Targeted 9; full 436 PASS |
| 2D-3 | PASS | Checkpoint: Milestone 2D-3 - official BAG contracts | Targeted 14; full 441 PASS |
| 2D-4 | NOT_STARTED | Geen | Niet uitgevoerd |
| 2D-5 | NOT_STARTED | Geen | Niet uitgevoerd |
| 2D-6 | NOT_STARTED | Geen | Niet uitgevoerd |

## Besluiten Seth

29 september 2026: optie 1, beperkte Milestone-2D-netwerkuitzondering goedgekeurd.
Toegestaan: read-only officiele PDOK BGT/BAG-contractinspectie; begrensde live fetches
binnen vooraf vastgelegde officiele endpoints/scopes; lokale raw evidence, hashes,
provenance en validatiebewijs; expliciete live opt-in voor live proof; uitsluitend
noodzakelijk netwerkverkeer voor deze keten. Geen productiecredentials, cloudwrites,
arbitrary URL/netwerk, andere integraties of niet vooraf toegestane bronnen.
Capability-, provenance-, K00- en Human Approval-grenzen blijven intact.
AGENTS.md en het faseverslag zijn hiermee bijgewerkt. Dit besluit is afgehandeld;
geen nieuwe toestemming nodig voor afzonderlijke fetches binnen deze grenzen.

## Uitgevoerd

2C-hergebruik geinventariseerd; zes BGT-contextlagen voorgesteld. Officiele BGT/BAG
metadata plus negen schemas via 11 vaste metadatarequests gecontroleerd (HTTP 200).
Raw contractbewijs: .tools/2d-contracts/; compact bewijs:
docs/milestone-2d-contract-inspection.json. Geen features opgehaald, geen productie-
code gewijzigd. Broncontract: docs/milestone-2d-phase1-source-contract.md.

## Afgehandelde BAG-keuze

Besluit Seth: BAG pand EN verblijfsobject opnemen, beide zelfstandig met eigen identiteit/provenance.
Officiele bronrelaties, geen synthetische samenvoeging of LLM-afleiding.
De onderstaande opties zijn alleen beslisgeschiedenis.
Optie 1 (voorkeur): BAG pand + verblijfsobject voor gebouwcontext en individuele
gebruiksdoelen/oppervlakten/adrescontext. Optie 2: alleen pand, geen individuele
VBO-/adrescontext. Beide zijn officiele PDOK-bronnen binnen de reeds goedgekeurde
netwerkuitzondering; de keuze betreft productinhoud, niet fetchtoestemming.
Protocol paragraaf 4 en BAG-gate: materieel verschillende productuitkomsten.

Bekende beperkingen: contract vastgesteld; actuele BAG-featurewaarden
niet onderzocht. Geen claim op volledige BGT-vlakdekking of point-in-timeconsistentie.
Technische selecties binnen officiele semantiek en vastgesteld A02-doel zelfstandig uitvoeren;
geen automatische DECISION_REQUIRED voor zulke selecties. Geen nieuwe dependencies.
Uitgesloten untracked items ongemoeid; master blijft op baseline.

Next action: 2D-4 actueel samengesteld A02-bronbeeld met bron- en revisiereferenties.
Geen open beslisgate. Geen nieuwe toestemming nodig voor de netwerkuitzondering.
