#!/usr/bin/env bash
set -euo pipefail

REPORTS_DIR="$(cd "$(dirname "$0")/.." && pwd)/reports"

echo "=============================================="
echo "  PH eReferral + PH Core — Full Test Suite"
echo "=============================================="
echo ""

# ── Prompt: clear reports (except comparison.md) ──
if [[ -t 0 ]]; then
    echo -n "Clear reports folder (excluding comparison.md)? [y/N] (default N in 5s): "
    read -t 5 -r CLEAR_CHOICE || CLEAR_CHOICE="n"
    echo ""
else
    read -r CLEAR_CHOICE
fi
if [[ "${CLEAR_CHOICE,,}" == "y" ]]; then
    echo "Clearing reports..."
    find "$REPORTS_DIR" -maxdepth 1 -type f -name '*.md' ! -name 'comparison.md' -delete
    echo "Done (kept comparison.md)"
    echo ""
fi

# ── Track overall timing ──
OVERALL_START=$(date +%s)
ALL_OK=true

run_test() {
    local label="$1" script="$2" base_url="$3"
    echo "──────────────────────────────────────────────"
    echo "  [$label]"
    echo "  Script: $script"
    echo "  Server: $base_url"
    echo "──────────────────────────────────────────────"
    if python3 "$script" --base-url "$base_url"; then
        echo ""
        return 0
    else
        echo ""
        ALL_OK=false
        return 1
    fi
}

# ── PHeRef tests ──
echo "==========  PH eREFERRAL TESTS  =========="
echo ""

run_test "PHeRef / localhost"             "tests/test_phereferral.py" "http://localhost:8080/fhir"
run_test "PHeRef / cdr.pheref.fhirlab.net" "tests/test_phereferral.py" "https://cdr.pheref.fhirlab.net/fhir"
run_test "PHeRef / fhirportal.telehealth.ph/PHeRef" "tests/test_phereferral.py" "https://fhirportal.telehealth.ph/PHeRef/fhir"

# ── PH Core tests ──
echo "==========  PH CORE TESTS  =========="
echo ""

run_test "PH Core / localhost"             "tests/test_phcore.py" "http://localhost:8080/fhir"
run_test "PH Core / cdr.phcore.fhirlab.net" "tests/test_phcore.py" "https://cdr.phcore.fhirlab.net/fhir"
run_test "PH Core / fhirportal.telehealth.ph/phcore" "tests/test_phcore.py" "https://fhirportal.telehealth.ph/phcore/fhir"

# ── Summary ──
OVERALL_END=$(date +%s)
DURATION=$((OVERALL_END - OVERALL_START))
MIN=$((DURATION / 60))
SEC=$((DURATION % 60))

echo ""
echo "=============================================="
echo "  ALL TESTS COMPLETE"
echo "  Duration: ${MIN}m ${SEC}s"
echo "  Reports: $REPORTS_DIR/"
echo "=============================================="

if [ "$ALL_OK" = false ]; then
    echo ""
    echo "  Some tests reported failures (see above)."
    echo "  Run the individual scripts for details."
fi

echo ""
echo "  To generate a comparison report:"
echo "    Use an AI agent to read all test-report-*.md"
echo "    files and write reports/comparison.md"
echo ""
