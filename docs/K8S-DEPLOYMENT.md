# Kubernetes Deployment Guide

This document is addressed to the agent implementing the Kubernetes deployment.
It captures the fully-working Docker Compose configuration for both FHIR servers,
every known HAPI v8.10.0 bug and its workaround, the critical post-startup seeding
step, and the test procedure. Read it completely before writing any manifests.

---

## 1. What You Are Deploying

Two independent FHIR R4 servers built on the **stock** `hapiproject/hapi:v8.10.0-1` image
(no custom build). Do not use any custom image — the stock image is the requirement.

| Server | Directory | Purpose | IGs loaded |
|--------|-----------|---------|------------|
| **PHeRef** | `PHeRef/` | PH eReferral FHIR server | `fhir.ph.core` v0.2.0, `fhir.ph.ereferral` v0.1.0, `hl7.fhir.uv.extensions.r4` v5.3.0, `hl7.terminology.r4` v6.2.0 |
| **Ph-core** | `Ph-core/` | PH Core FHIR server | `fhir.ph.core` v0.2.0, `hl7.fhir.uv.extensions.r4` v5.3.0, `hl7.terminology.r4` v6.2.0 |

Both use PostgreSQL 14 as the database backend. The servers are independent and do not
communicate with each other.

---

## 2. Critical HAPI v8.10.0 Bugs and Workarounds

These are NOT optional. Each one will prevent the server from starting or cause test
failures if omitted.

### 2a. OnDSTU2Condition NPE at Spring component scan

**Symptom:** Server crashes immediately on startup with:
```
Cannot invoke "String.toUpperCase()" because getProperty("hapi.fhir.fhir_version") returned null
```
**Root cause:** Spring's `OnDSTU2Condition` checks `hapi.fhir.fhir_version` during component
scanning, before the external YAML config (`file:/app/config/`) has been loaded. The property
is null at that point.

**Fix:** Set the env var `HAPI_FHIR_FHIR_VERSION: R4` on the container. Spring's
`SystemEnvironmentPropertySource` maps this to `hapi.fhir.fhir_version` early enough to
satisfy the condition check before YAML loads.

### 2b. Flyway Postgres version incompatibility

**Symptom:** Server crashes with:
```
org.flywaydb.core.api.exception.FlywayException: Unsupported Database: PostgreSQL 14.x
```
**Root cause:** The Flyway version bundled in HAPI v8.10.0 does not recognise PostgreSQL 14
(or 15). Hibernate can manage the schema directly without Flyway.

**Fix:** Set env var `SPRING_FLYWAY_ENABLED: "false"`. Hibernate's DDL auto-management
creates and updates the schema instead.

### 2c. ImplementationGuide referential integrity crash

**Symptom:** Server crashes during IG installation with:
```
HAPI-1286: Error installing IG fhir.ph.core#0.2.0:
Resource HealthcareService/healthcareservice-single-example not found,
specified in path: ImplementationGuide.definition.resource.reference
```
**Root cause:** When HAPI installs an `ImplementationGuide` resource, it checks that every
resource referenced in `IG.definition.resource.reference` exists in the database. The IGs
reference example resources that are not included in the installed resource types.

**Fix:** Do **not** include `ImplementationGuide` in `installResourceTypes` for any IG entry.
The current `application.yaml` files already exclude it. See Section 4 for full config.

### 2d. DNS failure on Ubuntu systemd-resolved hosts (Docker Compose only)

**Symptom:** Remote terminology service calls silently fail. Codes from `v3-RoleCode`,
`observation-category`, LOINC, and SNOMED are returned as "Unknown code" even though a
remote terminology service is configured. All terminology validation passes silently.

**Root cause:** Ubuntu's systemd-resolved stub resolver listens on `127.0.0.53`, which is
unreachable from inside Docker containers. Containers inherit the host's `resolv.conf` and
cannot reach `tx.fhirlab.net` or any other external hostname.

**Fix (Docker Compose):** `dns: [8.8.8.8, 8.8.4.4]` on the HAPI service.

**Fix (Kubernetes):** **This problem does not exist in K8S.** Kubernetes pods have their own
working DNS (`kube-dns` / `CoreDNS`) and can reach external hostnames without any special
configuration. Do not add any DNS override in K8S manifests.

### 2e. UCUM regression — HAPI Issue #7796 (post-startup seeding required)

