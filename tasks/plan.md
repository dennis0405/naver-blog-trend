# Implementation Plan: Naver–Velog Dual Editorial Pipeline

Status: Approved for implementation on 2026-08-11

Source of truth: `specs/naver_velog_dual_editorial_pipeline.md`

## Overview

공개 Velog 트렌딩·추천 수집을 Naver daily pipeline에 추가하고, source별 점수와 품질 gate로 균형 잡힌 참고 대상을 만든다. local style extraction은 공통·플랫폼별 playbook을 갱신하고, review skill은 동일한 초안에서 표현이 독립적인 Velog와 Naver 완성본을 생성한다.

## Architecture Decisions

- 공개 HTML 수집만 사용하고 로그인·browser dependency를 제외한다.
- 외부 source를 공통 record로 normalize하되 점수식은 source별로 둔다.
- reference targets는 source quota를 적용한 뒤 round-robin으로 합친다.
- popularity ranking과 style quality를 별도 signal로 유지한다.
- 공통 구조 편집본에서 Velog와 Naver candidate를 분기한다.
- Naver 평문 renderer는 Naver 전용 AI 편집 결과의 syntax만 제거한다.

## Dependency Graph

```text
Velog parser/client
    └── Velog collector
            └── multi-source body fetch
                    └── source-specific scoring
                            └── style quality + quota selection
                                    └── platform-aware extraction
                                            └── dual-platform review skill
                                                    └── workflow + README
```

## Phases

### Phase 0: Specification

- Commit approved spec, plan and task checklist.

### Phase 1: Velog Collection

- Add a fixture-tested flight payload parser and public client.
- Add the daily Velog collector and unified public body input.
- Verify focused collector tests and the full suite.

### Phase 2: Ranking and Quality Gate

- Generalize score component names and persist source-neutral candidate fields.
- Add Velog cohort scoring, style quality scoring and source quotas.
- Round-robin reference targets and expose source counts in daily reports.
- Verify focused ranking tests and the full suite.

### Phase 3: Platform Style Extraction

- Pass source into isolated style inputs.
- Generate validated common, Naver and Velog observations in one extraction run.
- Atomically update all playbook outputs and run metadata.
- Update and validate the `extract-style` skill.

### Phase 4: Dual Draft Review

- Change the canonical publishing output to `post.velog.md`.
- Require independent Naver editing from the common structure and Naver playbook.
- Apply humanization and preservation checks to both branches.
- Update renderer contract, quality report contract and `review-draft` metadata.

### Phase 5: Automation and Documentation

- Add Velog collection to daily GitHub Actions.
- Update Korean README, repository tree, commands, data contracts and publishing flow.
- Run the full test suite, compile check, skill validators, workflow syntax inspection and dry runs.
- Perform a five-axis code review and resolve required findings.

## Commit Strategy

1. `docs: specify Naver and Velog editorial pipeline`
2. `feat: collect public Velog reference posts`
3. `feat: rank source-balanced style references`
4. `feat: extract platform-specific style playbooks`
5. `feat: create independent Velog and Naver final posts`
6. `docs: document the dual-platform workflow`

Every feature commit includes its focused tests and leaves the full suite green.

## Risks and Mitigations

| Risk | Impact | Mitigation |
|---|---|---|
| Velog flight payload changes | High | Isolate parser, reject empty success, keep fixture tests and clear failure |
| 인기 글이 style을 왜곡 | High | Keep popularity and style quality separate, enforce source/author diversity |
| 두 final의 사실이 달라짐 | High | Shared ledger, per-branch validation and cross-platform verdict |
| 기존 SQLite schema 충돌 | Medium | Detect incompatible schema and regenerate derived data deterministically |
| style extraction output 일부만 갱신 | High | Validate all three outputs, then replace as one logical transaction with rollback |
| CI network 일시 오류 | Medium | Existing retry policy and non-empty collector validation |

## Verification Checkpoints

- After Phase 1: parser and collector tests pass; no ranking behavior changes.
- After Phase 2: deterministic 15:15 quota fixtures pass; existing Naver ranking remains valid.
- After Phase 3: fake-Codex test updates all playbooks or none.
- After Phase 4: skill validation and renderer tests pass.
- Complete: all tests and compile checks pass, git diff is clean after commits.
