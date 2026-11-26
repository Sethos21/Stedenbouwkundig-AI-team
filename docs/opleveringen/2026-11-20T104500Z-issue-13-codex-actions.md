# Issue #13 — zelfstandige Codex Actions-route

**Opdrachtstatus** GEBLOKKEERD. De publicatiestatus staat in het PR-ontvangstbewijs.

- Bronopdracht https://github.com/Sethos21/Stedenbouwkundig-AI-team/issues/13
- Bestaande draft-PR https://github.com/Sethos21/Stedenbouwkundig-AI-team/pull/14
- Branch infra/codex-actions-independent, basis cc761efd0f967e56fc5d5d5d170c6bd4a6c9e7c1
- Work-commit 76a4ca46f6921e68a77638524d98bc5198693763

De workflow begrenst de proef tot één nieuw document per issue. De eigenaar
autoriseert de exacte issuerevisie via dispatch. De controller reserveert een
unieke claimref, scheidt model- en publicatierechten en controleert de diff
vóór de branchupdate. De workflow maakt een draft-PR. Claude, MVP-01a, K00
en HumanApprovalService zijn buiten de diff gebleven.

## Bewijs en beperkingen

- `python3 -m unittest discover -s scripts/codex-actions -v` gaf 8 geslaagde
  tests voor onder meer gewijzigde revisie, ongeldige vrijgave, dubbele claim,
  race, ontbrekend secret, buiten-scope diff, uitvoertekst en redirect.
- `.tools/source-venv/bin/python run_tests.py` gaf 507 geslaagde tests
  op Linux. Dit is dezelfde unittest-suite als de Windows-wrapper.
- `git diff --check` slaagde.
- Live Actions-proef en onafhankelijke beoordeling zijn niet uitgevoerd.
  Algemene codeopdrachten en automatische merges zijn niet geïmplementeerd.

## Blokkade en hervatpunt

De integratie kreeg HTTP 403 op Actions-permissions en secrets. GitHub meldde
een planbeperking voor branchregels op deze private repository. Master is
onbeschermd en auto-merge staat uit. Laat eerst de bootstrap-PR onafhankelijk
beoordelen. Richt daarna de beveiligde environments, Actions-PR-permissie en
afzonderlijke projectsleutel in volgens de
[installatiehandleiding](../infra/CODEX_ACTIONS_INSTALLATIE.md). Voor
automerge is een plan nodig dat branchbeleid afdwingt terwijl de repository
privé blijft. Controleer daarna de keten met een synthetisch issue.
