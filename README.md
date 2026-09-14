# BVC AI Ontwerpteam — Milestone 1 en 2A

Een lokale, versieerbare en testbare ontwerpruntime, volledig los van de BVC Financiële Rapportagetool. Deze milestone bewijst de keten **A01 Regisseur → A02 GIS & Brondata → A07 Gemeentelijke Reviewer → AWAITING_HUMAN_APPROVAL**.

Alle invoer is synthetische **TESTDATA**. Er is geen echte geometrie, bronvalidatie of ontwerp van Mastenbroekweg uitgevoerd. Een voldoende demo-review zegt uitsluitend dat de fixture-inventarisatie aan de demonstratiecriteria voldoet.

## Lokaal starten op Windows

Open PowerShell in deze projectmap:

```powershell
.\bvc-ai.ps1 demo gis-001
.\bvc-ai.ps1 tasks
.\bvc-ai.ps1 status GIS-001
.\bvc-ai.ps1 review GIS-001
.\bvc-ai.ps1 audit GIS-001
.\test.ps1
```

De meegeleverde projectlokale Python-installatie staat in .tools/python en wordt niet opgenomen in Git. Geen pip-installatie of externe Pythonpackages nodig. Op een ander systeem volstaat Python 3.12 of nieuwer:

```text
python bvc_ai.py demo gis-001
python run_tests.py
```

Het optionele globale CLI-argument --data kiest een afzonderlijke opslagmap **binnen het project**, bijvoorbeeld .\bvc-ai.ps1 --data runtime/experiment demo gis-001. Een bestaande GIS-001 wordt niet overschreven. Gebruik een andere opslagmap voor een nieuwe demonstratie.

## Menselijke goedkeuring

De workflow stopt altijd vóór een definitief besluit. Alleen de afzonderlijke HumanApprovalService in de vertrouwde CLI kan vanuit AWAITING_HUMAN_APPROVAL een besluit vastleggen:

```powershell
.\bvc-ai.ps1 approve GIS-001 --actor "Seth" --reason "Door mij beoordeeld"
.\bvc-ai.ps1 reject GIS-001 --actor "Seth" --reason "Meer onderbouwing nodig"
```

Voer deze opdrachten alleen uit als u zelf wilt beslissen. Actor, tijdstip, besluit en toelichting worden opgeslagen en geaudit. Dubbele besluiten en besluiten vanuit een verkeerde status worden geweigerd. Agentidentiteiten A01–A07 zijn verboden als menselijke actor. De test-suite simuleert CLI-besluiten in tijdelijke testopslag en verandert de demonstratie niet.

Dit is een lokale, vertrouwde bediening zonder productie-authenticatie: een getypte naam bewijst geen identiteit. Agentproviders krijgen geen approval-capability, opslag of uitvoertools. Willekeurige Python-code of iemand met schrijftoegang tot de database valt buiten deze beveiligingsgrens; zie docs/architecture.md.

## Architectuur en structuur

- src/bvc_ai/domain: datamodellen, expliciete statusmachine, bron- en K00-policy.
- src/bvc_ai/application: workflow, beperkte agentingang en aparte HumanApprovalService.
- src/bvc_ai/agents: providerprotocol en DeterministicTestProvider.
- src/bvc_ai/adapters: Drive/Document- en GIS-interfaces plus in-memory mocks.
- src/bvc_ai/infrastructure: SQLite-opslag en leesbare JSONL-auditexport.
- src/bvc_ai/cli: lokale bediening.
- config/agents.json: alle zeven rolprofielen met taken en verboden.
- examples/gis-001.json: uitsluitend TESTDATA-fixture.
- tests: geautomatiseerde domein-, workflow-, persistentie- en CLI-tests.
- docs: architectuur, workflow, statusmachine en validatie.
- runtime: lokale database en audit.jsonl; niet in Git.
- .tools: lokale interpreter, cache en tijdelijke testopslag; niet in Git.

De namespace onder src/bvc_ai voorkomt botsingen met generieke modulebenamingen. A01 coördineert, A02 inventariseert en A07 reviewt. A03 Stedenbouwkundige, A04 Landschapsarchitect, A05 Mobiliteitsontwerper en A06 Planoloog & Beleid zijn alleen voorbereid.

## Revisies en bronherkomst

Een onvoldoende review bewaart concrete herstelpunten en zet de taak terug naar READY. Hervat met .\bvc-ai.ps1 resume GIS-001. A02 ontvangt de herstelpunten en levert een nieuwe versie; eerdere output en reviews blijven bewaard. Er is geen onbegrensde automatische revisielus.

Elke output bevat task/agent/tijdstip, input- en bronverwijzingen, brontype en -status, confidence, versie, review- en approvalvelden en notes. De oorspronkelijke output heeft PENDING-reviewmetadata; de afzonderlijke Review koppelt het uiteindelijke verdict aan exact die versie. De actuele taak bevat de actuele reviewstatus en het eventuele menselijke besluit. Confidence 0.0 betekent hier geen vertrouwen in echte locatiefeiten.

