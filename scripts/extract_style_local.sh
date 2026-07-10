#!/usr/bin/env bash
set -euo pipefail

DATE="${1:?usage: scripts/extract_style_local.sh YYYY-MM-DD}"

python3 -m src.analyzers.extract_metadata_patterns --date "$DATE" --raw-dir raw
python3 -m src.analyzers.extract_body_style_patterns --date "$DATE" --raw-dir raw
python3 -m src.rankers.score_candidates --date "$DATE"
python3 -m src.analyzers.aggregate_playbook --week current
