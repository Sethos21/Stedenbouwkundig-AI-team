# MVP-route A — locatiegericht stedenbouwkundig onderzoek

Status: **functionele route A goedgekeurd door gebruiker op 13 november 2026**. Dit plan is een gefaseerd uitvoeringskader, **geen vrijgave van afzonderlijke Codex-opdrachten, agentactivatie, live bronaanroepen, merges of functionele keuzes buiten de vastgestelde kaders**.

## Doel en eerste acceptatie

Een gebruiker voert een eenduidig adres in en krijgt een **indicatieve, reproduceerbare haalbaarheidsverkenning** met (1) locatie en broncontext, (2) planologische broninformatie met versie/peildatum en onzekerheden, (3) maximaal twee transparante ontwikkelscenario's op basis van expliciete aannames, en (4) een risico-, onderzoeksvragen- en bronnenrapport. Het resultaat is geen vergunningadvies, bindende juridische toets of automatisch goedgekeurd ontwerp. Bij ontbrekende/tegenstrijdige gegevens: expliciet onbekend of veilig stoppen, nooit aannames als officiële feiten presenteren.

## Vaststaande architectuur en grenzen

- Hergebruik de bestaande A01-workflow, revisies, audit, A02-BAG/BGT/PDOK-adresresolutie en bronopslag, A06-DSO-services, ontwerpvariantlineage, A07-reviews, A08-thema's en read-only presentatie waar daadwerkelijk bruikbaar.
- Behoud de acht-agentarchitectuur en de huidige rolvolgorde: A01 → A02 → A06 → A08_GATE → A03_HYPOTHESIS → A04/A05 → A03_INTEGRATION → A04/A05/A08_REVIEW → A07 → A01_PACKAGE. Voor de MVP mogen niet-onderbouwde specialistische stappen alleen expliciete onderzoeksvragen/onzekerheden opleveren, geen fictieve inhoudelijke goedkeuring.
- HumanApprovalService blijft de enige definitieve menselijke beslisgate. K00 immutable. Geen provider krijgt CLI, shell, Store, filesystem, bronmutatie of approval-capability.
- Bestaande officiële bronautorisaties blijven gelden; nieuwe live bronnen/endpointscopes, credentials, cloud/ChatGPT-koppelingen, agentactivatie of externe gegevensdeling vereisen afzonderlijk besluit. TESTDATA, historische evidence en actuele live bronnen worden onderscheiden.
- Leidend technisch referentiekader: `docs/reviews/TECHNISCHE_NULMETING_INTEGRATIEPLAN_2026-11-12.md` op commit `1587c498e8218d04dd77ef2c9a67851fe3256dc1`; A06-karakterisatie `docs/reviews/A06_IDENTITY_CHARACTERIZATION_ISSUE_6.md` op `bee837908e3e555e91690360d5e15dfd00db316c` (PR #7). A06-issue #6 is GEBLOKKEERD; dit plan geeft geen toestemming tot validatorwijziging of merge van PR #7.
- Master bevat nog niet alle A06-featurecommits; integratie is **niet** stilzwijgend goedgekeurd. Verouderde README-beschrijvingen gelden niet boven actuele commitvaste reviews.

## Fasen en acceptatiecriteria

| Fase | Opdrachtomvang | Minimale acceptatie / stopcriterium |
|---|---|---|
| **MVP-00 — Integratiegereedheid** | Eén kleine read-only repositoryanalyse; geen codewijziging | Commitvaste component- en afhankelijkhedenmatrix; precieze functies, branches, interfacegrenzen, bestaande tests en ontbrekende koppelingen; voorstel voor één **offline** adres→locatiedossier-proef met reeds bewaarde evidence; één begrensde volgende opdracht. Geen aannames over beschikbaarheid van echte bronnen. |
| **MVP-01 — Adres naar locatiedossier** | 2–3 kleine opdrachten na afzonderlijke vrijgave | Eén eenduidig adres → reproduceerbare BAG/BGT-context met geometrie, hashes, provenance, peildatum en onzekerheden; ambigue adressen, ontbrekende records en bbox/projectgrens-verwarring falen veilig; geen TESTDATA als echt presenteren. |
| **MVP-02 — Planologische broncontext** | 2–4 kleine opdrachten, afhankelijk van afzonderlijke A06-contractbeslissing | DSO-documenten met letterlijke ID, versie, tijd en herleidbaar bronbewijs; onduidelijke toepasselijkheid blijft onbekend; geen normalisatieversoepeling zonder officieel onderbouwd contract, tests en aparte goedkeuring. |
| **MVP-03 — Indicatieve ontwikkelscenario's** | 2–3 kleine opdrachten | Twee transparante scenario's met bron-/afgeleide geometrie, expliciete aannames, berekende oppervlakten en beperkingen; revisie- en lineagecontroles; geen ongefundeerde bouwrechten of ontwerpclaims. |
| **MVP-04 — Risico, review en rapport** | 2–3 kleine opdrachten | Rapport onderscheidt bronfeit, afleiding, aanname, onzekerheid en onderzoeksvraag; relevante A08-thema's en A07-review zichtbaar; kritieke onbekenden worden niet PASS; stopt vóór menselijke beslissing. |
| **MVP-05 — Pilot en acceptatie** | 1–2 kleine opdrachten | Eén echte locatie onder afzonderlijk geautoriseerde bronvoorwaarden, vergelijking met handmatige beoordeling, reproduceerbare bronketen, veilige foutafhandeling, onafhankelijke review en expliciete gebruikersacceptatie. |

Deze aantallen zijn **planningsinschattingen, geen toegezegde doorlooptijd**. Fasen mogen alleen na een nieuwe expliciete gebruikersvrijgave worden uitgevoerd. Een offline proef met historische brongegevens is geen bewijs van actuele locatieconformiteit.

## Bewust buiten MVP

Geen volledige autonome agentorganisatie, nieuwe scheduler, kaarteditor/3D, algemene Drive/QGIS/ChatGPT-integratie, financiële grondexploitatie, volledige verkeers- en milieumodellen, juridische eindtoets of productiecloud. Bestaande functionaliteit niet herbouwen.

## Zuinig Codex-protocol

1. Eén GitHub Issue per begrensde taak; `docs/OPDRACHTENBUS.md` en `AGENTS.md` blijven leidend. **Voorbereide Issues krijgen geen `[KLAAR_VOOR_CODEX]` vóór afzonderlijke expliciete vrijgave.**
2. Start met relevante bestandslijst, bestaande interface/test en een beperkte hergebruikscan; geen volledige repo-heranalyse als nulmeting al bestaat.
3. Tijdens ontwikkeling gerichte tests; brede regressie alleen bij passende integratie. Noteer werkelijk uitgevoerde tests, niet-gecontroleerde aannames en risico's.
4. Kort opleverrapport via `CODEX_OPLEVERING_V1` en draft-PR; onafhankelijke ChatGPT-review en gebruikersbesluit vóór merge.
5. Bij scopegroei of tokenlimiet: veilig checkpoint en stop. Geen tweede sessie/claim of ongevraagde vervolgfase.

## Besluiten en open punten

**Vast:** route A, acht-agentarchitectuur behouden, MVP indicatief, gefaseerde goedkeuring, maximaal hergebruik, geen automatische menselijke approval, tokenzuinig werken.

**Open:** selectie pilotlocatie, precieze MVP-scenarioaannames, officiële A06-identiteitsspecificatie en contractherstel, voorwaarden voor live bronproef, concrete rapport-UX, omvang van specialistische checks. Deze worden pas op het relevante fasebesluit voorgelegd; ontwikkelagents beslissen ze niet zelfstandig.

**Eerstvolgende stap:** voorbereid GitHub Issue **MVP-00** voor uitsluitend read-only integratiegereedheidsanalyse. Nog niet vrijgegeven; geen Codex-run.
