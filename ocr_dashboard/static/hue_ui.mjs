export function mountHue(document, api = hueApi, confirm = message => window.confirm(message)) {
  const $ = id => document.getElementById(id);
  const provider = $('lighting-provider');
  const isWiz = provider?.value === 'wiz';
  const isBoth = provider?.value === 'both';
  provider?.addEventListener('change', () => {
    document.defaultView.localStorage.setItem('ocr-lighting-provider-v2', provider.value);
    document.defaultView.location.reload();
  });
  if (isWiz) {
    $('hue-discover').textContent = 'WiZ 전구 검색';
    $('hue-pair').textContent = '이 전구 연결';
  }
  let busy = false, paired = false, verified = false;
  let automatic = false, lastKey = null;
  const preference = value => {
    try {
      if (value !== undefined) document.defaultView.localStorage.setItem('ocr-hue-auto', String(value));
      return document.defaultView.localStorage.getItem('ocr-hue-auto') !== 'false';
    } catch { return true; }
  };
  function render() {
    if (provider) provider.disabled = busy;
    $('hue-auto').disabled = !automatic && (busy || !verified || !$('hue-light').value || $('lighting-activity').value !== 'auto');
    $('hue-auto').setAttribute('aria-pressed', String(automatic));
    $('hue-auto').textContent = automatic ? '자동 조명 연동 끄기' : 'OCR 결과로 자동 조명 연동 켜기';
    $('hue-auto-status').textContent = automatic ? '자동 연동 켜짐 · 다음 OCR 완료 시 선택한 조명에 적용합니다.' : '자동 연동 꺼짐';
    $('hue-discover').disabled = busy || automatic || isBoth;
    $('hue-bridge').disabled = busy || automatic;
    $('hue-pair').disabled = busy || automatic || isBoth || !$('hue-bridge').value;
    $('hue-verify').disabled = busy || !paired;
    $('hue-light').disabled = busy || automatic || !verified;
    $('hue-control').disabled = busy || !verified || !$('hue-light').value;
    $('hue-status').textContent = busy ? '연결 확인 중' : verified ? '조명 목록 확인 완료' : paired ? '연결 승인됨 · 검증 필요' : isWiz ? 'WiZ 전구 연결 필요' : '브릿지 연결 필요';
  }
  async function run(action) {
    if (busy) return;
    busy = true; render();
    try { await action(); }
    catch (error) { automatic = false; verified = false; $('hue-message').textContent = error.message; }
    finally { busy = false; render(); }
  }
  function options(id, values) {
    $(id).replaceChildren();
    for (const value of values) {
      const option = document.createElement('option');
      option.value = value.id; option.textContent = value.label;
      $(id).append(option);
    }
  }
  $('hue-bridge').addEventListener('change', () => {
    automatic = false; paired = verified = false; options('hue-light', []); render();
  });
  $('hue-light').addEventListener('change', () => { automatic = false; lastKey = null; render(); });
  $('lighting-activity').addEventListener('change', () => {automatic = false; render();});
  $('hue-auto').addEventListener('click', () => {
    automatic = !automatic; preference(automatic); lastKey = null; render();
    $('hue-message').textContent = automatic ? '자동 연동을 켰습니다. 페이지를 촬영하면 유형을 분석해 조명이 바뀝니다.' : '새 자동 명령을 중단했습니다. 이미 전송된 명령은 완료될 수 있습니다.';
  });
  document.addEventListener('lighting-ocr-ready', event => {
    const detail = event.detail;
    if (!automatic || !verified || busy || (!detail?.text?.trim() && !detail?.pageEligible)) return;
    const p = detail.profile;
    const key = JSON.stringify([$('hue-light').value,p.mode,p.mode === 'color' ? p.color : p.temperature_k,p.brightness_pct]);
    if (key === lastKey) { $('hue-message').textContent = '이전과 같은 조명값이라 현재 상태를 유지합니다.'; return; }
    const light = $('hue-light').value;
    run(async () => {
      const result = await api('/apply', {light_id:light, profile:{...p}, confirmed:true, preserve_brightness:true});
      if (result.applied === false) throw new Error(result.message || '자동 적용을 확인하지 못했습니다.');
      lastKey = key;
      $('hue-message').textContent = 'OCR 추천값 자동 적용 · ' + result.message;
    });
  });
  document.defaultView.addEventListener('pagehide', () => {automatic = false;});
  $('hue-discover').addEventListener('click', () => run(async () => {
    verified = false;
    const result = await api('/discover', {});
    options('hue-bridge', result.bridges.map(b => ({id:b.id, label:`${b.name} · ${b.ip}`})));
    $('hue-message').textContent = result.bridges.length ? (isWiz ? '전구를 선택하고 이 전구 연결을 누른 뒤 연결 검증을 누르세요.' : '브릿지를 선택하세요. 가운데 버튼을 누른 뒤 연결 승인 확인을 누르면 됩니다.') : '조명을 찾지 못했습니다. 같은 Wi-Fi와 로컬 통신 설정을 확인해 주세요.';
  }));
  $('hue-pair').addEventListener('click', () => run(async () => {
    paired = verified = false;
    const result = await api('/pair', {bridge_id:$('hue-bridge').value});
    paired = true; $('hue-message').textContent = result.message;
  }));
  $('hue-verify').addEventListener('click', () => run(async () => {
    verified = false;
    const result = await api('/verify', {});
    options('hue-light', result.lights.filter(x => x.reachable).map(x => ({id:x.id, label:x.name})));
    verified = true;
    $('hue-message').textContent = result.message + (result.lights.some(x=>x.reachable) ? '' : ' 연결 가능한 조명이 없습니다.');
  }));
  $('hue-control').addEventListener('click', () => {
    if ($('lighting-fields').disabled || !$('lighting-form').reportValidity()) {
      $('hue-message').textContent = '위의 조명 추천값을 새로고침하고 확인해 주세요.'; return;
    }
    const profile = {mode:$('lighting-mode').value, color:$('lighting-color').value,
      temperature_k:$('lighting-temperature').valueAsNumber, brightness_pct:$('lighting-brightness').valueAsNumber,
      basis:$('lighting-basis').value};
    const name = $('hue-light').selectedOptions[0]?.textContent;
    const setting = profile.mode === 'color' ? profile.color : `${profile.temperature_k} K`;
    if (!Number.isFinite(profile.brightness_pct) || !Number.isFinite(profile.temperature_k)) {
      $('hue-message').textContent = '위의 조명 추천값을 먼저 준비해 주세요.'; return;
    }
    if (!confirm(`${name} 조명에 ${setting}, 밝기 ${profile.brightness_pct}%를 한 번 적용할까요?`)) return;
    run(async () => {
      const result = await api('/apply', {light_id:$('hue-light').value, profile, confirmed:true});
      $('hue-message').textContent = result.message;
    });
  });
  render();
  run(async () => {
    const result = await api('/status', undefined, 'GET');
    paired = result.paired;
    if (paired) {
      const result = await api('/verify', {});
      const lights = result.lights.filter(x => x.reachable);
      options('hue-light', lights.map(x => ({id:x.id,label:x.name})));
      verified = lights.length > 0;
      automatic = verified && lights.length === 1 && preference() && $('lighting-activity').value === 'auto';
      $('hue-message').textContent = automatic ? '저장된 연결을 확인했습니다. 촬영하면 조명이 자동 적용됩니다.' : '연결을 확인했습니다. 조명 선택과 자동 연동 상태를 확인해 주세요.';
      return;
    }
    $('hue-message').textContent = paired ? '저장된 연결정보가 있습니다. 연결 검증을 눌러 주세요.' : isWiz ? 'WiZ 전구 검색부터 시작하세요.' : '브릿지 검색부터 시작하세요.';
  });
}

