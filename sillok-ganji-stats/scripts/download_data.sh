#!/usr/bin/env bash
# 공공데이터포털 dataset 15053647 (조선왕조실록 원문 XML, 태조~철종) 다운로드·해제.
# 라이선스: 이용허락범위 제한 없음. 크롤링이 아니라 벌크 파일 배포본을 받는다.
#
# 사용법:
#   SILLOK_BULK_URL="<포털에서 받은 zip URL>" scripts/download_data.sh
#   scripts/download_data.sh <zip URL> [<zip URL2> ...]
#   scripts/download_data.sh --zip /path/to/staged.zip     # 네트워크 건너뛰기
#
# 포털 파일데이터는 데이터셋 페이지를 거쳐야 실제 다운로드 URL이 나온다:
#   태조~철종 : https://www.data.go.kr/data/15053647/fileData.do
#   고종·순종 : https://www.data.go.kr/data/15053646/fileData.do
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
DATA_DIR="${DATA_DIR:-$ROOT/data}"
mkdir -p "$DATA_DIR"

# 세션 프록시 CA (있으면 curl에 전달)
CA_ARG=()
if [[ -f /root/.ccr/ca-bundle.crt ]]; then
  CA_ARG=(--cacert /root/.ccr/ca-bundle.crt)
fi

extract() {  # <zip>
  local zip="$1"
  echo "unzip $zip -> $DATA_DIR/"
  unzip -o -q "$zip" -d "$DATA_DIR"
  echo "xml files now staged: $(find "$DATA_DIR" -name '*.xml' | wc -l)"
}

# --zip 모드: 이미 받아둔 zip 해제
if [[ "${1:-}" == "--zip" ]]; then
  [[ -n "${2:-}" ]] || { echo "usage: $0 --zip <path>" >&2; exit 2; }
  extract "$2"
  exit 0
fi

# URL 수집: 인자 우선, 없으면 SILLOK_BULK_URL
urls=("$@")
if [[ ${#urls[@]} -eq 0 ]]; then
  if [[ -n "${SILLOK_BULK_URL:-}" ]]; then
    # shellcheck disable=SC2206
    urls=(${SILLOK_BULK_URL//,/ })
  fi
fi
if [[ ${#urls[@]} -eq 0 ]]; then
  cat >&2 <<EOF
다운로드 URL이 없습니다. 아래 중 하나로 지정하세요:
  export SILLOK_BULK_URL="https://.../sillok_raw_xml.zip"
  $0 "https://.../sillok_raw_xml.zip"
  $0 --zip data/sillok_raw_xml.zip
데이터셋 페이지: https://www.data.go.kr/data/15053647/fileData.do
EOF
  exit 2
fi

i=0
for url in "${urls[@]}"; do
  out="$DATA_DIR/sillok_raw_xml_${i}.zip"
  echo "downloading [$((i+1))/${#urls[@]}] $url"
  for try in 1 2 3 4; do
    if curl -fSL "${CA_ARG[@]}" --retry 0 -o "$out" "$url"; then
      break
    fi
    wait=$((2 ** try))
    echo "  failed (attempt $try); retry in ${wait}s" >&2
    sleep "$wait"
    [[ $try -eq 4 ]] && { echo "  giving up on $url" >&2; exit 1; }
  done
  extract "$out"
  i=$((i+1))
done

echo "done. next: python src/sillok_pipeline.py probe --dir data"
