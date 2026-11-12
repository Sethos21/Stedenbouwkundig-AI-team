# Technische nulmeting en integratieplan Stedenbouwkundig AI-team

Datum: 12 november 2026. Opdracht 1. Status: ter onafhankelijke beoordeling; geen functionele ontwerpkeuzes goedgekeurd en geen agent geactiveerd.

## 1. Conclusie en bewijsniveau

De lokale applicatie heeft een bruikbare, geteste kern voor workflow, bronopslag, revisies, onafhankelijke rolreviews en een afzonderlijke menselijke beslisgate. Herbouw is niet nodig. Een geïntegreerde AI-workflow voor echte ontwikkellocaties is echter nog niet beschikbaar. Er bestaan drie gedeeltelijk verbonden sporen:

1. De legacy A01–A02–A07-inventarisatie, standaard deterministisch, met een optionele echte modeladapter voor uitsluitend TESTDATA.
2. De acht-agentontwerplus met uitvoerbare gates en revisies, maar vaste synthetische specialistische voorstellen en fixturegeometrie.
3. De officiële BAG/BGT-bronketen met gevalideerde opslag en A02-context, plus afzonderlijke A06-services voor TESTDATA-classificatie en DSO-bronretrieval.

Bronimport hergebruikt al A02-gates, revisies en invalidatie van DesignWorkflow. De ontbrekende aansluiting is dus geen volledig ontbrekende workflow, maar een gecontroleerde overgang van echte source-evidence naar specialistische context, ontwerpgeometrie en inhoudelijke beoordeling. DSO-retrieval maakt nog geen juridisch toepasbare regels. Dertien milieuthema's in een fixture vormen nog geen milieuonderzoek.

Bewijsniveaus in dit rapport: **code** = aanwezig en geïnspecteerd; **offline test** = uitgevoerd met synthetische responses of expliciet bewaard bronarchief; **historisch livebewijs** = bestaande gedateerde rapportage/capture, geen nieuwe live verificatie. Modelkwaliteit en actuele externe interoperabiliteit zijn in deze opdracht niet getest. Geen fixture wordt als officiële brondata aangemerkt.

## 2. Exacte uitgangspositie

| Onderdeel | Vastgesteld |
|---|---|
| Werkmap | `Y:\seth\Documents\Codex Desktop\AI ontwerpteam` |
| Git-toplevel | `//BERNHEZE-DC01/gebruikers$/seth/Documents/Codex Desktop/AI ontwerpteam` |
| Repository / origin fetch en push | `https://github.com/Sethos21/Stedenbouwkundig-AI-team.git` |
| Beginbranch | `feature/a06-phase2-ow-retrieval` |
| Begin-HEAD | `28b4dd7b60fd5546e8161054ad76d7cd62bf831a` |
| Lokale master en opgeslagen origin/master | `18cc5894c39e5488fb1c40f10d489d7d010b1d12` |
| Opgeslagen origin/feature/a06-phase2-ow-retrieval | `28b4dd7b60fd5546e8161054ad76d7cd62bf831a` |
| Divergentie master...feature | 0 commits alleen op master, 4 alleen op feature |
| Gevolgde lokale wijzigingen / index bij aanvang | Geen |
| Ongevolgde bestaande items | `Stedenbouwkundig-AI-team/`, `phase3b-review.diff` |
| Nieuwe reviewbranch | `review/technische-nulmeting-integratieplan-2026-11-12`, rechtstreeks vanaf begin-HEAD |

Geen fetch, remote API, push of merge uitgevoerd. De origin-refs zijn uitsluitend de lokale laatst opgeslagen stand; actualiteit op GitHub is niet vastgesteld. De geneste ongevolgde map is niet als werkrepository gebruikt; bij de eerste bestandsinventarisatie zijn alleen namen ervan zichtbaar geworden. Beide ongevolgde items zijn niet gewijzigd of gestaged. Genegeerde runtimegegevens zijn niet algemeen geïnventariseerd of als schone baseline aangemerkt. De echte demo is niet geopend via de muterende CLI en niet beoordeeld.

