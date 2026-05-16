/**
 * Easy-Study – Frontend Application JS
 * Chat, Flashcards, Quiz, Pomodoro Timer, Summary, Parallax
 */
const API = '';
const $ = (id) => document.getElementById(id);
const $$ = (sel) => document.querySelectorAll(sel);

// ── State ─────────────────────────────────────────────────
let selectedPdfFile = null, isQuerying = false, totalChunks = 0;
let fcCards = [], fcIndex = 0, fcRatings = {};
let quizQs = [], quizIdx = 0, quizScore = 0, quizAnswered = false;
let timerInterval = null, timerSeconds = 25 * 60, timerRunning = false;
let timerTotal = 25 * 60, pomodoroCount = 0;
let currentConversationId = '';

// ── Parallax Stars ────────────────────────────────────────
(function initParallax() {
  const field = $('parallax-field');
  if (!field) return;
  for (let i = 0; i < 60; i++) {
    const s = document.createElement('div');
    s.className = 'parallax-star';
    s.style.left = Math.random() * 100 + '%';
    s.style.top = Math.random() * 100 + '%';
    s.style.animationDelay = Math.random() * 3 + 's';
    s.style.width = s.style.height = (1 + Math.random() * 2) + 'px';
    field.appendChild(s);
  }
  document.addEventListener('mousemove', (e) => {
    const x = (e.clientX / window.innerWidth - 0.5) * 20;
    const y = (e.clientY / window.innerHeight - 0.5) * 20;
    field.style.transform = 'translate(' + x + 'px,' + y + 'px)';
  });
})();

// ── Utilities ─────────────────────────────────────────────
let toastT;
function showToast(msg, type) {
  clearTimeout(toastT);
  $('toast').textContent = msg;
  $('toast').className = 'toast show ' + (type || 'default');
  toastT = setTimeout(function() { $('toast').className = 'toast'; }, 3500);
}
function showLoading(msg) {
  $('loading-text').textContent = msg || 'Processing...';
  $('loading-overlay').classList.add('active');
}
function hideLoading() { $('loading-overlay').classList.remove('active'); }
function esc(s) {
  return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}
function renderMarkdown(text) {
  // Render markdown if marked.js is loaded, otherwise fall back to escaped text
  if (typeof marked !== 'undefined') {
    try { return marked.parse(String(text || '')); } catch(e) {}
  }
  return esc(text).replace(/\n/g, '<br>');
}

// ── Health Check ──────────────────────────────────────────
async function checkHealth() {
  try {
    var r = await fetch(API + '/api/health');
    var d = await r.json();
    $('status-pill').textContent = '✅ Online';
    $('status-pill').className = 'pill online';
    // Also fetch active model
    try {
      var mr = await fetch(API + '/api/models/active');
      var md = await mr.json();
      var provIcons = { ollama: '🖥️', openai: '💎', gemini: '✨', openrouter: '🌐' };
      var icon = provIcons[md.provider] || '🤖';
      $('model-pill').textContent = icon + ' ' + md.model;
    } catch(e2) {
      $('model-pill').textContent = '🤖 ' + (d.components && d.components.ollama_model || 'llama3');
    }
  } catch(e) {
    $('status-pill').textContent = '🔴 Offline';
    $('status-pill').className = 'pill offline';
  }
}
checkHealth();
setInterval(checkHealth, 60000);

// ── Model Switcher ────────────────────────────────────────
(function initModelSwitcher() {
  var pill = $('model-pill');
  var dropdown = $('model-dropdown');
  var switcher = $('model-switcher');
  if (!pill || !dropdown) return;

  // Toggle dropdown
  pill.addEventListener('click', function(e) {
    e.stopPropagation();
    dropdown.classList.toggle('open');
    // Load available models on open
    if (dropdown.classList.contains('open')) loadAvailableModels();
  });

  // Close on outside click
  document.addEventListener('click', function(e) {
    if (!switcher.contains(e.target)) dropdown.classList.remove('open');
  });

  // Model option click
  dropdown.addEventListener('click', async function(e) {
    var btn = e.target.closest('.model-option');
    if (!btn || btn.classList.contains('disabled')) return;
    var provider = btn.dataset.provider;
    var model = btn.dataset.model;
    showLoading('Switching to ' + provider + ' / ' + model + '...');
    try {
      var r = await fetch(API + '/api/models/switch', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ provider: provider, model: model })
      });
      var d = await r.json();
      if (!r.ok) throw new Error(d.detail || 'Switch failed');
      // Update UI
      dropdown.querySelectorAll('.model-option').forEach(function(b) { b.classList.remove('active'); });
      btn.classList.add('active');
      var provIcons = { ollama: '🖥️', openai: '💎', gemini: '✨', openrouter: '🌐' };
      pill.textContent = (provIcons[d.provider] || '🤖') + ' ' + d.model;
      dropdown.classList.remove('open');
      showToast('✅ Switched to ' + d.provider + ' / ' + d.model, 'success');
    } catch(e2) {
      showToast('❌ ' + e2.message, 'error');
    } finally {
      hideLoading();
    }
  });

  async function loadAvailableModels() {
    try {
      var r = await fetch(API + '/api/models');
      var d = await r.json();
      if (!d.providers) return;
      // Mark unavailable providers
      Object.keys(d.providers).forEach(function(prov) {
        var group = $('provider-' + prov);
        if (!group) return;
        var avail = d.providers[prov].available;
        group.querySelectorAll('.model-option').forEach(function(btn) {
          if (!avail) {
            btn.classList.add('disabled');
            btn.title = prov + ' not configured';
          } else {
            btn.classList.remove('disabled');
            btn.title = '';
          }
        });
        // Show not configured label
        var label = group.querySelector('.model-provider-label');
        if (label && !avail) {
          label.innerHTML = label.textContent + ' <span class="not-configured">(not configured)</span>';
        }
      });
      // Mark active
      if (d.active) {
        dropdown.querySelectorAll('.model-option').forEach(function(btn) {
          btn.classList.remove('active');
          if (btn.dataset.provider === d.active.provider && 
              (btn.dataset.model === d.active.model || btn.dataset.model.startsWith(d.active.model + ':'))) {
            btn.classList.add('active');
          }
        });
      }
    } catch(e) { /* ignore */ }
  }
})();

