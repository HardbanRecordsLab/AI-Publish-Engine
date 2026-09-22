
const API = '';
let allJobs = [];
let authToken = '';

// ==================== AUTH GUARD ====================
async function checkAuth() {
  const stored = localStorage.getItem('admin_token');
  if (!stored) { showLogin(); return false; }
  try {
    const res = await fetch(API + '/api/admin/check', { headers: { 'Authorization': 'Bearer ' + stored } });
    if (res.ok) { authToken = stored; hideLogin(); return true; }
  } catch(e) {}
  localStorage.removeItem('admin_token');
  showLogin();
  return false;
}

function showLogin() {
  document.getElementById('loginOverlay').classList.remove('hidden');
  document.getElementById('loginError').textContent = '';
}

function hideLogin() {
  document.getElementById('loginOverlay').classList.add('hidden');
}

async function doLogin() {
  const email = document.getElementById('loginEmail').value.trim();
  const password = document.getElementById('loginPassword').value;
  const err = document.getElementById('loginError');
  const btn = document.getElementById('loginBtn');
  if (!email || !password) { err.textContent = 'Enter email and password'; return; }
  btn.disabled = true;
  btn.innerHTML = '<span class="login-spinner"></span> Signing in...';
  err.textContent = '';
  try {
    const data = await api('/api/admin/login', { method: 'POST', body: JSON.stringify({ email, password }) });
    authToken = data.token;
    localStorage.setItem('admin_token', authToken);
    hideLogin();
    document.getElementById('loginEmail').value = '';
    document.getElementById('loginPassword').value = '';
    initApp();
  } catch(e) {
    err.textContent = 'Invalid credentials';
  }
  btn.disabled = false;
  btn.innerHTML = 'Sign In';
}

function doLogout() {
  authToken = '';
  localStorage.removeItem('admin_token');
  showLogin();
  document.querySelectorAll('.panel').forEach(p => p.classList.remove('active'));
  document.querySelectorAll('.sidebar-link').forEach(l => l.classList.remove('active'));
}

// ==================== SPA ROUTING ====================
const PANEL_NAMES = {
  dashboard:'Dashboard', generator:'Ebook Generator', editor:'Chapter Editor',
  history:'Job History', batch:'Batch Generator', proofreader:'AI Proofreader',
  'beta-reader':'Beta Reader', coach:'Writing Coach', 'format-checker':'KDP Format Check',
  translate:'Translation', series:'Book Series', launch:'Launch Page',
  marketing:'Marketing Content', publish:'Publishing', revenue:'Revenue Dashboard', admin:'Admin Panel'
};

function switchPanel(name) {
  document.querySelectorAll('.panel').forEach(p => p.classList.remove('active'));
  document.querySelectorAll('.sidebar-link').forEach(l => l.classList.remove('active'));
  document.getElementById('panel-' + name).classList.add('active');
  document.querySelector(`.sidebar-link[data-panel="${name}"]`).classList.add('active');
  document.getElementById('panelTitle').textContent = PANEL_NAMES[name] || name;
  if (name === 'dashboard') refreshDashboard();
  if (name === 'history') refreshHistory();
}

document.querySelectorAll('.sidebar-link[data-panel]').forEach(link => {
  link.addEventListener('click', e => { e.preventDefault(); switchPanel(link.dataset.panel); });
});

// ==================== API HELPERS ====================
async function api(path, opts = {}) {
  const headers = { 'Content-Type': 'application/json', ...(authToken ? { 'Authorization': 'Bearer ' + authToken } : {}), ...opts.headers };
  if (opts.noJson) delete headers['Content-Type'];
  const res = await fetch(API + path, { ...opts, headers });
  if (!res.ok && opts.noFail) return null;
  if (!res.ok) { const e = await res.json().catch(()=>({})); throw new Error(e.detail || `HTTP ${res.status}`); }
  if (opts.raw) return res;
  return res.json();
}

// ==================== DASHBOARD ====================
async function refreshDashboard() {
  try {
    const jobs = await api('/api/admin/jobs', { headers: { 'Authorization': 'Bearer ' + authToken }, noFail: true });
    if (jobs && Array.isArray(jobs)) {
      allJobs = jobs;
      const total = jobs.length, done = jobs.filter(j => j.status === 'done').length, failed = jobs.filter(j => j.status === 'failed').length;
      const today = jobs.filter(j => { try { return new Date(j.created_at).toDateString() === new Date().toDateString() } catch(e) { return false } }).length;
      document.getElementById('dashJobs').textContent = total;
      document.getElementById('dashDone').textContent = done;
      document.getElementById('dashSuccess').textContent = total ? Math.round(done/total*100) + '%' : '-';
      document.getElementById('dashSuccessSub').textContent = done + '/' + total;
      document.getElementById('dashToday').textContent = today;
    }
  } catch(e) { /* dashboard silently fails */ }
}

// ==================== GENERATOR ====================
let selectedType = 'ebook', selectedTemplate = 'minimal', selectedFormats = ['epub', 'pdf'];
let selectedFiles = [];

