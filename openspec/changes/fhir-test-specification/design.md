# Design: FHIR Conformance Test Framework

## Architecture

```
tests/
├── test_phereferral.py       # PHeRef: 32 resources, Bundle + urn:uuid resolution
├── test_phcore.py            # PH Core: 18 resources, dependency-ordered + inline Bundles
└── run_all_tests.sh          # Batch runner for all 6 test combos

PHeRef/
└── testdata/
    ├── examples/              # 32 PHeRef example resources
    └── ph-core-examples/      # 18 PH Core example resources (7 profiles)

reports/                       # Generated markdown reports (gitignored)
└── comparison.md              # Manual cross-server comparison
```

## Test Runner Pattern (shared across both scripts)

```
┌─────────────────────────────────────────────────────────┐
│                  Test Runner                             │
│                                                         │
│  1. Resolve base URL (--base-url > .env > localhost)    │
│  2. Check server reachable (/metadata)                  │
│  3. Separate Bundle-* files from individual files       │
│  4. Phase 1: POST Bundle(s) → resolve UUIDs            │
│  5. Phase 2: PUT individual resources                   │
│  6. Generate markdown report                            │
└─────────────────────────────────────────────────────────┘
```

## PH Core Dependency Ordering

```
┌──────────────────────────────────────────────────────────┐
│  build_dependency_map(file_paths)                        │
│    → known_ids: set of "ResourceType/id"                 │
│    → dep_map: { res_id → {dep_res_id, ...} }            │
│                                                          │
│  _find_cycles(dep_map) — Tarjan's SCC algorithm          │
│    → list of strongly connected components (size > 1)    │
│                                                          │
│  resolve_put_order(file_paths)                           │
│    → (linear_order, circular_groups)                     │
│      - linear_order: topological sort of acyclic nodes   │
│      - circular_groups: [[paths for cycle, ...]]         │
│                                                          │
│  Main: POST inline Bundles for circular groups           │
│        PUT linear_order in dependency order              │
└──────────────────────────────────────────────────────────┘
```

## Report Generation

```
TestResult { name, resource_type, method, url, status, response_time, success, errors[] }

generate_markdown(results, ...)
  → Header (date, server, pass rate overview)
  → Loading Strategy section (PH Core only)
  → Result table (all resources with status)
  → Error Breakdown table (category → count → affected resources)
  → Root Cause Narratives (per category)
  → Failures Detail (per failing resource)
  → Timing (total, fastest, slowest, average)
```

## Data Flow

```
Client (CLI) → Test Script → FHIR Server (REST API)
                              ↓
                        Response/Errors
                              ↓
                    TestResult objects
                              ↓
                    generate_markdown()
                              ↓
                    reports/*.md
```