// ── Navigation ────────────────────────────────────────────
$$('.nav-btn').forEach(function(btn) {
  btn.addEventListener('click', function() {
    $$('.nav-btn').forEach(function(n) { n.classList.remove('active'); });
    $$('.view').forEach(function(v) { v.classList.remove('active'); });
    btn.classList.add('active');
    var view = $('view-' + btn.dataset.view);
    if (view) view.classList.add('active');
  });
});

// ── Tab Switching ─────────────────────────────────────────
$$('.tab').forEach(function(btn) {
  btn.addEventListener('click', function() {
    $$('.tab').forEach(function(b) { b.classList.remove('active'); });
    $$('.tab-content').forEach(function(c) { c.classList.remove('active'); });
    btn.classList.add('active');
    var el = $('content-' + btn.dataset.tab);
    if (el) el.classList.add('active');
  });
});

// ── PDF Drag & Drop ───────────────────────────────────────
var pdfDrop = $('pdf-drop-zone');
var pdfInput = $('pdf-file-input');
pdfDrop.addEventListener('click', function() { pdfInput.click(); });
['dragover','dragenter'].forEach(function(ev) {
  pdfDrop.addEventListener(ev, function(e) { e.preventDefault(); pdfDrop.classList.add('drag-over'); });
});
['dragleave','dragend','drop'].forEach(function(ev) {
  pdfDrop.addEventListener(ev, function() { pdfDrop.classList.remove('drag-over'); });
});
pdfDrop.addEventListener('drop', function(e) {
  e.preventDefault();
  var f = e.dataTransfer.files[0];
  if (f && f.type === 'application/pdf') selectPdf(f);
  else showToast('Please drop a valid PDF', 'error');
});
pdfInput.addEventListener('change', function() {
  if (pdfInput.files[0]) selectPdf(pdfInput.files[0]);
});
function selectPdf(f) {
  selectedPdfFile = f;
  pdfDrop.classList.add('file-selected');
  pdfDrop.querySelector('.drop-label').innerHTML = '📄 <strong>' + esc(f.name) + '</strong>';
  pdfDrop.querySelector('.drop-sub').textContent = (f.size / 1024).toFixed(1) + ' KB';
  $('btn-upload-pdf').disabled = false;
}

// ── Upload PDF ────────────────────────────────────────────
$('btn-upload-pdf').addEventListener('click', async function() {
  if (!selectedPdfFile) return;
  showLoading('Extracting & embedding PDF...');
  try {
    var fd = new FormData();
    fd.append('file', selectedPdfFile);
    fd.append('source_type', 'pdf');
    var r = await fetch(API + '/api/upload', { method: 'POST', body: fd });
    var d = await r.json();
    if (!r.ok) throw new Error(d.detail || 'Upload failed');
    addSource(d, 'pdf', selectedPdfFile.name);
    showToast('✅ ' + selectedPdfFile.name + ' uploaded!', 'success');
    selectedPdfFile = null;
    pdfDrop.classList.remove('file-selected');
    pdfDrop.querySelector('.drop-label').innerHTML = 'Drop PDF here or <span class="link-text">browse</span>';
    pdfDrop.querySelector('.drop-sub').textContent = 'Supports multi-page PDFs';
    $('btn-upload-pdf').disabled = true;
    pdfInput.value = '';
  } catch(e) { showToast('❌ ' + e.message, 'error'); }
  finally { hideLoading(); }
});

