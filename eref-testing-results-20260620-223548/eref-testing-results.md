# eReferral FHIR Server Testing Results — https://cdr.pheref.fhirlab.net/fhir

Generated: 2026-06-20T22:36:07.075995

## Critical Finding

**Basic eReferral flow appears working**

The server was reachable, the eReferral Patient profile was checked, and the script created Patient, Organization, Practitioner, and ServiceRequest test resources.

## Configuration

| Item | Value |
|---|---|
| Base URL | https://cdr.pheref.fhirlab.net/fhir |
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
| 3 | eReferral Patient profile | `GET /StructureDefinition?url=...` | 200 | Profile found | total=1 | ✅ Profile found | `logs/03-eref-patient-profile-search.json` |
| 4 | eReferral priority ValueSet | `GET /ValueSet?url=...` | 200 | ValueSet found | total=0 | ⚠️ ValueSet not found | `logs/04-eref-priority-valueset-search.json` |
| 5 | eReferral workflow CodeSystem | `GET /CodeSystem?url=...` | 200 | CodeSystem found | total=0 | ⚠️ CodeSystem not found | `logs/05-eref-workflow-codesystem-search.json` |
| 6 | Validate valid eReferral Patient | `POST /Patient/$validate` | 200 | 0 errors | errors=0 warnings=0 | ✅ No validation errors | `logs/06-validate-eref-patient-valid.json` |
| 7 | Validate invalid eReferral Patient | `POST /Patient/$validate` | 422 | Should return errors | errors=3 warnings=1 | ✅ Invalid patient detected | `logs/07-validate-eref-patient-invalid.json` |
| 8 | Create Patient without profile | `POST /Patient` | 201 | Blocked if interceptor requires profile | Patient/15659 | ⚠️ Accepted without profile | `logs/08-create-patient-no-profile.json` |
| 9 | Create eReferral Patient | `POST /Patient` | 201 | Created | Patient/15660 | ✅ Created | `logs/09-create-eref-patient.json` |
| 10 | Create referring Organization | `POST /Organization` | 201 | Created | Organization/15661 | ✅ Created | `logs/10-create-referring-organization.json` |
| 11 | Create receiving Organization | `POST /Organization` | 201 | Created | Organization/15662 | ✅ Created | `logs/11-create-receiving-organization.json` |
| 12 | Create Practitioner | `POST /Practitioner` | 201 | Created | Practitioner/15663 | ✅ Created | `logs/12-create-practitioner.json` |
| 13 | Create referral ServiceRequest | `POST /ServiceRequest` | 201 | Created | ServiceRequest/15666 | ✅ Created | `logs/13-create-servicerequest-referral.json` |
| 14 | Search Patient by identifier | `GET /Patient?identifier=...` | 200 | total >= 1 | total=1 | ✅ Patient searchable | `logs/14-search-patient-by-identifier.json` |
| 15 | Search ServiceRequest by Patient | `GET /ServiceRequest?subject=Patient/...` | 200 | total >= 1 | total=1 | ✅ Referral searchable | `logs/15-search-servicerequest-by-subject.json` |

## Important Raw Logs

### 01-metadata.json

```text
CapabilityStatement/5738aaf3-10c3-40ac-a95c-d2d101b4f77b
```

### 02-implementationguide-list.json

```text
Bundle type=searchset, total=0
```

### 03-eref-patient-profile-search.json