De vier featurecommits zijn `e2e0b81` (DSO-discovery), `2b4ed6a` (begrensde OW-retrieval/probe), `526a523` (veilige diagnostiek) en `28b4dd7` (vaste validatiecodes/contractaudit). De diff omvat 29 bestanden, 29.664 toevoegingen; veel daarvan zijn twee sets contract-JSON. Master bevat al de A02 spatial-context en A06 planological-context-ontwikkeling; DSO-discovery/retrieval en het herstelplan zijn uitsluitend op de featurelijn aanwezig. Een latere implementatie vanaf master kan deze vier commits dus niet als aanwezig veronderstellen. Deze reviewbranch bevat ze als uitgangsbasis, zonder daarmee een mergeadvies of acceptatie te geven.

## 3. Statusmatrix A01–A08

Legacy-profielen staan in `config/agents.json`: A01/A02/A07 actief, A03–A06 inactief, A08 ontbreekt. De afzonderlijke context `ONTWERPLUS_2B` definieert A01–A08 in `domain/design.py`; dat is bestaande, uitsluitend synthetische uitvoering en geen algemene activatie voor echte locaties.

| Agent | Aanwezige implementatie en verantwoordelijkheid | Input → output; afhankelijkheden | Werkelijke uitvoering / AI-status | Ontbreekt voor echte locaties; relevante tests |
|---|---|---|---|---|
| A01 Regisseur | `application/workflow.py`, `design_workflow.py`: toewijzing, volgorde, gates, revisies, findings, beslispakket | Brief of fixture + actuele staprevisies → taken, handoffs, audit, wachtstatus; package na A07 | Uitvoerbare deterministische applicatielogica, geen autonome LLM-regisseur. Bronimport hergebruikt A02-gates | Algemene locatie-initialisatie en integratie van losse contextservices; herstel na procesuitval. `test_runtime`, `test_design_workflow`, `test_milestone_2b1` |
| A02 GIS & Brondata | Legacy inventory; `source_import`, `source_basis`, `spatial_context`, `spatial_summary`; BAG/BGT/adresadapters | Begrensde scope + raw responses → snapshots, geometrieën, bronrecords, A02-revisie, feiten/context/summary; vertrouwde initialisatie vereist | Officiële bronketen daadwerkelijk geïmplementeerd, historisch livebewijs en offline Meppel-archiefcheck. Feitenafleiding deterministisch. Optionele modelinventarisatie uitsluitend TESTDATA | Geen juridische/projectgrens uit bbox; geen BRK/eigendom, volledige werelddekking of automatische relatieaanvulling. `test_source_*`, `test_pdok_*`, `test_bag_*`, `test_spatial_context` |
| A03 Stedenbouwkundige | `agents/design_mock.py`: hypothese en integratie; domein bewaakt variantlineage en berekent capaciteit | A02+A06+A08_GATE → twee vaste varianten; daarna eigen hypothese+A04+A05 → integratierevisie | Werkende TESTDATA-stappen, geen generatief locatieontwerp; OpenAI `design_step` weigert | Algemene ontwerpgeometrie, echte ruimtelijke randvoorwaarden en verantwoorde scenario-aannames. `test_design_workflow`, `test_milestone_2b1`; geometrie/findingcontrole fixturegebonden |
| A04 Landschapsarchitect | Mock landschapsvoorstel, finding en vakreview; eigen resolutie onder bewijscheck | A03-hypothese → landschapsobject; exacte integratie + transitieve inputs → review | Deterministische TESTDATA, geen landschaps-AI of hydrologisch/ecologisch model | Locatiegebonden groen/wateranalyse en algemene verificatie. A04 en A05 onafhankelijk van elkaar vóór integratie. Zelfde workflowtests; `design_verification.py` kent één vaste A04-regel |
| A05 Mobiliteitsontwerper | Mock ontsluiting, finding en vakreview | A03-hypothese → toegangsobject; integratie → review | Deterministische TESTDATA; parkeren/verkeerscapaciteit niet berekend | Netwerk, ontsluiting, parkeren en verkeersmodel/bronkeuze nog te ontwerpen. Zelfde workflowtests; één vaste A05-verificatieregel |
| A06 Planoloog & Beleid | Drie losse vormen: mock voorwaarden; `PlanologicalContextService`; DSO-discovery en OW-retrieval | Mock leest A02-revisie. V1: actuele A02-context + gepinde fixture → bron/regel/toepasselijkheid/interpretatie/classificatie/onzekerheid. DSO: expliciet RD-punt + tijd → kandidaten; expliciete documentkeuze + discovery-pin → letterlijke evidence | V1 deterministisch TESTDATA, geen vrije juridische tekstanalyse. DSO-adapters/services uitvoerbaar en offline getest, geen bewezen succesvolle live keten in deze nulmeting | DOCUMENT_IDENTITY-herstel, schema/profielscheiding, paginering, tijdsbinding, juridische werkingsgebieden en brug van OW-evidence naar toepasselijkheid ontbreken. `test_planological_context`, `test_dso_*`, `test_ow_document` |
| A07 Gemeentelijke Reviewer | Legacy inventory-review en ontwerplusreview met versiegebonden findings | Legacy A02-output → SUFFICIENT/INSUFFICIENT; ontwerp: actuele A04/A05/A08-vakreviews → review op integratie; daarna A01-package | Mock werkelijk uitvoerbaar; optionele modelreview alleen legacy TESTDATA. Rol en reviewversie gescheiden, geen bewijs van inhoudelijke AI-onafhankelijkheid of gemeentelijk oordeel | Reviewcriteria op echte evidence, specialistische inhoud en reviewercontext. Geen broninhoud aanpassen. `test_runtime`, `test_openai_provider`, `test_design_workflow` |
| A08 Milieu & Omgeving | Alleen ontwerplus: A08_GATE en A08_REVIEW, `ENV_THEMES` bevat 13 thema's | A02+A06 → risico/onderzoeksvragen; integratie + transitieve inputs → vakreview | Uitvoerbare deterministische fixture met indicatief geluidrisico, verder RESEARCH_REQUIRED; geen officiële milieuconnector of AI-analyse | Geautoriseerde bronketens, toepasselijkheid, actualiteit, berekeningen en formeel onderzoek ontbreken. `test_design_workflow` controleert themadekking, critical-gate en reviews |