// ── Ingest URL / YouTube ──────────────────────────────────
async function ingestUrl(url, label) {
  showLoading('Fetching ' + label + '...');
  try {
    var r = await fetch(API + '/api/ingest/url', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ url: url })
    });
    var d = await r.json();
    if (!r.ok) throw new Error(d.detail || 'Failed');
    addSource(d, d.detected_type || 'url', url);
    showToast('✅ ' + label + ' ingested!', 'success');
    return true;
  } catch(e) { showToast('❌ ' + e.message, 'error'); return false; }
  finally { hideLoading(); }
}
$('btn-ingest-url').addEventListener('click', async function() {
  var u = $('url-input').value.trim();
  if (!u) return showToast('Enter a URL', 'error');
  if (await ingestUrl(u, 'Article')) $('url-input').value = '';
});
$('btn-ingest-yt').addEventListener('click', async function() {
  var u = $('yt-input').value.trim();
  if (!u) return showToast('Enter a YouTube URL', 'error');
  if (await ingestUrl(u, 'YouTube video')) $('yt-input').value = '';
});

// ── Ingest Text ───────────────────────────────────────────
$('btn-ingest-text').addEventListener('click', async function() {
  var txt = $('notes-text').value.trim();
  var title = $('notes-title').value.trim() || 'My Notes';
  if (!txt) return showToast('Enter some text', 'error');
  showLoading('Embedding notes...');
  try {
    var r = await fetch(API + '/api/ingest/text', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ text: txt, title: title })
    });
    var d = await r.json();
    if (!r.ok) throw new Error(d.detail || 'Failed');
    addSource(d, 'text', title);
    showToast('✅ Notes saved!', 'success');
    $('notes-text').value = '';
  } catch(e) { showToast('❌ ' + e.message, 'error'); }
  finally { hideLoading(); }
});

function addSource(d, type, name) {
  totalChunks += d.chunks_created || 0;
  $('chunk-count').textContent = totalChunks + ' chunks';
  var icons = { pdf: '📄', url: '🌐', youtube: '▶️', text: '📝' };
  var sl = $('sources-list');
  var em = sl.querySelector('.source-empty');
  if (em) em.remove();
  var li = document.createElement('li');
  li.className = 'source-item';
  var short = name.length > 38 ? name.slice(0, 35) + '...' : name;
  li.innerHTML = '<span class="source-icon">' + (icons[type] || '📎') + '</span>' +
    '<div class="source-info"><div class="source-name" title="' + esc(name) + '">' + esc(short) + '</div>' +
    '<div class="source-meta">' + (d.chunks_created || 0) + ' chunks • ' + type.toUpperCase() + '</div></div>';
  sl.prepend(li);
}

