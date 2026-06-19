package ca.uhn.fhir.jpa.starter;

import ca.uhn.fhir.interceptor.api.IInterceptorService;
import jakarta.annotation.PostConstruct;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.context.annotation.Configuration;

@Configuration
public class PhErefDeduplicationInterceptorConfig {

    private static final Logger ourLog =
            LoggerFactory.getLogger(PhErefDeduplicationInterceptorConfig.class);

    private final IInterceptorService interceptorService;
    private final PhErefDeduplicationInterceptor dedupInterceptor;

    public PhErefDeduplicationInterceptorConfig(
            IInterceptorService interceptorService,
            PhErefDeduplicationInterceptor dedupInterceptor
    ) {
        this.interceptorService = interceptorService;
        this.dedupInterceptor = dedupInterceptor;
    }

    @PostConstruct
    public void register() {
        interceptorService.registerInterceptor(dedupInterceptor);
        ourLog.info("PH eReferral Dedup Interceptor registered");
    }
}