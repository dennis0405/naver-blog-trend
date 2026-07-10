#!/usr/bin/env bash
set -euo pipefail

DATE="${1:?usage: scripts/rank_targets_local.sh YYYY-MM-DD}"

python3 -m src.rankers.score_candidates --date "$DATE" --raw-dir raw --derived-dir data/derived