Fixtures moeten TESTDATA blijven. De overige bronstatussen zijn voorbereid, maar worden in deze demoworkflow niet als echte bronnen geaccepteerd. K00 is een mockreferentie zonder geometrie; schrijven, regenereren, aanpassen of verwijderen is verboden.

## Opslag en grenzen

Taakwijzigingen en canonieke auditevents worden samen in SQLite-transacties opgeslagen. audit.jsonl is een opnieuw te genereren leesbare export bij CLI-afsluiting. Audit is inspecteerbaar, niet cryptografisch fraudebestendig. Gebruik op de netwerkmap één actieve CLI/workflow tegelijk; meerdere machines en onbetrouwbare SMB-locking zijn niet ondersteund.

Milestone 1 heeft geen externe koppelingen. Milestone 2A voegt alleen een optionele OpenAI-provider toe; Google Drive, QGIS, PDOK, Kadaster, BGT, BAG en Autodesk Forma blijven afwezig. Er zijn geen kaartgeneratie, webdashboard, clouddeployment of productie-authenticatie. AIProvider is de uitbreidingsgrens voor de Responses API-adapter. Menselijke authenticatie/rechten en een read-only bronadapter met bron- en geometrievalidatie vallen buiten Milestone 2A.

## Milestone 2A: optionele OpenAI-provider

Milestone 1 blijft standaard beschikbaar met `--provider mock` (ook de standaard zonder argument).
Er zijn geen packages nodig: de OpenAI-adapter gebruikt Python HTTPS en de Responses API.
`OPENAI_API_KEY` wordt uitsluitend uit de procesomgeving gelezen; er wordt geen `.env` geladen of key opgeslagen.
Een ontbrekende key geeft bij `demo`/`resume` een fout, bij de beperkte `smoke` een expliciete SKIPPED-uitkomst.
Leescommando's en menselijke besluiten vereisen geen API-key, ook met `--provider openai`.

```powershell
.\bvc-ai.ps1 --provider mock smoke
.\bvc-ai.ps1 --provider openai smoke
```

De OpenAI-smoke doet maximaal één A02-aanvraag met de lokale `examples/gis-001.json` TESTDATA-fixture.
A07 gebruikt in deze smoke de deterministische provider. De bestaande workflow eindigt bij voldoende review
op AWAITING_HUMAN_APPROVAL. Iedere smoke krijgt een eigen `runtime/smoke/<unieke-id>`-map;
de bestaande goedgekeurde GIS-001 in `runtime` wordt niet aangeraakt. Het resultaat meldt de opslagmap.
Zonder omgevingskey wordt geen opslagmap gemaakt en geen API-call gedaan.

Voor een volledige providerworkflow in een afzonderlijke opslagmap (twee API-calls bij een succesvolle run):

```powershell
.\bvc-ai.ps1 --provider openai --data runtime/openai-demo demo gis-001
```

Model: `gpt-4.1-mini-2025-04-14`, instelbaar via `--model`. Socket-timeout: 30 seconden,
instelbaar via `--timeout` (maximaal 120). Per aanvraag maximaal 1200 outputtokens, geen automatische retries.
Het verzoek bevat geen tools en gebruikt `store: false`. De fixture wordt wel naar OpenAI verzonden.
Er is geen web-, GIS-, Drive- of ontwerpfunctionaliteit toegevoegd.

De adapter valideert JSON lokaal naast het strikte API-schema. A02 retourneert alleen tekstlijsten;
bronregisteritems worden lokaal ongewijzigd gekopieerd. Provider/model/rol/TESTDATA-herkomst wordt door
vertrouwde adaptercode toegevoegd in `payload.recommendations`; A07-herkomst staat in review `findings`.
`source_type=fixture` en `source_status=TESTDATA` blijven bronherkomst beschrijven, niet de AI-provider.
De domain/application-lagen, statusmachine en HumanApprovalService zijn ongewijzigd.
Zie [Milestone 2A-validatie](docs/milestone-2a.md).

## Milestone 2B — Ontwerplus (uitsluitend TESTDATA)

De acht-agent ontwerpworkflow heeft eigen rolcapabilities, revisiegates, specialistische reviews, een iteratielimiet en een menselijk beslispakket. De bestaande GIS-demo en rolconfiguratie blijven behouden.

```powershell
.\bvc-ai.ps1 demo design-test-001
.\bvc-ai.ps1 --data runtime/milestone-2b design-report DESIGN-TEST-001
```

De demo gebruikt alleen de deterministische provider en stopt op AWAITING_HUMAN_APPROVAL met human_approval null. Opslag staat apart onder runtime/milestone-2b. Zie [workflow en architectuur](docs/milestone-2b.md) en [validatiebewijs](docs/milestone-2b-validation.md).
