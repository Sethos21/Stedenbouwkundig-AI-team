# Milestone 2D — Autonomous Orchestrator

## 0. Rol en doel

Je bent de uitvoerende Codex-regieagent voor **BVC AI Ontwerpteam — Milestone 2D: Real GIS Source Basis**.

Werk zelfstandig fase voor fase. Seth is beslisser, niet de menselijke promptdoorgever. Vraag Seth uitsluitend wanneer een echte beslisgate ontstaat zoals hieronder gedefinieerd. Als geen beslissing nodig is, ga zelfstandig door.

Deze opdracht vervangt **niet** `AGENTS.md`. Lees `AGENTS.md` eerst en behandel die regels als bindend. Bij conflict: STOP met `DECISION_REQUIRED`.

Baseline bij het opstellen van dit protocol:
- repository: `Sethos21/Stedenbouwkundig-AI-team`
- branch: `master`
- geaccepteerde Milestone-2C closure: `65dcc27d38b4a3c2a5462f6c39380eb1685b6893`
- `docs/MILESTONE_2C_VALIDATION.md` eindigt met `MILESTONE_2C: PASS`
- Milestone 2C heeft een bewezen smalle live PDOK/BGT-`pand` keten voor Mastenbroekweg 2, Weert.

Controleer bij start zelf de actuele lokale en remote baseline. Als master verder staat dan bovenstaande commit door uitsluitend dit orchestratorbestand, is dat toegestaan. Andere onverwachte wijzigingen: STOP.

## 1. Niet onderhandelbare architectuurgrenzen

Behoud de bewezen Milestone-2C-mechanismen. Herbouw ze niet zonder aantoonbare noodzaak.

- K00 / bestaande geometrische waarheid blijft beschermd en immutable.
- Alleen de trusted A02 source-import capability mag geïmporteerde officiële brongeometrie naar `EXISTING_VALIDATED` promoveren.
- Provider/adapter krijgt nooit die capability.
- Human Approval blijft uitsluitend menselijk; geen agent/provider simuleert `APPROVED`, `ACCEPTED_RISK` of menselijke identiteit.
- TESTDATA en echte provider-origin blijven expliciet gescheiden.
- Immutable bronhistorie mag niet worden overschreven.
- Incomplete fetch wordt nooit trusted.
- CRS wordt nooit uit coördinaten gegokt.
- Geen automatische geometry repair.
- Query-scope completeness is geen point-in-time garantie.
- Offline replay doet geen providerfetch en creëert geen alternatieve promotion-route.
- Geen generieke arbitrary-URL/network capability.
- Gebruik bestaande opslag, hashing, validation, provenance, pagination, retry, budget, atomicity, idempotence, revision binding, stale propagation, audit en replay waar mogelijk.
- Nieuwe proof/tests alleen waar 2D nieuwe codepaden, collecties, broncontracten of risico's toevoegt. Volledige regressie blijft de eindcontrole.

## 2. Milestone 2D doel

Breid de bewezen 2C-keten gecontroleerd uit van alleen BGT `pand` naar een **minimale, bruikbare echte GIS-bronbasis voor A02** waarmee latere stedenbouwkundige agents feitelijke locatiecontext kunnen ontvangen.

Deze milestone bouwt nog **geen stedenbouwkundig ontwerp**.

Beoogde zes fasen:

1. **2D-1 — Bronselectie & datacontract**
2. **2D-2 — Multi-collection BGT import**
3. **2D-3 — BAG integratie**
4. **2D-4 — A02 ruimtelijke bronbasis**
5. **2D-5 — Echte Mastenbroekweg end-to-end testcase**
6. **2D-6 — Finale validatie & closure**

Fasegrenzen mogen alleen technisch worden verfijnd als het doel gelijk blijft. Scope-uitbreiding vereist een beslisgate.

## 3. Autonome werkcyclus per fase

Voor **iedere fase**:

1. Lees alleen relevante code, tests en documentatie.
2. Noteer de uitgangspositie en exacte fase-scope.
3. Bepaal het kleinste ontwerp dat de fase-eis invult.
4. Controleer of een beslisgate bestaat.
5. Zo nee: implementeer.
6. Schrijf/werk gerichte tests bij voor nieuw gedrag.
7. Voer targeted tests uit.
8. Voer voldoende regressie uit om het gewijzigde oppervlak te bewaken.
9. Voer `git diff --check` uit.
10. Inspecteer je eigen diff op scope creep, duplicatie en capability-bypass.
11. Maak een faseverslag onder `docs/`.
12. Commit de fase als zelfstandig checkpoint.
13. Alleen bij PASS: ga automatisch door naar de volgende fase.

