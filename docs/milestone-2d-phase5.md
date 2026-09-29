# Milestone 2D-5 - Mastenbroekweg live proof

Datum: 29 september 2026. Geaccepteerd hervatcheckpoint: `1c4ee6755c49872cd8dfe42b40d49bdc6f7838c4`.
Protocolupdate uit `818e084` afzonderlijk overgenomen in `f9bf210`; 2D-1 t/m 2D-4 intact.

## Delta

- `scripts/live_mastenbroekweg_2d.py --live-mastenbroekweg` gebruikt de acht bestaande gesloten bronprofielen, vaste RD-bbox en trusted importservice. Elke run krijgt nieuwe opslag onder `runtime/2d-live/`; bestaande runs worden geweigerd.
- A01 gebruikt expliciet TESTDATA-scaffolding. Alle broncaptures behouden provider-origin. Geen Human Approval, A03-A06, ontwerp of wijziging van runtime/GIS-001.
- Complete A02-bronbasis, summary, hashes en captureprovenance worden lokaal vastgelegd. Offline verificatie blokkeert socket/connect/DNS; reconstructie vergelijkt raw bytes, geometrie, features, pages en snapshots in lege archiefopslag zonder taken of trusted bindings. De A02-bronbasis wordt opnieuw uit de oorspronkelijke bindings opgebouwd; reconstructie publiceert geen alternatieve A02-revisie.
- Additive-choice toegepast op de reeds gekozen zes BGT- en twee complementaire BAG-collecties. Identiteit/provenance blijven gescheiden; onopgeloste relaties blijven onzekerheden, zonder extra fetches of synthetische verzoening.

## Verificatie en begrensd herstel

- Gerichte networkless tests: 4/4 PASS, 1.787 s; `.tools/2d-phase5-targeted.txt`. Opt-in/padgrens, acht collecties plus offline reconstructie, foutstop en niet-JSON-foutevidence.
- Eerste run `20260929T081607784190Z`: fail-closed bij BGT/onbegroeidterreindeel op requestdeadline; exacte ontvangen evidence behouden, geen promotion van deze mislukte collectie.
- Proof-only instelling: requestdeadline 60 s omdat parsing van grote polygonen binnen hetzelfde budget valt; totale fetchlimiet blijft 120 s per collectie, 64 MiB, 100 pagina's, 100000 features en maximaal twee retries. Geen endpoint/scope/architectuur/dependency-wijziging.
- Nieuwe live-run `20260929T125359317086Z`: PASS; alle acht collecties, 1415 bronobjecten, A02/v8. Replay en lege-opslagreconstructie PASS met netwerkblokkering. 168 opgeloste en 73 onopgeloste relaties; 201 records zonder officiele referentie. Geen bronconflict dat een nieuwe productkeuze vraagt.

## Grenzen

Counts zijn gedateerde observaties. Geen point-in-timegarantie, volledige BGT-dekking, ontwerp-, beleids- of eigendomsconclusies. Raw archieven blijven lokaal; het compacte proofrapport wordt versiebeheerd. Metadata is de in 2D-1 geaccepteerde contractverwachting, geen nieuw opgehaalde metadata.

Compact bewijs: `docs/milestone-2d-phase5-proof.json` met capture-/manifesthashes en SHA-256 van beide lokale archieven, bronbasis en origineel rapport. `git diff --check`: PASS. Volledige regressie uitsluitend in 2D-6.

2D-5: PASS
