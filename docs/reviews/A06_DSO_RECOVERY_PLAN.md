# A06 DSO — herstelplan voor een volgende fase

Status: voorstel voor onafhankelijke architectuur- en GitHub-review. Niets uit dit plan is in de diagnostiekfase geïmplementeerd. Basis: [contractmatrix](A06_DSO_CONTRACT_AUDIT.md). Geen automatische merge of live DSO-aanroepen.

## 1. Officiële schema-conformiteit — P1

Scheid validatie van het officiële schema van de vraag of de applicatie de bron veilig kan gebruiken. Leg voor de vier Presenteren-responsevormen en Ontsluiten Documenten de bereikbare schemas en keywords vast. Gebruik een aantoonbaar OAS 3.0-geschikte validator of toets een beperkte implementatie tegen een onafhankelijke referentie. Beperk ref-resolutie tot gepinde lokale schemas; geen schema-download tijdens verwerking.

Herstel daarna uitsluitend aantoonbare afwijkingen: additionalProperties volgens het contract, lege strings zonder minLength, optional/required, nullable op bereikbare schemas, allOf als conjunctie, typen/enums/formats. Bewaar toegestane extra brondata letterlijk in de evidence; laat deze geen requests, tools, capabilities of beslissingen aansturen. Onderscheid ontbrekende optionele brondata van onvoldoende applicatiebewijs. Geen velden bijmaken of uit onbewezen broninformatie aanvullen.

Acceptatiebewijs: positieve fixtures inclusief uitbreidingen en lege optionele waarden, negatieve fixtures voor iedere gebruikte schema-eis, onafhankelijke schema-oracle, behoud van raw evidence en ongewijzigde broninhoud. Geen claim van volledige OAS-conformiteit zonder dekking van alle bereikbare keywords.

## 2. Bewuste applicatiebeperkingen — P1

Maak een expliciete profielspecificatie: punt in RD, maximaal drie decimalen, begrensde geografische scope, vastgestelde OW-regelingen voor retrieval, geen geometrieën, geen juridische interpretatie, vaste netwerkgrenzen. Maak onderscheid tussen schema-ongeldige data, geldige maar niet-ondersteunde data en onvoldoende bindings-/volledigheidsbewijs. Een geldige respons mag niet als schemafout worden voorgesteld.

Behoud alle discoverykandidaten en hun families. Een profielbeperking rechtvaardigt een expliciet niet-ondersteund resultaat, geen stille selectie of publicatie van een subset als volledige set. Vaststelling van toepasselijkheid of juridische geldigheid blijft buiten de adapter.

Acceptatiebewijs: grensgevallen voor ondersteunde en uitgesloten families; onveranderde brondata; geen aanvullende capability, Store, shell, filesystem of approval-tool bij providers. K00, HumanApprovalService, A02 en A06 V1 blijven intact.

## 3. Volledige begrensde paginering — P1

Vervang de één-pagina-aanname pas na een afzonderlijk ontwerp. Bouw vervolgrequests uitsluitend uit het vaste officiële endpoint, oorspronkelijke filters en gecontroleerde paginanummers. Volg geen willekeurige provider-URL. Definieer maximale pagina's/documenten/bytes én één totale deadline. Houd tijdreisparameters, CRS, requestbody en sortering stabiel.

Controleer paginanummers, tellingen, dubbele document-/versie-identiteiten, herhaalde pagina's, next/last-tegenstrijdigheden en veranderingen tijdens retrieval. Bewaar raw evidence, hash en provenance voor elke pagina. Publiceer pas een complete set als de volledigheid aantoonbaar is. Budgetoverschrijding, ontbrekende pagina of serverdrift moet de hele set als incompleet markeren en gebruik als volledige set blokkeren; geen gedeeltelijke succesuitvoer.

Acceptatiebewijs: 0/1/meerdere pagina's, laatste gedeeltelijke pagina, maximumgrens, ontbrekende of herhaalde pagina, gewijzigde totalen, providerlinks naar andere host, deadline/bytebudget en credentialreflectie. De precieze conventie voor nul resultaten moet eerst uit contract of officieel bewijs worden vastgesteld.

## 4. Documentidentiteit en bronbinding — P1

