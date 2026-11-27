# Codex Actions voor documentatieproeven

Issue #13, concept-PR #14. Deze eerste route verwerkt één expliciet vrijgegeven
documentatieopdracht per run. Het model krijgt alleen de titel en inhoud van
het gekozen issue. Het krijgt geen tools, repository-inhoud of GitHub-token.
Het resultaat kan uitsluitend één nieuw bestand `docs/codex-results/issue-N.md`
opleveren. De controller schrijft daarnaast een vertrouwd opleverrapport in
`docs/opleveringen/` en plaatst na verificatie een `CODEX_OPLEVERING_V1`-bewijs
op de draft-PR. Beide paden staan expliciet op de allowlist. De route gebruikt de officiële Responses API met vaste model-ID
`gpt-5.3-codex`, maximaal 2.000 uitvoertokens en één aanvraag per claim.
Toegang tot dit model en de werkelijke kosten moeten in het gekozen OpenAI-project
worden gecontroleerd.

## Inschakelen na onafhankelijke review

1. Laat PR #14 onafhankelijk op beveiliging beoordelen en merge uitsluitend
   via het normale menselijke besluit. De workflow accepteert alleen dispatch
   vanaf `master`. Zet de route pas daarna aan.
2. Controleer in **Settings → Actions → General** dat de workflow mag draaien
   met de gepinde officiële checkout-action en dat Actions pull requests mag
   aanmaken. Laat de standaardrechten op read-only staan. De workflow kent
   schrijfbevoegdheden per job toe.
3. De eigenaar meldt dat `codex-control` en `codex-execution` onder
   **Settings → Environments** zijn beperkt tot `master`. Verifieer vóór
   vrijgave de branchbeperking, onafhankelijke reviewers en preventie van
   zelfgoedkeuring. De feitelijke handhaving is nog onbevestigd.
4. De eigenaar meldt dat `CODEX_ACTIONS_API_KEY` als environment-secret in
   `codex-execution` staat. Effectieve rechten, modeltoegang en kosten zijn
   nog onbevestigd. Gebruik uitsluitend synthetische invoer voor de proef.
5. De eigenaar meldt dat `CODEX_ACTIONS_ENABLED` een **repositoryvariabele**
   is met waarde `false`. Laat die waarde staan tot expliciete vrijgave.

## Alleen-lezen preflight na afzonderlijke vrijgave

1. Laat de wijziging onafhankelijk beoordelen en laat de eigenaar beslissen
   over merge. Controleer daarna de bestaande environment-, actor- en
   branchbeperkingen, de repositoryvariabele en eventuele actieve runs.
2. Laat de eigenaar na expliciete vrijgave **Codex independent** op `master`
   dispatchen met `mode=preflight`, zonder issue-ID of revisie. Dezelfde
   repository-, actor-, triggering actor-, master-, first-attempt- en
   enablement-guards gelden als voor documentuitvoering. De job deelt de
   bestaande concurrencygroep en gebruikt de bestaande `codex-execution`
   environment.
3. De job draait eerst de controllertests zonder API-sleutels in die stap.
   Daarna leest de controller de actuele master-SHA op GitHub en vraagt hij
   metadata voor het geconfigureerde model bij OpenAI op. Elke API krijgt
   uitsluitend haar eigen credential. De job stopt bij de eerste fout en
   heeft een limiet van twee minuten. Er zijn geen automatische retries.
   De preflight claimt geen issue, schrijft geen branch of PR en verstuurt
   geen issue-inhoud naar OpenAI.
4. Lees de veilige logregels op fase, operatie, HTTP-status en categorie.
   Een geslaagde modellookup bevestigt dat de sleutel de modelmetadata kan
   lezen. Toegang tot de Responses API, de payload, quota en kosten van een
   generatie vereisen een afzonderlijk vrijgegeven documentproef.

## Vrijgave en proef

De eigenaar maakt een nieuw issue met titelprefix `[CODEX-AUTO-DOC] `.
Gebruik een korte synthetische opdracht zoals «Beschrijf twee manieren om
schaduw in een fictieve speeltuin te bieden». ChatGPT kan de tekst voorbereiden.
De eigenaar controleert en autoriseert de exacte titel en tekst door op
`master` de workflow *Codex independent* te dispatchen met `mode=document`, het issue-ID en de
revisiehash. Bereken de hash vanuit de projectmap:

