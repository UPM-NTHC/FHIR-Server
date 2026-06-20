# eReferral FHIR Server Testing Results — https://cdr.phcore.fhirlab.net/fhir

Generated: 2026-06-20T22:36:27.585643

## Critical Finding

**eReferral Patient profile is not loaded**

The server is alive, but it did not find the configured eReferral Patient StructureDefinition. Fix the eReferral IG package loading before relying on validation.

## Configuration

| Item | Value |
|---|---|
| Base URL | https://cdr.phcore.fhirlab.net/fhir |
| eReferral Patient Profile | https://fhir.doh.gov.ph/pheref/StructureDefinition/ereferral-patient |
| Priority ValueSet | https://fhir.doh.gov.ph/pheref/ValueSet/ereferral-priority |
| Workflow CodeSystem | https://fhir.doh.gov.ph/pheref/CodeSystem/ereferral-workflow |
| ServiceRequest Profile | Not set. Plain FHIR ServiceRequest used. |
| Keep Created Resources | True |

## Test Summary

| # | Test | Endpoint | HTTP | Expected | Actual | Finding | Log |
|---|---|---|---|---|---|---|---|
| 1 | Metadata | `GET /metadata` | 200 | CapabilityStatement | HAPI FHIR Server 4.0.1 | ✅ Server reachable | `logs/01-metadata.json` |
| 2 | ImplementationGuide list | `GET /ImplementationGuide` | 200 | IG resources visible | total=0 | ⚠️ No IG resources listed | `logs/02-implementationguide-list.json` |
| 3 | eReferral Patient profile | `GET /StructureDefinition?url=...` | 200 | Profile found | total=0 | ❌ Profile not found | `logs/03-eref-patient-profile-search.json` |
| 4 | eReferral priority ValueSet | `GET /ValueSet?url=...` | 200 | ValueSet found | total=0 | ⚠️ ValueSet not found | `logs/04-eref-priority-valueset-search.json` |
| 5 | eReferral workflow CodeSystem | `GET /CodeSystem?url=...` | 200 | CodeSystem found | total=0 | ⚠️ CodeSystem not found | `logs/05-eref-workflow-codesystem-search.json` |
| 6 | Validate valid eReferral Patient | `POST /Patient/$validate` | 422 | 0 errors | errors=2 warnings=0 | ❌ Review OperationOutcome | `logs/06-validate-eref-patient-valid.json` |
| 7 | Validate invalid eReferral Patient | `POST /Patient/$validate` | 422 | Should return errors | errors=2 warnings=1 | ✅ Invalid patient detected | `logs/07-validate-eref-patient-invalid.json` |
| 8 | Create Patient without profile | `POST /Patient` | 201 | Blocked if interceptor requires profile | Patient/15659 | ⚠️ Accepted without profile | `logs/08-create-patient-no-profile.json` |
| 9 | Create eReferral Patient | `POST /Patient` | 422 | Created | Patient/not-created | ❌ Failed | `logs/09-create-eref-patient.json` |
| 10 | Create referring Organization | `POST /Organization` | 201 | Created | Organization/15660 | ✅ Created | `logs/10-create-referring-organization.json` |
| 11 | Create receiving Organization | `POST /Organization` | 201 | Created | Organization/15661 | ✅ Created | `logs/11-create-receiving-organization.json` |
| 12 | Create Practitioner | `POST /Practitioner` | 201 | Created | Practitioner/15662 | ✅ Created | `logs/12-create-practitioner.json` |
| 13 | Create referral ServiceRequest | `POST /ServiceRequest` | SKIPPED | Created | ServiceRequest/not-created | ❌ Failed or skipped | `logs/13-create-servicerequest-referral.json` |
| 14 | Search Patient by identifier | `GET /Patient?identifier=...` | 200 | total >= 1 | total=0 | ⚠️ Patient not found | `logs/14-search-patient-by-identifier.json` |
| 15 | Search ServiceRequest by Patient | `GET /ServiceRequest?subject=Patient/...` | SKIPPED | total >= 1 | total=0 | ⚠️ Referral not found | `logs/15-search-servicerequest-by-subject.json` |

## Important Raw Logs

### 01-metadata.json

```text
CapabilityStatement/4efc80a7-a09f-44c6-bc7b-df18b1c12f71
```

### 02-implementationguide-list.json

```text
Bundle type=searchset, total=0
```

### 03-eref-patient-profile-search.json

```text
Bundle type=searchset, total=0
```

### 04-eref-priority-valueset-search.json

```text
Bundle type=searchset, total=0
```

### 05-eref-workflow-codesystem-search.json

```text
Bundle type=searchset, total=0
```

### 06-validate-eref-patient-valid.json

```text
ERROR: Profile reference 'https://fhir.doh.gov.ph/pheref/StructureDefinition/ereferral-patient' has not been checked because it could not be found, and the validator is set to not fetch unknown profiles
ERROR: Invalid profile. Failed to retrieve profile with url=https://fhir.doh.gov.ph/pheref/StructureDefinition/ereferral-patient
```

### 07-validate-eref-patient-invalid.json

```text
WARNING: Constraint failed: dom-6: 'A resource should have narrative for robust management' (defined in http://hl7.org/fhir/StructureDefinition/DomainResource) (Best Practice Recommendation)
ERROR: Profile reference 'https://fhir.doh.gov.ph/pheref/StructureDefinition/ereferral-patient' has not been checked because it could not be found, and the validator is set to not fetch unknown profiles
ERROR: Invalid profile. Failed to retrieve profile with url=https://fhir.doh.gov.ph/pheref/StructureDefinition/ereferral-patient
```

### 08-create-patient-no-profile.json

```text
Patient/15659
```

### 09-create-eref-patient.json

```text
ERROR: Profile reference 'https://fhir.doh.gov.ph/pheref/StructureDefinition/ereferral-patient' has not been checked because it could not be found, and the validator is set to not fetch unknown profiles
ERROR: Invalid profile. Failed to retrieve profile with url=https://fhir.doh.gov.ph/pheref/StructureDefinition/ereferral-patient
```

### 10-create-referring-organization.json

```text
Organization/15660
```

### 11-create-receiving-organization.json

```text
Organization/15661
```

### 12-create-practitioner.json

```text
Practitioner/15662
```

### 13-create-servicerequest-referral.json

```text
ERROR: Skipped because Patient, Practitioner, or receiving Organization was not created.
```

### 14-search-patient-by-identifier.json

```text
Bundle type=searchset, total=0
```

### 15-search-servicerequest-by-subject.json

```text
ERROR: Skipped because Patient was not created.
```

## Files

- Summary JSON: `eref-testing-results-20260620-223612/summary.json`
- Markdown report: `eref-testing-results-20260620-223612/eref-testing-results.md`
- HTML report: `eref-testing-results-20260620-223612/eref-testing-results.html`
- Payloads: `eref-testing-results-20260620-223612/payloads/`
- Logs: `eref-testing-results-20260620-223612/logs/`