document.querySelectorAll('.content-tab').forEach(tab => {
  tab.addEventListener('click', () => {
    document.querySelectorAll('.content-tab').forEach(t => t.classList.remove('active'));
    tab.classList.add('active');
    selectedType = tab.dataset.type;
    loadTemplates(selectedType);
  });
});

async function loadTemplates(type) {
  try {
    const grid = document.getElementById('templateGrid');
    grid.innerHTML = '<div style="grid-column:1/-1;text-align:center;padding:16px"><div class="spinner"></div></div>';
    const themes = await api('/api/themes');
    const grouped = {};
    themes.forEach(t => {
      const types = t.types || ['ebook'];
      types.forEach(tp => { if (!grouped[tp]) grouped[tp] = []; grouped[tp].push(t); });
    });
    const available = grouped[type] || themes;
    grid.innerHTML = available.slice(0, 12).map(t => `
      <div class="template-card ${t.id === selectedTemplate ? 'active' : ''}" onclick="selectTemplate('${t.id}', this)">
        <div class="template-card-preview" style="background:${t.colors?.background || '#1a1a2e'}">
          ${t.icon ? '<img src="/api/themes/'+t.id+'/icon" style="width:24px;height:24px;border-radius:4px" onerror="this.style.display=\'none\'">' : '📄'}
        </div>
        <div class="template-card-name">${t.name || t.id}</div>
        <div class="template-card-desc">${t.description || ''}</div>
      </div>
    `).join('');
  } catch(e) {
    document.getElementById('templateGrid').innerHTML = '<div style="grid-column:1/-1;text-align:center;padding:16px;color:var(--text-muted)">Failed to load templates</div>';
  }
}

function selectTemplate(id, el) {
  document.querySelectorAll('.template-card').forEach(c => c.classList.remove('active'));
  el.classList.add('active');
  selectedTemplate = id;
}

async function loadFormats() {
  const chips = document.getElementById('formatChips');
  try {
    const sizes = await api('/api/print-sizes');
    const fmtList = sizes?.formats || ['pdf','epub','docx','html','mobi','website'];
    chips.innerHTML = fmtList.map(f => `<span class="format-chip ${selectedFormats.includes(f) ? 'active' : ''}" onclick="toggleFormat('${f}', this)">${f.toUpperCase()}</span>`).join('');
  } catch(e) {
    chips.innerHTML = ['pdf','epub','docx'].map(f => `<span class="format-chip ${selectedFormats.includes(f) ? 'active' : ''}" onclick="toggleFormat('${f}', this)">${f.toUpperCase()}</span>`).join('');
  }
}

function toggleFormat(fmt, el) {
  el.classList.toggle('active');
  if (selectedFormats.includes(fmt)) selectedFormats = selectedFormats.filter(f => f !== fmt);
  else selectedFormats.push(fmt);
}

// Drop zone
const dropZone = document.getElementById('dropZone');
const fileInput = document.getElementById('fileInput');
dropZone.addEventListener('click', () => fileInput.click());
dropZone.addEventListener('dragover', e => { e.preventDefault(); dropZone.classList.add('dragover'); });
dropZone.addEventListener('dragleave', () => dropZone.classList.remove('dragover'));
dropZone.addEventListener('drop', e => { e.preventDefault(); dropZone.classList.remove('dragover'); handleFiles(e.dataTransfer.files); });
fileInput.addEventListener('change', () => handleFiles(fileInput.files));
function handleFiles(files) {
  selectedFiles = [...files];
  document.getElementById('fileList').innerHTML = selectedFiles.map(f => `<div style="font-size:11px;color:var(--accent-1);padding:2px 0">📄 ${f.name}</div>`).join('');
}

async function generate() {
  const topic = document.getElementById('topicInput').value.trim();
  if (!topic) { showError('Validation', 'Please enter a topic'); return; }
  const audience = document.getElementById('audienceInput').value.trim();
  const tone = document.getElementById('toneInput').value;
  const chapters = document.getElementById('chaptersInput').value;
  const keywords = document.getElementById('keywordsInput').value.trim();
  const lang = document.getElementById('languageInput').value;
  const provider = document.getElementById('providerSelect').value;

  const formData = new FormData();
  formData.append('topic', topic);
  formData.append('style', selectedTemplate);
  formData.append('content_type', selectedType);
  formData.append('audience', audience);
  formData.append('tone', tone);
  formData.append('chapters', chapters);
  formData.append('keywords', keywords);
  formData.append('language', lang);
  formData.append('provider', provider);
  formData.append('formats', selectedFormats.join(','));
  selectedFiles.forEach(f => formData.append('files', f));

  showProgress();
  try {
    const res = await fetch(API + '/api/generate', { method: 'POST', headers: authToken ? { 'Authorization': 'Bearer ' + authToken } : {}, body: formData });
    const data = await res.json();
    if (data.job_id) {
      pollJob(data.job_id);
    } else {
      showError('Generation failed', data.error || 'Unknown error');
    }
  } catch(e) {
    showError('Network error', e.message);
  }
}

function showProgress() {
  document.getElementById('progressSection').classList.add('visible');
  document.getElementById('resultCard').classList.remove('visible');
  document.getElementById('errorCard').classList.remove('visible');
  window.GENERATING = true;
}

