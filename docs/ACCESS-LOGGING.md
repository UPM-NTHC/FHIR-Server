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

## Structured JSON Output (Optional)

For production deployments that ingest logs into ELK, Loki, or CloudWatch, you can route the `fhirtest.access` logger to a JSON appender via a custom `logback-spring.xml`. This is not currently configured but can be added by mounting a logback config into the container at `/app/config/logback-spring.xml`.
