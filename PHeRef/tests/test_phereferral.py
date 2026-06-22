#!/usr/bin/env python3
"""PH eReferral Example Resource Tests.

POSTs the transaction bundle and PUTs each individual example to a FHIR server.
Generates a timestamped markdown report in PHeRef/reports/.

Usage:
    python tests/test_phereferral.py
    python tests/test_phereferral.py --base-url http://localhost:8080/fhir
    python tests/test_phereferral.py --base-url http://localhost:8080/fhir --examples-dir testdata/examples
"""

import json, os, sys, glob, time, argparse
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_DIR = SCRIPT_DIR.parent / "PHeRef"

DEFAULT_EXAMPLES_DIR = str(PROJECT_DIR / "testdata" / "examples")
DEFAULT_REPORT_DIR = str(SCRIPT_DIR.parent / "reports")
DEFAULT_TIMEOUT = 120


def load_env_base_url(env_path: Path) -> str | None:
    if not env_path.is_file():
        return None
    addr = None
    port = None
    for line in env_path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            continue
        key, _, val = line.partition("=")
        key, val = key.strip(), val.strip().strip("\"'")
        if key == "PHEREF_SERVER_ADDRESS":
            addr = val.rstrip("/")
        elif key == "PHEREF_SERVER_PORT":
            port = val
    if addr and port:
        return f"{addr}:{port}/fhir"
    if addr:
        return f"{addr}/fhir"
    return None


def resolve_base_url(args_base_url: str | None) -> str:
    if args_base_url:
        return args_base_url.rstrip("/")
    env_url = load_env_base_url(PROJECT_DIR / ".env")
    if env_url:
        return env_url.rstrip("/")
    return "http://localhost:8080/fhir"


def extract_domain_label(base_url: str) -> str:
    """Extract a human-readable domain label from a FHIR base URL.

    Examples:
      http://localhost:8080/fhir      -> localhost
      https://cdr.pheref.fhirlab.net  -> cdr.pheref.fhirlab.net
      https://fhirportal.telehealth.ph -> fhirportal.telehealth.ph
    """
    host = urlparse(base_url).hostname or "unknown"
    return host


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

try:
    import requests
except ImportError:
    print("ERROR: 'requests' library is required. Install with: pip install requests")
    sys.exit(1)


def server_reachable(base_url: str, timeout: int = 5) -> bool:
    try:
        r = requests.get(f"{base_url}/metadata", timeout=timeout, headers={"Accept": "application/fhir+json"})
        return r.status_code < 500
    except requests.exceptions.RequestException:
        return False


def extract_response_errors(status_code: int, body: dict) -> list[str]:
    """Extract error messages from a FHIR response body.

    Checks for OperationOutcome issues with severity error/fatal,
    and for Bundle transaction responses checks each entry's status + outcome.
    """
    errors = []
    rt = body.get("resourceType")
    if rt == "OperationOutcome":
        for issue in body.get("issue", []):
            sev = issue.get("severity", "")
            if sev in ("error", "fatal"):
                errors.append(f"[{sev}] {issue.get('diagnostics', issue.get('details', {}).get('text', ''))}")
    if rt == "Bundle":
        entries = body.get("entry", [])
        if not entries and status_code >= 300:
            errors.append("Empty response bundle")
        for i, entry in enumerate(entries):
            resp = entry.get("response", {})
            entry_status_str = resp.get("status", "")
            entry_code = int(entry_status_str.split()[0]) if entry_status_str and entry_status_str.split()[0].isdigit() else status_code
            if entry_code >= 300:
                errors.append(f"  entry[{i}] HTTP {entry_status_str}")
            outcome = resp.get("outcome")
            if outcome and outcome.get("resourceType") == "OperationOutcome":
                for issue in outcome.get("issue", []):
                    sev = issue.get("severity", "")
                    if sev in ("error", "fatal"):
                        errors.append(f"  entry[{i}] [{sev}] {issue.get('diagnostics', '')}")
    return errors