De modeladapter in `agents/openai_provider.py` is echte netwerkimplementatie, niet alleen documentatie. Zijn inventory/review worden met gemockt HTTP getest. Het bestaan van die adapter bewijst geen succesvolle actuele modelcall; deze opdracht deed er geen. Er is geen lokale modelruntime aanwezig in de onderzochte implementatie. Lokaal uitvoerbare software en lokaal uitgevoerde AI zijn verschillende eigenschappen.

## 4. Herbruikbare kern en bestaande grenzen

- **Workflow:** `domain/design.py` legt de bestaande afhankelijkheden vast: A01_START → A02 → A06 → A08_GATE → A03_HYPOTHESIS → A04/A05 → A03_INTEGRATION → A04/A05/A08_REVIEW → A07 → A01_PACKAGE. Dit is een bruikbare basis voor de gewenste volgorde. Maximaal drie automatische integraties; daarna REQUIRES_HUMAN_DECISION.
- **Revisies en transacties:** actuele inputrevisies, transitieve invalidatie, stale reviews, findinghistorie, idempotency en optimistische conflictcontrole bestaan. Providerwerk gebeurt vóór de schrijftransactie; voorstelvalidatie en hercontrole voorkomen commit van stale input. Fouten en geweigerde gates worden geaudit waar de opslag beschikbaar is.
- **Bronketen:** vaste contracten voor BGT pand/wegdeel/ondersteunendwegdeel/waterdeel/begroeidterreindeel/onbegroeidterreindeel en BAG pand/verblijfsobject; raw bytes/hashes, begrensde fetch, CRS/geometrievalidatie, volledigheid, capabilitygebonden promotie, replay en reconstructie. `source_schema.py` bevat versie 1 met afzonderlijke brontabellen en referentiële constraints; oude documenten die alleen tasks/audit noemen zijn historisch.
- **A02-context:** recordrefs, geometriehashes, provenance, letterlijke attributen, gescheiden BAG/BGT-tellingen en expliciete onzekerheden. Technische bbox is geen project-, eigendoms- of juridisch gebied. Som van bronoppervlakken is geen union of unieke gebouwoppervlakte.
- **A06-evidence:** lokale contractpins, oorspronkelijke documentinhoud, hashes, structuurpointers, expliciete selectie, veilige foutcodes en geen arbitrary link-following zijn bruikbaar; juridische duiding is een andere laag.
- **Menselijke gate:** `application/approval.py` blijft de enige beslisroute, vanuit de vertrouwde CLI. Provideractoren zijn geen menselijke identiteit. Reviews en actuele revisies blijven verplicht; risicoacceptatie maakt een bestaand package stale. Geen approval-tool bij een agent.
- **Presentatie:** `DesignPresentation` levert een read-only snapshot en weigert writes. Dit is geen kaartviewer of dashboard. Drive/GIS-protocollen en mocks in `adapters/repositories.py` bewijzen geen werkende Drive/QGIS-integratie.

