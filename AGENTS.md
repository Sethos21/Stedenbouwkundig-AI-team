# Ontwikkelregels BVC AI Ontwerpteam

- Werk uitsluitend in deze projectmap. Geen relatie met de BVC Financiële Rapportagetool.
- Milestone 1 gebruikt uitsluitend TESTDATA. Presenteer nooit fixtures als echte brondata.
- A01, A02 en A07 zijn actief. Activeer A03–A06 alleen na een expliciete volgende opdracht.
- Geen enkele agent mag APPROVED of REJECTED toekennen. De definitieve beslisroute loopt via HumanApprovalService vanuit de vertrouwde CLI.
- Geef providers nooit de human capability, Store, CLI, shell, filesystemtools of een approval-tool.
- Verplaats geen approval-logica naar de workflow. Vertrouw geen actornaam uit provider-output als menselijke identiteit.
- K00 blijft immutable. Alle toekomstige GIS-adapters moeten de K00-policy toepassen; registreer alleen afgeleide lagen.
- Wijzig specialistische broninhoud niet tijdens review. Reviews verwijzen naar de beoordeelde outputversie.
- Houd statusovergangen expliciet en audit geblokkeerde overgangen en fouten.
- Gebruik geen productiecredentials, externe integraties, downloads van GIS-bronnen of cloudwrites binnen deze milestone, behalve de hieronder expliciet toegestane Milestone-2D-bronketen.
- Milestone 2D (besluit Seth, 29 september 2026): read-only contractinspectie van officiële PDOK BGT/BAG-bronnen en begrensde live fetches binnen vooraf vastgelegde officiële endpoints/scopes zijn toegestaan, met lokale raw evidence, hashes, provenance en validatiebewijs en expliciete live opt-in voor de live proof. Alleen daarvoor noodzakelijke netwerktoegang; geen productiecredentials, cloudwrites, arbitrary URL/netwerktoegang, andere externe integraties of niet vooraf toegestane bronnen/endpoints. Capability-, provenance-, K00- en Human Approval-grenzen blijven onverkort gelden.
- Aanvullend besluit Seth, 30 september 2026: de offici�le PDOK Locatieserver mag uitsluitend voor adresresolutie naar een officieel BAG-adres/co�rdinaat en daarvan afgeleide TEST/ANALYSIS-bbox worden gebruikt, gevolgd door de bestaande BAG/BGT-keten. Alleen HTTPS GET naar `https://api.pdok.nl/bzk/locatieserver/search/v3_1/free` met het vaste begrensde adresprofiel; geen algemene GIS-bron, arbitrary netwerk of vervanging van BAG/BGT-bronwaarheid. Vereist: expliciete live opt-in, eenduidige match, raw evidence/hashes/provenance, fail closed, K00/capability- en Human Approval-grenzen intact.
- Schrijf caches, tooling, testbestanden en runtimegegevens alleen onder deze projectmap.
- Voer na relevante wijzigingen test.ps1 uit. CLI-approvaltests gebruiken uitsluitend geïsoleerde tijdelijke opslag.
- Keur de echte demo nooit goed namens de gebruiker. Laat runtime/GIS-001 wachten op de mens.
- Wijzig geen globale Git-configuratie vanwege de netwerkshare.
- Python-code en lokale bestanden zijn vertrouwd; de huidige capabilitygrens is geen sandbox voor kwaadwillende Python-plugins. Vereis procesisolatie en authenticatie voordat zulke plugins of externe callers worden toegevoegd.

## Structurele GitHub-overdracht (besluit Seth, 12 november 2026)

- Rond iedere ontwikkel-, onderzoeks- en reviewopdracht af volgens [de overdrachtsprocedure](docs/opleveringen/README.md), met [het compacte opleverformat](docs/opleveringen/TEMPLATE.md). Doe dit uit eigen beweging; vraag niet opnieuw toestemming voor de hier toegestane publicatie van eigen werk.
- Registreer werkelijk uitgevoerd werk, gewijzigde bestanden, besluiten, tests inclusief beperkingen, open punten en vervolgstap. Gebruik VOLTOOID, ONVOLTOOID of GEBLOKKEERD voor opdrachtstatus; dit is nooit Human Approval of goedkeuring van eigen werk.
- Bewaar één herkenbaar rapport per opdracht onder docs/opleveringen/. Bestaande inhoudelijke review-/milestonerapporten blijven leidend: verwijs ernaar in plaats van ze te kopiëren. De index is branchgebonden; de nieuwste publicatie over branches heen wordt via de PR-publicatiebewijzen gevonden.
- Commit alleen eigen, toegestane wijzigingen op een werkbranch. Push uitsluitend die branch naar origin, zonder force, tags, merges of writes naar master/beschermde branches. Controleer daarna de exacte remote HEAD. Bestaande lokale wijzigingen en ongevolgde bestanden blijven ongemoeid.
- Publiceer na bevestigde push een nieuw PR-publicatiebewijs met marker CODEX_OPLEVERING_V1, exacte remote SHA en commitvaste rapportlink. Gebruik een draft-PR met titelprefix [Codex-oplevering], of hergebruik de bestaande taak-PR met die herkenbare prefix. De precieze volgorde en vindprocedure staan in de index. Geen eigen goedkeuringsreview, auto-merge of merge.
- GEPUBLICEERD mag alleen na geslaagde push en bevestiging van de bedoelde remote commit worden gemeld; de structurele overdracht is pas vindbaar na het gecontroleerde PR-publicatiebewijs. Bij mislukte push: NIET GEPUBLICEERD, met oorzaak en veilige vervolgstap. Nooit een oude remote SHA presenteren als nieuwe oplevering.
- Bij onderbreking: leg veilig vast wat wel/niet is uitgevoerd en welke tests onvolledig zijn; markeer ONVOLTOOID (of GEBLOKKEERD bij een concrete blokkade). Publiceer alleen een veilig checkpoint. Als stoppen/crash publicatie verhindert, doe dit bij hervatting; claim geen afronding of ongeziene testuitslag.
- Deze toestemming geldt uitsluitend voor projectdocumentatie, toegestane werkbranches, draft-PRs en hun overdrachtsberichten op GitHub. Zij verruimt geen functioneel ontwerp, productieactie, live bron-API, gegevenspublicatie of agentcapability. Publiceer geen credentials, persoonsgegevens of vertrouwelijke brondata; vat veilig samen en vermeld bewust niet-gepubliceerd bewijs. K00 en HumanApprovalService blijven ongewijzigd.
- Bij 'Controleer Codex terminal' betekent terminal: de nieuwste geverifieerde GitHub-oplevering volgens de index, niet toegang tot een terminalsessie. Onafhankelijke ChatGPT-review en het definitieve gebruikersbesluit blijven afzonderlijk. Een nieuwere expliciete opdracht die publicatie beperkt, gaat voor; registreer dan de beperking.
