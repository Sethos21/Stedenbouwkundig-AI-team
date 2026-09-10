# BVC AI Ontwerpteam — Milestone 1

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

Er zijn geen koppelingen met OpenAI, Google Drive, QGIS, PDOK, Kadaster, BGT, BAG of Autodesk Forma. Er zijn geen kaartgeneratie, webdashboard, clouddeployment of productie-authenticatie. AIProvider is de uitbreidingsgrens voor een latere Responses API/Agents SDK-adapter. Voor Milestone 2: eerst de menselijke identiteit en rechten uitwerken, daarna één read-only bronadapter met bron- en geometrievalidatie.