def build_uuid_map_from_bundle_response(bundle_response: dict, bundle_request: dict) -> dict[str, str]:
    """Build a mapping from urn:uuid → ResourceType/ID from a transaction Bundle response.

    Uses the Bundle request entries' fullUrl (which contains urn:uuid) and
    the corresponding response entries' location (which contains ResourceType/ID).
    """
    uuid_map = {}
    request_entries = bundle_request.get("entry", [])
    response_entries = bundle_response.get("entry", [])
    for req_entry, resp_entry in zip(request_entries, response_entries):
        full_url = req_entry.get("fullUrl", "")
        location = resp_entry.get("response", {}).get("location", "")
        if full_url.startswith("urn:uuid:") and location:
            resource_path = location.split("/_history")[0] if "/_history" in location else location
            uuid_map[full_url] = resource_path
    return uuid_map


def replace_urn_uuid_refs(obj, uuid_map: dict[str, str]):
    """Recursively walk a parsed JSON object and replace urn:uuid: references.

    Handles:
      - {"reference": "urn:uuid:..."}
      - {"reference": {"identifier": ...}} — not touched
      - Any string value that is an urn:uuid
    """
    if isinstance(obj, dict):
        for key, val in obj.items():
            if key == "reference" and isinstance(val, str) and val in uuid_map:
                obj[key] = uuid_map[val]
            else:
                replace_urn_uuid_refs(val, uuid_map)
    elif isinstance(obj, list):
        for item in obj:
            replace_urn_uuid_refs(item, uuid_map)


# ---------------------------------------------------------------------------
# test results
# ---------------------------------------------------------------------------

class TestResult:
    __slots__ = ("name", "resource_type", "method", "url", "status", "response_time", "success", "errors")

    def __init__(self, name, resource_type, method, url, status, response_time, success, errors=None):
        self.name = name
        self.resource_type = resource_type
        self.method = method
        self.url = url
        self.status = status
        self.response_time = response_time
        self.success = success
        self.errors = errors or []


# ---------------------------------------------------------------------------
# test runners
# ---------------------------------------------------------------------------

def post_bundle(base_url: str, path: str, timeout: int, results: list[TestResult]) -> dict | None:
    with open(path) as f:
        bundle = json.load(f)
    resource_type = bundle.get("resourceType", "Bundle")
    resource_id = bundle.get("id", os.path.basename(path))
    url = f"{base_url}"
    print(f"  {resource_type}/{resource_id}")
    print(f"  POST {url}")
    start = time.time()
    try:
        r = requests.post(url, json=bundle, headers={"Content-Type": "application/fhir+json"}, timeout=timeout)
        elapsed = time.time() - start
        body = r.json() if r.text else {}
        errors = extract_response_errors(r.status_code, body)
        ok = 200 <= r.status_code < 300 and not errors
        if ok:
            _print_success(r, elapsed)
        else:
            _print_failure(r, elapsed, errors)
        results.append(TestResult(resource_id, resource_type, "POST", url, r.status_code, elapsed, ok, errors))
        return body if ok else None
    except Exception as e:
        elapsed = time.time() - start
        print(f"  ERROR: {e}")
        results.append(TestResult(resource_id, resource_type, "POST", url, 0, elapsed, False, [str(e)]))
        return None


def put_resource(base_url: str, path: str, timeout: int, results: list[TestResult]):
    with open(path) as f:
        resource = json.load(f)
    resource_type = resource.get("resourceType", "Unknown")
    resource_id = resource.get("id", os.path.basename(path))
    url = f"{base_url}/{resource_type}/{resource_id}"
    print(f"  {resource_type}/{resource_id}")
    print(f"  PUT {url}")
    start = time.time()
    try:
        r = requests.put(url, json=resource, headers={"Content-Type": "application/fhir+json"}, timeout=timeout)
        elapsed = time.time() - start
        body = r.json() if r.text else {}
        errors = extract_response_errors(r.status_code, body)
        ok = 200 <= r.status_code < 300 and not errors
        if ok:
            _print_success(r, elapsed)
        else:
            _print_failure(r, elapsed, errors)
        results.append(TestResult(resource_id, resource_type, "PUT", url, r.status_code, elapsed, ok, errors))
    except Exception as e:
        elapsed = time.time() - start
        print(f"  ERROR: {e}")
        results.append(TestResult(resource_id, resource_type, "PUT", url, 0, elapsed, False, [str(e)]))