function showError(title, msg) {
  document.getElementById('progressSection').classList.remove('visible');
  document.getElementById('errorTitle').textContent = title;
  document.getElementById('errorMsg').textContent = msg;
  document.getElementById('errorCard').classList.add('visible');
}

function showResult(job) {
  document.getElementById('progressSection').classList.remove('visible');
  document.getElementById('resultTitle').textContent = job.topic || 'Your Book';
  document.getElementById('resultMeta').textContent = `Style: ${job.style || 'minimal'} · Type: ${job.content_type || 'ebook'}`;
  const id = job.id;
  const isInteractive = job.content_type === 'interactive-book';
  document.getElementById('resultFormats').innerHTML = selectedFormats.map(f =>
    `<a class="result-format-btn" href="${API}/api/download/${id}?format=${f}" target="_blank"><span style="font-size:16px">${['📕','📖','📄','🌐','📱','🌍']['pdf epub docx html mobi website'.split(' ').indexOf(f)] || '📁'}</span> ${f.toUpperCase()}</a>`
  ).join('') +
  `<a class="result-format-btn" href="${API}/api/preview/${id}" target="_blank">👁️ Preview</a>` +
  `<a class="result-format-btn" href="${API}/api/editor/${id}/chapters" target="_blank">✏️ Edit</a>` +
  `<a class="result-format-btn" href="${API}/api/download/${id}/print" target="_blank">🖨️ Print PDF</a>` +
  (isInteractive ? `<a class="result-format-btn" href="${API}/api/reader/${id}" target="_blank">📖 Read Online</a>` : '') +
  `<button class="result-format-btn" onclick="showEmbedCode('${id}')">🔗 Embed</button>`;
  document.getElementById('resultCard').classList.add('visible');
}

let pollInterval = null;

function pollJob(jobId) {
  const steps = ['research','structure','writing','design','proofread','format','export'];
  document.getElementById('progressSteps').innerHTML = steps.map(s =>
    `<div class="progress-step" data-step="${s}"><span class="progress-step-icon">○</span><span class="progress-step-label">${s}</span></div>`
  ).join('');
  document.getElementById('progressStatus').innerHTML = `<span>Starting...</span> <button class="btn btn-sm btn-error" onclick="cancelJob('${jobId}')" style="font-size:9px;padding:2px 6px">Cancel</button>`;

  pollInterval = setInterval(async () => {
    try {
      const job = await api('/api/status/' + jobId);
      if (!job) return;
      const pct = job.progress || 0;
      document.getElementById('progressFill').style.width = pct + '%';
      document.getElementById('progressPct').textContent = pct + '%';
      const stepIdx = Math.floor((pct / 100) * steps.length);
      document.querySelectorAll('.progress-step').forEach((el, i) => {
        el.classList.toggle('done', i < stepIdx);
        el.classList.toggle('current', i === stepIdx);
        el.classList.toggle('failed', job.status === 'failed' && i === stepIdx);
        el.querySelector('.progress-step-icon').textContent = i < stepIdx ? '✓' : i === stepIdx ? (job.status === 'failed' ? '✗' : '●') : '○';
      });
      document.getElementById('progressStatus').innerHTML = `<span>${job.status} (${pct}%)</span> ${pct < 100 ? `<button class="btn btn-sm btn-error" onclick="cancelJob('${jobId}')" style="font-size:9px;padding:2px 6px">Cancel</button>` : ''}`;
      if (job.status === 'done' || job.status === 'completed') {
        clearInterval(pollInterval);
        showResult(job);
      } else if (job.status === 'failed' || job.status === 'error') {
        clearInterval(pollInterval);
        showError('Generation failed', job.error || 'Unknown error');
      } else if (job.status === 'cancelled') {
        clearInterval(pollInterval);
        showError('Cancelled', 'Job was cancelled');
      }
    } catch(e) { /* keep polling */ }
  }, 1000);
}

document.getElementById('generateBtn').addEventListener('click', generate);

// ==================== PROVIDERS ====================
async function loadProviders() {
  try {
    const providers = await api('/api/providers');
    const sel = document.getElementById('providerSelect');
    const current = localStorage.getItem('preferred_provider') || 'openrouter';
    sel.innerHTML = providers.map(p =>
      `<option value="${p.id}" ${p.id === current ? 'selected' : ''}>${p.id}</option>`
    ).join('');
    sel.addEventListener('change', () => localStorage.setItem('preferred_provider', sel.value));
    sel.dispatchEvent(new Event('change'));
  } catch(e) {}
}

document.getElementById('providerSelect').addEventListener('change', function() {
  const name = document.getElementById('providerName');
  const dot = document.getElementById('providerDot');
  name.textContent = this.value || 'unknown';
  dot.className = 'provider-dot on';
});