**Symptom:** UCUM unit codes (e.g. `mm[Hg]`, `kg/m2`, `Cel`) fail validation with
"Code not found in http://unitsofmeasure.org" even though UCUM is an algorithmic system.

**Root cause:** HAPI v8.10.0 ships a classpath UCUM stub with `content: not-present`. The
terminology module (TRM) intercepts UCUM validation, finds the stub, and returns "code not
found" instead of falling through to the algorithmic UCUM validator.

**Fix:** After the server is ready, PUT a `content: fragment` CodeSystem at URL
`http://unitsofmeasure.org` to the server. This overrides the classpath stub. The fragment
lists only the UCUM codes used by the Philippine IGs — any code not in the fragment is
not considered invalid (per `content: fragment` semantics).

The file is at `PHeRef/ucum-fragment.json` and `Ph-core/ucum-fragment.json` (identical).

**This must be done after every fresh database start.** The fragment is stored in the DB.
If the DB volume is wiped, it must be re-seeded. In K8S, implement this as a Job or
post-startup hook — see Section 6.

### 2f. Draft-status StructureDefinition installation

**Symptom:** Profile validation silently passes for all resources because no profile
constraints are loaded. HAPI skips any `StructureDefinition`, `ValueSet`, or `CodeSystem`
with `status: draft`.

**Root cause:** `fhir.ph.core` and `fhir.ph.ereferral` ship their resources with
`status: draft`.

**Fix:** `validate_resource_status_for_package_upload: false` in `application.yaml`.
Already set in both server configs.

---

## 3. Required Environment Variables

These must be set on the HAPI container. They are not in the YAML config because they
are needed before the YAML is parsed.

| Variable | Value | Purpose |
|----------|-------|---------|
| `SPRING_CONFIG_LOCATION` | `file:/app/config/` | Tells Spring Boot where the external YAML is mounted |
| `SPRING_MAIN_ALLOW_CIRCULAR_REFERENCES` | `"true"` | Required by HAPI's JPA context wiring |
| `HAPI_FHIR_FHIR_VERSION` | `R4` | Prevents OnDSTU2Condition NPE (bug 2a above) |
| `SPRING_FLYWAY_ENABLED` | `"false"` | Disables Flyway migration (bug 2b above) |

In K8S, set these in the container's `env:` block.

---

## 4. Configuration Files

Both configuration files (`application.yaml` and `mdm-rules.json`) must be mounted into
the container at `/app/config/`. In K8S, use a `ConfigMap` mounted at `/app/config/`.

### 4a. PHeRef — `application.yaml`

Full working content (as committed in `PHeRef/config/application.yaml`):