## 5. A06: DOCUMENT_IDENTITY en herstelstatus

De gebruiker noemt DOCUMENT_IDENTITY als laatst bekende fout. In de gevolgde documenten staat wel de eerdere FAILED_CLOSED/SUPPRESSED-probe, maar geen eenduidige, volledige capture waarmee deze specifieke gemelde fout aan één predicate kan worden gekoppeld. Er is geen live reproductie uitgevoerd en er zijn geen credentials of ongecontroleerde runtime-dumps onderzocht. De precieze oorzaak blijft daarom **niet vastgesteld**.

De foutcode heeft meerdere ontstaansplaatsen:

- `adapters/dso_discovery.py`: dubbele document-/URI-identiteit, negatieve versie, OW expression/URI-mismatch of IMRO-identiteit. Discovery gebruikt slashvervanging; de audit noemt conflicterende officiële beschrijvingen.
- `adapters/ow_document.py`: endpoint-ID-profiel, HAL-documentlink, verschil in identiteit/expressie/versie/type/bevoegd gezag en dubbele componentidentiteit. Presenteren gebruikt slash- én koppeltekenvervanging.
- `application/ow_document.py`: gewijzigde discovery-pin/raw hash/replay, niet-unieke selectie, annotatiebinding, veranderde metadata tussen eerste en laatste fetch, gemengde origins en onopgeloste referenties.

Een universele replace-regel of soepeler accepteren van IDs is dus geen aangetoond herstel. De fout kan ook terecht onveilige bronbinding blokkeren. Tijdsbinding heeft bovendien een eigen code; meerdere afwijkingen kunnen optreden, waarbij de eerste afwijzing de getoonde code bepaalt.

| Maatregel | Stand op begin-HEAD |
|---|---|
| Veilige fase/categorie/HTTP/contractdiagnostiek | Geïmplementeerd in 526a523; oorspronkelijke foutdetails blijven onderdrukt |
| Gesloten `validation_error_code`, behouden over transportgrens | Geïmplementeerd in 28b4dd7; o.a. DOCUMENT_IDENTITY en UNKNOWN |
| Contractaudit, lokaal opgeslagen vergelijking en herstelvoorstel | Aanwezig in `docs/reviews/A06_DSO_*`; audit is geen volledige conformiteitsverklaring |
| Gedragsbehoud t.o.v. 526a523 | Bestaande tests vergelijken 43 scenario's en AST-predicaten; diagnostiek was bewust geen validatiereparatie |
| Officieel schema versus applicatiebewijs scheiden | Nog voorstel; handgeschreven validators blijven gedeeltelijk te streng/onvolledig |
| Endpointgebonden identiteit, collisies en precieze tijdsassen oplossen | Nog voorstel; geen bewezen reparatie van gemelde fout |
| Volledige begrensde paginering | Ontbreekt: discovery accepteert één complete pagina, maximaal 200 documenten; meer pagina's falen gesloten |
| Compatibiliteitsbeleid/pinwijziging | Niet doorgevoerd; bestaande pins behouden |
| Presenteren-interoperabiliteit en geldige lege/optionele bronvormen | Offline beperkte ondersteuning; herstel en live bewijs ontbreken |
| OW-evidence koppelen aan juridische toepasselijkheid/V1-classificatie | Niet geïmplementeerd; V1 eist gestructureerde TESTDATA en is geen echte tekstinterpreter |

