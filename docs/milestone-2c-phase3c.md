# Milestone 2C - Fase 3C: failure/security-validatie

## Uitgangspunt en scope

Geaccepteerde Fase 3B: 30c9c86a7818bc996812629195cb151b8ce98c96.
Voor het werk is master naar origin gepusht en is expliciet geverifieerd:
master == origin/master == remote refs/heads/master == deze commit.
De twee uitgesloten untracked items zijn niet geopend of gewijzigd.

Uitsluitend netwerkloze validatie van de bestaande read-only PDOK-pand-adapter.
Geen nieuwe dependencies, live transport, bronimport, SourceImportService,
staging/promotion, EXISTING_VALIDATED-capability, geometry repair, CRS inference,
Human Approval-wijzigingen of Fase 4. Bestaande geometry/CRS-validatie blijft leidend.

## Eerst gereproduceerde bugs en minimale correcties

De nieuwe tests zijn tegen ongewijzigde Fase 3B uitgevoerd. De eerste run
(72 tests) faalde met 1 failure en 5 subtest/errors. De uitgebreide reproducerende
run (98 tests) faalde met 1 failure en 8 subtest/errors. Drie oorzaken:

1. `fetch` controleerde na parsing uitsluitend de totale tijd, niet de kortere
   requestdeadline. Een parser die precies de requestdeadline bereikte kon
   VALIDATING teruggeven. Nu wordt ook na parsing de requestdeadline getoetst.
   Regressies dekken de eerste en een latere pagina, zonder gedeeltelijke bundle.
2. Een door een defecte vertrouwde transportimplementatie ongeldig gemaakte
   HttpResponse met niet-bytes body gooide buiten de foutafhandeling een exception
   tijdens raw hashing. `fetch_page` gooide ook bij een niet-HttpResponse object.
   Beide ingangen toetsen nu het response-/bodytype voor capture. Er worden geen
   bytes geconverteerd of verzonnen: fetch geeft INCOMPLETE, fetch_page geeft
   conform zijn bestaande contract FAILED. Werkelijk ontvangen bytes blijven
   bij ongeldige responsemetadata wel behouden.
3. Cursorwaarden werden als geordende tuple vergeleken. Herschikte dubbele
   cursorparameters plus een gewijzigde overige parameter ontweken deze check.
   Sorteren van de cursorwaarden voor cyclusdetectie sluit dit gat, consistent
   met de bestaande gesorteerde requestidentiteit. De request-URL zelf en
   parameterparen blijven ongewijzigd. De oude situatie was nog steeds begrensd
   door budgetten; dit was geen arbitrary-host-fetch.

Productiediff: uitsluitend adapters/pdok_bgt.py, 7 regels toegevoegd en 4 verwijderd.
Geen stijlrefactor of nieuwe architectuur. De reproducerende tests blijven als
regressietests behouden.

## Nieuwe bewijsmatrix

33 testmethoden in tests/test_pdok_bgt_security.py, met subtests voor varianten.
Alle gebruiken synthetische TESTDATA, SequenceTransport, een fake tijdklok en
fake sleep. Socketconstructie, create_connection en DNS-resolutie worden tijdens
ieder nieuw testgeval geblokkeerd met AssertionError.

- URL-scope: verkeerde scheme/host, host-suffix/trailing dot, userinfo, poorten,
  protocol-relative links, fragments inclusief lege fragmenten, backslashes,
  ASCII-whitespace/controltekens, Unicode, kapotte percentescapes, encoded/dubbel
  encoded paden, slash/backslash/NUL-trucs, dot-segments, andere collectie,
  collectie-endpoint, item-endpoint en relatieve paden bereiken het transport niet.
- Query-only continuations behouden exact de opaque query. Percent-encoded
  padachtige data, controltekens en URL-waarden in querywaarden veranderen nooit
  scheme/host/path; zij worden niet als te volgen URL geinterpreteerd.
- Equivalenties: parameterordering, percent-encoding van namen/waarden, plus
  versus encoded spatie, lege waarden en dubbele queryparen. URL-cycli worden
  gestopt voor een extra transportaanroep. Verschillende duplicate-parameter-
  multisets blijven verschillende requests. Cursor-multisetcycli worden gestopt.
