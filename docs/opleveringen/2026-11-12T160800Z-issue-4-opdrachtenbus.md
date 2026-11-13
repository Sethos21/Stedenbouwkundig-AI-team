# Oplevering — Issue #4: GitHub-opdrachtenbus

- Opdracht-ID: `2026-11-12T160800Z-issue-4-opdrachtenbus`.
- Bronopdracht: [Issue #4](https://github.com/Sethos21/Stedenbouwkundig-AI-team/issues/4), expliciet vrijgegeven door de gebruiker in deze sessie en in het issue.
- Run-ID: `issue-4-20261112-start-1`; [claimcomment](https://github.com/Sethos21/Stedenbouwkundig-AI-team/issues/4#issuecomment-6828782081).
- Doel: één vaste startinstructie voor het gecontroleerd ophalen, claimen en opleveren van GitHub-opdrachten; uitsluitend procesdocumentatie.
- Opdrachtstatus: **VOLTOOID** voor implementatie en lokale controles. Publicatie en teruglink worden na deze commit afzonderlijk bevestigd.
- Publicatiestatus: zie CODEX_OPLEVERING_V1 in [draft-PR #5](https://github.com/Sethos21/Stedenbouwkundig-AI-team/pull/5); geen voorafgaande GEPUBLICEERD-claim in dit bestand.

## Uitgevoerd en besluiten

De volledige Issue #4-opdracht en actuele AGENTS.md op master zijn gelezen, inclusief bestaande overdrachtsprocedure en ontwikkelrichtlijnen. Lokale status, masterhistorie, remote refs, beschikbare issues/PRs en `.github` zijn onderzocht. De eerdere overdrachts-PR #3 was inmiddels gemergd door een andere actor; actuele basis is `41fbea461f75745e3ffe52d37f4c6f185c8bd29a`. Codex heeft in deze opdracht niet gemergd.

Er was één issuekandidaat (#4), zonder comments/eerdere claim, geen `codex/issue-*`-remote branch en geen bestaande taak-PR. De goedgekeurde issuebody is tijdens uitvoering opnieuw opgehaald en exact gelijk bevonden. De oorspronkelijke branch `docs/github-opleverprocedure` op `00214914a658697b8cf6bcac170746f3f4d86a3e` bleef intact. Geen gevolgde lokale wijzigingen bij aanvang; de bestaande ongevolgde `Stedenbouwkundig-AI-team/` en `phase3b-review.diff` blijven ongemoeid.

Keuze binnen de opdracht: expliciete issuetitelmarkers, aansluitend op de bestaande `[KLAAR_VOOR_CODEX]`-titel. De issue-response meldde geen labels (`null`); de connector kan de volledige repository-labelcatalogus niet via de beschikbare fetchroute opvragen. Daarom geen claim dat alle repositorylabels ontbreken en geen nieuw labelbeleid of labelmutaties. De basis bevatte geen gevolgde `.github`-bestanden/workflows.

Dubbelstartbeveiliging hergebruikt de noodzakelijke werkbranch: GitHub create-only `codex/issue-4` vanaf actuele master slaagde. Een tweede create naar dezelfde naam werd veilig geweigerd. De startclaim is in het issue vastgelegd; alleen de titelprefix is gewijzigd naar IN_UITVOERING. Body/vrijgave/scope bleven gelijk. Geen extra lockbranch, helper, dependency, scheduler, runner of workflow nodig.

De [procedure](../OPDRACHTENBUS.md) definieert de trigger 'Nieuwe opdracht staat klaar', volledige selectiecontrole, precies één geldige kandidaat, create-only claim, expliciet hervatten, statusovergangen en issue-teruglink. Rapportstatus en publicatiestatus blijven gescheiden van de busstatus. Labels/comments zijn geen lock. Er wordt geen algemene multi-worker- of multi-issue-lockgarantie geclaimd; één actieve vertrouwde uitvoerende sessie per repository is een harde gebruiksvoorwaarde, bij onzekerheid stoppen.

## Gewijzigde bestanden

| Bestand | Doel |
|---|---|
| [AGENTS.md](../../AGENTS.md) | Starttrigger, busstatus, claim-/exclusiviteitsgrens en terugkoppeling toevoegen; bestaande regels behouden |
| [OPDRACHTENBUS.md](../OPDRACHTENBUS.md) | Eén compacte procedure met vaste startinstructie, selectie, statusmodel, claim/idempotentie en hervatten |
| [TEMPLATE.md](TEMPLATE.md) | Eén regel voor bronissue, run-ID en claimcomment in bestaand opleverformat |
| [README.md](README.md) | Alleen nieuwe branchgebonden indexrij en nieuwste rapportlink |
| Dit rapport | Uitgevoerd werk, controles, beperkingen en overdracht voor Issue #4 |

## Tests en verificatiebewijs

| Werkelijk uitgevoerde controle | Resultaat | Beperking |
|---|---|---|
| GitHub issue-fetch #4 en master AGENTS-fetch | Volledige scope en expliciete vrijgave beschikbaar zonder terminaltekst van gebruiker | Geen autonome vrijgave door Codex |
| `git status --short --branch`, `git rev-parse HEAD`, remote-inspectie | Geen gevolgde lokale wijzigingen; twee bestaande untracked items | Genegeerde runtimegegevens niet geïnventariseerd |
| `git fetch --no-tags origin master`, `git ls-remote --heads origin master` | Basis `41fbea461f75745e3ffe52d37f4c6f185c8bd29a` bevestigd | Geen lokale/remote masterwrite |
| Issue-/PR-/commentinspectie en `git ls-remote --heads origin 'refs/heads/codex/issue-*'` | Voor claim geen eerdere uitvoering van #4 gevonden | Geen bewijs voor afwezigheid van buiten-protocol werkers |
| GitHub create-branch `codex/issue-4` op basis-SHA | Succes; werkbranch gereserveerd | Alleen nieuwe vaste ref; niet een algemene distributed lock |
| Dezelfde create nogmaals, vóór inhoudelijke wijzigingen | **Verwachte weigering: HTTP 422, Reference already exists**; daaropvolgende `ls-remote` bevestigde dezelfde basis-SHA | Veilige sequentiële dubbelstartproef; geen echte parallelle clients gestart |
| Claimcomment/issue-readback | Claim #6828782081 aanwezig; titel IN_UITVOERING; issuebody later exact onveranderd | Titel/body-vrijgave hebben bewust actuele versus historische betekenis |
| Eenmalige lokale Python-doccontrole via projectlokale `python.exe -B -` | PASS/exit 0: oorspronkelijke AGENTS-bytes behouden met EOL-normalisatie; relatieve links bestaan; selectie/status/claim/hervat/publicatievelden aanwezig | Geen runtimeparser of automatische bushelper toegevoegd |
| `git diff --cached --check` voor W | PASS/exit 0; 3 procesbestanden, 84 toevoegingen | Alleen documentatie |
| Scopecontrole `git diff <basis> --name-only -- src tests scripts config .github` | Leeg; geen applicatie-, test-, bron-, configuratie- of workflowwijzigingen | Geen functionele regressieclaim |
| W-push en remoteverificatie | `0801d76721cd15c3084677a20ce5dd60058086d4` bevestigd | Definitieve report-HEAD R komt in ontvangstbewijs |
| `test.ps1` | **NIET UITGEVOERD** volgens bestaande documentatie-only procedure | Geen applicatiecode/testwijziging; oude suiteuitslagen niet hergebruikt |

De eindcontrole van rapport/index, R-push, exacte remote HEAD, draft-PR-/rapportreadback en issue-teruglink wordt vastgelegd in het PR-ontvangstbewijs en de issue-statusreactie. Die feiten ontstaan na deze report-commit en worden niet vooraf als uitgevoerd aangemerkt.

### Handmatige scenarioanalyse van de instructies

| Invoer/toestand | Vereiste uitkomst volgens vastgelegde procedure |
|---|---|
| Eén open, vrijgegeven, niet-opgepakt issue | Na preflight en bevestigde create-only claim uitvoeren |
| Nul kandidaten / meerdere kandidaten | Stop; geen stille nieuwste-selectie of fallback |
| Ready-marker zonder herleidbare vrijgave / gewijzigde scope | Stop; geen bevoegdheden uit marker afleiden |
| Onbesliste afhankelijkheid / onvolledige zoekresultaten | Stop met ontbrekende informatie |
| Bestaande claim/branch/PR, ook gesloten of branch later verwijderd | Geen nieuwe start; historie blijft bepalend |
| Claimtimeout / onbekende write-uitkomst | Stop; dezelfde SHA is geen eigendomsbewijs |
| Andere actieve uitvoerder / exclusiviteit onbekend | Stop; geen parallelle uitvoering starten |
| Geblokkeerd of gecrasht werk | Alleen expliciet hervatten nadat vorige sessie gestopt is; bestaande claim en revisies controleren |
| VOLTOOID maar push/overdracht mislukt | Geen OPGELEVERD; blokkade plus NIET GEPUBLICEERD volgens overdrachtsprocedure |
| Gepubliceerd ONVOLTOOID-checkpoint | Issue blijft GEBLOKKEERD; publicatie is geen voltooiing |

Dit is documentair getoetst, behalve de hierboven werkelijk uitgevoerde succesvolle claim en dubbelstartweigering. Geen foutinjectie voor netwerkuitval, crash, meerdere issueselecties of echte concurrency uitgevoerd.

## Aandachtspunten, open punten en hervatten

Geen inhoudelijke blocker voor deze documentatieopdracht. Onafhankelijke beoordeling staat open. Definitieve publicatie/teruglink moet uit het externe ontvangstbewijs blijken. Het issue blijft open; OPGELEVERD betekent uitsluitend overgedragen voor review, geen functionele goedkeuring of merge.

Claimref, GitHub-rechten en comments veronderstellen vertrouwde deelnemers. De vaste ref verhindert dubbele create voor hetzelfde issue; zij vergrendelt niet alle schrijfacties of verschillende issues over meerdere niet-meewerkende clients. Nieuwe parallelle agents zouden een afzonderlijk ontwerp vereisen. Bij onzekere claim/herstart wordt geen lock gestolen of verlopen verklaard. Er is geen achtergrondproces dat tijdens een crash alsnog oplevert.

Geen A06-ontwikkeling, live bron-API, productieactie, secrets, brondata, HumanApprovalService-/K00-wijziging, auto-merge of eigen goedkeuring. De labelcatalogusbeperking is expliciet hierboven vastgelegd. Oude lokale encoding is niet opgeschoond. Bestaande branches/ongevolgde bestanden zijn behouden. Deze nieuwe instructies staan tot toegestane merge alleen op de werkbranch.

## Aanbevolen vervolgstap

ChatGPT beoordeelt Issue #4, de diff, de selectie-/claimgrenzen en het geverifieerde publicatiebewijs in [draft-PR #5](https://github.com/Sethos21/Stedenbouwkundig-AI-team/pull/5). Alleen na gebruikersbesluit kan integratie volgen. Geen volgende opdracht of A06-ontwikkeling starten.

## Git en publicatie

- Branch: `codex/issue-4`.
- Basis: `41fbea461f75745e3ffe52d37f4c6f185c8bd29a`.
- Work-commit W: `0801d76721cd15c3084677a20ce5dd60058086d4`.
- Report-commit R en bevestigde remote HEAD: exact in CODEX_OPLEVERING_V1 van [PR #5](https://github.com/Sethos21/Stedenbouwkundig-AI-team/pull/5).
- Commitvaste rapportlink: `report_url` in dat bewijs.
- Bronissue en terugkoppeling: [Issue #4](https://github.com/Sethos21/Stedenbouwkundig-AI-team/issues/4).
- [Vindprocedure](README.md#vind-de-nieuwste-gepubliceerde-oplevering); nieuwe issue-status wordt pas na geslaagde overdracht gezet en teruggelezen.
