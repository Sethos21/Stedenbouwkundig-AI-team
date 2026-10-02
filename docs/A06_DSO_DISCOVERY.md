# A06 DSO discovery foundation — fase 1

Afzonderlijke application-capability: `DSODiscoveryService` in
`src/bvc_ai/application/dso_discovery.py`. A06 Planological Context V1 blijft
ongewijzigd. Geen interpretatie, constraints, SDK, providers, bronfallback,
juridische tekstextractie, werkingsgebieddownload of Human Approval.

## Officieel contract

[Officieel register](https://developer.omgevingswet.overheid.nl/api-register/api/omgevingsinformatie-ontsluiten/)
verwijst naar de productie-[OpenAPI-specificatie](https://service.omgevingswet.overheid.nl/publiek/omgevingsinformatie/api/ontsluiten/v2/openapi.json).
De originele publieke specificatie is zonder credentials lokaal vastgelegd als
`docs/contracts/dso/ontsluiten-v2.openapi.json`, versie **2.13.1**,
SHA-256 `4b2c33dc2a91a8c9073042978636f5222802395c3f1664b82c0c425eb126e0b4`.
De parser controleert deze hash bij gebruik; geen runtime schema-download.

Enige runtime-endpoint:
`POST https://service.omgevingswet.overheid.nl/publiek/omgevingsinformatie/api/ontsluiten/v2/documenten/_zoek`.

Het is een read-only zoekoperatie, ondanks POST. Body: uitsluitend een GeoJSON
Point in `geometrie`; `Content-Crs` is
`http://www.opengis.net/def/crs/EPSG/0/28992`. Geen fuzzy `_find`.
Vaste parameters: `page=0`, `size=200`, `_sort=ASC`,
`inclusiefToekomstigGeldig=false`. Geen serverlinks volgen.

`geldigOp` is de expliciete peildatum (YYYY-MM-DD). `beschikbaarOp` is daarnaast
een verplicht expliciet RFC3339-tijdstip met tijdzone: beide tijdassen zijn nodig
om de aanvraag reproduceerbaar vast te leggen. Geen impliciet vandaag/nu.
Retrievaltijd is afzonderlijk UTC en verandert bij een nieuwe opvraging.

## Interface

```python
service = DSODiscoveryService(trusted_transport)
result = service.discover_point(
    [155000, 463000],
    peildatum="2026-10-02",
    beschikbaar_op="2026-10-02T10:30:00+02:00",
)
```

Deze getallen zijn alleen een interfacevoorbeeld, geen live bewijs. Tests gebruiken
uitsluitend gemarkeerde synthetische responses. Voor toekomstig expliciet live
gebruik: `DSOLivePostTransport(live_opt_in=True)`; secret uitsluitend uit
`DSO_API_KEY` bij de daadwerkelijke call. Deze fase voert geen live proof uit.

De vertrouwde lokale laag kan `discover_a02_point(store, spatial_context,
record_ref, peildatum=..., beschikbaar_op=...)` gebruiken. A02 wordt vóór en na
discovery opnieuw gevalideerd. Alleen een bestaand SOURCE_COORDINATES-puntfeit
wordt gebruikt; nooit stil een centroid of bbox-middelpunt. Context-, revisie-,
record- en geometriehashbinding worden opgenomen. A02 en zijn geometrieën blijven
ongewijzigd. Een toekomstige agent ontvangt alleen het beperkte discovery-interface
en data; Store/transport/credentials blijven bij de vertrouwde applicatie.
Er wordt nu geen agent-tool geregistreerd.

## Resultaat en provenance

`BVC_A06_DSO_DISCOVERY_V1` bevat alle documentkandidaten, gesorteerd op officiële
identiteit/versie; er wordt geen document gekozen. Meerdere verschillende
documenten zijn normaal. Dubbele identiteiten, onduidelijke OW/IMRO-familie,
ontbrekende identifiers, inconsistente intervals en onvolledige pagina's falen
gesloten. Een complete lege set betekent alleen nul gevonden kandidaten.

Alle officiële documentmetadata blijven behouden: identificatie, URI-identificatie,
versie, type, titel, aangeleverdDoorEen, aanwezige geldigheids- en
beschikbaarheidstijden, OW-expressionId of IMRO-metadata, gerelateerde versies
en verwijzingen. Links/geometrie-identificaties zijn uitsluitend metadata en
worden niet opgehaald. Metadata impliceert geen vertrouwde juridische constraint.

Provenance bevat endpoint, methode, beide tijdassen en alle queryparameters,
zoekgeometrie, niet-geheime requestheaders, requesthash, API-versie, contracthash
en retrieval start/einde. Exacte geaccepteerde UTF-8 response plus SHA-256 blijft
in het pakket voor offline herparsing. `discovery_hash` bindt het hele pakket,
behalve zichzelf, via canonieke JSON SHA-256. De application-capability schrijft
geen bestanden of Store; de vertrouwde caller kan dit pakket lokaal bewaren.
Gelijke response/input/timestamps geven gelijke output; nieuwe retrievaltijd
betekent bewust een andere capture. Hashes zijn geen authenticatie.

## Grenzen en fail closed

- Alleen een RD-punt, twee coördinaten, maximaal millimeterprecisie zonder afronden;
  begrensd Nederlands RD-profiel. Geen gebiedsdekkingsclaim.
- Maximaal één aantoonbaar complete pagina, 200 documenten en 4 MiB.
  Meer resultaten worden afgewezen in plaats van gedeeltelijk gebruikt.
- Totale deadline maximaal 15 seconden inclusief DNS/TLS/headers/body.
  Een vertraagde daemonworker mag na annulering geen request meer verzenden.
- Alleen productie-HTTPS, vast host/path/body/header/queryprofiel, geen redirects,
  proxy, retries, cookies, decompressie of arbitrary URL-toegang.
- API-Version moet exact 2.13.1 zijn. De schema-parser verwerpt onbekende velden,
  ongeldige typen, dubbele JSON-keys en contractdrift. Contractupdates vereisen review.
- De ingebedde voorbeelden in de officiële OpenAPI verschillen op onderdelen van
  het huidige schema (onder meer metadata-indeling). Het actuele schema is leidend;
  fixtures zijn daarom schema-conforme synthetische voorbeelden. Live compatibiliteit
  is zonder live proof niet aangetoond.
- De key bestaat uitsluitend in runtimegeheugen en de X-API-Key-transportheader.
  HTTP-debug is uitgeschakeld; providerfouttekst en responseheaders worden niet
  geëxporteerd. Key-reflectie in headers, body of JSON-escaped tekst wordt geweigerd
  voordat response-evidence of hashes worden gemaakt.
- Geen statusovergangen of publicatie; fouten stoppen met vaste exceptions.
  Geen veranderingen aan K00-, capability- of Human Approval-grenzen.

Offline tests: `tests/test_dso_discovery.py`, synthetische fixtures in
`tests/dso_fixtures.py`. Volledige regressie: `./test.ps1`.