// ==================== HISTORY ====================
async function refreshHistory() {
  const body = document.getElementById('historyBody');
  const empty = document.getElementById('historyEmpty');
  try {
    const jobs = allJobs.length ? allJobs : await api('/api/admin/jobs', { headers: { 'Authorization': 'Bearer ' + authToken }, noFail: true });
    if (!jobs || !jobs.length) { body.innerHTML = ''; empty.style.display = ''; return; }
    empty.style.display = 'none';
    body.innerHTML = jobs.slice().reverse().slice(0, 50).map(j => `
      <tr>
        <td style="font-family:monospace;font-size:10px" title="${j.id}">${(j.id||'').slice(0,8)}...</td>
        <td style="max-width:120px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">${j.topic||'—'}</td>
        <td><span class="badge badge-${j.status === 'done' ? 'done' : j.status === 'failed' ? 'failed' : j.status === 'processing' ? 'processing' : 'queued'}">${j.status}</span></td>
        <td>${j.content_type||'ebook'}</td>
        <td>${j.style||'—'}</td>
        <td style="font-size:11px">${j.created_at ? new Date(j.created_at).toLocaleString() : '—'}</td>
        <td>
          ${j.status === 'done' ? `<a class="btn btn-sm btn-primary" href="${API}/api/download/${j.id}?format=pdf" style="text-decoration:none;color:#fff;font-size:10px;padding:3px 8px">PDF</a>` : ''}
          ${j.status === 'done' ? `<a class="btn btn-sm btn-secondary" href="${API}/api/preview/${j.id}" target="_blank" style="text-decoration:none;font-size:10px;padding:3px 8px">Preview</a>` : ''}
          ${(j.status === 'queued' || j.status === 'processing') ? `<button class="btn btn-sm btn-error" onclick="cancelJob('${j.id}')" style="font-size:9px;padding:2px 6px">✕</button>` : ''}
        </td>
      </tr>
    `).join('');
  } catch(e) { body.innerHTML = ''; empty.style.display = ''; }
}

// ==================== EDITOR ====================
async function loadEditor() {
  const jobId = document.getElementById('editorJobId').value.trim();
  if (!jobId) return;
  const container = document.getElementById('editorContent');
  container.innerHTML = '<div style="text-align:center;padding:24px"><div class="spinner"></div></div>';
  window.open(API + '/api/editor/' + jobId + '/chapters', '_blank');
  setTimeout(() => container.innerHTML = '<div style="text-align:center;padding:24px;color:var(--text-muted)">Opened editor in new tab</div>', 500);
}

// ==================== PROOFREADER ====================
async function runProofread() {
  const jobId = document.getElementById('proofJobId').value.trim();
  if (!jobId) { document.getElementById('proofResult').innerHTML = '<div style="color:var(--error);font-size:12px;margin-top:8px">Enter a Job ID</div>'; return; }
  const chapter = document.getElementById('proofChapter').value;
  const result = document.getElementById('proofResult');
  result.innerHTML = '<div style="text-align:center;padding:16px"><div class="spinner"></div> Running proofread...</div>';
  try {
    const path = chapter ? '/api/proofread/' + jobId + '/chapter/' + chapter : '/api/proofread/' + jobId;
    const data = await api(path, { method: 'POST' });
    result.innerHTML = '<pre style="font-size:12px;color:var(--text-secondary);white-space:pre-wrap;margin-top:8px">' + JSON.stringify(data, null, 2) + '</pre>';
  } catch(e) { result.innerHTML = '<div style="color:var(--error);font-size:12px">' + e.message + '</div>'; }
}

// ==================== BETA READER ====================
async function runBetaRead() {
  const jobId = document.getElementById('betaJobId').value.trim();
  if (!jobId) return;
  const result = document.getElementById('betaResult');
  result.innerHTML = '<div style="text-align:center;padding:16px"><div class="spinner"></div> Running beta read...</div>';
  try {
    const data = await api('/api/beta-read/' + jobId, { method: 'POST' });
    result.innerHTML = '<pre style="font-size:12px;color:var(--text-secondary);white-space:pre-wrap;margin-top:8px">' + JSON.stringify(data, null, 2) + '</pre>';
  } catch(e) { result.innerHTML = '<div style="color:var(--error);font-size:12px">' + e.message + '</div>'; }
}

// ==================== COACH ====================
let coachSessionId = null;

async function startCoaching() {
  const input = document.getElementById('coachInput').value.trim();
  if (!input) return;
  const content = document.getElementById('coachContent');
  content.innerHTML = '<div style="text-align:center;padding:16px"><div class="spinner"></div></div>';
  document.getElementById('coachBtn').disabled = true;
  try {
    const data = await api('/api/coach/start', { method: 'POST', body: JSON.stringify({ topic: input }) });
    coachSessionId = data.session_id || null;
    content.innerHTML = formatCoachResponse(data);
    document.getElementById('coachInput').value = '';
    document.getElementById('coachReplyArea').classList.remove('hidden');
  } catch(e) { content.innerHTML = '<div style="color:var(--error);font-size:12px">' + e.message + '</div>'; }
  document.getElementById('coachBtn').disabled = false;
}