def validate_json(path: str, results: list[TestResult]):
    fname = os.path.basename(path)
    try:
        with open(path) as f:
            data = json.load(f)
        rt = data.get("resourceType", "Unknown")
        rid = data.get("id", fname)
        if not data.get("resourceType"):
            raise ValueError("Missing resourceType")
        if rt == "Bundle":
            entries = data.get("entry", [])
            print(f"  Bundle/{rid} — {len(entries)} entries, JSON valid")
        else:
            print(f"  {rt}/{rid} — JSON valid")
        results.append(TestResult(rid, rt, "DRY", "", 0, 0, True))
    except (json.JSONDecodeError, ValueError) as e:
        print(f"  INVALID: {e}")
        results.append(TestResult(fname, "Unknown", "DRY", "", 0, 0, False, [str(e)]))


# ---------------------------------------------------------------------------
# output helpers
# ---------------------------------------------------------------------------

def _print_success(r, elapsed):
    print(f"  ├─ Status: {r.status_code} ({(elapsed):.3f}s) ✓")


def _print_failure(r, elapsed, errors=None):
    print(f"  ├─ Status: {r.status_code} ({(elapsed):.3f}s) ✗")
    if errors:
        for e in errors[:5]:
            print(f"  ├─ {e}"[:250])
    if not errors:
        try:
            body = r.json()
            issue = body.get("issue", [])
            if issue:
                for iss in issue[:3]:
                    print(f"  ├─ {iss.get('severity','')} {iss.get('diagnostics','')}"[:200])
        except Exception:
            pass
        print(f"  └─ Body: {r.text[:200]}")
    print()


# ---------------------------------------------------------------------------
# error categorization
# ---------------------------------------------------------------------------

ERROR_CATEGORIES = {
    "terminology": {
        "label": "Terminology / Code Validation",
        "patterns": ["Unable to validate code", "Unknown code", "Code is not found", "CodeSystem"],
        "narrative": "The server could not validate terminology codes (SNOMED, LOINC, UCUM, etc.) against its terminology server. This typically means the remote terminology service lacks the required CodeSystem or version.",
    },
    "urn_uuid_ref": {
        "label": "Unresolved Bundle-Scoped Reference (urn:uuid)",
        "patterns": ["urn:uuid", "Invalid resource reference", "Does not contain resource type"],
        "narrative": "The resource references a Bundle-scoped temporary identifier (urn:uuid) that could not be resolved. This happens when resources are loaded individually instead of through a transaction Bundle.",
    },
    "missing_prereq": {
        "label": "Missing Prerequisite Resource",
        "patterns": ["not found, specified in path"],
        "narrative": "A resource references another resource that does not exist on the server. Resources must be loaded in dependency order (standalone resources first, then referencing resources).",
    },
    "endpoint_404": {
        "label": "Endpoint Not Found (404)",
        "patterns": ["404"],
        "narrative": "The server returned HTTP 404, indicating the FHIR endpoint path is incorrect or the server does not support the requested resource type.",
    },
    "timeout": {
        "label": "Request Timeout",
        "patterns": ["timed out", "Read timed out", "Timeout"],
        "narrative": "The server did not respond within the configured timeout. This may indicate slow performance, high load, or a blocking operation.",
    },
}


def categorize_errors(results: list[TestResult]) -> dict:
    """Categorize all errors across failed results into groups."""
    counts: dict[str, int] = {}
    affected: dict[str, list[str]] = {}
    for cat_key, cat in ERROR_CATEGORIES.items():
        counts[cat_key] = 0
        affected[cat_key] = []
    counts["other"] = 0
    affected["other"] = []

    for r in results:
        if r.success:
            continue
        categorized = False
        for err in r.errors:
            for cat_key, cat in ERROR_CATEGORIES.items():
                for pat in cat["patterns"]:
                    if pat.lower() in err.lower():
                        counts[cat_key] += 1
                        resource_id = f"{r.resource_type}/{r.name}"
                        if resource_id not in affected[cat_key]:
                            affected[cat_key].append(resource_id)
                        categorized = True
                        break
                if categorized:
                    break
        if not categorized and r.errors:
            counts["other"] += len(r.errors)
            resource_id = f"{r.resource_type}/{r.name}"
            if resource_id not in affected["other"]:
                affected["other"].append(resource_id)

    return {"counts": counts, "affected": affected}


