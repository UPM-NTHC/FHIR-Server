# FHIR Implementation Guide Validation Implementation Guide

## System Administrator Documentation

### Project Overview
This document describes the implementation of a HAPI FHIR REST API server with FHIR Implementation Guide (IG) validation for PH Core and PH e-Referral profiles.

---

## Table of Contents
1. [Architecture](#architecture)
2. [Technology Stack](#technology-stack)
3. [Implementation Steps](#implementation-steps)
4. [File Structure](#file-structure)
5. [Configuration Details](#configuration-details)
6. [Validation Logic](#validation-logic)
7. [Deployment](#deployment)
8. [Testing](#testing)
9. [Troubleshooting](#troubleshooting)

---

## Architecture

### System Components
- **HAPI FHIR REST Server**: RESTful API for FHIR R4 resources
- **Resource Providers**: Handle CRUD operations for Patient and ServiceRequest
- **FHIR Validator**: Validates resources against FHIR standards and IG profiles
- **Docker Containerization**: Application and database deployment

### Data Flow
1. Client sends POST request with FHIR resource
2. Resource Provider receives request
3. Validation checks:
   - Presence of `meta.profile` field
   - Exact case-sensitive match of profile URL
   - FHIR schema validation
4. If validation passes, resource is stored
5. If validation fails, 422 Unprocessable Entity error returned

---

## Technology Stack

### Backend
- **Java 17**
- **Spring Boot 3.2.0**
- **HAPI FHIR 7.0.2** (R4)
- **Maven** (build tool)

### Dependencies
```xml
- hapi-fhir-base: 7.0.2
- hapi-fhir-structures-r4: 7.0.2
- hapi-fhir-server: 7.0.2
- hapi-fhir-validation: 7.0.2
- hapi-fhir-validation-resources-r4: 7.0.2
- spring-boot-starter-web: 3.2.0
- spring-boot-starter-logging: 3.2.0
```

### Infrastructure
- **Docker & Docker Compose**
- **PostgreSQL** (database)
- **Tomcat** (embedded servlet container)

---

## Implementation Steps

### Step 1: Project Setup
Created Maven project with Spring Boot and HAPI FHIR dependencies.

### Step 2: FHIR Configuration
Created `FhirConfig.java` to provide:
- `FhirContext` bean (R4 version)
- `FhirValidator` bean for resource validation

### Step 3: Server Configuration
Created `FhirServerConfig.java` to:
- Configure RestfulServer
- Register resource providers
- Set up interceptors
- Map servlet to `/fhir/*`

### Step 4: Resource Providers
Created two resource providers:

#### PatientResourceProvider
- Handles Patient resource CRUD operations
- Validates `meta.profile` against PH Core Patient profile
- Uses in-memory storage (ConcurrentHashMap)

#### ServiceRequestResourceProvider
- Handles ServiceRequest resource CRUD operations
- Validates `meta.profile` against PH e-Referral ServiceRequest profile
- Uses in-memory storage (ConcurrentHashMap)

### Step 5: Validation Logic
Implemented strict validation:
1. Check if `meta` field exists
2. Check if `meta.profile` exists
3. Verify exact case-sensitive match of profile URL
4. Run FHIR schema validation
5. Reject with 422 error if any validation fails

### Step 6: Docker Deployment
Created:
- `Dockerfile`: Multi-stage build for Java application
- `docker-compose.yml`: Orchestrates application and PostgreSQL containers
- `application.yaml`: Application configuration

---

## File Structure

```
eref/
├── pom.xml                                    # Maven dependencies
├── Dockerfile                                 # Docker build configuration
├── docker-compose.yml                         # Container orchestration
├── application.yaml                           # Application configuration
├── mdm-rules.json                             # MDM rules (unused in current setup)
└── src/main/java/com/eref/
    ├── EreferralApplication.java              # Main Spring Boot application
    ├── config/
    │   ├── FhirConfig.java                    # FHIR context and validator beans
    │   ├── FhirServerConfig.java             # REST server configuration
    │   └── FhirValidationInterceptorAdapter.java # Validation interceptor
    ├── provider/
    │   ├── PatientResourceProvider.java      # Patient resource handler
    │   └── ServiceRequestResourceProvider.java # ServiceRequest resource handler
    └── interceptor/
        └── HL7ValidationInterceptor.java     # Legacy interceptor (unused)
```

---

## Configuration Details

### FhirConfig.java
```java
@Configuration
public class FhirConfig {
    @Bean
    public FhirContext fhirContext() {
        return FhirContext.forR4();
    }

    @Bean
    public FhirValidator fhirValidator(FhirContext fhirContext) {
        return fhirContext.newValidator();
    }
}
```

### FhirServerConfig.java
- Registers PatientResourceProvider
- Registers ServiceRequestResourceProvider
- Registers LoggingInterceptor
- Registers FhirValidationInterceptorAdapter
- Maps servlet to `/fhir/*`

### application.yaml
```yaml
server:
  port: 8080

spring:
  application:
    name: ereferral-server
```

---

## Validation Logic

### Profile URLs (Case-Sensitive)

#### Patient
- **Required URL**: `https://fhir.doh.gov.ph/phcore/StructureDefinition/ph-core-patient`
- **Validation**: Exact string match (case-sensitive)

#### ServiceRequest
- **Required URL**: `https://fhir.doh.gov.ph/ereferral/StructureDefinition/ereferral-service-request`
- **Validation**: Exact string match (case-sensitive)

### Validation Code Example
```java
String expectedProfile = "https://fhir.doh.gov.ph/phcore/StructureDefinition/ph-core-patient";
if (!thePatient.hasMeta() || !thePatient.getMeta().hasProfile()) {
    throw new UnprocessableEntityException("Patient validation failed: meta.profile is required");
}

boolean hasCorrectProfile = false;
for (UriType profile : thePatient.getMeta().getProfile()) {
    if (expectedProfile.equals(profile.getValue())) {
        hasCorrectProfile = true;
        break;
    }
}

if (!hasCorrectProfile) {
    throw new UnprocessableEntityException("Patient validation failed: meta.profile must be exactly " + expectedProfile);
}
```

---

## Deployment

### Build Docker Image
```bash
docker build -t hapi-custom:latest .
```

### Start Containers
```bash
docker-compose up -d
```

### View Logs
```bash
docker logs eref-hapi --tail 30
```

### Stop Containers
```bash
docker-compose down
```

---

## Testing

### Test Patient Creation (Valid)
```bash
curl -X POST http://localhost:8081/fhir/Patient \
  -H "Content-Type: application/json" \
  -d '{
    "resourceType": "Patient",
    "meta": {
      "profile": ["https://fhir.doh.gov.ph/phcore/StructureDefinition/ph-core-patient"]
    },
    "name": [{"family": "Dela Cruz", "given": ["Juan"]}],
    "gender": "male",
    "birthDate": "1985-03-15"
  }'
```

### Test Patient Creation (Invalid - Wrong Case)
```bash
curl -X POST http://localhost:8081/fhir/Patient \
  -H "Content-Type: application/json" \
  -d '{
    "resourceType": "Patient",
    "meta": {
      "profile": ["HTTPS://FHIR.DOH.GOV.PH/PHCORE/STRUCTUREDEFINITION/PH-CORE-PATIENT"]
    },
    "name": [{"family": "Dela Cruz", "given": ["Juan"]}],
    "gender": "male",
    "birthDate": "1985-03-15"
  }'
```
**Expected Result**: 422 Unprocessable Entity error

### Test ServiceRequest Creation (Valid)
```bash
curl -X POST http://localhost:8081/fhir/ServiceRequest \
  -H "Content-Type: application/json" \
  -d '{
    "resourceType": "ServiceRequest",
    "meta": {
      "profile": ["https://fhir.doh.gov.ph/ereferral/StructureDefinition/ereferral-service-request"]
    },
    "status": "active",
    "intent": "order",
    "code": {
      "coding": [{
        "system": "http://snomed.info/sct",
        "code": "183519001",
        "display": "Referral to cardiology service"
      }]
    },
    "subject": {"reference": "Patient/1"},
    "authoredOn": "2026-06-17"
  }'
```

### Get Patient
```bash
curl http://localhost:8081/fhir/Patient/1
```

### Get ServiceRequest
```bash
curl http://localhost:8081/fhir/ServiceRequest/1
```

---

## Troubleshooting

### Common Issues

#### 1. Port Already in Use
**Error**: Port 8080 already in use
**Solution**: Stop other services using port 8080 or change port in application.yaml

#### 2. Validation Fails Unexpectedly
**Check**:
- `meta.profile` field is present
- URL is exactly correct (case-sensitive)
- Resource has all required fields

#### 3. Docker Build Fails
**Check**:
- Docker daemon is running
- Sufficient disk space
- Network connectivity for Maven dependencies

#### 4. Application Won't Start
**Check logs**:
```bash
docker logs eref-hapi
```
Look for:
- Java version compatibility
- Missing dependencies
- Configuration errors

### Validation Error Messages

#### Missing meta.profile
```
Patient validation failed: meta.profile is required
```

#### Incorrect Profile URL
```
Patient validation failed: meta.profile must be exactly https://fhir.doh.gov.ph/phcore/StructureDefinition/ph-core-patient
```

#### FHIR Schema Validation Failed
```
Patient validation failed: [validation details in OperationOutcome]
```

---

## Security Considerations

### Current Implementation
- No authentication/authorization (development only)
- In-memory storage (not persistent)
- No HTTPS (HTTP only)

### Production Recommendations
1. Add authentication (OAuth2, JWT)
2. Implement authorization (RBAC)
3. Use persistent storage (PostgreSQL with HAPI FHIR JPA)
4. Enable HTTPS/TLS
5. Add rate limiting
6. Implement audit logging
7. Add input sanitization
8. Use secrets management for credentials

---

## Performance Considerations

### Current Limitations
- In-memory storage limits scalability
- No connection pooling
- No caching
- Single-threaded validation

### Optimization Recommendations
1. Use HAPI FHIR JPA Server for database persistence
2. Implement connection pooling
3. Add caching for frequently accessed resources
4. Consider async validation for large resources
5. Implement pagination for search results

---

## Future Enhancements

### Planned Features
1. Support for additional FHIR resources (Observation, Condition, etc.)
2. Full PH Core IG validation (not just profile URL)
3. Full PH e-Referral IG validation
4. Database persistence with HAPI FHIR JPA
5. Authentication and authorization
6. FHIR Bulk Data Export
7. FHIR Subscription support
8. SMART on FHIR integration

### IG Package Loading
To enable full IG validation (not just profile URL checking):
1. Load IG packages using NPM or direct download
2. Configure ValidationSupportChain with IValidationSupport implementations
3. Add CommonTerminologies and other validation modules
4. Enable schematron validation if needed

---

## References

### Documentation
- [HAPI FHIR Documentation](https://hapifhir.io/)
- [FHIR R4 Specification](https://hl7.org/fhir/R4/)
- [PH Core Implementation Guide](https://build.fhir.org/ig/UP-Manila-SILab/ph-core/)
- [PH e-Referral Implementation Guide](https://build.fhir.org/ig/niccoreyes/ph-ereferral/)

### Tools
- [FHIR Validator](https://validator.fhir.org/)
- [Simplifier.net](https://simplifier.net/)
- [Postman](https://www.postman.com/) for API testing

---

## Support

For issues or questions:
1. Check logs: `docker logs eref-hapi`
2. Review this documentation
3. Consult HAPI FHIR documentation
4. Check FHIR specification

---

**Document Version**: 1.0  
**Last Updated**: June 17, 2026  
**Author**: System Administrator  
**Project**: eReferral FHIR Server
