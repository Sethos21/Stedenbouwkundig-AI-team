# Milestone 2D-3 - BAG pand en verblijfsobject

Besluit Seth: beide collecties voor officiele gebouwcontext en individuele
gebruiksdoelen/oppervlakten/adressen; afzonderlijke bronobjecten met eigen identiteit
zoals vastgelegd in fase 2D-1. Geen synthetische samenvoeging of door LLM afgeleide
relaties. Geen aparte adreslaag of BRK.

Gesloten BAG/pand en BAG/verblijfsobject profielen gebruiken uitsluitend
https://api.pdok.nl/kadaster/bag/ogc/v2/collections/pand/items respectievelijk
https://api.pdok.nl/kadaster/bag/ogc/v2/collections/verblijfsobject/items.
De bestaande keten verwerkt beide ongewijzigd: geen BAG-specifieke fetch/import-
architectuur. Polygon versus Point wordt expliciet gecheckt. BAG identificatie is
verplicht naast het ongewijzigde provider feature-ID. Pand/VBO-referentielijsten
blijven exact in properties; schema-/integerchecks bewaken kernattributen.

BAG/BGT gebruiken verschillende namespaces; gelijke feature-IDs overschrijven geen
geometrie. De dataset/collectie en raw evidence blijven in provenance. Objectrelaties
worden alleen uit de officiele arrays gelezen; er wordt niets gevolgd of geraden.
2D-4 maakt deze geregistreerde verwijzingen leesbaar en toont niet opgeloste of
conflicterende relaties expliciet. Geen aanspraak op volledigheid buiten de bbox.

Gereproduceerde testfout: de nieuwe BAG integercheck wees ook correcte getallen af,
omdat de bestaande strict_json parser Decimal gebruikt. Kleinste fix accepteert
gehele Decimal-waarden zonder afronden; tests weigeren boolean, negatief en fractie.
De bestaande verliesvrije parser en raw evidence zijn niet gewijzigd.

Targeted BAG+BGT: 14/14 PASS, 4.376 s. Testgevallen: beide collecties, intacte
properties/identiteit, replay en reconstructie, BAG/BGT-scheiding, typefouten,
endpoint-/next-grenzen, lege collecties en idempotence. Alleen synthetische evidence,
socket/DNS geblokkeerd. Geen featurefetch in deze fase.

Volledige test.ps1 regressie: 441/441 PASS, 63.629 s, exitcode 0.
Log: .tools/2d-phase3-regression.txt. git diff --check PASS. Fase 2D-3: PASS.
