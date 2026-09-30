# BAG individual bootstrap live evidence

Result: **PASS_WITH_FINDINGS**. See `result.json`, `comparison.json`, test logs
and `secret-scan.json`. The source API specification is in `openapi.zip`;
`specification.json` records its original-byte hash and non-cookie metadata.

`meppel-bag-api-live.zip` contains the new raw BAG address response, address
provenance, full eight-collection OGC archive, source basis, report, comparison
baseline and independent offline verification result. `archive-manifest.json`
provides SHA256 hashes of the ZIP and its original evidence files.
No credentials or request authentication headers are included.

For independent replay, extract the ZIP into a fresh directory under
`runtime/2d-live/`, then run:

```powershell
.tools/source-venv/Scripts/python.exe -B scripts/verify_address_proof.py --directory runtime/2d-live/EXTRACTED
```

No BAG key or network is needed for replay. The original Meppel/Locatieserver
archive and the prior BAG href correction evidence remain unchanged.
The 10 missing BAG targets and 3 BGT zero references remain unresolved;
this bootstrap does not supplement the OGC area source set.
