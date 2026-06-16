# Multi-stage Dockerfile for eReferral FHIR Server
FROM maven:3.9-eclipse-temurin-17 AS builder

WORKDIR /app

# Copy pom.xml and download dependencies
COPY pom.xml .
RUN mvn dependency:go-offline -B

# Copy source code
COPY src ./src

# Build the application
RUN mvn clean package -DskipTests

# Runtime stage
FROM eclipse-temurin:17-jre

WORKDIR /app

# Copy the built jar from builder
COPY --from=builder /app/target/*.jar app.jar

# Copy configuration files
COPY application.yaml ./config/application.yaml
COPY mdm-rules.json ./config/mdm-rules.json

# Expose port
EXPOSE 8080

# Run the application
ENTRYPOINT ["java", "-jar", "app.jar"]