// ── Chat (SSE Streaming — tokens appear in real-time) ─────
async function sendQuery() {
  if (isQuerying) return;
  var question = $('query-input').value.trim();
  if (!question) return;
  isQuerying = true;
  $('btn-send').disabled = true;
  $('query-input').value = '';
  var welcome = $('chat-messages').querySelector('.welcome-card');
  if (welcome) welcome.remove();
  appendMsg('user', question);

  // Build streaming URL
  var params = new URLSearchParams({
    question: question,
    top_k: $('topk-select').value,
    conversation_id: currentConversationId || ''
  });
  var streamUrl = API + '/api/query/stream?' + params.toString();

  // Create AI message bubble immediately (optimistic UI)
  var aiDiv = document.createElement('div');
  aiDiv.className = 'message ai';
  aiDiv.innerHTML = '<div class="msg-avatar">🧠</div><div class="msg-body">' +
    '<div class="msg-bubble"><div class="typing-dots"><div class="dot"></div><div class="dot"></div><div class="dot"></div></div></div>' +
    '<div class="msg-meta"></div></div>';
  $('chat-messages').appendChild(aiDiv);
  scrollChat();

  var bubbleEl = aiDiv.querySelector('.msg-bubble');
  var metaEl = aiDiv.querySelector('.msg-meta');
  var fullText = '';
  var metaData = {};

  try {
    var response = await fetch(streamUrl);
    if (!response.ok) {
      var errData = await response.json().catch(function() { return {}; });
      throw new Error(errData.detail || 'Query failed (' + response.status + ')');
    }

    var reader = response.body.getReader();
    var decoder = new TextDecoder();
    var buffer = '';

    while (true) {
      var result = await reader.read();
      if (result.done) break;
      buffer += decoder.decode(result.value, { stream: true });

      // Parse SSE lines
      var lines = buffer.split('\n');
      buffer = lines.pop(); // Keep incomplete line in buffer

      for (var i = 0; i < lines.length; i++) {
        var line = lines[i].trim();
        if (!line.startsWith('data: ')) continue;
        var jsonStr = line.slice(6);
        var evt;
        try { evt = JSON.parse(jsonStr); } catch(pe) { continue; }

        if (evt.type === 'cached') {
          // Full cached response — render immediately
          aiDiv.remove();
          evt.cached = true;
          evt.question = question;
          appendAI(evt);
          isQuerying = false;
          $('btn-send').disabled = false;
          $('query-input').focus();
          return;
        }

        if (evt.type === 'meta') {
          metaData = evt;
          // Show metadata tags immediately
          var provIcons = { ollama: '🖥️', openai: '💎', gemini: '✨', openrouter: '🌐' };
          var provName = evt.provider || 'unknown';
          var provIcon = provIcons[provName] || '🧠';
          var sourceType = (evt.source || '').includes('_rag') ? 'RAG' : (evt.source || '').includes('_direct') ? 'Direct' : 'AI';
          var srcTag = '<span class="meta-chip rag">' + provIcon + ' ' + sourceType + '</span>';
          var modelTag = evt.model ? '<span class="meta-chip model-chip">📦 ' + esc(evt.model) + '</span>' : '';
          var confTag = evt.confidence > 0 ? '<span class="meta-chip conf">Conf: ' + (evt.confidence * 100).toFixed(0) + '%</span>' : '';
          metaEl.innerHTML = srcTag + modelTag + confTag;
          // Replace typing dots with empty text (tokens will fill it)
          bubbleEl.innerHTML = '';
        }

        if (evt.type === 'token') {
          fullText += evt.content;
          // Render markdown progressively
          bubbleEl.innerHTML = renderMarkdown(fullText);
          scrollChat();
        }

        if (evt.type === 'error') {
          bubbleEl.innerHTML = '<span style="color:var(--red)">❌ ' + esc(evt.content) + '</span>';
          showToast('Query failed', 'error');
        }

        if (evt.type === 'done') {
          // Final render with markdown
          if (fullText) bubbleEl.innerHTML = renderMarkdown(fullText);
          // Add source chips
          if (metaData.sources && metaData.sources.length > 0) {
            var sid = 'src-' + Date.now();
            var chips = metaData.sources.map(function(s) {
              return '<div class="source-chip"><strong>' + esc(s.source_type || '?').toUpperCase() +
                '</strong> · ' + esc(s.source_name || '') + ' · score: ' + (s.score || '?') +
                '<br><span style="opacity:.6">' + esc(s.preview || '') + '</span></div>';
            }).join('');
            var srcHtml = '<button class="msg-sources-toggle" onclick="toggleSrc(this,\'' + sid + '\')">📎 View ' +
              metaData.sources.length + ' source(s) ▾</button><div class="msg-sources" id="' + sid + '" style="display:none">' + chips + '</div>';
            aiDiv.querySelector('.msg-body').insertAdjacentHTML('beforeend', srcHtml);
          }
          scrollChat();
        }
      }
    }
  } catch(e) {
    // Fallback: if streaming fails, try regular POST endpoint
    aiDiv.remove();
    var typingId = appendTyping();
    try {
      var r = await fetch(API + '/api/query', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ question: question, top_k: parseInt($('topk-select').value), conversation_id: currentConversationId })
      });
      var d = await r.json();
      removeTyping(typingId);
      if (!r.ok) throw new Error(d.detail || 'Query failed');
      appendAI(d);
    } catch(e2) {
      removeTyping(typingId);
      appendMsg('ai', '❌ Error: ' + e2.message, true);
      showToast('Query failed', 'error');
    }
  } finally {
    isQuerying = false;
    $('btn-send').disabled = false;
    $('query-input').focus();
  }
}
$('query-input').addEventListener('keydown', function(e) {
  if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); sendQuery(); }
});
$('btn-send').addEventListener('click', sendQuery);

