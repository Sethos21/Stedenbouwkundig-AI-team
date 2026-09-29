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
- Schrijf caches, tooling, testbestanden en runtimegegevens alleen onder deze projectmap.
- Voer na relevante wijzigingen test.ps1 uit. CLI-approvaltests gebruiken uitsluitend geïsoleerde tijdelijke opslag.
- Keur de echte demo nooit goed namens de gebruiker. Laat runtime/GIS-001 wachten op de mens.
- Wijzig geen globale Git-configuratie vanwege de netwerkshare.
- Python-code en lokale bestanden zijn vertrouwd; de huidige capabilitygrens is geen sandbox voor kwaadwillende Python-plugins. Vereis procesisolatie en authenticatie voordat zulke plugins of externe callers worden toegevoegd.
