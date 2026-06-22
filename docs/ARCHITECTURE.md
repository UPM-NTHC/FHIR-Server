# Architecture Documentation

## System Overview

This repository contains two FHIR R4 server deployments for the Philippine National Telehealth Center (NTHC), both built on [HAPI FHIR JPA Server Starter](https://github.com/hapifhir/hapi-fhir-jpaserver-starter):

- **Ph-core** — Philippine Core FHIR server hosting the PH Core Implementation Guide
- **PHeRef** — Philippine eReferral FHIR server hosting both PH Core and PH eReferral IGs

Each deployment is a self-contained Docker Compose stack with its own PostgreSQL database, Lucene full-text index, and HAPI FHIR JPA application.

## Deployment Architecture

```mermaid
C4Context
    title System Context — PH FHIR Server Platform

    Person(clinician, "Clinician", "Referring/receiving healthcare worker")
    Person(admin, "System Admin", "Deploys and manages FHIR servers")

    System_Boundary(platform, "FHIR Server Platform") {
        System(phcore, "Ph-core FHIR Server", "HAPI FHIR R4 — PH Core IG<br/>localhost:8080")
        System(pheref, "PHeRef FHIR Server", "HAPI FHIR R4 — PH eReferral IG<br/>localhost:8081")
    }

    System_Ext(ontoserver, "Ontoserver (tx.fhirlab.net)", "Remote terminology service<br/>SNOMED CT, LOINC, PSGC, PSOC, PHCW")
    System_Ext(txfhirorg, "tx.fhir.org", "HL7 terminology service<br/>UCUM validation")
    System_Ext(fhirhub, "FHIRHub (fhirhub.telehealth.ph)", "IG package registry<br/>PH Core & PH eReferral packages")

    Rel(clinician, pheref, "Creates referrals, queries patients", "FHIR REST API")
    Rel(clinician, phcore, "Registers patients, manages records", "FHIR REST API")
    Rel(phcore, ontoserver, "Validates terminology", "FHIR $validate-code")
    Rel(pheref, ontoserver, "Validates terminology", "FHIR $validate-code")
    Rel(pheref, txfhirorg, "UCUM validation", "FHIR $validate-code")
    Rel(phcore, fhirhub, "Downloads IG packages", "HTTP GET (startup)")
    Rel(pheref, fhirhub, "Downloads IG packages", "HTTP GET (startup)")
```

## Container Architecture

```mermaid
C4Container
    title Container Diagram — Docker Compose Stacks

    Container_Boundary(phcore_stack, "Ph-core Stack (port 8080/5432)") {
        Container(phcore_app, "phcore-hapi", "Java 17 / Spring Boot / HAPI FHIR", "FHIR R4 server with PH Core IG")
        ContainerDb(phcore_db, "phcore-db", "PostgreSQL 15", "FHIR resource storage")
    }

    Container_Boundary(pheref_stack, "PHeRef Stack (port 8081/5433)") {
        Container(pheref_app, "eref-hapi", "Java 17 / Spring Boot / HAPI FHIR", "FHIR R4 server with PH Core + eReferral IGs")
        ContainerDb(pheref_db, "eref-db", "PostgreSQL 15", "FHIR resource storage")
    }

    Rel(phcore_app, phcore_db, "JDBC", "jdbc:postgresql://db:5432/hapi")
    Rel(pheref_app, pheref_db, "JDBC", "jdbc:postgresql://db:5432/hapi")
```

## Implementation Guide Dependency

```mermaid
graph TD
    subgraph "HL7 Base"
        FHIR_R4["HL7 FHIR R4<br/>(base spec)"]
        EXT_R4["hl7.fhir.uv.extensions.r4<br/>v5.3.0"]
    end

    subgraph "Philippine National IGs"
        PH_CORE["fhir.ph.core<br/>v0.2.0"]
        PH_EREF["fhir.ph.ereferral<br/>v0.1.0"]
    end

    subgraph "Server Deployments"
        PHCORE_SERVER["Ph-core Server<br/>:8080"]
        PHEREF_SERVER["PHeRef Server<br/>:8081"]
    end

    PH_CORE --> FHIR_R4
    PH_CORE --> EXT_R4
    PH_EREF --> PH_CORE
    PH_EREF --> EXT_R4

    PHCORE_SERVER --> PH_CORE
    PHCORE_SERVER --> EXT_R4

    PHEREF_SERVER --> PH_CORE
    PHEREF_SERVER --> PH_EREF
    PHEREF_SERVER --> EXT_R4
```

## Terminology Resolution

Both servers delegate terminology validation to external terminology services rather than hosting CodeSystem/ValueSet expansions locally. This keeps the servers lightweight and ensures terminology is always current.

```mermaid
flowchart LR
    subgraph "FHIR Server"
        VAL["Validation Engine"]
    end

    subgraph "Remote Terminology"
        ONTO["Ontoserver<br/>tx.fhirlab.net/fhir"]
        TX["tx.fhir.org/r4"]
    end

    VAL -->|"SNOMED CT"| ONTO
    VAL -->|"LOINC"| ONTO
    VAL -->|"PSGC, PSOC, PHCW,<br/>PSCED-Level"| ONTO
    VAL -->|"UCUM"| TX
```

**Terminology routing (PHeRef):**

| System | Route |
|--------|-------|
| SNOMED CT (`https://snomed.info/sct`) | Ontoserver |
| LOINC (`http://loinc.org`) | Ontoserver |
| PSGC (`https://psa.gov.ph/classification/psgc`) | Ontoserver |
| PSOC (`https://fhir.doh.gov.ph/phcore/CodeSystem/PSOC`) | Ontoserver |
| PHCW (`https://fhir.doh.gov.ph/phcore/CodeSystem/PHCW`) | Ontoserver |
| UCUM (`http://unitsofmeasure.org`) | tx.fhir.org |

**Ph-core** uses a wildcard route — all terminology systems go to Ontoserver.

## Master Data Management (MDM)

Both servers run HAPI's MDM module for patient deduplication using Philippine national identifiers.

```mermaid
flowchart TD
    subgraph "Incoming Patient"
        PAT["Patient Resource"]
    end

    subgraph "MDM Matching Pipeline"
        CAND["Candidate Search<br/>identifier / family+birthdate"]
        MATCH["Match Rules"]
    end

    subgraph "Match Outcomes"
        AUTO["AUTO MATCH<br/>(Golden Record linked)"]
        POSS["POSSIBLE MATCH<br/>(Manual review)"]
        NEW["NO MATCH<br/>(New Golden Record)"]
    end

    PAT --> CAND
    CAND --> MATCH
    MATCH -->|"PSA National ID match<br/>OR PhilHealth ID match"| AUTO
    MATCH -->|"Family name + Birthdate match"| POSS
    MATCH -->|"No match found"| NEW
```

**MDM matching rules:**

| Field | Identifier System | Algorithm | Result |
|-------|-------------------|-----------|--------|
| PSA National ID | `https://psa.gov.ph/philid` | IDENTIFIER (exact) | MATCH |
| PhilHealth ID | `https://philhealth.gov.ph` | IDENTIFIER (exact) | MATCH |
| Family Name + Birth Date | — | STRING + DATE | POSSIBLE_MATCH |

**EID System:** `https://psa.gov.ph/philid` (Philippine Identification System)

## eReferral Workflow — Resource Model

```mermaid
classDiagram
    class Patient {
        +Identifier[] identifier
        +HumanName[] name
        +code gender
        +date birthDate
        +ContactPoint[] telecom
        +Address[] address
        meta.profile: ereferral-patient
    }

    class Practitioner {
        +Identifier[] identifier
        +HumanName[] name
        PRC License Number
    }

    class Organization {
        +Identifier[] identifier
        +string name
        DOH Facility Code
    }

    class ServiceRequest {
        +code status
        +code intent
        +code priority
        +CodeableConcept category
        +Reference subject
        +Reference requester
        +Reference[] performer
        +date authoredOn
        +CodeableConcept[] reasonCode
        category: referral
    }

    ServiceRequest --> Patient : subject
    ServiceRequest --> Practitioner : requester
    ServiceRequest --> Organization : performer (receiving)
    Practitioner --> Organization : affiliated with (referring)
```

## Validation Pipeline

```mermaid
flowchart TD
    REQ["Incoming FHIR Request<br/>(POST /Patient)"] --> REPO_VAL

    subgraph "HAPI Validation Stack"
        REPO_VAL["Repository Validating Interceptor<br/>(enable_repository_validating_interceptor: true)"]
        REPO_VAL --> PROFILE["Profile Validation<br/>(StructureDefinition constraints)"]
        PROFILE --> REF_INT["Referential Integrity Check<br/>(enforce_referential_integrity_on_write: true)"]
        REF_INT --> TERM["Terminology Validation<br/>(remote tx service)"]
    end

    TERM --> STORE["Resource Persisted to PostgreSQL"]

    REQ2["POST /Patient/$validate"] --> VALIDATE_OP["$validate Operation<br/>(always available)"]
    VALIDATE_OP --> OO["OperationOutcome<br/>(errors/warnings)"]
```

## Network Port Mapping

```mermaid
flowchart LR
    subgraph "Host Network"
        P8080["localhost:8080"]
        P5432["localhost:5432"]
        P8081["localhost:8081"]
        P5433["localhost:5433"]
    end

    subgraph "Ph-core Containers"
        PHCORE_HAPI["phcore-hapi<br/>:8080"]
        PHCORE_DB["phcore-db<br/>:5432"]
    end

    subgraph "PHeRef Containers"
        EREF_HAPI["eref-hapi<br/>:8080"]
        EREF_DB["eref-db<br/>:5432"]
    end

    P8080 --> PHCORE_HAPI
    P5432 --> PHCORE_DB
    P8081 --> EREF_HAPI
    P5433 --> EREF_DB
```

## Repository Structure

```
FHIR-Server/
├── Ph-core/                    # PH Core FHIR server
│   ├── docker-compose.yml      # Stack: phcore-hapi + phcore-db
│   ├── Dockerfile              # Multi-stage build (Maven → distroless)
│   ├── pom.xml                 # HAPI FHIR JPA dependencies
│   ├── config/
│   │   ├── application.yaml    # Server config, IG loading, terminology
│   │   └── mdm-rules.json     # Patient deduplication rules
│   └── src/                    # Java sources and tests
├── PHeRef/                     # PH eReferral FHIR server
│   ├── docker-compose.yml      # Stack: eref-hapi + eref-db
│   ├── .env                    # PHEREF_SERVER_ADDRESS, PHEREF_SERVER_PORT
│   ├── Dockerfile              # Multi-stage build (Maven → distroless)
│   ├── pom.xml                 # HAPI FHIR JPA dependencies
│   ├── config/
│   │   ├── application.yaml    # Server config, IG loading, terminology
│   │   └── mdm-rules.json     # Patient deduplication rules
│   └── src/                    # Java sources and tests
├── tests/
│   └── run-bundle-test.py      # Bundle transaction test script
├── docs/
│   ├── ARCHITECTURE.md         # This document
│   └── TESTING.md              # Test script documentation
├── generate_eref_testing_report.py     # eReferral test suite (Python)
└── generate_eref_testing_report_v2.sh  # eReferral test suite (Bash, legacy)
```

## Key Configuration Differences

| Aspect | Ph-core | PHeRef |
|--------|---------|--------|
| Host port (FHIR) | 8080 | 8081 |
| Host port (PostgreSQL) | 5432 | 5433 |
| Implementation Guides | PH Core, HL7 Extensions R4 | PH Core, PH eReferral, HL7 Extensions R4 |
| Terminology routing | Wildcard → Ontoserver | Per-system routing (Ontoserver + tx.fhir.org) |
| Container name | phcore-hapi | eref-hapi |
| Port configurable via .env | No | Yes (`PHEREF_SERVER_PORT`) |
| IG dependency fetching | `fetchDependencies: true` | Selective (`false` for PH Core, `true` for eRef) |
| Access logging | Disabled | Enabled (structured, `fhirtest.access`) |

## Access Logging

PHeRef has structured per-request access logging enabled via HAPI's `LoggingInterceptor`. Each FHIR request produces a log line with operational metadata suitable for statistical accounting and debugging.

```mermaid
flowchart LR
    REQ["Incoming FHIR Request"] --> LI["LoggingInterceptor"]
    LI --> LOG["Logger: fhirtest.access"]
    LOG --> STDOUT["Container stdout<br/>(docker logs)"]
```

**Logged fields:**

| Field | Description |
|-------|-------------|
| `verb` | HTTP method (GET, POST, PUT, DELETE) |
| `path` | Servlet path (e.g. `/fhir/Patient`) |
| `op` | FHIR operation type (read, search, create, etc.) |
| `opName` | Named operation (e.g. `$validate`) |
| `resource` | Resource type or ID |
| `remoteAddr` | Client IP address |
| `forwardedFor` | X-Forwarded-For header (proxy/load balancer) |
| `userAgent` | Client User-Agent header |
| `requestId` | Unique request identifier |
| `params` | Query/search parameters |
| `processingMs` | Server processing time in milliseconds |

**Error logging** is also enabled — failed requests additionally capture `exceptionMessage`.

**Note:** Ph-core does not currently have the logger enabled. The logger configuration exists in the HAPI starter codebase but is commented out in Ph-core's `application.yaml`.

## Build Pipeline

```mermaid
flowchart TD
    subgraph "Multi-stage Docker Build"
        SRC["Source Code + pom.xml"]
        SRC --> MVN["Maven Build Stage<br/>(eclipse-temurin-17)"]
        MVN --> |"dependency:go-offline"| DEPS["Cached Dependencies"]
        DEPS --> COMPILE["mvn clean install -DskipTests"]
        COMPILE --> REPACKAGE["spring-boot:repackage -Pboot"]
        REPACKAGE --> WAR["ROOT.war"]
    end

    subgraph "Runtime Image"
        WAR --> DISTROLESS["gcr.io/distroless/java21<br/>(nonroot, uid 65532)"]
        DISTROLESS --> ENTRYPOINT["PropertiesLauncher<br/>+ OpenTelemetry agent"]
    end
```

## Startup Sequence

```mermaid
sequenceDiagram
    participant DC as Docker Compose
    participant DB as PostgreSQL
    participant HAPI as HAPI FHIR Server
    participant HUB as FHIRHub (IG Registry)
    participant TX as Ontoserver

    DC->>DB: Start container
    DC->>HAPI: Start container (depends_on: db)
    HAPI->>DB: JDBC connection + Hibernate schema init
    HAPI->>HUB: Download PH Core package.tgz
    HAPI->>HUB: Download PH eReferral package.tgz (PHeRef only)
    HAPI->>HUB: Download HL7 Extensions R4 package
    HAPI->>HAPI: Install StructureDefinitions, SearchParameters
    HAPI->>HAPI: Initialize MDM rules
    HAPI->>HAPI: Build Lucene indexes
    Note over HAPI: Server ready — accepting requests
    HAPI->>TX: Terminology validation (on first coded resource)
```
