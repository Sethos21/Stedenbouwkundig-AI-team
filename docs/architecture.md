# Architectuur en beveiligingsgrens

Python 3.12+, uitsluitend standaardbibliotheek. De CLI is de vertrouwde composition root. Workflow gebruikt AIProvider voor een gestructureerde inventarisatie en review. Geen provider ontvangt services, shelltools of filesystemtoegang als runtimecapaciteit.

De agentingang AgentSession kan alleen de gecontroleerde workflow-statusfunctie aanroepen. Iedere definitieve overgang wordt daar geweigerd, ongeacht actor. HumanApprovalService vereist een identiteitscapability die alleen de CLI-compositie en geïsoleerde tests bezitten. Ook die service controleert de statusmachine, actor en voldoende review.

De capability is een procesintern Python-object, geen credential of productie-authenticatie. Python-moduleprivé is een API-grens, geen OS-beveiliging. Een toekomstige externe provider mag alleen data retourneren. Onvertrouwde Python-plugins, shelltoegang, rechtstreeks databasebewerken en een agent die zelfstandig de CLI kan starten zijn niet ondersteund en kunnen niet met deze lokale API-grens worden beveiligd. Voeg daarvoor een afzonderlijk proces, geauthenticeerde menselijke sessie en OS-rechten toe in een latere milestone. Binnen de geleverde agentruntime is geen approval-tool beschikbaar.

De regels voor K00 worden vóór iedere mockschrijfactie uitgevoerd. Reads leveren kopieën. De mock bevat geen geometrie. De bronoutput heeft een gesloten top-level schema; A02 kan geen design-outputtype of extra ontwerplagen registreren. Vrije tekst wordt niet semantisch door een echt model geverifieerd.

SQLite gebruikt rollback-journaling (DELETE) en transacties voor besluiten plus audit. JSONL is een projectie van de canonieke audittabel; bij een crash kan de projectie achterlopen en wordt deze bij de volgende CLI-opdracht opnieuw opgebouwd. Geïsoleerde lokale CLI-processen worden getest, maar gelijktijdige workflow-uitvoering vanaf meerdere hosts en SMB-storingen vallen buiten M1. Onderbreking kan een RUNNING-taak achterlaten; automatische crashrecovery is nog niet gebouwd.

Geen externe calls, credentials of productiebronnen. Providerimplementaties zijn vertrouwde code; de huidige implementatie is deterministisch. Rolprofielen beschrijven ook toekomstige beperkingen; runtimehandhaving richt zich op de actieve broninventarisatie, statusmachine, bronstatus, reviewverdict, approval-capability en K00.