async function coachReply() {
  const msg = document.getElementById('coachReply').value.trim();
  if (!msg || !coachSessionId) return;
  const content = document.getElementById('coachContent');
  content.innerHTML += '<div style="text-align:center;padding:8px"><div class="spinner"></div></div>';
  document.getElementById('coachReply').disabled = true;
  try {
    const data = await api('/api/coach/answer', { method: 'POST', body: JSON.stringify({ session_id: coachSessionId, answer: msg }) });
    content.innerHTML = content.innerHTML.replace('<div style="text-align:center;padding:8px"><div class="spinner"></div></div>', '');
    content.innerHTML += formatCoachResponse(data);
    document.getElementById('coachReply').value = '';
    document.getElementById('coachCard').scrollTop = document.getElementById('coachCard').scrollHeight;
  } catch(e) { content.innerHTML += '<div style="color:var(--error);font-size:12px">' + e.message + '</div>'; }
  document.getElementById('coachReply').disabled = false;
}

function coachNewSession() {
  coachSessionId = null;
  document.getElementById('coachContent').innerHTML = '<div style="font-size:13px;color:var(--text-muted)">Start a new coaching session.</div>';
  document.getElementById('coachReplyArea').classList.add('hidden');
  document.getElementById('coachInput').value = '';
  document.getElementById('coachReply').value = '';
}

function formatCoachResponse(data) {
  const msg = data.message || data.response || JSON.stringify(data, null, 2);
  const role = data.role || 'assistant';
  return `<div style="background:var(--bg);border:1px solid var(--border);border-radius:var(--radius-sm);padding:10px;margin-bottom:8px">
    <div style="font-size:10px;text-transform:uppercase;letter-spacing:.6px;color:var(--text-muted);margin-bottom:4px">${role}</div>
    <div style="font-size:13px;color:var(--text-secondary);white-space:pre-wrap">${msg}</div>
  </div>`;
}

// ==================== FORMAT CHECKER ====================
async function runFormatCheck() {
  const jobId = document.getElementById('formatJobId').value.trim();
  if (!jobId) return;
  const result = document.getElementById('formatResult');
  result.innerHTML = '<div style="text-align:center;padding:16px"><div class="spinner"></div></div>';
  try {
    const data = await api('/api/format-check/' + jobId);
    result.innerHTML = '<pre style="font-size:12px;color:var(--text-secondary);white-space:pre-wrap;margin-top:8px">' + JSON.stringify(data, null, 2) + '</pre>';
  } catch(e) { result.innerHTML = '<div style="color:var(--error);font-size:12px">' + e.message + '</div>'; }
}

// ==================== SERIES ====================
async function createSeries() {
  const name = document.getElementById('seriesName').value.trim();
  const desc = document.getElementById('seriesDesc').value.trim();
  if (!name) return;
  try {
    await api('/api/series', { method: 'POST', body: JSON.stringify({ name, description: desc }) });
    document.getElementById('seriesName').value = '';
    document.getElementById('seriesDesc').value = '';
    refreshSeries();
  } catch(e) { alert('Error: ' + e.message); }
}

async function refreshSeries() {
  const list = document.getElementById('seriesList');
  try {
    const data = await api('/api/series');
    if (!data || !data.length) { list.innerHTML = '<div style="font-size:12px;color:var(--text-muted)">No series yet</div>'; return; }
    list.innerHTML = data.map(s => `
      <div style="background:var(--bg);border:1px solid var(--border);border-radius:var(--radius-sm);padding:12px;margin-bottom:8px">
        <div style="font-weight:600;font-size:13px">${s.name}</div>
        <div style="font-size:11px;color:var(--text-muted)">${s.description || ''} · ${s.books ? s.books.length : 0} books</div>
      </div>
    `).join('');
  } catch(e) { list.innerHTML = '<div style="font-size:12px;color:var(--error)">Failed to load series</div>'; }
}

// ==================== LAUNCH PAGE ====================
async function generateLaunchPage() {
  const jobId = document.getElementById('launchJobId').value.trim();
  if (!jobId) return;
  const result = document.getElementById('launchResult');
  result.innerHTML = '<div style="text-align:center;padding:16px"><div class="spinner"></div></div>';
  try {
    const data = await api('/api/launch-page/' + jobId, { method: 'POST' });
    result.innerHTML = '<pre style="font-size:12px;color:var(--text-secondary);white-space:pre-wrap;margin-top:8px">' + JSON.stringify(data, null, 2) + '</pre>';
  } catch(e) { result.innerHTML = '<div style="color:var(--error);font-size:12px">' + e.message + '</div>'; }
}

// ==================== MARKETING ====================
async function generateMarketing() {
  const jobId = document.getElementById('mktJobId').value.trim();
  if (!jobId) return;
  const result = document.getElementById('mktResult');
  result.innerHTML = '<div style="text-align:center;padding:16px"><div class="spinner"></div></div>';
  try {
    const data = await api('/api/marketing/generate/' + jobId, { method: 'POST' });
    result.innerHTML = '<pre style="font-size:12px;color:var(--text-secondary);white-space:pre-wrap;margin-top:8px">' + JSON.stringify(data, null, 2) + '</pre>';
  } catch(e) { result.innerHTML = '<div style="color:var(--error);font-size:12px">' + e.message + '</div>'; }
}