```yaml
spring:
  main:
    allow-circular-references: true
  datasource:
    url: jdbc:postgresql://db:5432/hapi
    username: admin
    password: admin
    driverClassName: org.postgresql.Driver
  jpa:
    properties:
      hibernate.dialect: ca.uhn.fhir.jpa.model.dialect.HapiFhirPostgresDialect
      hibernate.search.enabled: true
      hibernate.search.backend.type: lucene
      hibernate.search.backend.analysis.configurer: ca.uhn.fhir.jpa.search.HapiHSearchAnalysisConfigurers$HapiLuceneAnalysisConfigurer
      hibernate.search.backend.directory.type: local-filesystem
      hibernate.search.backend.directory.root: /app/target/lucene_indexes
      hibernate.search.schema_management.strategy: CREATE

hapi:
  fhir:
    fhir_version: R4
    tester:
      home:
        name: PH eReferral FHIR Server
        server_address: 'http://localhost:8080/fhir'
        refuse_to_fetch_third_party_urls: false
        fhir_version: R4
    mdm_enabled: true
    mdm_rules_enabled: true
    mdm_config_json: file:/app/config/mdm-rules.json
    validate_resource_status_for_package_upload: false
    enable_repository_validating_interceptor: false
    enforce_referential_integrity_on_write: true
    validation:
      requests_enabled: true
      responses_enabled: false
    subscription:
      resthook_enabled: true
      websocket_enabled: false
      email_enabled: false
    openapi_enabled: false
    implementationguides:
      ph_core:
        name: fhir.ph.core
        version: 0.2.0
        reloadExisting: false
        installMode: STORE_AND_INSTALL
        packageUrl: https://fhirhub.telehealth.ph/IG/PH-Core/package.tgz
        fetchDependencies: false
        installResourceTypes:
          - StructureDefinition
          - SearchParameter
          - NamingSystem
          - Subscription
          # ImplementationGuide intentionally excluded — see bug 2c
      ph_eref:
        name: fhir.ph.ereferral
        version: 0.1.0
        reloadExisting: false
        installMode: STORE_AND_INSTALL
        packageUrl: https://fhirhub.telehealth.ph/IG/PH-eReferral/package.tgz
        fetchDependencies: true
        installResourceTypes:
          - StructureDefinition
          - SearchParameter
          - NamingSystem
          - Subscription
          # ImplementationGuide intentionally excluded — see bug 2c
        dependencyExcludes:
          - "hl7.fhir.uv.extensions"
          - "hl7.fhir.uv.extensions.r4"
          - hl7.fhir.uv.extensions.r5
          - "hl7.terminology.r5"
          - "fhir.ph.core"
      hl7_extensions_r4:
        name: hl7.fhir.uv.extensions.r4
        version: 5.3.0
        reloadExisting: false
        installMode: STORE_AND_INSTALL
        fetchDependencies: true
        installResourceTypes:
          - StructureDefinition
          - SearchParameter
          # ImplementationGuide intentionally excluded — see bug 2c
        dependencyExcludes:
          - "hl7.terminology.r5"
          - "hl7.terminology.r4"
      hl7_terminology_r4:
        name: hl7.terminology.r4
        version: 6.2.0
        reloadExisting: false
        installMode: STORE_AND_INSTALL
        fetchDependencies: false
        installResourceTypes:
          - CodeSystem
          - ValueSet
    logical_urls:
      - http://terminology.hl7.org/*
      - https://terminology.hl7.org/*
      - http://snomed.info/*
      - https://snomed.info/*
      - http://unitsofmeasure.org/*
      - https://unitsofmeasure.org/*
      - http://loinc.org/*
      - https://loinc.org/*
    remote_terminology_service:
      loinc:
        system: "http://loinc.org"
        url: "https://tx.fhirlab.net/fhir"
      snomed:
        system: "https://snomed.info/sct"
        url: "https://tx.fhirlab.net/fhir"
      phcw:
        system: "https://fhir.doh.gov.ph/phcore/CodeSystem/PHCW"
        url: "https://tx.fhirlab.net/fhir"
      psoc:
        system: "https://fhir.doh.gov.ph/phcore/CodeSystem/PSOC"
        url: "https://tx.fhirlab.net/fhir"
      psced-level:
        system: "https://psa.gov.ph/classification/psced/level"
        url: "https://tx.fhirlab.net/fhir"
      psgc:
        system: "https://psa.gov.ph/classification/psgc"
        url: "https://tx.fhirlab.net/fhir"
      psoc-unit:
        system: "https://psa.gov.ph/classification/psoc/unit"
        url: "https://tx.fhirlab.net/fhir"
      ucum:
        system: "http://unitsofmeasure.org"
        url: "https://tx.fhir.org/r4"
      all:
        system: '*'
        url: 'https://tx.fhirlab.net/fhir'
```

**Important:** The `datasource.url` uses the hostname `db`. In K8S, change this to the
PostgreSQL Service hostname (e.g. `jdbc:postgresql://pheref-db:5432/hapi` or the cluster
DNS name of your PostgreSQL service). The username and password should come from a Secret.

### 4b. Ph-core — `application.yaml`

Full working content (as committed in `Ph-core/config/application.yaml`):

