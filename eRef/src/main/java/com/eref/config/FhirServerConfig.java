package com.eref.config;

import ca.uhn.fhir.context.FhirContext;
import ca.uhn.fhir.rest.server.RestfulServer;
import ca.uhn.fhir.rest.server.interceptor.LoggingInterceptor;
import ca.uhn.fhir.validation.FhirValidator;
import com.eref.interceptor.HL7ValidationInterceptor;
import com.eref.provider.PatientResourceProvider;
import com.eref.provider.ServiceRequestResourceProvider;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.web.servlet.ServletRegistrationBean;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;

/**
 * FHIR REST Server Configuration
 */
@Configuration
public class FhirServerConfig {

    @Autowired
    private FhirContext fhirContext;

    @Autowired
    private FhirValidator fhirValidator;

    @Autowired
    private HL7ValidationInterceptor hl7ValidationInterceptor;

    @Autowired
    private PatientResourceProvider patientResourceProvider;

    @Autowired
    private ServiceRequestResourceProvider serviceRequestResourceProvider;

    @Bean
    public RestfulServer restfulServer() {
        RestfulServer server = new RestfulServer(fhirContext);
        
        // Add logging interceptor
        LoggingInterceptor loggingInterceptor = new LoggingInterceptor();
        loggingInterceptor.setLogExceptions(true);
        server.registerInterceptor(loggingInterceptor);
        
        // Add HL7 validation interceptor
        server.registerInterceptor(new FhirValidationInterceptorAdapter(hl7ValidationInterceptor, fhirValidator));
        
        // Register resource providers
        server.registerProvider(patientResourceProvider);
        server.registerProvider(serviceRequestResourceProvider);
        
        return server;
    }

    @Bean
    public ServletRegistrationBean<RestfulServer> fhirServletRegistration(RestfulServer restfulServer) {
        ServletRegistrationBean<RestfulServer> registration = new ServletRegistrationBean<>(restfulServer);
        registration.addUrlMappings("/fhir/*");
        registration.setLoadOnStartup(1);
        return registration;
    }
}
