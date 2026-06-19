# Access Logging

## Overview

The PHeRef FHIR server uses HAPI FHIR's built-in `LoggingInterceptor` to produce structured per-request access logs. Every inbound FHIR REST interaction is logged with operational metadata for auditing, debugging, and statistical accounting.

The logger does **not** log request or response bodies — only metadata about each request.

## Configuration

The logger is configured in `PHeRef/config/application.yaml`:

```yaml
hapi:
  fhir:
    logger:
      name: fhirtest.access
      format: "verb=${requestVerb} path=${servletPath} op=${operationType} opName=${operationName} resource=${idOrResourceName} remoteAddr=${remoteAddr} forwardedFor=${requestHeader.x-forwarded-for} userAgent=${requestHeader.user-agent} requestId=${requestId} params=${requestParameters} processingMs=${processingTimeMillis}"
      error_format: "verb=${requestVerb} path=${requestUrl} op=${operationType} resource=${idOrResourceName} remoteAddr=${remoteAddr} requestId=${requestId} error=${exceptionMessage}"
      log_exceptions: true
```

## How It Works

1. HAPI FHIR registers the `LoggingInterceptor` at server startup when the `hapi.fhir.logger` configuration block is present.
2. The interceptor hooks into `SERVER_PROCESSING_COMPLETED` — it fires **after** each request finishes processing.
3. It interpolates the configured format string using request/response context variables.
4. The resulting log line is emitted via SLF4J under the logger name `fhirtest.access`.
5. Output destination depends on the logging backend (Logback by default) — in Docker, this goes to container stdout.

## Log Format Fields

### Standard request log

| Variable | Field | Example |
|----------|-------|---------|
| `${requestVerb}` | HTTP method | `GET`, `POST`, `PUT`, `DELETE` |
| `${servletPath}` | Request path relative to servlet | `/fhir/Patient/123` |
| `${operationType}` | FHIR interaction type | `read`, `search-type`, `create`, `update`, `delete`, `extended-operation-instance` |
| `${operationName}` | Named operation (if applicable) | `$validate`, `$everything`, `$match` |
| `${idOrResourceName}` | Resource type or resource ID | `Patient`, `Patient/123` |
| `${remoteAddr}` | Client IP address | `172.18.0.1` |
| `${requestHeader.x-forwarded-for}` | Forwarded-for header (behind proxy) | `203.0.113.42` |
| `${requestHeader.user-agent}` | Client user agent | `curl/8.5.0` |
| `${requestId}` | Server-assigned request ID | `W4kNfL2R8vXbP3` |
| `${requestParameters}` | Query string parameters | `identifier=PH-123&_pretty=true` |
| `${processingTimeMillis}` | Time spent processing (ms) | `47` |

### Error log (on exceptions)

| Variable | Field | Example |
|----------|-------|---------|
| `${requestUrl}` | Full request URL | `http://localhost:8081/fhir/Patient/$validate` |
| `${exceptionMessage}` | Exception message text | `HAPI-0524: Resource Patient/999 is not known` |

## Example Output

### Successful request

```
verb=GET path=/fhir/Patient op=search-type opName= resource=Patient remoteAddr=172.18.0.1 forwardedFor=203.0.113.42 userAgent=curl/8.5.0 requestId=W4kNfL2R8vXbP3 params=identifier=PH-EREF-TEST-123 processingMs=47
```

### Create operation

```
verb=POST path=/fhir/Patient op=create opName= resource=Patient remoteAddr=172.18.0.1 forwardedFor= userAgent=python-urllib/3.11 requestId=X9mBc1K4pQzR7 params= processingMs=132
```

### Named operation

```
verb=POST path=/fhir/Patient/$validate op=extended-operation-type opName=$validate resource=Patient remoteAddr=172.18.0.1 forwardedFor= userAgent=curl/8.5.0 requestId=A2nDf8L3wYtS5 params=_pretty=true processingMs=89
```

### Error

```
verb=GET path=http://localhost:8081/fhir/Patient/999 op=read resource=Patient/999 remoteAddr=172.18.0.1 requestId=B7pGk4M2rVnW1 error=HAPI-0524: Resource Patient/999 is not known
```

## Viewing Logs

Since the server runs in Docker, access logs appear in container stdout:

```bash
# Follow live logs
docker logs -f eref-hapi

# Filter for access log lines only
docker logs eref-hapi 2>&1 | grep "fhirtest.access"
```

## Enabling on Ph-core

To enable the same logging on the Ph-core server, add the `logger` block to `Ph-core/config/application.yaml` under `hapi.fhir`:

```yaml
    logger:
      name: fhirtest.access
      format: "verb=${requestVerb} path=${servletPath} op=${operationType} opName=${operationName} resource=${idOrResourceName} remoteAddr=${remoteAddr} forwardedFor=${requestHeader.x-forwarded-for} userAgent=${requestHeader.user-agent} requestId=${requestId} params=${requestParameters} processingMs=${processingTimeMillis}"
      error_format: "verb=${requestVerb} path=${requestUrl} op=${operationType} resource=${idOrResourceName} remoteAddr=${remoteAddr} requestId=${requestId} error=${exceptionMessage}"
      log_exceptions: true
```

