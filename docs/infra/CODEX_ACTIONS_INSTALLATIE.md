# Codex Actions voor documentatieproeven

Issue #13, concept-PR #14. Deze eerste route verwerkt één expliciet vrijgegeven
documentatieopdracht per run. Het model krijgt alleen de titel en inhoud van
het gekozen issue. Het krijgt geen tools, repository-inhoud of GitHub-token.
Het resultaat kan uitsluitend één nieuw bestand `docs/codex-results/issue-N.md`
opleveren. De route gebruikt de officiële Responses API met vaste model-ID
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
3. Maak in **Settings → Environments** `codex-control` en `codex-execution`.
   Beperk beide tot `master`. Stel onafhankelijke vereiste reviewers en
   preventie van zelfgoedkeuring in, voor zover het private repositoryplan
   deze mogelijkheden ondersteunt. Schakel de route pas in als de
   beveiligingsreview heeft vastgesteld dat die bescherming afgedwongen wordt.
4. Plaats een afzonderlijke OpenAI-projectsleutel als secret
   `CODEX_ACTIONS_API_KEY` in `codex-execution`. Beperk de sleutel tot
   noodzakelijke API-rechten en controleer modeltoegang, limieten en monitoring.
   Voer geen vertrouwelijke data in het proefissue in.
5. Zet de repositoryvariabele `CODEX_ACTIONS_ENABLED` op `true`, uitsluitend
   tijdens een door de eigenaar beheerd automatisch uitvoeringsvenster.
   Start in dat venster geen handmatige opdrachtenbussessie.

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
het docbestand en de draft-PR met de teruglink naar de run. Laat het resultaat
onafhankelijk beoordelen. Verwacht bij een tweede dispatch naar hetzelfde
issue dat de claim stopt vóór modelgebruik. Issue #11 en #13 zijn uitgesloten.
De handmatige opdrachtenbus behoudt haar eigen vrijgaveregels.

## Fouten en merge

Bij een onzekere claim-, push- of statuswrite blijft een bestaande claimref
staan. Reruns zijn geblokkeerd. Controleer run, issuecomments, branch en PR
bij herstel. Start geen tweede uitvoering en verwijder geen claim om opnieuw
te beginnen. Zet bij een incident `CODEX_ACTIONS_ENABLED` uit en stop actieve
runs via Actions. De workflow maakt alleen draft-PRs.

Automatische merges blijven geblokkeerd. GitHub retourneerde voor deze private
repository een planbeperking op branchregels, `master` is onbeschermd en
`allow_auto_merge` staat uit. Een volgende wijziging vereist een GitHub-plan
met afgedwongen branchbescherming voor deze private repository, verplichte
actuele checks, onafhankelijke review voor de laatste push, bescherming tegen
bypass en een bij merge gevalideerde bestandsallowlist. Schakel auto-merge
pas in na onafhankelijke verificatie van die volledige keten. Gevoelige
paden en de infrastructuur-PR vallen buiten elke automatische merge.
