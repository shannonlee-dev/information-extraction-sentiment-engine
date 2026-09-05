# 미션 범위 감성 엔진 개선 Implementation Plan

> **상태: 미실행 후속 제안.** 기존 엔진의 외부 평가는 완료됐고 목표에 미달했다. 이 문서는 재설계 실행 지시가 있을 때 개발 분할 진단부터 진행하기 위한 계획이다. 체크박스는 실제 검증 후 표시한다. 이미 열람한 v1 final은 새 엔진의 독립 최종 평가에 재사용할 수 없다.

**Goal:** 개발 자료에서 확인된 활용형·품사·부정 범위 오류를 공통 언어 규칙으로 개선하되, 미션의 사전 기반 점수와 공개 API를 유지한다.

**Architecture:** 한 개의 KOMORAN 어댑터가 원문 위치를 보존한 형태소를 반환한다. 입력과 사전을 같은 어휘 표현으로 정규화하고, 제한된 형태소 문법으로 감성 사건과 수정어를 연결한다. 평가 데이터의 준비·보류·최종 판정은 A 계획에 맡긴다.

**Tech Stack:** Python 3.10 이상, 내장 re, KoNLPy 0.6.0, 그 배포물의 KOMORAN jar/model, 실제 호환성을 검증한 JPype/JDK, pytest. JDK 17은 우선 검증할 후보이며 동작 확인 사실이 아니다.

**평가 기준:** [동결 프로토콜](evaluation/sentiment-protocol.md), [실행 가이드](evaluation/benchmark-guide.md), [확정 결과](evaluation/sentiment-results.md). 완료된 상위 계획과 대체된 초기 제안은 Git 커밋 `db765d9`에 보존돼 있다.

이하 A1~A7은 기준선 보존 → 데이터 준비 → 평가기 → 개발 진단 → 후보 선택·동결 → 최종 평가 → 문서화를 뜻한다. v1은 단일 baseline 평가까지 완료했으며, 복수 후보 선택은 [프로젝트 진단](project-audit.md)에 기록한 release 형식 호환 문제를 해결한 뒤 새 평가 버전에서 사용해야 한다.

## 1. 범위·전제·분기

- 미션은 토큰화, 200개 이상 감성어, 사전 합산, 부정·강조, 이중부정 한 구성을 요구한다. KoNLPy는 허용하며 JVM/형태소 도입 자체가 목표는 아니다.
- A1 기준선 스냅샷과 A2 데이터 격리를 완료한 상태에서 A4 development의 반복 오류가 개선 근거다. final/selection을 읽어 개선 방향을 결정하지 않는다.
- 형태소·문법 규칙의 후보는 미션 공개 `analyze_sentiment(text, apply_modifiers=True)`, `analyze(text)`와 기존 `SentimentResult`, `SentimentMatch` 필드·자료형을 보존한다. 공개 `tokens`는 기존 `_TOKEN_PATTERN`의 원문 토큰 표시를 유지하고 내부 형태소와 구분한다.
- 기존 `extraction.py`와 5종 추출 정규화는 변경하지 않는다. 재설계 실패해도 baseline으로 A 계획의 평가를 완료할 수 있다.
- B1 환경 검증을 통과하면 B2~B4를 진행한다. 실패 시 silent fallback을 넣지 않고 B 후보 미완료로 기록한다.
- 기본 개선 후보 **M**은 감사한 프로젝트 사전 + KOMORAN + 제한 문법이다. 외부 KNU의 이용·배포 조건과 변환 검수가 충족될 때만 후보 **K**를 추가한다. A5에서 baseline/M/K 최대 3개를 비교한다. KNU 확보 실패가 M 또는 외부 평가 자체를 막지 않는다.
- B 단계의 성능 게이트에 합성 92%/90% 또는 새 외부 0.80을 강제하지 않는다. 기능 계약을 확인한 뒤 최종 성능은 A6에서 판정한다.

## 2. 조사에서 확인한 기술 사실

2026-09-05 조사 기준:

