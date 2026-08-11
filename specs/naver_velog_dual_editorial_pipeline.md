# Spec: Naver–Velog Dual Editorial Pipeline

Status: Approved by user on 2026-08-11

## Objective

개인 기술 블로그 작성자가 자신의 경험을 바탕으로 쓴 초안을 품질 높은 글로 완성할 수 있도록, Naver Blog와 Velog의 공개 상위 글을 함께 수집·선별하고 플랫폼별 스타일을 분리해 참고한다.

한 번의 `$review-draft {draft_name}` 실행으로 서로 독립적으로 편집된 Velog Markdown과 Naver 평문을 모두 생성한다. 두 글은 제목, 문장, 문단, 소제목과 전개 리듬이 달라도 되지만 초안의 사실, 경험, 날짜, 수치, 코드 동작, URL과 결론은 같아야 한다.

완료 범위는 다음과 같다.

- daily GitHub Actions에서 Naver와 Velog 공개 글을 함께 수집한다.
- Velog의 주간 트렌딩과 공개 추천 상위 20개를 수집한다.
- 플랫폼별 점수식을 적용하고 Naver 15개, Velog 15개를 기본 쿼터로 선발한다.
- 인기 후보와 스타일 참고 대상을 품질 게이트로 분리한다.
- `$extract-style` 호출을 유지하면서 공통, Velog, Naver 플레이북을 생성한다.
- `$review-draft`가 `post.velog.md`, `post.naver.txt`, `quality_report.md`를 생성하도록 확장한다.
- 두 완성본에 `humanize-korean`을 각각 적용하고 사실 일관성을 검사한다.
- 기존 7일 데이터 보존과 사람의 최종 게시 원칙을 유지한다.

## Non-Goals

- Velog 또는 Naver에 자동 게시하지 않는다.
- Velog 계정 로그인, 개인화 피드, 쿠키 또는 세션을 사용하지 않는다.
- headless browser를 기본 수집기로 추가하지 않는다. 공개 HTML 수집으로 충분하지 않다는 운영 증거가 생기면 별도 변경으로 검토한다.
- 기존 게시글을 일괄 이전하거나 다시 생성하지 않는다.
- 외부 글의 사실, 경험, 문장 또는 코드를 사용자 글에 추가하지 않는다.
- Naver와 Velog의 플랫폼 점수를 같은 원점수로 직접 비교하지 않는다.
- 초안마다 새로운 동적 플레이북을 만들지 않는다.

## Tech Stack

- Python 3.12
- Python standard library
- `unittest`
- SQLite와 JSONL
- GitHub Actions
- Codex CLI 기반 local style extraction
- repository-local Codex skills

새 Python dependency는 추가하지 않는다. Velog 페이지는 비로그인 공개 HTML의 Next.js flight payload를 읽으며 외부 응답을 untrusted data로 검증한다.

## Commands

```bash
# Velog 공개 후보 수집
python3 -m src.collectors.collect_velog_posts --date today

# Naver와 Velog 공개 본문 수집
python3 -m src.collectors.fetch_blog_bodies --date today --raw-dir raw

# 플랫폼별 점수화와 쿼터 선발
scripts/rank_targets_local.sh today

# 공통·플랫폼별 스타일 플레이북 생성
$extract-style

# 플랫폼별 완성본 생성
$review-draft {draft_name}

# 검증
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests -p 'test*.py'
python3 -m compileall -q src scripts tests
```

## Project Structure

```text
src/clients/velog_client.py                 # 공개 목록 HTML 요청과 flight payload parsing
src/collectors/collect_velog_posts.py       # trending/curated metadata JSONL 생성
src/collectors/fetch_blog_bodies.py         # Naver·Velog 후보 본문 수집
src/rankers/score_candidates.py             # 플랫폼별 점수와 쿼터 통합
src/rankers/extract_reference_targets.py    # 스타일 품질 게이트와 round-robin 선발
configs/scoring.yaml                         # 플랫폼별 가중치와 기본 쿼터
raw/{date}/velog_posts.jsonl                 # Velog 공개 후보 metadata
raw/{date}/blog_bodies.jsonl                 # 두 플랫폼 공개 본문
data/derived/{date}/reference_targets.jsonl  # 플랫폼 균형 참고 대상
knowledge/style/style_playbook.md            # 플랫폼 공통 규칙
knowledge/style/platforms/velog.md            # Velog 규칙
knowledge/style/platforms/naver.md            # Naver 규칙
.agents/skills/extract-style/                 # 같은 명령으로 세 플레이북 생성
.agents/skills/review-draft/                  # 플랫폼별 독립 완성본 생성
posts/final/{draft}/post.velog.md
posts/final/{draft}/post.naver.txt
posts/final/{draft}/quality_report.md
```

## Data Contracts

