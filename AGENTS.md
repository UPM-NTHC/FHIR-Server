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

## Example Resource Tests

### Location

Test script lives at the **repo root** `tests/test_examples.py` (moved from `PHeRef/tests/`).

All resources (examples, reports, config) remain under `PHeRef/`.

### Run tests against FHIR server

```bash
# From repo root — uses .env (PHEREF_SERVER_ADDRESS + PHEREF_SERVER_PORT) by default
python3 tests/test_examples.py

# From repo root — specify any target server
python3 tests/test_examples.py --base-url http://localhost:8080/fhir
python3 tests/test_examples.py --base-url https://cdr.pheref.fhirlab.net/fhir
python3 tests/test_examples.py --base-url https://fhirportal.telehealth.ph/PHeRef/fhir

# From inside PHeRef/ — one level deeper
cd PHeRef
python3 ../tests/test_examples.py
```

### What it does

- Loads 32 example FHIR resources from `PHeRef/testdata/examples/`
- **Phase 1** (Bundle): `POST` the transaction Bundle — resolves all `urn:uuid` cross-references to real resource IDs
- **Phase 2** (individual): `PUT` each resource with resolved references — verifies every resource is independently loadable
- Falls back to dry-run (JSON structure validation only) if server is unreachable
- Generates a domain-labeled markdown report

### Reports

- Output: `PHeRef/reports/test-report-{domain}-{timestamp}.md`
  - e.g. `test-report-localhost-2026-06-21T021210Z.md`
  - e.g. `test-report-cdr.pheref.fhirlab.net-2026-06-21T021236Z.md`
  - e.g. `test-report-fhirportal.telehealth.ph-2026-06-21T021218Z.md`
- Reports include categorized error narratives with root cause explanations
- Report directory (`PHeRef/reports/`) is gitignored — local only
- Comparison report: `PHeRef/reports/comparison.md` (manual, generated per-session)
