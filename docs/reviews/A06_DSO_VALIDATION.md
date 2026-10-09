# A06 DSO — validatie en oplevering

Referentiecommit: `526a52312a518fa5d4ab27943b1f4984ed6b31e0`.
Branch: `feature/a06-phase2-ow-retrieval`.

## Testresultaten

| Controle | Resultaat | Bewijs |
|---|---|---|
| Gerichte offline tests | 41 geslaagd; 0 mislukt; 0 overgeslagen; exitcode 0 | [Log](../evidence/a06-contract-audit/targeted-tests.txt) |
| Volledige regressie via `test.ps1` | 548 geslaagd; 0 mislukt; 0 overgeslagen; exitcode 0 | [Log](../evidence/a06-contract-audit/regression-tests.txt) |
| Gedragsvergelijking | 43/43 gelijk aan referentiecommit, ook in volledige regressie | `ContractAuditTests.test_exact_baseline_behavior_and_evidence` |
| Structurele codevergelijking | Validatiepredicaten en verwerking gelijk na verwijderen van uitsluitend diagnostiekinstrumentatie | `ContractAuditTests.test_validation_predicates_match_reviewed_source` |
| Foutuitvoer | Alleen vaste `validation_error_code` toegevoegd; status/details/phase/category/http_status/contract_version en exit 1 behouden | `test_schema_conformity_codes_and_suppressed_cli`, bestaande DiagnosticTests |
| Contractpins | Beide hashes en versies gecontroleerd; pins ongewijzigd | [Vergelijking](../evidence/a06-contract-audit/comparison.json) |

Gericht commando, uitgevoerd met lokale Python, bytecode uitgeschakeld en `src`/`tests` op PYTHONPATH:

```powershell
& .tools/source-venv/Scripts/python.exe -B -m unittest -v test_dso_contract_audit test_dso_diagnostics test_dso_discovery test_ow_document test_dso_phase2_probe
& ./test.ps1
```

De 43 scenario's omvatten schema-conforme basisresponses, extra toegestane eigenschappen, lege optionele strings, nul resultaten, meerdere pagina's, ontbrekende vereiste velden, ongeldige typen/enums, OW/IMRO-identiteiten, intervallen, versieverschillen, beide transporten, synthetische authenticatie-/netwerk-/reflectiefouten en volledige retrieval. Succesresultaten worden op canonieke hash vergeleken; afwijzingen op exceptiontype/-bericht en bestaande diagnosevelden. UNKNOWN wordt expliciet getest waar de bestaande categorie specifieker is dan het nieuwe vocabulaire.

De oorspronkelijke nieuwe test verwachtte ten onrechte UNKNOWN bij ontbrekende optionele paginavelden. Het bestaande gedrag wees dit al af als paginaprobleem. Alleen de testverwachting is naar PAGINATION gecorrigeerd; geen productieregel aangepast. Daarna zijn de gerichte suite en de volledige regressie succesvol uitgevoerd.

## Gewijzigde bestanden

Implementatie:

- `src/bvc_ai/adapters/dso_diagnostics.py`: gesloten vocabulaire, exceptionannotatie en toevoeging aan veilige rapportage.
- `src/bvc_ai/adapters/dso_contract.py`: classificatie op JSON-/schemavalidatiepunten.
- `src/bvc_ai/adapters/dso_discovery.py`: classificatie van contenttype, paginering, familie, identiteit en interval.
- `src/bvc_ai/adapters/dso_live.py`: code behouden over de veilige transport-exceptiongrens.
- `src/bvc_ai/adapters/ow_document.py`: classificatie van schema, contenttype, identiteit, tijdsbinding en structuur.
- `src/bvc_ai/application/ow_document.py`: classificatie van bestaande discovery-/retrievalbindingsfouten.

Tests:

- `tests/test_dso_diagnostics.py`: expliciete verwachte uitvoervelden inclusief nieuwe code.
- `tests/test_dso_contract_audit.py`: synthetische schema-/diagnosegevallen, offline vergelijking met referentiecommit en AST-bewijs.

Documentatie/bewijs:

- `docs/reviews/A06_DSO_CONTRACT_AUDIT.md`: contractmatrix, prioriteiten, bronnen, resterende UNKNOWN-paden.
- `docs/reviews/A06_DSO_RECOVERY_PLAN.md`: afzonderlijk voorstel voor volgende fase.
- `docs/reviews/A06_DSO_VALIDATION.md`: dit verslag.
- `docs/evidence/a06-contract-audit/.gitattributes`: bewaart de exacte contractbytes bij Windows-checkouts.
- `docs/evidence/a06-contract-audit/comparison.json`: versies, hashes en volledige semantische diff.
- `docs/evidence/a06-contract-audit/ontsluiten-current.openapi.json` en `presenteren-current.openapi.json`: afzonderlijke officiële contractcaptures.
- `docs/evidence/a06-contract-audit/targeted-tests.txt` en `regression-tests.txt`: testlogs.

`dso_phase2_probe.py`, de PowerShell-probewrapper, discovery application service en beide gepinde contracten zijn geïnspecteerd maar ongewijzigd. De reeds bestaande ongevolgde map en reviewdiff blijven buiten de commit.

## Grenzen en review

Geen live DSO-aanroepen of productiecredentials gebruikt. De contractcaptures zijn openbare documentinspectie en geen brondata. Alle nieuwe testgevallen zijn TESTDATA. Veiligheids-, K00-, Human Approval-, A02- en A06 V1-grenzen zijn niet gewijzigd. Geen definitieve APPROVED/REJECTED-status toegekend, geen merge uitgevoerd.

Dit is diagnostiek plus audit; de adapter is hiermee niet volledig contractconform verklaard. De matrix documenteert bestaande afwijzingen van geldige responses en ontbrekende ondersteuning. Het herstelplan is uitsluitend een voorstel. Na één commit en push naar dezelfde featurebranch stopt het werk voor onafhankelijke GitHub-review. De definitieve SHA wordt in de oplevering genoemd; hij wordt niet zelfreferentieel in dit commitdocument opgenomen.
