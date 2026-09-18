import {createLightingController} from './lighting_state.mjs';

export function mountLighting(document, api = lightingApi, download = downloadSettings) {
  const $ = id => document.getElementById(id);
  let connectionMessage = '실제 조명 연결은 비활성 상태입니다.';
  const controls = {mode:'lighting-mode', color:'lighting-color', temperature_k:'lighting-temperature',
    brightness_pct:'lighting-brightness', basis:'lighting-basis'};
  function render(state) {
    const enabled = Boolean(state.profile) && !state.pending;
    $('lighting-fields').disabled = !enabled;
    $('lighting-save').disabled = $('lighting-apply').disabled = !enabled;
    $('lighting-export').disabled = state.pending;
    $('lighting-recommend').disabled = state.pending;
    $('lighting-reason').textContent = state.pending ? '설정을 확인하고 있습니다…' : state.profile ?
      `${state.label} · ${state.reason}` : 'OCR 텍스트가 바뀌었습니다. 추천 새로고침을 눌러 주세요.';
    const message = state.error || state.application?.message || connectionMessage;
    $('lighting-status').textContent = message === '조명이 연결되지 않아 실제 기기에 적용하지 않았습니다.' ?
      '이 영역은 미리보기이며 조명에 적용하지 않았습니다. 실제 연결과 자동 연동 상태는 아래 Hue 영역에서 확인하세요.' : message;
    $('lighting-save-status').textContent = state.dirty ? '저장하지 않은 수정값이 있습니다.' : state.saved ?
      '이 활동의 프로필을 이 Mac에 저장했습니다.' : '저장된 프로필 또는 기본 예시를 미리보고 있습니다.';
    if (state.profile) {
      for (const [key, id] of Object.entries(controls)) {
        const value = String(state.profile[key]);
        if ($(id).value !== value && document.activeElement !== $(id)) $(id).value = value;
      }
      const p = state.profile;
      $('lighting-color').disabled = !enabled || p.mode !== 'color';
      $('lighting-temperature').disabled = !enabled || p.mode !== 'temperature';
      // Illustrative warm/cool swatches, not calibrated color-temperature rendering.
      const color = p.mode === 'color' ? p.color : p.temperature_k < 3300 ? '#ffd6a3' : p.temperature_k < 4500 ? '#fff1d6' : '#eaf2ff';
      $('lighting-swatch').style.backgroundColor = color;
      $('lighting-swatch').style.opacity = String(Math.max(0, Math.min(1, p.brightness_pct / 100)));
      const summary = `${state.label} · ${p.mode === 'color' ? p.color : p.temperature_k + ' K'} · 밝기 ${p.brightness_pct}%`;
      $('lighting-preview').setAttribute('aria-label', summary);
      $('lighting-summary').textContent = `${summary}. 화면의 색과 밝기는 참고용입니다.`;
    } else {
      $('lighting-swatch').style.opacity = '0';
      $('lighting-preview').setAttribute('aria-label', '추천을 다시 불러와 주세요');
      $('lighting-summary').textContent = '추천이 준비되면 설정 미리보기가 표시됩니다.';
    }
  }
  const controller = createLightingController(api, render);
  async function run(action) {
    try { await action(); }
    catch (error) { $('lighting-status').textContent = error.message; }
  }
  let recommendationRun = 0, pageAnalysis = null;
  const refresh = (fromOCR = false) => run(async () => {
    const current = ++recommendationRun;
    const text = $('result').value;
    const analysis = pageAnalysis;
    if (fromOCR === true && analysis && !analysis.eligible) {
      controller.invalidate();
      $('lighting-reason').textContent = '페이지 판단 보류 · ' + analysis.reason;
      return;
    }
    await controller.recommend(text, $('lighting-activity').value, analysis?.kind);
    if (fromOCR === true && current === recommendationRun && (text.trim() || analysis?.eligible) && text === $('result').value &&
        $('lighting-activity').value === 'auto' && controller.state.profile && !controller.state.error) {
      document.dispatchEvent(new document.defaultView.CustomEvent('lighting-ocr-ready', {detail:{
        text, pageEligible:Boolean(analysis?.eligible), activity:controller.state.activity, profile:{...controller.state.profile}}}));
    }
  });
  $('lighting-recommend').addEventListener('click', refresh);
  $('lighting-activity').addEventListener('change', refresh);
  for (const [key, id] of Object.entries(controls)) {
    $(id).addEventListener('input', () => {
      const value = key === 'temperature_k' || key === 'brightness_pct' ? $(id).valueAsNumber : $(id).value;
      controller.edit({[key]:value});
    });
  }
  $('lighting-form').addEventListener('submit', event => {
    event.preventDefault();
    if ($('lighting-form').reportValidity()) run(() => controller.save());
  });
  $('lighting-apply').addEventListener('click', () => {
    if ($('lighting-form').reportValidity()) run(() => controller.apply());
  });
  $('lighting-export').addEventListener('click', () => run(async () => {
    download(await controller.exportSaved(), 'lighting-profiles.json');
  }));
  $('result').addEventListener('input', () => {if ($('lighting-activity').value === 'auto') controller.invalidate();});
  document.addEventListener('ocr-cleared', () => {pageAnalysis = null; $('page-analysis').textContent = '새 페이지를 분석할 준비가 됐습니다.'; if ($('lighting-activity').value === 'auto') controller.invalidate();});
  document.addEventListener('ocr-complete', event => {
    pageAnalysis = event.detail?.page_analysis || null;
    $('page-analysis').textContent = pageAnalysis ? `${pageAnalysis.label} · ${pageAnalysis.reason}` : '페이지 정보가 없습니다.';
    if ($('lighting-activity').value === 'auto') refresh(true);
  });
  run(async () => {const status = await api('/status', undefined, 'GET'); connectionMessage = status.message; render(controller.state);});
  refresh();
  return controller;
}

async function lightingApi(path, body, method = 'POST') {
  const response = await fetch('/api/lighting' + path, {
    method, headers:body === undefined ? {} : {'Content-Type':'application/json'},
    body:body === undefined ? undefined : JSON.stringify(body), signal:AbortSignal.timeout(10000)
  });
  const data = await response.json();
  if (!response.ok) throw new Error(data.error || '조명 설정 요청에 실패했습니다.');
  return data;
}

function downloadSettings(data, name) {
  const url = URL.createObjectURL(new Blob([JSON.stringify(data, null, 2)], {type:'application/json;charset=utf-8'}));
  const link = document.createElement('a'); link.href = url; link.download = name; link.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

if (typeof document !== 'undefined') mountLighting(document);