1. KoNLPy **v0.6.0** wrapper는 `self.jki.analyze(sentence).getTokenList()`를 사용한다. `pos()`는 형태소/POS만 뽑으며 `flatten=False` 목록을 어절과 zip하면 안 된다. [T1]
2. 같은 태그의 `konlpy/java`에는 **komoran-3.0.jar**가 있다. 온라인 KOMORAN 문서는 3.3.9다. 최신 문서의 위치 API가 배포 jar에서 동일하게 동작한다고 가정하지 않는다. [T2][T3]
3. 공식 설치 문서는 Java 의존성을 설명하지만 Python 3.10/3.12·JPype·JDK 17 조합을 인증하지 않는다. 실제 import/초기화/위치·메모리 검증이 필요하다. [T4]
4. KNU는 단어뿐 아니라 어구·문형·축약어·이모티콘을 포함한다. 공개 README/ReadMe.txt 조사에서 명시적 라이선스 조건은 확인하지 못했다. 외부 출처가 있다는 사실만으로 검수 없는 전체 phrase lookup 또는 재배포를 정당화하지 않는다. [T5][T6]

이 문서 작성 중 KoNLPy/Java 설치, jar 호출, 사전 다운로드, 형태소 분석 성능 실험을 실행하지 않았다.

## 3. 형태소·사전·점수 계약

### 형태소 위치와 초기화

- 분석기 접근은 `korean.py` 한 곳에서 한다. 레지스트리·복수 백엔드 프레임워크를 만들지 않는다. `self.jki` 의존성을 어댑터 내부에 가두고 배포 버전·파일 해시를 확인한다.
- `MorphToken`은 `morph:str`, `pos:str`, `start:int`, `end:int`, `eojeol_index:int`를 가진다. `morph`를 원문 substring과 같다고 가정하지 않는다. `lemma`라는 필드명으로 일반 표제어 추출을 보증하지 않는다.
- `text.splitlines(keepends=True)`로 줄과 원래 시작점을 보존한다. CR/LF 구분자는 분석 입력에서 제외해도 전체 오프셋에 정확히 더한다. 원문 NFC/공백 축약은 하지 않는다. 어절은 원문 공백 구간으로 정의하고 형태소 범위와 대조한다.
- Java UTF-16 경계→Python code point 인덱스를 명시적으로 변환한다. emoji surrogate 중간 경계는 오류다. 축약형에서 여러 형태소가 같은 음절 범위를 가질 수 있다. 구간 중첩 자체를 실패로 보지 않는다.
- 문장부호·줄바꿈을 절 경계 구성에 보존한다. 분석기가 빈 입력/공백만 입력에 반환하는 결과는 별도로 정의한다. 전체가 분석 불가능한 비어 있지 않은 입력과 정상 빈 감성 매칭을 구별한다.
- 하나의 프로세스에서 JVM을 한 번 초기화하고 bounded 캐시만 사용한다. heap 1024MiB를 우선 검증하며 실제 peak RSS도 기록한다. 모델/설정 변경 시 캐시를 재사용하지 않는다.
- 지원 경로는 저장소 checkout+editable install이다. 현 구조의 루트 `data/` 접근을 wheel 설치 지원이라고 주장하지 않는다. 패키지 배포 개선은 별도 범위다.

### 사전 구축과 KNU 선택 조건