Een fase is geen PASS omdat code compileert. PASS vereist dat de fase-acceptatiecriteria aantoonbaar zijn vervuld en er geen blocker openstaat.

Bij een reproduceerbare bug binnen de fase-scope: schrijf/reproduceer eerst de failing test, maak de kleinste fix, herhaal verificatie. Dit is geen gebruikersbeslissing tenzij de fix architectuur/scope verandert.

## 4. Wanneer Seth WEL gevraagd moet worden

STOP en rapporteer exact:

`DECISION_REQUIRED: <korte titel>`

De standaard is **zelfstandig beslissen binnen doel en trustgrenzen**. Een keuze is niet automatisch een gebruikersbeslissing alleen omdat er meerdere technisch geldige opties bestaan.

### 4.1 Eerst de additive-choice test

Wanneer twee of meer officiële broncollecties, attributensets of technische opties ieder relevante, complementaire informatie leveren, vraag eerst:

1. kunnen ze veilig naast elkaar bestaan zonder bestaande bronwaarheid te overschrijven?
2. blijven identiteit en provenance afzonderlijk traceerbaar?
3. vallen ze allemaal binnen reeds goedgekeurde bronautoriteit, endpoints, milestone-scope en trustgrenzen?
4. voegt de combinatie geen nieuwe dependency, capability of fundamenteel productgedrag toe?
5. is de extra complexiteit proportioneel en begrensd?

Als alle antwoorden **ja** zijn, kies dan standaard de **combinatie / superset** in plaats van kunstmatig één optie weg te kiezen. Leg de reden vast en ga zelfstandig door.

Voorbeeld: als officiële BAG `pand` gebouwcontext levert en `verblijfsobject` complementair gebruiksdoel/oppervlakte/adres/pandrelaties levert, en beide veilig als afzonderlijke bronobjecten met eigen provenance kunnen bestaan, neem beide op. Maak daar geen `DECISION_REQUIRED` van.

Dit is **geen regel om altijd alles te verzamelen**. Redundante, irrelevante, conflicterende, kostbare, onbetrouwbare of scope-uitbreidende bronnen mogen niet automatisch worden toegevoegd.

### 4.2 Zelfstandig technische keuzes maken

Maak zonder Seth onder andere zelfstandig:
- selectie tussen reeds toegestane officiële collecties als officiële semantiek + milestone-doel de keuze dragen;
- keuze voor meerdere complementaire collecties volgens §4.1;
- interne implementatiedetails en helpernamen;
- teststructuur;
- kleine refactors;
- herstel van duidelijke bugs;
- fail-closed behandeling die bestaand productgedrag niet verruimt.

Documenteer zulke keuzes kort in het faseverslag/statusbestand.

### 4.3 Echte beslisgates

Vraag Seth alleen als minstens één van deze situaties overblijft:

- opties zijn **wederzijds uitsluitend** en veranderen materieel productgedrag of toekomstig architectuurbeleid;
- een nieuwe externe databron, licentie of bronautoriteit buiten de reeds goedgekeurde scope moet worden gekozen;
- bronwaarheid, semantiek, CRS of providercontract kan niet betrouwbaar worden vastgesteld;
- een benodigde wijziging raakt K00, Human Approval, capability ownership of een andere bestaande veiligheidsinvariant;
- de gevraagde fase blijkt alleen haalbaar met duidelijke scope-uitbreiding;
- een nieuwe dependency is echt noodzakelijk;
- live brondata levert een inhoudelijke ambiguïteit op die niet veilig naast elkaar kan blijven bestaan of fail-closed kan worden behandeld;
- bestaande bindende documentatie spreekt elkaar inhoudelijk tegen;
- een destructieve Git-handeling/history rewrite/force push zou nodig zijn;
- tests tonen een probleem waarvan meerdere oplossingsrichtingen materieel productgedrag wijzigen.

Geef dan:
1. het feitelijke probleem;
2. maximaal 3 opties;
3. consequentie per optie;
4. jouw technisch voorkeursvoorstel;
5. de ene concrete beslissing die Seth moet nemen.

Na Seths antwoord: leg de beslissing vast in het relevante faseverslag en hervat automatisch.