function appendMsg(role, text, isError) {
  var div = document.createElement('div');
  div.className = 'message ' + role;
  var avatar = role === 'user' ? '👤' : '🧠';
  div.innerHTML = '<div class="msg-avatar">' + avatar + '</div>' +
    '<div class="msg-body"><div class="msg-bubble' + (isError ? ' error' : '') + '">' +
    esc(text).replace(/\n/g, '<br>') + '</div></div>';
  $('chat-messages').appendChild(div);
  scrollChat();
}
function appendAI(d) {
  var provIcons = { ollama: '🖥️', openai: '💎', gemini: '✨', openrouter: '🌐' };
  var provName = d.provider || 'unknown';
  var provIcon = provIcons[provName] || '🧠';
  var sourceType = (d.source || '').includes('_rag') ? 'RAG' : (d.source || '').includes('_direct') ? 'Direct' : 'AI';
  var srcTag = '<span class="meta-chip rag">' + provIcon + ' ' + sourceType + '</span>';
  var modelTag = d.model
    ? '<span class="meta-chip model-chip">📦 ' + esc(d.model) + '</span>' : '';
  var confTag = d.confidence !== undefined && d.confidence > 0
    ? '<span class="meta-chip conf">Conf: ' + (d.confidence * 100).toFixed(0) + '%</span>' : '';
  var srcHtml = '';
  if (d.sources && d.sources.length > 0) {
    var sid = 'src-' + Date.now();
    var chips = d.sources.map(function(s) {
      return '<div class="source-chip"><strong>' + esc(s.source_type || '?').toUpperCase() +
        '</strong> · ' + esc(s.source_name || '') + ' · score: ' + (s.score || '?') +
        '<br><span style="opacity:.6">' + esc(s.preview || '') + '</span></div>';
    }).join('');
    srcHtml = '<button class="msg-sources-toggle" onclick="toggleSrc(this,\'' + sid + '\')">📎 View ' +
      d.sources.length + ' source(s) ▾</button><div class="msg-sources" id="' + sid + '" style="display:none">' + chips + '</div>';
  }
  var cacheTag = d.cached ? '<span class="meta-chip rag">⚡ Cached</span>' : '';
  var div = document.createElement('div');
  div.className = 'message ai';
  div.innerHTML = '<div class="msg-avatar">🧠</div><div class="msg-body">' +
    '<div class="msg-bubble">' + renderMarkdown(d.answer || 'No answer.') + '</div>' +
    '<div class="msg-meta">' + srcTag + modelTag + confTag + cacheTag + '</div>' + srcHtml + '</div>';
  $('chat-messages').appendChild(div);
  scrollChat();
}
window.toggleSrc = function(btn, id) {
  var p = document.getElementById(id);
  if (!p) return;
  var open = p.style.display !== 'none';
  p.style.display = open ? 'none' : 'flex';
  btn.textContent = open ? '📎 View sources ▾' : '📎 Hide sources ▴';
};
function appendTyping() {
  var id = 'typing-' + Date.now();
  var div = document.createElement('div');
  div.className = 'message ai'; div.id = id;
  div.innerHTML = '<div class="msg-avatar">🧠</div><div class="msg-body"><div class="msg-bubble">' +
    '<div class="typing-dots"><div class="dot"></div><div class="dot"></div><div class="dot"></div></div></div></div>';
  $('chat-messages').appendChild(div);
  scrollChat();
  return id;
}
function removeTyping(id) { var el = document.getElementById(id); if (el) el.remove(); }
function scrollChat() { $('chat-messages').scrollTo({ top: $('chat-messages').scrollHeight, behavior: 'smooth' }); }

// ── Flashcards ────────────────────────────────────────────
$('btn-gen-flashcards').addEventListener('click', async function() {
  var topic = $('fc-topic').value.trim() || null;
  var count = parseInt($('fc-count').value);
  showLoading('Generating ' + count + ' flashcards...');
  try {
    var r = await fetch(API + '/api/generate/flashcards', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ topic: topic, count: count })
    });
    var d = await r.json();
    if (!r.ok) throw new Error(d.detail || 'Generation failed');
    fcCards = d.flashcards || [];
    fcIndex = 0;
    fcRatings = {};
    if (fcCards.length === 0) throw new Error('No flashcards generated');
    $('fc-deck-area').style.display = 'block';
    $('fc-controls').style.display = 'none';
    renderFC();
    showToast('✅ ' + fcCards.length + ' flashcards generated!', 'success');
  } catch(e) { showToast('❌ ' + e.message, 'error'); }
  finally { hideLoading(); }
});

function renderFC() {
  if (!fcCards.length) return;
  var card = fcCards[fcIndex];
  $('fc-front-text').textContent = card.front;
  $('fc-back-text').textContent = card.back;
  $('fc-card-inner').classList.remove('flipped');
  $('fc-progress-text').textContent = (fcIndex + 1) + ' / ' + fcCards.length;
  $('fc-progress-fill').style.width = ((fcIndex + 1) / fcCards.length * 100) + '%';
  updateMastery();
}
$('fc-card').addEventListener('click', function() {
  $('fc-card-inner').classList.toggle('flipped');
});
$('fc-prev').addEventListener('click', function() {
  if (fcIndex > 0) { fcIndex--; renderFC(); }
});
$('fc-next').addEventListener('click', function() {
  if (fcIndex < fcCards.length - 1) { fcIndex++; renderFC(); }
});
$$('.fc-rate').forEach(function(btn) {
  btn.addEventListener('click', function() {
    fcRatings[fcIndex] = btn.dataset.rate;
    updateMastery();
    if (fcIndex < fcCards.length - 1) { fcIndex++; renderFC(); }
  });
});
$('fc-shuffle').addEventListener('click', function() {
  for (var i = fcCards.length - 1; i > 0; i--) {
    var j = Math.floor(Math.random() * (i + 1));
    var tmp = fcCards[i]; fcCards[i] = fcCards[j]; fcCards[j] = tmp;
  }
  fcIndex = 0; fcRatings = {}; renderFC();
  showToast('🔀 Shuffled!', 'success');
});
$('fc-restart').addEventListener('click', function() {
  fcIndex = 0; fcRatings = {};
  $('fc-deck-area').style.display = 'none';
  $('fc-controls').style.display = 'block';
});
function updateMastery() {
  var total = fcCards.length, easy = 0;
  for (var k in fcRatings) { if (fcRatings[k] === 'easy') easy++; }
  $('fc-mastery').textContent = 'Mastery: ' + (total ? Math.round(easy / total * 100) : 0) + '%';
}