- 프로젝트 사전 원본 schema `term,variants,score,domain,source`를 유지한다. 별도 `data/lexicon_annotations.json`에 항목별 품사/의미 근거·원자성·수정어 소비 정책·검수 이력을 저장한다.
- `scripts/build_sentiment_lexicon.py`는 같은 형태소 설정으로 `data/sentiment_lexicon_compiled.json`을 결정적으로 생성한다. compiled에는 원본/분석기/model 해시, canonical ID, key, score, domain, source, atomic 표기를 포함한다. 런타임은 이 해시를 대조하고 불일치하면 명시적 설정 오류다.
- key는 감성 어휘의 `(morph,pos)` 열이다. J 계열 조사, EP/EF/EC 종결·시제 등을 **어휘 말단 활용부에서만** 제외한다. XSV/XSA 파생 접사와 의미를 바꾸는 내부 구성은 보존한다. 전 문장에서 품사 몇 개를 삭제해 phrase를 억지로 연결하지 않는다.
- 명사 복합어 내부의 감성 명사 부분 매칭을 제한한다. 어절/파생 경계를 지키며 명사/용언 동형어를 구별한다. 동일 lemma의 문맥별 POS 차이를 감성 분석기가 완벽하게 해결한다고 주장하지 않는다.
- 겹친 후보는 토큰 시작 위치 기준 왼쪽부터 **긴 어휘 key 우선**, 같은 길이는 검수된 명시 우선순위, 나머지 동점은 canonical ID 정렬로 결정한다. 같은 사건을 중복 합산하지 않는다.
- 동일 key의 같은 점수는 한 항목으로 병합해 출처들을 보존한다. 상충 점수는 충돌 보고서로 보내고 검수된 override가 없는 경우 매칭에서 제외한다. 파일 순서·임의 평균은 사용하지 않는다.
- 항목 수는 최종 compiled에서 충돌/0점/활용 중복 제외 후 canonical lexical entry 200개 이상, 그중 직접 구축한 domain entry 30개 이상이다. 서로 다른 동의어 단어까지 모두 한 개로 합치지 않는다. 활용형 여러 개를 대표어 수로 중복 집계하지 않는다.
- `문제가 해결되다` 등 관측 오류를 고치려고 넣은 구문은 항목별 근거를 감사한다. 독립 어휘 의미가 없이 문장을 열거한 것은 후보 M에서 제외하고 기록한다. 특정 4개 표현의 점수 회복을 필수 기능으로 두지 않는다. 독립적 관용구는 근거를 남겨 유지할 수 있다.
- 명사/형용사 점수와 ±1/±2/±3 기준을 문서화한다. 직접 점수는 경험적 설정이며 통계적으로 학습된 정답이 아니다. AI가 검수하면 AI 검수로 기록한다.

K 후보 조건:

1. 실제 KNU 원본 경로·commit·바이트 해시·필드/점수 범위를 확인한다. 미션의 잘못된 `read_csv(json)` 예시를 그대로 구현하지 않는다.
2. 이용·배포 근거를 문서화할 수 있을 때만 도입한다. 확인할 수 없으면 K만 제외하고 M으로 진행한다. 출처 표기와 라이선스 허가는 별개다.
3. 검수 범위는 **최대 500개 canonical 항목**으로 제한한다. 원본 항목을 정규화 문자열/원본 ID 순으로 감사하며 어휘/품사/극성/부정 소비 기준에 맞는 항목을 채택한다. 최종 문장이나 final 감성어 출현 빈도로 고르지 않는다. 후보 M의 기본 어휘를 억지로 없애지 않고 외부 항목을 추가한 K의 효과를 개발 실험에서 따로 보고한다.
4. 0점, 스키마 오류, 비합성 여부 미검토 phrase, 합성적 부정·강조 phrase는 제외 목록으로 남긴다. 출처 있는 비합성 관용구는 내부 수정어 소비를 표시한다. 원본 점수를 유지하고 도메인 override는 별도 표시한다.
5. 재현에는 원본 해시만으로 충분하지 않다. 채택/제외/override 결정 파일 자체와 compiled 해시를 버전 관리한다. 외부 자료 배포 조건에 맞게 원본/파생물의 공개 범위를 정한다.

### 제한된 구문과 점수

형태소 분석은 의존 구문 분석이 아니다. 아래 문법은 POS 열·어절·연결 어미를 이용한 제한된 matcher다. 의미 연결의 일반 해법으로 부르지 않는다.

| 지원 구성 | 연결 계약 | 필수 반례 |
|---|---|---|
| 용언/파생 용언의 활용 | 동일 감성 어휘에 높임·시제·종결만 붙으면 같은 base score | `피해` 명사와 `피하다` 동사 혼동 금지 |
| 선행 안/못 | 같은 절에서 바로 뒤 술어 그룹, 중간엔 허용된 강조 부사만 | `불만이지만 ... 못 ...`을 앞 절 불만에 연결 금지 |
| 후행 -지 않다/-지 못하다 | 연결 어미 지 + 부정 보조 용언을 원 술어 사건에 연결 | 부정 용언 근처 다른 감성어를 거리만으로 반전 금지 |
| 감성 명사 + 없다/아니다 | 해당 명사+조사와 서술어의 국소 구성에만 연결 | `불만을 말할 시간이 없다`에서 불만 반전 금지 |
| [[감성 용언]-지 않다]+것은 아니다 | 명사화된 앞 술어에 두 부정을 중첩 연결 | `친절하지 않다. 그것은 아니다`를 한 사건의 이중부정으로 합치지 않음 |
| 강조 부사 + 술어 그룹 | 같은 그룹 사건에만 배수 적용 | 다른 절의 감성어에 전달 금지 |
| 독립/대조 절 | 사건을 분리해 기여 합산 | 하지만 뒤를 무조건 우승시키지 않음 |