## 5. Wanneer je zelf moet stoppen zonder beslissing

Gebruik `BLOCKED:` als uitvoering onmogelijk is door bijvoorbeeld ontbrekende toegang, corrupte repo, niet-reproduceerbare baseline, onbeschikbare vereiste bron of falende tooling.

Probeer eerst redelijke, niet-destructieve diagnose/herstelacties. Verzin geen resultaat en omzeil geen veiligheidsgrens.

## 6. Fase 2D-1 — Bronselectie & datacontract

### Doel
Bepaal vóór productiecode welke minimale bronlagen A02 echt nodig heeft en hoe ze door de bestaande 2C-keten passen.

### Werk
- Inventariseer welke 2C-componenten direct herbruikbaar zijn.
- Onderzoek de actuele PDOK/BGT collection-contracten die voor de minimale ruimtelijke basis relevant zijn.
- Selecteer **niet automatisch alle BGT-collecties**.
- Motiveer per kandidaat: stedenbouwkundige waarde, geometrie, relevante attributen, CRS/provenance, overlap met andere bronnen en noodzaak.
- Maak onderscheid tussen:
  - minimaal noodzakelijk in 2D;
  - nuttig later;
  - expliciet buiten scope.
- Definieer collection-agnostic versus collection-specific delen van adapter/import/replay.
- Definieer het BAG-doel voor 2D-3 zonder BAG al te implementeren.
- Schrijf `docs/milestone-2d-phase1-source-contract.md`.

### Gate
Als bronselectie een inhoudelijke keuze vereist die niet uit officiële bronsemantiek en het milestone-doel volgt: `DECISION_REQUIRED`.

### PASS
Een compact, implementeerbaar datacontract zonder onnodige bronbreedte, geen productiegedrag gewijzigd, relevante bestaande tests nog groen.

## 7. Fase 2D-2 — Multi-collection BGT import

### Doel
Maak de bestaande bewezen BGT-keten veilig bruikbaar voor de in 2D-1 geselecteerde BGT-collecties.

### Eisen
- Geen tweede importarchitectuur.
- Generaliseer alleen waar nodig.
- Per collectie expliciet contract; geen arbitrary collection/URL fetch.
- Bestaande bounded fetch/pagination/next-link security/raw evidence/CRS/geometry/provenance/completeness/trusted promotion/atomicity/idempotence/replay blijven gelden.
- Fail closed voor onbekende of afwijkende collectiecontracten.
- Default networkless tests.
- Live calls alleen wanneer deze fase expliciet een beperkte proof nodig heeft en dat veilig uit het contract volgt; anders bewaren voor 2D-5.
- Schrijf `docs/milestone-2d-phase2.md`.

### PASS
Alle geselecteerde BGT-collecties kunnen via één gecontroleerde architectuur met tests worden verwerkt zonder regressie van `pand`.

## 8. Fase 2D-3 — BAG integratie

### Doel
Voeg alleen de BAG-context toe die noodzakelijk is om A02's ruimtelijke bronbeeld feitelijk bruikbaar te maken.

### Eisen
- Gebruik officiële broncontracten.
- Geen coördinaten of objectrelaties laten raden door een LLM.
- Leg identiteit, provenance en relatie tot BGT expliciet vast.
- BAG mag BGT-geometrie niet stilzwijgend overschrijven.
- Conflicterende officiële bronnen worden als conflict/provenance vastgelegd of fail-closed behandeld; niet synthetisch verzoend.
- Hergebruik 2C/2D trustmechanismen waar passend.
- Geen BRK in deze fase tenzij Seth expliciet besluit de scope te wijzigen.
- Schrijf `docs/milestone-2d-phase3.md`.

### Gate
Als de exacte BAG-inhoud of bronroute een materiële productkeuze vereist: `DECISION_REQUIRED`.

### PASS
De minimaal afgesproken BAG-context is reproduceerbaar, gevalideerd en provenance-safe beschikbaar zonder bestaande bronwaarheid te beschadigen.

## 9. Fase 2D-4 — A02 ruimtelijke bronbasis

### Doel
Maak van de gevalideerde losse bronnen één **leesbaar bronbeeld** voor downstream agents, zonder nieuwe bronwaarheid te fabriceren.

