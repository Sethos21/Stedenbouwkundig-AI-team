# Architectuur en beveiligingsgrens

Python 3.12+, uitsluitend standaardbibliotheek. De CLI is de vertrouwde composition root. Workflow gebruikt AIProvider voor een gestructureerde inventarisatie en review. Geen provider ontvangt services, shelltools of filesystemtoegang als runtimecapaciteit.

De agentingang AgentSession kan alleen de gecontroleerde workflow-statusfunctie aanroepen. Iedere definitieve overgang wordt daar geweigerd, ongeacht actor. HumanApprovalService vereist een identiteitscapability die alleen de CLI-compositie en geïsoleerde tests bezitten. Ook die service controleert de statusmachine, actor en voldoende review.

De capability is een procesintern Python-object, geen credential of productie-authenticatie. Python-moduleprivé is een API-grens, geen OS-beveiliging. Een toekomstige externe provider mag alleen data retourneren. Onvertrouwde Python-plugins, shelltoegang, rechtstreeks databasebewerken en een agent die zelfstandig de CLI kan starten zijn niet ondersteund en kunnen niet met deze lokale API-grens worden beveiligd. Voeg daarvoor een afzonderlijk proces, geauthenticeerde menselijke sessie en OS-rechten toe in een latere milestone. Binnen de geleverde agentruntime is geen approval-tool beschikbaar.

De regels voor K00 worden vóór iedere mockschrijfactie uitgevoerd. Reads leveren kopieën. De mock bevat geen geometrie. De bronoutput heeft een gesloten top-level schema; A02 kan geen design-outputtype of extra ontwerplagen registreren. Vrije tekst wordt niet semantisch door een echt model geverifieerd.

SQLite gebruikt rollback-journaling (DELETE) en transacties voor besluiten plus audit. JSONL is een projectie van de canonieke audittabel; bij een crash kan de projectie achterlopen en wordt deze bij de volgende CLI-opdracht opnieuw opgebouwd. Geïsoleerde lokale CLI-processen worden getest, maar gelijktijdige workflow-uitvoering vanaf meerdere hosts en SMB-storingen vallen buiten M1. Onderbreking kan een RUNNING-taak achterlaten; automatische crashrecovery is nog niet gebouwd.

Milestone 1 doet geen externe calls en gebruikt geen credentials of productiebronnen. Providerimplementaties zijn vertrouwde code; de standaardimplementatie is deterministisch. Rolprofielen beschrijven ook toekomstige beperkingen; runtimehandhaving richt zich op de actieve broninventarisatie, statusmachine, bronstatus, reviewverdict, approval-capability en K00.

## Milestone 2A

De CLI selecteert via agents/factory.py de mock- of OpenAI-provider. De bestaande AIProvider-interface en alle domain/application-code blijven ongewijzigd. agents/openai_provider.py verzorgt HTTPS, strikte JSON-output, lokale antwoordvalidatie en veilige foutmeldingen. Er is geen SDK of package geïnstalleerd. De key komt uitsluitend uit OPENAI_API_KEY.

De provider retourneert uitsluitend data en ontvangt geen Store, human capability, AgentSession of tools. Providerherkomst wordt in bestaande tekstvelden vastgelegd: A02 in payload.recommendations, A07 in Review.findings. Bronreferenties blijven ongewijzigde fixture/TESTDATA-items. Er is geen nieuw provenance-datamodel of databasemigratie.

De CLI-smoke composeert InventorySmokeProvider: één geselecteerde inventory-call en een deterministische A07-review. De volledige bestaande workflow draait in een unieke submap; de goedgekeurde runtime/GIS-001 blijft intact. Fouten tijdens de call worden door de bestaande workflow geaudit en leiden tot FAILED. Ontbrekende configuratie wordt vóór taakcreatie afgehandeld.

Deze beperkte, vertrouwde adapter introduceert geen procesisolatie of productie-authenticatie. De eerder beschreven lokale beveiligingsgrens blijft gelden.
