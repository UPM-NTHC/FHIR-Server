package ca.uhn.fhir.jpa.starter;

import ca.uhn.fhir.interceptor.api.Hook;
import ca.uhn.fhir.interceptor.api.Pointcut;
import ca.uhn.fhir.rest.api.server.RequestDetails;
import jakarta.servlet.http.HttpServletResponse;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.stereotype.Component;

@Component
public class PhErefDeduplicationInterceptor {

    private static final Logger ourLog =
            LoggerFactory.getLogger(PhErefDeduplicationInterceptor.class);

    public PhErefDeduplicationInterceptor() {
        ourLog.info("PH eReferral Dedup Interceptor bean created");
    }

    @Hook(Pointcut.SERVER_INCOMING_REQUEST_PRE_HANDLED)
    public void dedupBeforeHapiHandles(
            RequestDetails requestDetails,
            HttpServletResponse response
    ) {
        ourLog.info("DEDUP interceptor fired: {}", requestDetails.getRequestPath());

        return;
    }
}