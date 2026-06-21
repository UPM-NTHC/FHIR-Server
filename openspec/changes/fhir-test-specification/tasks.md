# Tasks

## 1. PH eReferral Test Script (`test_phereferral.py`)
- [x] 1.1 Renamed from `test_examples.py` to `test_phereferral.py`
- [x] 1.2 Updated docstring and report labels to "PH eReferral"
- [x] 1.3 Report filename prefix: `test-report-pheref-{domain}-{ts}.md`
- [x] 1.4 `.env` keys: `PHEREF_SERVER_ADDRESS`, `PHEREF_SERVER_PORT`

## 2. PH Core Test Script (`test_phcore.py`)
- [x] 2.1 Created with same two-phase structure (Bundle → PUT)
- [x] 2.2 Default examples dir: `PHeRef/testdata/ph-core-examples/`
- [x] 2.3 Report label: "PH Core Example Test Report"
- [x] 2.4 Report filename prefix: `test-report-phcore-{domain}-{ts}.md`
- [x] 2.5 `.env` keys: `PH_CORE_SERVER_ADDRESS`, `PH_CORE_SERVER_PORT`
- [x] 2.6 Added `missing_profile` error category

## 3. PH Core Examples
- [x] 3.1 Copied 45 example JSONs from PH Core IG build output
- [x] 3.2 Narrowed to 7 target profiles: Patient, Organization, Practitioner, PractitionerRole, Condition, Encounter, Observation
- [x] 3.3 Removed 19 non-target resource files
- [x] 3.4 Removed 8 files failing on localhost (PSGC terminology issues + removed dependency types)

## 4. Dependency Ordering (PH Core)
- [x] 4.1 `_collect_refs()` — recursively extract all `ResourceType/ID` references from JSON
- [x] 4.2 `build_dependency_map()` — build dependency graph from reference analysis
- [x] 4.3 `_find_cycles()` — Tarjan's SCC algorithm for detecting circular deps
- [x] 4.4 `resolve_put_order()` — topological sort with cycle separation
- [x] 4.5 Inline Bundle POST for circular Condition ↔ Encounter pairs
- [x] 4.6 Loading strategy printed to CLI: "Dependency order: {N} resources linearly, {M} group(s)"

## 5. Report Enhancement (PH Core)
- [x] 5.1 Loading Strategy section in generated markdown report
- [x] 5.2 `linear_count` and `circular_count` parameters in `generate_markdown()`
- [x] 5.3 Updated docstring describing loading strategy

## 6. Batch Runner
- [x] 6.1 Created `tests/run_all_tests.sh`
- [x] 6.2 Interactive prompt with 5s timeout (default N) for clearing reports
- [x] 6.3 TTY detection for clean non-interactive pipe mode
- [x] 6.4 Runs all 6 test combos sequentially
- [x] 6.5 Reports overall duration
- [x] 6.6 Listed in AGENTS.md

## 7. Documentation
- [x] 7.1 AGENTS.md updated with separate usage docs for each script
- [x] 7.2 PH Core notes about `ResourceType/ID` references and circular deps
- [x] 7.3 Batch runner documented

## 8. Reports Directory
- [x] 8.1 Moved from `PHeRef/reports/` to repo root `reports/`
- [x] 8.2 Both scripts updated to point to root `reports/`
- [x] 8.3 `.gitignore` already covers root `reports/`
