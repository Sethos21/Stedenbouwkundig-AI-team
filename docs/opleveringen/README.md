# Codex-opleveringen

Deze index en het [template](TEMPLATE.md) voeren de overdrachtsregels uit [AGENTS.md](../../AGENTS.md) uit. Ze vervangen geen inhoudelijke milestoneverslagen, reviewrapporten of runtime-audit. De onafhankelijke beoordelaar leest bronwijzigingen en testbewijs op GitHub; terminaluitvoer hoeft niet te worden gekopieerd. Toegang tot deze private repository blijft vereist.

## Vind de nieuwste gepubliceerde oplevering

Vaste ingang: [alle Codex-opleverings-PRs, ook gesloten en gemergde](https://github.com/Sethos21/Stedenbouwkundig-AI-team/pulls?q=is%3Apr%20%22%5BCodex-oplevering%5D%22%20in%3Atitle%20sort%3Aupdated-desc). Deze ingang werkt ook vóórdat deze instructies naar master zijn gemergd. PR-sortering is alleen een zoekhulp: een reviewreactie kan een oude PR naar boven verplaatsen.

Bij **'Controleer Codex terminal'**:

1. Zoek in `Sethos21/Stedenbouwkundig-AI-team` alle PRs (alle states, alle pagina's) met titelprefix `[Codex-oplevering]`. Lees hun top-level Conversation-comments; alleen de exacte marker `CODEX_OPLEVERING_V1` telt als overdrachtsbewijs. Een draft of open PR zonder zo'n bewijs is nog geen structurele oplevering.
2. Controleer de markervelden, de commit op GitHub, het rapport op die SHA en de aangegeven work-commit. Een publicatiebewijs met ontbrekende/niet-bereikbare commit of rapport is ongeldig. Branch en report-SHA moeten overeenkomen met het vastgelegde verificatiebewijs. Controleer de actuele remote branch nogmaals als die bestaat. Als HEAD inmiddels verder is gegaan, beoordeel de gepinde publicatie als historische snapshot en meld het verschil; behandel ongepubliceerde nieuwe commits niet automatisch als oplevering.
3. Bepaal de nieuwste geldige publicatie op **GitHubs `created_at` van het publicatiecomment**, niet op commitdatum, bestandsnaam, PR-nummer, PR-updated_at of lokale klok. Bij gelijke serverseconde: hoogste numerieke comment-ID. Lees alle relevante comments over alle resultaten; zoekresultaten kunnen vertraagd zijn. Gebruik zo nodig de volledige PR-lijst. Meld onvolledige toegang/paginering als beperking en claim dan niet dat de wereldwijd nieuwste oplevering vaststaat.
4. Neem ook ONVOLTOOID en GEBLOKKEERD mee: het nieuwste gepubliceerde checkpoint kan onvoltooid zijn. Controleer opdrachtstatus apart van publicatiestatus. Lees rapport, diff en tests, beoordeel onafhankelijk en adviseer een vervolgstap. Geef nooit Human Approval namens de gebruiker.
5. Een latere correctie is een nieuw comment met verwijzing naar het vervangen comment. Gebruik de oude ontvangstbewijzen niet als actuele stand; verwijder of wijzig ze niet. Bij ingetrokken bewijs blijft de intrekking zichtbaar. Een gesloten/ongemergde PR blijft een publicatie, geen geaccepteerde implementatie.

Dit vraagt geen centrale indexwrite op master. Iedere werkbranch houdt alleen zijn eigen index bij; oudere indexen kunnen dus geen globale actualiteit claimen. Parallelle branches publiceren eigen rapporten en PR-comments zonder elkaar te overschrijven. Bij een later expliciet toegestane merge blijven alle rapporten behouden en worden indexrijen gecombineerd; dat is geen automatisch onderdeel van opleveren.

## Branchgebonden index

Nieuwste rapport op **deze branch**: [Issue #4 — GitHub-opdrachtenbus](2026-11-12T160800Z-issue-4-opdrachtenbus.md). Publicatiebevestiging staat in het PR-ontvangstbewijs; deze rij is geen globale nieuwste-publicatieclaim.

| Datum checkpoint (UTC) | Opdracht / rapport | Opdrachtstatus | Branch | PR / publicatiebewijs |
|---|---|---|---|---|
| 2026-11-12 | [Issue #4: opdrachtenbus](2026-11-12T160800Z-issue-4-opdrachtenbus.md) | VOLTOOID; publicatie afzonderlijk verifiëren | `codex/issue-4` | [Draft #5](https://github.com/Sethos21/Stedenbouwkundig-AI-team/pull/5), CODEX_OPLEVERING_V1-comment |
| 2026-11-12 | [GitHub-overdracht en documentatieproef](2026-11-12T152800Z-github-overdracht.md) | VOLTOOID; publicatie afzonderlijk verifiëren | `docs/github-opleverprocedure` | [Draft #3](https://github.com/Sethos21/Stedenbouwkundig-AI-team/pull/3), CODEX_OPLEVERING_V1-comment |

## Rapportnaam en inhoud

Gebruik `docs/opleveringen/YYYY-MM-DDTHHMMSSZ-korte-opdracht.md` (UTC, geen dubbelepunt, unieke opdrachtslug). Controleer dat het bestand nog niet bestaat; bij een parallelle naamcollision kies een unieke suffix, nooit overschrijven. Gebruik [TEMPLATE.md](TEMPLATE.md). Per opdracht één rapport; checkpoints van diezelfde opdracht mogen hetzelfde pad op nieuwe commits gebruiken. Iedere publicatie krijgt een nieuw, commitvast ontvangstbewijs, zodat oude snapshots inspecteerbaar blijven.

Link naar bestaand inhoudelijk bewijs in docs/reviews/ of milestoneverslagen. Kopieer niet alle terminaluitvoer. Noem echte commando's, resultaat, tijd/exitcode waar beschikbaar, broncommit en beperkingen. Bij niet-uitgevoerde tests: expliciet NIET UITGEVOERD en waarom. Bij afgebroken tests: ONVOLLEDIG, nooit PASS. Geef relevante gecontroleerde logregels of veilige bewijsbestanden mee wanneer nodig; een hash van alleen lokaal bewijs maakt dat bewijs nog niet controleerbaar via GitHub. Publiceer geen secrets, persoonsgegevens, gevoelige raw captures of runtime-databases. Als bewijs niet gedeeld kan worden, zeg welk oordeel daardoor beperkt blijft.

## Commit- en publicatieprocedure

1. Lees AGENTS.md en de huidige opdracht; inspecteer branch/HEAD/status, remote en lokale wijzigingen. Kies een toegestane werkbranch en leg de basis vast. Geen automatische stash, reset, clean, merge of wijziging aan andermans bestanden. Start niet vanaf een verouderde aanname over master.
2. Voer alleen geautoriseerd werk uit. Test naar impact en projectregels; `test.ps1` bij relevante applicatie-/testwijzigingen, CLI-approvaltests uitsluitend geïsoleerd. Alleen documentatie: controleer inhoud, links, diff en bevoegdheidsgrenzen; leg gemotiveerd vast dat de applicatiesuite niet is uitgevoerd. Dit is geen toestemming om verplichte tests voor codewijzigingen over te slaan.
3. Maak de **work-commit W** met toegestane inhoudelijke wijzigingen en relevante bewijsstukken. Bij uitsluitend onderzoek kan W een bestaand inhoudelijk onderzoeksrapport bevatten; bij een veilig statuscheckpoint zonder commitbare werkzaamheden mag W de bestaande onderzochte HEAD zijn. Registreer altijd W exact en verduidelijk wat is getest. Inspecteer de staged bestandslijst, niet `git add .`.
4. Maak het compacte opleverrapport met branch, basis, W en werkelijke status; werk alleen de eigen indexrij bij. Maak de **report-commit R**. De report-commit bevat uitsluitend overdrachtsdocumentatie/bewijs; inhoudelijke wijzigingen na de test vereisen herbeoordeling en zo nodig nieuwe tests. Een bestand kan zijn eigen commit-SHA niet bevatten: W staat in het rapport, de exacte R en publicatiebevestiging komen in het PR-ontvangstbewijs. Geen zelfreferentiële amend-/commitlus.
5. Push expliciet één branch, bijvoorbeeld `git -c push.followTags=false push origin refs/heads/<branch>:refs/heads/<branch>`. Geen force, `--all`, `--mirror`, tagpush of beschermde-branchwrite. Controleer met `git ls-remote --heads origin refs/heads/<branch>` dat remote HEAD exact R is. Bij conflict/afwijking stoppen en onderzoeken, niet forceren.
6. Maak/hergebruik een draft-PR met titelprefix `[Codex-oplevering]`, juiste basis en reviewscope. Een voorlopige documentatiepush om de draft-PR te openen is toegestaan, maar is nog geen afgeronde overdracht. Geen reviewers automatisch benaderen, eigen werk goedkeuren of auto-merge activeren. Voeg na de definitieve push een nieuw Conversation-comment volgens onderstaand formaat toe.
7. Lees het comment en rapport via GitHub terug; controleer marker, R, W, link en opdrachtstatus. Noteer de GitHub-servertijd/comment-ID uit de response. Geef gebruiker rapportlink, PR/commentlink, remote SHA en GEPUBLICEERD terug; stop voor onafhankelijke review. Als push slaagt maar PR/commentpublicatie niet: meld 'branch gepusht; structurele overdracht NIET GEPUBLICEERD' en de bevestigde SHA, zonder vindbaarheid te claimen. Probeer na herstel alleen de ontbrekende stap; zoek eerst of een timeout tóch een comment heeft gemaakt.

Bij publicatie staat in het rapport dat de publicatiestatus uit het PR-ontvangstbewijs komt. Dat is bewust geen vooraf ingevulde GEPUBLICEERD-claim. W (getest werk) en R (gepubliceerde report-HEAD) zijn verschillende identiteiten. De acceptatiecontrole vergelijkt **R** met de remote HEAD, niet W. De commitvaste rapportlink gebruikt R, nooit alleen een beweegbare branchnaam.

## Vast PR-ontvangstbewijs

Plaats dit uitsluitend na bevestigde push/remote-check. Het is een publicatiebericht, geen reviewverdict of menselijk besluit.

```text
CODEX_OPLEVERING_V1
opdracht_id: <zelfde ID als rapport>
opdracht_status: VOLTOOID | ONVOLTOOID | GEBLOKKEERD
publicatiestatus: GEPUBLICEERD
branch: <werkbranch>
work_commit: <40 hex W>
report_commit: <40 hex R>
remote_head_verified: <exact dezelfde 40 hex R>
remote_verification: git ls-remote --heads origin refs/heads/<werkbranch>
report_path: docs/opleveringen/<naam>.md
report_url: https://github.com/Sethos21/Stedenbouwkundig-AI-team/blob/<R>/docs/opleveringen/<naam>.md
pr_url: <PR-url>
supersedes: <eerder comment-url of GEEN>
```

GitHub levert de publicatietijd via comment.created_at; het bericht zelf hoeft geen betrouwbare lokale publicatietijd te verzinnen. Bij foutieve publicatie: nieuw correctie-/intrekkingscomment met `supersedes`, uitleg en expliciet welke velden/claims vervallen. Een intrekking gebruikt `publicatiestatus: INGETROKKEN` en telt niet als nieuwe geldige oplevering; toon wel dat het ingetrokken rapport niet meer leidend is.

## Onderbroken of geblokkeerde opdracht

Publiceer een veilig statusrapport met ONVOLTOOID zodra veilig stoppen mogelijk is; kies GEBLOKKEERD bij een concrete noodzakelijke blokkade. Beschrijf precies uitgevoerd/niet uitgevoerd werk, resterende wijzigingen, testdekking en hervatpunt. Neem onveilige of ongeautoriseerde deelwijzigingen niet mee. Een aparte statusbranch vanaf een vertrouwde commit is mogelijk als dat bestaande lokale wijzigingen niet raakt; forceer geen branchwissel. Als ook statuspublicatie niet veilig kan, meld NIET GEPUBLICEERD en geef de lokale locatie/blokkade. Bij onverwachte procesuitval kan geen agent nog een rapport publiceren: bij hervatten eerst de werkelijke toestand reconstrueren en dan een checkpoint publiceren. Dit protocol is een vaste agentwerkwijze, geen achtergrondservice die na een crash blijft draaien.

## Invoering en grenzen

Deze procedure wordt door toekomstige agents gevolgd zodra zij deze versie van AGENTS.md lezen. Oude branches krijgen wijzigingen niet automatisch; vóór onafhankelijke acceptatie/merge staat de procedure alleen op deze werkbranch. Voor werk op een oudere branch moet de opdracht de procedure expliciet aanwijzen of moet zij via een afzonderlijk toegestane integratie beschikbaar komen. Er wordt niet eigenmachtig naar master gemergd om dit te forceren.

Alleen GitHub-overdracht is hier toegestaan. Bestaande bron-/netwerkautorisaties, K00, HumanApprovalService, agentactivatie, datarechten en onafhankelijke beoordeling blijven gelden. GitHub-publicatie is geen vrijgave voor productie of formele projectgoedkeuring.
