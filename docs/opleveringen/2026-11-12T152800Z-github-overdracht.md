# Oplevering — Structurele GitHub-overdracht

- Opdracht-ID: 2026-11-12T152800Z-github-overdracht
- Datum checkpoint: 12 november 2026 (UTC).
- Doel: vaste, controleerbare Codex-overdracht via GitHub zonder terminaluitvoer kopiëren; veilige documentatie-only proef.
- Opdrachtstatus: VOLTOOID voor procesdocumentatie en lokale proefcontroles; publicatie wordt afzonderlijk bevestigd.
- Publicatiestatus: uitsluitend bepaald door het CODEX_OPLEVERING_V1-ontvangstbewijs in [draft-PR #3](https://github.com/Sethos21/Stedenbouwkundig-AI-team/pull/3). Dit bestand claimt vóór die verificatie geen GEPUBLICEERD.

## Uitgevoerd en besluiten

Bestaande AGENTS.md, documentatiestructuur, milestone-/reviewoverdracht, Git-status, historie en GitHub-PR-procedure zijn onderzocht. De inmiddels op remote master aanwezige `docs/ONTWIKKELRICHTLIJNEN.md` is gelezen en behouden. Hergebruik van bestaande Markdown, Git en draft-PRs volstaat; geen dependency, applicatiescript, achtergrondservice of GitHub Action toegevoegd.

De opdracht autoriseert vaste publicatie van eigen toegestane wijzigingen. AGENTS.md verwijst nu naar één procedure en één template. Inhoudelijke verslagen onder docs/reviews/ en milestoneverslagen blijven bestaan; het nieuwe rapport is een compacte overdracht, geen duplicaat of vervanging van runtime-audit.

Een index in één werkbranch kan niet bewijzen wat op alle andere branches het laatst is gepubliceerd. Daarom is docs/opleveringen/README.md branchgebonden en bevat de vaste ingang naar herkenbare PRs. Een nieuw PR-comment na remote-verificatie legt de exacte rapportcommit en commitvaste link vast. Voor globale volgorde geldt GitHubs comment.created_at, met comment-ID als tie-breaker; alle states/pagina's worden meegenomen. Gewone reviewreacties veranderen de publicatievolgorde niet. Dit alternatief voorkomt centrale indexwrites naar master en conflicten tussen parallelle branches.

Een bestand kan niet zijn eigen commit-SHA opnemen. De inhoudelijke work-commit W staat hieronder; report-commit R en de gelijk bevonden remote HEAD staan in het externe PR-ontvangstbewijs. Daarmee stopt de commitlus en kan de onafhankelijke reviewer beide versies precies aanwijzen. Een publicatiebewijs is geen eigen reviewgoedkeuring of Human Approval.

De proef gebruikt de bestaande repository en draft-PR #3. Deze branch is gebaseerd op actuele remote master, niet op de eerdere nulmetingsfeaturelijn. Geen A06-code is toegevoegd, verwijderd of gemergd ten opzichte van deze basis; de andere branches blijven intact.

## Gewijzigde bestanden

| Bestand | Wijziging |
|---|---|
| [AGENTS.md](../../AGENTS.md) | Toegevoegde vaste overdrachtsregels; bestaande regels behouden |
| [README.md](README.md) | Procedure, nieuwste-publicatie-algoritme, branchindex, ontvangstbewijs en onderbrekingsroute |
| [TEMPLATE.md](TEMPLATE.md) | Compact opleverformat met opdrachtstatus, tests/beperkingen, W/R en publicatieverwijzing |
| Dit rapport | Documentatie-only proef en uitgevoerde controles; de index linkt ernaar |

Bestaande ongevolgde `Stedenbouwkundig-AI-team/` en `phase3b-review.diff` zijn niet gestaged, gewijzigd of verwijderd. Lokale master en eerdere feature/reviewbranches zijn niet verplaatst. `origin/master` is alleen via fetch ververst van de eerder opgeslagen 18cc589 naar de actuele 04eae824; dat is geen merge of remote masterwrite.

## Tests en verificatiebewijs

| Werkelijk uitgevoerde controle | Scope / uitkomst | Beperking |
|---|---|---|
| `git status --short --branch`, `git rev-parse HEAD`, `git remote -v` | Begin op review/technische-nulmeting-integratieplan-2026-11-12, HEAD 1587c498e8218d04dd77ef2c9a67851fe3256dc1; geen gevolgde wijzigingen; twee bestaande untracked items | Genegeerde runtimegegevens niet geïnventariseerd |
| `git ls-remote --heads origin master`, daarna `git fetch --no-tags origin master` | Remote master bevestigd op 04eae824115e1f57f49e0a5f11f7e5f0bf6c2ccb; nieuwe branch daarop gebaseerd | Geen mastermerge |
| GitHub repositorymetadata en bestaande PRs gelezen | Private repository, default master; bestaande review- en PR-praktijk bevestigd | GitHub-toegang vereist voor latere ChatGPT-review |
| Eenmalige lokale Python-doccontrole, `python.exe -B -` | Alle relatieve lokale Markdown-bestandslinks bestaan; bestaande AGENTS-bytes behouden met alleen EOL-normalisatie; verplichte publicatie-/onderbrekingsvelden aanwezig | Geen algemene Markdown-renderer of URL-crawler; externe bronlinks niet opgevraagd |
| Eerste versie van dezelfde doccontrole | STOP vóór stage/commit: UnicodeDecodeError bij UTF-8-decoding van bestaande AGENTS-inhoud | Geen productiefout: bestaande encoding behouden, checker aangepast naar bytes; geen stil herstel van broninhoud |
| Herhaalde bytegebaseerde doccontrole | PASS, exitcode 0: bestaande regels behouden, lokale links bestaan, publicatievelden en onderbrekingsroute aanwezig | Bewijst processtructuur, niet toekomstige agentnaleving |
| `git diff --cached --check` vóór work-commit | PASS, exitcode 0; drie procesbestanden, 125 toegevoegde regels | Geen applicatiecode gewijzigd |
| Expliciete branchpush + `git ls-remote --heads origin refs/heads/docs/github-opleverprocedure` | Voorlopige W-push bevestigd op 7920e41f289fd039ffb059b4810ab952de553d30 | W is nog niet de definitieve rapportpublicatie |
| Draft-PR via GitHub aangemaakt en response gelezen | PR #3, draft=true, base=master, head=docs/github-opleverprocedure | Geen eigen review, merge of auto-merge |
| Documentaire scenario-inspectie | Zie onderstaande tabel | Geen echte netwerkstoring, crash of parallelle branchmutaties uitgelokt |
| `test.ps1` | **NIET UITGEVOERD**: uitsluitend procesdocumentatie gewijzigd; lokale document-, scope- en Git-controles uitgevoerd | Geen nieuwe applicatieregressieclaim; eerdere 548-testuitslag van de nulmetingsbranch is niet voor deze branch hergebruikt |

Laatste doc-/scopecontrole, definitieve R-push, remote HEAD en GitHub-readback worden na het vastleggen van dit bestand in het PR-ontvangstbewijs geregistreerd. Dit rapporteert de volgorde eerlijk en vereist geen nieuwe commit om de eigen SHA of post-pushfeiten in te vullen.

### Scenario-inspectie van de procedure

| Geval | Vastgelegd gedrag |
|---|---|
| Succes | Report-commit R pushen, remote HEAD==R, nieuw PR-bewijs en readback; pas dan structurele overdracht GEPUBLICEERD |
| Push mislukt / remote wijkt af | NIET GEPUBLICEERD, oorzaak en vervolgstap; geen force en geen oude SHA als nieuwe overdracht |
| Push goed, PR/comment mislukt | Branch/SHA wel bevestigd; structurele overdracht NIET GEPUBLICEERD; ontbrekende stap veilig hervatten |
| Onderbroken test/opdracht | ONVOLTOOID en onvolledige testuitslag; alleen veilig checkpoint, nooit afgerond noemen |
| Harde crash | Geen belofte van achtergrondpublicatie; bij hervatten toestand reconstrueren en checkpoint publiceren |
| Twee werkbranches | Elk eigen index en ontvangstbewijs; globale nieuwste op GitHub-commenttijd, geen masterwrite |
| Oude PR krijgt nieuwe reviewreactie | PR-updated_at is niet leidend; alleen publicatiecomment telt |
| Nieuwste checkpoint is geblokkeerd | GEBLOKKEERD telt mee bij nieuwste-publicatiebepaling; geen terugval naar een oudere succesvolle oplevering |
| Onvolledige zoekresultaten / geen toegang | Beperking melden; geen claim dat de globale nieuwste gevonden is |
| Correctie / intrekking | Nieuw comment met supersedes; historische bewijzen blijven zichtbaar |

## Aandachtspunten en open punten

- De definitieve GitHub-publicatiecheck staat buiten deze commit in het ontvangstbewijs. Als die ontbreekt, is de structurele proef niet als gepubliceerd bewezen, ook al is dit rapport al op een branch zichtbaar.
- Onafhankelijke ChatGPT-review is nog niet uitgevoerd. Deze procedure verleent geen toestemming om haar eigen PR te mergen.
- AGENTS.md bevatte al niet-uniforme tekstencoding. De bestaande bytes zijn behouden; deze procesopdracht voert geen brede encodingcorrectie uit.
- De index is bewust niet globaal. Het PR-bewijs is de vaste vindroute en is via GitHub controleerbaar, maar is geen cryptografisch onveranderbare audit: vertrouwde GitHub-accountbevoegdheden blijven een aanname.
- Op oudere branches en master geldt de nieuwe werkwijze niet vanzelf voordat deze versie van de instructies beschikbaar is. Tot onafhankelijke review en toegestane integratie moet een vervolgopdracht deze branch/procedure expliciet aanwijzen. Er is geen autonome propagatie of merge uitgevoerd.
- Geen productiecredentials gelezen/gepubliceerd, geen live bron-API gebruikt, geen persoonsgegevens of raw brondata toegevoegd. Bestaande GitHub/Git-authenticatie is alleen voor de geautoriseerde overdracht gebruikt. Runtimegegevens, K00, HumanApprovalService, agentactivatie en functionele ontwerpen zijn ongewijzigd.

## Aanbevolen vervolgstap

Onafhankelijke ChatGPT-review van de diff vanaf basis 04eae824, deze proef en het PR-ontvangstbewijs. Verifieer de commitvaste links, de overeenkomst van report_commit en remote_head_verified, en de vindroute met 'Controleer Codex terminal'. Alleen de gebruiker kan daarna toestemming geven voor integratie naar master. Geen functionele vervolgontwikkeling starten in deze opdracht.

## Git en publicatie

- Branch: `docs/github-opleverprocedure`.
- Basiscommit: `04eae824115e1f57f49e0a5f11f7e5f0bf6c2ccb`.
- Work-commit W: `7920e41f289fd039ffb059b4810ab952de553d30`.
- Report-commit R / bevestigde remote HEAD: zie het nieuwste CODEX_OPLEVERING_V1-ontvangstbewijs voor opdracht-ID `2026-11-12T152800Z-github-overdracht` in [PR #3](https://github.com/Sethos21/Stedenbouwkundig-AI-team/pull/3).
- GitHub-rapportlink: de commitvaste `report_url` met R in datzelfde bewijs.
- [Vaste vindroute en verificatie](README.md#vind-de-nieuwste-gepubliceerde-oplevering).
- Status van onafhankelijke beoordeling: nog te beoordelen, geen eigen goedkeuring.