## Docker Integration

### Log Drivers

Docker captures all container stdout/stderr and routes it through the configured [log driver](https://docs.docker.com/config/containers/logging/). The default `json-file` driver writes logs to `/var/lib/docker/containers/<id>/<id>-json.log` on the host.

Since the HAPI FHIR server writes access logs to stdout via SLF4J/Logback, they are automatically captured by Docker with no additional configuration.

### Viewing Logs

```bash
# Live tail of eRef server logs
docker logs -f eref-hapi

# Last 100 lines
docker logs --tail 100 eref-hapi

# Logs since a specific time
docker logs --since 2024-01-15T10:00:00 eref-hapi

# Filter access log lines (grep the logger name from Logback output)
docker logs eref-hapi 2>&1 | grep "fhirtest.access"
```

### Log Rotation (json-file driver)

The default `json-file` driver does not rotate logs unless configured. To prevent disk exhaustion, add logging options to `docker-compose.yml`:

```yaml
services:
  eref-hapi:
    logging:
      driver: json-file
      options:
        max-size: "50m"
        max-file: "5"
```

This retains up to 250 MB of logs (5 × 50 MB) per container before rotating.

### Using Docker Compose Log Commands

```bash
# View logs from all services in the stack
docker compose logs

# Follow only the HAPI container
docker compose logs -f eref-hapi

# Show timestamps
docker compose logs -t eref-hapi
```

### Forwarding to External Log Aggregators

Docker supports swapping the log driver to send logs directly to external systems without modifying the application:

| Driver | Target | Example |
|--------|--------|---------|
| `fluentd` | Fluentd / Fluent Bit → Elasticsearch, Loki | `driver: fluentd` |
| `syslog` | Syslog server / rsyslog | `driver: syslog` |
| `awslogs` | AWS CloudWatch Logs | `driver: awslogs` |
| `gcplogs` | Google Cloud Logging | `driver: gcplogs` |
| `gelf` | Graylog (GELF) | `driver: gelf` |
| `splunk` | Splunk HEC | `driver: splunk` |

Example — forwarding to a Fluent Bit sidecar:

```yaml
services:
  eref-hapi:
    logging:
      driver: fluentd
      options:
        fluentd-address: "localhost:24224"
        tag: "fhir.eref"
```

### Separating Access Logs from Application Logs

By default, access logs (`fhirtest.access`) and application logs (Spring Boot, Hibernate, etc.) are mixed in the same stdout stream. To separate them:

**Option 1 — Filter at the aggregator level** using the logger name pattern `fhirtest.access` in your Fluentd/Loki/ELK pipeline.

**Option 2 — Custom Logback configuration** to route access logs to a separate file or appender:

Mount a custom `logback-spring.xml` into the container:

```yaml
services:
  eref-hapi:
    volumes:
      - ./config/logback-spring.xml:/app/config/logback-spring.xml
```

Example `logback-spring.xml` that splits access logs:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<configuration>
    <!-- Application logs to stdout -->
    <appender name="STDOUT" class="ch.qos.logback.core.ConsoleAppender">
        <encoder>
            <pattern>%d{yyyy-MM-dd HH:mm:ss.SSS} [%thread] %-5level %logger{36} - %msg%n</pattern>
        </encoder>
    </appender>

    <!-- Access logs to separate file -->
    <appender name="ACCESS_FILE" class="ch.qos.logback.core.rolling.RollingFileAppender">
        <file>/app/logs/access.log</file>
        <rollingPolicy class="ch.qos.logback.core.rolling.SizeAndTimeBasedRollingPolicy">
            <fileNamePattern>/app/logs/access.%d{yyyy-MM-dd}.%i.log</fileNamePattern>
            <maxFileSize>50MB</maxFileSize>
            <maxHistory>7</maxHistory>
        </rollingPolicy>
        <encoder>
            <pattern>%d{ISO8601} %msg%n</pattern>
        </encoder>
    </appender>

    <!-- Route access logger to its own appender -->
    <logger name="fhirtest.access" level="INFO" additivity="false">
        <appender-ref ref="ACCESS_FILE" />
    </logger>

    <root level="INFO">
        <appender-ref ref="STDOUT" />
    </root>
</configuration>
```

Then mount the logs directory as a volume to persist and access them from the host:

```yaml
    volumes:
      - ./logs:/app/logs
```

## Structured JSON Output (Optional)

For production deployments that ingest logs into ELK, Loki, or CloudWatch, you can route the `fhirtest.access` logger to a JSON appender by using a Logback JSON encoder in the custom `logback-spring.xml` above. Replace the `<encoder>` in the access appender with:

```xml
<encoder class="net.logstash.logback.encoder.LogstashEncoder">
    <includeMdcKeyName>requestId</includeMdcKeyName>
</encoder>
```

This requires the `logstash-logback-encoder` dependency (already available in the HAPI FHIR classpath). The output will be one JSON object per line, compatible with structured log ingestion pipelines.