// ── Quiz ──────────────────────────────────────────────────
$('btn-gen-quiz').addEventListener('click', async function() {
  var topic = $('quiz-topic').value.trim() || null;
  var count = parseInt($('quiz-count').value);
  showLoading('Generating ' + count + ' quiz questions...');
  try {
    var r = await fetch(API + '/api/generate/quiz', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ topic: topic, count: count })
    });
    var d = await r.json();
    if (!r.ok) throw new Error(d.detail || 'Generation failed');
    quizQs = d.questions || [];
    quizIdx = 0; quizScore = 0; quizAnswered = false;
    if (quizQs.length === 0) throw new Error('No questions generated');
    $('quiz-area').style.display = 'block';
    $('quiz-controls').style.display = 'none';
    $('quiz-score').style.display = 'none';
    $('quiz-card').style.display = 'block';
    renderQuiz();
    showToast('✅ ' + quizQs.length + ' questions generated!', 'success');
  } catch(e) { showToast('❌ ' + e.message, 'error'); }
  finally { hideLoading(); }
});

function renderQuiz() {
  var q = quizQs[quizIdx];
  quizAnswered = false;
  $('quiz-progress-text').textContent = 'Question ' + (quizIdx + 1) + ' of ' + quizQs.length;
  $('quiz-progress-fill').style.width = ((quizIdx + 1) / quizQs.length * 100) + '%';
  $('quiz-question').textContent = (quizIdx + 1) + '. ' + q.question;
  $('quiz-explanation').style.display = 'none';
  $('quiz-next-btn').style.display = 'none';
  var opts = $('quiz-options');
  opts.innerHTML = '';
  var letters = ['A', 'B', 'C', 'D'];
  q.options.forEach(function(opt, i) {
    var btn = document.createElement('button');
    btn.className = 'quiz-option';
    btn.innerHTML = '<span class="quiz-option-letter">' + letters[i] + '</span>' + esc(opt);
    btn.addEventListener('click', function() { answerQuiz(i); });
    opts.appendChild(btn);
  });
}
function answerQuiz(idx) {
  if (quizAnswered) return;
  quizAnswered = true;
  var q = quizQs[quizIdx];
  var btns = $$('.quiz-option');
  btns.forEach(function(b, i) {
    b.classList.add('disabled');
    if (i === q.correct) b.classList.add('correct');
    if (i === idx && idx !== q.correct) b.classList.add('wrong');
  });
  if (idx === q.correct) quizScore++;
  $('quiz-expl-text').textContent = q.explanation || 'No explanation available.';
  $('quiz-explanation').style.display = 'block';
  if (quizIdx < quizQs.length - 1) {
    $('quiz-next-btn').style.display = 'block';
    $('quiz-next-btn').textContent = 'Next Question →';
  } else {
    $('quiz-next-btn').style.display = 'block';
    $('quiz-next-btn').textContent = 'See Results →';
  }
}
$('quiz-next-btn').addEventListener('click', function() {
  if (quizIdx < quizQs.length - 1) { quizIdx++; renderQuiz(); }
  else { showQuizScore(); }
});
function showQuizScore() {
  $('quiz-card').style.display = 'none';
  $('quiz-score').style.display = 'block';
  var pct = Math.round(quizScore / quizQs.length * 100);
  $('score-value').textContent = quizScore + ' / ' + quizQs.length;
  $('score-percent').textContent = pct + '%';
  $('score-bar-fill').style.width = pct + '%';
  $('score-icon').textContent = pct >= 80 ? '🏆' : pct >= 50 ? '🎯' : '📚';
}
$('quiz-retry').addEventListener('click', function() {
  $('quiz-area').style.display = 'none';
  $('quiz-controls').style.display = 'block';
});

