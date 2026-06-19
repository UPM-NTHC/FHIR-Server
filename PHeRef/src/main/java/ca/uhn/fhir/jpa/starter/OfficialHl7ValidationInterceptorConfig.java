package ca.uhn.fhir.jpa.starter;

import ca.uhn.fhir.context.FhirContext;
import ca.uhn.fhir.interceptor.api.IInterceptorService;
import ca.uhn.fhir.jpa.interceptor.validation.IRepositoryValidatingRule;
import ca.uhn.fhir.jpa.interceptor.validation.RepositoryValidatingInterceptor;
import ca.uhn.fhir.jpa.interceptor.validation.RepositoryValidatingRuleBuilder;
import ca.uhn.fhir.validation.ResultSeverityEnum;
import jakarta.annotation.PostConstruct;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.context.ApplicationContext;
import org.springframework.context.annotation.Configuration;

import java.util.List;

@Configuration
public class OfficialHl7ValidationInterceptorConfig {

    private static final Logger ourLog =
            LoggerFactory.getLogger(OfficialHl7ValidationInterceptorConfig.class);

    private static final String PHCORE_PATIENT_PROFILE =
            "https://fhir.doh.gov.ph/phcore/StructureDefinition/ph-core-patient";

    private static final String EREF_PATIENT_PROFILE =
            "https://fhir.doh.gov.ph/pheref/StructureDefinition/ereferral-patient";

    private static final String EREF_SERVICE_REQUEST_PROFILE =
            "https://fhir.doh.gov.ph/pheref/StructureDefinition/ereferral-service-request";

    private static final String EREF_TASK_PROFILE =
            "https://fhir.doh.gov.ph/pheref/StructureDefinition/ereferral-task";

    private final FhirContext fhirContext;
    private final IInterceptorService interceptorService;
    private final ApplicationContext applicationContext;

    public OfficialHl7ValidationInterceptorConfig(
            FhirContext fhirContext,
            IInterceptorService interceptorService,
            ApplicationContext applicationContext
    ) {
        this.fhirContext = fhirContext;
        this.interceptorService = interceptorService;
        this.applicationContext = applicationContext;
    }

    @PostConstruct
    public void registerOfficialHl7Validator() {

        RepositoryValidatingRuleBuilder ruleBuilder =
                applicationContext.getBean(RepositoryValidatingRuleBuilder.class);

        ruleBuilder
                .forResourcesOfType("Patient")
                .requireAtLeastOneProfileOf(
                        PHCORE_PATIENT_PROFILE,
                        EREF_PATIENT_PROFILE
                )
                .and()
                .requireValidationToDeclaredProfiles()
                .errorOnUnknownProfiles()
                .rejectOnSeverity(ResultSeverityEnum.ERROR);

        ruleBuilder
                .forResourcesOfType("ServiceRequest")
                .requireAtLeastProfile(EREF_SERVICE_REQUEST_PROFILE)
                .and()
                .requireValidationToDeclaredProfiles()
                .errorOnUnknownProfiles()
                .rejectOnSeverity(ResultSeverityEnum.ERROR);

        ruleBuilder
                .forResourcesOfType("Task")
                .requireAtLeastProfile(EREF_TASK_PROFILE)
                .and()
                .requireValidationToDeclaredProfiles()
                .errorOnUnknownProfiles()
                .rejectOnSeverity(ResultSeverityEnum.ERROR);

        List<IRepositoryValidatingRule> rules = ruleBuilder.build();

        RepositoryValidatingInterceptor interceptor =
                new RepositoryValidatingInterceptor(fhirContext, rules);

        interceptorService.registerInterceptor(interceptor);

        ourLog.info(">>> PH CORE + PH EREFERRAL VALIDATOR LOADED. Rules count: {}", rules.size());
    }
}