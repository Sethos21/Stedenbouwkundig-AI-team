# Milestone 2D-1 - Bronselectie en datacontract (beslisversie)

Baseline: `03051103ddec842b2be3b6d6aa0aa5553b7444cc`.
Werkbranch: `milestone-2d-work`. Datum: 29 september 2026.
Status: PASS; geen productiecodewijziging.

## Besluit Seth: beperkte netwerkuitzondering

Seth heeft optie 1 expliciet goedgekeurd: uitsluitend read-only contractinspectie
van officiele PDOK BGT/BAG-bronnen, begrensde live bronfetches van vooraf vastgelegde
officiele endpoints/scopes, lokale raw evidence/hashes/provenance/validatiebewijs
en expliciete live opt-in voor de live proof. Alleen noodzakelijk netwerkverkeer
voor deze bronketen. Geen productiecredentials, cloudwrites, arbitrary URL/netwerk,
andere integraties, niet vooraf toegestane bronnen/endpoints of omzeiling van
capability-, provenance-, K00- of Human Approval-grenzen. AGENTS.md is minimaal
hiermee in overeenstemming gebracht. Deze toestemming hoeft niet per fetch te
worden herhaald. De inhoudelijke BAG-selectie hieronder is een afzonderlijke gate.

## Officiele contractinspectie

Vooraf begrensde metadata-inspectie: HTTPS GET op api.pdok.nl, geen redirects,
15 seconden socket-timeout, maximaal 2 MB per document, 11 vaste metadata/schema-
requests, geen items/featurefetch. Alle 11 requests HTTP 200. Exacte bodybytes en
responsemetadata staan lokaal onder `.tools/2d-contracts/`; het compacte
`milestone-2d-contract-inspection.json` bevat URLs, timestamps, headers en SHA-256.
Webinspectie is alleen orientatie; de directe responses vormen het lokale bewijs.
Dit is contractbewijs, geen live import/promotion/replaybewijs.