### Velog Candidate

`raw/{date}/velog_posts.jsonl`은 글이 트렌딩과 추천에 함께 등장하면 하나의 record로 합친다.

```text
id
source = "velog"
canonical_url
title_clean
description_clean
author_name
author_url
postdate                 # YYYYMMDD
released_at              # source ISO timestamp
tabs                     # trending_week, curated
tab_ranks                # tab별 1-based rank
best_rank
likes
comments_count
body_fetch_eligible
collected_at
```

URL은 `https://velog.io/@{username}/{url_slug}` 형식만 허용한다. 필수 필드가 없거나 비공개 글인 record는 버린다. 한 페이지 안의 중복 `id`와 두 탭 사이의 중복 URL은 합친다.

### Unified Candidate

Naver와 Velog 후보는 다음 공통 필드를 갖는다.

```text
source
candidate_id
canonical_url
title_clean
description_clean
author_name
author_url
postdate
discovery_channel
best_rank
has_body
body_status
body_path
total_score
score_components
style_quality_score
signals
```

외부 본문은 SQLite와 reference target JSONL에 저장하지 않는다. body text는 7일 보존 대상 raw JSONL에만 둔다.

## Collection and Scoring

### Velog Collection

- `https://velog.io/trending/week`와 `https://velog.io/curated`를 각각 요청한다.
- 페이지마다 상위 20개의 공개 post object만 사용한다.
- flight payload의 JSON string을 해석한 뒤 allowlisted post object만 받는다.
- HTML 구조 또는 payload가 올바르지 않거나 한 탭에서 유효 후보를 하나도 찾지 못하면 명확히 실패한다. 빈 성공 파일을 만들지 않는다.
- 같은 글이 두 탭에 있으면 `tabs`와 `tab_ranks`를 합친다.
- 본문 fetch는 기존 `PublicBodyFetcher`의 공개 HTML 경로를 재사용한다.

### Source-Specific Scores

공통 component 이름은 다음과 같다.

```text
rank_score
popularity_score
recency_score
tech_relevance_score
source_repeat_score
novelty_score
```

Naver에서 `rank_score`는 검색 순위, `popularity_score`는 DataLab 추이를 의미한다. Velog에서 `rank_score`는 탭 순위, `popularity_score`는 같은 날 cohort 안에서 정규화한 좋아요·댓글 반응을 의미한다. `source_repeat_score`는 Naver에서는 여러 검색어 노출, Velog에서는 여러 탭 노출을 뜻한다.

플랫폼마다 `configs/scoring.yaml`의 별도 가중치를 사용한다. 점수는 플랫폼 내부 정렬에만 사용한다.

### Quota Merge

- 기본 쿼터는 Naver 15개, Velog 15개다.
- 각 플랫폼에서 body와 최소 기술 관련성, 스타일 품질 기준을 통과한 후보를 점수순으로 선발한다.
- 최종 reference target은 source별 목록을 round-robin으로 합쳐 `rank_position`을 부여한다.
- 한 플랫폼의 후보가 쿼터보다 적어도 다른 플랫폼이 남은 쿼터를 자동으로 가져가지 않는다. 표본 균형 실패를 daily report에 드러낸다.

## Style Quality Gate

`style_quality_score`는 인기도와 별도로 다음 공개 본문 특성을 사용한다.

- 충분한 본문 길이
- 여러 문단 또는 section에 해당하는 line 구조
- 문제·원인·과정·해결·결과 계열 표현
- 코드, 명령, 목록 또는 절차에 해당하는 구조적 신호
- 광고·교육 모집·단순 뉴스 요약 같은 low-signal 표현의 부재

초기 최소값은 설정으로 관리한다. 품질 점수는 완벽한 글을 판정하지 않고 지나치게 얕은 글이 플레이북을 지배하지 않게 하는 gate다.

## Style Extraction

`$extract-style`의 이름과 실행 명령을 유지한다. 최근 7일의 source-balanced reference targets와 body를 읽고 각 input에 `source`를 포함한다.

한 번의 격리된 batch 분석은 다음 세 범주의 추상 관찰을 만든다.

- 플랫폼 공통 규칙
- Naver 전용 규칙
- Velog 전용 규칙

aggregation 결과를 검증한 후 다음 generated 영역을 atomic하게 갱신한다.

```text
knowledge/style/style_playbook.md
knowledge/style/platforms/naver.md
knowledge/style/platforms/velog.md
knowledge/style/runs/{as_of}.md
```

외부 원문, URL, 작성자, 코드 원문은 어느 playbook에도 남기지 않는다. 기존 `style_playbook.md`의 human 영역은 그대로 보존한다.

## Draft Review

`$review-draft {draft_name}`은 초안을 유일한 사실 출처로 삼고 다음 순서로 처리한다.

