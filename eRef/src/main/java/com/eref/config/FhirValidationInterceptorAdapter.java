package com.eref.config;

import ca.uhn.fhir.interceptor.api.Hook;
import ca.uhn.fhir.interceptor.api.Interceptor;
import ca.uhn.fhir.interceptor.api.Pointcut;
import ca.uhn.fhir.rest.api.server.RequestDetails;
import ca.uhn.fhir.rest.server.exceptions.UnprocessableEntityException;
import ca.uhn.fhir.validation.FhirValidator;
import ca.uhn.fhir.validation.ValidationResult;
import com.eref.interceptor.HL7ValidationInterceptor;
import org.hl7.fhir.instance.model.api.IBaseOperationOutcome;
import org.hl7.fhir.instance.model.api.IBaseResource;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

/**
 * Adapter to integrate HL7ValidationInterceptor with HAPI FHIR REST server
 */
@Interceptor
public class FhirValidationInterceptorAdapter {

    private static final Logger log = LoggerFactory.getLogger(FhirValidationInterceptorAdapter.class);

    private final HL7ValidationInterceptor hl7ValidationInterceptor;
    private final FhirValidator fhirValidator;

    public FhirValidationInterceptorAdapter(HL7ValidationInterceptor hl7ValidationInterceptor, FhirValidator fhirValidator) {
        this.hl7ValidationInterceptor = hl7ValidationInterceptor;
        this.fhirValidator = fhirValidator;
    }

    @Hook(Pointcut.STORAGE_PRECOMMIT_RESOURCE_CREATED)
    public void validateResourceOnCreate(RequestDetails theRequestDetails, IBaseResource theResource) {
        log.info("VALIDATION INTERCEPTOR: Validating resource on CREATE - Type: {}, ID: {}", 
                 theResource.fhirType(), theResource.getIdElement().getValue());
        performValidation(theRequestDetails, theResource);
    }

    @Hook(Pointcut.STORAGE_PRECOMMIT_RESOURCE_UPDATED)
    public void validateResourceOnUpdate(RequestDetails theRequestDetails, IBaseResource theOldResource, IBaseResource theNewResource) {
        log.info("VALIDATION INTERCEPTOR: Validating resource on UPDATE - Type: {}, ID: {}", 
                 theNewResource.fhirType(), theNewResource.getIdElement().getValue());
        performValidation(theRequestDetails, theNewResource);
    }

    private void performValidation(RequestDetails theRequestDetails, IBaseResource theResource) {
        if (shouldBypassValidation(theRequestDetails)) {
            log.info("VALIDATION INTERCEPTOR: Validation bypassed");
            return;
        }

        log.info("VALIDATION INTERCEPTOR: Starting validation for resource: {}", theResource.fhirType());
        ValidationResult validationResult = fhirValidator.validateWithResult(theResource);
        
        log.info("VALIDATION INTERCEPTOR: Validation result - Successful: {}, Messages: {}", 
                 validationResult.isSuccessful(), validationResult.getMessages().size());

        if (!validationResult.isSuccessful()) {
            IBaseOperationOutcome operationOutcome = validationResult.toOperationOutcome();
            
            StringBuilder errorMessage = new StringBuilder();
            errorMessage.append("HL7 Validation Failed for resource: ")
                       .append(theResource.fhirType())
                       .append("\n");

            log.error("VALIDATION INTERCEPTOR: Validation failed - {}", errorMessage.toString());
            throw new UnprocessableEntityException(errorMessage.toString(), operationOutcome);
        }
        
        log.info("VALIDATION INTERCEPTOR: Validation passed successfully");
    }

    private boolean shouldBypassValidation(RequestDetails theRequestDetails) {
        String validationBypass = theRequestDetails.getHeader("X-Validation-Bypass");
        if ("true".equalsIgnoreCase(validationBypass)) {
            return true;
        }

        String[] validateParams = theRequestDetails.getParameters().get("_validate");
        if (validateParams != null && validateParams.length > 0 && "false".equalsIgnoreCase(validateParams[0])) {
            return true;
        }

        return false;
    }
}