// ── Pomodoro Timer ────────────────────────────────────────
function formatTime(s) {
  return String(Math.floor(s / 60)).padStart(2, '0') + ':' + String(s % 60).padStart(2, '0');
}
function updateTimerDisplay() {
  $('timer-time').textContent = formatTime(timerSeconds);
  var circumference = 2 * Math.PI * 90;
  var offset = circumference * (1 - timerSeconds / timerTotal);
  var ring = $('timer-ring-progress');
  if (ring) ring.style.strokeDashoffset = offset;
}
$$('.timer-mode-btn').forEach(function(btn) {
  btn.addEventListener('click', function() {
    if (timerRunning) return;
    $$('.timer-mode-btn').forEach(function(b) { b.classList.remove('active'); });
    btn.classList.add('active');
    var mins = parseInt(btn.dataset.duration);
    timerTotal = mins * 60;
    timerSeconds = timerTotal;
    $('timer-mode').textContent = mins === 25 ? 'FOCUS' : mins === 5 ? 'SHORT BREAK' : 'LONG BREAK';
    updateTimerDisplay();
  });
});
$('timer-start').addEventListener('click', function() {
  if (timerRunning) {
    clearInterval(timerInterval);
    timerRunning = false;
    $('timer-start').textContent = '▶ Start';
    return;
  }
  timerRunning = true;
  $('timer-start').textContent = '⏸ Pause';
  timerInterval = setInterval(function() {
    timerSeconds--;
    updateTimerDisplay();
    if (timerSeconds <= 0) {
      clearInterval(timerInterval);
      timerRunning = false;
      $('timer-start').textContent = '▶ Start';
      pomodoroCount++;
      updateSessionDots();
      showToast('⏰ Timer complete!', 'success');
      try { new Audio('data:audio/wav;base64,UklGRnoGAABXQVZFZm10IBAAAAABAAEAQB8AAEAfAAABAAgAZGF0YQ==').play(); } catch(e) {}
    }
  }, 1000);
});
$('timer-reset').addEventListener('click', function() {
  clearInterval(timerInterval);
  timerRunning = false;
  var activeMode = document.querySelector('.timer-mode-btn.active');
  timerTotal = parseInt(activeMode ? activeMode.dataset.duration : 25) * 60;
  timerSeconds = timerTotal;
  $('timer-start').textContent = '▶ Start';
  updateTimerDisplay();
});
function updateSessionDots() {
  var dots = $$('.session-dot');
  dots.forEach(function(d, i) {
    d.classList.toggle('filled', i < pomodoroCount);
  });
  $('timer-session-count').textContent = pomodoroCount + ' / 4';
}
updateTimerDisplay();

// Custom time input
$('timer-custom-set').addEventListener('click', function() {
  if (timerRunning) return;
  var mins = parseInt($('timer-custom-minutes').value);
  if (!mins || mins < 1) mins = 1;
  if (mins > 180) mins = 180;
  $('timer-custom-minutes').value = mins;
  timerTotal = mins * 60;
  timerSeconds = timerTotal;
  // Deactivate preset buttons
  $$('.timer-mode-btn').forEach(function(b) { b.classList.remove('active'); });
  $('timer-mode').textContent = 'CUSTOM ' + mins + 'M';
  updateTimerDisplay();
});
// Also set on Enter key
$('timer-custom-minutes').addEventListener('keydown', function(e) {
  if (e.key === 'Enter') { e.preventDefault(); $('timer-custom-set').click(); }
});
// Sync custom input when preset is clicked
$$('.timer-mode-btn').forEach(function(btn) {
  btn.addEventListener('click', function() {
    $('timer-custom-minutes').value = btn.dataset.duration;
  });
});

// ── Summary ───────────────────────────────────────────────
$('btn-gen-summary').addEventListener('click', async function() {
  var topic = $('summary-topic').value.trim() || null;
  var length = $('summary-length').value;
  showLoading('Generating ' + length + ' summary...');
  try {
    var r = await fetch(API + '/api/generate/summary', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ topic: topic, length: length })
    });
    var d = await r.json();
    if (!r.ok) throw new Error(d.detail || 'Generation failed');
    $('summary-result').style.display = 'block';
    $('summary-result-title').textContent = '📋 Summary: ' + (d.topic || 'General');
    $('summary-text').textContent = d.summary || 'No summary generated.';
    var kpList = $('keypoints-list');
    kpList.innerHTML = '';
    (d.key_points || []).forEach(function(kp) {
      var li = document.createElement('li');
      li.textContent = kp;
      kpList.appendChild(li);
    });
    showToast('✅ Summary generated!', 'success');
  } catch(e) { showToast('❌ ' + e.message, 'error'); }
  finally { hideLoading(); }
});

// ── Keyboard Shortcuts ────────────────────────────────────
document.addEventListener('keydown', function(e) {
  // Don't trigger shortcuts when typing in inputs
  var tag = (e.target.tagName || '').toLowerCase();
  if (tag === 'input' || tag === 'textarea' || tag === 'select') return;

  var activeView = document.querySelector('.view.active');
  var viewId = activeView ? activeView.id : '';

  // Flashcard shortcuts
  if (viewId === 'view-flashcards' && fcCards.length > 0) {
    if (e.key === 'ArrowLeft') { e.preventDefault(); if (fcIndex > 0) { fcIndex--; renderFC(); } }
    if (e.key === 'ArrowRight') { e.preventDefault(); if (fcIndex < fcCards.length - 1) { fcIndex++; renderFC(); } }
    if (e.key === ' ') { e.preventDefault(); $('fc-card-inner').classList.toggle('flipped'); }
  }

  // "/" to focus chat input
  if (e.key === '/' && viewId === 'view-chat') {
    e.preventDefault();
    $('query-input').focus();
  }
});

