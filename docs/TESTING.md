# eReferral FHIR Server Testing Documentation

## Overview

This test suite validates an **eReferral FHIR R4 server** implementation built on HAPI FHIR. It exercises the server's ability to:

- Serve its CapabilityStatement (conformance)
- Host eReferral-specific FHIR conformance resources (StructureDefinitions, ValueSets, CodeSystems)
- Validate Patient resources against the eReferral Patient profile
- Enforce profile requirements via server interceptors
- Support RESTful CRUD operations for the core eReferral workflow resources
- Enable search by identifier and resource references

The test simulates an end-to-end eReferral flow: registering a patient, creating the referring/receiving organizations, a practitioner, and finally a ServiceRequest representing the referral itself.

## Prerequisites

- **HAPI FHIR R4 server** with the Philippine eReferral Implementation Guide loaded
- **Python 3.9+** (stdlib only — no pip dependencies required)
- **curl** (used by the legacy bash version; Python version uses urllib)
- Docker Compose stacks running (see `eRef/docker-compose.yml`)

## Usage

### Python version (recommended)

```bash
python3 generate_eref_testing_report.py [BASE_URL]
```

### Bash version (legacy)

```bash
bash generate_eref_testing_report_v2.sh [BASE_URL]
```

### Examples

```bash
# Default: http://localhost:8081/fhir
python3 generate_eref_testing_report.py

# Custom URL
python3 generate_eref_testing_report.py http://fhir.example.org/fhir

# With environment overrides
KEEP_CREATED=false \
SERVICE_REQUEST_PROFILE_URL="https://fhir.doh.gov.ph/pheref/StructureDefinition/ereferral-servicerequest" \
python3 generate_eref_testing_report.py
```

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `KEEP_CREATED` | `true` | Whether to retain test resources on the server after the run |
| `SERVICE_REQUEST_PROFILE_URL` | *(empty)* | If set, the ServiceRequest will include this in `meta.profile` |
| `EREF_PATIENT_PROFILE_URL` | `https://fhir.doh.gov.ph/pheref/StructureDefinition/ereferral-patient` | eReferral Patient profile canonical URL |
| `EREF_PRIORITY_VS_URL` | `https://fhir.doh.gov.ph/pheref/ValueSet/ereferral-priority` | eReferral priority ValueSet canonical URL |
| `EREF_WORKFLOW_CS_URL` | `https://fhir.doh.gov.ph/pheref/CodeSystem/ereferral-workflow` | eReferral workflow CodeSystem canonical URL |
| `CONNECT_TIMEOUT` | `3` | TCP connection timeout in seconds |
| `MAX_TIME` | `20` | Maximum total request time in seconds |

## Test Coverage

### Test 1 — CapabilityStatement

**Endpoint:** `GET /metadata`

Retrieves the server's [CapabilityStatement](http://hl7.org/fhir/R4/capabilitystatement.html) resource. This is the FHIR conformance endpoint that describes the server's supported resources, operations, and search parameters. A successful response confirms the server is operational and speaking FHIR.

### Test 2 — ImplementationGuide Search

**Endpoint:** `GET /ImplementationGuide`