// ==================== REVENUE ====================
function refreshRevenue() {
  const el = document.getElementById('revenueContent');
  let rev = JSON.parse(localStorage.getItem('publishing_revenue') || '[]');
  if (!rev.length) { el.innerHTML = '<div style="font-size:12px;color:var(--text-muted)">No revenue data. Add entries to track earnings.</div>'; return; }
  const total = rev.reduce((s, r) => s + (r.amount || 0), 0);
  el.innerHTML = `
    <div style="margin-bottom:12px"><strong style="font-size:18px">$${total.toFixed(2)}</strong> <span style="font-size:12px;color:var(--text-muted)">total earnings</span></div>
    <table><thead><tr><th>Book</th><th>Platform</th><th>Amount</th><th>Date</th></tr></thead>
    <tbody>${rev.slice(-20).reverse().map(r => `<tr><td>${r.book||'—'}</td><td>${r.platform||'—'}</td><td>$${(r.amount||0).toFixed(2)}</td><td style="font-size:11px">${r.date||'—'}</td></tr>`).join('')}</tbody></table>
  `;
}

// ==================== ADMIN ====================
async function adminRefresh() {
  try {
    const jobs = await api('/api/admin/jobs', { headers: { 'Authorization': 'Bearer ' + authToken } });
    const body = document.getElementById('adminBody');
    body.innerHTML = jobs.slice().reverse().map(j => `
      <tr>
        <td style="font-family:monospace;font-size:10px" title="${j.id}">${(j.id||'').slice(0,8)}...</td>
        <td style="max-width:100px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">${j.topic||'—'}</td>
        <td><span class="badge badge-${j.status === 'done' ? 'done' : j.status === 'failed' ? 'failed' : j.status === 'processing' ? 'processing' : 'queued'}">${j.status}</span></td>
        <td><div style="width:60px;height:4px;background:var(--border);border-radius:2px;overflow:hidden"><div style="height:100%;width:${j.progress||0}%;background:linear-gradient(90deg,var(--accent-1),var(--accent-3));border-radius:2px"></div></div></td>
        <td>${j.style||'—'}</td>
        <td style="font-size:11px">${j.created_at ? new Date(j.created_at).toLocaleString() : '—'}</td>
        <td>
          ${j.status === 'done' ? `<a class="btn btn-sm btn-primary" href="${API}/api/download/${j.id}?format=pdf" target="_blank" style="text-decoration:none;color:#fff;font-size:9px;padding:2px 6px">PDF</a>` : ''}
          ${j.status === 'done' ? `<a class="btn btn-sm btn-secondary" href="${API}/api/preview/${j.id}" target="_blank" style="text-decoration:none;font-size:9px;padding:2px 6px">Preview</a>` : ''}
          ${(j.status === 'queued' || j.status === 'processing') ? `<button class="btn btn-sm btn-error" onclick="cancelJob('${j.id}')" style="font-size:9px;padding:2px 6px">Cancel</button>` : ''}
          ${j.status === 'failed' ? `<button class="btn btn-sm btn-secondary" onclick="adminRetry('${j.id}')" style="font-size:9px;padding:2px 6px">Retry</button>` : ''}
          <button class="btn btn-sm btn-error" onclick="adminDelete('${j.id}')" style="font-size:9px;padding:2px 6px">✕</button>
        </td>
      </tr>
    `).join('');
    if (!jobs.length) body.innerHTML = '<tr><td colspan="7" style="text-align:center;padding:24px;color:var(--text-muted)">No jobs</td></tr>';
  } catch(e) {}
}

async function exportCSV() {
  try {
    const res = await fetch(API + '/api/admin/jobs/export', { headers: { 'Authorization': 'Bearer ' + authToken } });
    if (!res.ok) throw new Error('Export failed');
    const blob = await res.blob();
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url; a.download = 'jobs_export.csv'; a.click();
    URL.revokeObjectURL(url);
  } catch(e) { alert('Export error: ' + e.message); }
}

async function cancelJob(jobId) {
  try {
    await api('/api/cancel/' + jobId, { method: 'POST' });
    if (pollInterval) clearInterval(pollInterval);
    document.getElementById('progressSection').classList.remove('visible');
    showError('Cancelled', 'Job was cancelled');
    refreshHistory();
    adminRefresh();
    refreshDashboard();
  } catch(e) {}
}

async function adminDelete(jobId) {
  if (!confirm('Delete job?')) return;
  try { await api('/api/admin/jobs/' + jobId, { method: 'DELETE', headers: { 'Authorization': 'Bearer ' + authToken } }); adminRefresh(); } catch(e) {}
}
async function adminRetry(jobId) {
  try { await api('/api/admin/jobs/' + jobId + '/retry', { method: 'POST', headers: { 'Authorization': 'Bearer ' + authToken } }); adminRefresh(); } catch(e) {}
}

// ==================== TRANSLATION ====================
let selectedLangs = [];

