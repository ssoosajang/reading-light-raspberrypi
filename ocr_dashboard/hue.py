"""Local Hue bridge integration: HTTPS with trust-on-first-use certificate pinning.

Only discovery/config is read before trust; the chosen certificate is pinned before
sending a pairing request or credentials. Keys never appear in API responses/logs.
"""
import colorsys
import hashlib
import http.client
import ipaddress
import json
import os
from pathlib import Path
import re
import ssl
import tempfile
import threading
from urllib.request import urlopen
from urllib.parse import urlsplit
from flask import Blueprint, jsonify, request
from .lighting import validate_profile


class HueError(Exception):
    def __init__(self, message, status=503):
        super().__init__(message)
        self.status = status


def private_ipv4(value):
    address = ipaddress.IPv4Address(value)
    if not any(address in ipaddress.IPv4Network(net) for net in ('10.0.0.0/8', '172.16.0.0/12', '192.168.0.0/16')):
        raise ValueError('공유기 내부의 IPv4 주소만 사용할 수 있습니다.')
    return str(address)


class HueTransport:
    def request(self, bridge, method, path, payload=None):
        ip = private_ipv4(bridge['ip'])
        # A saved SHA-256 pin replaces public-CA validation for the bridge certificate.
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        context.check_hostname = False
        context.verify_mode = ssl.CERT_NONE
        conn = http.client.HTTPSConnection(ip, timeout=5, context=context)
        try:
            conn.connect()
            fingerprint = hashlib.sha256(conn.sock.getpeercert(binary_form=True)).hexdigest()
            if bridge.get('fingerprint') != fingerprint:
                raise HueError('브릿지 인증서가 변경됐습니다. 연결을 다시 확인해 주세요.')
            conn.request(method, path, body=None if payload is None else json.dumps(payload),
                         headers={'Content-Type': 'application/json'})
            response = conn.getresponse()
            raw = response.read(1024 * 1024 + 1)
            if response.status != 200 or len(raw) > 1024 * 1024:
                raise HueError('브릿지 응답을 확인하지 못했습니다.')
            return json.loads(raw)
        finally:
            conn.close()

    def discover(self):
        with urlopen('https://discovery.meethue.com', timeout=5) as response:
            candidates = json.loads(response.read(65536))
        if not isinstance(candidates, list):
            raise HueError('검색 응답을 확인하지 못했습니다.')
        result = []
        for candidate in candidates[:4]:
            ip = private_ipv4(candidate['internalipaddress'])
            bridge_id = candidate['id'].lower()
            if not re.fullmatch(r'[a-f0-9]{16}', bridge_id):
                continue
            context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
            context.check_hostname = False
            context.verify_mode = ssl.CERT_NONE
            conn = http.client.HTTPSConnection(ip, timeout=3, context=context)
            try:
                conn.connect()
                fingerprint = hashlib.sha256(conn.sock.getpeercert(binary_form=True)).hexdigest()
            finally:
                conn.close()
            bridge = {'id': bridge_id, 'ip': ip, 'fingerprint': fingerprint}
            config = self.request(bridge, 'GET', '/api/config')
            if not isinstance(config, dict) or config.get('bridgeid', '').lower() != bridge_id:
                continue
            result.append({**bridge, 'name': str(config.get('name', 'Hue Bridge'))[:100]})
        return result


