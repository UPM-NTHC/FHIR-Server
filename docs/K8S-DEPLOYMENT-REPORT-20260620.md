# K8S Deployment Report — PHeRef & Ph-core

**Date:** 2026-06-20  
**Cluster:** hapi-red-4 (EKS, ap-southeast-2)  
**Deployed by:** Kiro agent  
**Flux commit:** `89ce575` (main branch, hapi-fhir/flux repo)

---

## Servers Deployed

| Server | Namespace | URL | Status |
|--------|-----------|-----|--------|
| PH eReferral (PHeRef) | `hapifhir-pheref` | https://cdr.pheref.fhirlab.net/fhir | ✅ Running |
| PH Core | `hapifhir-phcore` | https://cdr.phcore.fhirlab.net/fhir | ✅ Running |

Both running HAPI FHIR v8.10.0 on FHIR R4 (`hapiproject/hapi:v8.10.0-1` stock image).

---

## Changes Made (vs previous config on main)

The following changes were required to align the running K8S deployments with the
specifications in `docs/K8S-DEPLOYMENT.md`:

### 1. Added `hl7_terminology_r4` IG (both servers)

**Why:** The deployment guide specifies that both servers install `hl7.terminology.r4` v6.2.0
with `CodeSystem` and `ValueSet` resource types. Without this, terminology validation relies
entirely on remote services — adding latency and creating a hard dependency on
`tx.fhirlab.net` availability for standard HL7 codes.

### 2. Added `enforce_referential_integrity_on_write: true` (both servers)

**Why:** Required by the test suite (tests G1/G2). Ensures resources with dangling references
(pointing to non-existent resources) are rejected at write time with HTTP 422.

### 3. Added `enable_repository_validating_interceptor: false` (both servers)

**Why:** Explicit declaration per K8S deployment guide. The Repository Validating Interceptor
would reject resources without valid profiles at persistence time — this is too strict for
the current use case where profiling is optional.

### 4. Fixed `ucum` remote_terminology_service system URL (PHeRef)

**Previous:** `system: "http://loinc.org"` (incorrect — routed LOINC validation to tx.fhir.org)  
**Fixed:** `system: "http://unitsofmeasure.org"` (correctly routes UCUM validation to tx.fhir.org)

### 5. Added `all` catch-all remote terminology service (PHeRef)

**Why:** The deployment guide specifies `all: { system: '*', url: 'https://tx.fhirlab.net/fhir' }`
as a fallback for any terminology system not explicitly listed. Without it, codes from
unlisted systems would fail validation silently.

### 6. Added UCUM fragment ConfigMaps + seeded via PUT (both servers)

**Why:** HAPI v8.10.0 bug #7796 — ships a `content: not-present` UCUM CodeSystem stub that
causes all UCUM code validations to fail. The fragment (22 codes used by PH IGs) overrides
this stub. Seeded via `PUT /fhir/CodeSystem/ucum-fragment`.

### 7. Fixed Ph-core `ph_core` fetchDependencies (false, not true)

**Why:** Ph-core should not fetch dependencies for ph_core IG — the dependencies
(`hl7.fhir.uv.extensions.r4`, `hl7.terminology.r4`) are listed as separate IG entries
with their own install configuration.

---

## Test Results

### PHeRef — `generate_eref_testing_report.py`

| # | Test | Result |
|---|------|--------|
| 1 | CapabilityStatement | ✅ |
| 2 | ImplementationGuide list | ⚠️ (by design — IG resource type excluded) |
| 3 | eReferral Patient profile | ✅ |
| 4 | eReferral priority ValueSet | ⚠️ (by design — ValueSet install excluded) |
| 5 | eReferral workflow CodeSystem | ⚠️ (by design — CodeSystem install excluded) |
| 6 | Validate valid eReferral Patient | ✅ |
| 7 | Validate invalid eReferral Patient | ✅ |
| 8 | Create Patient without profile | ⚠️ (by design — RVI disabled) |
| 9 | Create eReferral Patient | ✅ |
| 10 | Create referring Organization | ✅ |
| 11 | Create receiving Organization | ✅ |
| 12 | Create Practitioner | ✅ |
| 13 | Create referral ServiceRequest | ✅ |
| 14 | Search Patient by identifier | ✅ |
| 15 | Search ServiceRequest by Patient | ✅ |

**Verdict:** No ❌ failures. All ⚠️ are expected per deployment guide.

### PHeRef — `run-bundle-test.py`

16/17 PASS. Single failure:
- **H1** (response validation headers): FAIL — `responses_enabled: false` by design, so no
  `X-Validation-*` headers are present. This is a correct config choice (response validation
  adds latency to every read).

### Ph-core — `generate_eref_testing_report.py`

Expected ❌ on tests 3, 6, 9, 13 — these use eReferral-specific profile URLs that are not
installed on the Ph-core server (by design — it only carries ph-core IG). All other tests ✅/⚠️.

---

## Architecture Notes

- **Flux CD managed:** All configs are in `gitlab.com/.../hapi-fhir/flux.git` (main branch).
  Direct kubectl changes are reverted on reconciliation.
- **UCUM seeding:** Stored in DB (persistent). ConfigMap provided in Flux repo for reference
  bootstrap command only. Must be re-run if database is wiped.
- **hl7_terminology_r4:** Large IG (~60-90s install time on first boot). Subsequent boots
  use cached data from PostgreSQL.
- **Shared ALB:** Both servers share the cluster ALB via Ingress auto-discovery of ACM certs.
