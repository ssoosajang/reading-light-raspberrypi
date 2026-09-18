const $ = id => document.getElementById(id);
const piCamera = document.body.dataset.cameraBackend === 'picamera';
let piURL = null;
let selected = null, sourceURL = null, stream = null, latest = null, busy = false;
let live = false, generation = 0, timer = null, requestAbort = null, candidate = null, matches = 0;
function liveStatus(text) { $('live-status').textContent = text; }
function stopCamera() {
  if ($('pi-camera-preview')) $('pi-camera-preview').hidden = true;
  if (piURL) { URL.revokeObjectURL(piURL); piURL = null; }
  live = false; generation++; clearTimeout(timer); timer = null;
  requestAbort?.abort(); candidate = null; matches = 0;
  document.dispatchEvent(new Event('ocr-cleared'));
  liveStatus('자동 인식 중지 · 카메라 시작을 누르면 다시 시작합니다.');
  if (stream) stream.getTracks().forEach(track => track.stop());
  stream = null; $('video').srcObject = null; $('video').hidden = true;
  $('capture').disabled = true; $('stop').disabled = true; $('camera').disabled = busy;
}
function choose(blob) {
  selected = blob; latest = null; $('result').value = '';
  document.dispatchEvent(new Event('ocr-cleared'));
  $('txt').disabled = $('json').disabled = true;
  $('preview').hidden = true; $('preview').removeAttribute('src');
  $('detection').textContent = '아직 처리한 이미지가 없습니다.';
  if (sourceURL) URL.revokeObjectURL(sourceURL);
  sourceURL = URL.createObjectURL(blob); $('source').src = sourceURL;
  $('source').hidden = false; $('run').disabled = false;
  $('status').textContent = '이미지가 준비되었습니다. 텍스트 추출을 눌러 주세요.';
}
$('file').addEventListener('change', event => {
  const file = event.target.files[0]; if (!file) return;
  if (file.size > 16 * 1024 * 1024) { $('status').textContent = '파일은 16 MB 이하로 선택해 주세요.'; return; }
  stopCamera(); choose(file);
});
$('camera').onclick = async () => {
  $('camera').disabled = true;
  $('status').textContent = '카메라 연결을 요청했습니다. 브라우저 또는 macOS의 카메라 권한 요청을 확인해 주세요.';
  try {
    if (piCamera) {
      const starting = ++generation;
      live = true; candidate = null; matches = 0;
      $('stop').disabled = false;
      liveStatus('자동 인식 중 · 카메라 모듈을 확인하고 있습니다.');
      captureLive(starting);
      return;
    }
    if (!navigator.mediaDevices?.getUserMedia) throw new Error('이 주소에서는 카메라를 사용할 수 없습니다. localhost에서 열거나 이미지를 업로드해 주세요.');
    const starting = ++generation;
    const opened = await navigator.mediaDevices.getUserMedia({video: {facingMode: 'environment', width: {ideal: 1920}, height: {ideal: 1080}}, audio: false});
    if (starting !== generation) { opened.getTracks().forEach(track => track.stop()); return; }
    stream = opened;
    $('video').srcObject = stream; $('video').hidden = false;
    await $('video').play();
    if (starting !== generation) return;
    live = true; candidate = null; matches = 0;
    $('capture').disabled = false; $('stop').disabled = false;
    liveStatus('자동 인식 중 · 책 한 페이지를 고정해서 비춰 주세요.');
    captureLive(starting);
    $('status').textContent = '책 한 쪽이 화면을 크게 채우도록 정면으로 비춘 뒤 촬영하세요. 작은 글자는 가까이 비춰 주세요.';
  } catch (error) { stopCamera(); $('status').textContent = `카메라를 열 수 없습니다. 권한과 연결을 확인해 주세요. ${error.message}`; }
};
$('stop').onclick = stopCamera;
$('capture').onclick = () => {
  const video = $('video'); if (!video.videoWidth) return;
  const canvas = document.createElement('canvas'); canvas.width = video.videoWidth; canvas.height = video.videoHeight;
  canvas.getContext('2d').drawImage(video, 0, 0);
  canvas.toBlob(blob => { if (blob) {stopCamera(); choose(blob); $('run').click();} }, 'image/jpeg', .92);
};
async function captureLive(token) {
  if (!live || token !== generation || busy) return;
  if (piCamera) {
    try {
      requestAbort = new AbortController();
      const response = await fetch('/api/camera/frame', {method:'POST',signal:requestAbort.signal});
      if (!response.ok) throw new Error((await response.json()).error || '카메라 촬영 실패');
      const blob = await response.blob();
      if (!live || token !== generation) return;
      if (piURL) URL.revokeObjectURL(piURL);
      piURL = URL.createObjectURL(blob);
      $('pi-camera-preview').src = piURL; $('pi-camera-preview').hidden = false;
      selected = blob;
      await runOCR(true, token);
    } catch (error) {
      if (token !== generation) return;
      stopCamera(); liveStatus('카메라 오류 · ' + error.message);
    }
    return;
  }
  const video = $('video');
  if (!video.videoWidth) { timer = setTimeout(() => captureLive(token), 500); return; }
  const canvas = document.createElement('canvas');
  canvas.width = video.videoWidth; canvas.height = video.videoHeight;
  canvas.getContext('2d').drawImage(video, 0, 0);
  canvas.toBlob(blob => {
    if (!blob || !live || token !== generation) return;
    selected = blob;
    runOCR(true, token);
  }, 'image/jpeg', .92);
}
$('run').onclick = () => runOCR(false);
async function runOCR(continuous = false, token = generation) {
  if (!selected || busy) return;
  if (!continuous) { stopCamera(); token = generation; }
  busy = true;
  ['run', 'file', 'camera', 'mode', 'language', 'rectify', 'txt', 'json'].forEach(id => $(id).disabled = true);
  latest = null; $('result').value = ''; $('preview').hidden = true;
  document.dispatchEvent(new Event('ocr-cleared'));
  $('status').textContent = '문서를 처리하고 있습니다…';
  if (continuous) liveStatus('자동 인식 중 · 페이지를 분석하고 있습니다.');
  $('capture').disabled = true;
  try {
    const form = new FormData(); form.append('image', selected, 'document.jpg');
    form.append('mode', $('mode').value); form.append('language', $('language').value);
    form.append('rectify', String($('rectify').checked));
    requestAbort = new AbortController();
    const response = await fetch('/api/ocr', {method: 'POST', body: form, signal: requestAbort.signal});
    const data = await response.json(); if (!response.ok) throw new Error(data.error || '처리하지 못했습니다.');
    if (token !== generation || (continuous && !live)) return;
    latest = data; $('result').value = data.text; $('preview').src = data.preview; $('preview').hidden = false;
    let stable = true;
    if (continuous) {
      const analysis = data.page_analysis;
      if (!analysis?.eligible) { candidate = null; matches = 0; stable = false; }
      else { matches = candidate === analysis.kind ? matches + 1 : 1; candidate = analysis.kind; stable = matches >= 2; }
      liveStatus(!analysis?.eligible ? '판단 보류 · 조명 유지. 책을 고정해서 비춰 주세요.' :
        stable ? `자동 인식 중 · ${analysis.label} 확인 · 조명 연동 중` : `${analysis.label} 감지 · 같은 유형인지 한 번 더 확인합니다.`);
      $('page-analysis').textContent = analysis ? `${analysis.label} · ${stable ? '연속 확인 완료' : '확인 중'}` : '페이지 확인 중';
    }
    if (stable) document.dispatchEvent(new CustomEvent('ocr-complete', {detail:{page_analysis:data.page_analysis}}));
    $('detection').textContent = data.document_detected ? '문서 영역을 감지해 원근을 보정했습니다. 잘못 잘렸다면 자동 보정을 끄고 다시 시도하세요.' : data.rectify_requested ? '문서 경계를 찾지 못해 전체 이미지를 사용했습니다.' : '자동 보정을 끄고 전체 이미지를 사용했습니다.';
    $('status').textContent = data.page_analysis?.eligible ? `완료 · ${data.page_analysis.label}. 아래 조명 연동 상태를 확인하세요.` : data.text ? '완료되었습니다. 내용을 확인한 뒤 저장하세요.' : '텍스트를 찾지 못했습니다. 조명이나 전처리 설정을 바꿔 다시 시도하세요.';
  } catch (error) {
    if (token !== generation) return;
    if (continuous) stopCamera();
    $('status').textContent = error.message; $('detection').textContent = '처리가 완료되지 않았습니다.';
    liveStatus('인식 오류로 중지했습니다. 카메라 시작으로 다시 시도하세요.');
  }
  finally {
    busy = false; ['run', 'file', 'camera', 'mode', 'language', 'rectify'].forEach(id => $(id).disabled = false);
    $('txt').disabled = $('json').disabled = !latest;
    $('camera').disabled = live;
    $('capture').disabled = !live;
    $('run').disabled = live || !selected;
    if (continuous && live && token === generation) timer = setTimeout(() => captureLive(token), 2000);
  }
};
function download(format) {
  if (!latest) return;
  const {preview, ...metadata} = latest;
  const content = format === 'txt' ? $('result').value : JSON.stringify({...metadata, text: $('result').value}, null, 2);
  const url = URL.createObjectURL(new Blob([content], {type: format === 'txt' ? 'text/plain;charset=utf-8' : 'application/json;charset=utf-8'}));
  const link = document.createElement('a'); link.href = url; link.download = `ocr-result.${format}`; link.click(); setTimeout(() => URL.revokeObjectURL(url), 1000);
}
$('txt').onclick = () => download('txt'); $('json').onclick = () => download('json');
window.addEventListener('pagehide', stopCamera);
document.addEventListener('visibilitychange', () => { if (document.hidden && live) stopCamera(); });
fetch('/api/health').then(r => r.json()).then(data => { $('health').textContent = data.ready ? '한글 · 영문 OCR 준비 완료' : 'OCR 엔진 설치 확인 필요'; }).catch(() => { $('health').textContent = '서버 연결 확인 필요'; });
