#!/usr/bin/env bash
set -u

# eReferral FHIR testing report generator for HAPI FHIR R4
# Safer v2: prints progress and writes a report even if some tests fail.
# Usage:
#   bash generate_eref_testing_report_v2.sh [BASE_URL]
# Example:
#   bash generate_eref_testing_report_v2.sh http://localhost:8081/fhir
# Optional:
#   KEEP_CREATED=false bash generate_eref_testing_report_v2.sh http://localhost:8081/fhir
#   SERVICE_REQUEST_PROFILE_URL="https://fhir.doh.gov.ph/pheref/StructureDefinition/<profile>" bash generate_eref_testing_report_v2.sh

BASE_URL="${1:-http://localhost:8081/fhir}"
EREF_PATIENT_PROFILE_URL="${EREF_PATIENT_PROFILE_URL:-https://fhir.doh.gov.ph/pheref/StructureDefinition/ereferral-patient}"
EREF_PRIORITY_VS_URL="${EREF_PRIORITY_VS_URL:-https://fhir.doh.gov.ph/pheref/ValueSet/ereferral-priority}"
EREF_WORKFLOW_CS_URL="${EREF_WORKFLOW_CS_URL:-https://fhir.doh.gov.ph/pheref/CodeSystem/ereferral-workflow}"
SERVICE_REQUEST_PROFILE_URL="${SERVICE_REQUEST_PROFILE_URL:-}"
KEEP_CREATED="${KEEP_CREATED:-true}"
CONNECT_TIMEOUT="${CONNECT_TIMEOUT:-3}"
MAX_TIME="${MAX_TIME:-20}"

TIMESTAMP="$(date +%Y%m%d-%H%M%S)"
OUT_DIR="eref-testing-results-${TIMESTAMP}"
mkdir -p "$OUT_DIR/logs" "$OUT_DIR/payloads"

REPORT_MD="$OUT_DIR/eref-testing-results.md"
REPORT_HTML="$OUT_DIR/eref-testing-results.html"
SUMMARY_JSON="$OUT_DIR/summary.json"
SUMMARY_TSV="$OUT_DIR/test-summary.tsv"

PYTHON_BIN=""
if command -v python3 >/dev/null 2>&1; then
  PYTHON_BIN="python3"
elif command -v python >/dev/null 2>&1; then
  PYTHON_BIN="python"
else
  echo "ERROR: python3 or python is required."
  exit 1
fi

if ! command -v curl >/dev/null 2>&1; then
  echo "ERROR: curl is required."
  exit 1
fi

# Create placeholder files immediately so the result folder is never empty.
echo -e "#\tTest\tEndpoint\tHTTP\tExpected\tActual\tFinding\tLog" > "$SUMMARY_TSV"
echo '{"status":"started","message":"Script started but has not completed yet."}' > "$SUMMARY_JSON"
echo "# eReferral FHIR Server Testing Results" > "$REPORT_MD"
echo "Report is being generated. If you see only this line, the script was interrupted early." >> "$REPORT_MD"

urlencode() {
  "$PYTHON_BIN" - "$1" <<'PY'
import sys, urllib.parse
print(urllib.parse.quote(sys.argv[1], safe=''))
PY
}

json_get() {
  local file="$1"
  local expr="$2"
  "$PYTHON_BIN" - "$file" "$expr" <<'PY'
import sys, json
file, expr = sys.argv[1], sys.argv[2]
try:
    with open(file, encoding='utf-8') as f:
        data = json.load(f)
except Exception:
    print("")
    raise SystemExit(0)
cur = data
for part in expr.split('.'):
    if not part:
        continue
    if isinstance(cur, list):
        try:
            cur = cur[int(part)]
        except Exception:
            print("")
            raise SystemExit(0)
    elif isinstance(cur, dict):
        cur = cur.get(part, "")
    else:
        print("")
        raise SystemExit(0)
if isinstance(cur, (dict, list)):
    print(json.dumps(cur, ensure_ascii=False))
else:
    print(cur)
PY
}

issue_count() {
  local file="$1"
  local severity="$2"
  "$PYTHON_BIN" - "$file" "$severity" <<'PY'
import sys, json
file, severity = sys.argv[1], sys.argv[2]
try:
    with open(file, encoding='utf-8') as f:
        data = json.load(f)
    print(sum(1 for i in data.get('issue', []) if i.get('severity') == severity))
except Exception:
    print(0)
PY
}

