/* iDotMatrix Web UI — app.js */

let _hasImage = false;
let _isGif = false;
let _previewUrl = null;

/* ── Utilities ── */
function debounce(fn, ms) {
  let timer = null;
  return function (...args) {
    clearTimeout(timer);
    timer = setTimeout(() => fn(...args), ms);
  };
}

let _toastTimer = null;
function toast(msg, isError = false) {
  const el = document.getElementById('toast');
  el.textContent = msg;
  el.className = 'show' + (isError ? ' error' : '');
  clearTimeout(_toastTimer);
  _toastTimer = setTimeout(() => { el.className = ''; }, 2800);
}

async function api(method, path, body = null, isFile = false) {
  const opts = { method };
  if (body && !isFile) {
    opts.headers = { 'Content-Type': 'application/json' };
    opts.body = JSON.stringify(body);
  } else if (isFile) {
    opts.body = body;
  }
  const res = await fetch(path, opts);
  if (!res.ok) {
    let msg = `错误 ${res.status}`;
    try { const j = await res.json(); msg = j.error || msg; } catch {}
    throw new Error(msg);
  }
  return res;
}

/* ── State collection ── */
function getParams() {
  const fit = document.querySelector('.fit-btn.active')?.dataset.fit || 'crop';
  return {
    fit,
    dither: document.getElementById('dither').checked,
    brightness: parseFloat(document.getElementById('s-brightness').value),
    contrast: parseFloat(document.getElementById('s-contrast').value),
    saturation: parseFloat(document.getElementById('s-saturation').value),
  };
}

/* ── Status polling ── */
async function fetchStatus() {
  try {
    const res = await api('GET', '/api/status');
    const data = await res.json();
    updateStatusUI(data);
  } catch {}
}

function updateStatusUI(data) {
  const dot = document.getElementById('status-dot');
  const text = document.getElementById('status-text');
  const addr = document.getElementById('status-addr');
  const btnDisc = document.getElementById('btn-disconnect');
  const btnOn = document.getElementById('btn-on');
  const btnOff = document.getElementById('btn-off');
  if (data.connected) {
    dot.className = 'dot dot-on';
    text.textContent = '已连接';
    addr.textContent = data.address || '';
    btnDisc.disabled = false;
    btnOn.disabled = false;
    btnOff.disabled = false;
  } else {
    dot.className = 'dot dot-off';
    text.textContent = '未连接';
    addr.textContent = data.last_device ? `上次: ${data.last_device}` : '';
    btnDisc.disabled = true;
    btnOn.disabled = true;
    btnOff.disabled = true;
  }
  updateSendButtons();
}

function updateSendButtons() {
  const connected = document.getElementById('status-dot').classList.contains('dot-on');
  document.getElementById('btn-send').disabled = !(_hasImage && !_isGif && connected);
  document.getElementById('btn-gif').disabled = !(_hasImage && _isGif && connected);
}

/* ── Scan + connect ── */
document.getElementById('btn-scan').addEventListener('click', async () => {
  toast('扫描中(约10秒)...');
  try {
    const res = await api('POST', '/api/scan');
    const devices = await res.json();
    const list = document.getElementById('device-list');
    list.innerHTML = '';
    if (!devices.length) { list.innerHTML = '<li>未发现设备</li>'; }
    devices.forEach(d => {
      const li = document.createElement('li');
      const info = document.createElement('span');
      info.className = 'device-info';
      info.textContent = d.name;
      const addrSpan = document.createElement('span');
      addrSpan.className = 'device-addr';
      addrSpan.textContent = d.address;
      info.appendChild(document.createElement('br'));
      info.appendChild(addrSpan);
      li.appendChild(info);
      const btn = document.createElement('button');
      btn.textContent = '连接';
      btn.onclick = () => connectDevice(d.address);
      li.appendChild(btn);
      list.appendChild(li);
    });
    document.getElementById('scan-modal').classList.remove('hidden');
  } catch (e) { toast(e.message, true); }
});

document.getElementById('btn-modal-close').addEventListener('click', () => {
  document.getElementById('scan-modal').classList.add('hidden');
});

async function connectDevice(address) {
  document.getElementById('scan-modal').classList.add('hidden');
  try {
    await api('POST', '/api/connect', { address });
    toast(`已连接 ${address}`);
    fetchStatus();
  } catch (e) { toast(e.message, true); }
}

