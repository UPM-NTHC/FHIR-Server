# Proposal: FHIR Conformance Test Framework

## Intent
Validate that FHIR servers correctly implement the PH eReferral and PH Core Implementation Guides by testing example resources against live endpoints, with clear pass/fail reporting and root-cause analysis.

## Scope
- Two test scripts: one for PH eReferral (PHeRef) profiles, one for PH Core profiles
- Test via Bundle POST (transaction) and individual resource PUT
- Dependency-ordered loading with built-in cycle resolution for circular refs (Condition ↔ Encounter)
- Dry-run mode (JSON validation only) when server unreachable
- Generated markdown reports with categorized error narratives
- Endpoints: localhost dev server, CDR servers (cdr.pheref.fhirlab.net, cdr.phcore.fhirlab.net), FHIRPortal (fhirportal.telehealth.ph)

## Non-Goals
- Performance/load testing
- Security/authorization testing
- Validating non-FHIR endpoints
- Testing IG publication tooling (SUSHI, etc.)

## Approach
Two independent test scripts sharing a common runner pattern, each targeting its own IG's example resources and server endpoints. PH Core includes dependency-graph analysis to order PUTs correctly.