def save_credentials(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(dir=path.parent, prefix='.hue-')
    try:
        with os.fdopen(fd, 'w') as stream:
            json.dump(data, stream)
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def create_hue_blueprint(app):
    api = Blueprint('hue', __name__, url_prefix='/api/hue')
    transport = app.config.get('HUE_TRANSPORT') or HueTransport()
    path = Path(app.config.get('HUE_CREDENTIALS_PATH', Path(app.instance_path) / 'hue.json'))
    lock = threading.Lock()
    candidates = {}
    verified = set()

    def credentials():
        try:
            data = json.loads(path.read_text())
            private_ipv4(data['ip'])
            if not re.fullmatch(r'[a-zA-Z0-9_-]{8,128}', data['username']):
                raise ValueError()
            if not re.fullmatch(r'[a-f0-9]{64}', data['fingerprint']):
                raise ValueError()
            return data
        except FileNotFoundError:
            raise HueError('먼저 브릿지를 검색하고 연결해 주세요.', 409)
        except (ValueError, KeyError, TypeError):
            raise HueError('저장된 연결정보를 읽지 못했습니다. 다시 연결해 주세요.')

    def body(keys):
        data = request.get_json(silent=True)
        if not isinstance(data, dict) or set(data) != set(keys):
            raise ValueError('입력 항목을 확인해 주세요.')
        return data

    @api.before_request
    def local_only():
        if urlsplit(request.host_url).hostname not in ('localhost', '127.0.0.1', '::1'):
            return jsonify(error='이 Mac의 대시보드에서 연결해 주세요.'), 403
        if request.method != 'GET' and (request.headers.get('Origin') != request.host_url.rstrip('/') or not request.is_json):
            return jsonify(error='대시보드에서 요청을 다시 시작해 주세요.'), 403

    @api.errorhandler(HueError)
    def hue_error(error):
        return jsonify(error=str(error), applied=False), error.status

    @api.errorhandler(ValueError)
    def invalid(_error):
        return jsonify(error='입력값 또는 조명의 지원 범위를 확인해 주세요.', applied=False), 400

    @api.errorhandler(OSError)
    @api.errorhandler(http.client.HTTPException)
    @api.errorhandler(KeyError)
    @api.errorhandler(TypeError)
    def unavailable(_error):
        return jsonify(error='브릿지 통신 또는 연결정보 저장에 실패했습니다. 연결을 확인하고 다시 시도해 주세요.', applied=False), 503

    @api.get('/status')
    def status():
        return jsonify(paired=path.exists(), verified=bool(verified), applied=False)

    @api.post('/discover')
    def discover():
        body([])
        with lock:
            found = transport.discover()
            candidates.clear()
            candidates.update({b['id']: b for b in found})
            return jsonify(bridges=[{k: b[k] for k in ('id', 'ip', 'name')} for b in found])

    @api.post('/pair')
    def pair():
        data = body(['bridge_id'])
        with lock:
            if not isinstance(data['bridge_id'], str) or data['bridge_id'] not in candidates:
                raise ValueError()
            bridge = candidates[data['bridge_id']]
            verified.clear()
            response = transport.request(bridge, 'POST', '/api', {'devicetype': 'ocr_dashboard#mac'})
            if not isinstance(response, list) or not response:
                raise HueError('브릿지 인증 응답을 확인하지 못했습니다.')
            if any(item.get('error', {}).get('type') == 101 for item in response):
                raise HueError('브릿지 가운데 버튼을 누른 뒤 연결 승인 확인을 눌러 주세요.', 409)
            username = response[0].get('success', {}).get('username')
            if not isinstance(username, str) or not re.fullmatch(r'[a-zA-Z0-9_-]{8,128}', username):
                raise HueError('브릿지 인증에 실패했습니다.')
            save_credentials(path, {**bridge, 'username': username})
            return jsonify(paired=True, applied=False, message='연결 승인 완료. 연결 검증으로 조명 목록을 확인하세요.')

    @api.post('/verify')
    def verify():
        body([])
        with lock:
            verified.clear()
            config = credentials()
            response = transport.request(config, 'GET', '/api/' + config['username'] + '/lights')
            if not isinstance(response, dict):
                raise HueError('조명 목록을 읽지 못했습니다. 브릿지 연결 승인을 확인해 주세요.')
            lights = []
            for identifier, light in response.items():
                if not re.fullmatch(r'[0-9]+', identifier) or not isinstance(light, dict):
                    continue
                state = light.get('state', {})
                lights.append({'id': identifier, 'name': str(light.get('name', '조명'))[:100],
                               'reachable': state.get('reachable') is True, 'on': state.get('on') is True})
                if state.get('reachable') is True:
                    verified.add(identifier)
            return jsonify(lights=lights, applied=False, message='조명 상태를 읽었습니다. 실제 조명은 변경하지 않았습니다.')

    @api.post('/apply')
    def apply():
        data = request.get_json(silent=True)
        if not isinstance(data, dict) or set(data) not in ({'light_id','profile','confirmed'}, {'light_id','profile','confirmed','preserve_brightness'}):
            raise ValueError()
        preserve = data.get('preserve_brightness', False)
        if type(preserve) is not bool:
            raise ValueError()
        if data['confirmed'] is not True or not isinstance(data['light_id'], str):
            raise ValueError()
        profile = validate_profile(data['profile'])
        with lock:
            if not verified:
                raise HueError('먼저 연결 검증을 완료해 주세요.', 409)
            identifier = data['light_id']
            if identifier not in verified:
                raise ValueError()
            config = credentials()
            base = '/api/' + config['username'] + '/lights/' + identifier
            light = transport.request(config, 'GET', base)
            if not isinstance(light, dict) or light.get('state', {}).get('reachable') is not True:
                verified.clear()
                raise HueError('조명에 연결할 수 없습니다. 연결 검증을 다시 해 주세요.')
            state = light['state']
            command = {'on': profile['brightness_pct'] > 0}
            if command['on'] or preserve:
                command['bri'] = max(1, round(profile['brightness_pct'] * 254 / 100))
                if profile['mode'] == 'temperature':
                    ct = round(1000000 / profile['temperature_k'])
                    limits = light.get('capabilities', {}).get('control', {}).get('ct', {})
                    if 'ct' not in state or not limits.get('min', 153) <= ct <= limits.get('max', 500):
                        raise ValueError()
                    command['ct'] = ct
                else:
                    if not all(key in state for key in ('hue', 'sat')):
                        raise ValueError()
                    rgb = [int(profile['color'][i:i+2], 16) / 255 for i in (1, 3, 5)]
                    hue, saturation, _ = colorsys.rgb_to_hsv(*rgb)
                    command.update(hue=round(hue * 65535), sat=round(saturation * 254))
            if preserve:
                command.pop('on', None)
                command.pop('bri', None)
            response = transport.request(config, 'PUT', base + '/state', command)
            acknowledgments = {}
            if isinstance(response, list):
                for item in response:
                    if 'error' in item:
                        raise HueError('조명 명령 일부가 거절됐습니다. 실제 상태를 확인해 주세요.')
                    acknowledgments.update(item.get('success', {}))
            if any(acknowledgments.get(f'/lights/{identifier}/state/{key}') != value for key, value in command.items()):
                raise HueError('명령의 전체 성공 응답을 확인하지 못했습니다. 실제 상태를 확인해 주세요.')
            return jsonify(applied=True, message='브릿지가 명령을 승인했습니다. 실제 빛의 변화도 확인해 주세요.')

    return api