Leidend vervolgvoorstel: [bestaand herstelplan](A06_DSO_RECOVERY_PLAN.md), met [contractmatrix](A06_DSO_CONTRACT_AUDIT.md) en [historische validatie](A06_DSO_VALIDATION.md). Eerst ontwerpbeoordeling van bronconflicten en profieleisen; daarna pas wijziging van validatieregels. Geen live DSO-call is door dit rapport toegestaan.

## 6. Technische en functionele tekortkomingen

1. **Geen algemene locatie-workflow.** CLI biedt demo/resume/source-basis/spatial-context, geen geïntegreerd locatieonderzoek met alle contextservices. `DesignWorkflow.create()` laadt één fixture. `SourceImportService` vereist nog een TESTDATA-taakcontext, ook wanneer de bronrecords echte provider-evidence zijn. Die scheiding mag niet door herlabelen verdwijnen.
2. **Twee geometriemodellen.** Echte brongeometrie bestaat in SourceStore; ontwerpvoorstellen verwijzen naar vooraf geregistreerde fixturegeometrie. Findingresolutie kent exact twee synthetische rechthoekregels. Dit is geen algemene geometrische ontwerp- of toetsengine.
3. **Inhoudelijke dekking ontbreekt.** A03–A05 genereren geen echte locatievarianten; A08 heeft geen milieubronnen; A06 levert geen bewezen echte toepasselijkheid. Een ontbrekend onderzoek moet zichtbaar blijven en mag niet als geschiktheid gelden.
4. **Geen geïntegreerde contextlineage voor alle services.** A02-import heeft revisions/stale; losse A06-resultaten hebben hashes en verificatie, maar worden niet vanzelf een actuele specialistische workflowrevisie. Verschillende classificaties (`CONSTRAINT` in V1 versus `HARD_CONSTRAINT` in mock) vereisen een expliciet semantisch contract, geen stille veldmapping.
5. **Review is technisch onafhankelijk, inhoudelijk beperkt.** Versies en rolrechten worden bewaakt; een deterministische PASS_WITH_FINDINGS is geen echte specialistische of gemeentelijke beoordeling. OpenAI inventory/review deelt een providerconfiguratie en levert geen garantie op onafhankelijke oordeelsvorming.
6. **Operationele grenzen.** Eén vertrouwde gebruiker/procescontext; SQLite op netwerkshare vereist beheerst enkelvoudig gebruik. Geen gevalideerde multi-host scheduler; legacy RUNNING-crashrecovery ontbreekt. Audit is inspecteerbaar, niet fraudebestendig; bij opslaguitval kan ook foutaudit mislukken.
7. **Beveiliging voor externe callers ontbreekt.** Procesinterne capabilities zijn geen sandbox. Externe toegang of onbetrouwbare plugins vereisen eerst authenticatie, procesisolatie en OS-rechten. Dit is een latere fase.
8. **Documentatie loopt uiteen.** README/architecture bevatten vroege standaardbibliotheek- en 'geen BAG/BGT'-beschrijvingen, terwijl huidige code Shapely/NumPy en bronadapters bevat. Historische goedgekeurde runtime-status in oude verslagen is geen huidige statuscontrole. `AGENTS.md` is geen algemene toestemming voor alle later aanwezige BAG/DSO-routes. Nieuwe uitvoering vereist afstemming met de actuele opdracht en expliciete bronautorisatie.

