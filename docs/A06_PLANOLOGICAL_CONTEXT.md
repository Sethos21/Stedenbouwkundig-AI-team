# A06 Planological Context V1

Lokale, deterministische TESTDATA-service: `PlanologicalContextService(store)` in
`src/bvc_ai/application/planological_context.py`. Geen connectors, LLM, CLI-commando,
workflowactivatie, nieuwe geometrieën, opslagmutaties of Human Approval. A03–A05
blijven onaangeroerd. A06 schrijft geen agentrevisie of taakstatus; daarom ontstaan
hier geen nieuwe statusovergangen. Validatiefouten blokkeren met een exception.

## Contract en gebruik

De vertrouwde lokale aanroeper gebruikt:

```python
service = PlanologicalContextService(store)
result = service.build(a02_context, fixture_input, expected_input_hash=pinned_hash)
service.verify(result, current_a02_context, current_fixture_input,
               expected_input_hash=current_pinned_hash)
```

Downstream agents ontvangen uitsluitend JSON. De aanroeper beheert de actuele
fixture-revisie en de onafhankelijk vastgelegde hash; een hash uit onbeheerde
provider-output is geen vertrouwde pin. Hashes bewijzen integriteit, geen
authenticiteit of juridische geldigheid. Verificatie vereist de huidige input,
niet alleen de zelfbeschrijving van een oud resultaat.

De uitvoer heeft format `BVC_A06_PLANOLOGICAL_CONTEXT_V1` en altijd bronstatus
`TESTDATA`. De zes onderscheiden onderdelen zijn:

- **SOURCE:** `sources[]` met bronidentiteit, versie, TESTDATA-status, gesimuleerde
  juridische status EFFECTIVE/DRAFT/UNKNOWN en bronhash.
- **RULE:** `rules[].rule_identity` is het unieke paar bron-ID/regel-ID.
  `source_rule` bewaart de volledige oorspronkelijke regel, locator, letterlijke
  tekst, gestructureerde betekenis, eventuele hoeveelheid en onzekerheden.
- **APPLICABILITY:** `applicability` bewaart status, letterlijke toepasselijkheidsbasis
  en exact doelbereik. De oorspronkelijke toepasselijkheid blijft ook in de bronregel.
- **INTERPRETATION:** afzonderlijke, vaste machineleesbare betekenis, onderwerp,
  methodeversie en pad naar provenance. Geen herschreven juridische broninhoud.
- **CLASSIFICATION:** uitsluitend CONSTRAINT, STEERING, INFORMATION of UNCERTAINTY,
  met een afzonderlijk provenance-pad.
- **UNCERTAINTY:** reden-codes en oorspronkelijke onzekerheidsteksten; nooit
  aangevulde ontbrekende juridische betekenis.

Het invoerformat is `BVC_A06_FIXTURE_INPUT_V1`, met TESTDATA-status, `input_revision`,
`a02_context_hash` en expliciete bronnen/regels. Uitvoerclassificaties worden
niet als input geaccepteerd. Het volledige compacte voorbeeld staat in
`tests/planological_fixtures.py`; dit bindt synthetische regels aan bestaande
referenties uit een gevalideerde A02-context.

De gecontroleerde fixture levert zowel letterlijke tekst als gestructureerde
betekenis: BINDING, POLICY_AMBITION, NEUTRAL_INFORMATION of UNKNOWN, onderwerp,
EXPLICIT/UNCLEAR en brononzekerheden. V1 interpreteert geen vrije juridische tekst
en controleert de juridische equivalentie van tekst en structuur niet automatisch.
Die consistentie is een verantwoordelijkheid bij de review van de fixture.
Onbekende schema-elementen en ongeldige referenties worden afgewezen.

## Toepasselijkheid

Status: APPLIES, DOES_NOT_APPLY of UNKNOWN, onafhankelijk van het doelbereik:

- FULL_ANALYSIS_SCOPE: exact alle bestaande A02-scopecontracten.
- A02_GEOMETRY: één of meer bestaande A02-geometriereferenties voor een deelgebied.
- SOURCE_OBJECT: één of meer volledige A02-recordreferenties
  `[source_contract, snapshot_id, source_id]`.

Iedere variant gebruikt uitsluitend zijn eigen referentievelden. Lege, gemengde,
onbekende of dubbele referenties falen gesloten. De provenance verwijst naar de
bijbehorende A02-provenance-indexen, met daarin de bestaande geometriehashes.
Er worden geen geometrieën gemaakt, geclipt, gecombineerd of geometrische relaties
afgeleid. Een zelfstandig juridisch werkingsgebied buiten de bestaande
A02-geometrieën wordt in V1 niet ondersteund. De volledige analysescope is geen
juridische of projectgrens. De status en basis komen uitsluitend uit testdata.

Alleen BINDING + EFFECTIVE + EXPLICIT + APPLIES + niet-lege basis + geen
onzekerheden levert CONSTRAINT. Een indicatieve hoeveelheid levert evenmin een
harde constraint. Beleidsambities leveren STEERING, neutrale relevante informatie
INFORMATION. Onbekende bronstatus/betekenis, onduidelijkheid, ontbrekende basis,
niet-geldende bindende regels en brononzekerheden leveren UNCERTAINTY.
DOES_NOT_APPLY blijft als expliciete status bewaard, met UNCERTAINTY en reden
APPLICABILITY_DOES_NOT_APPLY; downstream mag dit niet als toepasselijke beperking
gebruiken. Dit houdt de gevraagde vier classificaties aan.

`quantity` is optioneel (anders null): letterlijke numerieke `value`, `unit` en
operator MAXIMUM/MINIMUM/EQUALS/INDICATIVE, zonder conversie. De bronwaarde blijft
ook bij onzekerheid bewaard en is op zichzelf geen geldende eis.

## Integriteit en validatie

SHA-256 over canonieke JSON (gesorteerde keys, UTF-8, compacte separators, geen
NaN/Infinity) bindt de volledige input, iedere bron, regel en toepasselijkheidsbasis.
De uitvoer bindt A02-context-, basis- en revisiehash/identiteit en de inputrevisie.
`context_hash` dekt alle output behalve zichzelf. Lijstvolgorde is onderdeel van
de input: dezelfde input geeft dezelfde output, zonder tijdstempels of randomness.

A02 wordt vóór en na afleiding opnieuw opgebouwd en geverifieerd via de bestaande
SpatialContextService. Wijzigingen, stale revisies en verkeerde A02-inputbindingen
falen gesloten. A06-verificatie reconstrueert de output uit de actuele vertrouwde
input en vergelijkt canonieke hashes, ook als een gewijzigde output opnieuw is
gehasht. A02, K00, bronrecords, audit en menselijke beslissingen blijven ongewijzigd.

`tests/test_planological_context.py` gebruikt synthetische BAG/BGT-responses via de
bestaande testhelpers; ook die zijn geen echte broncaptures. Netwerk is geblokkeerd.
Tests bewijzen alle classificaties, toepasselijkheidsvarianten, bronbehoud,
determinisme, read-only gedrag, stale/tamper-afwijzing, ontbrekende basis,
dubbele identiteiten, schemafouten en een A02-revisiewijziging tijdens afleiding.
Volledige regressie: `./test.ps1`.
