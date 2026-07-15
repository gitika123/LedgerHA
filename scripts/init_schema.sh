#!/usr/bin/env bash
# Bootstraps local schema. For RDS, set DATABASE_URL first.
set -euo pipefail
cd "$(dirname "$0")/../app"
python -m app.bootstrap_schema