Los het conflict op tussen Ontsluiten OAS slashvervanging, functionele documentatie non-word-vervanging en Presenteren slash/koppelteken-vervanging. Gebruik per endpoint een gedocumenteerde transformatie; geen universele replace-regel. Leg technische ontwerpidentiteiten, work/expression-identiteit, versie en mogelijke normalisatiecollisies vast. Bewaar oorspronkelijke identificaties. Geen actornaam uit bronoutput als menselijke identiteit vertrouwen.

Specificeer vervolgens alle tijdsassen en intervallen, inclusief eindwerking, gerelateerde versies en fractionele timestamp-precisie. Vergelijk met behoud van bronprecisie. Afwezigheid van een optioneel veld kan bindingsbewijs onmogelijk maken; vul dit niet op met een gok. Een expliciete documentselectie en replay-pin blijven verplicht. Hashes bewijzen integriteit, geen authenticatie; onbeheerde externe callers of kwaadwillende Python-plugins vereisen eerst authenticatie en procesisolatie.

Acceptatiebewijs: OW/IMRO, koppeltekens en andere toegestane ID-tekens, technische ontwerp-ID, botsende normalisaties, afwijkende expressie/versie/gezag, nanosecondeverschil, gelijke/omgekeerde intervallen en source-originmix. Metadata-bracket blijft als beperkte coherentiecontrole benoemd, niet als atomische snapshotgarantie.

## 5. Contractversies en verschillen — P2

Behoud de huidige pins totdat een expliciet versie-/compatibiliteitsbesluit is genomen. De huidige audit toont voor Ontsluiten 2.13.1 uitsluitend een extra relatief serverpad; Presenteren 8.2.5 is byte-identiek. Dat verschil is geen reden om endpoints of hashes stil te wijzigen.

Definieer hoe API-Version, patchcompatibiliteit, gepinde SHA-256 en actuele publicatie worden onderscheiden. Iedere pinwijziging krijgt een aparte diff op paths/parameters/schemas en een reviewbaar changelog met hash. Verruim nooit de netwerkallowlist op basis van een nieuwe serverslijst.

Acceptatiebewijs: ongewijzigd contract, alleen servermetadata gewijzigd, compatibele en incompatibele schemaverandering, ontbrekende/ongeldige versieheader en wijziging zonder nieuw versienummer. Geen runtime-autoupdate.

## 6. Presenteren v8-interoperabiliteit — P1

Valideer de vier gebruikte GET-vormen en beide annotatiefamilies op hun eigen schemas. Leg de mapping van discovery geldigOp/beschikbaarOp naar Presenteren geldigOp/inWerkingOp/beschikbaarOp expliciet vast. Het gelijkstellen van inWerkingOp aan geldigOp is nu een applicatiekeuze en kan een andere versie opleveren. Geen fallback naar een andere regeling, datum of versie om een mismatch te laten verdwijnen.

Behandel HAL als bronbinding; links worden niet willekeurig opgehaald. Maak transport-equivalente URL-vormen alleen acceptabel na aantoonbare normalisatie zonder host-, pad-, tijd- of identiteitsverlies. Bepaal het beleid voor lege structuur, ontbrekende optionele versie/expressie, gereserveerde/vervallen componenten en lege annotaties. Behoud alle letterlijke tekst, bronobjecten en verwijzingen; geen juridische duiding of inhoudelijke wijziging.

Acceptatiebewijs: regeltekst- en divisieannotaties, exacte componentbinding, ontbreken van optionele metadata, geldige lege bronvormen, volledige referentieresolutie, veranderde metadata tussen eerste en laatste request en afwijkende tijdlinks. Een eventuele latere live proof vereist een nieuwe expliciete opdracht en opt-in; deze fase levert daarvoor geen bewijs.

## Voorgestelde volgorde

Eerst bronconflicten en profieleisen besluiten, vervolgens schema-conformiteit en identiteit/tijdsbinding implementeren, daarna begrensde paginering en geïntegreerde Presenteren-verificatie. Elke stap krijgt gerichte offline tests en `test.ps1`. Onafhankelijke review bepaalt de vervolgopdracht. De echte demo/runtime GIS-001 blijft wachten op de mens.
