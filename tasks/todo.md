# Tasks: Naver–Velog Dual Editorial Pipeline

Source of truth: `specs/naver_velog_dual_editorial_pipeline.md`

- [x] Task 0: Commit the approved spec and implementation plan
  - Acceptance: objective, contracts, boundaries and success criteria are explicit
  - Verify: `git diff --check`
  - Files: `specs/`, `tasks/`

- [x] Task 1: Collect public Velog trending and curated posts
  - Acceptance: valid top posts are deduplicated and written to `velog_posts.jsonl`
  - Verify: focused parser and collector tests, then full suite
  - Files: client, collector, body fetcher, tests

- [x] Task 2: Rank and select source-balanced style references
  - Acceptance: source-specific scores, style gate, 15:15 quotas and round-robin ordering work
  - Verify: focused ranking tests, SQLite/report integration, then full suite
  - Files: scoring config, rankers, reports, tests

- [ ] Task 3: Extract common and platform-specific playbooks
  - Acceptance: one run atomically updates common, Naver and Velog generated rules
  - Verify: fake-Codex integration tests and extract-style skill validation
  - Files: extraction script, prompts, knowledge templates, skill, tests

- [ ] Task 4: Generate independent Velog and Naver final posts
  - Acceptance: review skill writes both platform outputs and cross-platform quality verdict
  - Verify: renderer tests, skill validation and read-only forward test
  - Files: review skill, renderer contract, metadata, tests

- [ ] Task 5: Update automation and Korean documentation
  - Acceptance: daily workflow collects Velog and README describes the full operation
  - Verify: workflow inspection, README command/path checks, full suite and compile check
  - Files: GitHub Actions, README, task status

- [ ] Task 6: Final review and clean handoff
  - Acceptance: no required correctness, security, architecture or documentation finding remains
  - Verify: staged diff review, secret scan, `git status --short --branch`
  - Files: only corrections required by review
