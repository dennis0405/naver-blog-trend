# Naver Tech Blog Agent

This MVP collects Naver blog search signals across discovery and target layers, stores metadata and public body text under `raw/{date}` with 7-day rolling retention, and leaves style extraction to a local script.

## What This Project Does Not Do

- It does not auto-publish to Naver Blog.
- It does not collect views, likes, comments, or private metrics.
- It does not keep raw external blog data for more than 7 days.
- It does not run style extraction as a GitHub Actions cron job.
- It does not bypass login, CAPTCHA, robots, or service restrictions.

## Setup

1. Copy `.env.example` to `.env`.
2. Fill `NAVER_CLIENT_ID` and `NAVER_CLIENT_SECRET`.
3. Run collection:

```bash
python3 -m src.collectors.collect_naver_search --date today --layers all
python3 -m src.collectors.collect_naver_trend --date today
python3 -m src.collectors.fetch_blog_bodies --date today --raw-dir raw
python3 -m src.maintenance.prune_raw_data --raw-dir raw --keep-days 7
```

## Tests

```bash
python3 -m unittest discover -s tests -p 'test*.py'
```
