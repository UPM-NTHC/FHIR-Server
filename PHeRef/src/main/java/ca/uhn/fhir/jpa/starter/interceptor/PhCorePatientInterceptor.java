package ca.uhn.fhir.jpa.starter.interceptor;

import ca.uhn.fhir.interceptor.api.Hook;
import ca.uhn.fhir.interceptor.api.Interceptor;
import ca.uhn.fhir.interceptor.api.Pointcut;
import ca.uhn.fhir.rest.api.server.RequestDetails;
import ca.uhn.fhir.rest.server.exceptions.UnprocessableEntityException;
import org.hl7.fhir.instance.model.api.IBaseResource;
import org.hl7.fhir.r4.model.CanonicalType;
import org.hl7.fhir.r4.model.Identifier;
import org.hl7.fhir.r4.model.Patient;
import org.springframework.stereotype.Component;

@Component
@Interceptor
public class PhCorePatientInterceptor {

    private static final String PHCORE_PATIENT_PROFILE =
            "https://fhir.doh.gov.ph/phcore/StructureDefinition/ph-core-patient";

    private static final String PHILHEALTH_SYSTEM =
            "http://philhealth.gov.ph/fhir/Identifier/philhealth-id";

    private static final String PHILSYS_SYSTEM =
            "http://philsys.gov.ph/fhir/Identifier/philsys-id";

    @Hook(Pointcut.STORAGE_PRESTORAGE_RESOURCE_CREATED)
    public void beforeCreate(IBaseResource resource, RequestDetails requestDetails) {
        validate(resource);
    }

    @Hook(Pointcut.STORAGE_PRESTORAGE_RESOURCE_UPDATED)
    public void beforeUpdate(IBaseResource resource, RequestDetails requestDetails) {
        validate(resource);
    }

    private void validate(IBaseResource resource) {
        if (!(resource instanceof Patient patient)) {
            return;
        }

        requirePhCoreProfile(patient);
        validateIdentifiersIfPresent(patient);
    }

    private void requirePhCoreProfile(Patient patient) {
        boolean hasProfile = patient.getMeta().getProfile().stream()
                .map(CanonicalType::getValueAsString)
                .anyMatch(profile -> canonicalMatches(profile, PHCORE_PATIENT_PROFILE));

        if (!hasProfile) {
            fail("Patient must declare PH Core Patient profile: " + PHCORE_PATIENT_PROFILE);
        }
    }

    private void validateIdentifiersIfPresent(Patient patient) {
        if (!patient.hasIdentifier()) {
            return;
        }

        for (Identifier identifier : patient.getIdentifier()) {
            if (!identifier.hasSystem() || !identifier.hasValue()) {
                fail("Patient.identifier must have both system and value when provided.");
            }

            String system = identifier.getSystem();

            if (!PHILHEALTH_SYSTEM.equals(system) && !PHILSYS_SYSTEM.equals(system)) {
                fail("Unsupported PH Core Patient identifier system: " + system
                        + ". Supported systems: "
                        + PHILHEALTH_SYSTEM + " or " + PHILSYS_SYSTEM + ".");
            }
        }
    }

    private boolean canonicalMatches(String actual, String expected) {
        if (actual == null) {
            return false;
        }

        return actual.equals(expected) || actual.startsWith(expected + "|");
    }

    private void fail(String message) {
        throw new UnprocessableEntityException(message);
    }
}