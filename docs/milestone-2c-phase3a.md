# Milestone 2C — Fase 3A: PDOK adapterbasis

Baseline: master / 818531dd86f84100baa063fbbc7cc333b12e271c.
De vooraf uitgevoerde preflight is hergebruikt: clean worktree, 241/241 groen.
Scope is uitsluitend de aangescherpte Fase-3A-opdracht, niet de eerdere volledige
Fase-3-opdracht. Geen live netwerk of Mastenbroekweg-import uitgevoerd.

## Implementatie

- adapters/source_transport.py: kleine GetTransport Protocol met uitsluitend
  get(GetRequest), immutable HttpResponse en CapturedResponse.
  GetRequest.method staat vast op GET. De transportgrens levert ongewijzigde
  bytes en headers, zonder parsing of redirects. Geen live HTTP-client gebouwd.
- adapters/pdok_bgt.py: PDOKBGTAdapter met vaste officiële base
  https://api.pdok.nl/lv/bgt/ogc/v1 en collection pand.
  fetch_page doet exact één transportaanroep en verwerkt één pagina.
- Geen wijzigingen aan bestaande source-, hash-, validatie-, opslag- of
  workflowmodules. Geen nieuwe dependencies.

De request bevat bbox uit een expliciete FetchExtent, bbox-crs en crs als
http://www.opengis.net/def/crs/EPSG/0/28992, f=jsonfg en integer limit 1..1000.
Accept is application/vnd.ogc.fg+json. Een ongeldig request faalt vóór transport.
De adapter voegt geen datetime/peildatumparameter toe of verzint een historische
selectie. Fase 3A claimt geen aanvullend bewezen actualiteitscontract.

## Raw capture en foutgrens

Iedere ontvangen HttpResponse wordt vóór Content-Type-controle, JSON-decoding
of featuremapping vastgelegd in CapturedResponse, met:

- exacte body en bestaande RawResponse/SHA-256;
- originele status en headerparen;
- exacte request-URL, parameters en Accept-header;
- retrieval start/eind via injecteerbare klok;
- expliciete ResponseOrigin.

Ook 3xx/4xx/5xx, invalid JSON, CRS-conflicten en invalid geometrie behouden de
ontvangen response/capture. Bij een transportexception zonder response is
capture None; er wordt geen response gefabriceerd. Geen retries.
Bij een parse-/validatiefout lekken geen gedeeltelijk geaccepteerde
SourcePage/SourceFeature/GeometryRecord-resultaten naar buiten.

ResponseOrigin.TESTDATA blijft TESTDATA in alle provenance.
ResponseOrigin.PROVIDER_RESPONSE betekent uitsluitend UNVALIDATED_PROVIDER_RESPONSE.
Deze afkomstmarkering is een verklaring van de vertrouwde transportimplementatie,
geen sandbox of bewijs van authenticiteit. In deze fase zijn alleen expliciet
synthetische TESTDATA-responses via fake transport gebruikt.

## JSON-FG-profiel en aansluiting op Fase 1/2

Vereist: HTTP 200, application/vnd.ogc.fg+json (eventueel UTF-8 charset),
UTF-8 JSON-object met type FeatureCollection en features-array.
Geen gecomprimeerde body in dit basisprofiel; geen impliciete decompressie.
Dubbele JSON-keys en dubbele HTTP-headernamen worden geweigerd.

Per feature: type Feature, niet-lege string id, properties-object en place-object.
Geen identityfallback via properties/lokaal_id of geometryhash. Dubbele feature-ID's
binnen dezelfde pagina falen. Klassiek geometry wordt niet als RD-bron gebruikt
en vervangt een ontbrekende place nooit.

place wordt zonder geometriecorrectie gemapt naar het bestaande GeometryRecord,
met de bestaande geometry_structural_hash/canonicalization_version en
validate_geometry_record. Decimalwaarden blijven exact in de gemapte JSON;
er wordt geen float-rounding ingevoerd door de adapter. De originele raw bytes
blijven daarnaast volledig behouden.

