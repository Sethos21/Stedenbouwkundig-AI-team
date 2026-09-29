# Milestone 2D-4 - A02 ruimtelijke bronbasis

Scope: leesbaar, traceerbaar bronbeeld van de zes BGT-collecties en BAG pand/VBO.
Geen ontwerpgeometrie, beleid, eigendom, nieuwe bronautoriteit of nieuwe capability.

## Implementatie

SourceImportService houdt voor 2D een source_set in de actuele A02-output bij.
Elke entry bevat broncontract, snapshot, manifesthash en oorspronkelijke
importrevisie. Bij een nieuwe import wordt alleen die collectie vervangen; andere
leden worden eerst offline hergevalideerd tegen immutable evidence, oorspronkelijke
binding, succes-audit en actuele A01-inputcontext. Daarna publiceert uitsluitend
de bestaande trusted A02-service alle bronobjectreferenties in een nieuwe A02-
revisie. De bestaande transactie, K00Policy en stale-route blijven leidend.

Historische importrevisies worden niet heractiveerd. Hun immutable bronrecords
worden expliciet meegenomen in de nieuwe output. Bestaande bindings worden niet
gewijzigd. Een identieke herimport van een meegenomen bron retourneert zijn
originele binding en registreert ook de actuele A02-revisie in de noop-audit;
er ontstaat geen nieuwe publicatie. Een verwijderde/vervangen historische bron
kan niet stilzwijgend via die noop-route terugkeren.

SourceBasisService is read-only en heeft geen promotioncapability. build() leest
binnen een consistente transactie de actuele output, controleert alle publicaties
via replay/readback en vergelijkt de objectreferenties van de actuele A02-revisie.
Standaard zijn alle acht broncontracten vereist. Een expliciete gedeeltelijke
weergave benoemt ontbrekende collecties en claimt geen complete bronbasis.
De weergave bevat bronrecords/properties, geometry refs, raw hashes, snapshots,
importrevisies, een deterministische basis_hash en een inspecteerbare samenvatting.
verify() weigert zowel gewijzigde inhoud als een inmiddels stale A02-revisie.

Officiele relaties worden uitsluitend letterlijk uit bag_pnd, pand en
verblijfsobject-attributen gelezen. Geen ruimtelijke/LLM-match, synthetische inverse
relatie of automatische URL-fetch. Niet opgeloste verwijzingen, dubbelzinnige
identiteiten en niet wederzijds bevestigde relaties worden als onzekerheid
weergegeven. Geen brongeometrie wordt gewijzigd of samengevoegd.

CLI: `source-basis <task_id> [--revision <verwachte-A02-revisie>]` leest een complete
bronbasis en weigert stale input. HumanApprovalService en de workflowimplementatie
zijn niet gewijzigd; providers ontvangen geen aanvullende diensten of tools.

## Verificatie

Targeted: 22/22 PASS, 14.423 s, exitcode 0.
Log: `.tools/2d-phase4-targeted.txt`.
De acht nieuwe bronbasistests controleren complete/partiele weergave, read-only
werking, CLI, expliciete relaties/conflicten, replacement/stale/historiebehoud,
no-op, rollback van de gehele bronset en ontbrekend publicatiebewijs/tampering.
De bestaande nieuwe BGT/BAG-tests zijn in dezelfde gerichte run meegenomen.
Alle bronbodies in tests zijn synthetisch, geen echte providerwaarnemingen.

## Checkpoint en grenzen

Op verzoek van Seth stopt uitvoering na het huidige checkpoint (TOKEN/CAPACITY
CONTROL). De al gestarte volledige regressie wordt afgerond; geen nieuwe suite of
fase gestart. Nog geen 2D-live featurefetch uitgevoerd. Live contractconformiteit
van actuele features en end-to-end replaybewijs behoren tot fase 2D-5 en staan open.
De standaard regressie blijft netwerkloos; een aanvullende finale guard-run is
onderdeel van 2D-6 en is bij dit checkpoint niet gestart.

Bekende beperkingen: alleen vaste testcasebbox en vastgelegde bronnen; geen
point-in-timegarantie of volledige BGT-vlakdekking. Relaties buiten de bbox blijven
onopgelost. Gehele Decimal-attributen behouden het bestaande verliesvrije contract.
A02-workflowcontext blijft TESTDATA-scaffolding; provider-origin wordt apart
bewaard. De bestaande lokale Python/CLI/filesystem-vertrouwensgrens blijft gelden.

Volledige reeds lopende test.ps1: 449/449 PASS, 95.810 s, exitcode 0.
Log: `.tools/2d-phase4-regression.txt`. git diff --check en staged check: PASS.
Fase 2D-4: PASS. Geen fase 2D-5 of 2D-6 gestart.
