#!/usr/bin/env bash
set -euo pipefail
project_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$project_dir"
if [[ ! -x .venv-pi/bin/python ]]; then
  echo '먼저 bash scripts/setup-raspberrypi.sh 를 실행해 주세요.' >&2
  exit 1
fi
export OCR_ENGINE=tesseract
export CAMERA_BACKEND=picamera
exec .venv-pi/bin/python -m ocr_dashboard
