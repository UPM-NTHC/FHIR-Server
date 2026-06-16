package com.eref;

import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;

/**
 * Main Spring Boot Application for eReferral FHIR Server
 */
@SpringBootApplication
public class EreferralApplication {

    public static void main(String[] args) {
        SpringApplication.run(EreferralApplication.class, args);
    }
}