brief_findings() {
  local file="$1"
  "$PYTHON_BIN" - "$file" <<'PY'
import sys, json
file = sys.argv[1]
try:
    with open(file, encoding='utf-8') as f:
        data = json.load(f)
except Exception:
    print('No JSON response. Check .err and .headers files.')
    raise SystemExit(0)
rt = data.get('resourceType')
if rt == 'OperationOutcome':
    issues = data.get('issue', [])
    if not issues:
        print('OperationOutcome returned with no issues.')
    for issue in issues[:8]:
        sev = issue.get('severity', '').upper()
        diag = issue.get('diagnostics') or issue.get('details', {}).get('text') or issue.get('code', '')
        print(f'{sev}: {diag}')
elif rt == 'Bundle':
    print(f"Bundle type={data.get('type','')}, total={data.get('total', 0)}")
    for entry in data.get('entry', [])[:5]:
        res = entry.get('resource', {})
        if res:
            print(f"- {res.get('resourceType','Resource')}/{res.get('id','')}")
elif rt:
    rid = data.get('id', '')
    print(rt + (f'/{rid}' if rid else ''))
else:
    print('JSON response received, but resourceType is missing.')
PY
}

http_call() {
  local name="$1"
  local method="$2"
  local url="$3"
  local body_file="${4:-}"
  local out_file="$OUT_DIR/logs/${name}.json"
  local status_file="$OUT_DIR/logs/${name}.status"
  local header_file="$OUT_DIR/logs/${name}.headers"
  local err_file="$OUT_DIR/logs/${name}.err"
  local status="000"

  if [ -n "$body_file" ]; then
    status=$(curl -sS --connect-timeout "$CONNECT_TIMEOUT" --max-time "$MAX_TIME" \
      -D "$header_file" -o "$out_file" -w "%{http_code}" \
      -X "$method" "$url" \
      -H "Content-Type: application/fhir+json" \
      -H "Accept: application/fhir+json" \
      --data-binary "@$body_file" 2> "$err_file" || true)
  else
    status=$(curl -sS --connect-timeout "$CONNECT_TIMEOUT" --max-time "$MAX_TIME" \
      -D "$header_file" -o "$out_file" -w "%{http_code}" \
      -X "$method" "$url" \
      -H "Accept: application/fhir+json" 2> "$err_file" || true)
  fi

  [ -z "$status" ] && status="000"
  echo "$status" > "$status_file"

  if [ ! -s "$out_file" ]; then
    local err_text=""
    if [ -s "$err_file" ]; then
      err_text=$(tr '\n' ' ' < "$err_file" | sed 's/"/\\"/g')
    else
      err_text="No response body returned."
    fi
    cat > "$out_file" <<EOFJSON
{"resourceType":"OperationOutcome","issue":[{"severity":"error","code":"processing","diagnostics":"$err_text"}]}
EOFJSON
  fi

  echo "$status"
}

extract_created_id() {
  local resource_type="$1"
  local body_file="$2"
  local header_file="$3"
  local rid=""
  rid="$(json_get "$body_file" "id")"
  if [ -n "$rid" ]; then
    echo "$rid"
    return
  fi
  "$PYTHON_BIN" - "$resource_type" "$header_file" <<'PY'
import sys, re
resource_type, header_file = sys.argv[1], sys.argv[2]
try:
    text = open(header_file, encoding='utf-8', errors='ignore').read()
except Exception:
    print('')
    raise SystemExit(0)
pattern = r'(?:Location|Content-Location):\s*[^\r\n]*/' + re.escape(resource_type) + r'/([^/\s]+)'
m = re.search(pattern, text, re.I)
print(m.group(1) if m else '')
PY
}

add_row() {
  local num="$1"
  local test_name="$2"
  local endpoint="$3"
  local http="$4"
  local expected="$5"
  local actual="$6"
  local finding="$7"
  local log="$8"
  printf "%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\n" "$num" "$test_name" "$endpoint" "$http" "$expected" "$actual" "$finding" "$log" >> "$SUMMARY_TSV"
  echo "[$num] $test_name -> HTTP $http | $finding"
}

cleanup_created() {
  local resource_type="$1"
  local rid="$2"
  local name="$3"
  if [ "$KEEP_CREATED" = "true" ]; then
    return
  fi
  if [ -n "$rid" ]; then
    curl -sS --connect-timeout "$CONNECT_TIMEOUT" --max-time "$MAX_TIME" \
      -X DELETE "$BASE_URL/$resource_type/$rid" \
      -H "Accept: application/fhir+json" \
      > "$OUT_DIR/logs/${name}-delete.json" 2> "$OUT_DIR/logs/${name}-delete.err" || true
  fi
}

