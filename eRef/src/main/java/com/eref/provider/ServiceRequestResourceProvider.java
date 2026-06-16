package com.eref.provider;

import ca.uhn.fhir.rest.annotation.*;
import ca.uhn.fhir.rest.api.MethodOutcome;
import ca.uhn.fhir.rest.param.StringParam;
import ca.uhn.fhir.rest.server.IResourceProvider;
import ca.uhn.fhir.rest.server.exceptions.UnprocessableEntityException;
import ca.uhn.fhir.validation.FhirValidator;
import ca.uhn.fhir.validation.ValidationResult;
import org.hl7.fhir.instance.model.api.IBaseResource;
import org.hl7.fhir.r4.model.IdType;
import org.hl7.fhir.r4.model.ServiceRequest;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Component;

import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Map;

/**
 * FHIR Resource Provider for ServiceRequest resources
 * Used for PH e-Referral implementation
 */
@Component
public class ServiceRequestResourceProvider implements IResourceProvider {

    private static final Logger log = LoggerFactory.getLogger(ServiceRequestResourceProvider.class);
    private static final Map<String, ServiceRequest> serviceRequestStore = new HashMap<>();
    private static Long idCounter = 1L;

    @Autowired
    private FhirValidator fhirValidator;

    @Override
    public Class<? extends IBaseResource> getResourceType() {
        return ServiceRequest.class;
    }

    @Create
    public MethodOutcome createServiceRequest(@ResourceParam ServiceRequest theServiceRequest) {
        log.info("RESOURCE PROVIDER: Creating service request - Validating resource");
        
        // Validate that meta.profile is present and matches PH e-Referral ServiceRequest profile exactly
        String expectedProfile = "https://fhir.doh.gov.ph/ereferral/StructureDefinition/ereferral-service-request";
        if (!theServiceRequest.hasMeta() || !theServiceRequest.getMeta().hasProfile()) {
            log.error("RESOURCE PROVIDER: Validation failed - meta.profile is required");
            throw new UnprocessableEntityException("ServiceRequest validation failed: meta.profile is required");
        }
        
        boolean hasCorrectProfile = false;
        for (org.hl7.fhir.r4.model.UriType profile : theServiceRequest.getMeta().getProfile()) {
            if (expectedProfile.equals(profile.getValue())) {
                hasCorrectProfile = true;
                break;
            }
        }
        
        if (!hasCorrectProfile) {
            log.error("RESOURCE PROVIDER: Validation failed - meta.profile must be exactly: {}", expectedProfile);
            throw new UnprocessableEntityException("ServiceRequest validation failed: meta.profile must be exactly " + expectedProfile);
        }
        
        // Validate the service request
        ValidationResult validationResult = fhirValidator.validateWithResult(theServiceRequest);
        log.info("RESOURCE PROVIDER: Validation result - Successful: {}, Messages: {}", 
                 validationResult.isSuccessful(), validationResult.getMessages().size());
        
        if (!validationResult.isSuccessful()) {
            log.error("RESOURCE PROVIDER: Validation failed - {}", validationResult.getMessages());
            throw new UnprocessableEntityException("ServiceRequest validation failed", validationResult.toOperationOutcome());
        }
        
        Long id = idCounter++;
        theServiceRequest.setId(new IdType("ServiceRequest", id.toString()));
        serviceRequestStore.put(id.toString(), theServiceRequest);
        
        log.info("RESOURCE PROVIDER: ServiceRequest created successfully with ID: {}", id);
        
        MethodOutcome outcome = new MethodOutcome();
        outcome.setCreated(true);
        outcome.setId(theServiceRequest.getIdElement());
        outcome.setResource(theServiceRequest);
        return outcome;
    }

    @Read
    public ServiceRequest readServiceRequest(@IdParam IdType theId) {
        ServiceRequest serviceRequest = serviceRequestStore.get(theId.getIdPart());
        if (serviceRequest == null) {
            throw new ca.uhn.fhir.rest.server.exceptions.ResourceNotFoundException(theId);
        }
        return serviceRequest;
    }

    @Update
    public MethodOutcome updateServiceRequest(@IdParam IdType theId, @ResourceParam ServiceRequest theServiceRequest) {
        log.info("RESOURCE PROVIDER: Updating service request - Validating resource");
        
        // Validate the service request
        ValidationResult validationResult = fhirValidator.validateWithResult(theServiceRequest);
        log.info("RESOURCE PROVIDER: Validation result - Successful: {}, Messages: {}", 
                 validationResult.isSuccessful(), validationResult.getMessages().size());
        
        if (!validationResult.isSuccessful()) {
            log.error("RESOURCE PROVIDER: Validation failed - {}", validationResult.getMessages());
            throw new UnprocessableEntityException("ServiceRequest validation failed", validationResult.toOperationOutcome());
        }
        
        if (!serviceRequestStore.containsKey(theId.getIdPart())) {
            throw new ca.uhn.fhir.rest.server.exceptions.ResourceNotFoundException(theId);
        }
        theServiceRequest.setId(theId);
        serviceRequestStore.put(theId.getIdPart(), theServiceRequest);
        
        log.info("RESOURCE PROVIDER: ServiceRequest updated successfully with ID: {}", theId.getIdPart());
        
        MethodOutcome outcome = new MethodOutcome();
        outcome.setId(theServiceRequest.getIdElement());
        outcome.setResource(theServiceRequest);
        return outcome;
    }

    @Delete
    public MethodOutcome deleteServiceRequest(@IdParam IdType theId) {
        if (!serviceRequestStore.containsKey(theId.getIdPart())) {
            throw new ca.uhn.fhir.rest.server.exceptions.ResourceNotFoundException(theId);
        }
        serviceRequestStore.remove(theId.getIdPart());
        
        MethodOutcome outcome = new MethodOutcome();
        outcome.setId(theId);
        return outcome;
    }

    @Search
    public List<ServiceRequest> searchServiceRequest(@OptionalParam(name = "code") StringParam theCode) {
        List<ServiceRequest> results = new ArrayList<>();
        
        if (theCode == null || theCode.isEmpty()) {
            results.addAll(serviceRequestStore.values());
        } else {
            for (ServiceRequest serviceRequest : serviceRequestStore.values()) {
                if (serviceRequest.hasCode() && 
                    serviceRequest.getCode().getCodingFirstRep().getCode().contains(theCode.getValue())) {
                    results.add(serviceRequest);
                }
            }
        }
        
        return results;
    }
}
