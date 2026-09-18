# 책에 맞는 빛 — Raspberry Pi 5

카메라로 책 페이지를 주기적으로 촬영하고, 분류 결과에 따라 Philips Hue와 WiZ 조명을 조절하는 현장용 대시보드입니다.

## 가장 쉬운 설치

Raspberry Pi OS 64-bit Desktop에서, 카메라 모듈을 연결하고 같은 Wi-Fi에 조명을 연결한 다음 터미널에서 실행하세요.

```bash
sudo apt-get update
sudo apt-get install -y git
git clone https://github.com/ssoosajang/reading-light-raspberrypi.git OCR-project
cd OCR-project
bash scripts/setup-raspberrypi.sh
bash scripts/start-raspberrypi.sh
```

Pi의 Chromium에서 http://127.0.0.1:5050 을 엽니다. 실행 터미널은 열어두세요.

다음부터는 `cd ~/OCR-project` 후 `bash scripts/start-raspberrypi.sh`만 실행합니다. clone은 홈 폴더에서 실행하는 기준입니다.

## 조명 연결

설정에서 Hue와 WiZ를 각각 선택하여 연결합니다. Hue는 브리지 물리 버튼으로 승인하고, WiZ는 앱의 보안 설정에서 로컬 통신과 모든 컨트롤 허용을 선택합니다. 각각 연결 검증을 마치면 ‘Hue + WiZ 함께’를 선택하고 자동 연동을 켭니다. 조명은 먼저 켜두세요. 함께 모드는 각 종류에 연결 가능한 조명 한 개씩을 지원합니다.

| 분류 | 색온도 |
|---|---|
| 수학·계산 | 6500 K, 차가운 흰빛 |
| 영어·독서 | 4500 K |
| 그림·미술 | 3000 K, 따뜻한 흰빛 |

RGB 순수 파랑을 사용하지 않습니다. 자동 적용은 각 조명의 기존 밝기를 유지합니다. 과목별 보편적인 최적 조명을 보장하는 설정은 아닙니다.

## 카메라 및 실행 범위

- 카메라 확인: `rpicam-hello --list-cameras`
- Pi 카메라 모듈은 rpicam-still로 주기적 촬영하며, 화면은 최근 사진을 갱신합니다.
- Tesseract 한국어/영어 OCR을 사용하고, 같은 유형을 두 번 확인한 뒤 조명을 변경합니다.
- 실제 Pi5 하드웨어에서 설치·카메라·분류 성능은 아직 검증하지 않았습니다. Mac 실물 조명 제어 확인과 Pi 실기기 검증은 별개입니다.
- 인증정보와 이미지, Mac 전용 바이너리는 배포하지 않습니다. 연결은 Pi에서 새로 설정합니다.

[상세 설치 안내](docs/RASPBERRY_PI_SETUP.md) · [로그인 없는 현장 실행 페이지](https://tobis-reading-light.tobislab0809.chatgpt.site)

현장 실행 페이지는 해당 기기의 localhost 대시보드를 여는 링크입니다. 다른 컴퓨터에서 Pi를 원격 제어하는 기능은 없습니다.


## 인식 미세조정 업데이트 (2026-09-18)

USB 웹캠으로 사용하는 경우, 기존 서버를 Ctrl+C로 종료한 후:

```bash
cd ~/OCR-project
git pull --ff-only
bash scripts/start-raspberrypi.sh usb
```

카메라 모듈은 마지막 인자를 `module`로 바꾸세요. Chromium에서 새로고침하고 설정 → 인식 미세조정을 확인하세요. 회색조/2600px가 Tesseract의 새 기본값입니다. 글 배치(자동/한 문단/흩어진 글)와 해상도(2000/2600/3200px)를 비교하고, 최근 촬영 원본 저장 및 인식한 글 확인으로 원인을 점검할 수 있습니다. 해상도 변경 후 중지→시작하세요. 실제 Pi에서 인식률 향상은 아직 확인하지 않았습니다.