```bash
gh api repos/Sethos21/Stedenbouwkundig-AI-team/issues/ISSUE_ID |
  python3 -c 'import hashlib,json,sys; i=json.load(sys.stdin); data=json.dumps([i["title"],i["body"]],ensure_ascii=False,separators=(",",":")); print(hashlib.sha256(data.encode()).hexdigest())'
```

Controleer de claimcomment, de geslaagde tests in de run, de exacte diff van
het docbestand en het opleverrapport, plus de draft-PR met teruglink naar de
run en het ontvangstbewijs. Laat het resultaat
onafhankelijk beoordelen. Verwacht bij een tweede dispatch naar hetzelfde
issue dat de claim stopt vóór modelgebruik. Issue #11 en #13 zijn uitgesloten.
De handmatige opdrachtenbus behoudt haar eigen vrijgaveregels.

## Diagnose en herstel van bestaande claims

De controller geeft per API-aanroep uitsluitend een vaste operatienaam,
HTTP-status (of `none`) en een vaste categorie. Lees bijvoorbeeld 401 als
authenticatiefout, 403 als verboden, 404 als onvindbaar, 429 als limiet,
400 als afgewezen verzoek en 5xx als serverfout. De categorie geeft het
HTTP-resultaat weer. De concrete oorzaak kan per API verschillen. Log
geen headers, fouttekst, requestinhoud, ruwe bodies of credentials bij
vervolgonderzoek.

1. Houd de route bij een incident uitgeschakeld en wacht tot betrokken
   runs beëindigd zijn. Voor #16 en #17 staan de bestaande
   [claim #16](https://github.com/Sethos21/Stedenbouwkundig-AI-team/issues/16#issuecomment-7218716791)
   en [claim #17](https://github.com/Sethos21/Stedenbouwkundig-AI-team/issues/17#issuecomment-7219019452)
   gekoppeld aan respectievelijk
   [run 46001838637](https://github.com/Sethos21/Stedenbouwkundig-AI-team/actions/runs/46001838637)
   en [run 46003890207](https://github.com/Sethos21/Stedenbouwkundig-AI-team/actions/runs/46003890207).
2. Laat de eigenaar per claim run/poging, revisie, basis-SHA, claimref en
   huidige HEAD, eventuele resultaatbestanden en PR (alle statussen)
   vergelijken. Stop bij afwijking of onduidelijke write-uitkomst voor
   handmatige reconciliatie. Laat claims en refs intact.
3. Leg per issue met een nieuwe auditcomment vast wie de toestand
   verifieerde, wanneer, welke run/ref/PR en SHA zijn bekeken, en welk
   herstelbesluit is genomen. Bewaar bestaande comments. Herhaal geen
   workflowpoging en gebruik geen vervangende branch voor hetzelfde issue.
4. Als de eigenaar na diagnose een nieuwe documentproef wil, gebruik dan
   na expliciete vrijgave een nieuw synthetisch issue met een eigen
   revisiehash en een verwijzing naar het herstelbesluit bij de oude claim.
   Een hervatfunctie voor dezelfde claim zou een nieuw bevoegdheidsbesluit
   en een afzonderlijk beoordeeld ontwerp vereisen.

## Fouten en merge

Bij een onzekere claim-, push- of statuswrite blijft een bestaande claimref
staan. Reruns zijn geblokkeerd. Controleer run, issuecomments, branch en PR
bij herstel. Start geen tweede uitvoering en verwijder geen claim om opnieuw
te beginnen. Zet bij een incident `CODEX_ACTIONS_ENABLED` uit en stop actieve
runs via Actions. De workflow maakt alleen draft-PRs.

De repository is publiek. De actieve [ruleset 27890519](https://github.com/Sethos21/Stedenbouwkundig-AI-team/rules/27890519)
beschermt de default branch `master` met een PR-verplichting, verplichte
afhandeling van reviewthreads, een verbod op verwijderen en force-push, en
zonder bypass. De ruleset vereist nul approvals en geen statuschecks.
Nul approvals dwingt geen onafhankelijke review af. Auto-merge staat uit. De twee documentproeven hierboven strandden in de uitvoeringsfase. De infrastructuur-PR en
gevoelige paden vallen buiten automatische merges.
