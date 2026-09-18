# 라즈베리파이 현장 설치

## 권장 구성과 현재 지원 범위

Raspberry Pi 5 + Raspberry Pi OS 64-bit Desktop, 모니터·키보드, Chromium, CSI 카메라 모듈로 시작합니다. Pi의 rpicam-still로 주기적으로 촬영하고 Pi 자체에서 Tesseract로 OCR을 처리합니다. Mac의 Apple Vision과 인식 정확도·속도가 같다고 보장하지 않습니다. 이 설치 스크립트는 작성·문법 확인했으나 Pi 실기기에서는 아직 검증하지 않았습니다.

CSI 카메라 모듈용 촬영 경로를 추가했습니다. 시작 스크립트가 이 모드를 선택합니다. 화면은 실시간 동영상 대신 최근 촬영 이미지를 갱신합니다. 시작 전에 `rpicam-hello --list-cameras`로 카메라가 나타나는지 확인하세요. 전원을 끈 상태에서 Pi 5에 맞는 카메라 케이블로 연결합니다. 공식 문서: https://www.raspberrypi.com/documentation/computers/camera_software.html

## 최초 설치

1. Raspberry Pi OS Desktop을 준비하고 Pi와 Hue/WiZ를 같은 공유기에 연결합니다.
2. 이 프로젝트의 `ocr_dashboard/`, `scripts/`를 포함한 소스 폴더를 Pi의 `~/OCR-project`로 복사합니다. Mac의 `.venv`, `node_modules`, `.git`, `instance`는 복사하지 않아도 됩니다. Hue 인증정보는 새 Pi에서 다시 연결할 수 있습니다.
3. Pi 터미널에서 실행합니다.

```bash
cd ~/OCR-project
bash scripts/setup-raspberrypi.sh
bash scripts/start-raspberrypi.sh
```

시작 명령을 실행한 터미널은 열어둡니다. 종료는 Ctrl+C입니다.

## 실행

Pi의 Chromium에서 http://127.0.0.1:5050 을 엽니다. GPT Sites 실행 페이지의 버튼도 같은 주소를 엽니다. Mac/휴대폰에서 그 버튼을 누르면 Pi로 연결되지 않습니다.

설정 → WiZ 선택 → 전구 검색 → 이 전구 연결 → 연결 검증 → 자동 연동 켜기. WiZ 앱의 보안 설정에서 로컬 허용과 모든 컨트롤 허용을 사용합니다. Hue는 개별 선택 후 검색, 물리 버튼 승인, 연결 검증 순서입니다. 둘 다 연결한 다음 Hue + WiZ 함께를 선택합니다. 각 종류 한 개씩 연결 가능한 구성이 현재 함께 모드의 조건입니다.

시작 → 카메라 허용 → 책을 비춥니다. 같은 유형을 두 번 확인하면 수학6500/독서4500/미술3000 K를 적용합니다. 자동 변경은 기존 밝기를 유지하므로 조명은 먼저 켜 둡니다.

## 다음 실행

```bash
cd ~/OCR-project
bash scripts/start-raspberrypi.sh
```

매번 설치할 필요는 없습니다. 로그인 없이 여는 GPT Sites 페이지는 실행 안내용이며 OCR 서버 자체를 클라우드에서 실행하지 않습니다.
