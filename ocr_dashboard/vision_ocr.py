"""macOS on-device OCR. Images travel through stdin, never a temporary file."""
import json
import subprocess
from pathlib import Path
import cv2

BINARY = Path(__file__).resolve().parent.parent / 'instance' / 'vision-ocr'


def recognize(image, language):
    raw = cv2.imencode('.png', image)[1].tobytes()
    try:
        result = subprocess.run([str(BINARY), language], input=raw, capture_output=True, timeout=30, check=True)
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError('OCR timeout') from exc
    except (OSError, subprocess.CalledProcessError) as exc:
        raise ValueError('Mac 글자 인식 엔진을 실행하지 못했습니다.') from exc
    rows = json.loads(result.stdout)
    h,w = image.shape[:2]
    data = {key:[] for key in ('text','conf','left','top','width','height','block_num','par_num','line_num')}
    for i,row in enumerate(rows):
        values = (row['text'],row['confidence']*100,round(row['x']*w),round(row['y']*h),round(row['w']*w),round(row['h']*h),1,1,i+1)
        for key,value in zip(data,values): data[key].append(value)
    return data