- Pagination: malformed/ontbrekende href, ongeldige links-array, meerdere next-
  links, duplicate features binnen/over pagina's, corrupte of ontbrekende
  vervolgresponse. Eerdere pagina-evidence blijft, features/geometries zijn leeg.
- Exacte eindgrenzen voor pagina's/features/bytes mogen VALIDATING opleveren;
  dezelfde grenzen met pending continuation zijn INCOMPLETE. Featureoverschrijding,
  paginalimit, bodycap en exacte/overschreden tijdgrenzen falen gesloten.
- HTTP: alle 500..599-statussen en 429 hebben begrensde retries en errorcaptures;
  maximaal max_pages * (max_retries + 1) requests. Retry-After test lege/onjuiste/
  dubbele waarden, HTTP-date, minimumbackoff en onvoldoende tijd. Retrybytes
  tellen cumulatief. Redirects en andere onverwachte statussen worden niet gevolgd
  of geretryd. TimeoutError/OSError stoppen direct zonder fictieve response.
- Ongeldige transportobjecten/bodytypes falen gesloten. Ongeldige status,
  headerstructuur en origin behouden beschikbare bytes als evidence.
- Response: malformed JSON, invalid UTF-8, duplicate JSON-keys, non-finite
  getallen, te diepe JSON, verkeerd Content-Type/charset, ontbrekend/verkeerd
  Content-Crs, duplicate relevante headers, unsupported Content-Encoding,
  ongeldige FeatureCollection/features/coordRefSys/numberReturned en een ongeldige
  feature na een geldige feature. Geen gedeeltelijke mapping komt vrij.
- Capture is al aanwezig wanneer de parser wordt aangeroepen. Ook foutbodies
  en een response die het bytebudget overschrijdt worden exact behouden.
- De requestdeadline omvat parsing in fetch en fetch_page. Een parsefailure
  tijdens deadlineoverschrijding blijft eveneens gesloten met capture.

Ontbrekende next-links betekenen uitsluitend pagination_exhausted, ook wanneer
numberMatched groter is dan het ontvangen aantal. Succes blijft VALIDATING,
nooit automatische COMPLETE. Manifest verklaart NOT_GUARANTEED voor point-in-time.

## Grenzen van dit bewijs

Geen live providercompatibiliteit of querycompleteness bewezen. Een stilzwijgend
weggelaten vervolg kan niet uit alleen pagination_exhausted worden uitgesloten.
De collectie is uitsluitend pand. Het bestaande smalle Retry-After-profiel
ondersteunt geen HTTP-date. TimeoutError/OSError worden bewust niet geretryd.

GetTransport blijft een vertrouwd synchroon Python-contract: een werkelijk
transport moet caps tijdens body-read afdwingen en redirects weigeren. De adapter
kan niet-cooperatieve Python-code niet afbreken. Dit is geen sandbox voor
kwaadwillende plugins. Bij een ongeldige niet-bytes body wordt geen raw capture
verzonnen. Exacte URL en GetRequest.parameters bewaren duplicate queryparameters;
bestaande dict-gebaseerde metadata zijn geen verliesvrije queryrepresentatie.

## Verificatie

Targeted commando (projectlokale source-venv, bytecode uit):

```powershell
& ./.tools/source-venv/Scripts/python.exe -B -c "import run_tests, unittest; suite=unittest.defaultTestLoader.discover('tests', pattern='test_pdok_bgt*.py'); result=unittest.TextTestRunner(verbosity=1).run(suite); raise SystemExit(not result.wasSuccessful())"
```

Targeted: 101/101 PASS (68 bestaande Fase 3A/3B + 33 nieuwe Fase 3C), 0.503 s.

Volledige regressie: ./test.ps1, 342/342 PASS, 43.619 s, exitcode 0.
CLI-approvaltests gebruiken uitsluitend hun bestaande projectlokale tijdelijke
opslag. De echte runtime/GIS-001 is niet aangeraakt of goedgekeurd.
Git diff --check: PASS; nieuwe bestanden ook afzonderlijk op witruimte getoetst.

Reviewbranch: milestone-2c-phase3c-review, vanaf de hierboven geverifieerde master.
Uitsluitend drie Fase 3C-bestanden: adaptercorrectie, nieuwe securitytests en dit
rapport. Geen merge of verdere masterwijziging; stop na Fase 3C.