## 7. Voorgestelde integratie zonder herbouw

A01 blijft vertrouwde applicatie-orchestratie, met DesignWorkflow als basis. De CLI composeert opslag en bronservices; providers ontvangen uitsluitend gevalideerde datakopieën en revision-bound input, nooit Store, CLI, filesystem, shell of menselijke capability. Bronservices leveren hun bestaande evidencecontracten. Een toekomstige, afzonderlijk te beoordelen aansluiting legt vast welke context bij welke specialistische revisie hoort en verifieert de huidige bronstatus vóór gebruik en commit.

A02 levert feitelijke context; A06 levert afzonderlijke broninhoud, toepasselijkheid en interpretatie; A08 levert onderbouwde risico's en expliciete onderzoeksgaten. A03 maakt scenario's, A04/A05 leveren specialistische bijdragen, A03 integreert. Vakreviews en A07 beoordelen exact die outputversie, zonder deze te herschrijven. A01 stelt daarna het bestaande menselijke beslispakket samen. HumanApprovalService blijft erbuiten en ongewijzigd de verplichte definitieve gate. K00 blijft immutable; alleen afgeleide lagen mogen worden geregistreerd.

Voor een toekomstige ChatGPT-aansluiting is uitsluitend een architectuurgrens voorgesteld: een afzonderlijke, geauthenticeerde procesadapter vóór de bestaande data-only provider-/applicatiegrens. Eerst eventueel expliciet geselecteerde read-only exports met revisie/provenance; later gestructureerde voorstellen met toegestane rol, schema, inputrevisies, omvangsbudget en lokale herverificatie. Brontekst geldt als data, nooit als instructie om tools te activeren. Geen directe database-, shell-, bestands- of approvalroute. Een externe actornaam vormt geen menselijke identiteit; definitieve besluiten blijven in de vertrouwde lokale CLI. Transport, productkeuze, gegevensdeling en authenticatie zijn nog niet gekozen. De aanwezige OpenAI-adapter is geen ChatGPT-koppeling en wordt hiervoor niet stil uitgebreid.

## 8. Implementatiefasen ter beoordeling

Dit is prioritering, geen opdracht tot uitvoering of nieuwe functionele besluitvorming. Per fase blijft onafhankelijke beoordeling van gewijzigde contracten nodig. Testdata en bewaarde officiële evidence worden afzonderlijk gelabeld.

