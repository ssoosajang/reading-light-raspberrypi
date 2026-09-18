"""Provider boundary. Only the disabled implementation is wired into this app.

Future integrations must validate their device's supported mode/ranges before
transmission, use finite timeouts, and report applied=True only after device
acknowledgment. Never infer an actual state from the requested profile.
"""
from typing import Protocol, TypedDict
from .lighting import validate_profile


class LightingStatus(TypedDict):
    provider: str
    connected: bool
    applied: bool
    message: str


class LightingAdapter(Protocol):
    def status(self) -> LightingStatus: ...
    def apply(self, profile: dict) -> LightingStatus: ...


class DisabledLightingAdapter:
    def status(self) -> LightingStatus:
        return {'provider': 'disabled', 'connected': False, 'applied': False,
                'message': '조명이 연결되지 않아 실제 기기에 적용하지 않았습니다.'}

    def apply(self, profile: dict) -> LightingStatus:
        validate_profile(profile)
        return self.status()
