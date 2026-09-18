(() => {
  const $ = id => document.getElementById(id);
  const button = $('session-toggle'), status = $('session-status');
  if (!button || !status) return;
  let confirmed = false;
  document.addEventListener('ocr-cleared', () => { confirmed = false; });
  function render() {
    const running = !$('stop').disabled;
    button.textContent = running ? '중지' : '시작';
    button.setAttribute('aria-pressed', String(running));
    button.disabled = !running && $('camera').disabled;
    const live = $('live-status').textContent;
    const message = $('hue-message').textContent;
    if (!running) {
      status.textContent = /오류/.test(live) ? live : button.disabled ? '카메라 연결 중…' : '시작을 누르고 책을 비춰 주세요.';
    } else if (/판단 보류/.test(live)) {
      status.textContent = '책을 고정해서 비춰 주세요.';
    } else if (/조명 연동 중/.test(live)) {
      const kind = $('page-analysis').textContent.split(' · ')[0];
      status.textContent = $('hue-auto').getAttribute('aria-pressed') !== 'true' ? '조명 연결 설정을 확인해 주세요.' :
        confirmed && message.startsWith('OCR 추천값 자동 적용') ? `${kind} · 조명 적용 완료` :
        confirmed && message.startsWith('이전과 같은') ? `${kind} · 조명 유지` : `${kind} · 조명 확인 중…`;
    } else {
      status.textContent = '책을 확인하고 있습니다…';
    }
  }
  button.addEventListener('click', () => {
    (!$('stop').disabled ? $('stop') : $('camera')).click();
    render();
  });
  const observer = new MutationObserver(records => {
    if (records.some(record => record.target === $('hue-message'))) confirmed = true;
    render();
  });
  for (const id of ['camera','stop','live-status','page-analysis','hue-message','hue-auto']) {
    observer.observe($(id), {attributes:true,childList:true,characterData:true,subtree:true});
  }
  window.addEventListener('pagehide', () => observer.disconnect());
  render();
})();
