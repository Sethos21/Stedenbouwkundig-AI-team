# A06 official OW document retrieval — fase 2

Bronbewijs van één expliciet geselecteerde vastgestelde OW-regeling. Dit voegt
geen planologische classificatie, applicability, AI-interpretatie of agent-tools toe.
A02, A06 V1 en Human Approval blijven ongewijzigd.

## Officieel contract en endpoints

Het [officiële register](https://developer.omgevingswet.overheid.nl/api-register/api/omgevingsdocument-presenteren/)
verwijst naar [Presenteren v8 OpenAPI](https://developer.omgevingswet.overheid.nl/publish/pages/166112/omgevingsdocumenten-presenteren-v8.json).
De originele specificatie is vastgelegd in
`docs/contracts/dso/presenteren-v8.openapi.json`: versie **8.2.5**, SHA-256
`37d70096ae6bd338a6b7824da12512a6375644bf20171613da4fbc8843a2105d`.
De lokale .gitattributes bewaart de originele contractbytes zonder Git-regelafbrekingconversie.
Deze hash en de response API-version worden strikt gecontroleerd; geen runtime
contractdownload of stil accepteren van drift.

Vaste productiebase:
`https://service.omgevingswet.overheid.nl/publiek/omgevingsdocumenten/api/presenteren/v8`.

Alleen GET naar:
- `/regelingen/{uriIdentificatie}`;
- `/regelingen/{uriIdentificatie}/documentstructuur`;
- `/regelingen/{uriIdentificatie}/regeltekstannotaties` **of**
  `/regelingen/{uriIdentificatie}/divisieannotaties`.

De officiële metadata bepaalt welke van beide annotatiestructuren beschikbaar is.
Die link wordt uitsluitend gevalideerd tegen bovenstaande gesloten profielen.
Requests worden lokaal opgebouwd; response-URL's worden nooit rechtstreeks gevolgd.
Andere links, afbeeldingen en publicaties blijven onopgehaalde bronverwijzingen.
`_expand=false` op metadata/annotaties; geometriepayloads worden geweigerd.

Er zijn vier calls: metadata, structuur, annotaties, opnieuw metadata.
De tweede metadatacapture moet inhoudelijk exact gelijk zijn aan de eerste.
Dit detecteert veranderingen tijdens retrieval; het is geen atomaire serversnapshot.

## Capability en binding aan discovery

```python
service = OWDocumentRetrievalService(trusted_transport)
evidence = service.retrieve(
    discovery_package,
    selected_official_document_identity,
    expected_discovery_hash=independently_pinned_discovery_hash,
)
```

Voor toekomstig live gebruik: `DSOLiveOWTransport(live_opt_in=True)`, met dezelfde
runtime-only `DSO_API_KEY`-grens als fase 1. Geen live proof uitgevoerd.
Mockresponses zijn uitdrukkelijk synthetisch en bevatten geen opgeslagen key.

De caller moet de volledige officiële identificatie exact uit de discoveryset
kiezen. Verificatie controleert de onafhankelijk vastgelegde discoveryhash en
bouwt discovery opnieuw op uit de ruwe evidence, requestgegevens en timestamps.
Een eventuele A02-binding blijft onderdeel van die pin; retrieval herbeoordeelt
geen A02-actualiteit en krijgt geen Store. Een hash is integriteitsbewijs, geen
authenticatie. De pin moet uit de vertrouwde applicatie komen, niet uit een
onbeheerde provider-output.

IMRO, ontwerpen, besluiten en vergunningen worden geweigerd. Geen alternatieve
versie, fuzzy keuze of fallback. Identificatie, expressionId, registratienummer,
documenttype en bevoegdgezagcode moeten overeenkomen met de geselecteerde
discoverymetadata. Aanwezige geldigheids-/beschikbaarheidstijden worden vergeleken.
Documentstructuur en annotaties moeten via officiële links aan hetzelfde document
en dezelfde tijdcoördinaten gebonden zijn. Ontbrekende componentinhoud,
dubbele identifiers en onopgeloste interne annotatiereferenties falen gesloten.

`geldigOp` en `beschikbaarOp` komen uit discovery. `inWerkingOp` wordt expliciet
gelijk gesteld aan `geldigOp`; een daardoor andere versie wordt geweigerd.
Presenteren rondt beschikbaarheid omhoog op hele seconden: niet-nul fracties
worden daarom geweigerd, niet stil afgerond. Tijdzone wordt expliciet UTC.
Het gesloten URI-profiel ondersteunt de officiële vervanging van slash en
koppelteken door underscore; overige niet-ondersteunde URI-tekens falen gesloten.

## Bronbewijs en afgeleide structuur

`BVC_A06_OW_SOURCE_EVIDENCE_V1` bevat:
- discoveryhash en de volledige geselecteerde discoverydocumentmetadata;
- vier broncaptures met originele API-JSON en exacte UTF-8 response;
- endpoint/queryparameters, niet-geheime requestheaders, request-/responsehashes,
  contract-URL/hash/versie, bronstatus en retrieval start/einde per capture;
- de originele documentstructuur, metadata, annotaties, relaties en
  locatie-/geometrie-identificaties als verwijzingen;
- een afzonderlijke `derived_structure`: uitsluitend letterlijke work-/expression-
  componentidentifiers met JSON-pointers naar de betreffende broncapture;
- een canonieke SHA-256 `evidence_hash` over het hele resultaat behalve zichzelf.

Geen XML/HTML-uitvoering, juridische tekstanalyse, geometrieconstructie of
interpretatie van annotaties. De capability retourneert een lokaal serialiseerbaar
pakket; zij schrijft geen Store of bestanden. De vertrouwde caller kan het pakket
lokaal bewaren. Een toekomstige agent krijgt alleen deze capability, geen transport,
secret, filesystem of willekeurige HTTP-toegang.

## Grenzen en tests

Alleen vastgestelde regelingen binnen dit profiel. Maximaal vier responses van
elk 4 MiB en 15 seconden; geen paginering of gedeeltelijke fallback.
De strikte schema-subset en verplichte bindingen kunnen geldige maar buiten dit
profiel vallende responses weigeren. Geen live interoperabiliteitsbewijs zonder key.

`tests/test_ow_document.py` test discoverybinding, OW/IMRO-scheiding, determinisme,
bronbehoud, hashes, metadata-/versie-/tijdconflicten, incomplete structuur,
annotatiereferenties, contractdrift, secretreflectie en ongewijzigde A02/A06 V1.
De bestaande fase-1-tests blijven ongewijzigd. Volledige regressie: `./test.ps1`.

## Lokaal testen na GitHub-review

Codex voert geen live DSO-aanroepen uit. Open na review gewone Windows PowerShell
waarin DSO_API_KEY al als omgevingsvariabele beschikbaar is. De wrapper gebruikt
de bestaande lokale Python-installatie en downloadt niets.

Geef beide tijdassen expliciet op (onderstaande datum is slechts een voorbeeld):

~~~powershell
./scripts/test_dso_phase2.ps1 -Live -Peildatum '2026-10-02' -BeschikbaarOp '2026-10-02T09:00:00Z'
~~~

Kies vervolgens bewust een volledige OW-identificatie uit de getoonde discoveryset:

~~~powershell
./scripts/test_dso_phase2.ps1 -Live -Peildatum '2026-10-02' -BeschikbaarOp '2026-10-02T09:00:00Z' -DocumentIdentity '/akn/nl/act/…'
~~~

Het tweede commando doet opnieuw discovery en bindt retrieval aan de hash van
die capture. Geen automatische documentkeuze. Een IMRO-document, ontwerp,
onvolledige response of contractafwijking stopt gesloten. Zonder documentkeuze
test het script uitsluitend discovery; een lege set bewijst geen retrieval.

De vaste Meppel-testlocatie komt uit het bestaande, op SHA-256 gepinde
meppel-live-evidence.zip en address-evidence.json: K.E. Borgerlaan 4,
RD [208874.379, 524096.822]. Dit is uitsluitend een testpunt, geen gebiedsgrens.
Er vindt geen nieuwe PDOK-, BAG- of BGT-aanroep plaats.

De sleutel wordt uitsluitend via de geerfde omgevingsvariabele aan het bestaande
transport beschikbaar gesteld: geen keyparameter, prompt, bestand of log.
De console toont uitsluitend JSON met status, tijdassen, documentidentiteiten,
versies, hashes en aantallen. Providerfouten worden niet afgedrukt.
Broncaptures worden binnen de capability volledig gevalideerd en uitsluitend
in geheugen gehouden; deze smoke test schrijft geen bestanden, Store of brondata.
De consolehash alleen is dus geen duurzaam gearchiveerd bronbewijs.
Een succesvolle probe is geen Human Approval of juridische beoordeling.

## Offline verificatie voor review (8 oktober 2026)

- Definitieve test.ps1: 536 tests geslaagd (158,679 seconden).
- Gerichte OW-retrieval- en probe-tests: 14 geslaagd.
- PowerShell-parsercontrole en git diff --cached --check: geslaagd.
- Geen live DSO-aanroepen vanuit Codex; live interoperabiliteit blijft te testen
  vanuit lokale Windows PowerShell na code-review.

## Veilige diagnose van live interoperabiliteit

De eerste probe gaf alleen FAILED_CLOSED/SUPPRESSED: de transportworker verving
elke fout door None en de CLI verving vervolgens iedere exception door dezelfde
melding. Daardoor zijn de oorzaak en HTTP-status van die eerdere live-test niet
achteraf te reconstrueren. Deze uitbreiding voert zelf geen live test uit.

Bij fouten blijft de exitcode 1 en blijven status=FAILED_CLOSED en
details=SUPPRESSED behouden. Aanvullende vaste velden:

- phase: discovery (voorbereiding/discoveryvalidatie), transport,
  response (ontvangstcontrole) of validatie (contract/schema/documentbinding).
- category: AUTHENTICATION (ontbrekende/ongeldige configuratie, HTTP 401/403),
  NETWORK_TRANSPORT (onder meer DNS/TLS/timeout), UNEXPECTED_HTTP_STATUS
  (andere niet-200-status, inclusief redirects), CONTRACT_VERSION_MISMATCH
  (lokale contracthash of ontbrekende/afwijkende API-Version),
  SCHEMA_VALIDATION (JSON/schema, responsegrenzen of documentbinding),
  INTERNAL_APPLICATION (onverwachte applicatiefout).
- http_status: uitsluitend een HTTP-status als getal, indien bekend; anders null.
- contract_version: uitsluitend een versie met drie numerieke delen van elk
  maximaal drie cijfers; bij ontbrekende, dubbelzinnige, onveilige of met de
  DSO_API_KEY overeenkomende waarde null. Dit is de ontvangen API-Version,
  geen bevestiging dat de versie ondersteund wordt.

De transportworker exporteert geen oorspronkelijke exception of traceback.
De CLI serialiseert uitsluitend de gesloten diagnostische velden, nooit
exceptiontekst, request-/responseheaders of providerbody. HTTP-foutbodies worden
niet gelezen. Een interne fout zonder betrouwbare fasecontext krijgt validatie
als veilige terugvalfase. Diagnostiek voegt geen fallback, retry of request toe.
Vaste endpoints, 4 MiB-limiet, 15-seconden-deadline en expliciete live-opt-in
blijven ongewijzigd. A02, A06 V1, K00 en Human Approval zijn niet aangepast.

Offline categorie-, redactie- en parsertests: tests/test_dso_diagnostics.py.
Een lokale herhaling na review gebruikt dezelfde PowerShell-commando's als boven.

Diagnoseverificatie: 37 gerichte DSO-tests geslaagd; volledige test.ps1: 544 tests geslaagd (175,510 seconden). Geen live DSO-test uitgevoerd.