document.getElementById('btn-disconnect').addEventListener('click', async () => {
  try {
    await api('POST', '/api/disconnect');
    toast('已断开连接');
    fetchStatus();
  } catch (e) { toast(e.message, true); }
});

/* ── Upload ── */
const dropZone = document.getElementById('drop-zone');
const fileInput = document.getElementById('file-input');

dropZone.addEventListener('dragover', e => { e.preventDefault(); dropZone.classList.add('drag-over'); });
dropZone.addEventListener('dragleave', () => dropZone.classList.remove('drag-over'));
dropZone.addEventListener('drop', e => {
  e.preventDefault();
  dropZone.classList.remove('drag-over');
  if (e.dataTransfer.files[0]) handleFile(e.dataTransfer.files[0]);
});
fileInput.addEventListener('change', e => { if (e.target.files[0]) handleFile(e.target.files[0]); });

async function handleFile(file) {
  const fd = new FormData();
  fd.append('file', file);
  try {
    const res = await api('POST', '/api/upload', fd, true);
    const data = await res.json();
    _hasImage = true;
    _isGif = data.is_gif;
    document.getElementById('drop-filename').textContent = file.name;
    document.getElementById('gif-fps').classList.toggle('hidden', !_isGif);
    updateSendButtons();
    refreshPreview();
  } catch (e) { toast(e.message, true); }
}

/* ── Preview (debounced) ── */
const refreshPreview = debounce(async function () {
  if (!_hasImage) return;
  try {
    const res = await api('POST', '/api/preview', getParams());
    const blob = await res.blob();
    if (_previewUrl) URL.revokeObjectURL(_previewUrl);
    _previewUrl = URL.createObjectURL(blob);
    const img = document.getElementById('preview-img');
    img.src = _previewUrl;
    img.style.display = 'block';
    document.getElementById('preview-placeholder').style.display = 'none';
  } catch (e) { toast(e.message, true); }
}, 300);

/* ── Image options → trigger preview ── */
document.querySelectorAll('.fit-btn').forEach(btn => {
  btn.addEventListener('click', () => {
    document.querySelectorAll('.fit-btn').forEach(b => b.classList.remove('active'));
    btn.classList.add('active');
    refreshPreview();
  });
});
document.getElementById('dither').addEventListener('change', refreshPreview);

function bindSlider(sliderId, valId) {
  const s = document.getElementById(sliderId);
  const v = document.getElementById(valId);
  s.addEventListener('input', () => { v.textContent = parseFloat(s.value).toFixed(1); refreshPreview(); });
}
bindSlider('s-brightness', 'v-brightness');
bindSlider('s-contrast', 'v-contrast');
bindSlider('s-saturation', 'v-saturation');

/* ── Send ── */
document.getElementById('btn-send').addEventListener('click', async () => {
  try {
    await api('POST', '/api/send', getParams());
    toast('已发送到屏');
  } catch (e) { toast(e.message, true); }
});

document.getElementById('btn-gif').addEventListener('click', async () => {
  const _rawFps = parseInt(document.getElementById('fps').value, 10);
  const fps = (Number.isNaN(_rawFps) || _rawFps < 1) ? 10 : _rawFps;
  try {
    await api('POST', '/api/gif', { fps, ...getParams() });
    toast('GIF 已发送到屏');
  } catch (e) { toast(e.message, true); }
});

/* ── Device brightness ── */
const devBrightness = document.getElementById('s-dev-brightness');
const devBrightnessVal = document.getElementById('v-dev-brightness');
devBrightness.addEventListener('input', () => {
  devBrightnessVal.textContent = devBrightness.value;
});
devBrightness.addEventListener('change', async () => {
  try {
    await api('POST', '/api/brightness', { level: parseInt(devBrightness.value) });
  } catch (e) { toast(e.message, true); }
});

/* ── Power ── */
document.getElementById('btn-on').addEventListener('click', async () => {
  try { await api('POST', '/api/power', { on: true }); toast('开屏'); } catch (e) { toast(e.message, true); }
});
document.getElementById('btn-off').addEventListener('click', async () => {
  try { await api('POST', '/api/power', { on: false }); toast('关屏'); } catch (e) { toast(e.message, true); }
});

/* ── Init ── */
fetchStatus();
setInterval(fetchStatus, 3000);
