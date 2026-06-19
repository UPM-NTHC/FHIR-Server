#!/usr/bin/env python3
"""eReferral FHIR R4 Server Testing Report Generator.

Validates an eReferral HAPI FHIR R4 server by executing a suite of 15 tests
covering profiling, terminology, validation, CRUD operations, and search.

Generates Markdown, HTML, JSON, and TSV reports with detailed findings.

Usage:
    python3 generate_eref_testing_report.py [BASE_URL]

Environment Variables:
    KEEP_CREATED                 - Keep created test resources (default: true)
    SERVICE_REQUEST_PROFILE_URL  - Profile URL for ServiceRequest (optional)
    EREF_PATIENT_PROFILE_URL    - eReferral Patient profile URL
    EREF_PRIORITY_VS_URL        - eReferral priority ValueSet URL
    EREF_WORKFLOW_CS_URL        - eReferral workflow CodeSystem URL
    CONNECT_TIMEOUT             - Connection timeout in seconds (default: 3)
    MAX_TIME                    - Max request time in seconds (default: 20)
"""

from __future__ import annotations

import json
import html as html_mod
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path
from typing import Optional


@dataclass
class Config:
    """Test suite configuration loaded from CLI args and environment."""

    base_url: str = "http://localhost:8081/fhir"
    eref_patient_profile_url: str = (
        "https://fhir.doh.gov.ph/pheref/StructureDefinition/ereferral-patient"
    )
    eref_priority_vs_url: str = (
        "https://fhir.doh.gov.ph/pheref/ValueSet/ereferral-priority"
    )
    eref_workflow_cs_url: str = (
        "https://fhir.doh.gov.ph/pheref/CodeSystem/ereferral-workflow"
    )
    service_request_profile_url: str = ""
    keep_created: bool = True
    connect_timeout: int = 3
    max_time: int = 20

    @classmethod
    def from_env(cls, args: list[str]) -> Config:
        """Build configuration from CLI arguments and environment variables."""
        base_url = args[1] if len(args) > 1 else os.environ.get(
            "BASE_URL", "http://localhost:8081/fhir"
        )
        return cls(
            base_url=base_url,
            eref_patient_profile_url=os.environ.get(
                "EREF_PATIENT_PROFILE_URL",
                cls.eref_patient_profile_url,
            ),
            eref_priority_vs_url=os.environ.get(
                "EREF_PRIORITY_VS_URL",
                cls.eref_priority_vs_url,
            ),
            eref_workflow_cs_url=os.environ.get(
                "EREF_WORKFLOW_CS_URL",
                cls.eref_workflow_cs_url,
            ),
            service_request_profile_url=os.environ.get(
                "SERVICE_REQUEST_PROFILE_URL", ""
            ),
            keep_created=os.environ.get("KEEP_CREATED", "true").lower() == "true",
            connect_timeout=int(os.environ.get("CONNECT_TIMEOUT", "3")),
            max_time=int(os.environ.get("MAX_TIME", "20")),
        )


@dataclass
class TestResult:
    """Result of a single test case."""

    num: int
    name: str
    endpoint: str
    http_status: str
    expected: str
    actual: str
    finding: str
    log_file: str


@dataclass
class HttpResponse:
    """HTTP response from a FHIR server call."""

    status_code: str
    body: dict
    headers: dict[str, str] = field(default_factory=dict)
    error: str = ""


