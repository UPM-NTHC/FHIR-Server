package com.eref.interceptor;

import ca.uhn.fhir.validation.FhirValidator;
import ca.uhn.fhir.validation.ValidationResult;
import org.hl7.fhir.instance.model.api.IBaseResource;
import org.hl7.fhir.r4.model.OperationOutcome;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Component;

/**
 * HL7 Validation Service for eReferral FHIR Server
 * 
 * This service validates FHIR resources against HL7 standards
 * and configured implementation guides (PH Core, PH eReferral).
 */
@Component
public class HL7ValidationInterceptor {

    private final FhirValidator fhirValidator;

    @Autowired
    public HL7ValidationInterceptor(FhirValidator fhirValidator) {
        this.fhirValidator = fhirValidator;
    }

    /**
     * Validate a FHIR resource against HL7 standards
     * 
     * @param resource The FHIR resource to validate
     * @return ValidationResult containing validation outcome
     */
    public ValidationResult validateResource(IBaseResource resource) {
        return fhirValidator.validateWithResult(resource);
    }

    /**
     * Validate a FHIR resource and throw exception if validation fails
     * 
     * @param resource The FHIR resource to validate
     * @throws IllegalArgumentException if validation fails
     */
    public void validateResourceOrThrow(IBaseResource resource) {
        ValidationResult validationResult = validateResource(resource);
        
        if (!validationResult.isSuccessful()) {
            OperationOutcome operationOutcome = (OperationOutcome) validationResult.toOperationOutcome();
            
            // Build detailed error message
            StringBuilder errorMessage = new StringBuilder();
            errorMessage.append("HL7 Validation Failed for resource: ")
                       .append(resource.fhirType())
                       .append("\n");
            
            operationOutcome.getIssue().forEach(issue -> {
                errorMessage.append("- ")
                           .append(issue.getSeverity().toCode())
                           .append(": ")
                           .append(issue.getDiagnostics())
                           .append("\n");
            });

            throw new IllegalArgumentException(errorMessage.toString());
        }
    }

    /**
     * Check if validation should be bypassed based on headers or parameters
     * 
     * @param validationBypassHeader Value of X-Validation-Bypass header
     * @param validateParam Value of _validate parameter
     * @return true if validation should be bypassed
     */
    public boolean shouldBypassValidation(String validationBypassHeader, String validateParam) {
        // Check for validation bypass header
        if ("true".equalsIgnoreCase(validationBypassHeader)) {
            return true;
        }

        // Check for validation parameter
        if ("false".equalsIgnoreCase(validateParam)) {
            return true;
        }

        return false;
    }
}