// ── Chat History (localStorage) ───────────────────────────
function saveChatHistory() {
  try {
    var msgs = $('chat-messages');
    if (msgs) localStorage.setItem('easy-study-chat', msgs.innerHTML);
  } catch(e) {}
}
function loadChatHistory() {
  try {
    var saved = localStorage.getItem('easy-study-chat');
    if (saved && saved.length > 100) {
      $('chat-messages').innerHTML = saved;
    }
  } catch(e) {}
}
// Load on start
loadChatHistory();
// Save after each AI response (hook into scrollChat)
var _origScrollChat = scrollChat;
scrollChat = function() {
  _origScrollChat();
  saveChatHistory();
};

// ── Conversation Management (Claude-like) ─────────────────
async function createNewChat() {
  try {
    var r = await fetch(API + '/api/conversations', { method: 'POST' });
    var d = await r.json();
    currentConversationId = d.id;
    // Clear chat messages and show welcome
    $('chat-messages').innerHTML = '<div class="welcome-card glass">' +
      '<div class="welcome-icon">🧠</div>' +
      '<h1 class="welcome-title">Easy-Study AI</h1>' +
      '<p class="welcome-desc">Upload your study materials, then ask me anything.</p>' +
      '</div>';
    refreshChatList();
    $('query-input').focus();
  } catch(e) { console.error('Failed to create conversation', e); }
}

async function refreshChatList() {
  try {
    var r = await fetch(API + '/api/conversations?limit=20');
    var d = await r.json();
    var list = $('chat-history-list');
    if (!d.conversations || d.conversations.length === 0) {
      list.innerHTML = '<li class="chat-history-empty">No conversations yet</li>';
      return;
    }
    list.innerHTML = d.conversations.map(function(c) {
      var isActive = c.id === currentConversationId;
      var time = c.updated_at ? new Date(c.updated_at).toLocaleTimeString([], {hour:'2-digit',minute:'2-digit'}) : '';
      return '<li class="chat-history-item' + (isActive ? ' active' : '') + '" data-id="' + c.id + '">' +
        '<span class="chat-icon">💬</span>' +
        '<span class="chat-title">' + esc(c.title || 'New Chat') + '</span>' +
        '<span class="chat-time">' + time + '</span>' +
        '<span class="chat-delete" data-id="' + c.id + '" title="Delete">✕</span>' +
        '</li>';
    }).join('');
  } catch(e) { /* ignore */ }
}

async function loadConversation(convId) {
  try {
    currentConversationId = convId;
    var r = await fetch(API + '/api/conversations/' + convId);
    var d = await r.json();
    $('chat-messages').innerHTML = '';
    if (!d.messages || d.messages.length === 0) {
      $('chat-messages').innerHTML = '<div class="welcome-card glass">' +
        '<div class="welcome-icon">🧠</div><h1 class="welcome-title">Easy-Study AI</h1>' +
        '<p class="welcome-desc">Ask me anything about your study materials.</p></div>';
    } else {
      d.messages.forEach(function(m) {
        appendMsg('user', m.question);
        appendAI({
          answer: m.answer,
          provider: m.provider,
          model: m.model,
          confidence: m.confidence,
          source: m.source,
          cached: m.cached
        });
      });
    }
    refreshChatList();
    $('query-input').focus();
  } catch(e) { console.error('Failed to load conversation', e); }
}

async function deleteConversation(convId) {
  try {
    await fetch(API + '/api/conversations/' + convId, { method: 'DELETE' });
    if (convId === currentConversationId) {
      await createNewChat();
    } else {
      refreshChatList();
    }
  } catch(e) { /* ignore */ }
}

// New Chat button
$('btn-new-chat').addEventListener('click', createNewChat);

// Chat history click handler (delegation)
$('chat-history-list').addEventListener('click', function(e) {
  var delBtn = e.target.closest('.chat-delete');
  if (delBtn) {
    e.stopPropagation();
    deleteConversation(delBtn.dataset.id);
    return;
  }
  var item = e.target.closest('.chat-history-item');
  if (item) loadConversation(item.dataset.id);
});

// KB toggle (collapsible knowledge base)
$('kb-toggle').addEventListener('click', function() {
  $('kb-toggle').closest('.kb-section').classList.toggle('collapsed');
});

// After each query, refresh chat list (debounced, non-blocking)
var _refreshTimer = null;
function debouncedRefreshChatList() {
  clearTimeout(_refreshTimer);
  _refreshTimer = setTimeout(refreshChatList, 2000);
}
var _origSendQuery = sendQuery;
sendQuery = async function() {
  await _origSendQuery();
  debouncedRefreshChatList();
};

// On page load: create fresh chat + load history
(async function initConversations() {
  await createNewChat();
  refreshChatList();
})();

// ── Sidebar Toggle (ChatGPT/Claude-like) ──────────────────
$('sidebar-toggle').addEventListener('click', function() {
  var layout = $('chat-layout');
  var btn = $('sidebar-toggle');
  var isHidden = layout.classList.toggle('sidebar-hidden');
  btn.classList.toggle('moved', isHidden);
  btn.textContent = isHidden ? '☰' : '✕';
  if (isHidden) $('query-input').focus();
});

// ── Focus ─────────────────────────────────────────────────
$('query-input').focus();
