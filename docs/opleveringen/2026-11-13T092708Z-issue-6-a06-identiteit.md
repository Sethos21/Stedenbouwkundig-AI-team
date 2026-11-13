# Oplevering — Issue #6: A06-identiteitskarakterisatie

- Opdracht-ID: `2026-11-13T092708Z-issue-6-a06-identiteit`.
- Bronopdracht: [Issue #6](https://github.com/Sethos21/Stedenbouwkundig-AI-team/issues/6), expliciete gebruikersvrijgave 13 november 2026; startbericht in deze sessie en later verzoek tot voortzetten.
- Run-ID: `issue-6-20261113-start-1`; [bevestigde claim](https://github.com/Sethos21/Stedenbouwkundig-AI-team/issues/6#issuecomment-6848927566).
- Datum checkpoint (UTC): 2026-11-13T10:54:18Z.
- Doel: offline karakterisatie van bestaande DSO-identiteitspredicaten, zonder runtimewijzigingen.
- Opdrachtstatus: **GEBLOKKEERD** conform de expliciete stopvoorwaarde van Issue #6 bij onduidelijkheid over de identiteitsspecificatie. Matrix, tests en bewijs zijn uitgevoerd; het officiële broncontractconflict blijft onopgelost. Dit is geen Human Approval.
- Publicatiestatus: zie het afzonderlijke CODEX_OPLEVERING_V1-ontvangstbewijs; geen voorafgaande GEPUBLICEERD-claim.

## Uitgevoerd en besluiten

De volledige opdracht, actuele masterinstructies, overdrachtsprocedure, A06-contractaudit, herstelplan, validatie en nulmeting zijn gelezen. Remote master `0050e8c0595a969eb5c1a84462964008014c44b2`, A06 `28b4dd7b60fd5546e8161054ad76d7cd62bf831a` en nulmeting `1587c498e8218d04dd77ef2c9a67851fe3256dc1` zijn geverifieerd. PR #5 was gemergd. De volledige open-issuelijst gaf #6 als enige nieuwe kandidaat; #4 was opgeleverd. Er was geen eerdere issue-6-claim, branch of taak-PR. Geen parallelle uitvoerder gestart.

Create-only claim `codex/issue-6` vanaf master slaagde; claimcomment, titel en ref zijn teruggelezen. Eén titelupdate gaf een connectorfout; readback liet zien dat de titel niet was gewijzigd. De gerichte herhaling slaagde vóór inhoudelijk werk. De oorspronkelijke issuebody is bij checkpoints exact ongewijzigd bevonden.

De [inhoudelijke matrix en het hersteladvies](../reviews/A06_IDENTITY_CHARACTERIZATION_ISSUE_6.md) zijn leidend. Daar staan concrete code-/schema-/bronverwijzingen, alle 17 nieuwe testnamen, mogelijke DOCUMENT_IDENTITY-oorzaken en de open contractvragen. Kern: discovery gebruikt slash-only, Presenteren slash+koppelteken; sommige collisies ontstaan pas bij Presenteren. Letterlijke metadata-binding blokkeert de geteste verwisseling. Expression-prefixvalidatie is geen volledige versieparser. De historische live fout is niet gereproduceerd of gerepareerd.

Veilige werkbasis: werkbranch blijft op master; een lokale `git archive` van de exacte A06-commit vormt de testbasis. Alleen nieuwe tests worden in die snapshot toegevoegd. Geen runtime-integratie, cherry-pick, merge of featurebranchwrite. Bestaande fixtures, validators, pins en de standaardbibliotheek/unittest worden hergebruikt; geen externe dependency of nieuwe functionele keuze.

## Gewijzigde bestanden

- `tests/characterization/a06_identity_cases.py`: 17 synthetische TESTDATA-tests voor huidig gedrag.
- `scripts/run_a06_identity.py`: expliciete offline runner met gepinde snapshot, projectlokale opslag, geërfde Python-netwerkguard en voor/na-hashes.
- `docs/reviews/A06_IDENTITY_CHARACTERIZATION_ISSUE_6.md`: veld-/predicatematrix, bronconflicten en NO-GO-advies.
- `docs/evidence/issue-6/results.json`: commando's, uitslagen, test-/runner-/loghashes en ontwikkelfouten.
- `docs/evidence/issue-6/targeted-tests.txt`, `docs/evidence/issue-6/full-tests.txt`, `docs/evidence/issue-6/master-tests.txt`: veilige unittest-uitvoer.
- Dit rapport en `docs/opleveringen/README.md`: overdracht en eigen branchgebonden indexrij.

Bestaande ongevolgde `Stedenbouwkundig-AI-team/` en `phase3b-review.diff` blijven ongemoeid en buiten commits. Geen delta in bestaande runtime, validators, contractpins, bronadapters, agentconfiguratie, K00 of HumanApprovalService. Geen bestaande reviewbroninhoud gewijzigd.

## Tests en verificatiebewijs

De nieuwe tests zijn vóór W uitgevoerd tegen de hieronder expliciet gepinde runtime. [results.json](../evidence/issue-6/results.json) koppelt de testbytes en Git-blobs aan W. `runtime_commit` in dit bewijs is de geteste runtimebasis, niet de latere work-commit. De volledige A06-run gebruikte dezelfde test-AST; daarna zijn alleen lege eindregels verwijderd en zijn alle 17 tests opnieuw gericht uitgevoerd. Tekstgelijkheid na rstrip en AST-gelijkheid zijn gecontroleerd. De runner in Git verschilt van uitgevoerde bytes uitsluitend door gecontroleerde CRLF/LF-normalisatie.

Elk commando hieronder heeft prefix `& .tools/source-venv/Scripts/python.exe -B scripts/run_a06_identity.py`.

| Werkelijk commando / controle | Geteste scope | Resultaat / bewijs | Beperking |
|---|---|---|---|
| `--suite targeted` | A06 `28b4dd7...` + definitieve tests uit W | **17 OK**, exit 0, unittest 0,662 s; [log](../evidence/issue-6/targeted-tests.txt) | Synthetische fixtures en gemockte transports |
| `--suite full` | A06 `28b4dd7...`, 548 bestaande + 17 nieuwe tests | **565 OK**, exit 0, unittest 185,751 s; [log](../evidence/issue-6/full-tests.txt) | Offline `run_tests.py`; nieuwe test heeft alleen latere EOF-opruiming |
| `--suite master` → `pwsh -NoProfile -File test.ps1` | Masterbasis `0050e8c...`, ongewijzigde runtime op werkbranch | **507 OK**, exit 0, unittest 167,957 s; [log](../evidence/issue-6/master-tests.txt) | Master bevat DSO-featurecode niet; karakterisatie wordt via expliciete runner uitgevoerd |
| Snapshotintegriteit | Alle oorspronkelijke bestanden in beide definitieve A06-snapshots | **181/181 byte-identiek** voor/na, geen gewijzigde bestanden | Nieuwe test, tijdelijke opslag en logs apart |
| Python-netwerkguard | Targeted/full/master | 2/23/22 proceslogs; **0 socket-events** | Geen OS-sandbox; vertrouwde testcode, geen kwaadwillende plugins |
| Documentlinks/testnamen/commitvaste bronnen | Inhoudelijk rapport en lokale Git-objecten | Alle 17 testnamen aanwezig; relatieve links en 10 gepinde bronlinks bestaan | Geen externe contractwebsite opnieuw gecontroleerd |
| `git diff --cached --check`, expliciete bestandslijst, runtime-scopevergelijking | Eigen wijzigingen | Geslaagd; oorspronkelijke runtime/config/pins/test-entrypoints ongewijzigd | Geen nieuwe live-conformiteitsclaim |

Ontwikkelruns zijn niet verzwegen: importshadowing in de nieuwe runner, een onjuiste testverwachting over CLI-`details`, gedeelde fixture-linkobjecten en twee BAG-testfouten door een ontbrekende genegeerde tijdelijke hoofdmap zijn gecorrigeerd in uitsluitend nieuwe testondersteuning. De laatste volledige en gerichte runs slagen; exacte geschiedenis staat in results.json. Geen bestaande test of validator is aangepast om een uitslag groen te maken.

Tests gebruiken geïsoleerde tijdelijke CLI-opslag; geen besluit op de echte demo. Runtime/GIS-001 is niet via een muterende opdracht benaderd. Alle tooling/temp/logs staan binnen de projectmap. Live DSO/PDOK, productiecredentials en actuele officiële contractfetches: **NIET UITGEVOERD**, buiten scope. De gepubliceerde logs bevatten testnamen en einduitslagen; absolute lokale paden en stdout-samenvatting van bestaand bronarchief zijn bewust niet gepubliceerd. Lokale raw-loghashes zijn afzonderlijk van gepubliceerde loghashes gelabeld.

## Aandachtspunten, open punten en hervatten

**Blokkade: onopgeloste identiteitsspecificatie.** De bestaande contractaudit beschrijft slash-only, slash+koppelteken en non-word-regels die niet als één bewezen contract kunnen worden behandeld. De tests tonen huidige predicates en botsingen, maar kiezen geen nieuwe semantiek. Issue #6 verlangt in deze situatie fail closed en GEBLOKKEERD. Het advies is **NO-GO voor herstelwijzigingen die nu normalisatie/validatie versoepelen**. De technische testuitvoering zelf is afgerond en betrouwbaar binnen de vermelde offline grenzen.

Veilig vervolg: onafhankelijke review van matrix en bewijs, daarna een afzonderlijk gebruikersbesluit over officiële contractverduidelijking of een nieuwe begrensde bewijsopdracht. Geen stille herstart, gewijzigde pins, live proof, nieuwe agentactivatie of automatische implementatie. De bestaande claim blijft staan; hervatten alleen volgens OPDRACHTENBUS.md. Deze status is geen goedkeuringsverdict.

Tussen tests en evidencepublicatie weigerde de automatische goedkeuringscontrole eenmaal uitvoering wegens een gebruikslimiet; de opdracht was niet uitgevoerd. Na het expliciete gebruikersbericht 'ga door' slaagde dezelfde stap. Remote basis/claim en issuebody zijn daarna opnieuw gecontroleerd. Er zijn geen ongeziene testuitslagen gebruikt.

## Git en publicatie

- Branch: `codex/issue-6`.
- Basiscommit: `0050e8c0595a969eb5c1a84462964008014c44b2`.
- Work-commit W: `000dd27e04aa07705e8fbefcca40640dcaef4023`.
- Report-commit R / bevestigde remote HEAD: in het externe CODEX_OPLEVERING_V1-ontvangstbewijs.
- Draft-PR en commitvaste rapportlink: via [de vaste publicatie-ingang](README.md#vind-de-nieuwste-gepubliceerde-oplevering), met bronissue #6 en bovenstaande run-ID.
- Publicatiebeperking: geen aanvullende inhoudelijke publicatiebeperking; succes van push en readback volgt afzonderlijk in het ontvangstbewijs. De broncontractblokkade staat los van publicatiestatus.
- Na geverifieerde overdracht: teruglink in Issue #6 met busstatus GEBLOKKEERD; issue open laten. Stop voor onafhankelijke ChatGPT-review. Niet mergen.
