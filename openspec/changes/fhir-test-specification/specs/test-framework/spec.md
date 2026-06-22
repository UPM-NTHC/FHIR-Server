# Delta for Test Framework

## ADDED Requirements

### Requirement: Dual-Script Architecture
The system SHALL provide two independent test scripts, one for each IG profile set.

#### Scenario: Run PHeRef tests
- GIVEN a FHIR server supporting PH eReferral profiles
- WHEN the user runs `python3 tests/test_phereferral.py --base-url <url>`
- THEN all 32 PHeRef example resources are tested
- AND results are recorded in a markdown report

#### Scenario: Run PH Core tests
- GIVEN a FHIR server supporting PH Core profiles
- WHEN the user runs `python3 tests/test_phcore.py --base-url <url>`
- THEN all PH Core example resources are tested
- AND results are recorded in a markdown report

#### Scenario: Default localhost target
- GIVEN no `--base-url` argument
- WHEN the user runs either script
- THEN the script reads `.env` for server address/port
- AND falls back to `http://localhost:8080/fhir` if `.env` is absent

### Requirement: Two-Phase Test Execution
The system SHALL execute tests in two phases: Bundle POST then individual PUT.

#### Scenario: Phase 1 — Bundle POST
- GIVEN a reachable server
- WHEN the test starts
- THEN Bundle files (prefixed with `Bundle-`) are POSTed as transaction Bundles
- AND `urn:uuid` cross-references are resolved to real server resource IDs

#### Scenario: Phase 2 — Individual PUT
- GIVEN resolved UUID mappings from Phase 1
- WHEN individual resources are PUT
- THEN `urn:uuid` references are replaced with real IDs
- AND each resource is PUT to `{base_url}/{ResourceType}/{id}`

### Requirement: Dependency-Ordered Loading (PH Core)
The system SHALL load PH Core resources in dependency order to satisfy cross-references.

#### Scenario: Topological sort
- GIVEN a set of PH Core resource files
- WHEN the dependency graph is analyzed
- THEN resources with no dependencies are PUT first
- AND resources depending on already-loaded resources are PUT next

#### Scenario: Circular dependency resolution
- GIVEN a circular dependency (Condition ↔ Encounter)
- WHEN the cycle is detected via Tarjan's SCC algorithm
- THEN the cycle members are POSTed as an inline transaction Bundle
- AND remaining resources are PUT linearly

#### Scenario: Unresolvable references
- GIVEN a resource referencing a resource type not in the test set
- WHEN that resource is PUT
- THEN it fails with a missing-prerequisite error
- AND the failure is captured in the report

### Requirement: Dry-Run Mode
The system SHALL fall back to JSON validation when the server is unreachable.

#### Scenario: Server unreachable
- GIVEN an unreachable server
- WHEN the test runs
- THEN all JSON files are validated for structural correctness
- AND a message indicates dry-run mode

#### Scenario: Structural validation
- GIVEN a JSON file
- WHEN validated in dry-run mode
- THEN `resourceType` is present
- AND JSON is parseable
- AND Bundles report their entry count

### Requirement: Markdown Reports
The system SHALL generate timestamped, domain-labeled markdown reports.

#### Scenario: Report filename
- GIVEN a test run against `https://cdr.phcore.fhirlab.net/fhir`
- WHEN the report is generated
- THEN the filename SHALL be `test-report-phcore-cdr.phcore.fhirlab.net-{timestamp}.md`

#### Scenario: Report contents
- GIVEN a completed test run
- WHEN the report is generated
- THEN it contains a result table with resource, method, URL, status, time, pass/fail
- AND an analysis section with categorized errors and root cause narratives
- AND timing statistics

#### Scenario: Report location
- GIVEN a test run
- WHEN the report is generated
- THEN it is written to `reports/` at the repository root

### Requirement: Loading Strategy Documentation
The system SHALL document its loading strategy in both CLI output and the generated report.

#### Scenario: CLI dependency summary
- GIVEN a PH Core test run
- WHEN dependency analysis completes
- THEN the CLI prints `Dependency order: {N} resources linearly, {M} circular group(s) ({K} resources via Bundles)`

