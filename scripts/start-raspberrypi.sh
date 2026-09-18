#!/usr/bin/env bash
set -euo pipefail
project_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$project_dir"
if [[ ! -x .venv-pi/bin/python ]]; then
  echo '먼저 bash scripts/setup-raspberrypi.sh 를 실행해 주세요.' >&2
  exit 1
fi
export OCR_ENGINE=tesseract
case "${1:-${CAMERA_BACKEND:-picamera}}" in
  usb|browser) export CAMERA_BACKEND=browser ;;
  module|picamera) export CAMERA_BACKEND=picamera ;;
  *) echo '사용법: bash scripts/start-raspberrypi.sh usb 또는 module' >&2; exit 1 ;;
esac
export OMP_THREAD_LIMIT=2
exec .venv-pi/bin/python -m ocr_dashboard
