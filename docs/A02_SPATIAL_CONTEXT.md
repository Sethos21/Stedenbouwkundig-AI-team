# A02 feitelijke ruimtelijke basissituatie

`python bvc_ai.py --data <projectlokale-archiefmap> spatial-context <task-id> --revision <A02/vN>`

De vertrouwde lokale `SpatialContextService.build()` retourneert dezelfde JSON als
`BVC_A02_SPATIAL_CONTEXT_V1`. Volgende agents ontvangen alleen deze data, geen
Store, service of capability. Er worden geen agents geactiveerd en geen
bronobjecten, K00, revisies of menselijke beslissingen gewijzigd.

- `basis_hash` en `revision_id` binden het resultaat aan de actuele, volledig
  gevalideerde source basis. `context_hash` is SHA-256 van canonical JSON zonder
  dat hashveld (gesorteerde keys, UTF-8, compacte separators).
- `categories` indexeert bronobjectreferenties in zes categorieën. Een referentie
  is `[source_contract, snapshot_id, source_id]`. BAG- en BGT-panden zijn aparte
  bronregistraties; objectaantallen zijn geen aantallen unieke gebouwen.
- `objects[].facts` bevat categorie, geometriesoort, RD-bounds, puntpositie of
  planaire oppervlakte van de volledige brongeometrie (met aftrek van gaten),
  en aanwezige letterlijke kenmerken uit een vaste allowlist. Elk feit noemt
  methode en `provenance_ref`, een index in `provenance`. Letterlijke kenmerken
  behouden hun oorspronkelijke veldnaam en waarde; ontbrekende/null kenmerken
  worden niet ingevuld. BAG-oppervlakte is een bronattribuut, geen berekende
  geometrieoppervlakte. Bounds zijn getallen, geen nieuwe brongeometrie.
- `provenance` bevat record-, geometrie-, importrevisie-, raw-response- en
  manifestverwijzingen, geometriehash, bronstatus en expliciete CRS-metadata.
- `relations` en `uncertainties` behouden de source-basisinhoud en krijgen
  `provenance_refs` naar de betrokken bronobjecten. Onopgeloste, ambigue en
  ontbrekende relaties blijven staan; ruimtelijke nabijheid maakt geen relatie.
- `scope` bewaart de technische fetch-bbox per bron. Deze is geen projectgrens.
  Geometrieën worden niet geclipt of samengevoegd. De categorie
  wegen/verharding bewijst geen verharding; het eventuele bronkenmerk blijft
  leidend. Compleet betekent dat alle acht broncollecties aanwezig zijn, niet
  dat de fysieke wereld volledig of op één tijdstip is geregistreerd.

`verify(context)` verwerpt gewijzigde output of een verouderde A02-revisie.
Een nieuwe bronimport vereist een nieuwe afleiding. De afleiding is deterministisch
binnen de bestaande geometrie-runtime en doet geen netwerkcalls of LLM-calls.

De offline praktijktest leest het geaccepteerde Meppel BAG API-bootstraparchief,
controleert pakket- en bestandshashes, reconstrueert de gevalideerde source basis
in geïsoleerde projectlokale opslag en controleert dat het databasebestand,
bronobjecten, audit en taakstatus ongewijzigd blijven. De echte broncaptures
blijven onderscheiden van de TESTDATA-taakcontext. Uitvoeren: `./test.ps1`.

## Deterministische feitelijke samenvatting

`summary` is onderdeel van de bestaande `context_hash` en bindt ook expliciet
`basis_hash` en `revision_id`. De afleiding leest uitsluitend de bestaande
A02-feiten. `by_collection` geeft per broncollectie het aantal bronrecords,
het aantal polygonale oppervlaktefeiten en hun rekenkundige som in m2.
Zonder polygonale feiten is de som `null`. Dit is geen geometrische union,
gebiedsdekking of unieke gebouwoppervlakte; overlap kan aanwezig zijn.
`by_category.collection_record_counts` rapporteert aantallen uitgesplitst naar
broncollectie. BAG- en BGT-panden krijgen nergens een gecombineerd totaal.

Per collectie zijn letterlijke verdelingen beschikbaar voor `gebruiksdoel`,
`fysiek_voorkomen`, `functie`, `status` en `bouwjaar`, inclusief aanwezig/afwezig.
Iedere volledige getypeerde waarde vormt één bucket: lijsten worden niet
opgesplitst en strings niet geconverteerd. Het bouwjaarbereik gebruikt uitsluitend
positieve gehele getallen; overige aanwezige waarden blijven in de verdeling en
krijgen een expliciet uitgesloten aantal. Dit beoordeelt geen plausibiliteit.
Relatietellingen tellen gerichte officiële referentierecords per status, geen
unieke paren. Een terugverwijzing telt dus als een afzonderlijk bronfeit.

De provenance-selectors verwijzen naar de broncollectie van `objects` en hun
bestaande feit-provenance, respectievelijk naar `relations[].provenance_refs`.
Er worden geen nieuwe bronfeiten, relaties of geometrieën toegevoegd.