```yaml
spring:
  main:
    allow-circular-references: true
  datasource:
    url: jdbc:postgresql://db:5432/hapi
    username: admin
    password: admin
    driverClassName: org.postgresql.Driver
  jpa:
    properties:
      hibernate.dialect: ca.uhn.fhir.jpa.model.dialect.HapiFhirPostgresDialect
      hibernate.search.enabled: true
      hibernate.search.backend.type: lucene
      hibernate.search.backend.analysis.configurer: ca.uhn.fhir.jpa.search.HapiHSearchAnalysisConfigurers$HapiLuceneAnalysisConfigurer
      hibernate.search.backend.directory.type: local-filesystem
      hibernate.search.backend.directory.root: /app/target/lucene_indexes
      hibernate.search.schema_management.strategy: CREATE

hapi:
  fhir:
    fhir_version: R4
    tester:
      home:
        name: PH Core FHIR Server
        server_address: 'http://localhost:8080/fhir'
        refuse_to_fetch_third_party_urls: false
        fhir_version: R4
    mdm_enabled: true
    mdm_rules_enabled: true
    mdm_config_json: file:/app/config/mdm-rules.json
    validate_resource_status_for_package_upload: false
    enable_repository_validating_interceptor: false
    enforce_referential_integrity_on_write: true
    validation:
      requests_enabled: true
      responses_enabled: false
    subscription:
      resthook_enabled: true
      websocket_enabled: false
      email_enabled: false
    openapi_enabled: false
    implementationguides:
      ph_core:
        name: fhir.ph.core
        version: 0.2.0
        reloadExisting: false
        installMode: STORE_AND_INSTALL
        packageUrl: https://fhirhub.telehealth.ph/IG/PH-Core/package.tgz
        fetchDependencies: false
        installResourceTypes:
          - StructureDefinition
          - SearchParameter
          - NamingSystem
          - Subscription
          # ImplementationGuide intentionally excluded — see bug 2c
      hl7_extensions_r4:
        name: hl7.fhir.uv.extensions.r4
        version: 5.3.0
        reloadExisting: false
        installMode: STORE_AND_INSTALL
        fetchDependencies: true
        installResourceTypes:
          - StructureDefinition
          - SearchParameter
          # ImplementationGuide intentionally excluded — see bug 2c
        dependencyExcludes:
          - "hl7.terminology.r5"
          - "hl7.terminology.r4"
      hl7_terminology_r4:
        name: hl7.terminology.r4
        version: 6.2.0
        reloadExisting: false
        installMode: STORE_AND_INSTALL
        fetchDependencies: false
        installResourceTypes:
          - CodeSystem
          - ValueSet
    logical_urls:
      - http://terminology.hl7.org/*
      - https://terminology.hl7.org/*
      - http://snomed.info/*
      - https://snomed.info/*
      - http://unitsofmeasure.org/*
      - https://unitsofmeasure.org/*
      - http://loinc.org/*
      - https://loinc.org/*
    remote_terminology_service:
      loinc:
        system: "http://loinc.org"
        url: "https://tx.fhirlab.net/fhir"
      snomed:
        system: "http://snomed.info/sct"
        url: "https://tx.fhirlab.net/fhir"
      ucum:
        system: "http://unitsofmeasure.org"
        url: "https://tx.fhir.org/r4"
      all:
        system: '*'
        url: 'https://tx.fhirlab.net/fhir'
```

### 4c. MDM rules

Both servers mount the same `mdm-rules.json` file from their respective `config/` directories
(`PHeRef/config/mdm-rules.json` and `Ph-core/config/mdm-rules.json`). Include it in the
same ConfigMap as `application.yaml`. HAPI loads it at `file:/app/config/mdm-rules.json`.

---

## 5. Database

Each server needs its own PostgreSQL 14 database. The servers must not share a database.

| Server | Database name | Default credentials |
|--------|--------------|---------------------|
| PHeRef | `hapi` | `admin` / `admin` |
| Ph-core | `hapi` | `admin` / `admin` |

The credentials are referenced in `application.yaml`. In K8S, override `spring.datasource.url`,
`spring.datasource.username`, and `spring.datasource.password` via environment variables
(`SPRING_DATASOURCE_URL`, `SPRING_DATASOURCE_USERNAME`, `SPRING_DATASOURCE_PASSWORD`) sourced
from a Secret, rather than hardcoding them in the ConfigMap.

**First-boot schema creation:** Hibernate creates all tables on first boot (`CREATE` DDL
strategy). No pre-seeding or migration scripts are needed. The database just needs to exist
and be reachable before HAPI starts.

**Startup ordering:** HAPI will crash on first connect if Postgres is not yet ready. Add a
readiness gate — either a Kubernetes `initContainer` that loops until `pg_isready` succeeds,
or configure a `startupProbe` that allows enough time for Postgres to become ready. In the
current Docker Compose setup, HAPI retries via `restart: unless-stopped` but that is not
reliable; use a proper init container in K8S.

---

## 6. UCUM Fragment — Post-Startup Seeding (Critical)

After the HAPI server is ready (i.e. GET `/fhir/metadata` returns 200), a one-time PUT
request must be made to seed the UCUM fragment. This fixes bug 2e.

