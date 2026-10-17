# Ontwikkelrichtlijnen — hergebruik en open source

## Doel
Bij substantiële nieuwe functionaliteit eerst aantoonbaar onderzoeken of bestaande projectcode of een betrouwbare open-sourcecomponent geschikt is. Dit is een onderzoeks- en beslisregel, geen toestemming om bestaande architectuur of goedgekeurde keuzes te vervangen.

## Werkwijze
1. Lees eerst README.md, AGENTS.md, relevante docs, huidige implementatie en tests. Identificeer reeds beschikbare functionaliteit en vastgelegde besluiten.
2. Formuleer de concrete behoefte en acceptatiecriteria; zoek vervolgens gericht naar maximaal drie serieuze bestaande oplossingen.
3. Vergelijk: intern hergebruik, externe integratie en zelfbouw. Beoordeel functionele dekking, architectuurpassing, volwassenheid/onderhoud, testbaarheid, veiligheid, licentie en verplichtingen, afhankelijkheden, kosten en migratierisico.
4. Adviseer één optie met onderbouwing, alternatieven, onzekerheden en eventuele beperkte proof-of-concept in een aparte branch.
5. Vraag Seth vooraf toestemming voor belangrijke architectuurwijzigingen, nieuwe externe afhankelijkheden, vervanging van goedgekeurde onderdelen en definitieve functionele besluiten. Zonder akkoord alleen onderzoeken en documenteren.
6. Leg het besluit en de relevante bronnen vast in de projectdocumentatie. Laat implementatie, tests en opleverrapportage aansluiten op de bestaande projectafspraken.

## Specifieke projectgrenzen
- Behoud de acht-agent-ontwerpvisie en de daadwerkelijk geactiveerde rollen zoals in de actuele milestone beschreven; ga niet uit van acht actieve agents.
- HumanApprovalService, K00-policy, capabilitygrenzen, bronherkomst, audittrail en expliciete live opt-in blijven leidend.
- Open-sourceonderzoek verleent geen toestemming voor het uitvoeren van externe code, willekeurige netwerkcalls, nieuwe GIS-bronnen of productiedata.
- Controleer vóór gebruik altijd de concrete licentie en beveiligings-/onderhoudsstatus; GitHub-stars zijn geen kwaliteitsgarantie.
- Houd het BVC AI Ontwerpteam gescheiden van de BVC Financiële Rapportagetool.

## Eerste onderzoeksvragen (nog geen keuze)
- Is het bestaande workflow- en agentorkestratiesysteem voldoende, of voegt een framework aantoonbaar iets toe?
- Welke bestaande, licentiegeschikte componenten helpen bij officiële BAG/BGT/PDOK-data, geometrieverwerking en bronvalidatie zonder de bestaande keten te omzeilen?
- Welke bestaande oplossingen verbeteren reproduceerbare evaluaties, reviews en rapportage zonder menselijke goedkeuring over te nemen?
