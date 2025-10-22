#!/bin/bash
# Script to run all 8 multiworker test scenarios
# Each test takes ~5-6 minutes, total runtime ~40-48 minutes

set -e  # Exit on error

echo "=========================================="
echo "Multi-Worker Cache Architecture Test Suite"
echo "=========================================="
echo "Total tests: 8"
echo "Estimated time: 40-48 minutes"
echo "=========================================="
echo ""

# Create backup of old results if they exist
if ls multiworker_results/*.json 1> /dev/null 2>&1; then
    echo "Backing up old results..."
    mkdir -p multiworker_results/old_results_high_overlap
    mv multiworker_results/*.json multiworker_results/old_results_high_overlap/
    echo "✓ Old results moved to multiworker_results/old_results_high_overlap/"
    echo ""
fi

# Test counter
TEST_NUM=1
TOTAL_TESTS=8

# Function to run a test
run_test() {
    local workers=$1
    local cache_mode=$2
    local assignment=$3

    echo "=========================================="
    echo "TEST $TEST_NUM/$TOTAL_TESTS: $cache_mode + $assignment"
    echo "=========================================="
    echo "Started at: $(date '+%H:%M:%S')"
    echo ""

    python multiworker_test.py "$workers" "$cache_mode" "$assignment"

    echo ""
    echo "✓ Test $TEST_NUM complete at $(date '+%H:%M:%S')"
    echo ""

    TEST_NUM=$((TEST_NUM + 1))
}

# Run all 8 scenarios
echo "STARTING TEST SUITE AT: $(date '+%H:%M:%S')"
echo ""

# Sticky Assignment Tests (4 tests)
run_test 4 "2-tier" "sticky"
run_test 4 "3-tier-redundant" "sticky"
run_test 4 "3-tier-sticky" "sticky"
run_test 4 "3-tier-shared" "sticky"

# Sharded Assignment Tests (4 tests)
run_test 4 "2-tier" "sharded"
run_test 4 "3-tier-redundant" "sharded"
run_test 4 "3-tier-sticky" "sharded"
run_test 4 "3-tier-shared" "sharded"

echo "=========================================="
echo "ALL TESTS COMPLETE!"
echo "=========================================="
echo "Finished at: $(date '+%H:%M:%S')"
echo ""
echo "Results saved in: multiworker_results/"
echo ""
echo "Generated files:"
ls -lh multiworker_results/*.json
echo ""
echo "✅ Test suite complete! Ready for analysis."