```text
Bundle type=searchset, total=1
- StructureDefinition/6020
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
INFORMATION: This element does not match any known slice defined in the profile https://fhir.doh.gov.ph/pheref/StructureDefinition/ereferral-patient|0.1.0 (this may not be a problem, but you should check that it's not intended to match a slice) - Does not match slice 'PHCorePhilHealthID' (discriminator: ('http://philhealth.gov.ph/fhir/Identifier/philhealth-id' in system))
INFORMATION: This element does not match any known slice defined in the profile https://fhir.doh.gov.ph/pheref/StructureDefinition/ereferral-patient|0.1.0 (this may not be a problem, but you should check that it's not intended to match a slice) - Does not match slice 'PHCorePhilSysID' (discriminator: ('http://philsys.gov.ph/fhir/Identifier/philsys-id' in system))
INFORMATION: This element does not match any known slice defined in the profile https://fhir.doh.gov.ph/pheref/StructureDefinition/ereferral-patient|0.1.0 (this may not be a problem, but you should check that it's not intended to match a slice) - Does not match slice 'PHCorePhilHealthID' (discriminator: ('http://philhealth.gov.ph/fhir/Identifier/philhealth-id' in system))
INFORMATION: This element does not match any known slice defined in the profile https://fhir.doh.gov.ph/pheref/StructureDefinition/ereferral-patient|0.1.0 (this may not be a problem, but you should check that it's not intended to match a slice) - Does not match slice 'PHCorePhilSysID' (discriminator: ('http://philsys.gov.ph/fhir/Identifier/philsys-id' in system))
INFORMATION: This element does not match any known slice defined in the profile https://fhir.doh.gov.ph/pheref/StructureDefinition/ereferral-patient|0.1.0 (this may not be a problem, but you should check that it's not intended to match a slice) - Does not match slice 'PHCorePhilHealthID' (discriminator: ('http://philhealth.gov.ph/fhir/Identifier/philhealth-id' in system))
INFORMATION: This element does not match any known slice defined in the profile https://fhir.doh.gov.ph/pheref/StructureDefinition/ereferral-patient|0.1.0 (this may not be a problem, but you should check that it's not intended to match a slice) - Does not match slice 'PHCorePhilSysID' (discriminator: ('http://philsys.gov.ph/fhir/Identifier/philsys-id' in system))
INFORMATION: This element does not match any known slice defined in the profile https://fhir.doh.gov.ph/pheref/StructureDefinition/ereferral-patient|0.1.0 (this may not be a problem, but you should check that it's not intended to match a slice) - Does not match slice 'PHCorePhilHealthID' (discriminator: ('http://philhealth.gov.ph/fhir/Identifier/philhealth-id' in system))
INFORMATION: This element does not match any known slice defined in the profile https://fhir.doh.gov.ph/pheref/StructureDefinition/ereferral-patient|0.1.0 (this may not be a problem, but you should check that it's not intended to match a slice) - Does not match slice 'PHCorePhilSysID' (discriminator: ('http://philsys.gov.ph/fhir/Identifier/philsys-id' in system))
```

### 07-validate-eref-patient-invalid.json

```text
ERROR: Patient.name: minimum required = 1, but only found 0 (from https://fhir.doh.gov.ph/pheref/StructureDefinition/ereferral-patient|0.1.0)
ERROR: Patient.gender: minimum required = 1, but only found 0 (from https://fhir.doh.gov.ph/pheref/StructureDefinition/ereferral-patient|0.1.0)
ERROR: Patient.birthDate: minimum required = 1, but only found 0 (from https://fhir.doh.gov.ph/pheref/StructureDefinition/ereferral-patient|0.1.0)
WARNING: Constraint failed: dom-6: 'A resource should have narrative for robust management' (defined in http://hl7.org/fhir/StructureDefinition/DomainResource) (Best Practice Recommendation)
```

### 08-create-patient-no-profile.json

```text
Patient/15659
```

### 09-create-eref-patient.json

```text
Patient/15660
```

### 10-create-referring-organization.json

```text
Organization/15661
```

### 11-create-receiving-organization.json

```text
Organization/15662
```

### 12-create-practitioner.json

```text
Practitioner/15663
```

### 13-create-servicerequest-referral.json

```text
ServiceRequest/15666
```

### 14-search-patient-by-identifier.json

```text
Bundle type=searchset, total=1
- Patient/15660
```

### 15-search-servicerequest-by-subject.json

```text
Bundle type=searchset, total=1
- ServiceRequest/15666
```

## Files

- Summary JSON: `eref-testing-results-20260620-223548/summary.json`
- Markdown report: `eref-testing-results-20260620-223548/eref-testing-results.md`
- HTML report: `eref-testing-results-20260620-223548/eref-testing-results.html`
- Payloads: `eref-testing-results-20260620-223548/payloads/`
- Logs: `eref-testing-results-20260620-223548/logs/`