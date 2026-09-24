# Milestone 2C - Fase 3B: robuust ophalen

Uitgangspunt: master, 26990f0ca5cb91d421f445bb1e96587ecc419f8c.
Preflight: HEAD en branch conform opdracht; alleen de vooraf bestaande,
uitgesloten map Stedenbouwkundig-AI-team/ was untracked. Deze is niet gelezen,
gewijzigd of toegevoegd. Geen live PDOK-verkeer of nieuwe dependencies.

## Implementatie

PDOKBGTAdapter.fetch gebruikt dezelfde GetTransport, CapturedResponse, parser,
SourcePage/SourceFeature/GeometryRecord en bestaande geometry/CRS/hashcontroles
als Fase 3A. Geen parallelle importarchitectuur of SourceSnapshot-publicatie.
fetch_page blijft beschikbaar met een request-timeout en response-bytecap.

FetchBudgets defaults: 100 pagina's, 100.000 features, 64 MiB responsebodies,
120 seconden totale tijd, 15 seconden per request, maximaal twee retries per
pagina met exponentiele wachttijd vanaf 0,25 seconde. Configuratie vereist
positieve eindige waarden; retries zijn configureerbaar van 0 tot 10.
De totale bovengrens aan requests is max_pages * (max_retries + 1).
Alle ontvangen responsebodies tellen mee, inclusief HTTP-foutresponses.
De laatste pagina mag exact het pagina-, feature- of bytebudget benutten.
Een onopgeloste continuation op een uitgeput budget faalt gesloten.

De monotone tijdklok en slaapfunctie zijn injecteerbaar. Request-timeout is
het minimum van de ingestelde timeout en resterende totale tijd. Deadlinechecks
vinden plaats voor requests en na ontvangst, parsing en mapping. GetTransport
moet timeout en bytecap al tijdens de volledige request/body-read afdwingen;
de adapter controleert ook achteraf. Een niet-cooperatieve Python-implementatie
kan niet door deze synchrone contractgrens worden afgebroken. Er is geen live
transport toegevoegd. Bij een exception zonder response wordt geen raw body
verzonnen; alle daadwerkelijk geretourneerde HttpResponses blijven bewaard.

## Continuation en veiligheid

Vervolglinks zijn onbetrouwbare input. Alleen query-relatieve links en absolute
HTTPS-links naar exact api.pdok.nl/lv/bgt/ogc/v1/collections/pand/items worden
geaccepteerd. Andere hosts, userinfo, poorten, protocollen, paden, fragments,
backslashes, whitespace/controltekens en malformed percent-escapes worden
geweigerd. Geen redirects, metadatafetch of arbitrary-URL API.
Andere relatieve padvormen worden bewust conservatief geweigerd.
De originele opaque query wordt niet herschreven of opnieuw geencodeerd.

Cycle detection vergelijkt endpoint plus gedecodeerde/gesorteerde queryparen;
herhaalde cursorwaarden worden ook bij gewijzigde overige parameters geweigerd.
Andere opaque parameterprofielen worden via requestidentiteit en de eindige
budgetten begrensd. Dubbele feature-ID's over pagina's falen eveneens gesloten.

HTTP 429 en 5xx worden begrensd opnieuw geprobeerd. Retry-After in gehele
seconden wordt gerespecteerd als minimumwachttijd; ongeldige/dubbele waarden en
HTTP-date-vormen falen gesloten in dit beperkte profiel. Een wachttijd die niet
binnen het tijdsbudget past, stopt direct. Andere HTTP-statussen, transportfouten
en timeouts stoppen zonder retry. Retry exhaustion blijft INCOMPLETE.

## Bewijs en fasegrens

Iedere ontvangen body wordt voor parsing exact vastgelegd met de bestaande
raw-responsehash, request, status, headers, origin en retrievaltijden.
FetchResult bewaart captures en controleerbare pagina-/pogingmetadata, inclusief
retryvolgnummer, originele inkomende/uitgaande continuation, resolved next-URL,
requestlimieten, ontvangen bytes, hashes, paginametadata en foutreden.
SourcePage.next_url wordt absoluut gemaakt zodat de bestaande completeness-
validator de keten kan vergelijken met de volgende request_url; de originele
providerlink blijft in capture, manifest en provenance behouden. Paginanummers
van pagina's en features lopen door. SourcePage.cursor blijft None omdat er
geen universeel provider-tokenveld wordt verzonnen.

numberReturned wordt, indien aanwezig, door de bestaande parser exact getoetst
aan de ontvangen features. Afwezig blijft onbekend. Een ontbrekende next-link
na een geldige pagina betekent uitsluitend pagination_exhausted. De adapter
kan een door de provider stilzwijgend weggelaten link niet zelfstandig bewijzen.

Succes blijft VALIDATING, nooit COMPLETE; pagination_exhausted is transportbewijs,
geen gevalideerde querycompleteness of point-in-time-garantie. De bestaande
archive-completenessvalidator blijft verplicht bij een toekomstige vertrouwde
import; er wordt hier geen importservice gebouwd om die stap te simuleren.
Bij iedere afgebroken fetch: INCOMPLETE, pagination_exhausted=false en expliciete
failure_reason. Raw captures en pagina-evidence blijven beschikbaar, maar geen
partiele feature-/geometrybundle wordt als bruikbaar resultaat teruggegeven.
TESTDATA-provenance blijft behouden. Human Approval, K00 en immutable storage
zijn niet aangepast; geen promotion, Fase 3C of Fase 4.

## Tests

Nieuw: tests/test_pdok_bgt_fetch.py, 34 netwerkloze tests met synthetische
TESTDATA, fake transport en fake klok. Dekking: meerdere pagina's, opaque links,
verboden links, URL-/cursorcycli, alle budgetten en exacte grenzen, cumulatieve
bytes inclusief retries, timeouts, mappingdeadline, 429/5xx/retry exhaustion,
Retry-After, incomplete vervolgpaginering, count mismatch, dubbele feature-ID's,
raw capture, lege tussenpagina's en nooit COMPLETE bij afbreken.

Targeted: 68/68 PASS (34 bestaande Fase 3A + 34 nieuwe Fase 3B).
Command: lokale source-venv Python -B, import run_tests voor dezelfde src-path,
unittest discovery in tests met pattern test_pdok_bgt*.py.

Volledige regressie: test.ps1, 309/309 PASS (42,488 s), exitcode 0.
Git diff --check: PASS. Nieuwe bestanden afzonderlijk op trailing whitespace gecontroleerd.
Geen commit, push of merge uitgevoerd. Stop na Fase 3B.