class FhirClient:
    """HTTP client for FHIR server interactions."""

    def __init__(self, config: Config, out_dir: Path) -> None:
        self.config = config
        self.logs_dir = out_dir / "logs"

    def call(
        self,
        name: str,
        method: str,
        url: str,
        body: Optional[dict | Path] = None,
    ) -> HttpResponse:
        """Execute an HTTP request and save response artifacts.

        Args:
            name: Test identifier used for log file naming.
            method: HTTP method (GET, POST, DELETE).
            url: Full request URL.
            body: Request body as dict or path to JSON file.

        Returns:
            HttpResponse with status, parsed body, and headers.
        """
        out_file = self.logs_dir / f"{name}.json"
        header_file = self.logs_dir / f"{name}.headers"
        err_file = self.logs_dir / f"{name}.err"

        headers = {"Accept": "application/fhir+json"}
        data = None

        if body is not None:
            headers["Content-Type"] = "application/fhir+json"
            if isinstance(body, Path):
                data = body.read_bytes()
            else:
                data = json.dumps(body).encode("utf-8")

        req = urllib.request.Request(url, data=data, headers=headers, method=method)
        status_code = "000"
        response_body: dict = {}
        response_headers: dict[str, str] = {}
        error_text = ""

        try:
            import socket
            old_timeout = socket.getdefaulttimeout()
            socket.setdefaulttimeout(self.config.max_time)
            try:
                with urllib.request.urlopen(req, timeout=self.config.max_time) as resp:
                    status_code = str(resp.status)
                    response_headers = dict(resp.headers)
                    raw = resp.read()
                    response_body = json.loads(raw) if raw else {}
            finally:
                socket.setdefaulttimeout(old_timeout)
        except urllib.error.HTTPError as e:
            status_code = str(e.code)
            response_headers = dict(e.headers) if e.headers else {}
            raw = e.read()
            try:
                response_body = json.loads(raw) if raw else {}
            except (json.JSONDecodeError, ValueError):
                response_body = {
                    "resourceType": "OperationOutcome",
                    "issue": [{"severity": "error", "code": "processing",
                               "diagnostics": raw.decode("utf-8", errors="replace")}],
                }
        except Exception as e:
            error_text = str(e)
            response_body = {
                "resourceType": "OperationOutcome",
                "issue": [{"severity": "error", "code": "processing",
                           "diagnostics": error_text}],
            }

        # Save artifacts
        out_file.write_text(json.dumps(response_body, indent=2, ensure_ascii=False), encoding="utf-8")
        header_file.write_text(
            "\n".join(f"{k}: {v}" for k, v in response_headers.items()), encoding="utf-8"
        )
        err_file.write_text(error_text, encoding="utf-8")

        return HttpResponse(
            status_code=status_code,
            body=response_body,
            headers=response_headers,
            error=error_text,
        )

    def delete(self, resource_type: str, resource_id: str, name: str) -> None:
        """Delete a resource (cleanup)."""
        if resource_id:
            url = f"{self.config.base_url}/{resource_type}/{resource_id}"
            try:
                self.call(f"{name}-delete", "DELETE", url)
            except Exception:
                pass


class PayloadGenerator:
    """Generates FHIR test payloads."""

    def __init__(self, config: Config, timestamp: str, payloads_dir: Path) -> None:
        self.config = config
        self.timestamp = timestamp
        self.payloads_dir = payloads_dir

    def valid_patient(self) -> Path:
        """Generate a conformant eReferral Patient resource."""
        resource = {
            "resourceType": "Patient",
            "meta": {"profile": [self.config.eref_patient_profile_url]},
            "text": {
                "status": "generated",
                "div": '<div xmlns="http://www.w3.org/1999/xhtml">Juan Dela Cruz eReferral test patient</div>',
            },
            "identifier": [
                {"system": "https://philhealth.gov.ph", "value": f"PH-EREF-TEST-{self.timestamp}"},
                {"system": "https://psa.gov.ph/philsys", "value": f"PSN-EREF-TEST-{self.timestamp}"},
            ],
            "name": [{"family": "Dela Cruz", "given": ["Juan"]}],
            "gender": "male",
            "birthDate": "1990-01-01",
            "telecom": [{"system": "phone", "value": "+639171234567", "use": "mobile"}],
            "address": [{"line": ["Barangay Malinis"], "city": "Quezon City", "state": "NCR", "country": "PH"}],
        }
        return self._write("eref-patient-valid.json", resource)

    def invalid_patient(self) -> Path:
        """Generate a non-conformant Patient (missing required fields)."""
        resource = {
            "resourceType": "Patient",
            "meta": {"profile": [self.config.eref_patient_profile_url]},
        }
        return self._write("eref-patient-invalid.json", resource)

    def no_profile_patient(self) -> Path:
        """Generate a Patient without meta.profile."""
        resource = {
            "resourceType": "Patient",
            "identifier": [{"system": "https://philhealth.gov.ph", "value": f"PH-EREF-NO-PROFILE-{self.timestamp}"}],
            "name": [{"family": "NoProfile", "given": ["ShouldFailIfInterceptorWorks"]}],
            "gender": "male",
            "birthDate": "1990-01-01",
        }
        return self._write("eref-patient-no-profile.json", resource)

    def referring_organization(self) -> Path:
        """Generate a referring facility Organization."""
        resource = {
            "resourceType": "Organization",
            "identifier": [{"system": "https://doh.gov.ph/fhir/healthcare-facility-code", "value": f"REF-FACILITY-{self.timestamp}"}],
            "name": "Barangay Health Center Test",
        }
        return self._write("referring-organization.json", resource)

    def receiving_organization(self) -> Path:
        """Generate a receiving facility Organization."""
        resource = {
            "resourceType": "Organization",
            "identifier": [{"system": "https://doh.gov.ph/fhir/healthcare-facility-code", "value": f"REC-FACILITY-{self.timestamp}"}],
            "name": "Referral Hospital Test",
        }
        return self._write("receiving-organization.json", resource)

    def practitioner(self) -> Path:
        """Generate a referring Practitioner."""
        resource = {
            "resourceType": "Practitioner",
            "identifier": [{"system": "https://prc.gov.ph/license-number", "value": f"PRC-TEST-{self.timestamp}"}],
            "name": [{"family": "Reyes", "given": ["Maria"]}],
        }
        return self._write("practitioner.json", resource)

    def service_request(
        self, patient_id: str, practitioner_id: str, receiving_org_id: str
    ) -> Path:
        """Generate a referral ServiceRequest linking all actors."""
        resource: dict = {
            "resourceType": "ServiceRequest",
            "status": "active",
            "intent": "order",
            "category": [{"coding": [{"system": "http://terminology.hl7.org/CodeSystem/servicerequest-category", "code": "referral", "display": "Referral"}]}],
            "priority": "urgent",
            "code": {"text": "Referral for emergency consultation"},
            "subject": {"reference": f"Patient/{patient_id}" if patient_id else "Patient/UNKNOWN"},
            "requester": {"reference": f"Practitioner/{practitioner_id}" if practitioner_id else "Practitioner/UNKNOWN"},
            "performer": [{"reference": f"Organization/{receiving_org_id}" if receiving_org_id else "Organization/UNKNOWN"}],
            "authoredOn": date.today().isoformat(),
            "reasonCode": [{"text": "Persistent chest pain and shortness of breath"}],
            "note": [{"text": "eReferral test created by generate_eref_testing_report.py."}],
        }
        if self.config.service_request_profile_url:
            resource["meta"] = {"profile": [self.config.service_request_profile_url]}
        return self._write("eref-servicerequest.json", resource)

    def _write(self, filename: str, resource: dict) -> Path:
        path = self.payloads_dir / filename
        path.write_text(json.dumps(resource, indent=2, ensure_ascii=False), encoding="utf-8")
        return path




