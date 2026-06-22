# AGENTS.md — aiscream-jpa

## Operations

### Restart normally (preserves data)
```bash
docker compose down && docker compose up -d
```

### Restart fresh (wipes database, clean slate) 
Avoid doing this unless you are on a repeated error, or if the changes necessitate starting from scratch
```bash
docker compose down -v && rm -rf hapi.postgress.data && docker compose up -d
```

## Debugging

### Check Docker logs
```bash
docker compose logs --tail=2000 | grep -i "error\|exception\|FAILED\"
```

### Verify remote terminology service
```bash
# Check if tx.fhirlab.net has a CodeSystem
curl -s "https://tx.fhirlab.net/fhir/CodeSystem?url=<CODESYSTEM_URL>" | python3 -m json.tool

# List all CodeSystems
curl -s "https://tx.fhirlab.net/fhir/CodeSystem?_count=5&_summary=true" | python3 -m json.tool

# Delete a resource from tx.fhirlab.net
curl -s -X DELETE "https://tx.fhirlab.net/fhir/CodeSystem/<ID>" -H "Content-Type: application/fhir+json"
```

### Test local FHIR server
```bash
curl -s http://localhost:8080/fhir/metadata | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('software',{}).get('name'), d.get('software',{}).get('version'))"
```

## Configuration lookups

### HAPI FHIR JPA starter — reference application.yaml
Always check the canonical starter config for property structure:
```
https://raw.githubusercontent.com/hapifhir/hapi-fhir-jpaserver-starter/refs/heads/master/src/main/resources/application.yaml
```

Consider `gh cli` to navigate.

### HAPI FHIR docs
- Root: `https://hapifhir.io/hapi-fhir/docs/`
- JPA config: `https://hapifhir.io/hapi-fhir/docs/server_jpa/configuration.html`
- Lucene/Elasticsearch: `https://hapifhir.io/hapi-fhir/docs/server_jpa/elastic.html`
- Terminology: `https://hapifhir.io/hapi-fhir/docs/server_jpa/terminology.html`
- Validation support: `https://hapifhir.io/hapi-fhir/docs/validation/validation_support_modules.html`
- Package registry: `https://hapifhir.io/hapi-fhir/docs/server_jpa/packages.html`

### GitHub repos (use `gh` CLI or raw.githubusercontent.com)
- HAPI FHIR core: `hapifhir/hapi-fhir`
- HAPI JPA starter: `hapifhir/hapi-fhir-jpaserver-starter`

## Example Resource Tests (PH eReferral)

### Script

`tests/test_phereferral.py` — tests PHeRef examples against PHeRef-capable servers.

### Run

```bash
# From repo root
python3 tests/test_phereferral.py
python3 tests/test_phereferral.py --base-url http://localhost:8080/fhir
python3 tests/test_phereferral.py --base-url https://cdr.pheref.fhirlab.net/fhir
python3 tests/test_phereferral.py --base-url https://fhirportal.telehealth.ph/PHeRef/fhir
```

### What it does

- Loads 32 example FHIR resources from `PHeRef/testdata/examples/`
- **Phase 1** (Bundle): `POST` the transaction Bundle — resolves all `urn:uuid` cross-references to real resource IDs
- **Phase 2** (individual): `PUT` each resource with resolved references
- Falls back to dry-run (JSON validation only) if server unreachable
- Report: `reports/test-report-pheref-{domain}-{timestamp}.md`

## Example Resource Tests (PH Core)

### Script

`tests/test_phcore.py` — tests PH Core examples against PH Core-capable servers.

### Run

```bash
# From repo root
python3 tests/test_phcore.py
python3 tests/test_phcore.py --base-url http://localhost:8080/fhir
python3 tests/test_phcore.py --base-url https://cdr.phcore.fhirlab.net/fhir
python3 tests/test_phcore.py --base-url https://fhirportal.telehealth.ph/phcore/fhir
```

### What it does

- Loads 26 example FHIR resources from `PHeRef/testdata/ph-core-examples/` (sourced from PH Core IG build, filtered to Patient/Organization/Practitioner/PractitionerRole/Condition/Encounter/Observation profiles)
- **Phase 1** (Bundle): `POST` the transaction Bundles (ACS case + Single transaction) — creates core resources atomically
- **Phase 2** (individual): `PUT` each resource independently
- Falls back to dry-run (JSON validation only) if server unreachable
- Report: `reports/test-report-phcore-{domain}-{timestamp}.md`

### Notes

- PH Core examples use `ResourceType/ID` references (no `urn:uuid` placeholders). The bundle handles circular dependencies (Condition ↔ Encounter). Standalone resources may fail in a server that resolves all references eagerly — this is expected and captured in the report.
- `Organization/organization-pgh-example` and `Practitioner/practitioner-ed-example` are **excluded** from the test set — they contain PSGC codes (`1339000003`) not found in any tested terminology service. Their dependents (Patient/patient-acs, Encounter/encounter-ed, PractitionerRole/practitionerrole-ed) still reference them but pass because HAPI FHIR accepts dangling references on PUT. Adding PSGC support to the terminology service would allow restoring these files.
- `.env` keys for PH Core: `PH_CORE_SERVER_ADDRESS`, `PH_CORE_SERVER_PORT`

## Reports (common)

- Reports output to `reports/` (repo root, gitignored)
- Categorized error narratives with root cause explanations
- Comparison report: `reports/comparison.md` (manual, generated per-session)

## Run All Tests (batch)

```bash
# Interactive — prompts before clearing reports (default N, 5s timeout)
./tests/run_all_tests.sh
```

Runs all 6 test combos sequentially:
- `test_phereferral.py` → localhost, cdr.pheref, fhirportal/PHeRef
- `test_phcore.py`     → localhost, cdr.phcore, fhirportal/phcore
