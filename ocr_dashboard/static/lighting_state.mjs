// Pure UI state: injected API keeps requests separate from rendering and testable.
export function createLightingController(api, changed = () => {}) {
  const state = {activity:null, label:'', profile:null, reason:'', dirty:false,
    pending:false, error:'', application:null, saved:false};
  let revision = 0;
  function invalidate() {
    revision += 1;
    Object.assign(state, {activity:null, label:'', profile:null, reason:'', dirty:false,
      pending:false, error:'', application:null, saved:false});
    changed(state);
  }
  async function operation(action, update) {
    const current = ++revision;
    state.pending = true; state.error = ''; changed(state);
    try {
      const response = await action();
      if (current === revision) update(response);
      return response;
    } catch (error) {
      if (current === revision) { state.error = error.message; throw error; }
    } finally {
      if (current === revision) {state.pending = false; changed(state);}
    }
  }
  function requireProfile() {
    if (!state.profile || state.pending) throw new Error('활동 추천이 준비된 뒤 다시 시도해 주세요.');
  }
  return {
    state, invalidate,
    async recommend(text, activity, pageKind) {
      invalidate();
      return operation(() => api('/recommend', {text, activity, ...(pageKind ? {page_kind:pageKind} : {})}), result => {
        Object.assign(state, {activity:result.activity, label:result.label,
          profile:{...result.profile}, reason:result.reason});
      });
    },
    edit(values) {
      requireProfile();
      state.profile = {...state.profile, ...values};
      state.dirty = true; state.saved = false; state.application = null; state.error = '';
      changed(state);
    },
    async save() {
      requireProfile();
      return operation(() => api(`/profiles/${state.activity}`, {...state.profile}, 'PUT'), () => {
        state.dirty = false; state.saved = true;
      });
    },
    async apply() {
      requireProfile(); state.application = null;
      return operation(() => api('/apply', {profile:{...state.profile}}), result => {
        state.application = result;
      });
    },
    async exportSaved() {
      return operation(() => api('/export', undefined, 'GET'), () => {});
    }
  };
}
