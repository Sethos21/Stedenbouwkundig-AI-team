# BAG API Individuele Bevragingen — secret setup

## Doel

Deze repository gebruikt de **BAG API Individuele Bevragingen** uitsluitend voor officiële adres- en objectresolutie binnen de A02-bronketen.

## BELANGRIJK — zet de API-key NIET in dit bestand

Een echte API-key is een geheim en mag nooit worden vastgelegd in:

- Git-tracked bestanden;
- Markdown-documentatie;
- broncode;
- testfixtures;
- proof JSON;
- logs;
- screenshots;
- commits of pull requests.

Gebruik dit document dus alleen als instructie. **Plak de sleutel hier niet in.**

## Verwachte secretnaam

Gebruik lokaal voorlopig:

`BAG_API_KEY`

De applicatie moet deze waarde later uitsluitend tijdens runtime uit de omgeving/secret-configuratie lezen.

Voorbeeld van de verwachte variabele:

```text
BAG_API_KEY=<JOUW_API_KEY>
```

Bovenstaande regel is uitsluitend een voorbeeld. Vervang `<JOUW_API_KEY>` nooit in een Git-tracked bestand.

## GitHub

Als de sleutel later nodig is voor een GitHub Actions-workflow, sla hem op als een **GitHub Actions repository secret** met de naam:

`BAG_API_KEY`

De sleutel zelf hoort niet in de repository.

## Lokale ontwikkeling

De lokale Codex-/ontwikkelomgeving mag de sleutel via een environment variable ontvangen. Implementatie moet fail-closed zijn wanneer de sleutel ontbreekt.

De applicatie mag de sleutel nooit:

- loggen;
- in exceptionteksten opnemen;
- in raw-response evidence opslaan;
- in request-proofbestanden opnemen;
- committen;
- teruggeven in rapportages.

## Architectuurgrens

De BAG API Individuele Bevragingen is bedoeld voor individuele officiële BAG-bevragingen, waaronder adres-/objectresolutie. De bestaande BAG/BGT OGC-keten blijft verantwoordelijk voor de geografische gebiedsanalyse.

Beoogde keten:

```text
Gebruikersadres
    ↓
BAG API Individuele Bevragingen
    ↓
officiële BAG-identiteit / locatiebasis
    ↓
deterministische analysegeometrie
    ↓
bestaande BAG/BGT OGC-keten
    ↓
A02 gevalideerde bronbasis
```

## Status

De API-toegang is aangevraagd. Live integratie en de Meppel-generalisation-test worden hervat zodra de sleutel beschikbaar is.

Testadres:

`K.E. Borgerlaan 4, 7942 HC Meppel, Nederland`