async function loadLanguages() {
  const container = document.getElementById('langCheckboxes');
  try {
    const langs = await api('/api/languages');
    container.innerHTML = langs.map(l => `
      <label style="font-size:11px;display:flex;align-items:center;gap:4px;cursor:pointer">
        <input type="checkbox" value="${l.code || l}" onchange="toggleLang(this)"> ${l.name || l}
      </label>
    `).join('');
  } catch(e) {
    container.innerHTML = '<div style="font-size:11px;color:var(--text-muted)">Failed to load languages</div>';
  }
}

function toggleLang(el) {
  if (el.checked) selectedLangs.push(el.value);
  else selectedLangs = selectedLangs.filter(l => l !== el.value);
}

async function runTranslation() {
  const jobId = document.getElementById('transJobId').value.trim();
  const err = document.getElementById('transError');
  const result = document.getElementById('transResult');
  if (!jobId) { err.textContent = 'Enter a Job ID'; return; }
  if (!selectedLangs.length) { err.textContent = 'Select at least one language'; return; }
  err.textContent = '';
  result.innerHTML = '<div style="text-align:center;padding:16px"><div class="spinner"></div> Translating...</div>';
  document.getElementById('transBtn').disabled = true;
  try {
    const data = await api('/api/translate/' + jobId, { method: 'POST', body: JSON.stringify({ languages: selectedLangs }) });
    result.innerHTML = '<pre style="font-size:12px;color:var(--text-secondary);white-space:pre-wrap">' + JSON.stringify(data, null, 2) + '</pre>';
  } catch(e) { result.innerHTML = '<div style="color:var(--error);font-size:12px">' + e.message + '</div>'; }
  document.getElementById('transBtn').disabled = false;
}

// ==================== PUBLISHING ====================
async function genMetadata() {
  const jobId = document.getElementById('pubJobId').value.trim();
  const result = document.getElementById('pubResult');
  if (!jobId) { result.innerHTML = '<div style="color:var(--error);font-size:12px">Enter a Job ID</div>'; return; }
  result.innerHTML = '<div style="text-align:center;padding:16px"><div class="spinner"></div> Generating metadata...</div>';
  try {
    const data = await api('/api/publish/metadata/' + jobId, { method: 'POST' });
    result.innerHTML = '<pre style="font-size:12px;color:var(--text-secondary);white-space:pre-wrap">' + JSON.stringify(data, null, 2) + '</pre>';
  } catch(e) { result.innerHTML = '<div style="color:var(--error);font-size:12px">' + e.message + '</div>'; }
}

async function loadPlatforms() {
  const el = document.getElementById('pubPlatforms');
  el.innerHTML = '<div style="text-align:center;padding:8px"><div class="spinner"></div></div>';
  try {
    const data = await api('/api/publish/platforms');
    el.innerHTML = data.length ? data.map(p =>
      `<div style="background:var(--bg);border:1px solid var(--border);border-radius:var(--radius-sm);padding:8px;margin-bottom:6px;font-size:12px">${p.name || p.id || p}${p.url ? ' — <span style="color:var(--text-muted)">' + p.url + '</span>' : ''}</div>`
    ).join('') : '<div style="font-size:12px;color:var(--text-muted)">No platforms configured</div>';
  } catch(e) { el.innerHTML = '<div style="font-size:12px;color:var(--error)">Failed to load platforms</div>'; }
}

// ==================== BATCH ====================
let batchFiles = [];

document.addEventListener('DOMContentLoaded', () => {
  const dz = document.getElementById('batchDropZone');
  if (!dz) return;
  const fi = document.getElementById('batchFileInput');
  dz.addEventListener('click', () => fi.click());
  dz.addEventListener('dragover', e => { e.preventDefault(); dz.classList.add('dragover'); });
  dz.addEventListener('dragleave', () => dz.classList.remove('dragover'));
  dz.addEventListener('drop', e => { e.preventDefault(); dz.classList.remove('dragover'); handleBatchFiles(e.dataTransfer.files); });
  fi.addEventListener('change', () => handleBatchFiles(fi.files));
});

function handleBatchFiles(files) {
  batchFiles = [...files];
  document.getElementById('batchFileList').innerHTML = batchFiles.map(f => `<div style="font-size:11px;color:var(--accent-1);padding:2px 0">📄 ${f.name}</div>`).join('');
}

async function runBatch() {
  const result = document.getElementById('batchResult');
  if (!batchFiles.length) { result.innerHTML = '<div style="color:var(--error);font-size:12px">Drop or select files first</div>'; return; }
  const provider = document.getElementById('batchProvider').value;
  document.getElementById('batchBtn').disabled = true;
  result.innerHTML = '<div style="text-align:center;padding:16px"><div class="spinner"></div> Starting batch jobs...</div>';
  try {
    const formData = new FormData();
    batchFiles.forEach(f => formData.append('files', f));
    if (provider) formData.append('provider', provider);
    const res = await fetch(API + '/api/generate-batch', { method: 'POST', headers: authToken ? { 'Authorization': 'Bearer ' + authToken } : {}, body: formData });
    const data = await res.json();
    result.innerHTML = '<div style="font-size:13px;color:var(--text-secondary)">Batch started. ' + (data.jobs || data.job_ids || []).length + ' jobs created.</div>' +
      '<pre style="font-size:12px;color:var(--text-secondary);white-space:pre-wrap;margin-top:8px">' + JSON.stringify(data, null, 2) + '</pre>';
  } catch(e) { result.innerHTML = '<div style="color:var(--error);font-size:12px">' + e.message + '</div>'; }
  document.getElementById('batchBtn').disabled = false;
}

