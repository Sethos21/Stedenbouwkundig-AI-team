# A06-identiteitscontract — offline karakterisatie (Issue #6)

Status: karakterisatie van bestaand gedrag; geen nieuwe identiteitsspecificatie, reparatie of Human Approval. Alle nieuwe gevallen zijn synthetische TESTDATA. De oorzaak van de eerder gemelde live DOCUMENT_IDENTITY is met dit bewijs niet vastgesteld.

## Basis en veilige hergebruikstrategie

- Opdracht: [Issue #6](https://github.com/Sethos21/Stedenbouwkundig-AI-team/issues/6).
- Werkbranch `codex/issue-6`, create-only vanaf geverifieerde master `0050e8c0595a969eb5c1a84462964008014c44b2`; PR #5 was gemergd vóór de claim.
- Geïnspecteerde en geteste A06-runtime: `28b4dd7b60fd5546e8161054ad76d7cd62bf831a`, actuele remote `feature/a06-phase2-ow-retrieval` bij start.
- Nulmeting: [rapport op 1587c498e8218d04dd77ef2c9a67851fe3256dc1](https://github.com/Sethos21/Stedenbouwkundig-AI-team/blob/1587c498e8218d04dd77ef2c9a67851fe3256dc1/docs/reviews/TECHNISCHE_NULMETING_INTEGRATIEPLAN_2026-11-12.md), remote eveneens gecontroleerd. De nulmeting zelf had geen remoteverificatie gedaan.

Master bevat de opdrachtenbus maar niet de vier DSO-featurecommits. Daarom geen cherry-pick, merge, rebase of kopie van runtimecode naar deze branch. [De testrunner](../../scripts/run_a06_identity.py) exporteert uitsluitend de exact gepinde, lokaal aanwezige A06-commit met `git archive` naar een nieuwe map onder `.tools/`, kopieert daar [de nieuwe tests](../../tests/characterization/a06_identity_cases.py) en gebruikt de bestaande interpreter/dependencies. Alle oorspronkelijke snapshotbestanden worden voor/na de run op SHA-256 vergeleken. De werkbranch behoudt de actuele masterprocedures; de featurebranch blijft intact. Dit is hergebruik voor tests, geen integratie of mergeadvies. Git-history blijft lokaal beschikbaar voor de bestaande 526a523-differentiaaltests, die vanuit de snapshot de bovenliggende repository alleen lezen.

De standaard mastersuite ontdekt deze karakterisatie bewust niet: master bevat de te testen DSO-modules niet. Reproductie vereist het expliciete runnercommando hieronder en de gepinde featurecommit in lokale Git-objecten. Ontbrekende objecten/interpreter/dependencies zijn een fout, geen download of skip. De runner is testondersteuning, geen nieuwe agentcapability of productie-isolatie. Er zijn geen externe libraries toegevoegd.

## Bronnen en pins

Alle verwijzingen hieronder zijn naar reeds aanwezige repositorydocumentatie of lokaal opgeslagen contracten. Geen website, PDF, DSO- of PDOK-endpoint is tijdens deze opdracht opnieuw opgehaald. Eerdere beschrijvingen van functionele documentatie zijn dus secundair bewijs uit de bestaande audit, geen opnieuw gecontroleerde officiële tekst.

| Afkorting | Commitvaste bron | Versie / SHA-256 |
|---|---|---|
| O | [Ontsluiten-pin](https://github.com/Sethos21/Stedenbouwkundig-AI-team/blob/28b4dd7b60fd5546e8161054ad76d7cd62bf831a/docs/contracts/dso/ontsluiten-v2.openapi.json) | 2.13.1; `4b2c33dc2a91a8c9073042978636f5222802395c3f1664b82c0c425eb126e0b4` |
| P | [Presenteren-pin](https://github.com/Sethos21/Stedenbouwkundig-AI-team/blob/28b4dd7b60fd5546e8161054ad76d7cd62bf831a/docs/contracts/dso/presenteren-v8.openapi.json) | 8.2.5; `37d70096ae6bd338a6b7824da12512a6375644bf20171613da4fbc8843a2105d` |
| Audit | [Bestaande contractaudit](https://github.com/Sethos21/Stedenbouwkundig-AI-team/blob/28b4dd7b60fd5546e8161054ad76d7cd62bf831a/docs/reviews/A06_DSO_CONTRACT_AUDIT.md), matrix 18, 19, 22–26 | Historische inspectie 9 oktober 2026; geen actuele providerclaim |
| Herstel | [Bestaand herstelplan](https://github.com/Sethos21/Stedenbouwkundig-AI-team/blob/28b4dd7b60fd5546e8161054ad76d7cd62bf831a/docs/reviews/A06_DSO_RECOVERY_PLAN.md), §4–6 | Voorstel; niet uitgevoerd |
| Validatie | [Bestaande validatie](https://github.com/Sethos21/Stedenbouwkundig-AI-team/blob/28b4dd7b60fd5546e8161054ad76d7cd62bf831a/docs/reviews/A06_DSO_VALIDATION.md) | Historisch 548 tests; nieuwe uitslagen staan in het opleverrapport |

Het auditmanifest noemt daarnaast Ontsluiten `92c8efcefa0ee88ed4e16f99060976de7b0538f031b1ef2faf0b121862f407b4`, eveneens versie 2.13.1, met uitsluitend een extra serverpad. Dat is een afzonderlijke historische capture, geen gebruikte runtimepin. Presenteren was byte-identiek. Pins en replaybestanden zijn in deze opdracht niet gewijzigd.

Codelegenda, steeds op A06-commit `28b4dd7...`:

- [C: dso_contract.py](https://github.com/Sethos21/Stedenbouwkundig-AI-team/blob/28b4dd7b60fd5546e8161054ad76d7cd62bf831a/src/bvc_ai/adapters/dso_contract.py)
- [D: adapters/dso_discovery.py](https://github.com/Sethos21/Stedenbouwkundig-AI-team/blob/28b4dd7b60fd5546e8161054ad76d7cd62bf831a/src/bvc_ai/adapters/dso_discovery.py)
- [W: adapters/ow_document.py](https://github.com/Sethos21/Stedenbouwkundig-AI-team/blob/28b4dd7b60fd5546e8161054ad76d7cd62bf831a/src/bvc_ai/adapters/ow_document.py)
- [AW: application/ow_document.py](https://github.com/Sethos21/Stedenbouwkundig-AI-team/blob/28b4dd7b60fd5546e8161054ad76d7cd62bf831a/src/bvc_ai/application/ow_document.py)

## Veld-, predicate- en bronmatrix

`O:#/...` en `P:#/...` zijn exacte JSON Pointers in de hierboven gepinde bestanden. Regels in de codelegenda verwijzen uitsluitend naar die commit. Acceptatie betekent hier alleen dat de bestaande validator de synthetische invoer accepteert, geen geldige juridische identiteit of officieel toegestane bronvorm.

| Veld / herkomst | Betekenis en contractpointer | Huidige predicate en normalisatie | DOCUMENT_IDENTITY / andere grens |
|---|---|---|---|
| Ontsluiten `identificatie` | Document-ID: AKN voor OW, planId voor IMRO. O:#/components/schemas/Identificatie; Document/properties/identificatie | D:105–109 unieke letterlijke hoofdidentiteit, ook over verschillende `versie`; D:122 OW begint `/akn/nl/`; D:126 IMRO begint `NL.IMRO.` | Dubbel of verkeerd familie-ID: D:108/124/127. Geen automatische selectie van nieuwste versie |
| Ontsluiten `uriIdentificatie` | URI-veilige vorm met slash naar underscore. O:#/components/schemas/UriIdentificatie en O:#/components/parameters/UriIdentificatie | D:107 uniek; D:122 OW exact `identity.replace('/', '_')`; D:126 IMRO exact gelijk aan identity. Koppelteken blijft behouden | Collision of mismatch: D:108/124/127. Geen non-word-transformatie |
| Ontsluiten `expressionId` | Identificatie van een specifieke documentversie. O:#/components/schemas/ExpressionId; OmgevingsdocumentMetadata/required en /properties/expressionId | D:121–125 vereist prefix `identity + '/'` en set-uniciteit. C:96 string moet niet leeg zijn. Geen parser die datum, taaldeel of `;versie` aan `versie` koppelt | Verkeerde prefix of dubbele expression: D:124. Willekeurige suffix na geldige prefix kan door; dat bewijst geen officiële semantiek |
| Ontsluiten `versie` | Documentversienummer, integer/int32. O:#/components/schemas/Versie | C typevalidatie; D:107 negatief geweigerd, nul niet; geen int32-bereikcontrole. Hoofd-ID blijft uniek onafhankelijk van versie | Negatief/dubbele hoofd-ID D:108; verkeerd type faalt eerder als schemafout |
| Presenteren path `uriIdentificatie` | P:#/components/parameters/uriIdentificatie beschrijft slash én koppelteken naar underscore | W:226 en AW:61 leiden opnieuw af uit letterlijke geselecteerde `identificatie`, niet uit discovery-URI; W:89–91 ASCII-profiel `_akn_nl_act_[A-Za-z0-9_]+` | Ongeldig endpoint-ID/kind W:91. Discovery-URI met koppelteken direct aan build_request geven wordt geweigerd; adapter gebruikt de andere afleiding |
| Presenteren `identificatie` | P:#/components/schemas/Omgevingsdocument/properties/identificatie → StopIdentificatie, required | W:180 exact gelijk aan geselecteerde discovery-identiteit. Geen normalisatie van responsidentiteit | W:186; gelijk endpoint bij botsende IDs verleent geen gelijkheid van bronidentiteit |
| Presenteren `expressionId` | P:#/components/schemas/Regeling/allOf/1/properties/expressionId, optionele string in schema | W:181 exacte stringvergelijking met discovery expression; ontbrekend geeft `None`, dus mismatch | W:186. Schema-optioneel is niet voldoende bewijs voor applicatiebinding |
| Presenteren `geregistreerdMet.versie` | P:#/components/schemas/Registratiegegevens/properties/versie; number, niet in required | W:182 `.get('versie') != selected['versie']`; numerieke Python-gelijkheid, geen stringnormalisatie. Geen zelfstandige expression/versieparser | W:186 bij verschil/ontbreken. Matrix claimt geen strengere int-eis dan implementatie |
| Presenteren type en gezag | P:#/components/schemas/Regeling/allOf/1/properties/type; Omgevingsdocument/properties/aangeleverdDoorEen | W:183–185 vergelijkt `type.waarde` en `aangeleverdDoorEen.code` met discovery; overige metadata niet dezelfde identiteitspredicate | Ook W:186: DOCUMENT_IDENTITY betekent dus niet uitsluitend ID-escaping |
| HAL `self`, `regeling`, `documentstructuur` | P:#/components/schemas/RegelingLinks, DocumentstructuurLinks, AnnotatieLinks | W:130–152 vergelijkt scheme+netloc+path exact met vaste BASE, afgeleide URI en suffix; geen fragment. Query apart: drie tijdsassen, geen extra/dubbele keys, `_expand=false`. Links worden niet opgehaald | Pad/host/fragment W:135 DOCUMENT_IDENTITY; tijd W:140–147 TEMPORAL_INTERVAL; dubbele/extra query UNKNOWN. Geen algemene URL-equivalentie |
| HAL `annotaties` | Relatie op metadata/structuur naar regeltekst- of divisieannotaties | AW:62–73 kiest uitsluitend een van twee vaste suffixes op exact documentpad; daarna `_link`. Geen provider-URL als request | Verkeerd document/suffix AW:68; overige identity-linkconflicten W:135 |
| Componenten en annotatie-ID / refs | P:#/components/schemas/DocumentComponent; RegeltekstannotatiesVastgesteld, DivisieannotatiesVastgesteld | W:199–213 vereist niet-lege component-ID/expressie en unieke component-ID; AW:93–115 vereist annotatie-ID, globale annotatie-uniciteit, bestaande `wId`/`*Ref`/`*Refs` | W:206, AW:99/102/108/111. Componentexpressie wordt hier niet als globale documentexpression vergeleken |
| Discovery-pin/raw/replay en expliciete keuze | Lokale evidence-eis, niet OAS-identiteitsveld | AW:14–38 controleert format, pakketdigest, raw SHA en exacte canonieke replay; AW:48–50 selecteert één letterlijke ID | AW:19/23/38/50. Herhashen van gewijzigde afgeleide metadata omzeilt replay niet |
| Metadata-bracket en origin | Lokale coherentie-eis | AW:76 vergelijkt volledige eerste/laatste metadata canoniek; AW:79 eist dezelfde origin voor discovery en alle captures | AW:77/80. Zelfs alleen titelwijziging geeft DOCUMENT_IDENTITY. Bracket is geen atomische snapshot |
| Contractpin / API-Version | C:58–63; D:86–87; W:27–31/165–166 | Bytehash van vaste lokale pin en exacte API-patchversie | Categorie CONTRACT_VERSION_MISMATCH, validation_error_code UNKNOWN; niet verwarren met `document.versie` |

Schema-, contenttype- en paginacontroles gaan vóór identiteitschecks. Daarom bewijst alleen de foutcode nooit welke predicate of welk veld de historische fout veroorzaakte. De nieuwe gecombineerde schema/identity-case bevestigt de eerste-afwijzingregel.

## Nieuwe deterministische karakterisatie

Alle methoden staan in `IdentityCharacterizationTests` in [a06_identity_cases.py](../../tests/characterization/a06_identity_cases.py). Onderstaande namen laten het voorvoegsel `test_` weg. Negatieve cases toetsen zowel exceptiontype/locatiebericht als de gesloten validatiecode; positieve cases controleren concrete broninhoud of bindingsuitkomst. Dit zijn geen nieuwe productie-eisen.

| Testnaam | Huidige uitkomst |
|---|---|
| `slash_only_discovery_preserves_hyphen_and_source` | Hyphen blijft in discovery-URI; underscore op die plek geeft DOCUMENT_IDENTITY; bronobject niet gemuteerd |
| `presenteren_hyphen_endpoint_and_full_binding` | Zelfde document via slash+hyphen endpoint lukt met vier gemockte requests en letterlijke evidence; slash-only URI rechtstreeks aan requestbuilder faalt |
| `discovery_duplicate_identity_even_with_other_version` | Zelfde ID met versie 1/1 of 1/2 geweigerd |
| `discovery_slash_underscore_collision_is_rejected` | Verschillende `test/deel` en `test_deel` botsen in discovery-URI; beide volgordes geweigerd |
| `discovery_duplicate_expression_with_distinct_work_prefixes` | Elke afzonderlijke kandidaat met gedeelde expression voldoet aan prefixcheck; gezamenlijk afgewezen op dubbele expression |
| `discovery_expression_is_prefix_check_not_version_parser` | Prefix met `arbitrary-TESTDATA` of suffix `;999` bij versie 1 accepteert; andere work-prefix weigert |
| `discovery_negative_version_and_zero` | Nul geaccepteerd; negatief geweigerd |
| `presenteren_hyphen_underscore_collision_keeps_exact_selection` | `test-deel` en `test_deel` blijven twee discoverykandidaten, leiden tot hetzelfde endpoint; elk lukt alleen met exact eigen metadata. Metadata van de ander faalt na eerste request |
| `presenteren_exact_expression_and_version_not_normalized` | Andere of ontbrekende expression/versie geeft DOCUMENT_IDENTITY |
| `hal_conflicting_document_in_each_response_kind` | Verkeerd document in metadata/structuur/annotatielinks faalt op betreffende fetch; geen vervolgrequests |
| `hal_annotation_document_conflict_stops_before_structure` | Verkeerde annotatie-documentbinding faalt na metadata |
| `hal_same_document_wrong_time_is_temporal_not_identity` | Zelfde document maar andere tijd: TEMPORAL_INTERVAL |
| `duplicate_component_and_annotation_identity` | Dubbele component-ID en cross-collection annotatie-ID geweigerd |
| `discovery_pin_and_replay_conflict_before_transport` | Gewijzigde afgeleide versie faalt met oude digest én na herhash op replay; nul fetches |
| `unselected_identity_is_not_replaced_by_normalized_alias` | Normalisatie-alias is geen expliciete selectie; nul fetches |
| `metadata_bracket_detects_nonidentity_drift` | Alleen titelverschil in vierde response: DOCUMENT_IDENTITY |
| `first_failure_is_schema_before_identity` | Ontbrekende titel plus verkeerde expression geeft REQUIRED_FIELD vóór identity |

De synthetische ID-vormen bewijzen bereikbare implementatiepaden, niet dat elke vorm in officiële STOP-documenten mag voorkomen. Bestaande regressies dekken aanvullend IMRO/familie, type/gezag, oorsprong, tijd, referenties, bronhashes en veilige CLI-diagnostiek. De nieuwe suite kopieert deze implementatie niet en mockt geen validator: alleen het transport krijgt synthetische responses.

## Open contractvragen en hersteladvies

1. **Endpointgebonden escaping blijft onbeslist.** O noemt slash, P slash+koppelteken, de bestaande audit schrijft aan functionele Ontsluiten-documentatie v1.1 §2.2 non-word-vervanging toe. Die laatste PDF is hier niet opnieuw opgehaald. Een expliciete officiële verduidelijking per endpoint/versie en toegestane STOP/AKN-ID-tekens is nodig, inclusief technische ontwerpidentiteiten. Geen universele replace-regel afleiden.
2. **Collisies zijn aantoonbaar, herstelkeuze niet.** Discovery blokkeert slash/underscore-collisies, maar niet de pas in Presenteren ontstane hyphen/underscore-collisie. De letterlijke metadata-binding voorkomt de geteste verwisseling. Niet bewezen: of de officiële server beide IDs ondersteunt, welke response hij geeft, en of een toekomstige strengere collisioncheck geldige kandidaten zou weigeren. Daarvoor zijn officiële contractvoorbeelden en pas later eventueel een afzonderlijk geautoriseerde, begrensde live proof nodig.
3. **Expression versus documentversie.** De lokale OAS beschrijft betekenis maar geeft geen volledige samenhangspredicate; huidige code checkt prefix/uniciteit en daarna exacte kruis-API-gelijkheid. Een `;999`-suffix bij versie 1 is alleen een geaccepteerde synthetische codecase. Niet aannemen dat de twee nummers hetzelfde versiestelsel zijn. Eerst gezaghebbende specificatie van work/expression/versienummer en technische ontwerpen.
4. **Ontbrekende optionele P-binding.** Expression/versie zijn schema-optioneel maar noodzakelijk in huidig applicatieprofiel. Een eventuele alternatieve bewijsroute vraagt apart ontwerp; niet opvullen of fallbacken. Tijdas-mapping en HAL-equivalentie blijven eveneens bestaande open punten buiten deze karakterisatie.
5. **Historische DOCUMENT_IDENTITY niet gereproduceerd.** Er is geen eenduidige veilige capture van de gemelde fout. Code kan ook terecht verkeerde versie, origin, gewijzigde replay of titel-drift blokkeren. Geen reparatieclaim zonder predicategebonden reproduceerbaar bewijs. Een latere live proof vereist afzonderlijke bron-/endpointscope, expliciete opt-in, veilige raw evidence/provenance en onafhankelijke beoordeling.

**Advies: NO-GO voor een herstelimplementatie die nu normalisatie of validatie versoepelt.** Deze karakterisatie is voldoende voor onafhankelijke beoordeling van het bestaande gedrag en voor het formuleren van een afzonderlijke contractverduidelijkingsopdracht. Dit advies verleent geen Human Approval of toestemming voor vervolgwerk. De onopgeloste betekenisvragen blokkeren een gedragswijziging; ze maken de deterministische waarneming van het huidige gedrag niet onbetrouwbaar.

De expliciete stopvoorwaarde in Issue #6 verlangt GEBLOKKEERD bij onduidelijkheid over de identiteitsspecificatie. Daarom krijgen rapport en opdrachtenbus die status: de offline karakterisatie is uitgevoerd, maar het hierboven beschreven broncontractconflict blijft open. Er wordt geen eenduidige nieuwe specificatie verzonnen en geen herstel gestart. Onafhankelijke review en een nieuw gebruikersbesluit bepalen het vervolg.

## Reproductie en bewijsgrenzen

Vanuit de projectroot, met bestaande projectlokale Python en lokaal beschikbare gepinde Git-objecten:

```powershell
& .tools/source-venv/Scripts/python.exe -B scripts/run_a06_identity.py --suite targeted
& .tools/source-venv/Scripts/python.exe -B scripts/run_a06_identity.py --suite full
& .tools/source-venv/Scripts/python.exe -B scripts/run_a06_identity.py --suite master
```

`targeted` draait de 17 nieuwe tests. `full` draait het ongewijzigde `run_tests.py` van A06 inclusief nieuwe tests. `master` draait verplicht `test.ps1` op de werkbranch; deze route test de bestaande masterruntime, niet de afwezige DSO-runtime. De scripts staan bewust los van productie-entrypoints. Tempopslag, snapshot, logs en bytecodebeleid blijven projectlokaal; procesomgeving verwijdert API-keyvariabelen zonder waarden te publiceren. Een geërfde Python-auditguard weigert socket-events; startup en eventuele blokkades worden gelogd. Dit is geen OS-sandbox voor kwaadwillende plugins of bewijs dat willekeurige externe executables geen netwerk kunnen gebruiken. Bestaande tests gebruiken gemockte transports en geïsoleerde CLI-opslag.

Resultaten en exacte test-/runnerhashes staan in het compacte opleverrapport en de veilige evidencebestanden onder `docs/evidence/issue-6/`. Mislukte ontwikkelruns worden daar vermeld en niet als PASS hergebruikt. Geen nieuwe liveconformiteit, juridische toepasselijkheid of volledige OAS-conformiteit bewezen. K00, HumanApprovalService, runtime/GIS-001, agentactivatie, contractpins en bestaande broninhoud blijven ongewijzigd.
