"""Local lighting preview endpoints; no external provider configuration."""
from flask import Blueprint, current_app, jsonify, request
from .lighting import recommend, validate_profile
from .lighting_store import LightingStore, SettingsUnavailable
from .lighting_adapter import DisabledLightingAdapter, LightingAdapter


def create_lighting_blueprint():
    api = Blueprint('lighting', __name__, url_prefix='/api/lighting')

    adapter: LightingAdapter = DisabledLightingAdapter()
    store = LightingStore()

    def settings_path():
        return current_app.config['LIGHTING_SETTINGS_PATH']

    @api.errorhandler(SettingsUnavailable)
    def unavailable(error):
        return jsonify(error=str(error)), 503

    @api.errorhandler(ValueError)
    def invalid(error):
        return jsonify(error=str(error)), 400

    @api.post('/recommend')
    def recommendation():
        return jsonify(recommend(request.get_json(silent=True), store.load(settings_path())['profiles']))

    @api.get('/status')
    def status():
        return jsonify(adapter.status())

    @api.post('/apply')
    def apply():
        payload = request.get_json(silent=True)
        if not isinstance(payload, dict) or set(payload) != {'profile'}:
            raise ValueError('미리보기 프로필만 입력해 주세요.')
        profile = validate_profile(payload['profile'])
        return jsonify(**adapter.apply(profile), requested_profile=profile)

    @api.get('/settings')
    def settings():
        return jsonify(store.load(settings_path()))

    @api.put('/profiles/<activity>')
    def save_profile(activity):
        return jsonify(store.save(settings_path(), activity, request.get_json(silent=True)))

    @api.get('/export')
    def export():
        response = jsonify(store.load(settings_path()))
        response.headers['Content-Disposition'] = 'attachment; filename="lighting-profiles.json"'
        return response

    return api