export function createLightingApi(getProvider, fetcher = fetch) {
  let targets = [];
  async function send(provider, path, body, method) {
    const response = await fetcher('/api/' + provider + path, {method,
      headers: body === undefined ? {} : {'Content-Type':'application/json'},
      body: body === undefined ? undefined : JSON.stringify(body), signal:AbortSignal.timeout(30000)});
    const result = await response.json();
    if (!response.ok) throw new Error(`${provider}: ${result.error || '조명 연결 실패'}`);
    return result;
  }
  return async (path, body, method = 'POST') => {
    const provider = getProvider();
    if (provider !== 'both') return send(provider, path, body, method);
    if (path === '/status') {
      const results = await Promise.all(['hue','wiz'].map(p => send(p,path,undefined,'GET')));
      return {paired:results.every(r => r.paired)};
    }
    if (path === '/verify') {
      targets = [];
      const results = await Promise.all(['hue','wiz'].map(p => send(p,path,{},'POST')));
      for (const [index, result] of results.entries()) {
        const reachable = result.lights.filter(l => l.reachable);
        if (reachable.length !== 1) throw new Error('함께 모드는 Hue와 WiZ에 각각 연결 가능한 조명 한 개가 필요합니다.');
        targets.push({provider:['hue','wiz'][index], id:reachable[0].id, name:reachable[0].name});
      }
      return {lights:[{id:'both',name:targets.map(t=>t.name).join(' + '),reachable:true}],message:'Hue와 WiZ 연결 확인 완료'};
    }
    if (path === '/apply') {
      if (targets.length !== 2 || body.light_id !== 'both') throw new Error('두 조명을 먼저 연결 검증해 주세요.');
      const results = await Promise.allSettled(targets.map(t => send(t.provider,path,{...body,light_id:t.id},'POST')));
      const failures = results.flatMap((r,i) => r.status === 'rejected' ? [`${targets[i].provider}: ${r.reason.message}`] :
        r.value.applied !== true ? [`${targets[i].provider}: ${r.value.message || '적용 미확인'}`] : []);
      if (failures.length) throw new Error('일부 조명 적용 실패 · ' + failures.join(' / '));
      return {applied:true,message:'Hue와 WiZ 모두 색상 변경 명령을 승인했습니다.'};
    }
    throw new Error('새 조명 연결은 Hue 또는 WiZ를 개별 선택해 주세요.');
  };
}
const hueApi = createLightingApi(() => document.getElementById('lighting-provider')?.value || 'hue');
if (typeof document !== 'undefined') {
  const provider = document.getElementById('lighting-provider');
  try {
    const saved = document.defaultView.localStorage.getItem('ocr-lighting-provider-v2');
    if (provider && ['hue','wiz','both'].includes(saved)) provider.value = saved;
  } catch {}
  mountHue(document);
}
