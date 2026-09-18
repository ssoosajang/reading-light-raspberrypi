"""Local WiZ UDP control. Only discovered RFC1918 devices can be selected."""
import ipaddress
import json
import socket
import threading
import time
from pathlib import Path
from flask import Blueprint, jsonify, request
from .lighting import validate_profile


def private_ip(value):
    try:
        ip = ipaddress.IPv4Address(value)
        return any(ip in ipaddress.ip_network(net) for net in ('10.0.0.0/8', '172.16.0.0/12', '192.168.0.0/16'))
    except (ValueError, TypeError):
        return False


class WizTransport:
    def request(self, ip, method, params=None):
        if not private_ip(ip):
            raise ValueError('로컬 전구 주소만 사용할 수 있습니다.')
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.settimeout(2)
            for attempt in range(2):
                sock.sendto(json.dumps({'method': method, 'params': params or {}}).encode(), (ip, 38899))
                deadline = time.monotonic() + 2
                while time.monotonic() < deadline:
                    try:
                        raw, source = sock.recvfrom(8192)
                    except socket.timeout:
                        break
                    if source != (ip, 38899):
                        continue
                    try:
                        data = json.loads(raw)
                    except (ValueError, UnicodeError):
                        continue
                    if isinstance(data, dict) and data.get('method') == method:
                        if 'error' in data or not isinstance(data.get('result'), dict):
                            raise OSError('WiZ 명령이 거절됐습니다.')
                        return data['result']
            raise OSError('WiZ 응답이 없습니다. 전원·Wi-Fi·앱의 로컬 통신 설정을 확인해 주세요.')

    def discover(self):
        found = {}
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
            sock.settimeout(.3)
            sock.sendto(b'{"method":"getPilot","params":{}}', ('255.255.255.255', 38899))
            end = time.monotonic() + 3
            while time.monotonic() < end:
                try:
                    raw, (ip, port) = sock.recvfrom(8192)
                    data = json.loads(raw)
                    result = data.get('result', {})
                    if private_ip(ip) and port == 38899 and data.get('method') == 'getPilot' and isinstance(result, dict) and isinstance(result.get('mac'), str):
                        found[ip] = {'id': ip, 'ip': ip, 'mac': result['mac'], 'name': 'WiZ ' + result['mac'][-6:]}
                except (socket.timeout, ValueError, UnicodeError, AttributeError):
                    continue
        return list(found.values())


def create_wiz_blueprint(app):
    api = Blueprint('wiz', __name__, url_prefix='/api/wiz')
    transport = app.config.get('WIZ_TRANSPORT') or WizTransport()
    path = Path(app.config.get('WIZ_SETTINGS_PATH', Path(app.instance_path) / 'wiz.json'))
    candidates, verified = {}, {}
    lock = threading.Lock()

    def saved():
        try:
            value = json.loads(path.read_text())
            if isinstance(value, dict) and private_ip(value.get('ip')) and isinstance(value.get('mac'), str):
                return value
        except (OSError, ValueError):
            pass
        return None

    @api.before_request
    def local_only():
        if request.host.split(':')[0] not in ('localhost', '127.0.0.1'):
            return jsonify(error='이 Mac에서만 연결할 수 있습니다.'), 403
        if request.method != 'GET' and (request.headers.get('Origin') != request.host_url.rstrip('/') or not request.is_json):
            return jsonify(error='같은 대시보드에서 요청해 주세요.'), 403

    @api.errorhandler(ValueError)
    def invalid(error):
        return jsonify(error=str(error) or '잘못된 조명 설정입니다.'), 400

    @api.errorhandler(OSError)
    def unavailable(error):
        return jsonify(error='WiZ 연결을 확인하지 못했습니다. 전원과 같은 Wi-Fi 연결, WiZ 앱의 로컬 통신 설정을 확인해 주세요.'), 503

    @api.get('/status')
    def status():
        return jsonify(paired=saved() is not None)

    @api.post('/discover')
    def discover():
        with lock:
            lights = transport.discover()
            candidates.clear()
            candidates.update({light['id']: light for light in lights})
            return jsonify(bridges=lights)

    @api.post('/pair')
    def select():
        body = request.get_json(silent=True)
        if not isinstance(body, dict) or set(body) != {'bridge_id'} or not isinstance(body['bridge_id'], str):
            raise ValueError('검색한 전구를 선택해 주세요.')
        with lock:
            light = candidates.get(body['bridge_id'])
            if light is None:
                raise ValueError('먼저 WiZ 전구를 검색해 주세요.')
            state = transport.request(light['ip'], 'getPilot')
            if state.get('mac') != light['mac']:
                raise ValueError('전구 식별 정보가 바뀌었습니다. 다시 검색해 주세요.')
            path.parent.mkdir(parents=True, exist_ok=True)
            temporary = path.with_suffix('.tmp')
            temporary.write_text(json.dumps(light))
            temporary.replace(path)
            verified.clear()
            return jsonify(message='WiZ 전구 연결을 저장했습니다.')

    @api.post('/verify')
    def verify():
        with lock:
            verified.clear()
            light = saved()
            if light is None:
                raise ValueError('WiZ 전구를 먼저 선택해 주세요.')
            state = transport.request(light['ip'], 'getPilot')
            if state.get('mac') != light['mac']:
                raise ValueError('전구 주소가 바뀌었습니다. 다시 검색해 주세요.')
            verified[light['ip']] = light
            return jsonify(lights=[{'id':light['ip'], 'name':light['name'], 'reachable':True, 'on':state.get('state') is True}], message='WiZ 전구 응답을 확인했습니다.')

    @api.post('/apply')
    def apply():
        data = request.get_json(silent=True)
        if not isinstance(data, dict) or set(data) - {'light_id','profile','confirmed','preserve_brightness'} or data.get('confirmed') is not True or not isinstance(data.get('light_id'), str):
            raise ValueError('적용할 전구와 프로필을 확인해 주세요.')
        profile = validate_profile(data.get('profile'))
        preserve = data.get('preserve_brightness', False)
        if type(preserve) is not bool:
            raise ValueError('밝기 유지 설정을 확인해 주세요.')
        with lock:
            light = verified.get(data['light_id'])
            if light is None:
                return jsonify(error='먼저 WiZ 연결 검증을 완료해 주세요.'), 409
            state = transport.request(light['ip'], 'getPilot')
            if state.get('mac') != light['mac']:
                verified.clear()
                raise ValueError('전구 식별 정보가 바뀌었습니다.')
            if preserve and state.get('state') is not True:
                return jsonify(applied=False, message='WiZ 전구가 꺼져 있습니다. 앱이나 스위치로 켜 주세요.')
            if profile['mode'] == 'color':
                command = dict(zip(('r','g','b'), (int(profile['color'][i:i+2],16) for i in (1,3,5))))
                command.update(c=0, w=0)
            else:
                command = {'temp':profile['temperature_k']}
            if not preserve:
                command.update(state=profile['brightness_pct'] > 0, dimming=max(10,profile['brightness_pct']))
            result = transport.request(light['ip'], 'setPilot', command)
            if result.get('success') is not True:
                raise OSError('WiZ 명령 승인을 확인하지 못했습니다.')
            return jsonify(applied=True, message='WiZ 전구가 색상 변경 명령을 승인했습니다.')
    return api