class TestRunner:
    """Executes the 15 eReferral FHIR test cases."""

    def __init__(self, config: Config, out_dir: Path, timestamp: str) -> None:
        self.config = config
        self.out_dir = out_dir
        self.client = FhirClient(config, out_dir)
        self.payloads = PayloadGenerator(config, timestamp, out_dir / "payloads")
        self.results: list[TestResult] = []
        # Resource IDs for cleanup
        self.patient_id = ""
        self.ref_org_id = ""
        self.rec_org_id = ""
        self.practitioner_id = ""
        self.sr_id = ""
        self.no_profile_patient_id = ""

    def run_all(self) -> None:
        """Execute all 15 tests sequentially."""
        self._test_01_metadata()
        self._test_02_implementation_guide()
        self._test_03_patient_profile()
        self._test_04_priority_valueset()
        self._test_05_workflow_codesystem()
        self._test_06_validate_valid_patient()
        self._test_07_validate_invalid_patient()
        self._test_08_create_no_profile_patient()
        self._test_09_create_patient()
        self._test_10_create_referring_org()
        self._test_11_create_receiving_org()
        self._test_12_create_practitioner()
        self._test_13_create_service_request()
        self._test_14_search_patient()
        self._test_15_search_service_request()

    def cleanup(self) -> None:
        """Delete created test resources if KEEP_CREATED is false."""
        if self.config.keep_created:
            return
        self.client.delete("ServiceRequest", self.sr_id, "13-create-servicerequest-referral")
        self.client.delete("Practitioner", self.practitioner_id, "12-create-practitioner")
        self.client.delete("Organization", self.rec_org_id, "11-create-receiving-organization")
        self.client.delete("Organization", self.ref_org_id, "10-create-referring-organization")
        self.client.delete("Patient", self.patient_id, "09-create-eref-patient")

    def _extract_id(self, resp: HttpResponse) -> str:
        """Extract resource ID from response body or Location header."""
        rid = resp.body.get("id", "")
        if rid:
            return str(rid)
        location = resp.headers.get("Location", "") or resp.headers.get("Content-Location", "")
        if location:
            match = re.search(r"/([^/\s]+)$", location.split("?")[0])
            if match:
                return match.group(1)
        return ""

    def _add(self, num: int, name: str, endpoint: str, http: str,
             expected: str, actual: str, finding: str, log: str) -> None:
        result = TestResult(num, name, endpoint, http, expected, actual, finding, log)
        self.results.append(result)
        print(f"[{num}] {name} -> HTTP {http} | {finding}")

    def _issue_count(self, body: dict, severity: str) -> int:
        return sum(1 for i in body.get("issue", []) if i.get("severity") == severity)

    def _test_01_metadata(self) -> None:
        """Test 1: CapabilityStatement - verify server is reachable."""
        resp = self.client.call("01-metadata", "GET", f"{self.config.base_url}/metadata?_pretty=true")
        server_name = resp.body.get("software", {}).get("name", "Unknown")
        fhir_version = resp.body.get("fhirVersion", "Unknown")
        finding = "✅ Server reachable" if resp.status_code == "200" else "❌ Server not reachable"
        self._add(1, "Metadata", "GET /metadata", resp.status_code,
                  "CapabilityStatement", f"{server_name} {fhir_version}", finding, "logs/01-metadata.json")

    def _test_02_implementation_guide(self) -> None:
        """Test 2: Search for ImplementationGuide resources."""
        resp = self.client.call("02-implementationguide-list", "GET",
                                f"{self.config.base_url}/ImplementationGuide?_pretty=true")
        total = resp.body.get("total", 0)
        finding = "✅ IG listed" if total else "⚠️ No IG resources listed"
        self._add(2, "ImplementationGuide list", "GET /ImplementationGuide", resp.status_code,
                  "IG resources visible", f"total={total}", finding, "logs/02-implementationguide-list.json")

    def _test_03_patient_profile(self) -> None:
        """Test 3: Search for eReferral Patient StructureDefinition."""
        encoded = urllib.parse.quote(self.config.eref_patient_profile_url, safe="")
        resp = self.client.call("03-eref-patient-profile-search", "GET",
                                f"{self.config.base_url}/StructureDefinition?url={encoded}&_pretty=true")
        total = resp.body.get("total", 0)
        finding = "✅ Profile found" if total else "❌ Profile not found"
        self._add(3, "eReferral Patient profile", "GET /StructureDefinition?url=...", resp.status_code,
                  "Profile found", f"total={total}", finding, "logs/03-eref-patient-profile-search.json")

    def _test_04_priority_valueset(self) -> None:
        """Test 4: Search for eReferral priority ValueSet."""
        encoded = urllib.parse.quote(self.config.eref_priority_vs_url, safe="")
        resp = self.client.call("04-eref-priority-valueset-search", "GET",
                                f"{self.config.base_url}/ValueSet?url={encoded}&_pretty=true")
        total = resp.body.get("total", 0)
        finding = "✅ ValueSet found" if total else "⚠️ ValueSet not found"
        self._add(4, "eReferral priority ValueSet", "GET /ValueSet?url=...", resp.status_code,
                  "ValueSet found", f"total={total}", finding, "logs/04-eref-priority-valueset-search.json")

    def _test_05_workflow_codesystem(self) -> None:
        """Test 5: Search for eReferral workflow CodeSystem."""
        encoded = urllib.parse.quote(self.config.eref_workflow_cs_url, safe="")
        resp = self.client.call("05-eref-workflow-codesystem-search", "GET",
                                f"{self.config.base_url}/CodeSystem?url={encoded}&_pretty=true")
        total = resp.body.get("total", 0)
        finding = "✅ CodeSystem found" if total else "⚠️ CodeSystem not found"
        self._add(5, "eReferral workflow CodeSystem", "GET /CodeSystem?url=...", resp.status_code,
                  "CodeSystem found", f"total={total}", finding, "logs/05-eref-workflow-codesystem-search.json")

    def _test_06_validate_valid_patient(self) -> None:
        """Test 6: $validate a conformant eReferral Patient."""
        payload = self.payloads.valid_patient()
        resp = self.client.call("06-validate-eref-patient-valid", "POST",
                                f"{self.config.base_url}/Patient/$validate?_pretty=true", payload)
        errors = self._issue_count(resp.body, "error")
        warnings = self._issue_count(resp.body, "warning")
        finding = "✅ No validation errors" if errors == 0 else "❌ Review OperationOutcome"
        self._add(6, "Validate valid eReferral Patient", "POST /Patient/$validate", resp.status_code,
                  "0 errors", f"errors={errors} warnings={warnings}", finding,
                  "logs/06-validate-eref-patient-valid.json")

    def _test_07_validate_invalid_patient(self) -> None:
        """Test 7: $validate a non-conformant Patient (should produce errors)."""
        payload = self.payloads.invalid_patient()
        resp = self.client.call("07-validate-eref-patient-invalid", "POST",
                                f"{self.config.base_url}/Patient/$validate?_pretty=true", payload)
        errors = self._issue_count(resp.body, "error")
        warnings = self._issue_count(resp.body, "warning")
        finding = "✅ Invalid patient detected" if errors else "⚠️ No errors returned"
        self._add(7, "Validate invalid eReferral Patient", "POST /Patient/$validate", resp.status_code,
                  "Should return errors", f"errors={errors} warnings={warnings}", finding,
                  "logs/07-validate-eref-patient-invalid.json")

    def _test_08_create_no_profile_patient(self) -> None:
        """Test 8: Create Patient without meta.profile (interceptor should block)."""
        payload = self.payloads.no_profile_patient()
        resp = self.client.call("08-create-patient-no-profile", "POST",
                                f"{self.config.base_url}/Patient?_pretty=true", payload)
        self.no_profile_patient_id = self._extract_id(resp) if resp.status_code.startswith("2") else ""
        if resp.status_code.startswith("2"):
            finding = "⚠️ Accepted without profile"
        else:
            finding = "✅ Blocked without profile"
        self._add(8, "Create Patient without profile", "POST /Patient", resp.status_code,
                  "Blocked if interceptor requires profile",
                  f"Patient/{self.no_profile_patient_id or 'not-created'}", finding,
                  "logs/08-create-patient-no-profile.json")
        if not self.config.keep_created and self.no_profile_patient_id:
            self.client.delete("Patient", self.no_profile_patient_id, "08-create-patient-no-profile")

    def _test_09_create_patient(self) -> None:
        """Test 9: Create a conformant eReferral Patient."""
        payload = self.payloads.valid_patient()
        resp = self.client.call("09-create-eref-patient", "POST",
                                f"{self.config.base_url}/Patient?_pretty=true", payload)
        self.patient_id = self._extract_id(resp)
        finding = "✅ Created" if resp.status_code.startswith("2") else "❌ Failed"
        self._add(9, "Create eReferral Patient", "POST /Patient", resp.status_code,
                  "Created", f"Patient/{self.patient_id or 'not-created'}", finding,
                  "logs/09-create-eref-patient.json")

    def _test_10_create_referring_org(self) -> None:
        """Test 10: Create referring Organization."""
        payload = self.payloads.referring_organization()
        resp = self.client.call("10-create-referring-organization", "POST",
                                f"{self.config.base_url}/Organization?_pretty=true", payload)
        self.ref_org_id = self._extract_id(resp)
        finding = "✅ Created" if resp.status_code.startswith("2") else "❌ Failed"
        self._add(10, "Create referring Organization", "POST /Organization", resp.status_code,
                  "Created", f"Organization/{self.ref_org_id or 'not-created'}", finding,
                  "logs/10-create-referring-organization.json")

    def _test_11_create_receiving_org(self) -> None:
        """Test 11: Create receiving Organization."""
        payload = self.payloads.receiving_organization()
        resp = self.client.call("11-create-receiving-organization", "POST",
                                f"{self.config.base_url}/Organization?_pretty=true", payload)
        self.rec_org_id = self._extract_id(resp)
        finding = "✅ Created" if resp.status_code.startswith("2") else "❌ Failed"
        self._add(11, "Create receiving Organization", "POST /Organization", resp.status_code,
                  "Created", f"Organization/{self.rec_org_id or 'not-created'}", finding,
                  "logs/11-create-receiving-organization.json")

    def _test_12_create_practitioner(self) -> None:
        """Test 12: Create referring Practitioner."""
        payload = self.payloads.practitioner()
        resp = self.client.call("12-create-practitioner", "POST",
                                f"{self.config.base_url}/Practitioner?_pretty=true", payload)
        self.practitioner_id = self._extract_id(resp)
        finding = "✅ Created" if resp.status_code.startswith("2") else "❌ Failed"
        self._add(12, "Create Practitioner", "POST /Practitioner", resp.status_code,
                  "Created", f"Practitioner/{self.practitioner_id or 'not-created'}", finding,
                  "logs/12-create-practitioner.json")

    def _test_13_create_service_request(self) -> None:
        """Test 13: Create referral ServiceRequest linking Patient, Practitioner, Organization."""
        if not (self.patient_id and self.practitioner_id and self.rec_org_id):
            finding = "❌ Failed or skipped"
            self._add(13, "Create referral ServiceRequest", "POST /ServiceRequest", "SKIPPED",
                      "Created", "ServiceRequest/not-created", finding,
                      "logs/13-create-servicerequest-referral.json")
            # Write a placeholder log
            log_path = self.out_dir / "logs" / "13-create-servicerequest-referral.json"
            log_path.write_text(json.dumps({
                "resourceType": "OperationOutcome",
                "issue": [{"severity": "error", "code": "processing",
                           "diagnostics": "Skipped because Patient, Practitioner, or receiving Organization was not created."}]
            }, indent=2), encoding="utf-8")
            return

        payload = self.payloads.service_request(self.patient_id, self.practitioner_id, self.rec_org_id)
        resp = self.client.call("13-create-servicerequest-referral", "POST",
                                f"{self.config.base_url}/ServiceRequest?_pretty=true", payload)
        self.sr_id = self._extract_id(resp)
        finding = "✅ Created" if resp.status_code.startswith("2") else "❌ Failed or skipped"
        self._add(13, "Create referral ServiceRequest", "POST /ServiceRequest", resp.status_code,
                  "Created", f"ServiceRequest/{self.sr_id or 'not-created'}", finding,
                  "logs/13-create-servicerequest-referral.json")

    def _test_14_search_patient(self) -> None:
        """Test 14: Search Patient by identifier."""
        encoded = urllib.parse.quote(f"PH-EREF-TEST-{self.payloads.timestamp}", safe="")
        resp = self.client.call("14-search-patient-by-identifier", "GET",
                                f"{self.config.base_url}/Patient?identifier={encoded}&_pretty=true")
        total = resp.body.get("total", 0)
        finding = "✅ Patient searchable" if total else "⚠️ Patient not found"
        self._add(14, "Search Patient by identifier", "GET /Patient?identifier=...", resp.status_code,
                  "total >= 1", f"total={total}", finding, "logs/14-search-patient-by-identifier.json")

    def _test_15_search_service_request(self) -> None:
        """Test 15: Search ServiceRequest by subject reference."""
        if not self.patient_id:
            self._add(15, "Search ServiceRequest by Patient", "GET /ServiceRequest?subject=Patient/...",
                      "SKIPPED", "total >= 1", "total=0", "⚠️ Referral not found",
                      "logs/15-search-servicerequest-by-subject.json")
            log_path = self.out_dir / "logs" / "15-search-servicerequest-by-subject.json"
            log_path.write_text(json.dumps({
                "resourceType": "OperationOutcome",
                "issue": [{"severity": "error", "code": "processing",
                           "diagnostics": "Skipped because Patient was not created."}]
            }, indent=2), encoding="utf-8")
            return

        encoded = urllib.parse.quote(f"Patient/{self.patient_id}", safe="")
        resp = self.client.call("15-search-servicerequest-by-subject", "GET",
                                f"{self.config.base_url}/ServiceRequest?subject={encoded}&_pretty=true")
        total = resp.body.get("total", 0)
        finding = "✅ Referral searchable" if total else "⚠️ Referral not found"
        self._add(15, "Search ServiceRequest by Patient", "GET /ServiceRequest?subject=Patient/...",
                  resp.status_code, "total >= 1", f"total={total}", finding,
                  "logs/15-search-servicerequest-by-subject.json")


