#!/usr/bin/env bash
set -euo pipefail
project_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
if [[ "$(uname -s)" != Linux ]] || ! command -v apt-get >/dev/null; then
  echo 'Raspberry Pi OS에서 실행해 주세요.' >&2
  exit 1
fi
sudo apt-get update
sudo apt-get install -y rpicam-apps python3-venv python3-pip python3-opencv python3-pil tesseract-ocr tesseract-ocr-kor tesseract-ocr-eng
python3 -m venv --system-site-packages "$project_dir/.venv-pi"
"$project_dir/.venv-pi/bin/python" -m pip install 'Flask==3.1.3' 'pytesseract==0.3.13' 'waitress==3.0.2'
"$project_dir/.venv-pi/bin/python" -c 'import cv2, PIL, flask, pytesseract, waitress; assert {"kor", "eng"} <= set(pytesseract.get_languages()); print("OCR 의존성과 한국어·영어 확인 완료")'
printf '\n설치 완료. 실행: bash scripts/start-raspberrypi.sh\n'
