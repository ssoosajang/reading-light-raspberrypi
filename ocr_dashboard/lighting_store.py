"""Atomic local profile persistence. No OCR text or provider secrets in schema."""
from copy import deepcopy
import json
from pathlib import Path
import tempfile
import threading

from .lighting import ACTIVITIES, DEFAULT_PROFILES, validate_profile


class SettingsUnavailable(Exception):
    pass


class LightingStore:
    def __init__(self):
        self.lock = threading.Lock()

    def load(self, path):
        path = Path(path)
        try:
            raw = path.read_text(encoding='utf-8')
        except FileNotFoundError:
            return {'version': 1, 'profiles': deepcopy(DEFAULT_PROFILES)}
        except OSError as exc:
            raise SettingsUnavailable('조명 설정 파일을 읽을 수 없습니다.') from exc
        try:
            data = json.loads(raw)
            if not isinstance(data, dict) or set(data) != {'version', 'profiles'} or type(data['version']) is not int or data['version'] != 1:
                raise ValueError('schema')
            if not isinstance(data['profiles'], dict) or (not {'focus','reading','relax','general'} <= set(data['profiles']) or not set(data['profiles']) <= set(ACTIVITIES)):
                raise ValueError('profiles')
            for profile in data['profiles'].values():
                validate_profile(profile)
            data['profiles'] = {**deepcopy(DEFAULT_PROFILES), **data['profiles']}
            return data
        except (ValueError, TypeError) as exc:
            raise SettingsUnavailable('조명 설정 파일이 올바르지 않습니다. 파일을 확인해 주세요. 기존 파일은 유지했습니다.') from exc

    def save(self, path, activity, profile):
        if activity not in ACTIVITIES:
            raise ValueError('지원하는 활동을 선택해 주세요.')
        validated = validate_profile(profile)
        path = Path(path)
        with self.lock:
            settings = self.load(path)
            settings['profiles'][activity] = validated
            temporary = None
            try:
                path.parent.mkdir(parents=True, exist_ok=True)
                with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', dir=path.parent,
                                                 prefix='.lighting-', suffix='.tmp', delete=False) as output:
                    temporary = Path(output.name)
                    json.dump(settings, output, ensure_ascii=False, indent=2)
                temporary.replace(path)
            except OSError as exc:
                raise SettingsUnavailable('조명 설정을 저장하지 못했습니다. 폴더 쓰기 권한을 확인해 주세요.') from exc
            finally:
                if temporary is not None:
                    temporary.unlink(missing_ok=True)
            return settings