### Eisen
- A02-output verwijst naar gevalideerde bronrecords/revisions.
- Houd feit, afleiding en onzekerheid onderscheidbaar.
- Geen design geometry.
- Geen beleidsconclusies.
- Geen eigendomsconclusies zonder daarvoor gevalideerde bron.
- Geen geometrische waarheid kopiëren naar oncontroleerbare vrije tekst als enige representatie.
- Bronwijziging moet bestaande stale/revision-mechanismen respecteren.
- Maak een compacte machine-readable representatie plus menselijk inspecteerbare samenvatting als dit binnen bestaande architectuur past.
- Schrijf `docs/milestone-2d-phase4.md`.

### PASS
A02 kan aantoonbaar een downstream-consumable bronbasis leveren met traceerbaarheid naar officiële evidence en zonder promotion-/approval-bypass.

## 10. Fase 2D-5 — Echte Mastenbroekweg end-to-end testcase

### Doel
Bewijs op dezelfde testcase dat de bredere 2D-keten met echte bronnen werkt.

Testlocatie:
`Mastenbroekweg 2, 6006 PT Weert, Nederland`.

Gebruik de in 2C vastgelegde testcasecontext waar nog geldig, maar behandel oude feature-counts nooit als permanente verwachting.

### Eisen
- Live proof is expliciet opt-in.
- Alleen vooraf toegestane officiële endpoints/scopes.
- Bewaar exacte raw evidence/hashes/provenance.
- Controleer geselecteerde BGT-lagen en BAG-context.
- Bouw A02-bronbasis.
- Bewijs offline replay/reconstructie waar van toepassing.
- Geen ontwerp door A03/A04/A05.
- Geen Human Approval.
- Rapporteer feitelijke observaties, geen permanente broncounts.
- Schrijf compact machine-readable proofbestand en `docs/milestone-2d-phase5.md`.

### Gate
Als live officiële bronnen elkaar inhoudelijk tegenspreken op een manier die productsemantiek vereist: `DECISION_REQUIRED`.

### PASS
Een gedateerde echte run levert een traceerbare A02-bronbasis en kan zonder nieuwe providerfetch voldoende worden gereproduceerd volgens het afgesproken replaymodel.

## 11. Fase 2D-6 — Finale validatie & closure

### Doel
Sluit 2D formeel af zonder nieuwe functionaliteit.

### Controleer minimaal
- volledige keten voor iedere toegevoegde bron/collectie;
- alle 2C-invarianten;
- collection/endpoint allowlisting;
- raw evidence en hashing;
- CRS en geometry validation;
- provenance;
- completeness;
- trusted A02 promotion;
- atomicity/idempotence;
- revision/stale/audit;
- replay/reconstructie;
- BAG/BGT scheiding en relaties;
- A02-bronbasis traceerbaarheid;
- Human Approval boundary;
- K00 boundary;
- TESTDATA/provider separation;
- normale regressiesuite networkless;
- `git diff --check`.

Maak `docs/MILESTONE_2D_VALIDATION.md` met compacte traceability-matrix.

Eindig exact met:
- `MILESTONE_2D: PASS`, of
- `MILESTONE_2D: FAIL`.

PASS alleen bij groene volledige regressie, intacte invarianten, coherente fasen en geldige live proof binnen de expliciete trustgrenzen.

## 12. Git- en reviewworkflow

- Start vanaf schone, actuele master.
- Geen force push/history rewrite.
- Houd iedere fase als herkenbaar checkpoint.
- Push niet na iedere kleine wijziging.
- Na 2D-6 PASS: maak/push reviewbranch `milestone-2d-final-review`.
- Die reviewbranch bevat de complete Milestone-2D-reeks bovenop de geaccepteerde baseline.
- **Merge de final-reviewbranch niet zelf naar master.**
- Stop na push en rapporteer aan Seth dat onafhankelijke ChatGPT/GitHub-review nodig is.
- Seth hoeft de tussenfasen niet handmatig te reviewen zolang alle gates PASS zijn; de onafhankelijke eindreview controleert de werkelijke GitHub-diff en relevante bestanden.

Als de lokale workflow tussentijds master-checkpoints vereist, houd local master en geschiedenis lineair en veilig. Publiceer de uiteindelijke reviewbranch zonder de eindmerge zelf uit te voeren.

## 13. Voortgangsbestand

Onderhoud `docs/MILESTONE_2D_STATUS.md`.

Minimaal:
- baseline;
- huidige fase;
- status per fase: NOT_STARTED / RUNNING / PASS / BLOCKED / DECISION_REQUIRED;
- fasecommit;
- tests;
- belangrijke besluiten van Seth;
- bekende beperkingen;
- next action.