| Prioriteit / fase | Werk en afhankelijkheid | Risico / beslisgate | Acceptatiecriteria |
|---|---|---|---|
| P0 — baseline en contractontwerp | Deze nulmeting beoordelen; actuele componentstatus vastleggen; A06-identiteits-/tijd-/profielontwerp uit bestaand herstelplan concretiseren | Tegenstrijdige identiteitsspecificaties, scope/rolactivatie; geen validatie wijzigen zonder afzonderlijk goedgekeurd ontwerp | Elke contractkeuze heeft lokaal inspecteerbare bronverwijzing, huidige predicate, gewenst gedrag en positieve/negatieve offline gevallen; onopgeloste punten expliciet |
| P1 — A06 betrouwbaar bronbewijs | Na P0: schema versus profiel scheiden, identiteit/tijdsbinding, daarna begrensde paginering en Presenteren-verificatie volgens herstelplan | Onterecht versoepelen; onvolledige sets; versie-/tijdverwisseling | Schema-oracle, collisie-/mismatch-/precisietests, volledige pagina-evidence, vaste budgetten, geen fallback, alle regressies groen; live proof alleen met latere expliciete opdracht |
| P2 — lokale locatiecontext en A01-aansluiting | Hergebruik adres/BAG/BGT-import, A02-context en revisies; definieer algemene taakinitialisatie en contextbinding; echte projectgrens blijft apart | TESTDATA-taak onterecht echt maken; bbox als projectgrens; stale evidence | Eén geïsoleerd offline locatieonderzoek uit bewaard archief; bronherkomst ongewijzigd; gewijzigde A02-context invalideert afhankelijke outputs; herhaalbaarheid/idempotentie; geen onverwachte agentactivatie |
| P3 — A06 toepasselijkheid en A08 onderzoekskader | Op P1/P2: afzonderlijk ontwerp voor juridische bron→regel→toepasselijkheid en milieu-input; bronautorisatie vooraf | Juridische interpretatie of ontbrekende milieuinformatie als feit presenteren | Feit/interpretatie/onzekerheid gescheiden, herleidbare versie/werkingsgebied, onbekend blokkeert onbewezen conclusie; alle 13 thema's verantwoord als evidence of expliciete onderzoeksvraag; geen nieuwe bron zonder besluit |
| P4 — A03/A04/A05 echte scenario's | Op P2/P3: goedgekeurd contract voor afgeleide ontwerpgeometrie, aannames en specialistische voorstellen; providerkeuze apart | Fixtureberekeningen generaliseren zonder bewijs; lokale AI nog niet aanwezig | Twee traceerbare locatievarianten met afgeleide geometrie, expliciete aannames, geen bronmutatie; integratie/review bindt exacte revisies; algemene ruimtelijke controles vooraf ontworpen en getest |
| P5 — onafhankelijke review en lokale eindketen | Op P4: inhoudelijke A07-criteria, gebruikersbediening, herstelpad en evidencepakket samenbrengen | Technische PASS verwarren met toestemming; crash/stale review | Reproduceerbare keten stopt vóór menselijk besluit; stale/critical/iteratielimiet-/rollbacktests groen; geïsoleerde CLI-approvaltests; echte demo ongemoeid |
| P6 — externe aansluiting, later | Pas na lokaal geaccepteerde keten; apart proces/authenticatie en minimaal datacontract voor ChatGPT | Exfiltratie, promptinjectie, capabilitylek, schijnidentiteit | Expliciet goedgekeurde gegevensscope, geauthenticeerde sessies, begrensde voorstellen, audit/replay, geen approval- of arbitrary execution-tool; afzonderlijke securityreview |

## 9. Eerste kleine ontwikkelstap

Voorgesteld voor een **nieuwe opdracht**: uitsluitend een offline A06-identiteitscontract en karakterisatietests voorbereiden, zonder productieregels te veranderen. Beperk dit tot Ontsluiten `identificatie`/`uriIdentificatie`/`expressionId` en Presenteren document-/HAL-binding. Koppel elk geval aan de huidige predicate en gepinde contractspecificatie; leg slash/koppelteken, dubbele identiteit, verkeerde expressie/versie en normalisatiecollisies vast. Als het contractconflict niet met bestaande lokale bronnen oplosbaar is, noteer het als open ontwerpbeslissing; verzin geen normalisatie.

Acceptatie: een reviewbaar ontwerp met verwachte bestaande afwijzingen, expliciete bronconflicten, synthetische fixtures en tests die huidig gedrag karakteriseren; geen live requests, pinwijzigingen, agentactivatie, wijziging aan A02/K00/HumanApprovalService of claim dat de gemelde live fout is gerepareerd. Pas na ontwerpgoedkeuring volgt een afzonderlijke implementatiestap. Deze nulmetingsopdracht voert ook deze kleine stap niet uit.

## 10. Uitgevoerde controles en tests

Git-inspectie: branch, HEAD, toplevel, remote-URLs, lokale refs, status/index, commitvergelijking, bestandsdiff en whitespacecontrole. Geen netwerkverificatie van remote. Lokale lezing: AGENTS.md, README, architecture, Milestone 2B/2B.1, 2C-inventarisatie/closure, 2D-status/orchestrator/closure, Meppel/BAG-bootstrap, A02/A06-contractdocumentatie en alle drie A06-reviewdocumenten. Code-inspectie omvatte agents/provider, mock/AI-adapter, CLI, workflows/approval, source-import/basis/context, bronopslagschema, ontwerpvalidatie/verificatie en DSO/OW-services en validators; tests op relevante grenzen zijn geïnspecteerd en de bestaande suite is gestart.

