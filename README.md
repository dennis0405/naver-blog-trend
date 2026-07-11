# Naver Tech Blog Agent

This MVP collects Naver blog search signals across discovery and target layers, stores metadata and public body text under `raw/{date}` with 7-day rolling retention, and leaves style extraction to a local script.

## What This Project Does Not Do

- It does not auto-publish to Naver Blog.
- It does not collect views, likes, comments, or private metrics.
- It does not keep raw external blog data for more than 7 days.
- It does not run style extraction as a GitHub Actions cron job.
- It does not bypass login, CAPTCHA, robots, or service restrictions.

## Setup

1. Create `.env` locally or export environment variables.
2. Fill `NAVER_CLIENT_ID`, `NAVER_CLIENT_SECRET`, and `NAVER_API_PROVIDER=developers`.
3. Run collection:

```bash
python3 -m src.collectors.collect_naver_search --date today --layers all
python3 -m src.collectors.collect_naver_trend --date today
python3 -m src.collectors.fetch_blog_bodies --date today --raw-dir raw
python3 -m src.maintenance.prune_raw_data \
  --raw-dir raw \
  --derived-dir data/derived \
  --report-dir data/reports/daily \
  --keep-days 7
```

## Ranking

The daily GitHub workflow runs ranking after collection. To rerun ranking locally for an existing raw date:

```bash
scripts/rank_targets_local.sh 2026-07-10
```

This creates:

```text
data/derived/candidates.sqlite
data/derived/{date}/reference_targets.jsonl
data/reports/daily/{date}.md
```

Ranking and reference target selection do not run metadata extraction, body style extraction, or playbook aggregation.

## Local Style Extraction

Style extraction is a manual local operation. It is not part of the GitHub Actions cron job and does not fetch, rank, commit, or push data.

Prerequisites:

1. The Codex CLI is installed and authenticated locally.
2. The requested date and up to six preceding dates exist under both `data/derived/{date}` and `raw/{date}`. Pull the latest workflow artifacts before running when needed.
3. `knowledge/style/style_playbook.md` contains one generated marker pair. Text under `## Human Rules` is preserved.

Run with KST today as the final date:

```bash
python3 scripts/extract_style_local.py
```

Run for an explicit date:

```bash
python3 scripts/extract_style_local.py --as-of 2026-07-11
```

The default input window is seven days with the top five reference targets per day, capped at 35 before cross-day URL deduplication. Missing dates are skipped, but the command fails without modifying existing knowledge files when no valid body-backed target remains.

The command runs one isolated Codex extraction batch per non-empty date and one final aggregation pass. Codex shell tools are disabled, and allowlisted input is supplied through stdin as untrusted JSON. The extraction pass receives metadata and body text; the aggregation pass receives only validated abstract observations and count-based run statistics.

Successful runs update:

```text
knowledge/style/style_playbook.md
knowledge/style/runs/{date}.md
```

The playbook's `<!-- CODEX:GENERATED:START -->` and `<!-- CODEX:GENERATED:END -->` region is replaced only after all model outputs pass structural and source-copy validation. A failed Codex call or validation leaves existing knowledge files unchanged.

Optional flags are available through:

```bash
python3 scripts/extract_style_local.py --help
```

## Tests

```bash
python3 -m unittest discover -s tests -p 'test*.py'
python3 -m compileall -q src scripts tests
```
