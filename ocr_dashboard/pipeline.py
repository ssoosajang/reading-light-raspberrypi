"""Bounded, in-memory image processing and local OCR."""
import base64
import io
import warnings

import cv2
import numpy as np
import pytesseract
from PIL import Image, ImageOps, UnidentifiedImageError
from .page_analysis import analyze_page

Image.MAX_IMAGE_PIXELS = 24_000_000


def decode_image(raw):
    try:
        with warnings.catch_warnings():
            warnings.simplefilter('error', Image.DecompressionBombWarning)
            with Image.open(io.BytesIO(raw)) as source:
                if source.width * source.height > Image.MAX_IMAGE_PIXELS:
                    raise ValueError('이미지는 2,400만 픽셀 이하로 선택해 주세요.')
                rgb = ImageOps.exif_transpose(source).convert('RGB')
                rgb.thumbnail((2000, 2000))
                return cv2.cvtColor(np.array(rgb), cv2.COLOR_RGB2BGR)
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError,
            Image.DecompressionBombWarning) as exc:
        raise ValueError('지원하지 않거나 너무 큰 이미지입니다. JPG 또는 PNG를 선택해 주세요.') from exc


def rectify_document(image):
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    edges = cv2.Canny(cv2.GaussianBlur(gray, (5, 5), 0), 50, 150)
    edges = cv2.morphologyEx(edges, cv2.MORPH_CLOSE, np.ones((5, 5), np.uint8))
    contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    area = image.shape[0] * image.shape[1]
    for contour in sorted(contours, key=cv2.contourArea, reverse=True)[:10]:
        if cv2.contourArea(contour) < area * 0.2:
            continue
        polygon = cv2.approxPolyDP(contour, 0.02 * cv2.arcLength(contour, True), True)
        if len(polygon) != 4 or not cv2.isContourConvex(polygon):
            continue
        points = polygon.reshape(4, 2).astype(np.float32)
        center = points.mean(axis=0)
        points = points[np.argsort(np.arctan2(points[:, 1] - center[1], points[:, 0] - center[0]))]
        points = np.roll(points, -np.argmin(points.sum(axis=1)), axis=0)
        tl, tr, br, bl = points
        width = round(max(np.linalg.norm(tr - tl), np.linalg.norm(br - bl)))
        height = round(max(np.linalg.norm(bl - tl), np.linalg.norm(br - tr)))
        if min(width, height) < 50:
            continue
        target = np.float32([[0, 0], [width - 1, 0], [width - 1, height - 1], [0, height - 1]])
        transform = cv2.getPerspectiveTransform(points, target)
        return cv2.warpPerspective(image, transform, (width, height)), True
    return image, False


def process(raw, *, rectify=True, mode='threshold', language='kor+eng', engine='tesseract'):
    image = decode_image(raw)
    detected = False
    if rectify:
        image, detected = rectify_document(image)
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    if mode == 'threshold':
        processed = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                                         cv2.THRESH_BINARY, 31, 11)
    else:
        processed = gray
    if engine == 'vision':
        from .vision_ocr import recognize
        data = recognize(image, language)
    else:
        data = pytesseract.image_to_data(processed, lang=language, config='--psm 3', timeout=30, output_type=pytesseract.Output.DICT)
    rows = {}
    for i, word in enumerate(data['text']):
        if word.strip():
            key = tuple(data[k][i] for k in ('block_num', 'par_num', 'line_num'))
            rows.setdefault(key, []).append(word)
    text = '\n'.join(' '.join(words) for words in rows.values())
    page_analysis = analyze_page(image, data)
    success, encoded = cv2.imencode('.png', processed)
    if not success:
        raise ValueError('처리 이미지를 생성하지 못했습니다.')
    return {'engine': engine, 'text': text.strip(), 'page_analysis': page_analysis, 'document_detected': detected,
            'rectify_requested': rectify, 'language': language, 'preprocessing': mode,
            'width': processed.shape[1], 'height': processed.shape[0],
            'preview': 'data:image/png;base64,' + base64.b64encode(encoded).decode('ascii')}
