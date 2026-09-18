"""Editable demo profiles and explainable, local activity rules."""
from copy import deepcopy
import re

ACTIVITIES = {'focus': '집중', 'reading': '독서', 'relax': '휴식', 'general': '일반', 'english_book':'영어 글 중심', 'text_book':'글이 많은 페이지', 'picture_book':'그림 중심', 'math_book':'수학·계산', 'art_book':'미술·창작'}
KEYWORDS = {
    'focus': ('집중', '업무', '회의', 'focus', 'work', 'meeting'),
    'reading': ('독서', '읽기', '책', 'reading', 'read', 'book'),
    'relax': ('휴식', '명상', '휴게', 'relax', 'rest', 'meditation'),
}
DEFAULT_PROFILES = {
    activity: {'mode': 'temperature', 'color': color, 'temperature_k': temperature,
               'brightness_pct': brightness, 'basis': '기능 확인용 예시 값 · 연구 기반 권장치 아님'}
    for activity, color, temperature, brightness in (
        ('focus', '#EAF2FF', 5000, 80), ('reading', '#FFF1D6', 4000, 70),
        ('relax', '#FFD6A3', 2700, 35), ('general', '#FFFFFF', 3500, 60),
        ('english_book', '#F5F5FF', 4500, 80), ('text_book', '#FFF1D6', 4500, 70), ('picture_book', '#FFE5C4', 3000, 65),
        ('math_book', '#EAF2FF', 6500, 80), ('art_book', '#FFE5C4', 3000, 70))
}


RESEARCH_BASIS = {
    'math_book': 'Choi & Suk (2016), DOI 10.1364/OE.24.00A907. 초등 산술 학습의 6500 K 조건 참고. 모든 연령의 최적값을 뜻하지 않음. 자동 적용은 밝기 유지, 조도 미보정.',
    'english_book': '이붕주 (2020), DOI 10.5762/KAIS.2020.21.4.518. 언어 과제의 4500 K·500 lx 보고. 독서/영어 페이지에 참고 적용. 밝기 %는 500 lx 환산값이 아니며 자동 적용은 기존 밝기 유지.',
    'text_book': '이붕주 (2020), DOI 10.5762/KAIS.2020.21.4.518. 언어 과제의 4500 K·500 lx 보고를 독서 페이지에 참고 적용. 밝기 %는 조도 환산값 아님. 자동 적용은 밝기 유지.',
    'picture_book': '이붕주 (2020), DOI 10.5762/KAIS.2020.21.4.518. 창의 과제의 3000 K·500 lx 보고. 그림책을 창의 영역으로 연결한 것은 제품 가정이며 그림책 자체의 검증값이 아님. 자동 적용은 밝기 유지.',
    'art_book': '이붕주 (2020), DOI 10.5762/KAIS.2020.21.4.518. 창의 과제의 3000 K·500 lx 보고를 미술·창작에 참고 적용. 정확한 색 평가용 조명 기준은 아님. 자동 적용은 밝기 유지.',
}
# Shared Hue/WiZ white-light presets; RGB demonstration colors are no longer defaults.
SUBJECT_COLORS = {
    'math_book': ('temperature', '#EAF2FF', 6500),
    'english_book': ('temperature', '#FFFFFF', 4500),
    'text_book': ('temperature', '#FFFFFF', 4500),
    'picture_book': ('temperature', '#FFE5C4', 3000),
    'art_book': ('temperature', '#FFE5C4', 3000),
}
for _kind, (_mode, _color, _temperature) in SUBJECT_COLORS.items():
    DEFAULT_PROFILES[_kind].update(mode=_mode, color=_color, temperature_k=_temperature,
                                  basis=RESEARCH_BASIS[_kind])


def recommend(payload, profiles=None):
    if not isinstance(payload, dict) or set(payload) - {'text', 'activity', 'page_kind'}:
        raise ValueError('활동과 텍스트만 입력해 주세요.')
    text = payload.get('text', '')
    activity = payload.get('activity', 'auto')
    if not isinstance(text, str) or len(text) > 50_000:
        raise ValueError('텍스트는 50,000자 이하로 입력해 주세요.')
    if not isinstance(activity, str) or activity not in ('auto', *ACTIVITIES):
        raise ValueError('지원하는 활동을 선택해 주세요.')
    page_kind = payload.get('page_kind')
    if page_kind is not None and page_kind not in ('english_book','text_book','picture_book','math_book','art_book','uncertain'):
        raise ValueError('지원하지 않는 페이지 유형입니다.')
    if activity == 'auto' and page_kind in ('english_book','text_book','picture_book','math_book','art_book'):
        return {'activity':page_kind, 'label':ACTIVITIES[page_kind], 'source':'page',
                'reason':'촬영한 페이지의 언어와 글·그림 비중으로 분류했습니다.',
                'profile':deepcopy((profiles or DEFAULT_PROFILES)[page_kind])}
    source = 'manual' if activity != 'auto' else 'ocr'
    if source == 'manual':
        reason = '사용자가 선택한 활동을 우선했습니다.'
    else:
        lowered = text.casefold()
        words = set(re.findall(r'[a-z]+', lowered))
        matches = {key: [word for word in values if (word in words if word.isascii() else word in lowered)]
                   for key, values in KEYWORDS.items()}
        scores = {key: len(values) for key, values in matches.items()}
        highest = max(scores.values())
        winners = [key for key, score in scores.items() if score == highest]
        if highest and len(winners) == 1:
            activity = winners[0]
            reason = '일치 키워드: ' + ', '.join(matches[activity])
        else:
            activity = 'general'
            reason = '활동 힌트가 없거나 여러 활동이 겹쳐 일반 프로필을 제안합니다.'
    return {'activity': activity, 'label': ACTIVITIES[activity], 'source': source, 'reason': reason,
            'profile': deepcopy((profiles or DEFAULT_PROFILES)[activity])}


def validate_profile(profile):
    if not isinstance(profile, dict) or set(profile) != {'mode', 'color', 'temperature_k', 'brightness_pct', 'basis'}:
        raise ValueError('조명 모드, 색상, 색온도, 밝기, 근거 메모만 입력해 주세요.')
    if profile['mode'] not in ('temperature', 'color'):
        raise ValueError('색온도 또는 색상 모드를 선택해 주세요.')
    if not isinstance(profile['color'], str) or not re.fullmatch(r'#[0-9a-fA-F]{6}', profile['color']):
        raise ValueError('색상은 #RRGGBB 형식이어야 합니다.')
    for key, low, high in (('temperature_k', 2000, 6500), ('brightness_pct', 0, 100)):
        if type(profile[key]) is not int or not low <= profile[key] <= high:
            raise ValueError(f'{key} 값은 {low}–{high} 범위의 정수여야 합니다.')
    if not isinstance(profile['basis'], str) or len(profile['basis']) > 1000:
        raise ValueError('근거 메모는 1,000자 이하로 입력해 주세요.')
    return deepcopy(profile)