초기 거리 상한은 수정어와 사건 사이 **원문 어절 2개**다. 이는 이미 허용 문법이 성립한 연결의 안전 상한이다. 근접성만으로 새 연결을 만들지 않는다. v1 후보에서 거리 0/1/2 튜닝은 하지 않는다. 문법·강조 목록은 development에서 고정하고 selection 뒤 변경하지 않는다.

`없다`가 포함된 모든 명사를 무조건 반전하지 않는다. KNU/직접 사전에 원자적으로 등록한 비합성 표현의 내부 부정은 소비된 것으로 취급하고 외부 부정만 추가 연결한다. 합성 표현은 어휘 사건과 연산자로 분해한다. 중첩한 부정 보조용언을 독립 감성 사건으로 다시 세지 않는다.

```text
A(e)=min(2.0, 연결된 강조어 배수의 곱); 빈 곱=1
c(e)=w(e)*A(e)*(-1)^연결된_부정수
score=round(sum(c(e)),6)
positive if score>0; negative if score<0; neutral otherwise
mixed=양수 기여와 음수 기여가 동시에 존재
```

`매우/정말/아주`의 초기 배수는 1.5, 기존 다른 강조어는 modifiers.json의 검수된 값으로 고정한다. 이중부정은 지원 문법에서 부호를 복원하는 설계 정책이며 자연어의 완곡함·강도까지 원문 긍정과 같다는 주장으로 확대하지 않는다.

`apply_modifiers=False`에서도 동일한 형태소/사전/사건 분해를 사용하고 부정·강조 적용만 끈다. 원자적 관용구의 어휘 점수는 유지한다. 모든 match의 `text[start:end]==raw`, 합계 보존, 사건/연산자 단일 소비를 검사한다.

## 4. 파일·내부 인터페이스

| 파일 | 작업과 책임 |
|---|---|
| `src/sentiment_engine/korean.py` | word_forms 대신 단일 KOMORAN 어댑터, 위치 변환 |
| `src/sentiment_engine/sentiment.py` | compiled 사전 검증·사건 매칭·기존 공개 API |
| `src/sentiment_engine/sentiment_rules.py` | POS/절 기반 수정어 연결·추적·합산 |
| `src/sentiment_engine/models.py` | 기존 공개 dataclass 유지, 내부 MorphToken/Event 추가 |
| `data/sentiment_lexicon.json`, `data/modifiers.json` | 검수된 어휘/수정어 원본 |
| `data/lexicon_annotations.json`, `data/lexicon_provenance.json` | 의미·품사·원자성·출처·판정 이력 |
| `data/sentiment_lexicon_compiled.json` | 재현 가능한 정규화 사전 |
| `scripts/build_sentiment_lexicon.py` | 원본+검수 결정→compiled 변환 |
| `scripts/probe_komoran.py` | 실제 jar/model/API/offset 기술 검증 |
| `requirements.txt`, `requirements-runtime.lock`, `pyproject.toml` | 실제 검증 runtime 버전·hash·JDK 조건 |
| `tests/sentiment/test_morphology.py`, `test_composition.py` | 형태소 위치·문법·반례 |
| `tests/sentiment/test_resources_tokenizer.py`, `test_korean_matching.py`, `test_modifiers.py`, `test_scoring.py` | 기존 계약 migration/회귀 |
| `tests/test_integration_cli.py`, `src/sentiment_engine/cli.py` | 호환성과 JVM/자원 오류 진단 |
| `docs/evaluation/engine-development.md`, `README.md` | 환경·실험·후보 구성·지원 범위 |

다음은 내부 사양이다. 타입는 models.py에 한 번만 정의한다.

```text
MorphToken(morph:str,pos:str,start:int,end:int,eojeol_index:int)
SentimentEvent(canonical_id:str,term:str,score:int,
               token_start:int,token_end:int,atomic:bool)
ModifierLink(event_index:int,modifier_start:int,modifier_end:int,
             kind:str,rule_id:str,multiplier:float)
analyze_morphology(text:str) -> tuple[MorphToken,...]
find_events(tokens:tuple[MorphToken,...]) -> tuple[SentimentEvent,...]
link_modifiers(text:str,tokens:tuple[MorphToken,...],events:tuple[SentimentEvent,...])
  -> tuple[ModifierLink,...]
score_events(text:str,tokens:tuple[MorphToken,...],events:tuple[SentimentEvent,...],
             links:tuple[ModifierLink,...],*,apply_modifiers:bool) -> list[SentimentMatch]
```

