# Zelfstandige Codex-automatisering — technisch ontwerp v0.1

Status: **documentatieproef geïmplementeerd, niet geactiveerd of live getest**. Bronopdracht: [Issue #13](https://github.com/Sethos21/Stedenbouwkundig-AI-team/issues/13). Startbasis: `master@11bbdbdb96f9c048305c51ff999216dd6dbca152`.

## Scheiding en autorisatie

- Eigen GitHub Actions workflow(s) met `codex-` prefix; geen hergebruik of mutatie van Claude-workflows, -secrets, -triggers of -agents.
- Een afzonderlijk Codex-secret (`CODEX_ACTIONS_API_KEY`) en minimale `GITHUB_TOKEN`-rechten; geen tokens of brongegevens in logs.
- De huidige handmatige opdrachtenbus blijft geldig. De nieuwe automatische route krijgt een expliciet, afzonderlijk protocol en mag nooit dezelfde opdracht parallel uitvoeren.
- Start alleen op verifieerbare gebruikersvrijgave voor concrete scope. Issue-inhoud, labels en agentcomments zijn geen zelfstandige machtiging.
- Per repository maximaal één actieve Codex-uitvoerder, met claim op een vaste branch en fail-closed controles. `concurrency` alleen is onvoldoende als exclusieve lock over meerdere workflows.

## Uitvoering en kwaliteitsgrenzen

1. Preflight: check actuele master, vrijgave, bestaande claim/PR, afhankelijkheden, toegestane paden, beschikbaar secret en exclusieve uitvoeringsrechten.
2. Codex verwerkt uitsluitend een vastgepinde opdracht op een eigen branch, met minimaal benodigde tools, netwerkrechten en tokenlimieten.
3. Rapportage en tests worden herleidbaar aan run, issue, commits en PR gekoppeld; mislukking blokkeert oplevering.
4. Review vindt gescheiden van de uitvoerende agent plaats. Een agent mag eigen werk niet als onafhankelijke goedkeuring markeren.
5. Automatische merge is **opt-in per laagrisicocategorie** en vereist verplichte checks, scope-/padcontrole, actuele base en afgedwongen branchregels. Gevoelige wijzigingen (workflows, security, K00, HumanApprovalService, `AGENTS.md`) nooit automatisch mergen.
6. Geen admin-bypass of zelftoekenning van extra rechten. De eerste infrastructuurwijziging wordt niet door zichzelf geactiveerd of gemergd.

## Te verifiëren vóór activering

- Beschikbaarheid GitHub Actions, repositoryinstellingen, tokenpermissions, verplichte statuschecks en branchbescherming.
- Werkende en beveiligde Codex API-authenticatie, versie/pinning en kostenlimiet.
- End-to-end documentatieproef met aantoonbaar geïsoleerde uitvoering.
- Negatieve tests: ongeldige vrijgave, duplicate/race, ontbrekend secret, conflicten, tests-fail, scope-/padoverschrijding, mislukte review, mislukte statuswrite.
- Geen wijzigingen aan Claude of lopende MVP-01a-opdracht.

## Implementatie en configuratie

Draft-PR #14 bevat de uitvoerbare workflow `.github/workflows/codex-independent.yml`
en de controller `scripts/codex-actions/route.py`. De documentatieproef schrijft
één modelresultaat en één afzonderlijk vertrouwd opleverrapport via twee
expliciet toegestane paden. De controller verifieert branch, rapport en PR
voordat hij het overdrachtsbewijs schrijft.

De eigenaar meldt twee environments voor `master`, een afzonderlijk
environment-secret en repositoryvariabele `CODEX_ACTIONS_ENABLED=false`.
De [installatiehandleiding](CODEX_ACTIONS_INSTALLATIE.md) beschrijft de
geverifieerde ruleset en de nog onbevestigde workflowrechten, reviewers,
modeltoegang en kosten. Een live Actions-proef heeft nog niet plaatsgevonden.
De volgende stap is onafhankelijke beveiligingscontrole van de draft-PR.
