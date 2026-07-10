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
python3 -m src.maintenance.prune_raw_data --raw-dir raw --keep-days 7
```

## Local Ranking

After raw data exists for a date, run the local ranking layer:

```bash
scripts/rank_targets_local.sh 2026-07-10
```

This creates:

```text
data/derived/candidates.sqlite
data/derived/reference_targets.jsonl
data/reports/daily/{date}.md
```

Ranking and reference target selection do not run metadata extraction, body style extraction, or playbook aggregation.

## Tests

```bash
python3 -m unittest discover -s tests -p 'test*.py'
```