Update dit bestand bij iedere faseovergang. Het is hervatbare state voor een nieuwe Codex-sessie.

Bij hervatten:
1. lees `AGENTS.md`;
2. lees dit orchestratorbestand;
3. lees `docs/MILESTONE_2D_STATUS.md`;
4. verifieer Git tegen de geregistreerde checkpoint;
5. hervat de eerste niet-PASS fase.
Doe reeds geaccepteerd werk niet opnieuw zonder aanwijzing voor regressie.

## 13A. Token- en contextzuinige uitvoering

Gebruik context en uitvoeringsbudget doelgericht. Autonomie betekent niet dat reeds bewezen werk telkens opnieuw onderzocht of bewezen moet worden.

### Hervatten vanaf checkpoint
- Behandel een in `docs/MILESTONE_2D_STATUS.md` als PASS geregistreerde fase met commit en groene verificatie als geaccepteerd checkpoint.
- Lees bij hervatten primair `AGENTS.md`, dit orchestratorbestand en `docs/MILESTONE_2D_STATUS.md`.
- Lees daarna alleen code/documentatie die nodig is voor de eerstvolgende niet-PASS fase.
- Reconstrueer of herbewijs eerdere PASS-fasen niet zonder concrete regressie-indicatie.
- Gebruik commit `1c4ee6755c49872cd8dfe42b40d49bdc6f7838c4` als geaccepteerd uitvoeringscheckpoint voor 2D-1 t/m 2D-4 indien die commit in de lokale geschiedenis aanwezig is en de status daarmee overeenkomt.

### Teststrategie
- Draai tijdens een fase standaard alleen gerichte tests voor nieuw/geraakt gedrag plus de minimaal noodzakelijke aangrenzende regressie.
- Draai niet automatisch na iedere fase de volledige regressiesuite.
- Een extra volledige regressie vóór 2D-6 is alleen nodig als een wijziging aantoonbaar een brede architectuurgrens raakt of gerichte tests een bredere regressie suggereren.
- De volledige networkless regressiesuite blijft verplicht in 2D-6.
- Herhaal een reeds groene, relevante volledige regressie niet zonder codewijziging die dat oppervlak opnieuw raakt.

### Documentatie en analyse
- Faseverslagen beschrijven primair de delta: nieuw gedrag, nieuwe broncontracten/risico's, verificatie en beperkingen.
- Herhaal geen uitgebreide 2C-architectuurbeschrijvingen als een verwijzing naar bestaande invariant volstaat.
- Vermijd lange tussentijdse chatrapportages. Leg duurzame informatie compact vast in status/faseverslag.
- Onderzoek reeds vastgestelde officiële bronsemantiek niet opnieuw tenzij nieuwe evidence of een contractafwijking dat noodzakelijk maakt.

### Capaciteitsbewaking
- Start geen nieuwe fase wanneer de resterende sessiecapaciteit onvoldoende lijkt om die fase tot een veilig checkpoint te brengen.
- Bij lage capaciteit: rond alleen de lopende stap af, voer minimaal noodzakelijke verificatie uit, werk `MILESTONE_2D_STATUS.md` bij, commit geldige wijzigingen en STOP met `CHECKPOINT_READY`.
- Een capaciteitscheckpoint is geen `BLOCKED` en geen `DECISION_REQUIRED`.
- Een nieuwe Codex-sessie hervat vervolgens volgens §13 vanaf de eerste niet-PASS fase.

## 14. Eindrapport aan Seth

Tijdens autonome uitvoering geen lange voortgangsberichten nodig.

Bij `DECISION_REQUIRED`: alleen het beslispakket uit §4.
Bij `BLOCKED`: blocker, uitgevoerde diagnose, exact benodigde actie.
Bij eind-PASS rapporteer compact:

```text
MILESTONE_2D_EXECUTION: PASS
baseline: <sha>
final_review_branch: milestone-2d-final-review
head: <sha>
phase_commits:
  2D-1: <sha>
  2D-2: <sha>
  2D-3: <sha>
  2D-4: <sha>
  2D-5: <sha>
  2D-6: <sha>
full_regression: <result>
networkless: <result>
diff_check: PASS
live_proof: <reference>
decisions_by_seth: <none/list>
known_limitations: <compact>
next: independent ChatGPT/GitHub review
```

Daarna STOP. Start geen volgende milestone.