The UCUM fragment JSON is committed at `PHeRef/ucum-fragment.json` and
`Ph-core/ucum-fragment.json` (files are identical). Content:

```json
{
  "resourceType": "CodeSystem",
  "id": "ucum-fragment",
  "url": "http://unitsofmeasure.org",
  "version": "2.1.1",
  "name": "UCUM",
  "title": "Unified Code for Units of Measure (fragment)",
  "status": "active",
  "content": "fragment",
  "concept": [
    { "code": "mm[Hg]", "display": "Millimeter of mercury" },
    { "code": "d",       "display": "Day" },
    { "code": "%",       "display": "Percent" },
    { "code": "1",       "display": "Dimensionless unit" },
    { "code": "Cel",     "display": "Degree Celsius" },
    { "code": "cm",      "display": "Centimeter" },
    { "code": "kg",      "display": "Kilogram" },
    { "code": "kg/m2",   "display": "Kilogram per square meter (BMI)" },
    { "code": "mg",      "display": "Milligram" },
    { "code": "mg/dL",   "display": "Milligram per deciliter" },
    { "code": "/min",    "display": "Per minute" },
    { "code": "mmol/L",  "display": "Millimole per liter" },
    { "code": "{tbl}",   "display": "Tablet" },
    { "code": "mL",      "display": "Milliliter" },
    { "code": "L",       "display": "Liter" },
    { "code": "g",       "display": "Gram" },
    { "code": "h",       "display": "Hour" },
    { "code": "wk",      "display": "Week" },
    { "code": "mo",      "display": "Month" },
    { "code": "a",       "display": "Year (365.25 d)" },
    { "code": "min",     "display": "Minute" },
    { "code": "s",       "display": "Second" }
  ]
}
```

**The seeding command:**
```bash
curl -s -X PUT "http://<hapi-host>/fhir/CodeSystem/ucum-fragment" \
  -H "Content-Type: application/json" \
  -d '<json above>'
```
Expected response: HTTP 201 (first seed) or HTTP 200 (re-seed after restart with existing DB).

**Recommended K8S implementation:** A Kubernetes `Job` with:
1. An `initContainer` using a minimal image (`curlimages/curl` or `busybox`) that polls
   `GET /fhir/metadata` until HTTP 200 is returned (HAPI is ready).
2. The main container that executes the PUT request.

The Job should be created as part of the same Helm chart or manifest set and should run
after the HAPI `Deployment` is applied. Use `kubectl wait --for=condition=available` on the
Deployment before creating the Job if your tooling supports ordering.

Store the UCUM JSON in a `ConfigMap` and mount it as a file in the Job container.

**The Job only needs to run once per fresh database.** If the DB is persistent and the UCUM
fragment was previously seeded, the PUT returns 200 and is a no-op. It is safe to re-run on
every pod restart.

---

## 7. Startup Sequence and Timing

First boot is slow because HAPI downloads and installs all IG packages from the internet.
Plan for at least **3–4 minutes** before the server is ready on first boot.

Subsequent boots (existing DB) take approximately 60–90 seconds.

**First-boot startup sequence:**
1. PostgreSQL becomes ready (schema will be created by Hibernate).
2. HAPI starts, connects to PostgreSQL, Hibernate creates the schema (~10s).
3. HAPI downloads IG packages from `fhirhub.telehealth.ph` (requires outbound HTTP).
4. HAPI installs StructureDefinitions, SearchParameters, etc. into the DB.
5. HAPI loads `hl7.terminology.r4` CodeSystems and ValueSets (large — ~60–90s additional).
6. HAPI initialises MDM rules, Lucene indexes, and the REST server.
7. Server begins accepting requests.
8. **UCUM seeding Job must run** (step 6 above).

**Readiness probe:** Use `GET /fhir/metadata` — returns 200 when HAPI is fully ready.
Set `initialDelaySeconds: 60`, `periodSeconds: 10`, `failureThreshold: 30` to accommodate
first-boot IG installation time.

**Liveness probe:** Same endpoint. Set `initialDelaySeconds: 120`, `periodSeconds: 30`,
`failureThreshold: 5`.

**Lucene indexes:** The application writes Lucene full-text indexes to
`/app/target/lucene_indexes`. In Docker Compose this is ephemeral (inside the container).
In K8S, mount a `PersistentVolumeClaim` at `/app/target/lucene_indexes` to survive pod
restarts and avoid reindexing on every restart. If you do not mount a PVC, the indexes
will be rebuilt from the database on every pod start (which works but adds ~30s to boot).

