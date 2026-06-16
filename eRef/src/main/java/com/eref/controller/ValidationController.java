package com.eref.controller;

import ca.uhn.fhir.validation.ValidationResult;
import com.eref.interceptor.HL7ValidationInterceptor;
import org.hl7.fhir.r4.model.Patient;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

/**
 * REST Controller for HL7 Validation endpoints
 */
@RestController
@RequestMapping("/api")
public class ValidationController {

    private final HL7ValidationInterceptor validationInterceptor;

    @Autowired
    public ValidationController(HL7ValidationInterceptor validationInterceptor) {
        this.validationInterceptor = validationInterceptor;
    }

    /**
     * Health check endpoint
     */
    @GetMapping("/health")
    public ResponseEntity<String> health() {
        return ResponseEntity.ok("HL7 Validation Service is running");
    }

    /**
     * Validate a FHIR resource
     */
    @PostMapping("/validate")
    public ResponseEntity<String> validateResource(@RequestBody String resourceJson) {
        try {
            // Parse the JSON to a FHIR resource (simplified example)
            Patient patient = new Patient();
            patient.setId("test-patient");
            
            ValidationResult result = validationInterceptor.validateResource(patient);
            
            if (result.isSuccessful()) {
                return ResponseEntity.ok("Validation passed");
            } else {
                return ResponseEntity.badRequest().body(
                    "Validation failed: " + result.toOperationOutcome().toString()
                );
            }
        } catch (Exception e) {
            return ResponseEntity.internalServerError().body(
                "Error during validation: " + e.getMessage()
            );
        }
    }

    /**
     * Check if validation should be bypassed
     */
    @GetMapping("/bypass-check")
    public ResponseEntity<Boolean> checkBypass(
            @RequestHeader(value = "X-Validation-Bypass", required = false) String bypassHeader,
            @RequestParam(value = "_validate", required = false) String validateParam) {
        boolean shouldBypass = validationInterceptor.shouldBypassValidation(bypassHeader, validateParam);
        return ResponseEntity.ok(shouldBypass);
    }
}
