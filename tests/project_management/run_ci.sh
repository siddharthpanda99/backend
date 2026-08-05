#!/bin/bash
# ── PM Module CI Pipeline — Domain 32.06 ───────────────────────────────
# Runs the full PM test suite excluding AI-dependent tests that need
# third-party API keys.
#
# Usage:
#   bash tests/project_management/run_ci.sh
#
# Exit codes:
#   0 — all tests pass
#   1 — one or more tests failed
# ─────────────────────────────────────────────────────────────────────────

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"
cd "$PROJECT_DIR"

echo "═══ PM Module CI Pipeline ═══"
echo "Project: $PROJECT_DIR"
echo ""

# ── Step 1: Python syntax check ─────────────────────────────────────────
echo "─── Step 1: Syntax check ───"
python -m py_compile "$PROJECT_DIR/../Python Libs/common_lib/src/common_lib/modules/project_management/init_db.py"
python -m py_compile "$PROJECT_DIR/../Python Libs/common_lib/src/common_lib/modules/project_management/models.py"
echo "  ✓ Syntax OK"
echo ""

# ── Step 2: Import check ───────────────────────────────────────────────
echo "─── Step 2: Import check ───"
python -c "
from common_lib.modules.project_management import service, nodes, init_db
print('  ✓ Core PM module imports OK')
from common_lib.modules.project_management.offline import service, models, nodes
print('  ✓ Offline submodule imports OK')
from common_lib.modules.project_management.cache import service, models, nodes
print('  ✓ Cache submodule imports OK')
from common_lib.modules.project_management.universal_graph import service, models, nodes
print('  ✓ Universal Graph submodule imports OK')
"
echo ""

# ── Step 3: Migration check ─────────────────────────────────────────────
echo "─── Step 3: Model registration check ───"
python -c "
from common_lib.modules.project_management.init_db import get_pm_metadata
metadata = get_pm_metadata()
pm_tables = [t for t in metadata.tables.keys() if t.startswith('pm_')]
print(f'  ✓ {len(pm_tables)} PM tables registered: {sorted(pm_tables)}')
"
echo ""

# ── Step 4: Run unit + integration + security tests ─────────────────────
echo "─── Step 4: Running PM test suite (non-AI) ───"
uv run python -m pytest tests/project_management/test_node_wrappers.py \
    tests/project_management/test_integration.py \
    tests/project_management/test_security.py \
    tests/project_management/test_migration.py \
    tests/project_management/test_performance.py \
    -q --tb=line \
    -k 'not TestCategorizeIssue and not TestSuggestAssignee \
        and not TestSummarizeIssue and not TestSummarizeSprint \
        and not TestPredictComplexity and not TestVelocityAnalysis \
        and not TestSemanticSearch and not TestAiAssistant \
        and not TestRiskDetection and not TestStandupSummary \
        and not TestStatusReport and not TestDuplicateDetection \
        and not TestProjectPlanning and not TestSprintPlanning' \
    --tb=short

result=$?
if [ $result -eq 0 ]; then
    echo ""
    echo "═══ All PM CI checks passed ═══"
else
    echo ""
    echo "═══ PM CI checks FAILED (exit code $result) ═══"
fi
exit $result