def generate_narrative(results: list[TestResult], total_time: float) -> list[str]:
    """Generate a narrative summary of test outcomes."""
    passed = sum(1 for r in results if r.success)
    total = len(results)
    failed = [r for r in results if not r.success]
    cat_data = categorize_errors(results)

    lines = ["## Analysis", ""]

    if passed == total:
        lines.append("All resources loaded successfully with no errors.")
        lines.append("")
    else:
        active_cats = {k: v for k, v in cat_data["counts"].items() if v > 0}
        if active_cats:
            lines.append("### Error Breakdown")
            lines.append("")
            lines.append("| Category | Occurrences | Affected Resources |")
            lines.append("|---|---|---|")
            for cat_key, count in sorted(active_cats.items(), key=lambda x: -x[1]):
                if cat_key == "other":
                    label = "Other / Unclassified"
                else:
                    label = ERROR_CATEGORIES.get(cat_key, {}).get("label", cat_key)
                aff_list = cat_data["affected"].get(cat_key, [])
                aff_str = ", ".join(aff_list[:5])
                if len(aff_list) > 5:
                    aff_str += f" … and {len(aff_list) - 5} more"
                lines.append(f"| {label} | {count} | {aff_str} |")
            lines.append("")

            lines.append("### Root Cause Narratives")
            lines.append("")
            for cat_key in sorted(active_cats.keys(), key=lambda k: -active_cats[k]):
                if cat_key == "other":
                    lines.append(f"- **Other errors:** {active_cats[cat_key]} unclassified error(s) in {len(cat_data['affected'].get(cat_key, []))} resource(s).")
                else:
                    cat = ERROR_CATEGORIES[cat_key]
                    aff_list = cat_data["affected"][cat_key]
                    lines.append(f"- **{cat['label']}:** {cat['narrative']} Affected resources: {', '.join(aff_list)}.")
            lines.append("")

        if failed:
            lines.append(f"### Failures Detail")
            lines.append("")
            for r in failed:
                lines.extend([
                    f"#### {r.resource_type}/{r.name}",
                    f"",
                    f"- **HTTP {r.status}** in {r.response_time:.3f}s",
                ])
                for err in r.errors[:3]:
                    lines.append(f"- `{err}`")
                if len(r.errors) > 3:
                    lines.append(f"- *… and {len(r.errors) - 3} more errors*")
                lines.append("")

    lines.append("### Timing")
    lines.append("")
    times = [r.response_time for r in results if r.response_time > 0]
    if times:
        lines.append(f"- **Total wall time:** {total_time:.1f}s")
        lines.append(f"- **Fastest:** {min(times):.3f}s  **Slowest:** {max(times):.3f}s  **Average:** {sum(times)/len(times):.3f}s")
    lines.append("")
    return lines


