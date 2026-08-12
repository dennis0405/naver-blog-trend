# SNU AI Challenge 최종 원고 품질 보고서

## Verdict

**PASS** — 수정된 초안과 2026-08-12 스타일 플레이북을 기준으로 두 플랫폼 원고를 독립적으로 다시 작성했다. 사실·수치·URL·코드·결론이 양쪽에 보존됐고 게시를 막는 확인 항목이나 민감정보는 없다.

## Platform Verdicts

- Velog: **PASS** — 회고의 시간 흐름과 기술 판단을 짧은 문장형 소제목으로 재구성했으며 Markdown 구조 검사를 통과했다.
- Naver: **PASS** — 검색형 제목, 설명형 소제목, 모바일 문단으로 독립 작성한 뒤 전용 renderer 검사를 통과했다.

## Source Draft

- 원본: `posts/drafts/2026-08-11-snu-ai-challenge.md`
- 작업 전 SHA-256: `32894946a4bc3b5f7c8915a1e07616d1a19f85a81f4d52f1fda727d47153ba89`
- 작업 후 SHA-256: `32894946a4bc3b5f7c8915a1e07616d1a19f85a81f4d52f1fda727d47153ba89`
- 결과: byte-for-byte 보존

## Technical Accuracy

- 서울대학교 데이터사이언스대학원의 개최 배경, 2026년 과제, 예선 평가 방식과 참여 기간을 보존했다.
- TPRU-7B, InternVL2.5-8B-MPO, Qwen3.5-9B의 설명·원본 URL·비교 조건·public score를 보존했다.
- MultiHead의 Pairwise·Position·Global 구성, 순열 채점식, constrained decoding과 baseline 결과를 보존했다.
- Spatial Delta, Token Attention, Event Boundary, TTA, Multi-Turn verification의 방법·결과·한계를 보존했다.
- Frontier 계열 실패, RL sampling 회고, Qwen3.5-27B 최고 public score와 운영 교훈을 보존했다.
- 자동 대조 24개 항목이 모두 통과했다.

## Cross-Platform Factual Parity

- 초안의 URL 집합과 숫자 토큰이 Velog와 Naver 양쪽에 모두 남아 있다.
- 날짜, 모델명, 실험명, 점수, 코드 블록, 인과관계, 불확실성과 결론을 대조했다.
- `must_include` 6개 항목이 두 원고에 모두 포함됐다.
- 제목, 소제목, 문단 호흡만 플랫폼별로 다르며 보호 사실의 비대칭 누락이나 모순은 없다.

## Originality

사실 원천은 초안 하나만 사용했다. 2026-08-12에 갱신된 공통·Naver·Velog 플레이북에서는 추상적인 편집 규칙만 적용했으며, 수집된 블로그 본문이나 reference target 및 기존 final 원고는 읽거나 재사용하지 않았다.

## Confidentiality

- API token 패턴: 0건
- private key 패턴: 0건
- 이메일 패턴: 0건
- IPv4 패턴: 0건
- 비공개 저장소·서버 정보, 개인 credential, 팀원 개인정보, 공개 여부가 불분명한 대회 데이터: 발견되지 않음

## Style Playbooks

- 공통: 대회 배경에서 문제 정의, 실험, 실패, 운영 교훈으로 이어지는 회고 흐름을 적용했다. 도입의 대회 개요와 결과 요약은 중복 없이 하나로 합쳤다.
- Velog: 짧은 문장형 Markdown 소제목, 한 문단 한두 개의 판단, 기술적 근거 뒤의 해석, 주장 가까이 둔 링크를 적용했다.
- Naver: 검색 의도가 드러나는 제목, 설명형 소제목, 짧은 모바일 문단, 비교 표와 체크리스트의 편집기 친화적 렌더링을 적용했다.
- Velog 최신 표본은 3건으로 적으므로 low-confidence 장식 규칙은 강제하지 않았다.

## Humanize Korean

- Velog: H2 경계의 3개 chunk에 Fast Path를 별도 적용했다. 문자 가중 변경률 0.51%, 최저 등급 B, 건너뛴 절 0개, 모든 chunk 자체검증 6/6 통과.
- Naver: H2 경계의 3개 chunk에 Fast Path를 별도 적용했다. 문자 가중 변경률 0.76%, 최저 등급 B, 건너뛴 절 0개, 모든 chunk 자체검증 6/6 통과.
- URL, 표, 코드 블록, 인용, 날짜, 수치, 고유명사와 기술 식별자는 윤문 대상에서 제외하거나 원형을 보존했다.
- 의미 변경, 보호 span 차이, 30% 초과 변경이 없어 롤백은 없었다.
- 두 결과 모두 B 등급이므로 더 강한 AI 문체 제거가 필요하면 Claude Code의 strict 5인 파이프라인을 권장한다.

## Publishing Format

- `post.velog.md`: H1 1개, 일관된 heading 계층, 닫힌 코드 fence, 내부 metadata와 humanize 주석 없음.
- `post.naver.txt`: 독립 Naver Markdown 후보를 전용 renderer로 생성했다. 제목으로 시작하며 heading marker, fence delimiter, 표 구분선, inline backtick, Markdown link 문법과 Naver UI placeholder가 없다.
- 두 출력 모두 `[확인 필요]`가 없다.

## Remaining TODO

없음. 실제 게시 전 제목, 모바일 표 가독성, 대회 공개 범위를 사람이 마지막으로 검토하기를 권장한다.
