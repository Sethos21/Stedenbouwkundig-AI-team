# BAG API address bootstrap for A02

The generic address proof defaults to BAG API Individuele Bevragingen v2.
The official specification is archived in `evidence/bag-api-bootstrap/openapi.zip`
with its original-byte SHA256 in `specification.json`.

Only GET `/lvbag/individuelebevragingen/v2/adressenuitgebreid` on
`https://api.bag.kadaster.nl` is allowlisted. The request uses postcode,
huisnummer, explicit suffix fields where supplied, exacteMatch=true,
inclusiefEindStatus=false, page=1 and pageSize=10. A single exact address
must be returned, without continuation. No links are followed.

Authentication uses the documented `X-Api-Key` header. Set `BAG_API_KEY` in
the executing process; the transport reads it only after scope validation.
It never enters the serializable request, provenance, logs or archive.
Responses echoing the credential are discarded; upstream exception text is
not propagated. Requests are HTTPS-only, capped at 20 seconds including
DNS/body and 256 KiB, without redirects, retries or automatic fallback.

The official response supplies nummeraanduiding, verblijfsobject, pand,
openbare ruimte and woonplaats identifiers. This initial point bootstrap
supports Verblijfsobject; ligplaats/standplaats geometry is rejected.
Uncertain, ambiguous, malformed, mismatched or unsupported results fail closed.
The API's documented native CRS is EPSG:28992. A conflicting response CRS is
rejected. The original 2D/3D point is preserved; its first two RD ordinates
feed the existing deterministic 500 m square. No coordinate transformation
or synthetic BAG relation is performed. The square remains TEST/ANALYSIS
geometry, never a cadastral, property, policy or design boundary.

Run the trusted proof with explicit opt-in:

```powershell
.tools/source-venv/Scripts/python.exe -B scripts/live_address_2d.py `
  --address 'Street 12, 1234 AB City' --live-address `
  --compare-address-evidence runtime/2d-live/PRIOR/address-evidence.json
```

`--bootstrap locatieserver` selects the preserved legacy adapter explicitly.
The optional comparison replays the stored evidence and requires identical
nummeraanduiding/verblijfsobject identifiers and RD coordinates within 1 cm
rounding tolerance, before any OGC import. It never fetches a baseline.
The eight existing OGC contracts remain the source of area objects and
relations. The individual API only bootstraps the analysis; it cannot promote
sources, import objects, approve work or replace the OGC source set.

Offline verification uses `scripts/verify_address_proof.py --directory ...`;
it replays the BAG response without credentials and reconstructs the OGC
archive with socket/connect/DNS blocked. Existing Locatieserver archives
retain their original geometry identity and replay behavior.

The ten unresolved Meppel OGC targets are known only by OGC feature UUID.
There is no literal BAG registration identifier for those missing objects in
the archived source set. Individual existence checks therefore are not made;
no UUID-to-BAG conversion or extra source objects are synthesized.