---

## 8. Outbound Network Requirements

HAPI requires outbound internet access for:

| Host | Purpose | When |
|------|---------|------|
| `fhirhub.telehealth.ph` | IG package downloads (`PH-Core/package.tgz`, `PH-eReferral/package.tgz`) | First boot only (packages cached in DB after install) |
| `packages.fhir.org` | HL7 Extensions R4 package download | First boot only |
| `tx.fhirlab.net` | Remote terminology validation (SNOMED, LOINC, PHCW, PSOC, PSGC) | Every coded resource validation |
| `tx.fhir.org` | UCUM terminology validation (fallback for codes not in fragment) | Coded resource validation |

If the cluster runs behind a restrictive egress policy, these four hosts must be
whitelisted.

---

## 9. Test Procedure

### 9a. PHeRef — `tests/run-bundle-test.py`

This is the primary test suite for PHeRef. It must be run from the repository root.

**Prerequisites:**
- Server up and passing readiness probe
- UCUM fragment seeded (Section 6)
- Python 3 available

**Command:**
```bash
cd /path/to/FHIR-Server
python3 tests/run-bundle-test.py
```

The script targets `http://localhost:8080/fhir/` by default. If the server is elsewhere,
edit `BASE_URL` at the top of the file.

**Expected results:** 20/21 PASS. The single known failure is:

| Test | ID | Reason |
|------|----|--------|
| `$validate reports errors for invalid resource` | F2 | `$validate` on a no-profile Patient returns `dom-6` at severity WARNING, not ERROR. Requires custom Java interceptor configuration not possible via YAML on the stock image. Deferred — will be addressed via a dashboard function. |

All other 20 tests must pass. Any additional failures indicate a configuration problem.

**What the test covers:**
- A4: Patient with unknown profile URL rejected (422) — tests `requests_enabled: true`
- A5–A7: Valid PH Core / eReferral patients and bundles accepted
- 1–4: Patient create and deduplication bundle transactions
- C1–C2: Edge cases
- E: No-match Practitioner (POST returns single resource, not Bundle)
- F1–F3: `$validate` endpoint accessible and functional
- G1–G2: Referential integrity (dangling references rejected, valid references accepted)
- H1: Response headers

### 9b. Both servers — `generate_eref_testing_report.py`

This root-level script runs 15 tests against a running server and produces Markdown, HTML,
and JSON reports.

**Command:**
```bash
cd /path/to/FHIR-Server
python3 generate_eref_testing_report.py http://<server-host>/fhir
```

**Expected results for PHeRef:** No ❌ results. Some ⚠️ are acceptable:
- Test 2 ⚠️: No IG resources listed (ImplementationGuide resources excluded from install — by design)
- Test 4 ⚠️: eReferral priority ValueSet not found (ValueSet install intentionally excluded)
- Test 5 ⚠️: eReferral workflow CodeSystem not found (same reason)
- Test 8 ⚠️: Patient accepted without profile (RVI disabled — by design)

**Expected results for Ph-core:** The following ❌ results are expected and acceptable
because the test uses eReferral-specific profile URLs that are not installed on Ph-core:
- Test 3 ❌: eReferral Patient profile not found (not installed on Ph-core)
- Test 6 ❌: Valid eReferral Patient validation fails (unknown profile on Ph-core)
- Test 9 ❌: Create eReferral Patient rejected (unknown profile on Ph-core)
- Test 13 ❌: ServiceRequest skipped (depends on test 9)

All other tests should be ✅ or ⚠️ for Ph-core.

---

## 10. K8S Resource Summary

For each server (PHeRef and Ph-core), you will need:

| Resource | Purpose |
|----------|---------|
| `ConfigMap` | `application.yaml` + `mdm-rules.json` + `ucum-fragment.json` |
| `Secret` | PostgreSQL credentials (username, password, JDBC URL) |
| `Deployment` | HAPI FHIR server pod |
| `Service` | Exposes HAPI on port 8080 within the cluster |
| `PersistentVolumeClaim` (optional but recommended) | Lucene index persistence at `/app/target/lucene_indexes` |
| `Job` | Post-startup UCUM fragment seeding |
| PostgreSQL | Either a `StatefulSet` + `Service` + `PersistentVolumeClaim`, or an existing managed database |