SourceFeature.source_id blijft de provider-id. Properties blijven volledig
bewaard, inclusief lokale objectidentificatie, bronhouder en registratie-/
actualiteitsvelden wanneer aanwezig. Extra feature- en responsemetadata blijven
in provenance/metadata_json. source_version blijft None: dit beperkte profiel
interpreteert registratievelden niet zonder expliciet providercontract als
versie-ID. Dat is geen verlies van de oorspronkelijke velden.

numberReturned is optioneel; indien aanwezig moet het een niet-negatief geheel
getal zijn dat exact overeenkomt met len(features). Afwezig blijft onbekend/null;
parsed_feature_count wordt afzonderlijk geregistreerd. Een pagina met meer
features dan de aangevraagde limit faalt. Dit is requestcontractvalidatie,
geen implementatie van fetchbudgetten.

## CRS-bewijs

De vertrouwde caller moet expliciete collectionmetadata meegeven:
id=pand en een crs-lijst die RD ondersteunt. Aanwezige storageCrs moet in dit
native-RD-profiel eveneens RD zijn. De metadata worden niet live opgehaald.
Volledige metadata en de officiële collection-URL worden bewaard als context;
de URL alleen bewijst niet dat die metadata live zijn opgehaald.

Verplicht per response: Content-Crs en root coordRefSys als expliciete
RD-identificatie. Content-Crs kan de URI tussen punthaken bevatten.
Een aanwezige feature-level coordRefSys moet eveneens RD verklaren.
Ontbrekend bewijs, onbekende identificatie of conflict faalt gesloten.
Het basisprofiel ondersteunt coordRefSys als identifierstring; andere
representaties falen gesloten.

Request crs/bbox-crs, Content-Crs, root/feature coordRefSys en collectionmetadata
blijven in CRSMetadata.evidence/provenance. Axis-order easting/northing,
units metres en dimension 2 komen uit het bestaande expliciete EPSG:28992-contract.
De bestaande Fase-2-validator controleert het gemapte record opnieuw.
Geen coordinate guessing, CRS-transformatie of geometry repair.

## Fasegrens

Een succesvol PageResult heeft status VALIDATING, nooit COMPLETE.
Er wordt geen SourceSnapshot gemaakt of gepubliceerd. Een ontbrekende next-link
is in deze fase geen compleetheidsbewijs. Aanwezige next-links worden uitsluitend
ongewijzigd in SourcePage/metadata bewaard; niet opgelost, gevalideerd voor
vervolgrequests of gevolgd. Fase 3B moet eerst de scope/securitycontrole bouwen
voordat links gevolgd mogen worden.

Geen pagination, retries, fetchbudgetten, SourceImportService,
EXISTING_VALIDATED, revision/stale, replay, live import of URBAN_BASE.
Geen Store- of approval-capability. Bestaande invarianten zijn hergebruikt;
de tests voegen alleen gerichte controles voor de nieuwe adaptergrens toe.

## Verificatie

Nieuwe tests: tests/test_pdok_bgt.py, 34 netwerkloze tests.
Fake transport registreert GetRequest en levert exacte vooraf ingestelde bytes/
headers/status of een transportexception. Synthetische geometrie gebruikt een
abstract vlak van 0..10, niet de Mastenbroekweg-testcase.

Afzonderlijke Fase-3A-run: 34/34 OK (0.035 s).
Volledige test.ps1: 275/275 OK (42.589 s), exitcode 0. Alle 241 bestaande tests blijven groen. Geen afzonderlijke herbewijsruns van Fase 1/2 uitgevoerd. git diff --check en witruimtecontrole van nieuwe bestanden geslaagd. Alleen vier nieuwe Fase-3A-bestanden; geen bestaande bestanden gewijzigd. Geen commit, push of start van Fase 3B. Geen blocker voor de afgebakende offline adapterbasis; werkelijke providercompatibiliteit/live bewijs valt buiten deze fase.