make_report() {
  local finished_status="${1:-completed}"
  local critical_title="${CRITICAL_TITLE:-Testing incomplete}"
  local critical_text="${CRITICAL_TEXT:-Review the log files. The script may have been interrupted before all tests completed.}"

  "$PYTHON_BIN" - "$SUMMARY_TSV" "$SUMMARY_JSON" "$BASE_URL" "$EREF_PATIENT_PROFILE_URL" "$EREF_PRIORITY_VS_URL" "$EREF_WORKFLOW_CS_URL" "$SERVICE_REQUEST_PROFILE_URL" "$KEEP_CREATED" "$finished_status" "$critical_title" <<'PY'
import sys, csv, json
(tsv, out, base, patient_profile, priority_vs, workflow_cs, sr_profile, keep_created, status, critical_title) = sys.argv[1:11]
rows = []
try:
    with open(tsv, encoding='utf-8') as f:
        reader = csv.DictReader(f, delimiter='\t')
        rows = list(reader)
except Exception:
    rows = []
summary = {
    'status': status,
    'baseUrl': base,
    'erefPatientProfileUrl': patient_profile,
    'erefPriorityValueSetUrl': priority_vs,
    'erefWorkflowCodeSystemUrl': workflow_cs,
    'serviceRequestProfileUrl': sr_profile,
    'keepCreated': keep_created,
    'criticalTitle': critical_title,
    'testsRun': len(rows),
    'tests': rows,
}
with open(out, 'w', encoding='utf-8') as f:
    json.dump(summary, f, indent=2)
PY

  {
    echo "# eReferral FHIR Server Testing Results — $BASE_URL"
    echo ""
    echo "Generated: $(date -Iseconds)"
    echo ""
    echo "## Critical Finding"
    echo ""
    echo "**$critical_title**"
    echo ""
    echo "$critical_text"
    echo ""
    echo "## Configuration"
    echo ""
    echo "| Item | Value |"
    echo "|---|---|"
    echo "| Base URL | $BASE_URL |"
    echo "| eReferral Patient Profile | $EREF_PATIENT_PROFILE_URL |"
    echo "| Priority ValueSet | $EREF_PRIORITY_VS_URL |"
    echo "| Workflow CodeSystem | $EREF_WORKFLOW_CS_URL |"
    echo "| ServiceRequest Profile | ${SERVICE_REQUEST_PROFILE_URL:-Not set. Plain FHIR ServiceRequest used.} |"
    echo "| Keep Created Resources | $KEEP_CREATED |"
    echo ""
    echo "## Test Summary"
    echo ""
    echo "| # | Test | Endpoint | HTTP | Expected | Actual | Finding | Log |"
    echo "|---|---|---|---|---|---|---|---|"
    tail -n +2 "$SUMMARY_TSV" | while IFS=$'\t' read -r num test_name endpoint http expected actual finding log; do
      test_name=${test_name//|//}
      endpoint=${endpoint//|//}
      expected=${expected//|//}
      actual=${actual//|//}
      finding=${finding//|//}
      echo "| $num | $test_name | \`$endpoint\` | $http | $expected | $actual | $finding | \`$log\` |"
    done
    echo ""
    echo "## Important Raw Logs"
    echo ""
    for f in "$OUT_DIR"/logs/*.json; do
      [ -f "$f" ] || continue
      b="$(basename "$f")"
      echo "### $b"
      echo ""
      echo '```text'
      brief_findings "$f"
      echo '```'
      echo ""
    done
    echo "## Files"
    echo ""
    echo "- Summary JSON: \`$SUMMARY_JSON\`"
    echo "- Markdown report: \`$REPORT_MD\`"
    echo "- HTML report: \`$REPORT_HTML\`"
    echo "- Payloads: \`$OUT_DIR/payloads/\`"
    echo "- Logs: \`$OUT_DIR/logs/\`"
  } > "$REPORT_MD"

  "$PYTHON_BIN" - "$REPORT_MD" "$REPORT_HTML" <<'PY'
import sys, html, re
md_path, html_path = sys.argv[1], sys.argv[2]
text = open(md_path, encoding='utf-8').read()

def inline(s):
    s = html.escape(s)
    s = re.sub(r'`([^`]+)`', r'<code>\1</code>', s)
    s = re.sub(r'\*\*([^*]+)\*\*', r'<strong>\1</strong>', s)
    return s

out=[]; in_code=False; code=[]; in_table=False

def close_table():
    global in_table
    if in_table:
        out.append('</tbody></table>')
        in_table=False

for line in text.splitlines():
    if line.startswith('```'):
        if not in_code:
            close_table(); in_code=True; code=[]
        else:
            out.append('<pre><code>%s</code></pre>' % html.escape('\n'.join(code)))
            in_code=False
        continue
    if in_code:
        code.append(line); continue
    if not line.strip():
        close_table(); continue
    if line.startswith('# '):
        close_table(); out.append('<h1>%s</h1>' % inline(line[2:])); continue
    if line.startswith('## '):
        close_table(); out.append('<h2>%s</h2>' % inline(line[3:])); continue
    if line.startswith('### '):
        close_table(); out.append('<h3>%s</h3>' % inline(line[4:])); continue
    if line.startswith('|') and line.endswith('|'):
        cells=[c.strip() for c in line.strip('|').split('|')]
        if all(set(c) <= set('-: ') for c in cells):
            continue
        if not in_table:
            out.append('<table><tbody>'); in_table=True; tag='th'
        else:
            tag='td'
        if any(c in ('#','Item','Value','Test','Endpoint','HTTP','Expected','Actual','Finding','Log') for c in cells): tag='th'
        out.append('<tr>' + ''.join('<%s>%s</%s>' % (tag, inline(c), tag) for c in cells) + '</tr>')
        continue
    if line.startswith('- '):
        close_table(); out.append('<p>• %s</p>' % inline(line[2:])); continue
    close_table(); out.append('<p>%s</p>' % inline(line))
close_table()
css='''body{font-family:Arial,Helvetica,sans-serif;max-width:1100px;margin:30px auto;line-height:1.45;color:#111}table{border-collapse:collapse;width:100%;margin:16px 0}th,td{border:1px solid #ddd;padding:8px 10px;text-align:left;vertical-align:top}th{background:#f7f7f7}code{background:#f4f4f4;padding:2px 5px;border-radius:4px}pre{background:#f8f8f8;padding:16px;overflow-x:auto;border:1px solid #eee;border-radius:4px}h1{font-size:30px}h2{margin-top:30px}'''
open(html_path,'w',encoding='utf-8').write('<!doctype html><html><head><meta charset="utf-8"><title>eReferral FHIR Testing Results</title><style>'+css+'</style></head><body>'+'\n'.join(out)+'</body></html>')
PY
}

finish_on_exit() {
  local rc=$?
  trap - EXIT
  if [ "$rc" -eq 0 ]; then
    make_report "completed"
  else
    CRITICAL_TITLE="Script interrupted or failed"
    CRITICAL_TEXT="The script exited early with status $rc. Partial results are still included below. Check logs/*.err and logs/*.json."
    make_report "partial"
  fi
  echo ""
  echo "=============================================="
  echo "eReferral FHIR testing report generated"
  echo "Folder: $OUT_DIR"
  echo "Summary: $SUMMARY_JSON"
  echo "Markdown: $REPORT_MD"
  echo "HTML: $REPORT_HTML"
  echo "=============================================="
  exit "$rc"
}
trap finish_on_exit EXIT

# -----------------------------
# Payloads
# -----------------------------
cat > "$OUT_DIR/payloads/eref-patient-valid.json" <<EOFJSON
{
  "resourceType": "Patient",
  "meta": {
    "profile": ["$EREF_PATIENT_PROFILE_URL"]
  },
  "text": {
    "status": "generated",
    "div": "<div xmlns=\"http://www.w3.org/1999/xhtml\">Juan Dela Cruz eReferral test patient</div>"
  },
  "identifier": [
    {"system": "https://philhealth.gov.ph", "value": "PH-EREF-TEST-$TIMESTAMP"},
    {"system": "https://psa.gov.ph/philsys", "value": "PSN-EREF-TEST-$TIMESTAMP"}
  ],
  "name": [{"family": "Dela Cruz", "given": ["Juan"]}],
  "gender": "male",
  "birthDate": "1990-01-01",
  "telecom": [{"system": "phone", "value": "+639171234567", "use": "mobile"}],
  "address": [{"line": ["Barangay Malinis"], "city": "Quezon City", "state": "NCR", "country": "PH"}]
}
EOFJSON

cat > "$OUT_DIR/payloads/eref-patient-invalid.json" <<EOFJSON
{
  "resourceType": "Patient",
  "meta": {
    "profile": ["$EREF_PATIENT_PROFILE_URL"]
  }
}
EOFJSON

cat > "$OUT_DIR/payloads/eref-patient-no-profile.json" <<EOFJSON
{
  "resourceType": "Patient",
  "identifier": [{"system": "https://philhealth.gov.ph", "value": "PH-EREF-NO-PROFILE-$TIMESTAMP"}],
  "name": [{"family": "NoProfile", "given": ["ShouldFailIfInterceptorWorks"]}],
  "gender": "male",
  "birthDate": "1990-01-01"
}
EOFJSON

cat > "$OUT_DIR/payloads/referring-organization.json" <<EOFJSON
{
  "resourceType": "Organization",
  "identifier": [{"system": "https://doh.gov.ph/fhir/healthcare-facility-code", "value": "REF-FACILITY-$TIMESTAMP"}],
  "name": "Barangay Health Center Test"
}
EOFJSON

cat > "$OUT_DIR/payloads/receiving-organization.json" <<EOFJSON
{
  "resourceType": "Organization",
  "identifier": [{"system": "https://doh.gov.ph/fhir/healthcare-facility-code", "value": "REC-FACILITY-$TIMESTAMP"}],
  "name": "Referral Hospital Test"
}
EOFJSON

cat > "$OUT_DIR/payloads/practitioner.json" <<EOFJSON
{
  "resourceType": "Practitioner",
  "identifier": [{"system": "https://prc.gov.ph/license-number", "value": "PRC-TEST-$TIMESTAMP"}],
  "name": [{"family": "Reyes", "given": ["Maria"]}]
}
EOFJSON

echo "Starting eReferral FHIR tests..."
echo "Base URL: $BASE_URL"
echo "Output folder: $OUT_DIR"
echo ""

PATIENT_PROFILE_ENCODED="$(urlencode "$EREF_PATIENT_PROFILE_URL")"
PRIORITY_VS_ENCODED="$(urlencode "$EREF_PRIORITY_VS_URL")"
WORKFLOW_CS_ENCODED="$(urlencode "$EREF_WORKFLOW_CS_URL")"

# 1 metadata
META_STATUS="$(http_call "01-metadata" "GET" "$BASE_URL/metadata?_pretty=true")"
SERVER_NAME="$(json_get "$OUT_DIR/logs/01-metadata.json" "software.name")"
SERVER_VERSION="$(json_get "$OUT_DIR/logs/01-metadata.json" "software.version")"
FHIR_VERSION="$(json_get "$OUT_DIR/logs/01-metadata.json" "fhirVersion")"
if [ "$META_STATUS" = "200" ]; then META_FINDING="✅ Server reachable"; else META_FINDING="❌ Server not reachable"; fi
add_row "1" "Metadata" "GET /metadata" "$META_STATUS" "CapabilityStatement" "${SERVER_NAME:-Unknown} ${FHIR_VERSION:-Unknown}" "$META_FINDING" "logs/01-metadata.json"

# 2 IG list
IG_STATUS="$(http_call "02-implementationguide-list" "GET" "$BASE_URL/ImplementationGuide?_pretty=true")"
IG_TOTAL="$(json_get "$OUT_DIR/logs/02-implementationguide-list.json" "total")"; [ -z "$IG_TOTAL" ] && IG_TOTAL=0
if [ "$IG_TOTAL" != "0" ]; then IG_FINDING="✅ IG listed"; else IG_FINDING="⚠️ No IG resources listed"; fi
add_row "2" "ImplementationGuide list" "GET /ImplementationGuide" "$IG_STATUS" "IG resources visible" "total=$IG_TOTAL" "$IG_FINDING" "logs/02-implementationguide-list.json"

# 3 Patient profile
PROFILE_STATUS="$(http_call "03-eref-patient-profile-search" "GET" "$BASE_URL/StructureDefinition?url=$PATIENT_PROFILE_ENCODED&_pretty=true")"
PROFILE_TOTAL="$(json_get "$OUT_DIR/logs/03-eref-patient-profile-search.json" "total")"; [ -z "$PROFILE_TOTAL" ] && PROFILE_TOTAL=0
if [ "$PROFILE_TOTAL" != "0" ]; then PROFILE_FINDING="✅ Profile found"; else PROFILE_FINDING="❌ Profile not found"; fi
add_row "3" "eReferral Patient profile" "GET /StructureDefinition?url=..." "$PROFILE_STATUS" "Profile found" "total=$PROFILE_TOTAL" "$PROFILE_FINDING" "logs/03-eref-patient-profile-search.json"

# 4 priority ValueSet
PRIORITY_STATUS="$(http_call "04-eref-priority-valueset-search" "GET" "$BASE_URL/ValueSet?url=$PRIORITY_VS_ENCODED&_pretty=true")"
PRIORITY_TOTAL="$(json_get "$OUT_DIR/logs/04-eref-priority-valueset-search.json" "total")"; [ -z "$PRIORITY_TOTAL" ] && PRIORITY_TOTAL=0
if [ "$PRIORITY_TOTAL" != "0" ]; then PRIORITY_FINDING="✅ ValueSet found"; else PRIORITY_FINDING="⚠️ ValueSet not found"; fi
add_row "4" "eReferral priority ValueSet" "GET /ValueSet?url=..." "$PRIORITY_STATUS" "ValueSet found" "total=$PRIORITY_TOTAL" "$PRIORITY_FINDING" "logs/04-eref-priority-valueset-search.json"

# 5 workflow CodeSystem
WORKFLOW_STATUS="$(http_call "05-eref-workflow-codesystem-search" "GET" "$BASE_URL/CodeSystem?url=$WORKFLOW_CS_ENCODED&_pretty=true")"
WORKFLOW_TOTAL="$(json_get "$OUT_DIR/logs/05-eref-workflow-codesystem-search.json" "total")"; [ -z "$WORKFLOW_TOTAL" ] && WORKFLOW_TOTAL=0
if [ "$WORKFLOW_TOTAL" != "0" ]; then WORKFLOW_FINDING="✅ CodeSystem found"; else WORKFLOW_FINDING="⚠️ CodeSystem not found"; fi
add_row "5" "eReferral workflow CodeSystem" "GET /CodeSystem?url=..." "$WORKFLOW_STATUS" "CodeSystem found" "total=$WORKFLOW_TOTAL" "$WORKFLOW_FINDING" "logs/05-eref-workflow-codesystem-search.json"

# 6 validate valid patient
VALID_STATUS="$(http_call "06-validate-eref-patient-valid" "POST" "$BASE_URL/Patient/\$validate?_pretty=true" "$OUT_DIR/payloads/eref-patient-valid.json")"
VALID_ERRORS="$(issue_count "$OUT_DIR/logs/06-validate-eref-patient-valid.json" "error")"
VALID_WARNINGS="$(issue_count "$OUT_DIR/logs/06-validate-eref-patient-valid.json" "warning")"
if [ "$VALID_ERRORS" = "0" ]; then VALID_FINDING="✅ No validation errors"; else VALID_FINDING="❌ Review OperationOutcome"; fi
add_row "6" "Validate valid eReferral Patient" "POST /Patient/\$validate" "$VALID_STATUS" "0 errors" "errors=$VALID_ERRORS warnings=$VALID_WARNINGS" "$VALID_FINDING" "logs/06-validate-eref-patient-valid.json"

# 7 validate invalid patient
INVALID_STATUS="$(http_call "07-validate-eref-patient-invalid" "POST" "$BASE_URL/Patient/\$validate?_pretty=true" "$OUT_DIR/payloads/eref-patient-invalid.json")"
INVALID_ERRORS="$(issue_count "$OUT_DIR/logs/07-validate-eref-patient-invalid.json" "error")"
INVALID_WARNINGS="$(issue_count "$OUT_DIR/logs/07-validate-eref-patient-invalid.json" "warning")"
if [ "$INVALID_ERRORS" != "0" ]; then INVALID_FINDING="✅ Invalid patient detected"; else INVALID_FINDING="⚠️ No errors returned"; fi
add_row "7" "Validate invalid eReferral Patient" "POST /Patient/\$validate" "$INVALID_STATUS" "Should return errors" "errors=$INVALID_ERRORS warnings=$INVALID_WARNINGS" "$INVALID_FINDING" "logs/07-validate-eref-patient-invalid.json"

# 8 create no-profile patient
NO_PROFILE_STATUS="$(http_call "08-create-patient-no-profile" "POST" "$BASE_URL/Patient?_pretty=true" "$OUT_DIR/payloads/eref-patient-no-profile.json")"
NO_PROFILE_ID="$(extract_created_id "Patient" "$OUT_DIR/logs/08-create-patient-no-profile.json" "$OUT_DIR/logs/08-create-patient-no-profile.headers")"
if [[ "$NO_PROFILE_STATUS" =~ ^2 ]]; then NO_PROFILE_FINDING="⚠️ Accepted without profile"; else NO_PROFILE_FINDING="✅ Blocked without profile"; fi
add_row "8" "Create Patient without profile" "POST /Patient" "$NO_PROFILE_STATUS" "Blocked if interceptor requires profile" "Patient/${NO_PROFILE_ID:-not-created}" "$NO_PROFILE_FINDING" "logs/08-create-patient-no-profile.json"
cleanup_created "Patient" "$NO_PROFILE_ID" "08-create-patient-no-profile"

# 9 create valid patient
CREATE_PATIENT_STATUS="$(http_call "09-create-eref-patient" "POST" "$BASE_URL/Patient?_pretty=true" "$OUT_DIR/payloads/eref-patient-valid.json")"
PATIENT_ID="$(extract_created_id "Patient" "$OUT_DIR/logs/09-create-eref-patient.json" "$OUT_DIR/logs/09-create-eref-patient.headers")"
if [[ "$CREATE_PATIENT_STATUS" =~ ^2 ]]; then CREATE_PATIENT_FINDING="✅ Created"; else CREATE_PATIENT_FINDING="❌ Failed"; fi
add_row "9" "Create eReferral Patient" "POST /Patient" "$CREATE_PATIENT_STATUS" "Created" "Patient/${PATIENT_ID:-not-created}" "$CREATE_PATIENT_FINDING" "logs/09-create-eref-patient.json"

# 10 referring org
REF_ORG_STATUS="$(http_call "10-create-referring-organization" "POST" "$BASE_URL/Organization?_pretty=true" "$OUT_DIR/payloads/referring-organization.json")"
REF_ORG_ID="$(extract_created_id "Organization" "$OUT_DIR/logs/10-create-referring-organization.json" "$OUT_DIR/logs/10-create-referring-organization.headers")"
if [[ "$REF_ORG_STATUS" =~ ^2 ]]; then REF_ORG_FINDING="✅ Created"; else REF_ORG_FINDING="❌ Failed"; fi
add_row "10" "Create referring Organization" "POST /Organization" "$REF_ORG_STATUS" "Created" "Organization/${REF_ORG_ID:-not-created}" "$REF_ORG_FINDING" "logs/10-create-referring-organization.json"

# 11 receiving org
REC_ORG_STATUS="$(http_call "11-create-receiving-organization" "POST" "$BASE_URL/Organization?_pretty=true" "$OUT_DIR/payloads/receiving-organization.json")"
REC_ORG_ID="$(extract_created_id "Organization" "$OUT_DIR/logs/11-create-receiving-organization.json" "$OUT_DIR/logs/11-create-receiving-organization.headers")"
if [[ "$REC_ORG_STATUS" =~ ^2 ]]; then REC_ORG_FINDING="✅ Created"; else REC_ORG_FINDING="❌ Failed"; fi
add_row "11" "Create receiving Organization" "POST /Organization" "$REC_ORG_STATUS" "Created" "Organization/${REC_ORG_ID:-not-created}" "$REC_ORG_FINDING" "logs/11-create-receiving-organization.json"

# 12 practitioner
PRACT_STATUS="$(http_call "12-create-practitioner" "POST" "$BASE_URL/Practitioner?_pretty=true" "$OUT_DIR/payloads/practitioner.json")"
PRACT_ID="$(extract_created_id "Practitioner" "$OUT_DIR/logs/12-create-practitioner.json" "$OUT_DIR/logs/12-create-practitioner.headers")"
if [[ "$PRACT_STATUS" =~ ^2 ]]; then PRACT_FINDING="✅ Created"; else PRACT_FINDING="❌ Failed"; fi
add_row "12" "Create Practitioner" "POST /Practitioner" "$PRACT_STATUS" "Created" "Practitioner/${PRACT_ID:-not-created}" "$PRACT_FINDING" "logs/12-create-practitioner.json"

# Build ServiceRequest payload
"$PYTHON_BIN" - "$OUT_DIR/payloads/eref-servicerequest.json" "$SERVICE_REQUEST_PROFILE_URL" "$PATIENT_ID" "$PRACT_ID" "$REC_ORG_ID" <<'PY'
import sys, json, datetime
out, profile, patient_id, practitioner_id, receiving_org_id = sys.argv[1:6]
resource = {
  'resourceType': 'ServiceRequest',
  'status': 'active',
  'intent': 'order',
  'category': [{'coding': [{'system': 'http://terminology.hl7.org/CodeSystem/servicerequest-category', 'code': 'referral', 'display': 'Referral'}]}],
  'priority': 'urgent',
  'code': {'text': 'Referral for emergency consultation'},
  'subject': {'reference': f'Patient/{patient_id}' if patient_id else 'Patient/UNKNOWN'},
  'requester': {'reference': f'Practitioner/{practitioner_id}' if practitioner_id else 'Practitioner/UNKNOWN'},
  'performer': [{'reference': f'Organization/{receiving_org_id}' if receiving_org_id else 'Organization/UNKNOWN'}],
  'authoredOn': datetime.date.today().isoformat(),
  'reasonCode': [{'text': 'Persistent chest pain and shortness of breath'}],
  'note': [{'text': 'eReferral test created by generate_eref_testing_report_v2.sh.'}]
}
if profile:
    resource['meta'] = {'profile': [profile]}
with open(out, 'w', encoding='utf-8') as f:
    json.dump(resource, f, indent=2)
PY

# 13 ServiceRequest
if [ -n "$PATIENT_ID" ] && [ -n "$PRACT_ID" ] && [ -n "$REC_ORG_ID" ]; then
  SR_STATUS="$(http_call "13-create-servicerequest-referral" "POST" "$BASE_URL/ServiceRequest?_pretty=true" "$OUT_DIR/payloads/eref-servicerequest.json")"
  SR_ID="$(extract_created_id "ServiceRequest" "$OUT_DIR/logs/13-create-servicerequest-referral.json" "$OUT_DIR/logs/13-create-servicerequest-referral.headers")"
else
  SR_STATUS="SKIPPED"
  SR_ID=""
  cat > "$OUT_DIR/logs/13-create-servicerequest-referral.json" <<EOFJSON
{"resourceType":"OperationOutcome","issue":[{"severity":"error","code":"processing","diagnostics":"Skipped because Patient, Practitioner, or receiving Organization was not created."}]}
EOFJSON
fi
if [[ "$SR_STATUS" =~ ^2 ]]; then SR_FINDING="✅ Created"; else SR_FINDING="❌ Failed or skipped"; fi
add_row "13" "Create referral ServiceRequest" "POST /ServiceRequest" "$SR_STATUS" "Created" "ServiceRequest/${SR_ID:-not-created}" "$SR_FINDING" "logs/13-create-servicerequest-referral.json"

# 14 Search patient by identifier
PATIENT_IDENTIFIER_ENCODED="$(urlencode "PH-EREF-TEST-$TIMESTAMP")"
SEARCH_PATIENT_STATUS="$(http_call "14-search-patient-by-identifier" "GET" "$BASE_URL/Patient?identifier=$PATIENT_IDENTIFIER_ENCODED&_pretty=true")"
SEARCH_PATIENT_TOTAL="$(json_get "$OUT_DIR/logs/14-search-patient-by-identifier.json" "total")"; [ -z "$SEARCH_PATIENT_TOTAL" ] && SEARCH_PATIENT_TOTAL=0
if [ "$SEARCH_PATIENT_TOTAL" != "0" ]; then SEARCH_PATIENT_FINDING="✅ Patient searchable"; else SEARCH_PATIENT_FINDING="⚠️ Patient not found"; fi
add_row "14" "Search Patient by identifier" "GET /Patient?identifier=..." "$SEARCH_PATIENT_STATUS" "total >= 1" "total=$SEARCH_PATIENT_TOTAL" "$SEARCH_PATIENT_FINDING" "logs/14-search-patient-by-identifier.json"

# 15 Search ServiceRequest by subject
if [ -n "$PATIENT_ID" ]; then
  SUBJECT_ENCODED="$(urlencode "Patient/$PATIENT_ID")"
  SEARCH_SR_STATUS="$(http_call "15-search-servicerequest-by-subject" "GET" "$BASE_URL/ServiceRequest?subject=$SUBJECT_ENCODED&_pretty=true")"
  SEARCH_SR_TOTAL="$(json_get "$OUT_DIR/logs/15-search-servicerequest-by-subject.json" "total")"; [ -z "$SEARCH_SR_TOTAL" ] && SEARCH_SR_TOTAL=0
else
  SEARCH_SR_STATUS="SKIPPED"
  SEARCH_SR_TOTAL=0
  cat > "$OUT_DIR/logs/15-search-servicerequest-by-subject.json" <<EOFJSON
{"resourceType":"OperationOutcome","issue":[{"severity":"error","code":"processing","diagnostics":"Skipped because Patient was not created."}]}
EOFJSON
fi
if [ "$SEARCH_SR_TOTAL" != "0" ]; then SEARCH_SR_FINDING="✅ Referral searchable"; else SEARCH_SR_FINDING="⚠️ Referral not found"; fi
add_row "15" "Search ServiceRequest by Patient" "GET /ServiceRequest?subject=Patient/..." "$SEARCH_SR_STATUS" "total >= 1" "total=$SEARCH_SR_TOTAL" "$SEARCH_SR_FINDING" "logs/15-search-servicerequest-by-subject.json"

# Cleanup only when requested.
cleanup_created "ServiceRequest" "$SR_ID" "13-create-servicerequest-referral"
cleanup_created "Practitioner" "$PRACT_ID" "12-create-practitioner"
cleanup_created "Organization" "$REC_ORG_ID" "11-create-receiving-organization"
cleanup_created "Organization" "$REF_ORG_ID" "10-create-referring-organization"
cleanup_created "Patient" "$PATIENT_ID" "09-create-eref-patient"

# Critical finding logic.
if [ "$META_STATUS" != "200" ]; then
  CRITICAL_TITLE="eReferral server is not reachable"
  CRITICAL_TEXT="Check that your eReferral HAPI container is running and mapped to the correct host port, usually http://localhost:8081/fhir."
elif [ "$PROFILE_TOTAL" = "0" ]; then
  CRITICAL_TITLE="eReferral Patient profile is not loaded"
  CRITICAL_TEXT="The server is alive, but it did not find the configured eReferral Patient StructureDefinition. Fix the eReferral IG package loading before relying on validation."
elif [ "$VALID_ERRORS" != "0" ]; then
  CRITICAL_TITLE="eReferral profile found, but valid Patient has validation errors"
  CRITICAL_TEXT="Review logs/06-validate-eref-patient-valid.json. The profile may require fields not included in the simple test payload, or terminology support may be incomplete."
elif ! [[ "$SR_STATUS" =~ ^2 ]]; then
  CRITICAL_TITLE="Patient/actor creation ran, but ServiceRequest failed"
  CRITICAL_TEXT="Review logs/13-create-servicerequest-referral.json. This is usually caused by an interceptor rule, an invalid reference, or a profile requirement on ServiceRequest."
else
  CRITICAL_TITLE="Basic eReferral flow appears working"
  CRITICAL_TEXT="The server was reachable, the eReferral Patient profile was checked, and the script created Patient, Organization, Practitioner, and ServiceRequest test resources."
fi

# Normal exit triggers final report generation.
exit 0