#### Scenario: Report loading strategy section
- GIVEN a generated PH Core report
- WHEN the report is opened
- THEN it includes a "Loading Strategy" section describing the ordering approach

### Requirement: Batch Execution
The system SHALL provide a batch runner script for executing all test combinations.

#### Scenario: Run all tests
- GIVEN the batch runner
- WHEN `echo "y" | ./tests/run_all_tests.sh` is executed
- THEN all 6 test combos run sequentially (PHeRef × 3 servers + PH Core × 3 servers)
- AND reports are generated for each

#### Scenario: Report clearing prompt
- GIVEN an interactive terminal
- WHEN the batch runner starts
- THEN it prompts "Clear reports folder (excluding comparison.md)? [y/N]" with 5s timeout
- AND defaults to N if no input

#### Scenario: Non-interactive mode
- GIVEN a piped input
- WHEN the batch runner receives input via pipe
- THEN it reads the answer silently without showing the prompt banner

### Requirement: PHeRef — urn:uuid Resolution
The PHeRef test SHALL resolve `urn:uuid` temporary identifiers from Bundle responses.

#### Scenario: Build UUID map
- GIVEN a successful Bundle POST response
- WHEN response entries contain `location` fields
- THEN a mapping from `urn:uuid:{request fullUrl}` to `ResourceType/{response ID}` is built

#### Scenario: Replace references
- GIVEN a UUID map
- WHEN individual resources contain `urn:uuid:` references
- THEN those references are replaced with the real `ResourceType/ID` values
- AND the modified resource is PUT to the server

### Requirement: PH Core — Profile-Narrowed Examples
The PH Core test SHALL only include examples for the 7 target profiles.

#### Scenario: Filtered example set
- GIVEN the PH Core examples directory
- WHEN the test loads resources
- THEN only Patient, Organization, Practitioner, PractitionerRole, Condition, Encounter, and Observation resources are included
- AND no other resource types are tested

### Requirement: Error Categorization
The system SHALL categorize test failures into actionable groups.

#### Scenario: Terminology errors
- GIVEN a failure with "Unable to validate code" or "Unknown code" or "CodeSystem"
- WHEN errors are categorized
- THEN it is labeled "Terminology / Code Validation"

#### Scenario: Missing prerequisite errors
- GIVEN a failure with "not found, specified in path"
- WHEN errors are categorized
- THEN it is labeled "Missing Prerequisite Resource"

#### Scenario: Unresolved UUID reference
- GIVEN a failure with "urn:uuid" or "Invalid resource reference"
- WHEN errors are categorized
- THEN it is labeled "Unresolved Bundle-Scoped Reference (urn:uuid)"

#### Scenario: Missing profile errors
- GIVEN a failure with "could not be found" or "Failed to retrieve profile" or "Profile reference"
- WHEN errors are categorized
- THEN it is labeled "Missing Profile / StructureDefinition"

#### Scenario: Endpoint not found
- GIVEN a 404 response
- WHEN errors are categorized
- THEN it is labeled "Endpoint Not Found (404)"

#### Scenario: Timeout errors
- GIVEN a timeout exception
- WHEN errors are categorized
- THEN it is labeled "Request Timeout"

### Requirement: Error Narrative Generation
The system SHALL generate human-readable root cause narratives from categorized errors.

#### Scenario: Narrative per category
- GIVEN categorized errors
- WHEN the report is generated
- THEN each active category includes a narrative explaining the root cause
- AND lists affected resources

### Requirement: Environment Configuration
The system SHALL support environment-specific configuration via `.env` file.

#### Scenario: PHeRef env vars
- GIVEN a `.env` file with `PHEREF_SERVER_ADDRESS` and `PHEREF_SERVER_PORT`
- WHEN running `test_phereferral.py` without `--base-url`
- THEN the URL is constructed from these values

#### Scenario: PH Core env vars
- GIVEN a `.env` file with `PH_CORE_SERVER_ADDRESS` and `PH_CORE_SERVER_PORT`
- WHEN running `test_phcore.py` without `--base-url`
- THEN the URL is constructed from these values
