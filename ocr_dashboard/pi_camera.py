"""Bounded CSI camera snapshots through Raspberry Pi's supported rpicam CLI."""
import subprocess
import threading
from flask import Blueprint, Response, jsonify, request


def create_pi_camera_blueprint(app):
    api = Blueprint('pi_camera', __name__, url_prefix='/api/camera')
    lock = threading.Lock()

    @api.post('/frame')
    def frame():
        if app.config['CAMERA_BACKEND'] != 'picamera':
            return jsonify(error='Pi 카메라 모드가 아닙니다.'), 404
        if request.host.split(':')[0] not in ('localhost','127.0.0.1') or request.headers.get('Origin') != request.host_url.rstrip('/'):
            return jsonify(error='현장 기기의 대시보드에서 카메라를 시작해 주세요.'), 403
        if not lock.acquire(blocking=False):
            return jsonify(error='카메라가 촬영 중입니다. 잠시 후 다시 시작해 주세요.'), 409
        try:
            result = subprocess.run(['rpicam-still','--nopreview','--timeout','1200','--width','1920','--height','1080','--encoding','jpg','--output','-'],capture_output=True,timeout=10,check=True)
            if not result.stdout.startswith(b'\xff\xd8') or len(result.stdout) > 16*1024*1024:
                return jsonify(error='카메라 이미지가 올바르지 않습니다.'), 503
            return Response(result.stdout, mimetype='image/jpeg')
        except (OSError,subprocess.SubprocessError):
            return jsonify(error='카메라 모듈 연결을 확인해 주세요. rpicam-hello --list-cameras 로 점검할 수 있습니다.'),503
        finally:
            lock.release()
    return api
