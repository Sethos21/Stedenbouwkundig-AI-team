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

## Vrijgave en proef

De eigenaar maakt een nieuw issue met titelprefix `[CODEX-AUTO-DOC] `.
Gebruik een korte synthetische opdracht zoals «Beschrijf twee manieren om
schaduw in een fictieve speeltuin te bieden». ChatGPT kan de tekst voorbereiden.
De eigenaar controleert en autoriseert de exacte titel en tekst door op
`master` de workflow *Codex independent* te dispatchen met het issue-ID en de
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
Nul approvals dwingt geen onafhankelijke review af. Auto-merge staat uit
en er is nog geen live Actions-proef uitgevoerd. De infrastructuur-PR en
gevoelige paden vallen buiten automatische merges.