// ==================== AI THEME ====================
function showThemeGenerator() {
  const area = document.getElementById('themeGenArea');
  area.classList.toggle('hidden');
}

async function genTheme() {
  const prompt = document.getElementById('themePrompt').value.trim();
  const result = document.getElementById('themeResult');
  if (!prompt) { result.textContent = 'Describe a theme'; return; }
  result.innerHTML = '<div class="spinner"></div> Generating...';
  try {
    const data = await api('/api/themes/generate?description=' + encodeURIComponent(prompt), { method: 'POST' });
    result.innerHTML = '<span style="color:var(--success)">Theme created: ' + (data.name || data.id || 'done') + '</span>';
    loadTemplates(selectedType);
  } catch(e) { result.innerHTML = '<span style="color:var(--error)">' + e.message + '</span>'; }
}

// ==================== CUSTOM TEMPLATES ====================
function showCustomTemplates() {
  const area = document.getElementById('customTmplArea');
  area.classList.toggle('hidden');
  if (!area.classList.contains('hidden')) loadCustomTemplates();
}

async function loadCustomTemplates() {
  const list = document.getElementById('customTmplList');
  try {
    const data = await api('/api/templates/custom');
    if (!data || !data.length) { list.innerHTML = '<span style="color:var(--text-muted)">No custom templates uploaded</span>'; return; }
    list.innerHTML = data.map(t => `<div style="padding:4px 0;font-size:11px">📄 ${t.name || t}</div>`).join('');
  } catch(e) { list.innerHTML = '<span style="color:var(--error)">Failed to load</span>'; }
}

async function uploadTemplate() {
  const input = document.getElementById('customTmplInput');
  const file = input.files[0];
  const list = document.getElementById('customTmplList');
  if (!file) { list.innerHTML = '<span style="color:var(--error)">Select an HTML file</span>'; return; }
  list.innerHTML = '<div class="spinner"></div> Uploading...';
  try {
    const formData = new FormData();
    formData.append('file', file);
    const res = await fetch(API + '/api/templates/upload', { method: 'POST', body: formData });
    const data = await res.json();
    list.innerHTML = '<span style="color:var(--success)">Uploaded: ' + (data.name || 'ok') + '</span>';
    loadCustomTemplates();
  } catch(e) { list.innerHTML = '<span style="color:var(--error)">Upload failed</span>'; }
}

// ==================== EMBED ====================
function showEmbedCode(jobId) {
  const code = `<iframe src="${window.location.origin}/api/embed/${jobId}" width="100%" height="600" frameborder="0" style="border-radius:8px"></iframe>`;
  const el = document.createElement('div');
  el.style.cssText = 'position:fixed;inset:0;z-index:10000;background:rgba(0,0,0,.6);display:flex;align-items:center;justify-content:center';
  el.innerHTML = `<div style="background:var(--surface);border:1px solid var(--border);border-radius:var(--radius);padding:24px;max-width:600px;width:90%">
    <div style="font-size:14px;font-weight:600;margin-bottom:12px">🔗 Embed Code</div>
    <textarea style="width:100%;height:80px;font-family:monospace;font-size:11px;padding:8px;background:var(--bg);border:1px solid var(--border);border-radius:6px;color:var(--text-primary);resize:vertical" readonly onclick="this.select()">${code}</textarea>
    <div style="margin-top:10px;display:flex;gap:8px">
      <button class="btn btn-sm btn-primary" onclick="navigator.clipboard.writeText(this.parentElement.previousElementSibling.value);this.textContent='Copied!'">Copy</button>
      <button class="btn btn-sm btn-secondary" onclick="this.parentElement.parentElement.parentElement.remove()">Close</button>
    </div>
  </div>`;
  document.body.appendChild(el);
  el.addEventListener('click', e => { if (e.target === el) el.remove(); });
}

// ==================== INIT ====================
async function initApp() {
  document.querySelector('.sidebar-link[data-panel="dashboard"]').classList.add('active');
  document.getElementById('panel-dashboard').classList.add('active');
  document.getElementById('panelTitle').textContent = 'Dashboard';
  await loadProviders();
  await loadTemplates('ebook');
  loadFormats();
  refreshDashboard();
  refreshHistory();
  refreshSeries();
  refreshRevenue();
  loadLanguages();
  // Load batch providers
  try {
    const providers = await api('/api/providers');
    const sel = document.getElementById('batchProvider');
    if (sel) sel.innerHTML = providers.map(p => `<option value="${p.id}">${p.id}</option>`).join('');
  } catch(e) {}
  // Auto-refresh
  setInterval(refreshDashboard, 15000);
  setInterval(refreshHistory, 20000);
  setInterval(refreshSeries, 30000);
}

checkAuth().then(ok => { if (ok) initApp(); });