De standaard Windows-sandbox kon het proces niet starten wegens de combinatie van writable roots/netwerkshare. De lokale commands zijn vervolgens via de beschikbare geëscaleerde uitvoering uitgevoerd; geen globale Git-instelling is aangepast.

Eerste `test.ps1`-run is door de gespreksonderbreking onvolledig gebleven: geen einduitslag, dus geen PASS-claim. Log: `.tools/nulmeting-20261112/regression.txt`. Daarna is de volledige suite opnieuw gestart, zonder codewijzigingen. Nieuwe guard en log staan onder `.tools/nulmeting-20261112-complete/`.

Voor beide runs: bestaande projectlokale Python uit `.tools/source-venv`, bytecode uit via test.ps1, TEMP/TMP en PYTHONPATH binnen het project. De drie bekende API-keyvariabelen zijn in het testproces leeg gezet zonder hun waarden te lezen of publiceren; tests gebruiken waar nodig synthetische keys en gemockt HTTP. `sitecustomize.py` installeert een auditguard die `socket.*` weigert en door Python-CLI-subprocessen wordt geërfd. Dit is verificatietooling, geen productie-isolatie. CLI-approvaltests gebruiken bestaande tijdelijke teststores; er is geen besluit op de echte demo genomen.

| Nieuwe controle | Resultaat |
|---|---|
| Volledige bestaande suite via `test.ps1` | **548 tests, OK, exitcode 0; 217,995 seconden** |
| Failures / errors / skips | 0 / 0 / 0 volgens de unittest-einduitslag |
| Geërfde netwerkguard | 22 proceslogs; geen BLOCKED/socket-events geregistreerd |
| Volledig regressielog (lokaal, ignored) | `.tools/nulmeting-20261112-complete/regression.txt` |
| SHA-256 regressielog | `2db1ba40b65b23bed8b1b6a453612f9341b2f94cdc3a8ff5e5b9a9cb4e5fb152` |
| Gevolgde applicatie-/testbestanden na tests | Geen wijzigingen |
| Whitespacecontrole | `git diff --check` geslaagd; rapport wordt ook staged gecontroleerd |

De volledige suite omvat de gerichte A06-diagnostiek-/contract-/retrievaltests; deze zijn niet daarnaast nogmaals afzonderlijk gedraaid. Er zijn geen nieuwe tests of applicatiefuncties toegevoegd. Het regressielog blijft lokaal; de bovenstaande uitslag en hash zijn het gecommitteerde controleoverzicht, geen meegeleverd volledig logarchief.

Bestaande bewijsvoering is niet als nieuwe live test geteld: 2D rapporteert een historische Mastenbroekweg-run met acht collecties; de huidige suite bevat een offline test van het gecommitteerde Meppel BAG-bootstraparchief met hashcontrole en ongewijzigde databasecheck. A06-contracttests vergelijken met referentiecommit 526a523. Dit toetst respectievelijk bewaarde brondata en gedragsbehoud, niet actuele API-conformiteit of inhoudelijke juridische juistheid.

## 11. Oplevering en stopgrens

Uitsluitend dit rapport wordt aan de reviewbranch toegevoegd. Bestaande code, tests, contractpins, configuratie, lokale ongevolgde items en menselijke besluiten worden niet gewijzigd. Nieuwe tijdelijke testlogs/guardbestanden staan uitsluitend onder ignored `.tools/`; de suite beheert haar bestaande geïsoleerde testopslag. Geen merge, push, cloudwrite, live externe call of nieuwe functionaliteit.

De rapportcommit is niet zelfreferentieel in de tekst opgenomen; de exacte SHA wordt na commit in de oplevermelding vermeld. Reviewdiff: begin-HEAD `28b4dd7b60fd5546e8161054ad76d7cd62bf831a` naar de rapportcommit. Een diff tegen master bevat tevens de vier reeds bestaande A06-featurecommits en moet daarvan worden onderscheiden. Na commit stopt deze opdracht voor onafhankelijke beoordeling door ChatGPT.
