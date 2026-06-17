package ca.uhn.fhir.jpa.starter.interceptor;

import ca.uhn.fhir.interceptor.api.Hook;
import ca.uhn.fhir.interceptor.api.Interceptor;
import ca.uhn.fhir.interceptor.api.Pointcut;
import ca.uhn.fhir.rest.api.server.RequestDetails;
import ca.uhn.fhir.rest.server.exceptions.UnprocessableEntityException;
import org.hl7.fhir.instance.model.api.IBaseResource;
import org.hl7.fhir.r4.model.CanonicalType;
import org.hl7.fhir.r4.model.Reference;
import org.hl7.fhir.r4.model.ServiceRequest;
import org.springframework.stereotype.Component;

@Component
@Interceptor
public class PhEreferralInterceptor {

    private static final String PHEREF_SERVICEREQUEST_PROFILE =
            "https://fhir.doh.gov.ph/pheref/StructureDefinition/ereferral-service-request";

    @Hook(Pointcut.STORAGE_PRESTORAGE_RESOURCE_CREATED)
    public void beforeCreate(IBaseResource resource, RequestDetails requestDetails) {
        validate(resource);
    }

    @Hook(Pointcut.STORAGE_PRESTORAGE_RESOURCE_UPDATED)
    public void beforeUpdate(IBaseResource resource, RequestDetails requestDetails) {
        validate(resource);
    }

    private void validate(IBaseResource resource) {
        if (!(resource instanceof ServiceRequest serviceRequest)) {
            return;
        }

        requirePhEreferralProfile(serviceRequest);
        requireStatus(serviceRequest);
        requireIntentOrder(serviceRequest);
        requireSubjectPatient(serviceRequest);
        requireRequesterPractitionerRole(serviceRequest);
    }

    private void requirePhEreferralProfile(ServiceRequest serviceRequest) {
        boolean hasProfile = serviceRequest.getMeta().getProfile().stream()
                .map(CanonicalType::getValueAsString)
                .anyMatch(profile -> canonicalMatches(profile, PHEREF_SERVICEREQUEST_PROFILE));

        if (!hasProfile) {
            fail("ServiceRequest must declare PH eReferral ServiceRequest profile: "
                    + PHEREF_SERVICEREQUEST_PROFILE);
        }
    }

    private void requireStatus(ServiceRequest serviceRequest) {
        if (!serviceRequest.hasStatus()) {
            fail("PH eReferral ServiceRequest must have status.");
        }
    }

    private void requireIntentOrder(ServiceRequest serviceRequest) {
        if (!serviceRequest.hasIntent()) {
            fail("PH eReferral ServiceRequest must have intent.");
        }

        if (serviceRequest.getIntent() != ServiceRequest.ServiceRequestIntent.ORDER) {
            fail("PH eReferral ServiceRequest intent must be 'order'.");
        }
    }

    private void requireSubjectPatient(ServiceRequest serviceRequest) {
        if (!serviceRequest.hasSubject() || !serviceRequest.getSubject().hasReference()) {
            fail("PH eReferral ServiceRequest must have subject reference to Patient.");
        }

        if (!isReferenceTo(serviceRequest.getSubject(), "Patient")) {
            fail("PH eReferral ServiceRequest subject must reference a Patient.");
        }
    }

    private void requireRequesterPractitionerRole(ServiceRequest serviceRequest) {
        if (!serviceRequest.hasRequester() || !serviceRequest.getRequester().hasReference()) {
            fail("PH eReferral ServiceRequest must have requester reference to PractitionerRole.");
        }

        if (!isReferenceTo(serviceRequest.getRequester(), "PractitionerRole")) {
            fail("PH eReferral ServiceRequest requester must reference a PractitionerRole.");
        }
    }

    private boolean canonicalMatches(String actual, String expected) {
        if (actual == null) {
            return false;
        }

        return actual.equals(expected) || actual.startsWith(expected + "|");
    }

    private boolean isReferenceTo(Reference reference, String expectedResourceType) {
        if (reference == null || !reference.hasReference()) {
            return false;
        }

        String resourceType = reference.getReferenceElement().getResourceType();
        if (expectedResourceType.equals(resourceType)) {
            return true;
        }

        String rawReference = reference.getReference();
        return rawReference != null &&
                (rawReference.startsWith(expectedResourceType + "/")
                        || rawReference.contains("/" + expectedResourceType + "/"));
    }

    private void fail(String message) {
        throw new UnprocessableEntityException(message);
    }
}