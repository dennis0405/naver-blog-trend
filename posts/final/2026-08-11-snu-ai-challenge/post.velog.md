# SNU AI Challenge 회고: 순열 구조를 학습에 넣고 실패를 기록한 과정

[SNU AI Challenge](https://snuaichallenge.github.io/)는 서울대학교 데이터사이언스대학원이 자체 가공한 데이터를 공개하고 국내외 대학 학부생이 최신 AI 모델을 직접 개발해 성능을 겨루도록 마련한 경진대회다. 2026년 주제는 **텍스트로 풀어보는 장면의 재구성**이었다. 스토리라인 문장과 뒤섞인 이미지 프레임 네 장을 보고 문맥에 맞는 시간 순서를 복원하는 멀티모달 추론 과제다.

예선은 온라인으로 진행됐고, public leaderboard는 전체 test data 중 70%의 Exact Match Accuracy로 계산됐다. 나는 2026년 7월 9일부터 25일까지 멀티모달 모델 설계와 학습·추론 실험을 맡았다.

실험 과정의 최고 public leaderboard Exact Match는 **0.86585**였다. 정답 순열을 한 번에 고르는 대신 이미지 간 선후 관계와 각 이미지의 위치를 나눠 학습하면서 얻은 결과다. 다만 점수보다 오래 남은 것은 좋은 아이디어를 내는 법보다 아이디어를 제대로 비교하는 법이었다. 이 글에는 그 판단 과정과 실패를 함께 기록한다.

## 문제는 네 장의 순서를 하나로 복원하는 일이었다

겉으로 보면 과제는 단순하다. 사건을 설명하는 문장 하나와 시간 순서가 섞인 이미지 네 장이 주어지고, 각 이미지가 원래 몇 번째였는지 맞히면 된다.

예를 들어 실제 순서가 `A → C → D → B`라면 A, B, C, D의 위치는 각각 1, 4, 2, 3이다. 따라서 제출값은 `[1, 4, 2, 3]`이 된다. 평가 방식은 네 위치를 전부 맞혀야 정답으로 인정하는 Exact Match였다. 세 장을 맞히고 한 장을 틀려도 0점이다.

하지만 이미지 한 장을 잘 이해하는 것만으로는 부족했다.

1. 각 이미지의 상태와 행동을 읽어야 한다.
2. 두 이미지 중 무엇이 먼저인지 판단해야 한다.
3. 문장에 담긴 사건의 흐름과 이미지 네 장을 하나의 순서로 연결해야 한다.

나는 이 문제를 **Language-guided Visual Temporal Ordering**으로 정의했다. 문제에 이름을 붙이자 탐색할 연구 범위도 선명해졌다. 이미지 분류보다 temporal ordering과 procedural reasoning에 가까운 선행 연구를 찾아보기 시작했고, 모델을 평가할 기준도 단순한 이미지 이해 능력에서 관계와 순서를 얼마나 잘 다루는지로 바뀌었다.

## 정확도보다 먼저 제출 가능성을 확인했다

대회 모델은 인터넷이 없는 환경에서 단일 RTX 3090 24GB에 올라가야 했고, 전체 테스트 추론을 24시간 안에 끝내야 했다. 외부 데이터, 상용 API, 앙상블에도 제약이 있었다.

초반에는 대회 규정과 실행 조건부터 Codex skill로 구조화했다. 모델이나 새로운 전처리 아이디어를 검토할 때마다 공개 시점, 외부 자원 사용 여부, VRAM, 추론 시간, 오프라인 재현 가능성을 같은 기준으로 확인하기 위해서였다.

대회의 목표는 accuracy 하나가 아니었다.

```text
실제 최적화 대상
= 정확도 + 규정 준수 + 실행 가능성 + 재현 가능성
```

27B 모델은 점수뿐 아니라 24GB 안에 적재되는지를 함께 봐야 했다. 학습 데이터의 이미지 쌍을 기억해 추론에 활용하는 아이디어는 효과를 검증하기 전에 규정상 허용되는지부터 확인해야 했다. 좋은 아이디어라도 제출할 수 없다면 대회 시스템의 답은 될 수 없었다.

## Backbone은 같은 조건으로 비교했다

처음에는 temporal reasoning 특화 모델이 가장 유리하다고 예상했다. 이름이나 공개 benchmark만 보고 결정하지 않았다. 세 backbone을 같은 대회 train QLoRA 조건에서 비교했다.

| Backbone | 원본 자료 | 대회 실험 구성 | Public score |
|---|---|---|---:|
| TPRU-7B | [TPRU 논문](https://arxiv.org/abs/2602.18884) | TPRU-7B + 대회 train QLoRA | 0.46945 |
| InternVL2.5-8B-MPO | [MPO 논문](https://arxiv.org/abs/2411.10442) · [InternVL2.5 MPO 문서](https://internvl.readthedocs.io/en/latest/internvl2.5/preference_optimization.html) | InternVL + 대회 train QLoRA | 0.69982 |
| Qwen3.5-9B | [Qwen3.5 공식 소개](https://qwen.ai/blog?id=qwen3.5) · [공식 model card](https://huggingface.co/Qwen/Qwen3.5-9B) | NF4 4-bit + QLoRA | **0.77661** |

### TPRU-7B

[TPRU: Advancing Temporal and Procedural Understanding in Large Multimodal Models](https://arxiv.org/abs/2602.18884)는 작은 멀티모달 모델의 temporal·procedural understanding을 강화하기 위한 데이터와 학습 방법을 제안한 연구다. Qwen2.5-VL 계열을 기반으로 로봇 조작, embodied navigation, mobile GUI, LEGO 조립에서 수집한 24,750개 QA pair를 사용했다. Temporal Reordering, Next-Frame Prediction, Previous-Frame Review의 세 task로 학습하고 GRPO 기반 reinforcement learning을 적용했다.

세 task 가운데 Temporal Reordering이 대회 문제와 직접 닮아 있어 강한 후보라고 예상했다. 하지만 task-specific post-training이 대회 train 분포에 QLoRA로 적응한 뒤에도 높은 성능을 보장하지는 않았다.

### InternVL2.5-8B-MPO

[Enhancing the Reasoning Ability of Multimodal Large Language Models via Mixed Preference Optimization](https://arxiv.org/abs/2411.10442)은 약 300만 개의 multimodal preference sample로 구성된 MMPR dataset과 Mixed Preference Optimization, 즉 MPO를 제안한 논문이다. MPO는 response 사이의 상대 선호뿐 아니라 개별 response의 품질과 선호 답변의 생성 과정까지 함께 학습해 multimodal reasoning과 Chain-of-Thought 성능을 높이는 데 목적이 있다.

논문은 InternVL2-8B-MPO를 중심으로 설명하지만, 대회에서 사용한 checkpoint는 같은 MPO 방식을 InternVL2.5 8B에 적용한 [InternVL2.5-8B-MPO](https://internvl.readthedocs.io/en/latest/internvl2.5/preference_optimization.html)였다. 범용 multimodal reasoning과 CoT가 강화된 8B급 모델이라는 점에서 두 번째 후보로 선택했다.

### Qwen3.5-9B

Qwen3.5-9B는 [Qwen3.5 공식 소개](https://qwen.ai/blog?id=qwen3.5)와 [공식 model card](https://huggingface.co/Qwen/Qwen3.5-9B)를 원본 자료로 참고했다. Vision encoder를 포함한 9B causal language model이며, vision과 language를 하나의 foundation에서 다루는 early-fusion multimodal training을 사용한다. Language model은 Gated DeltaNet과 Gated Attention을 결합한 hybrid layout으로 구성된다.

특정 temporal ordering task용 checkpoint는 아니었다. 그래도 범용 시각·언어 이해와 reasoning capacity가 대회 데이터에 더 잘 적응할 가능성을 보고 비교에 포함했다.

실험 결과는 예상을 벗어났다. Temporal·procedural reasoning에 맞춰 post-training된 TPRU가 대회 분포에서도 가장 강할 것이라는 보장은 없었다. 세 모델 중에는 Qwen3.5-9B가 가장 높았고, 이후 실험의 backbone으로 선택했다.

비교에는 zero-shot 결과를 섞지 않았다. 모두 같은 데이터와 비슷한 학습 예산으로 대회 입출력 형식에 적응시킨 뒤 비교했다. 완벽한 비교는 아니었지만, 적어도 모델 이름과 크기 외의 조건을 가능한 한 맞추려 했다.

## 24-way 분류를 Pairwise와 Position으로 풀었다

이미지 네 장이 만들 수 있는 순서는 `4! = 24`개다. 가장 단순한 방법은 24개 class 중 하나를 바로 고르는 방식이다. 하지만 이 방식은 오답 사이의 거리를 가르쳐 주지 못한다.

정답이 `ABCD`라고 해보자.

- `ABDC`는 C와 D만 바뀐 가까운 오답이다.
- `DCBA`는 모든 선후 관계가 뒤집힌 먼 오답이다.

Exact Match에서는 둘 다 똑같이 0점이다. 일반적인 24-way one-hot target에도 `ABDC`가 `DCBA`보다 정답에 가깝다는 정보는 없다.

정답은 세 관점으로 나눴다.

- **Pairwise:** 이미지 여섯 쌍 각각에서 무엇이 먼저인지 예측한다.
- **Position:** A, B, C, D가 각각 1~4번째 중 어디인지 예측한다.
- **Global:** 24개 순열 중 하나를 직접 예측한다.

최종 설정은 Pairwise와 Position을 중심으로 학습했다. 추론할 때는 두 head가 내놓은 확률을 이용해 24개 유효 순열을 모두 채점하고, 가장 일관된 하나를 선택했다.

```text
S(순열)
= 6개 pair의 평균 log-probability
+ 4개 position의 평균 log-probability
```

Pairwise 판단끼리 `A < B`, `B < C`, `C < A`처럼 모순되더라도 그대로 출력하지 않는다. 마지막에는 반드시 24개 순열 중 하나로 투영된다. 부분 판단을 배우되 출력은 항상 유효한 전체 순서가 되도록 만든 것이다.

Qwen3.5-9B에 fresh QLoRA와 이 MultiHead를 함께 학습한 baseline은 **0.84816**을 기록했다. 복잡한 adapter를 붙이기 전에, 문제의 구조를 loss와 decoding에 반영한 것이 가장 큰 첫 개선이었다.

## Token Attention만 기준점을 넘었다

MultiHead 뒤에는 여러 병목 가설을 세웠다. 이미지 사이의 국소 변화량을 직접 비교하는 Spatial Delta, 문장의 시간 접속사 주변을 사건 단위로 나누는 Event Boundary, 중요한 image token을 선택적으로 모으는 Token Attention 등을 구현했다.

| 실험 | 질문 | Public score | 결과 |
|---|---|---:|---|
| MultiHead baseline | 순열을 pair와 position으로 분해하면 나아지는가? | 0.84816 | 기준점 |
| Spatial Delta | 이미지의 국소 변화 방향을 직접 보면 좋은가? | 0.84816 | 유지 |
| Token Attention | 작은 변화 token이 평균 pooling에서 사라지는가? | **0.85689** | +0.00873 |
| Event Boundary | 문장의 시간 단서를 frame과 직접 정렬하면 좋은가? | 0.84816 | 유지 |

Token Attention은 기존 mean pooling을 버리지 않고, 문장을 참고하는 attention residual을 더했다. 사진 전체를 평균내는 동시에 문장과 관련된 작은 영역에 확대경을 한 번 더 대는 방식이었다. 점수는 올랐지만 token 수 증가, attention pooling, head 재학습이 한꺼번에 들어간 실험이었다. 어느 요소가 얼마나 기여했는지는 분리하지 못했다.

Spatial Delta에서는 정답 순열의 평균 순위나 top-k 후보 품질이 좋아지는 구간이 있었지만 최종 top-1은 개선되지 않았다. 보조 지표가 좋아졌다는 사실과 leaderboard Exact Match가 좋아진다는 결론은 같지 않았다.

Event Boundary도 기대만큼 움직이지 않았다. Backbone이 이미 시간 표현을 충분히 반영했을 수도 있고, 규칙으로 나눈 event slot이 실제 사건 구조와 맞지 않았을 수도 있다. 한 번의 실험으로 원인을 확정하기는 어려웠다.

## 답이 갈릴 때만 다시 검증했다

추론 단계에서는 입력 슬롯에 대한 민감도를 줄이기 위해 TTA와 Multi-Turn verification을 사용했다.

TTA는 이미지를 회전하거나 자르는 방식이 아니었다. 같은 네 장을 `[A, B, C, D]`, `[B, C, D, A]`처럼 서로 다른 입력 자리에 놓고 네 번 추론한 뒤, 결과를 원래 이미지 기준으로 되돌렸다.

네 번의 top-1이 모두 같으면 그대로 끝냈다. 답이 갈릴 때만 여러 view에서 반복해서 지지된 후보 두 개를 골라 다시 검증했다. 모델에는 후보 순서를 하나씩 보여 주고, 세 인접 transition과 역방향 모순을 다시 확인하도록 요청했다. 새 forward에서 얻은 pair confidence를 기존 순열 점수와 합쳐 최종 후보를 골랐다.

```text
최종 점수
= 원래 입력의 순열 점수
+ TTA 투표 비율
+ 후보 재검증 confidence
```

학습 weight를 바꾸지 않은 이 추론 전략만으로도 MultiHead 기준 **0.84816에서 0.85689**로 올랐다. 모든 sample에 계산을 더 쓰지 않았다. 모델의 판단이 갈린 경우에만 재검증한 점도 대회 제약 안에서 의미가 있었다.

## 모듈을 합친다고 성능이 더해지지는 않았다

유효했던 모듈과 기대했던 모듈을 통합한 Frontier는 **0.86387**을 기록했다. 다만 독립 실험에서 개선되지 않은 Event Boundary도 함께 들어갔기 때문에, 이 점수만으로 각 모듈의 기여를 분리할 수는 없었다.

Frontier 다음에는 그럴듯해 보이는 가설을 여러 개 시험했다.

| 실험 | 출발 가설 | Public score | Frontier 대비 |
|---|---|---:|---:|
| Frontier-2 | 모든 모듈을 공동 학습하고 입력 순서 일관성을 가르치면 더 좋다 | 0.75916 | -0.10471 |
| Frontier-CNN | 별도 image caption을 더하면 장면 정보가 보완된다 | 0.85165 | -0.01222 |
| Frontier-Small | 작은 backbone이 제한된 데이터에 더 민감하게 적응한다 | 0.84816 | -0.01571 |
| Frontier-RL | 최종 순열 reward를 직접 최적화하면 더 좋다 | 0.85863 | -0.00524 |

가장 크게 떨어진 것은 모든 구성요소를 한꺼번에 공동 학습한 Frontier-2였다. 좋은 모듈을 한 objective에 넣어도 각 장점이 자동으로 보존되지는 않았다.

Caption 실험에서도 예상과 다른 결과가 나왔다. 저해상도 이미지에서 놓치는 정보를 문장이 보완할 것이라고 예상했지만, 생성된 caption은 원본 이미지를 언어로 압축한 정보였다. 부정확한 설명이 섞이자 보완 정보보다 noise에 가까워졌다. 입력 정보가 많아져도 유효한 정보까지 늘지는 않았다.

RL에서는 24개뿐인 action 중 sample마다 5개를 중복 허용해 뽑았다. 균등한 정책을 가정하면 서로 다른 action은 평균 약 4.6개만 관측하고, 정답 action이 한 번이라도 포함될 확률도 약 19.2%에 그친다. 대회가 끝나고 돌아보니 24개 action을 전부 평가해 expected reward를 계산하는 편이 sampling noise를 줄이는 더 자연스러운 설계였다.

## 마지막에는 모델 규모를 확인했다

마지막에는 Qwen3.5-27B NF4 4-bit에 같은 MultiHead를 붙였다. Token Attention이나 Event Boundary를 통합하지 않은 비교적 단순한 구성인데도 **0.86585**로 실험 중 가장 높은 public score를 기록했다. 9B MultiHead보다 0.01769 높았다.

4B, 9B, 27B 세 점만으로 모델 규모와 점수가 선형 관계라고 단정할 수는 없다. 다만 이번 대회에서 내가 관측한 범위에서는 task-specific 구조만큼 backbone capacity도 강한 병목이었다. 초반에 architecture 아이디어를 깊게 파기 전에 family와 scale을 작은 비용으로 넓게 훑었어야 했다.

## 대회가 끝난 뒤 보인 네 가지 실수

### Checkpoint 선택 기준이 일관되지 않았다

MultiHead는 validation Exact Match를 우선해 checkpoint를 골랐지만, 일부 adapter와 Frontier는 validation 없이 training loss의 최저점을 사용했다. Training loss와 leaderboard Exact Match가 반드시 같은 방향으로 움직이지 않는데도 선택 기준이 실험마다 달랐다.

다시 한다면 모든 실험에 다음 순서를 고정할 것이다.

```text
development Exact Match
→ pairwise accuracy
→ mean gold rank
→ 더 이른 checkpoint
```

### 대부분의 adapter를 1 epoch만 학습했다

특히 zero-init residual은 학습 시작 시 영향력이 0이다. 충분한 update 전에 학습을 끝냈다면 “효과가 없다”보다 “1 epoch 안에는 효과가 나타나지 않았다”가 정확한 결론이다. 실험 비용이 부족하다는 이유로 결론의 강도까지 과하게 높여서는 안 됐다.

### 한 실험에 여러 변경을 섞었다

Token Attention에는 attention pooling뿐 아니라 token budget 증가와 head 재학습도 들어갔다. Frontier에는 개선된 모듈과 개선되지 않은 모듈이 함께 들어갔다. 최종 점수는 알 수 있었지만, 다음 실험에 무엇을 남겨야 하는지는 흐려졌다.

### Scale 탐색이 늦었다

Task-specific adapter를 먼저 깊게 파고 27B는 뒤늦게 시험했다. 다음에는 `model family × scale` matrix를 짧게 screening한 뒤 구조 실험으로 들어갈 것이다. 좁고 깊게 탐색하기 전에 가장 큰 축부터 확인해야 한다.

## 다음 실험에 남길 판단 기준

첫째, **출력 구조가 분명한 문제라면 그 구조를 학습과 디코딩에도 넣어야 한다.** Temporal ordering은 이미지 네 장을 독립적으로 분류하는 문제가 아니라 pair 관계와 전체 순열의 일관성을 함께 다루는 문제였다. Pairwise, Position, constrained decoding으로 이를 드러냈을 때 가장 큰 첫 개선이 나왔다.

둘째, **좋은 보조 지표가 최종 목표의 개선을 보장하지 않는다.** Pair accuracy나 gold rank가 좋아져도 top-1 Exact Match는 그대로일 수 있다. 실험의 성공 기준은 구현 전에 정하고, 최종 평가 지표와 얼마나 정렬되는지 확인해야 한다.

셋째, **더 많은 모듈과 더 많은 입력이 항상 더 좋은 모델을 만들지는 않는다.** Caption은 noise가 될 수 있고, 공동 학습은 이미 잘 작동하던 모듈의 장점을 무너뜨릴 수 있었다. 추가한 요소마다 독립 기여를 확인할 수 있는 ablation이 필요하다.

넷째, **GPU는 단순한 실행 장비가 아니라 검증 가능한 질문의 수를 결정한다.** 한 번의 긴 학습보다 비교 가능한 짧은 screening, 일관된 checkpoint 기준, 재현 가능한 artifact가 더 중요할 때가 많았다.

마지막으로, **재현 가능성은 대회가 끝난 뒤 문서를 쓰며 챙기는 것이 아니었다.** 규정, 데이터 상태, 실험 설정, 실패한 가설, checkpoint 선택 이유를 처음부터 남겨야 다음 판단이 빨라진다. 이번 회고도 최고 점수 하나보다 어떤 질문을 던졌고, 왜 실패했으며, 다음에는 무엇을 바꿀지를 잊지 않기 위해 작성했다.

## 다시 참여하기 전 체크리스트

- [ ] 대회 규정과 실행 환경을 모델 선택 전에 체크한다.
- [ ] Model family와 scale을 같은 조건으로 짧게 screening한다.
- [ ] 최종 평가 지표에 맞춘 development set과 checkpoint 기준을 고정한다.
- [ ] 한 실험에서는 가능한 한 하나의 변수만 바꾼다.
- [ ] 새 모듈에는 baseline을 보존하는 초기화와 명확한 ablation을 준비한다.
- [ ] 학습 epoch가 부족하다면 결론도 그 범위 안에서만 내린다.
- [ ] 성공 점수뿐 아니라 실패 가설과 중단 이유를 함께 기록한다.

## 참고 자료

- [SNU AI Challenge 공식 페이지](https://snuaichallenge.github.io/)
- [SNU AI Challenge Kaggle 대회 페이지](https://www.kaggle.com/competitions/snuaichallenge)
- [TPRU: Advancing Temporal and Procedural Understanding in Large Multimodal Models](https://arxiv.org/abs/2602.18884)
- [Enhancing the Reasoning Ability of Multimodal Large Language Models via Mixed Preference Optimization](https://arxiv.org/abs/2411.10442)
- [InternVL2.5 Mixed Preference Optimization 문서](https://internvl.readthedocs.io/en/latest/internvl2.5/preference_optimization.html)
- [Qwen3.5 공식 소개](https://qwen.ai/blog?id=qwen3.5)
- [Qwen3.5-9B 공식 model card](https://huggingface.co/Qwen/Qwen3.5-9B)
- [Burn After Reading: Do Multimodal Large Language Models Truly Capture Order of Events in Image Sequences?](https://aclanthology.org/2025.findings-acl.1248/)
- [Sort Story: Sorting Jumbled Images and Captions into Stories](https://aclanthology.org/D16-1091/)
- [A Stitch in Time: Learning Procedural Workflow via Self-Supervised Plackett-Luce](https://openaccess.thecvf.com/content/CVPR2026/html/Che_A_Stitch_in_Time_Learning_Procedural_Workflow_via_Self-Supervised_Plackett-Luce_CVPR_2026_paper.html)
