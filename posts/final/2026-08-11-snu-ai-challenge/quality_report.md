# SNU AI Challenge 최종 원고 품질 보고서

## Verdict

**PASS** — 초안의 사실, 수치, 모델명, URL, 코드 블록과 결론을 두 플랫폼에 모두 보존했으며 게시를 막는 확인 항목이나 민감정보가 없다.

## Platform Verdicts

- Velog: **PASS** — H1 1개, 닫힌 코드 펜스, 유효한 Markdown 구조와 링크를 확인했다.
- Naver: **PASS** — 독립 Markdown 후보를 전용 변환기로 렌더링했으며 제목 시작, 일반 텍스트 구조와 금지 문법 부재를 확인했다.

## Source Draft

- 원본: `posts/drafts/2026-08-11-snu-ai-challenge.md`
- 작업 전 SHA-256: `32894946a4bc3b5f7c8915a1e07616d1a19f85a81f4d52f1fda727d47153ba89`
- 작업 후 SHA-256: `32894946a4bc3b5f7c8915a1e07616d1a19f85a81f4d52f1fda727d47153ba89`
- 결과: byte-for-byte 보존

## Technical Accuracy

- 대회 개최 배경, 문제 정의, 예선 평가 방식, 실행 제약과 참여 기간을 보존했다.
- TPRU-7B, InternVL2.5-8B-MPO, Qwen3.5-9B의 설명과 원본 자료 URL을 보존했다.
- Backbone 및 각 실험의 public score, MultiHead 구성, 순열 채점식, TTA와 Multi-Turn verification 동작을 보존했다.
- Frontier 계열 실패, RL sampling 회고, Qwen3.5-27B 결과와 실험 운영 교훈을 보존했다.
- 수치·날짜·모델명·코드 블록·URL 자동 대조 20개 항목이 모두 통과했다.

## Cross-Platform Factual Parity

- 사실, 날짜, 수치, 모델명, 실험명, URL, 코드 내용과 결론을 두 출력에서 대조했다.
- 초안의 모든 URL과 숫자 토큰이 양쪽 출력에 남아 있다.
- `must_include` 6개 항목을 양쪽 모두 포함한다.
- 플랫폼에 따른 제목, 소제목과 문단 표현만 다르며 사실의 누락이나 모순은 없다.

## Originality

초안만 사실 원천으로 사용했다. `style_playbook.md`, `platforms/naver.md`, `platforms/velog.md`에서는 추상적인 편집 규칙만 적용했으며 수집된 블로그 본문이나 reference target은 읽거나 재사용하지 않았다.

## Confidentiality

- API token 패턴: 0건
- private key 패턴: 0건
- 이메일 패턴: 0건
- IPv4 패턴: 0건
- 비공개 저장소·서버 정보, 개인 credential, 팀원 개인정보, 공개 여부가 불분명한 대회 데이터: 출력에서 발견되지 않음

## Style Playbooks

- 공통: 배경에서 문제, 실험, 실패, 교훈으로 이어지는 회고 구조와 사실·평가의 구분을 유지했다.
- Velog: 문장형 소제목, 짧은 문단, 주장 가까이 배치한 링크와 Markdown 표·코드 블록을 적용했다.
- Naver: 검색 의도가 드러나는 제목, 모바일에서 읽기 쉬운 문단, 편집기 친화적인 소제목·목록·표 렌더링을 적용했다.
- 초안에 없는 사실, 수치, 날짜, 코드와 URL은 추가하지 않았다.

## Humanize Korean

- Velog: H2 경계의 3개 chunk에 별도 Fast Path를 적용했다. 문자 가중 변경률 0.75%, 최저 등급 B, 건너뛴 절 0개, 전체 자체검증 6/6 통과. 사실과 보호 블록을 우선한 보수적 윤문이다.
- Naver: H2 경계의 3개 chunk에 별도 Fast Path를 적용했다. 문자 가중 변경률 0.82%, 최저 등급 B, 건너뛴 절 0개, 전체 자체검증 6/6 통과. 사실과 보호 블록을 우선한 보수적 윤문이다.
- 두 플랫폼 모두 의미 변경, 보호 span 차이, 30% 초과 변경이 없어 롤백하지 않았다.
- B 등급이므로 더 공격적인 AI 문체 제거가 필요하면 Claude Code의 strict 5인 파이프라인을 권장한다.

## Publishing Format

- `post.velog.md`: 정확히 1개의 H1, 유효한 소제목, 닫힌 코드 펜스, 내부 frontmatter·humanize 주석 없음.
- `post.naver.txt`: 전용 renderer로 생성했으며 제목으로 시작한다. heading marker, fence delimiter, 표 구분선, inline backtick, Markdown link 문법이 없다.
- 두 파일 모두 `[확인 필요]`가 없다.

## Remaining TODO

없음. 게시 전 사람이 제목, 문단 호흡과 대회 공개 범위를 마지막으로 확인하기를 권장한다.