def generate_markdown(results: list[TestResult], timestamp: str, base_url: str, server_up: bool, total_time: float = 0) -> str:
    passed = sum(1 for r in results if r.success)
    total = len(results)
    failed = [r for r in results if not r.success]

    lines = [
        f"# PH eReferral Example Test Report",
        f"",
        f"- **Date:** {timestamp}",
        f"- **Server:** `{base_url}`",
        f"- **Server Reachable:** {'Yes' if server_up else 'No (dry-run)'}",
        f"- **Total:** {total}  **Passed:** {passed}  **Failed:** {total - passed}  **Pass Rate:** {passed/total*100:.0f}%",
        f"",
    ]

    if server_up:
        lines.append(f"| # | Resource | Method | URL | Status | Time (s) | Result |")
        lines.append(f"|---|----------|--------|-----|--------|----------|--------|")
        for i, r in enumerate(results, 1):
            mark = "✓" if r.success else "✗"
            lines.append(f"| {i} | {r.resource_type}/{r.name} | {r.method} | `{r.url}` | {r.status} | {r.response_time:.3f} | {mark} |")
    else:
        lines.append(f"| # | Resource | Status |")
        lines.append(f"|---|----------|--------|")
        for i, r in enumerate(results, 1):
            mark = "✓" if r.success else "✗"
            lines.append(f"| {i} | {r.resource_type}/{r.name} | {mark} |")

    lines.append("")
    lines.extend(generate_narrative(results, total_time))
    lines.append("---")
    lines.append(f"_Generated at {timestamp}_")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="PH eReferral example resource tests. Uses PHeRef/testdata/examples/.")
    parser.add_argument("--base-url", help="FHIR server base URL (overrides .env)")
    parser.add_argument("--examples-dir", default=DEFAULT_EXAMPLES_DIR, help=f"Example JSONs directory (default: {DEFAULT_EXAMPLES_DIR})")
    parser.add_argument("--report-dir", default=DEFAULT_REPORT_DIR, help=f"Report output directory (default: {DEFAULT_REPORT_DIR})")
    parser.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT, help=f"HTTP timeout in seconds (default: {DEFAULT_TIMEOUT})")
    args = parser.parse_args()

    base_url = resolve_base_url(args.base_url)
    examples_dir = args.examples_dir
    report_dir = args.report_dir
    timeout = args.timeout

    print(f"PH eReferral Example Tests (PHeRef IHE eReferral Bundle + Resources)")
    print(f"{'=' * 60}")

    example_files = sorted(glob.glob(os.path.join(examples_dir, "*.json")))
    if not example_files:
        print(f"No JSON files found in {examples_dir}")
        sys.exit(1)
    print(f"Examples found: {len(example_files)}")
    print(f"Server: {base_url}")

    server_up = server_reachable(base_url)
    print(f"Reachable: {server_up}")
    if not server_up:
        print("WARNING: Server not reachable — running in dry-run (validate-only) mode")
    print()

    results: list[TestResult] = []
    uuid_map: dict[str, str] = {}

    # Separate Bundle files from individual resource files
    bundle_files = sorted(f for f in example_files if os.path.basename(f).startswith("Bundle-"))
    resource_files = sorted(f for f in example_files if not os.path.basename(f).startswith("Bundle-"))

    # 1. POST Bundle(s) first — resolves urn:uuid references → real resource IDs
    if server_up:
        for fpath in bundle_files:
            fname = os.path.basename(fpath)
            print(f"[{fname}]")
            with open(fpath) as f:
                bundle_request = json.load(f)
            bundle_response = post_bundle(base_url, fpath, timeout, results)
            if bundle_response and bundle_response.get("resourceType") == "Bundle":
                try:
                    uuid_map = build_uuid_map_from_bundle_response(bundle_response, bundle_request)
                    if uuid_map:
                        print(f"  └─ Resolved {len(uuid_map)} urn:uuid → Resource/ID mappings")
                except Exception as e:
                    print(f"  └─ Warning: could not build UUID map ({e})")
            print()

    # 2. PUT individual resources — with resolved references
    for fpath in resource_files:
        fname = os.path.basename(fpath)
        print(f"[{fname}]")
        if not server_up:
            validate_json(fpath, results)
        else:
            with open(fpath) as f:
                resource = json.load(f)
            if uuid_map:
                replace_urn_uuid_refs(resource, uuid_map)
                import tempfile
                tmp = tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False)
                json.dump(resource, tmp)
                tmp.close()
                put_resource(base_url, tmp.name, timeout, results)
                os.unlink(tmp.name)
            else:
                put_resource(base_url, fpath, timeout, results)
        print()

    passed = sum(1 for r in results if r.success)
    total = len(results)
    print(f"{'=' * 60}")
    print(f"SUMMARY  —  Passed: {passed}/{total}")
    print(f"{'=' * 60}")
    for r in results:
        icon = "✓" if r.success else "✗"
        if r.method == "DRY":
            print(f"  {icon}  {r.resource_type}/{r.name}")
        else:
            print(f"  {icon}  {r.resource_type}/{r.name}  {r.method} {r.status} ({r.response_time:.3f}s)")

    total_wall_time = sum(r.response_time for r in results if r.response_time > 0)

    domain_label = extract_domain_label(base_url)
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H%M%SZ")
    os.makedirs(report_dir, exist_ok=True)
    report_path = os.path.join(report_dir, f"test-report-pheref-{domain_label}-{ts}.md")
    with open(report_path, "w") as f:
        f.write(generate_markdown(results, ts, base_url, server_up, total_wall_time))
    print(f"\nReport saved: {report_path}")


if __name__ == "__main__":
    main()
