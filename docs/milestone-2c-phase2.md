# Milestone 2C — Fase 2: offline geometry/CRS/hash/completeness

Baseline en onveranderde HEAD: `master` /
`64ce34029dce15a1f05ee0cb9c4eedac08a593c4`.
Preflight: branch/HEAD correct, worktree clean; Fase-1-contracten, SQLite-schema,
source store en bestaande tests gelezen. Opdrachtgever heeft uitsluitend Fase 2
vrijgegeven. Geen commit, push, live GIS-verzoek, promotie of start Fase 3.

Specificatie:
[11 — Codex implementatiepakket MINIMAL_PROOF v0.1](https://docs.google.com/document/d/1-p-U6_AfoTq7qEZE2TWPWFOE18Ccew9F-jVbbCiKnWs/edit).
De expliciete Fase-2-opdracht bepaalt de actuele baseline en de beperktere scope.

## Dependencies en reproduceerbare lokale installatie

`requirements.txt` pint exact Shapely==2.1.2 en numpy==2.2.6.
`scripts/install_source_dependencies.ps1` gebruikt de bestaande projectlokale
CPython 3.12.14 in `.tools/python` om `.tools/source-venv` te maken.
De basisinterpreter is uv-managed (PEP 668); hij wordt niet aangepast.
Installatie gebruikt uitsluitend binary wheels, geen broncompilatie,
geen user-installatie, geen globale packages. Cache en tijdelijke bestanden
staan onder `.tools/pip-cache` en `.tools/install-temp`; oorspronkelijke TEMP/TMP
worden hersteld. Venv en packages vallen onder bestaande .gitignore.

Uitgevoerde installatie/import:

| Onderdeel | Waargenomen |
|---|---|
| Python | CPython 3.12.14, MSC v.1944, 64 bit |
| Platform | Windows Server 2022 / AMD64 |
| Wheel Shapely | shapely-2.1.2-cp312-cp312-win_amd64.whl |
| Wheel NumPy | numpy-2.2.6-cp312-cp312-win_amd64.whl |
| Shapely import | 2.1.2 |
| GEOS runtime | 3.13.1 |
| NumPy import | 2.2.6 |
| pip check | No broken requirements found |

Beide imports kwamen uit de projectlokale venv. GEOS komt mee met de Shapely-wheel,
niet uit een systeeminstallatie. De
[Shapely-installatiedocumentatie](https://shapely.readthedocs.io/en/2.1.2/installation.html)
beschrijft de meegeleverde GEOS-bibliotheek; hier is compatibiliteit ook werkelijk
bewezen door imports en topologietests. Geen pyproj geïnstalleerd of gebruikt.

Herhalen vanuit de projectmap:

```powershell
.\scripts\install_source_dependencies.ps1
.\test.ps1
```

`test.ps1` en `bvc-ai.ps1` verkiezen dezelfde projectlokale venv wanneer aanwezig;
de bestaande interpreter blijft fallback voor de legacy CLI. De volledige suite
vereist nu de geïnstalleerde Fase-2 dependencies. Er vindt geen automatische
download plaats bij een test- of CLI-run. Geen nieuwe CLI-functionaliteit.

## Geometryvalidatie

`domain/geometry_validation.py` biedt `validate_geometry`,
`validate_crs` en `validate_geometry_record`. Ondersteund:
Point, LineString, Polygon, MultiPolygon, inclusief holes.

Voor GEOS: object met uitsluitend type/coordinates; bekende typeaanduiding;
niet-null, niet-empty, exacte nesting; twee finite numerieke coördinaten per
positie (geen boolean/string/null); minimaal twee LineString-posities;
minimaal één polygonring; minstens vier ringposities met drie verschillende
vertices en een al gesloten ring. MultiPolygon bevat minstens één polygon.
Dubbele JSON-keys en NaN/Infinity zijn verboden. Overflow/underflow bij conversie
naar GEOS binary64 wordt geweigerd.

Vervolgens controleert Shapely/GEOS de echte geometrie met
[is_valid](https://shapely.readthedocs.io/en/2.1.2/reference/shapely.is_valid.html)
en is_empty. Dit detecteert onder andere self-intersections, holes buiten of
door de shell, overlappende holes en ongeldige MultiPolygon-overlap.
Fouten geven ValueError; geen buffer(0), make_valid, ringclosure-reparatie,
simplificatie, clipping, normalisatie of transformatie. Het originele
GeometryRecord en de bron-JSON blijven byte-ongewijzigd. Recordvalidatie verifieert
ook canonicalization_version en geometry_structural_hash.

De topologie-engine rekent met binary64; dit is geen exact-rationale
topologiegarantie voor willekeurige precisie. Hashing bewaart daarentegen de
exacte decimale JSON-getallen. GEOS-engineversie staat in het immutable
GeometryValidation-resultaat.

## CRS-contract en grenzen van bewijs

Canonical CRS: EPSG:28992 / Amersfoort RD New. Verplicht:

- expliciet CRS met niet-lege evidence;
- axis_order exact (`easting`, `northing`);
- units exact `metres`;
- dimension integer 2.

Normaliseerbare identificaties: EPSG:28992 (hoofdletterongevoelig), de expliciete
OGC URN `urn:ogc:def:crs:EPSG::28992` en HTTP/HTTPS
`www.opengis.net/def/crs/EPSG/0/28992`. De opgeslagen metadata worden niet herschreven.
Onbekende/andere CRS, waaronder EPSG:4326 en CRS84, falen validatie gesloten.
Hashing kan een expliciet ander CRS wel fingerprinten; een hash verleent geen
validiteit. Er bestaat geen transformatiepipeline.

Snapshot request/response/fetch-CRS, elke pagina en geometrie moeten native RD
declareren. Een aanwezige Content-Crs header mag dit niet tegenspreken.
`validate_geometry_record(..., source_crs=...)` detecteert een fout RD-label
wanneer de afzonderlijk meegegeven responsedeclaratie WGS84/CRS84 vermeldt.

Omgekeerde asmetadata en dimensie-/eenhedenconflicten zijn structureel aantoonbaar.
Een verkeerde numerieke x/y-volgorde of een vals RD-label bij verder onderling
consistente metadata is NIET betrouwbaar uit coördinaatgetallen alleen af te
leiden. Kleine getallen kunnen RD-coördinaten zijn; RD-achtige getallen bewijzen
RD evenmin. Tests leggen deze grens expliciet vast. Herkomst en waarheidsgehalte
van CRS-evidence moeten later door de vertrouwde adapter worden vastgesteld.
Er worden geen coordinate ranges gebruikt voor CRS guessing.

## Canonicalisatie en hashes

`domain/source_hashing.py` definieert
`CANONICALIZATION_VERSION = bvc-source-structural-v1`.
SHA-256 geeft steeds 64 lowercase hextekens.

Canonieke bytes zijn UTF-8 JSON met compacte separators, zonder BOM,
ensure_ascii=False en objectkeys gesorteerd op Unicode-codepoint.
De JSON wordt eerst naar een expliciete typeboom vertaald:

| Waarde | Typeboom |
|---|---|
| null | `["null"]` |
| boolean | `["bool",true/false]` |
| string | `["string","tekst"]` |
| getal | `["number","coefficient e exponent"]` zonder spaties |
| array/tuple | `["array",[getypeerde waarden in oorspronkelijke volgorde]]` |
| object | `["object",[[key,getypeerde waarde],...]]`, gesorteerd op key |

JSON-getallen worden met Decimal gelezen, zonder binary64-rounding voor de hash.
Trailing coefficient-zeroes worden in de exponent opgenomen; 1, 1.0 en 1e0
worden `1e0`; 1.20 wordt `12e-1`; +0/-0 worden `0`.
Geen Decimal-contextafronding. Directe Python-floats gebruiken hun
reproduceerbare Python-3.12 str-weergave; exacte brongetallen komen via JSON.
Strings worden niet Unicode-genormaliseerd. Arrays, coordinates, ringstart,
oriëntatie, nesting en multipartvolgorde blijven behouden. Numerieke schrijfwijze
normaliseren is onderdeel van identiteit en verandert geen opgeslagen bronbytes.

- `raw_response_hash`: SHA-256 van de exacte bytes, zonder decoding/normalisatie.
- `geometry_structural_hash`: canonieke type/coordinates, expliciet genormaliseerde
  CRS-identificatie, axis_order, dimension, units en canonicalization_version.
  Geometry_ref, provenance/evidence en run timestamps zijn geen geometrische
  identiteit. Geen topologische equivalentieclaim: ringrotatie/andere volgorde
  kan een andere hash geven.
- `snapshot_manifest_hash`: provider/dataset/collection/endpoint,
  bbox/fetch-CRS/analysis-geometry-identiteit, request/response-CRS,
  queryparameters, temporal_query, gedeclareerde aantallen, parser/validatorversie,
  consistency/evidence en provenance; pagina's op paginanummer met request,
  raw hash, status, media type, next/cursor en relevante headers; features
  op source_id met bronversie, paginareferentie, properties/provenance en
  geometry-identiteit. Relevante headers: Content-Type, Content-Crs,
  ETag en Last-Modified (case-insensitive; duplicaten verboden).

Retrieval start/eind, page retrieved_at, HTTP Date en snapshot_id zijn
runmetadata en vallen buiten manifestidentiteit. Geometry_ref is een
lokale verwijzing die in het manifest wordt vervangen door inhoudelijke
geometry-identiteit. Parser/validator/canonicalisatieversies en provenance
zijn wel inhoudelijk bewijs. Willekeurige timestampvelden in bronproperties
of provenance worden niet verwijderd: die kunnen broninhoud zijn.
Raw-responsebytes worden nooit aangepast; een timestamp in die bytes
verandert dus terecht de raw hash en daarmee het manifest.
Bij nieuwe hashregels is een nieuwe canonicalization_version vereist.

Hashberekening is geen validatie of promotie. De validator vergelijkt de
opgeslagen hashes met opnieuw berekende waarden.

## Completenesscontract

`domain/source_validation.py::validate_completeness` accepteert een exacte
offline bundel van bestaande SourceSnapshot/SourcePage/SourceFeature/
GeometryRecord/RawResponse-contracten. Resultaat is een frozen
CompletenessValidation; fouten geven ValueError. De functie wijzigt geen
status, opslag, audit, revisie of human decision.

Positief QUERY_SCOPE_COMPLETE-bewijs vereist:

1. geldige contracten, verplichte provenance, actuele validator-/canonicalisatieversie;
2. geen FAILED/INCOMPLETE snapshot of expliciete failure_markers;
3. minimaal één succesvolle pagina, ook bij nul features; alle gedeclareerde
   paginanummers 1..page_count exact éénmaal en feature_count passend;
4. correcte snapshot-, feature/page-, feature/geometry- en scopeverwijzingen,
   zonder dubbele identities of ongebruikte records in de bundel;
5. aanwezige raw responses met juiste bytes/hash;
6. aaneengesloten next-/cursorketen zonder onopgeloste voortzetting of cyclus;
7. native RD voor queryscope, pagina's en geometrieën; technisch geldige geometrie;
8. overeenkomende structurele geometry- en snapshotmanifesthashes.

Voor deze validatie betekent SourcePage.cursor een **uitgaande** cursor:
die moet exact overeenkomen met de volgende pagina's
request_parameters_json["cursor"]. Een next_url moet exact de volgende
request_url zijn. Wanneer beide aanwezig zijn, moeten beide oplossen.
De laatste pagina heeft beide op None. Lege strings zijn geen terminatiebewijs.
De functie doet geen netwerkverzoek, URL-resolutie of paginationtransport.

Een positief resultaat maakt de snapshot niet automatisch COMPLETE.
Fase 4 moet dit bewijs opnieuw verkrijgen binnen de vertrouwde publicatieroute.
De Fase-1 source store blijft een intern archief: een daar opgeslagen
COMPLETE-declaratie is op zichzelf geen validatiebewijs of EXISTING_VALIDATED.

POINT_IN_TIME_CONSISTENCY wordt onafhankelijk en ongewijzigd doorgegeven:
UNKNOWN, NOT_GUARANTEED of PROVIDER_GUARANTEED met evidence.
UNKNOWN is een additieve enumwaarde; geen SQL-migratie of herschrijving van
oude records. QUERY_SCOPE_COMPLETE promoveert UNKNOWN/NOT_GUARANTEED nooit
naar een garantie. Voor de latere PDOK BGT-proof is geen harde point-in-time
garantie vastgesteld.

## Vertrouwensgrens en resterend werk

Deze provideronafhankelijke validator controleert een **al geparste** bundel
tegen gedeclareerde counts, refs en continuations. Hij interpreteert geen
provider-specifieke raw payloads. Een toekomstige vertrouwde parser/adapter
moet counts, featuremembership per pagina, CRS-evidence, scope en alle failure/
incomplete markers volledig en correct uit raw responses afleiden.
De huidige tests bewijzen contractconsistentie en raw-integriteit, geen
authenticiteit van synthetische brondata of volledige mapping vanaf PDOK.

Geen willekeurige Python-plugin-sandbox; dezelfde vertrouwde Python-grens als
Fase 1. Geen page/byte/time-budget of transportbeleid toegevoegd; dat hoort bij
Fase 3. De validator houdt de volledige kleine bundel in geheugen.
Geen replay-engine, SourceImportService, A02 revision/stale-integratie,
ProjectGeometry-constructie, URBAN_BASE of andere databronnen.
De echte Mastenbroekweg-BBOX en BGT pand-proof zijn niet gebruikt.
Alle nieuwe fixtures zijn inline synthetische TESTDATA zonder locatieclaim.

K00Policy, HumanApprovalService/capability, reviewownership,
check_design_approval, iteratielimiet, stale/revisionsemantiek,
bestaande TESTDATA-fixtures, SQLite source schema/store en historische runtime
zijn ongewijzigd. Validators hebben geen Store, provider-/approvaltool of
EXISTING_VALIDATED-publicatiemethode.

## Verificatie

De onderstaande resultaten gelden voor de opgeleverde code.

## Uitgevoerde resultaten (2026-09-17)

| Controle | Resultaat |
|---|---|
| Fase 2 afzonderlijk | 102/102 OK, 0.087 s |
| Fase 1 afzonderlijk | 25/25 OK, 1.669 s |
| Volledige test.ps1 | 241/241 OK, 46.794 s, exitcode 0 |
| Bestaande regressie | Alle 139 baseline-tests behouden en groen |
| Nieuwe tests | 32 geometry + 13 CRS + 14 hashing + 43 completeness |
| Dependencycontrole | Imports geslaagd; pip check geslaagd |
| git diff --check | Geslaagd |
| Witruimte nieuwe bestanden | Geen trailing whitespace of extra lege eindregels |
| Branch/HEAD na implementatie | master / 64ce34029dce15a1f05ee0cb9c4eedac08a593c4 |
| Commit/push | Niet uitgevoerd |
| Fase 3 | Niet gestart |

Afzonderlijke unittest-discovery gebruikt de venv-interpreter en zet src vóór
de projectroot in sys.path, conform run_tests.py. Alle tests zijn offline.
De fixtures zijn synthetisch; er is geen officiële bronvalidatie geclaimd.
SQLite-/CLI-tests gebruiken uitsluitend hun bestaande geïsoleerde tijdelijke
opslag onder .tools/test-runs.

Gewijzigd: README.md, bvc-ai.ps1, test.ps1 en domain/sources.py
(alleen de additieve UNKNOWN-consistencywaarde).
Nieuw: requirements.txt, scripts/install_source_dependencies.ps1,
domain/geometry_validation.py, domain/source_hashing.py,
domain/source_validation.py, tests/test_source_validation.py en dit document.

Git diff --stat voor bestaande bestanden: 4 files changed,
12 insertions(+), 5 deletions(-). De zeven nieuwe bestanden zijn bewust
untracked en staan daarom nog niet in die standaard diffstat.
Geen bestanden gestaged. Geen overige projectbestanden gewijzigd.

Oordeel voor Fase 3: **GO WITH CONDITIONS**.
Fase 2 is technisch afgerond. Fase 3 vereist expliciete beoordeling/GO van de
opdrachtgever; de toekomstige adapter moet de hier beschreven cursorsemantiek,
raw-naar-featuremapping, verwachte aantallen, CRS-herkomst en failure markers
betrouwbaar leveren. Dit oordeel accepteert geen live proof, bronpromotie,
datasetconsistentie of Fase-4-integratie. De bestaande invarianten hoeven
hiervoor niet te worden afgezwakt.