1. 사실, 경험, 날짜, 수치, 이름, URL, 코드, 명령과 인용을 preservation ledger에 기록한다.
2. 공통 플레이북으로 게시 가능한 공통 구조 편집본을 `_workspace/`에 만든다.
3. 공통 구조 편집본과 `platforms/velog.md`로 Velog candidate를 작성한다.
4. 공통 구조 편집본과 `platforms/naver.md`로 Naver candidate Markdown을 작성한다.
5. 두 candidate에 `humanize-korean`을 각각 별도로 적용한다.
6. 각 결과를 preservation ledger와 비교한다.
7. Naver candidate Markdown을 deterministic renderer로 평문화한다.
8. 두 완성본 사이의 보호 항목 일관성을 검사한다.

표현, 제목, 문단, 소제목, 일부 section 순서, 표와 목록 방식은 달라도 된다. 사실, 인과관계, 날짜, 기간, 수치, 결과, 코드 동작, URL 목적, 공개 범위와 핵심 결론은 달라지면 안 된다.

최종 output은 세 파일만 쓴다.

```text
posts/final/{draft_stem}/post.velog.md
posts/final/{draft_stem}/post.naver.txt
posts/final/{draft_stem}/quality_report.md
```

quality report는 전체, Velog, Naver와 cross-platform factual consistency 판정을 분리한다. 어느 한 버전이라도 publish blocker가 있으면 전체 verdict도 통과할 수 없다.

## Code Style

- 외부 HTML과 JSON은 boundary에서 검증하고 allowlist record로 변환한다.
- 네트워크 요청과 parsing을 분리해 parser를 fixture로 단위 테스트한다.
- 공통 candidate field는 source-neutral 이름을 사용한다.
- `pathlib.Path`와 기존 JSONL helper를 재사용한다.
- deterministic 정렬에는 URL 또는 stable ID를 최종 tie-breaker로 사용한다.
- 예외 메시지에 본문, credential 또는 session 정보를 포함하지 않는다.

예시 interface:

```python
def parse_velog_posts(html_text: str, *, tab: str, limit: int = 20) -> list[dict[str, object]]:
    """Return validated, ordered public Velog posts from a flight payload."""
```

## Testing Strategy

- Velog flight payload parsing과 validation은 network 없는 unit test로 검증한다.
- collector는 fake client와 temporary directory로 JSONL contract를 검증한다.
- 플랫폼별 score, cohort normalization, quota shortage와 round-robin은 unit test로 검증한다.
- style quality gate는 얕은 글, 광고성 글, 구조화된 문제 해결 글을 fixture로 검증한다.
- style extraction은 fake Codex runner로 세 playbook의 atomic update와 금지 내용 검증을 확인한다.
- review skill의 renderer와 output contract를 검사한다.
- 일반 test suite에서 실제 Velog, Naver 또는 Codex network를 호출하지 않는다.

## Boundaries

### Always

- 기능 변경 전에 실패하는 focused test를 만든다.
- 외부 response와 draft body를 untrusted data로 처리한다.
- 매 increment 후 관련 테스트와 전체 회귀 검증을 수행한다.
- commit 전 staged diff와 secret pattern을 확인한다.

### Ask First

- Velog 로그인이나 browser dependency를 추가한다.
- 7일 보존 기간 또는 35개 style input 한도를 늘린다.
- 자동 게시 권한을 추가한다.
- source quota를 제거하고 단일 점수표로 합친다.

### Never

- credential, cookie, token 또는 `.env`를 raw data나 prompt에 넣지 않는다.
- 외부 글의 원문을 playbook이나 final post에 복사하지 않는다.
- 사용자가 승인하지 않은 사실을 draft에 추가하지 않는다.
- 수집 실패를 빈 성공 파일로 숨기지 않는다.

## Success Criteria

- daily workflow가 Naver와 Velog raw metadata/body를 수집하고 7일 뒤 정리한다.
- Velog 두 공개 탭의 상위 후보가 중복 제거되어 저장된다.
- source별 점수와 15:15 쿼터가 deterministic reference targets를 만든다.
- 품질 gate를 통과하지 못한 인기 글은 style input에서 제외된다.
- `$extract-style` 한 번으로 공통, Naver, Velog playbook이 생성된다.
- `$review-draft` 한 번으로 표현이 독립적인 두 완성본과 하나의 quality report가 생성된다.
- 두 완성본의 보호 사실이 일치하지 않으면 `PASS`가 될 수 없다.
- 전체 unit test, compile check, skill validation과 local dry run이 통과한다.
- README가 수집, 추출, 검토와 수동 게시 흐름을 한국어로 설명한다.

## Open Questions

없음. 쿼터, 수집량과 threshold는 configuration으로 조정 가능한 초기값으로 취급한다.
