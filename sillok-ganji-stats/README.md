# sillok-ganji-stats

조선왕조실록 원문에서 각 기사의 **일진(일간지, day pillar)** 을 전수 추출하고,
사건유형별로 60간지 / 천간(10) / 지지(12) 관측분포가 **균등분포와 다른지** 카이제곱
적합도 검정(Bonferroni 보정)으로 확인하는 파이프라인.

## 목적 · 가설

- **목적**: "실록에 기록된 특정 사건(붕어·졸기·처형·재변·즉위·반정)이 60일 주기의 일진과
  통계적으로 연관되는가?"를 재현 가능하게 검정한다.
- **귀무가설 H₀**: 각 사건유형의 일진 분포는 균등분포다(일진과 사건 발생은 독립).
- **대립가설 H₁**: 특정 천간/지지/간지에 사건이 균등 이상으로 몰린다.
- **주의**: 일진은 60일 주기로 순환하므로 표본이 크면 자연히 균등에 수렴한다. 유의한 편차가
  나와도 인과가 아니라 **기록·편찬 관행**(의례 집중, 재이 관측 보고 관행 등) 혼재변수를
  먼저 의심한다.

## 데이터 출처

- 태조~철종: 공공데이터포털 dataset **15053647** (실록 원문 XML, **이용허락범위 제한 없음**) —
  https://www.data.go.kr/data/15053647/fileData.do
- 고종·순종: dataset **15053646** — https://www.data.go.kr/data/15053646/fileData.do
- 간지는 원본 `<dateOccured type="간지">`에 이미 태그돼 있어 "추출"이 본질. `sillok.history.go.kr`
  크롤링은 robots.txt 전면차단 이력이 있어 사용하지 않는다(개별 대조용 폴백만).

## 디렉터리 구조

```
sillok-ganji-stats/
├── README.md
├── requirements.txt
├── scripts/download_data.sh   # 공공데이터포털 15053647 ZIP 다운로드·해제
├── src/sillok_pipeline.py     # 파서·분류·검증·통계 (단일 모듈)
├── data/                      # .gitignore 대상 (XML 원본, ZIP)
├── out/                       # .gitignore 대상 (sillok.db, 왕대별 db)
└── progress/                  # manifest.json, schema_probe.json (커밋 OK)
```

## 파이프라인 (각 단계 게이트)

| 단계 | 명령 |
|------|------|
| 1 다운로드 | `scripts/download_data.sh` (SILLOK_BULK_URL 또는 `--zip`) |
| 2 프로브(**게이트**) | `python src/sillok_pipeline.py probe --dir data` |
| 3 파싱 | `python src/sillok_pipeline.py parse --dir data` (게이트 통과 필요) |
| 4 검증 | `python src/sillok_pipeline.py verify` |
| 5 통계 | `python src/sillok_pipeline.py stats` |
| — | `python src/sillok_pipeline.py selfcheck` (앵커 재확인, 네트워크 불필요) |

> **절대원칙**: 프로브가 스키마(level4 id 자리수·간지 태그·왕대코드)를 실측 확정하기 전에는
> 전수 파싱을 돌리지 않는다. `parse`는 `progress/schema_probe.json`의 `gate_passed`가
> true가 아니면 실행을 거부한다(`--force`로만 우회).

## 설치 · 실행

```bash
pip install -r requirements.txt
export SILLOK_BULK_URL="https://.../sillok_raw_xml.zip"
scripts/download_data.sh
python src/sillok_pipeline.py probe --dir data     # 게이트
python src/sillok_pipeline.py parse  --dir data
python src/sillok_pipeline.py verify
python src/sillok_pipeline.py stats
```

## 사건 분류 (방법 A: 제목 기반)

국역 제목(`mainTitle`)만으로 분류한다. 한문 본문 매칭은 崩·薨·卒·誅 등이 문맥상
섞여 오탐이 심해(예: "…왕위에 오르다"가 붕어/처형으로 오분류) 쓰지 않는다. 어휘는
실제 제목으로 검증했다("졸기"/"왕위에 오르"/"지진" 등). 단, **재변은 '천둥/번개'(뇌진)가
빈번해 표본을 지배**하므로 재이(일식·지진·혜성) 신호를 보려면 천둥을 분리 검토할 것.

## 검증 · 통계 방법

- **일진 앵커**: 1900-01-01(양력) = 甲戌. JDN 산술과 `korean_lunar_calendar`의 독립 일주
  계산이 **둘 다** 원문 간지와 일치하는 기사(`verified=1`)만 통계에 넣는다.
- **검정**: 사건유형별 천간(df=9)·지지(df=11)·60간지(df=59)를 `scipy.stats.chisquare`로
  균등기대와 비교. Bonferroni 분모 = 사건유형수×층위수.
- **검정력**: 60간지는 셀당 기대도수<5면 `LOW_POWER`. N<50인 사건유형은 60간지 검정을
  생략하고 지지 층위·기술통계만 본다. 붕어처럼 N≈수십은 검정 제외, 사례표만 제시.

## 현재 상태

이 저장소를 만든 빌드 환경은 조직 egress 정책이 `www.data.go.kr`·`sillok.history.go.kr`을
차단(403)하여 **1단계 다운로드를 실행할 수 없었다.** 따라서 프로브 게이트는 **미통과**이고
`progress/schema_probe.json`은 플레이스홀더다. 네트워크가 열린 환경에서 위 순서대로 실행하면
게이트가 실측값으로 갱신된다.

네트워크가 필요 없는 부분은 검증돼 있다:

```bash
pytest -q       # 13 passed
python src/sillok_pipeline.py selfcheck
```

## 남은 "추측" (프로브로 확정)

- `_LV4_ID_RE` level4 id 자리수(설계서 예시로 1차 교정, 실데이터로 재확인)
- `KING_CODES` 중복 실록(선조수정/현종개수/숙종보궐/경종수정) 순서
- `parse_article_html` 웹 DOM 셀렉터
