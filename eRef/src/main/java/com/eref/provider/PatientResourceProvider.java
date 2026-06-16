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
import org.hl7.fhir.r4.model.Patient;
import org.hl7.fhir.r4.model.StringType;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Component;

import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Map;

/**
 * FHIR Resource Provider for Patient resources
 */
@Component
public class PatientResourceProvider implements IResourceProvider {

    private static final Logger log = LoggerFactory.getLogger(PatientResourceProvider.class);
    private static final Map<String, Patient> patientStore = new HashMap<>();
    private static Long idCounter = 1L;

    @Autowired
    private FhirValidator fhirValidator;

    @Override
    public Class<? extends IBaseResource> getResourceType() {
        return Patient.class;
    }

    @Create
    public MethodOutcome createPatient(@ResourceParam Patient thePatient) {
        log.info("RESOURCE PROVIDER: Creating patient - Validating resource");
        
        // Validate that meta.profile is present and matches PH Core Patient profile exactly
        String expectedProfile = "https://fhir.doh.gov.ph/phcore/StructureDefinition/ph-core-patient";
        if (!thePatient.hasMeta() || !thePatient.getMeta().hasProfile()) {
            log.error("RESOURCE PROVIDER: Validation failed - meta.profile is required");
            throw new UnprocessableEntityException("Patient validation failed: meta.profile is required");
        }
        
        boolean hasCorrectProfile = false;
        for (org.hl7.fhir.r4.model.UriType profile : thePatient.getMeta().getProfile()) {
            if (expectedProfile.equals(profile.getValue())) {
                hasCorrectProfile = true;
                break;
            }
        }
        
        if (!hasCorrectProfile) {
            log.error("RESOURCE PROVIDER: Validation failed - meta.profile must be exactly: {}", expectedProfile);
            throw new UnprocessableEntityException("Patient validation failed: meta.profile must be exactly " + expectedProfile);
        }
        
        // Validate the patient
        ValidationResult validationResult = fhirValidator.validateWithResult(thePatient);
        log.info("RESOURCE PROVIDER: Validation result - Successful: {}, Messages: {}", 
                 validationResult.isSuccessful(), validationResult.getMessages().size());
        
        if (!validationResult.isSuccessful()) {
            log.error("RESOURCE PROVIDER: Validation failed - {}", validationResult.getMessages());
            throw new UnprocessableEntityException("Patient validation failed", validationResult.toOperationOutcome());
        }
        
        Long id = idCounter++;
        thePatient.setId(new IdType("Patient", id.toString()));
        patientStore.put(id.toString(), thePatient);
        
        log.info("RESOURCE PROVIDER: Patient created successfully with ID: {}", id);
        
        MethodOutcome outcome = new MethodOutcome();
        outcome.setCreated(true);
        outcome.setId(thePatient.getIdElement());
        outcome.setResource(thePatient);
        return outcome;
    }

    @Read
    public Patient readPatient(@IdParam IdType theId) {
        Patient patient = patientStore.get(theId.getIdPart());
        if (patient == null) {
            throw new ca.uhn.fhir.rest.server.exceptions.ResourceNotFoundException(theId);
        }
        return patient;
    }

    @Update
    public MethodOutcome updatePatient(@IdParam IdType theId, @ResourceParam Patient thePatient) {
        log.info("RESOURCE PROVIDER: Updating patient - Validating resource");
        
        // Validate the patient
        ValidationResult validationResult = fhirValidator.validateWithResult(thePatient);
        log.info("RESOURCE PROVIDER: Validation result - Successful: {}, Messages: {}", 
                 validationResult.isSuccessful(), validationResult.getMessages().size());
        
        if (!validationResult.isSuccessful()) {
            log.error("RESOURCE PROVIDER: Validation failed - {}", validationResult.getMessages());
            throw new UnprocessableEntityException("Patient validation failed", validationResult.toOperationOutcome());
        }
        
        if (!patientStore.containsKey(theId.getIdPart())) {
            throw new ca.uhn.fhir.rest.server.exceptions.ResourceNotFoundException(theId);
        }
        thePatient.setId(theId);
        patientStore.put(theId.getIdPart(), thePatient);
        
        log.info("RESOURCE PROVIDER: Patient updated successfully with ID: {}", theId.getIdPart());
        
        MethodOutcome outcome = new MethodOutcome();
        outcome.setId(thePatient.getIdElement());
        outcome.setResource(thePatient);
        return outcome;
    }

    @Delete
    public MethodOutcome deletePatient(@IdParam IdType theId) {
        if (!patientStore.containsKey(theId.getIdPart())) {
            throw new ca.uhn.fhir.rest.server.exceptions.ResourceNotFoundException(theId);
        }
        patientStore.remove(theId.getIdPart());
        
        MethodOutcome outcome = new MethodOutcome();
        outcome.setId(theId);
        return outcome;
    }

    @Search
    public List<Patient> searchPatient(@OptionalParam(name = Patient.SP_FAMILY) StringParam theFamilyName) {
        List<Patient> results = new ArrayList<>();
        
        if (theFamilyName == null || theFamilyName.isEmpty()) {
            results.addAll(patientStore.values());
        } else {
            for (Patient patient : patientStore.values()) {
                if (patient.hasName()) {
                    for (org.hl7.fhir.r4.model.HumanName name : patient.getName()) {
                        if (name.hasFamily() && name.getFamily().toLowerCase().contains(theFamilyName.getValue().toLowerCase())) {
                            results.add(patient);
                            break;
                        }
                    }
                }
            }
        }
        
        return results;
    }
}
