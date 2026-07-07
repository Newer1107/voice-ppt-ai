#!/usr/bin/env bash
# Manually trigger the pipeline for a lecture.
# Usage: ./scripts/run_pipeline.sh <lecture-uuid>
set -euo pipefail

if [ $# -lt 1 ]; then
    echo "Usage: $0 <lecture-uuid>"
    echo ""
    echo "Dispatches the full 8-stage pipeline for an existing lecture."
    echo ""
    echo "Step 1: Find the lecture UUID"
    echo "  From the DB: sudo -u postgres psql -d lecture_narrator -c"
    echo "    \"SELECT id, title, status FROM lectures WHERE project_id = 'your-project-uuid';\""
    echo ""
    echo "Step 2: Trigger the pipeline"
    echo "  $0 <lecture-uuid>"
    exit 1
fi

LECTURE_ID="$1"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"

cd "$ROOT"
source .venv/bin/activate

python -c "
import sys, uuid, os, logging
from pathlib import Path

try:
    uuid.UUID('$LECTURE_ID')
except ValueError:
    print('ERROR: Invalid UUID format:', '$LECTURE_ID')
    sys.exit(1)

# Fix paths for lectures uploaded before the {lecture_id} fix.
# Old uploads stored files in a literal '{lecture_id}' directory
# but the DB was updated to the real UUID. Rename the directory.
from backend.src.config.settings import get_settings
settings = get_settings()
root = Path(settings.STORAGE_ROOT)
if not root.is_absolute():
    root = Path.cwd() / root
root = root.resolve()

placeholder_dir = root / 'projects'
if placeholder_dir.exists():
    for proj_dir in placeholder_dir.iterdir():
        if not proj_dir.is_dir():
            continue
        lec_dir = proj_dir / 'lectures'
        if not lec_dir.exists():
            continue
        for old_dir in lec_dir.iterdir():
            if '{lecture_id}' in old_dir.name:
                new_dir = lec_dir / '$LECTURE_ID'
                if old_dir.exists() and not new_dir.exists():
                    print(f'Fixing path: {old_dir.name} -> {new_dir.name}')
                    old_dir.rename(new_dir)

# Dispatch pipeline task
from backend.src.worker.tasks.lecture_tasks import process_lecture_pipeline
process_lecture_pipeline.delay('$LECTURE_ID')
print('Task dispatched. Check Celery worker logs for progress.')
"
