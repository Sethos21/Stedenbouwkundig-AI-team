# Milestone 2D-2 - Multi-collection BGT

Scope: uitsluitend de zes in 2D-1 vastgelegde BGT-collecties. Gesloten profielen
in domain/source_profiles.py, met per collectie endpoint, geometriecontract en
aparte dataset/collection namespace. BGT version en aanwezige kernattributen worden
gecontroleerd; originele properties blijven bewaard. Onbekende profielen worden
geweigerd. Geen vrije URL- of collectienaamconfiguratie.

Bestaande PDOKBGTAdapter, PDOKLiveGetTransport, SourceImportService en
SourceReplayService zijn minimaal geparameteriseerd. Default source_contract=None
behoudt het bestaande 2C-profiel, parser-ID, provenance en oude endpoint. Nieuwe
profielen gebruiken de actuele officiele /kadaster/bgt/ogc/v1 route en eigen
parser-ID. NEXT wordt voor 2D op endpoint EN ongewijzigde queryscope gecontroleerd
voordat het transport wordt aangeroepen. Live requests blijven exact begrensd op
de geaccepteerde testcasebbox, RD, JSON-FG, limit 1000 en eventuele cursor.

Geen opslagmigratie, dependency, nieuwe promotionroute of gewijzigde human/K00-
logica. De capability blijft alleen bij trusted A02; herparsen, immutable archief,
completeness, transactionele publicatie, binding, stale en audit blijven dezelfde
mechanismen. Lege volledige collecties zijn geldige resultaten, geen verzonnen data.

Gericht: tests/test_source_profiles.py, 9/9 PASS, 2.477 s. Alle zes collecties met
synthetische provider-origin evidence; import, replay, lege opslagreconstructie,
namespace, lege collectie, allowlist/next-security, metadata/schema/originweigering,
pagination/retry/budget, idempotence, rollback, mapping-tamper en replay relabeling.
Iedere test blokkeert socket/DNS. Geen live features opgehaald in deze fase.

De huidige afzonderlijke imports hebben afzonderlijke A02-revisies; een coherent
actueel bronbeeld wordt pas in 2D-4 opgebouwd. Een oude stale importrevisie wordt
hier niet stilzwijgend als actueel gepresenteerd.

Volledige regressie test.ps1: 436/436 PASS, 60.746 s, exitcode 0.
Log: .tools/2d-phase2-regression.txt. git diff --check: PASS. Fase 2D-2: PASS.