Searches for [ImplementationGuide](http://hl7.org/fhir/R4/implementationguide.html) resources on the server. An IG bundles profiles, extensions, terminology, and examples into a distributable package. Finding IG resources confirms the eReferral package metadata is published.

### Test 3 — eReferral Patient StructureDefinition

**Endpoint:** `GET /StructureDefinition?url=<eref-patient-profile-url>`

Searches for the eReferral Patient [StructureDefinition](http://hl7.org/fhir/R4/structuredefinition.html) by its canonical URL. This profile constrains the base FHIR Patient resource with Philippine eReferral-specific requirements (identifiers, mandatory fields). Its presence is required for profile-based validation.

### Test 4 — eReferral Priority ValueSet

**Endpoint:** `GET /ValueSet?url=<priority-vs-url>`

Searches for the eReferral priority [ValueSet](http://hl7.org/fhir/R4/valueset.html). ValueSets define allowed coded values — in this case, the referral priority levels (routine, urgent, stat, etc.). Required for terminology validation.

### Test 5 — eReferral Workflow CodeSystem

**Endpoint:** `GET /CodeSystem?url=<workflow-cs-url>`

Searches for the eReferral workflow [CodeSystem](http://hl7.org/fhir/R4/codesystem.html). CodeSystems define the actual codes and their meanings. This CodeSystem captures the referral workflow states.

### Test 6 — Validate Conformant Patient

**Endpoint:** `POST /Patient/$validate`

Invokes the [$validate](http://hl7.org/fhir/R4/resource-operation-validate.html) operation with a Patient resource that conforms to the eReferral Patient profile. The server should return an OperationOutcome with zero errors, confirming the profile constraints are satisfied.

### Test 7 — Validate Non-Conformant Patient

**Endpoint:** `POST /Patient/$validate`

Submits a minimal Patient with only `meta.profile` declared but missing all required fields. The server should return validation errors, proving that profile enforcement is active and correctly identifying constraint violations.

### Test 8 — Create Patient Without Profile (Interceptor Test)

**Endpoint:** `POST /Patient`

Attempts to create a Patient resource that lacks `meta.profile`. If the server has a profile-enforcement interceptor configured, this should be rejected (HTTP 412 Precondition Failed). This tests server-side governance — ensuring only profiled resources are accepted.

### Test 9 — Create eReferral Patient

**Endpoint:** `POST /Patient`

Creates a fully conformant eReferral Patient. This tests the RESTful `create` interaction and confirms the server accepts profiled Patient resources. The returned ID is used in subsequent tests.

### Test 10 — Create Referring Organization

**Endpoint:** `POST /Organization`

Creates an [Organization](http://hl7.org/fhir/R4/organization.html) representing the referring health facility (e.g., a Barangay Health Center). Identified by DOH healthcare facility code.

### Test 11 — Create Receiving Organization

**Endpoint:** `POST /Organization`

Creates an Organization representing the receiving facility (e.g., a referral hospital). Both organizations are needed to establish the referral chain.

### Test 12 — Create Practitioner

**Endpoint:** `POST /Practitioner`

Creates a [Practitioner](http://hl7.org/fhir/R4/practitioner.html) representing the referring clinician, identified by PRC license number. This resource is referenced as the `requester` in the ServiceRequest.

### Test 13 — Create Referral ServiceRequest

**Endpoint:** `POST /ServiceRequest`

Creates a [ServiceRequest](http://hl7.org/fhir/R4/servicerequest.html) with `category=referral`, linking:
- `subject` → the Patient (test 9)
- `requester` → the Practitioner (test 12)
- `performer` → the receiving Organization (test 11)

This is the core eReferral transaction — a formal request to transfer care from one facility to another.

### Test 14 — Search Patient by Identifier

**Endpoint:** `GET /Patient?identifier=<value>`

Searches for the created Patient using the `identifier` search parameter. Validates that the server indexes and supports searching by business identifiers (PhilHealth number).

### Test 15 — Search ServiceRequest by Subject

**Endpoint:** `GET /ServiceRequest?subject=Patient/<id>`

Searches for ServiceRequests referencing the test Patient. Validates that reference-based search parameters work, enabling queries like "find all referrals for this patient."

## Output Files

Each run produces a timestamped folder `eref-testing-results-YYYYMMDD-HHMMSS/` containing:

| File | Description |
|------|-------------|
| `summary.json` | Machine-readable results with all test data and configuration |
| `eref-testing-results.md` | Human-readable Markdown report |
| `eref-testing-results.html` | Self-contained HTML report for browser viewing |
| `test-summary.tsv` | Tab-separated summary for spreadsheet import |
| `logs/*.json` | Raw FHIR JSON responses from each test |
| `logs/*.headers` | HTTP response headers |
| `logs/*.err` | Any connection errors |
| `payloads/*.json` | Request payloads sent to the server |

## Interpreting Results

### Symbols

| Symbol | Meaning |
|--------|---------|
| ✅ | Test passed — behavior matches expectations |
| ⚠️ | Warning — non-critical deviation (e.g., no IG listed, but server works) |
| ❌ | Failure — expected behavior not observed |

### Critical Finding Logic

The report highlights the most significant issue found, in priority order:

1. **Server not reachable** — metadata endpoint failed
2. **Profile not loaded** — StructureDefinition not found on server
3. **Validation errors on valid Patient** — profile or terminology misconfiguration
4. **ServiceRequest failed** — interceptor or reference issue
5. **All clear** — basic eReferral flow works

## FHIR Concepts Tested

### Profiling and StructureDefinitions

The test verifies that the server hosts custom [StructureDefinitions](http://hl7.org/fhir/R4/profiling.html) that constrain base FHIR resources for the Philippine eReferral use case. Profiles add mandatory fields, terminology bindings, and business rules beyond base FHIR.

### Terminology (ValueSet and CodeSystem)

Validates that the server hosts the terminology resources needed for coded data validation. CodeSystems define the universe of codes; ValueSets select subsets for use in specific contexts (e.g., referral priority).

### Validation ($validate Operation)

Tests the server's ability to check resources against declared profiles and return structured [OperationOutcome](http://hl7.org/fhir/R4/operationoutcome.html) responses listing constraint violations.

### RESTful CRUD Operations

Exercises the standard FHIR RESTful API: `create` (POST), `read` (GET), and `delete` (DELETE) interactions across multiple resource types.

### Search Parameters

Tests both token-based search (`identifier`) and reference-based search (`subject`), which are fundamental to locating resources in a FHIR server.

### Resource References

The ServiceRequest test validates that the server correctly handles inter-resource references (Patient, Practitioner, Organization linked via `reference` elements).

### Server Interceptors

Test 8 specifically validates custom server-side logic (HAPI interceptors) that enforce governance rules — in this case, requiring all Patient resources to declare a `meta.profile`.