token_start/end는 형태소 열의 반개구간, 공개 start/end는 Python 원문 위치다. 원자적 항목의 내부 수정어는 링크를 추가하지 않고 소비 추적에 기록한다. 추적에 rule_id와 대상 event index를 저장해 부정 횟수뿐 아니라 대상도 검증한다.

## 5. 실행 작업

### B1 — 별도 환경에서 실제 KOMORAN 계약 확인

**Files:** probe_komoran.py, korean.py, 내부 타입, test_morphology.py, runtime lock.
**Consumes:** A1 baseline과 development 오류 근거. **Produces:** 위치가 보존된 형태소 어댑터 또는 명시적 부적격 판정.

- [ ] 별도 환경에서 KoNLPy 0.6.0/JDK 17을 우선 설치한다. Python 3.10/현재 Python에서 호환하는 JPype를 검증하고 실제 버전·Python/JDK vendor·OS·architecture를 기록한다. 현재 환경을 덮어쓰지 않는다.
- [ ] 배포 jar/model의 파일명·해시를 수집하고 토큰의 `getMorph/getPos/getBeginIndex/getEndIndex` 실재와 호출 결과를 확인한다. 3.3.9 문서만 보고 배포 jar 버전을 바꾸지 않는다.
- [ ] 축약·과거·높임, 이모지, 반복 단어, 공백 두 개, TAB, CRLF/빈 줄에 정확한 기대 source 범위를 둔 테스트를 작성하고 현재 어댑터에서 실패를 확인한다.

```python
def test_utf16_map_has_no_surrogate_midpoint():
    from sentiment_engine.korean import utf16_boundaries
    assert utf16_boundaries("🙂 좋다") == {0:0, 2:1, 3:2, 4:3, 5:4}

def test_repeated_words_keep_distinct_source_ranges():
    from sentiment_engine.korean import analyze_morphology
    text = "좋다  좋다"
    tokens = analyze_morphology(text)
    good = [t for t in tokens if t.morph == "좋" and t.pos == "VA"]
    assert [(t.start, t.end) for t in good] == [(0,1), (4,5)]
    assert all(0 <= t.start < t.end <= len(text) for t in tokens)
```

- [ ] `utf16_boundaries(text:str)->dict[int,int]`는 Unicode 문자를 순회하여 BMP면 Java index+1, supplementary면 +2, Python index+1로 경계만 기록한다. 없는 Java 경계를 조회하면 오류다. 문자열 find로 정렬하지 않는다.
- [ ] 실제 jar에서 축약형의 중첩 범위가 어떻게 나오는지 기록하고 어댑터 계약을 충족하는지 확인한다. 중첩된 음절 범위와 길이가 0인 범위를 구별하며 임의 범위 보정을 금지한다.
- [ ] 이 계획의 초기 위치 계약은 모든 반환 MorphToken에 `0 <= start < end <= len(text)`다. 실제 분석기가 타당한 zero-length 형태소를 요구하면 이를 조용히 버리거나 주변 글자에 붙이지 않는다. B1 부적격으로 기록하고 위치 계약 개정안을 먼저 문서화한 뒤 재검증한다. 원문 사건 정렬이 검증되기 전 B2로 넘어가지 않는다.
- [ ] cold/warm 호출·heap/RSS를 기록한다. `python -m pytest tests/sentiment/test_morphology.py -q`와 새 환경 import를 확인한다.

**Gate:** 위치·버전·환경 계약 미충족이면 B1 실패를 보고하고 B2를 진행하지 않는다. A 계획의 baseline 평가 경로는 사용 가능하다.

### B2 — 프로젝트 사전 감사·결정적 compiled 사전

**Files:** 사전 원본/annotations/provenance/compiled, build 스크립트, sentiment.py, resources 테스트.
**Consumes:** B1 분석기·현재 사전, 선택적으로 이용 조건 확인된 KNU. **Produces:** 후보 M, 조건 충족 시 K의 사전 artifact.