- [BGT collections](https://api.pdok.nl/kadaster/bgt/ogc/v1/collections?f=json):
  RD opslag, RD queryondersteuning en JSON-FG; licentielink CC0 1.0.
- [BAG collections](https://api.pdok.nl/kadaster/bag/ogc/v2/collections?f=json):
  RD opslag, RD queryondersteuning en JSON-FG; Public Domain Mark 1.0.

De huidige BGT-metadata verwijst naar `/kadaster/bgt/ogc/v1`; de 2C-code heeft
`/lv/bgt/ogc/v1` hardcoded. 2D moet de exacte huidige route expliciet allowlisten,
zonder redirects of vrije URL-configuratie. Bestaande 2C-archieven moeten hun
oude URL/parser/profiel behouden en offline reproduceerbaar blijven.

## BGT-selectievoorstel vanuit minimale locatiecontext

| Collectie | Waarde en noodzaak | Geometrie / relevante attributen | Overlap en begrenzing |
|---|---|---|---|
| pand | Bestaande bebouwing; behouden uit 2C | MultiPolygon; bag_pnd, lokaal_id, status, version | BGT-topografie; BAG blijft aparte bron |
| wegdeel | Feitelijke verkeersruimte; minimaal | Polygon; functie, fysiek_voorkomen | Geen bereikbaarheid of verkeerskundige conclusie |
| ondersteunendwegdeel | Bermen/verkeersondersteunende vlakken; minimaal naast wegdeel | Polygon; functie, fysiek_voorkomen | Onderscheiden van verkeersfunctie en generiek terrein |
| waterdeel | Feitelijk wateroppervlak; minimaal | Polygon; type | Geen waterveiligheid/beleid of hydrologisch model |
| begroeidterreindeel | Vegetatie/terreinvulling; minimaal | Polygon; fysiek_voorkomen | Geen ecologische waardering of gebruiksrecht |
| onbegroeidterreindeel | Overige terreinvulling; minimaal | Polygon; fysiek_voorkomen | Geen bouwrijpheid, eigendom of ontwikkelpotentie |

Per collectie gelden ook bronhouder, status, registratietijden, in_onderzoek en
relatieve_hoogteligging indien aanwezig. Ontbrekende waarden blijven ontbrekend;
geen status of attribuutwaarde afleiden. Alle originele properties blijven behouden.
Schemas: de zes vaste `/kadaster/bgt/ogc/v1/collections/<bovenstaande-id>/schema?f=json`
URLs zijn afzonderlijk vastgelegd in het inspectiebewijs. Hun geometry formats en
attributen zijn rechtstreeks gecontroleerd; dit voorstel neemt niet alle collecties op.

Nuttig later: ondersteunendwaterdeel, overbruggingsdeel, tunneldeel, spoor,
vegetatieobjecten en scheidingen. Ze voegen objectdetail toe dat buiten deze
minimale contextselectie valt. De geselecteerde lagen bewijzen geen volledige
vlakdekking, maaiveldmodel of afwezigheid van andere BGT-objecten.
Buiten 2D: BRK/eigendom, AHN/hoogtemodel, BRO, luchtfoto, ontwerp en beleidsconclusies.

## Hergebruik van 2C en kleinste voorgenomen uitbreiding

| Onderdeel | Herbruikbaar | Collection-specifieke wijziging die later nodig is |
|---|---|---|
| domain/sources.py; source_store/schema | RawResponse, SourcePage, SourceFeature, GeometryRecord, Snapshot, immutable opslag | Dataset/collectie blijven expliciete provenance; geen tweede archief |
| source_hashing; geometry_validation; source_validation | Structurele hashes, RD-bewijs, geometriecontrole, completeness | Per profiel toegestane geometrietypen; geen gokken/repair |
| adapters/pdok_bgt.py | Captures voor parsing, budgets, retries, paginering, JSON-FG-parser | Gesloten profiel voor metadata-id, dataset, endpoint, geometrytype en namespace |
| adapters/pdok_live.py | Bounded HTTPS GET, geen redirects/credentials | Expliciete eindige endpointlijst, vaste testcasebbox en RD/JSON-FG |
| application/source_import.py | Trusted A02 capability, stage, reparse, transactie, archive-readback, idempotence, revision/binding/stale/audit | Profielgebonden checks/provenance; provider krijgt geen capability |
| application/source_replay.py | Evidence-only reparse, vergelijken, reconstructie naar leeg archief | Vast profiel uit gearchiveerde provenance; geen fetch of nieuwe promotieroute |
| application/live_source_validation.py | Raw/hash/requestchain/originchecks | Nieuwe 2D-profielen naast behoud van exact 2C-profiel |

BGT/BAG-identiteiten en geometry refs krijgen dataset- en collectiecontext zodat
UUIDs of registratienummers niet tussen bronnen botsen. Raw body blijft origineel;
feature-ID en registratienummer zijn verschillende velden. Een later samengesteld
A02-bronbeeld moet alle gebruikte snapshots/revisions refereren; opeenvolgende
losse imports alleen zijn nog geen coherent samengesteld bronbeeld. Dit wordt in
2D-4 via de bestaande revision/stale-mechanismen uitgewerkt, niet via een extra
promotion- of approvalroute.

Voorgenomen live queryscope: uitsluitend de bestaande Mastenbroekweg-testcasebbox
`176492.301,360605.561,176992.301,361105.561`, EPSG:28992, JSON-FG, vaste limit,
begrensde pagina's/bytes/tijd/retries. Geen generieke zoek- of geocodingroute.
Fase 2D-2/3 tests moeten het expliciete schema per collectie, onbekende profielen,
query/next-link scope, lege volledige resultaten, cross-collection identiteiten,
rollback, provenance en offline replay testen. Querycompleteness blijft afzonderlijk
van NOT_GUARANTEED point-in-timeconsistentie.

## BAG: echte productkeuze voor A02

De [pand-schema](https://api.pdok.nl/kadaster/bag/ogc/v2/collections/pand/schema?f=json)
bevat identificatie, bouwjaar, status, aantal_verblijfsobjecten, gebruiksdoel en een
lijst verwijzingen naar verblijfsobjecten; geometrie is Polygon. Dit levert een
compact gebouwbeeld, maar geen individuele VBO-oppervlakten of adrescontext.

De [verblijfsobject-schema](https://api.pdok.nl/kadaster/bag/ogc/v2/collections/verblijfsobject/schema?f=json)
bevat Point, identificatie, gebruiksdoel, oppervlakte, status, adresvelden en
expliciete pandreferenties. Dat maakt context per gebruikseenheid mogelijk, met
meer-op-meer relaties en mogelijk verwijzingen buiten de bbox. Geen live objecten
zijn gelezen; de aantallen/daadwerkelijke relatievormen zijn nog niet vastgesteld.

De [adres-schema](https://api.pdok.nl/kadaster/bag/ogc/v2/collections/adres/schema?f=json)
bevat Point en adresidentiteit met een adresseerbaar-objectverwijzing. Een aparte
adreslaag is voor het voorkeursvoorstel niet nodig: VBO bevat al adresvelden.
Ligplaats, standplaats en woonplaats blijven buiten het minimale voorstel.

### Afgehandelde beslissing: gewenste BAG-inhoud

Protocol paragraaf 4 en de BAG-gate vereisen een beslissing als exacte BAG-inhoud
materieel productgedrag bepaalt. Officiele schemas bepalen wat de data betekenen,
maar niet of downstream A02 alleen gebouwcontext of ook individuele gebruikseenheden
moet leveren. De netwerkuitzondering kiest dat niet.

1. **Pand + verblijfsobject (technisch voorkeursvoorstel).** A02 krijgt bouwjaar/status
   plus individuele gebruiksdoelen, geregistreerde oppervlakten en adrescontext.
   Twee BAG-collecties, expliciete relaties en onopgeloste refs als onzekerheid;
   geen extra adreslaag of adreszoekservice.
2. **Alleen pand.** Kleinste BAG-uitbreiding met gebouwcontext en door de provider
   geleverde pandattributen; geen individuele VBO-oppervlakten/adressen. Downstream
   mag zulke vragen niet als gedekt behandelen.

In beide opties: BAG-geometrie blijft apart van BGT, nooit overschrijven of
synthetisch verzoenen. BGT bag_pnd versus BAG identificatie is alleen een expliciete
identiteitsrelatie bij aantoonbare overeenkomst; geen nearest-neighbour/LLM-match.
Geen eigendomsclaim, generatieve geometrie of uitnuttingsconclusie. Missende of
tegenstrijdige verwijzingen worden zichtbaar als onzekerheid/conflict en geven
geen aanleiding tot onbeperkte follow-up fetches.

Besluit Seth, 29 september 2026: neem zowel pand als verblijfsobject op. Beide
blijven afzonderlijke officiele bronobjecten met eigen identiteit en provenance.
Relaties uitsluitend uit officiele gegevens, nooit synthetisch of door een LLM.
Optie 1 is daarmee vastgesteld; de bovenstaande opties zijn beslisgeschiedenis.
Aanvullend: technische collectiekeuzes die rechtstreeks uit officiele semantiek en
het vastgestelde A02-doel volgen worden zelfstandig gemotiveerd; geen automatische
beslisgate zonder verandering van productgedrag, scope, architectuur, bronautoriteit
of veiligheidsgrenzen.

## Validatie en hervatting

Geen productiecode of tests gewijzigd. De baseline bevat 427 regressietests;
Release 1-projectshell behoort niet tot deze baseline. Volledige regressie: 427/427 PASS, 65.154 s, exitcode 0; log
`.tools/2d-phase1-regression.txt`. Geen nieuwe targeted tests nodig bij uitsluitend
contract/documentatiewijzigingen. `git diff --check` en staged check PASS.
BAG-beslissing ontvangen; broncontract vastgesteld. Hervat automatisch 2D-2.
