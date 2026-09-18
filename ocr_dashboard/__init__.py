"""Local OCR dashboard HTTP interface."""
import threading
import os
from pathlib import Path

import pytesseract
from flask import Flask, jsonify, render_template, request
from .pipeline import process
from .vision_ocr import BINARY
from .lighting_api import create_lighting_blueprint
from .hue import create_hue_blueprint
from .wiz import create_wiz_blueprint
from .pi_camera import create_pi_camera_blueprint


def create_app(test_config=None):
    app = Flask(__name__)
    app.config.update(MAX_CONTENT_LENGTH=16 * 1024 * 1024, CAMERA_BACKEND=os.environ.get("CAMERA_BACKEND", "browser"),
                      OCR_ENGINE=os.environ.get("OCR_ENGINE", "vision" if BINARY.exists() else "tesseract"),
                      LIGHTING_SETTINGS_PATH=Path(app.instance_path) / 'lighting.json')
    if test_config:
        app.config.update(test_config)
    app.register_blueprint(create_lighting_blueprint())
    app.register_blueprint(create_hue_blueprint(app))
    app.register_blueprint(create_wiz_blueprint(app))
    app.register_blueprint(create_pi_camera_blueprint(app))
    processing_lock = threading.Lock()

    @app.after_request
    def headers(response):
        response.headers['Cache-Control'] = 'no-store'
        response.headers['X-Content-Type-Options'] = 'nosniff'
        return response

    @app.get('/')
    def index():
        return render_template('index.html', camera_backend=app.config['CAMERA_BACKEND'], wiz_saved=(Path(app.instance_path) / 'wiz.json').exists(), both_saved=all((Path(app.instance_path) / name).exists() for name in ('wiz.json', 'hue.json')))

    @app.get('/api/health')
    def health():
        if app.config['OCR_ENGINE'] == 'vision':
            ready = BINARY.is_file() and os.access(BINARY, os.X_OK)
            return jsonify(ready=ready, languages=['kor', 'eng'], engine='vision'), 200 if ready else 503
        try:
            languages = pytesseract.get_languages(config='')
            ready = all(lang in languages for lang in ('kor', 'eng'))
            return jsonify(ready=ready, languages=[x for x in ('kor', 'eng') if x in languages]), 200 if ready else 503
        except (pytesseract.TesseractNotFoundError, pytesseract.TesseractError, OSError):
            return jsonify(ready=False, error='Tesseract 설치를 확인해 주세요.'), 503

    @app.errorhandler(413)
    def too_large(_error):
        return jsonify(error='파일은 16 MB 이하로 선택해 주세요.'), 413

    @app.post('/api/ocr')
    def ocr():
        upload = request.files.get('image')
        if upload is None:
            return jsonify(error='이미지 파일을 선택해 주세요.'), 400
        mode = request.form.get('mode', 'threshold')
        language = request.form.get('language', 'kor+eng')
        if mode not in ('threshold', 'gray') or language not in ('kor+eng', 'eng', 'kor'):
            return jsonify(error='지원하지 않는 처리 설정입니다.'), 400
        if not processing_lock.acquire(blocking=False):
            return jsonify(error='다른 이미지를 처리 중입니다. 잠시 후 다시 시도해 주세요.'), 429
        try:
            result = process(upload.read(), rectify=request.form.get('rectify', 'true') == 'true',
                             mode=mode, language=language, engine=app.config["OCR_ENGINE"])
            return jsonify(result)
        except ValueError as exc:
            return jsonify(error=str(exc)), 400
        except pytesseract.TesseractNotFoundError:
            return jsonify(error='Tesseract를 설치한 뒤 서버를 다시 시작해 주세요.'), 503
        except pytesseract.TesseractError:
            return jsonify(error='OCR 실행에 실패했습니다. Tesseract와 언어 데이터를 확인해 주세요.'), 503
        except RuntimeError:
            return jsonify(error='OCR 제한 시간 30초를 초과했습니다. 더 작은 이미지로 시도해 주세요.'), 504
        finally:
            processing_lock.release()

    return app