- [ ] 모든 현재 canonical 항목에 source/score/품사/도메인/유지·제외 근거를 기록한다. 활용형 중복과 동의어를 구별하고 전체 문장 예외를 감사한다.
- [ ] 정상 활용형, 피해/피하다, 명사 복합어 부분 매칭 방지, 같은 key 상충, 입력 파일 순서 독립성, 원자적 내부 부정 소비 테스트를 먼저 작성→실패 확인한다.
- [ ] key 구성·canonical 병합·충돌 제외를 구현한다. 최소 200개/직접 domain 30개는 compiled 최종 기준으로 검사한다. 부족하면 development에서 의미·극성이 설명 가능한 어휘를 추가하고 검수 근거를 남긴다.
- [ ] 원본+annotations+model hash가 같으면 compiled 바이트 동일, 사전 순서만 바뀌면 semantic index 동일, model hash가 바뀌면 런타임 거부를 검사한다.
- [ ] KNU는 3절 K 조건을 충족할 때만 도입한다. 채택/제외/override 파일이 재현에 포함되어야 한다. 조건 불명확 시 K 부적격 사유를 기록하고 M으로 진행한다.

```bash
python -m scripts.build_sentiment_lexicon \
  --source data/sentiment_lexicon.json \
  --annotations data/lexicon_annotations.json \
  --output data/sentiment_lexicon_compiled.json
python -m pytest tests/sentiment/test_resources_tokenizer.py tests/sentiment/test_morphology.py -q
```

**Gate:** 정규화 후 개수·출처·충돌·매칭 계약 통과. source가 외부인지 project인지 정확히 구별한다.

### B3 — 국소 문법·기여도·공개 API 연결

**Files:** sentiment_rules.py, sentiment.py, models.py, modifiers, composition/modifiers/scoring/matching 테스트.
**Consumes:** MorphToken·SentimentEvent. **Produces:** 기존 형식 SentimentResult와 내부 ModifierLink 추적.

- [ ] 어휘 확정→술어/절 경계→원자적 소비→단일 부정→명사화 이중부정→강조→합산 순서를 구현한다. 다중 규칙이 같은 연산자를 소비할 때 더 구체적인 문법 우선, 같은 문법이면 가장 안쪽 술어 그룹 우선으로 고정하고 trace에 남긴다.
- [ ] 3절 표의 정상/반례를 각 규칙 추가 전에 테스트로 만든다. 친절/불편/훌륭 등 서로 다른 어휘를 사용하고 trace의 대상 event index까지 검증한다.

```python
def test_supported_negation_composition():
    from sentiment_engine.sentiment import analyze_sentiment
    plain = analyze_sentiment("친절하다", apply_modifiers=False)
    negated = analyze_sentiment("친절하지 않다")
    doubled = analyze_sentiment("친절하지 않은 것은 아니다")
    emphatic = analyze_sentiment("매우 친절하다")
    assert plain.score > 0
    assert negated.score == -plain.score
    assert doubled.score == plain.score
    assert doubled.matches[0].negation_count == 2
    assert emphatic.score == 1.5 * plain.score
```

- [ ] 수정어 off/on의 사건 목록은 동일하고 기여도만 달라짐을 검사한다. 사전 원자성이 다른 구성에서 off 결과를 단순 문자열 단어합으로 강제하지 않는다.
- [ ] 모든 공개 match 원문 일치, contribution 합계, 강조 부호 보존, 사건/연산자 단일 소유, 분리된 절에 추가한 부정의 비간섭을 검사한다. 형태소 모델이 문맥에 따라 결과를 바꿀 수 있으므로 구조적 불변식은 같은 내부 사건 구조 조건 아래 검증한다.
- [ ] 문장별 if/평가 ID/전체 문장 lookup을 금지한다. 일반 문법으로 표현 못 하는 상태 변화·반어·의향은 미지원으로 기록한다.
- [ ] 기존 테스트에서 옛 거리 타이브레이크나 잘못된 활용형을 정답으로 요구하면 이유와 대체 의미 계약을 기록한다. 정상 공개 API 계약은 보존한다.
- [ ] `python -m pytest tests/sentiment -q` 실행. 새 미등록 외부 문장을 맞히도록 테스트 기대값을 실제 출력에 맞춰 바꾸지 않는다.

### B4 — 개발 비교·후보 동결·통합