class ReportGenerator:
    """Generates Markdown, HTML, JSON, and TSV reports from test results."""

    def __init__(self, config: Config, out_dir: Path, results: list[TestResult]) -> None:
        self.config = config
        self.out_dir = out_dir
        self.results = results

    def determine_critical_finding(self) -> tuple[str, str]:
        """Determine the most critical finding based on test results."""
        result_map = {r.num: r for r in self.results}

        r1 = result_map.get(1)
        if r1 and r1.http_status != "200":
            return ("eReferral server is not reachable",
                    "Check that your eReferral HAPI container is running and mapped to the correct host port, usually http://localhost:8081/fhir.")

        r3 = result_map.get(3)
        if r3 and "total=0" in r3.actual:
            return ("eReferral Patient profile is not loaded",
                    "The server is alive, but it did not find the configured eReferral Patient StructureDefinition. Fix the eReferral IG package loading before relying on validation.")

        r6 = result_map.get(6)
        if r6 and "errors=0" not in r6.actual:
            return ("eReferral profile found, but valid Patient has validation errors",
                    "Review logs/06-validate-eref-patient-valid.json. The profile may require fields not included in the simple test payload, or terminology support may be incomplete.")

        r13 = result_map.get(13)
        if r13 and not r13.http_status.startswith("2"):
            return ("Patient/actor creation ran, but ServiceRequest failed",
                    "Review logs/13-create-servicerequest-referral.json. This is usually caused by an interceptor rule, an invalid reference, or a profile requirement on ServiceRequest.")

        return ("Basic eReferral flow appears working",
                "The server was reachable, the eReferral Patient profile was checked, and the script created Patient, Organization, Practitioner, and ServiceRequest test resources.")

    def generate_all(self, status: str = "completed") -> None:
        """Generate all report artifacts."""
        critical_title, critical_text = self.determine_critical_finding()
        self._write_tsv()
        self._write_json(status, critical_title)
        self._write_markdown(critical_title, critical_text)
        self._write_html()

    def _write_tsv(self) -> None:
        path = self.out_dir / "test-summary.tsv"
        lines = ["#\tTest\tEndpoint\tHTTP\tExpected\tActual\tFinding\tLog"]
        for r in self.results:
            lines.append(f"{r.num}\t{r.name}\t{r.endpoint}\t{r.http_status}\t{r.expected}\t{r.actual}\t{r.finding}\t{r.log_file}")
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    def _write_json(self, status: str, critical_title: str) -> None:
        path = self.out_dir / "summary.json"
        data = {
            "status": status,
            "baseUrl": self.config.base_url,
            "erefPatientProfileUrl": self.config.eref_patient_profile_url,
            "erefPriorityValueSetUrl": self.config.eref_priority_vs_url,
            "erefWorkflowCodeSystemUrl": self.config.eref_workflow_cs_url,
            "serviceRequestProfileUrl": self.config.service_request_profile_url,
            "keepCreated": str(self.config.keep_created).lower(),
            "criticalTitle": critical_title,
            "testsRun": len(self.results),
            "tests": [
                {"num": r.num, "name": r.name, "endpoint": r.endpoint,
                 "http": r.http_status, "expected": r.expected, "actual": r.actual,
                 "finding": r.finding, "log": r.log_file}
                for r in self.results
            ],
        }
        path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")

    def _write_markdown(self, critical_title: str, critical_text: str) -> None:
        path = self.out_dir / "eref-testing-results.md"
        lines = [
            f"# eReferral FHIR Server Testing Results — {self.config.base_url}",
            "",
            f"Generated: {datetime.now().isoformat()}",
            "",
            "## Critical Finding",
            "",
            f"**{critical_title}**",
            "",
            critical_text,
            "",
            "## Configuration",
            "",
            "| Item | Value |",
            "|---|---|",
            f"| Base URL | {self.config.base_url} |",
            f"| eReferral Patient Profile | {self.config.eref_patient_profile_url} |",
            f"| Priority ValueSet | {self.config.eref_priority_vs_url} |",
            f"| Workflow CodeSystem | {self.config.eref_workflow_cs_url} |",
            f"| ServiceRequest Profile | {self.config.service_request_profile_url or 'Not set. Plain FHIR ServiceRequest used.'} |",
            f"| Keep Created Resources | {self.config.keep_created} |",
            "",
            "## Test Summary",
            "",
            "| # | Test | Endpoint | HTTP | Expected | Actual | Finding | Log |",
            "|---|---|---|---|---|---|---|---|",
        ]
        for r in self.results:
            lines.append(f"| {r.num} | {r.name} | `{r.endpoint}` | {r.http_status} | {r.expected} | {r.actual} | {r.finding} | `{r.log_file}` |")

        lines.extend(["", "## Important Raw Logs", ""])
        logs_dir = self.out_dir / "logs"
        for log_file in sorted(logs_dir.glob("*.json")):
            lines.append(f"### {log_file.name}")
            lines.append("")
            lines.append("```text")
            lines.append(self._brief_findings(log_file))
            lines.append("```")
            lines.append("")

        lines.extend([
            "## Files",
            "",
            f"- Summary JSON: `{self.out_dir}/summary.json`",
            f"- Markdown report: `{path}`",
            f"- HTML report: `{self.out_dir}/eref-testing-results.html`",
            f"- Payloads: `{self.out_dir}/payloads/`",
            f"- Logs: `{self.out_dir}/logs/`",
        ])
        path.write_text("\n".join(lines), encoding="utf-8")

    def _brief_findings(self, file: Path) -> str:
        """Summarize a JSON log file."""
        try:
            data = json.loads(file.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return "No JSON response. Check .err and .headers files."

        rt = data.get("resourceType")
        if rt == "OperationOutcome":
            issues = data.get("issue", [])
            if not issues:
                return "OperationOutcome returned with no issues."
            lines = []
            for issue in issues[:8]:
                sev = issue.get("severity", "").upper()
                diag = issue.get("diagnostics") or issue.get("details", {}).get("text") or issue.get("code", "")
                lines.append(f"{sev}: {diag}")
            return "\n".join(lines)
        elif rt == "Bundle":
            lines = [f"Bundle type={data.get('type', '')}, total={data.get('total', 0)}"]
            for entry in data.get("entry", [])[:5]:
                res = entry.get("resource", {})
                if res:
                    lines.append(f"- {res.get('resourceType', 'Resource')}/{res.get('id', '')}")
            return "\n".join(lines)
        elif rt:
            rid = data.get("id", "")
            return f"{rt}/{rid}" if rid else rt
        return "JSON response received, but resourceType is missing."

    def _write_html(self) -> None:
        """Convert the Markdown report to a self-contained HTML file."""
        md_path = self.out_dir / "eref-testing-results.md"
        html_path = self.out_dir / "eref-testing-results.html"
        text = md_path.read_text(encoding="utf-8")

        def inline(s: str) -> str:
            s = html_mod.escape(s)
            s = re.sub(r"`([^`]+)`", r"<code>\1</code>", s)
            s = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", s)
            return s

        out: list[str] = []
        in_code = False
        code: list[str] = []
        in_table = False

        def close_table() -> None:
            nonlocal in_table
            if in_table:
                out.append("</tbody></table>")
                in_table = False

        for line in text.splitlines():
            if line.startswith("```"):
                if not in_code:
                    close_table()
                    in_code = True
                    code = []
                else:
                    out.append(f"<pre><code>{html_mod.escape(chr(10).join(code))}</code></pre>")
                    in_code = False
                continue
            if in_code:
                code.append(line)
                continue
            if not line.strip():
                close_table()
                continue
            if line.startswith("# "):
                close_table()
                out.append(f"<h1>{inline(line[2:])}</h1>")
            elif line.startswith("## "):
                close_table()
                out.append(f"<h2>{inline(line[3:])}</h2>")
            elif line.startswith("### "):
                close_table()
                out.append(f"<h3>{inline(line[4:])}</h3>")
            elif line.startswith("|") and line.endswith("|"):
                cells = [c.strip() for c in line.strip("|").split("|")]
                if all(set(c) <= set("-: ") for c in cells):
                    continue
                if not in_table:
                    out.append("<table><tbody>")
                    in_table = True
                    tag = "th"
                else:
                    tag = "td"
                header_cells = ("#", "Item", "Value", "Test", "Endpoint", "HTTP", "Expected", "Actual", "Finding", "Log")
                if any(c in header_cells for c in cells):
                    tag = "th"
                out.append("<tr>" + "".join(f"<{tag}>{inline(c)}</{tag}>" for c in cells) + "</tr>")
            elif line.startswith("- "):
                close_table()
                out.append(f"<p>• {inline(line[2:])}</p>")
            else:
                close_table()
                out.append(f"<p>{inline(line)}</p>")
        close_table()

        css = ("body{font-family:Arial,Helvetica,sans-serif;max-width:1100px;margin:30px auto;"
               "line-height:1.45;color:#111}table{border-collapse:collapse;width:100%;margin:16px 0}"
               "th,td{border:1px solid #ddd;padding:8px 10px;text-align:left;vertical-align:top}"
               "th{background:#f7f7f7}code{background:#f4f4f4;padding:2px 5px;border-radius:4px}"
               "pre{background:#f8f8f8;padding:16px;overflow-x:auto;border:1px solid #eee;border-radius:4px}"
               "h1{font-size:30px}h2{margin-top:30px}")
        html_content = (
            f'<!doctype html><html><head><meta charset="utf-8">'
            f'<title>eReferral FHIR Testing Results</title><style>{css}</style></head><body>'
            + "\n".join(out) + "</body></html>"
        )
        html_path.write_text(html_content, encoding="utf-8")


def main() -> None:
    """Entry point: configure, run tests, generate reports."""
    config = Config.from_env(sys.argv)
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    out_dir = Path(f"eref-testing-results-{timestamp}")
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "logs").mkdir(exist_ok=True)
    (out_dir / "payloads").mkdir(exist_ok=True)

    print("Starting eReferral FHIR tests...")
    print(f"Base URL: {config.base_url}")
    print(f"Output folder: {out_dir}")
    print()

    runner = TestRunner(config, out_dir, timestamp)
    status = "completed"
    try:
        runner.run_all()
    except Exception as e:
        print(f"\nError during test execution: {e}", file=sys.stderr)
        status = "partial"
    finally:
        runner.cleanup()

    report = ReportGenerator(config, out_dir, runner.results)
    report.generate_all(status)

    print()
    print("==============================================")
    print("eReferral FHIR testing report generated")
    print(f"Folder: {out_dir}")
    print(f"Summary: {out_dir}/summary.json")
    print(f"Markdown: {out_dir}/eref-testing-results.md")
    print(f"HTML: {out_dir}/eref-testing-results.html")
    print("==============================================")


if __name__ == "__main__":
    main()
