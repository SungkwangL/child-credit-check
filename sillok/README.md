# 조선왕조실록 일진(일간지) 전수 추출 & 60간지 통계 검정

실록 원문에서 각 기사의 **일진(일간지, day pillar)** 을 전수 추출하고, 사건유형별로
60간지 / 천간(10) / 지지(12) 관측분포가 균등분포와 다른지 **카이제곱 적합도 검정**
(Bonferroni 보정)으로 확인하는 파이프라인.

전체 설계 근거·리서치·통계 해석 지침은 [`DESIGN.md`](DESIGN.md) 참조.

## 핵심 원칙

1. **크롤링하지 않는다.** 공공데이터포털 dataset 15053647(태조~철종, "이용허락범위 제한 없음")
   벌크 XML을 받아 파싱한다. `sillok.history.go.kr`는 robots.txt 전면차단 이력 +
   `/id/` 자동접근 차단. 크롤러(`crawler.py`)는 개별 기사 대조용 폴백일 뿐이다.
2. **간지는 원본에 이미 태그돼 있다.** `<dateOccured type="간지">` = 일진. "추출"이 본질이고
   JDN 산술 + `korean_lunar_calendar`로 **교차검증만** 한다.
3. **프로브 게이트가 절대원칙.** `probe`로 스키마(level4 id 자리수·간지 태그·왕대코드)를
   실측 확정하기 전에는 전수 파싱을 돌리지 않는다. `parse` 커맨드는 게이트 통과 전 실행을 거부한다.

## 파이프라인 단계

| 단계 | 커맨드 | 하는 일 |
|------|--------|---------|
| 1 다운로드 | `python -m sillok_pipeline download` | 벌크 ZIP 다운로드·해제 → `data/` |
| 2 프로브(게이트) | `python -m sillok_pipeline probe --dir data` | 스키마 실측 → `progress/schema_probe.json`, `gate_passed` 판정 |
| 3 파싱 | `python -m sillok_pipeline parse --dir data` | 전수 파싱 + 사건분류 → `sillok.db` (게이트 필요) |
| 4 검증 | `python -m sillok_pipeline verify` | JDN·라이브러리·원문 3자 일치 게이트 적용 |
| 5 통계 | `python -m sillok_pipeline stats` | 사건유형×층위 카이제곱, Bonferroni 보정 |
| — | `python -m sillok_pipeline selfcheck` | 간지 앵커 캘리브레이션 재확인(네트워크 불필요) |

## 설치

```bash
pip install -r requirements.txt
```

## 다운로드 소스

- 태조~철종: 공공데이터포털 dataset **15053647** — https://www.data.go.kr/data/15053647/fileData.do
- 고종·순종: dataset **15053646** — https://www.data.go.kr/data/15053646/fileData.do

포털에서 받은 실제 다운로드 URL을 `SILLOK_BULK_URL` 환경변수(공백/쉼표 구분)나 `--url`로
넘긴다. 이미 받아둔 ZIP이 있으면 `--zip <경로>`로 네트워크를 건너뛴다.

```bash
export SILLOK_BULK_URL="https://.../sillok_raw_xml.zip"
python -m sillok_pipeline download            # 또는 --zip data/sillok_raw_xml.zip
python -m sillok_pipeline probe --dir data    # 게이트
python -m sillok_pipeline parse  --dir data   # 게이트 통과 시에만
python -m sillok_pipeline verify
python -m sillok_pipeline stats
```

> **원본 XML은 커밋하지 않는다** (`.gitignore`: `data/ out/ *.db *.zip`). 재현성은 다운로드
> 스크립트로 확보한다.

## 현재 상태 / 빌드 환경 주의

이 저장소가 만들어진 빌드 환경에서는 조직 egress 정책이 `www.data.go.kr`·
`sillok.history.go.kr`을 차단(403)하여 **1단계 다운로드를 실행할 수 없었다.** 따라서
프로브 게이트는 아직 **미통과**이며 `progress/schema_probe.json`은 플레이스홀더다.
네트워크가 열린 환경에서 위 순서대로 `download` → `probe`를 실행하면 게이트가 통과되고
실측값으로 갱신된다.

네트워크가 필요 없는 부분(간지 산술, 앵커 캘리브레이션, 파서 구조, 사건분류)은
`pytest`로 검증돼 있다:

```bash
pytest -q          # 16 passed
```

## 코드에 남은 "추측"(프로브로 확정할 것)

- `parse.py` `_LV4_ID_RE` — level4 id 자리수(설계서 예시로 1차 교정, 실데이터로 재확인)
- `constants.py` `KING_CODES` — 중복 실록(선조수정/현종개수/숙종보궐/경종수정) 왕대코드 순서
- `crawler.py` `parse_article_html` — 웹 페이지 DOM 셀렉터