**Files:** engine-development 문서, README, CLI 진단, 통합 테스트, 후보 manifest.
**Consumes:** A development, baseline, M/가능하면 K. **Produces:** A5에 넘길 적격 후보 스냅샷 최대 2개.

- [ ] development 전체에서 baseline/M의 켬/끔을 비교한다. K가 있으면 같은 분석기·문법으로 M/K를 비교한다. 전체 개선을 형태소 한 요소의 인과 효과라고 주장하지 않는다.
- [ ] 같은 compiled 사전·사건 목록에서 수정어 on/off 차이를 측정한다. 구조나 자원을 동시에 바꾼 실험은 별도 복합 변경으로 표시한다.
- [ ] 개발 오류를 형태소·사전·극성·연결·혼합·문맥·별점 잡음으로 집계한다. 반복된 언어 오류에만 공통 수정하고 단일 평가 문장 패치를 넣지 않는다.
- [ ] `python -m pytest -q`, 기존 `--text/--evaluate all`, JSON/text 필드·종료 코드, JVM/자원 부재 진단을 검증한다. A1 정보 추출 결과와 대조한다.
- [ ] Python 3.10/현재 Python의 깨끗한 환경에서 설치·분석을 재현한다. 실제 장비에서 cold start, warm p50/p95, peak RSS를 개발 입력 분포와 함께 측정한다. A worker timeout 안에서 동작하는지 확인한다.
- [ ] baseline/M/K 후보 정의·사전·compiled·model·JDK·lock·설정·프로토콜 해시를 A의 candidate manifest로 고정한다. selection에 올리기 전 모든 개발 수정을 끝낸다.
- [ ] A5~A7로 돌아가 선택·최종 평가를 수행한다. B4의 개발 지표를 최종 일반화 성능이라고 쓰지 않는다.

## 6. 판단 기준과 한계

성공은 활용형·부정 범위에 관한 명시적 계약과 재현성의 충족이다. 형태소 분석기를 썼다는 사실만으로 외부 80%를 보장하지 않는다. 공통 문법도 개발셋에 과적합할 수 있으므로 A 계획의 미노출 평가를 유지한다.

KNU 단어 채택 자체는 정상적인 외부 어휘 자원 사용이다. 반대로 출처 없는 AI 사전도 미션이 허용하는 직접 구축 사전일 수 있다. 두 경우 모두 독립적인 사람 검수가 있었는지, 점수가 어떤 근거인지 정확히 표기한다. 별도의 수업 AI 사용 규정이 있다면 직접 구축 허용 문구만으로 AI 사용 허가까지 단정하지 않는다.

개선 후보의 전면 재설계가 기술적으로 막히거나 실익이 없으면 현 baseline의 미노출 결과와 한계를 보고하는 것도 완결된 A 평가 결과다. 분석기를 몰래 바꾸거나 final에 맞춰 규칙을 덧붙이지 않는다.

## 7. 조사 출처

- **[T1]** [KoNLPy v0.6.0 KOMORAN wrapper](https://raw.githubusercontent.com/konlpy/konlpy/v0.6.0/konlpy/tag/_komoran.py): jki 초기화, 줄 단위 처리, Token List 접근.
- **[T2]** [KoNLPy v0.6.0 Java 배포물](https://github.com/konlpy/konlpy/tree/v0.6.0/konlpy/java): komoran-3.0.jar. master/최신 문서와 버전 구별.
- **[T3]** [KOMORAN 3.3.9 Token List 문서](https://docs.komoran.kr/api/kr/co/shineware/nlp/komoran/model/KomoranResult.html): 형태소/POS/시작/끝 위치. 번들 3.0의 동작 검증 대체물이 아님.
- **[T4]** [KoNLPy 설치 문서](https://konlpy.org/en/latest/install/): JVM 의존성. 현대 Python/JDK 조합은 B1 실행 검증 대상.
- **[T5]** [KNU 저장소 설명](https://github.com/park1200656/KnuSentiLex): 단어·어구·문형·축약어·이모티콘과 구축 방법.
- **[T6]** [KNU ReadMe.txt](https://github.com/park1200656/KnuSentiLex/blob/master/ReadMe.txt): 사전 자원 설명. 조사에서 명시적 이용/배포 허가를 확인하지 못한 상태.

모든 체크박스는 미실행 상태다. 이 문서만으로 특정 API 조합의 동작이나 새 엔진 성능을 검증했다고 주장하지 않는다.