---

## 11. Docker Compose Reference (Working State)

The Docker Compose files in `PHeRef/docker-compose.yml` and `Ph-core/docker-compose.yml`
are the verified working reference. Use them as the source of truth for environment
variables, image versions, and volume mounts when writing K8S manifests.

**PHeRef** (`PHeRef/docker-compose.yml`):
```yaml
services:
  db:
    image: postgres:14
    container_name: eref-db
    environment:
      POSTGRES_DB: hapi
      POSTGRES_USER: admin
      POSTGRES_PASSWORD: admin
    volumes:
      - eref-db-data:/var/lib/postgresql/data
    ports:
      - "5433:5432"

  eref-hapi:
    image: "hapiproject/hapi:v8.10.0-1"
    container_name: eref-hapi
    depends_on:
      - db
    ports:
      - "${FHIR_SERVER_PORT:-8081}:8080"
    dns:
      - 8.8.8.8
      - 8.8.4.4
    environment:
      FHIR_SERVER_ADDRESS: "${FHIR_SERVER_ADDRESS:-http://localhost}"
      FHIR_SERVER_PORT: "${FHIR_SERVER_PORT:-8081}"
      SPRING_CONFIG_LOCATION: file:/app/config/
      SPRING_MAIN_ALLOW_CIRCULAR_REFERENCES: "true"
      HAPI_FHIR_FHIR_VERSION: R4
      SPRING_FLYWAY_ENABLED: "false"
    volumes:
      - ./config:/app/config
```

Note: `dns:` is Docker-specific for Ubuntu systemd-resolved hosts. **Remove it in K8S.**
Note: `FHIR_SERVER_ADDRESS` and `FHIR_SERVER_PORT` control the HAPI web UI's self-link only;
they do not affect the server's listening port (always 8080 inside the container).

**Ph-core** (`Ph-core/docker-compose.yml`):
```yaml
services:
  db:
    image: postgres:14
    container_name: phcore-db
    environment:
      POSTGRES_DB: hapi
      POSTGRES_USER: admin
      POSTGRES_PASSWORD: admin
    volumes:
      - phcore-db-data:/var/lib/postgresql/data
    ports:
      - "5432:5432"

  phcore-hapi:
    image: "hapiproject/hapi:v8.10.0-1"
    container_name: phcore-hapi
    depends_on:
      - db
    ports:
      - "8080:8080"
    dns:
      - 8.8.8.8
      - 8.8.4.4
    environment:
      SPRING_CONFIG_LOCATION: file:/app/config/
      SPRING_MAIN_ALLOW_CIRCULAR_REFERENCES: "true"
      HAPI_FHIR_FHIR_VERSION: R4
      SPRING_FLYWAY_ENABLED: "false"
    volumes:
      - ./config:/app/config
```

---

## 12. Verifying a Deployment

Run these checks in order after applying the K8S manifests:

```bash
# 1. HAPI metadata endpoint — confirms server is up
curl -s http://<host>/fhir/metadata | python3 -c "import sys,json; d=json.load(sys.stdin); print(d['fhirVersion'], d['software']['name'])"
# Expected: 4.0.1 HAPI FHIR Server

# 2. Confirm eReferral profile is installed (PHeRef only)
curl -s "http://<host>/fhir/StructureDefinition?url=https%3A%2F%2Ffhir.doh.gov.ph%2Fpheref%2FStructureDefinition%2Fereferral-patient&_summary=count" | python3 -c "import sys,json; d=json.load(sys.stdin); print('StructureDefs found:', d['total'])"
# Expected: 1

# 3. Confirm UCUM fragment is seeded
curl -s "http://<host>/fhir/CodeSystem/ucum-fragment" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d['content'], len(d['concept']), 'codes')"
# Expected: fragment 22 codes

# 4. Run the full test suite (PHeRef)
cd /path/to/FHIR-Server
BASE_URL=http://<host>/fhir/ python3 tests/run-bundle-test.py
# Expected: 20 PASS, 1 FAIL (F2 only)
```

If the UCUM check (step 3) fails or shows `content: not-present`, the seeding Job did not
run or failed. Re-run the seeding manually:
```bash
curl -s -X PUT "http://<host>/fhir/CodeSystem/ucum-fragment" \
  -H "Content-Type: application/json" \
  -d @PHeRef/ucum-fragment.json
```
