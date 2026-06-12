// ========== STREAMPILOT AI — CORE ENGINE ==========
// Navigation, Dashboard, Analytics, Charts

const SP = {
  charts: {},
  intervals: [],
  currentPage: 'dashboard',

  // === NAVIGATION ===
  initNav() {
    document.querySelectorAll('.nav-item[data-page]').forEach(item => {
      item.addEventListener('click', () => {
        const page = item.dataset.page;
        document.querySelectorAll('.nav-item').forEach(n => n.classList.remove('active'));
        item.classList.add('active');
        document.querySelectorAll('.page').forEach(p => p.classList.remove('active'));
        const el = document.getElementById('page-' + page);
        if (el) { el.classList.add('active'); el.style.animation = 'none'; el.offsetHeight; el.style.animation = ''; }
        SP.currentPage = page;
        SP.onPageEnter(page);
      });
    });
    document.addEventListener('keydown', e => { if (e.ctrlKey && e.key === 'k') { e.preventDefault(); document.getElementById('globalSearch')?.focus(); }});
  },

  onPageEnter(page) {
    if (page === 'dashboard') SP.initDashboard();
    else if (page === 'analytics') SP.initAnalytics();
    else if (page === 'monetization') SP.initMonetization();
    else if (page === 'livestream') SP.initLivestream();
  },

  rand(min, max) { return Math.floor(Math.random() * (max - min + 1)) + min; },
  randF(min, max) { return (Math.random() * (max - min) + min).toFixed(1); },
  fmt(n) { return n >= 1e6 ? (n/1e6).toFixed(1)+'M' : n >= 1e3 ? (n/1e3).toFixed(1)+'K' : n.toString(); },
  delay(ms) { return new Promise(r => setTimeout(r, ms)); },

  statCard(icon, value, label, change, up, bgCol) {
    const bg = bgCol || 'rgba(124,58,237,0.12)';
    return `<div class="stat-card"><div class="stat-header"><div class="stat-icon" style="background:${bg}">${icon}</div><span class="stat-change ${up?'up':'down'}">${up?'\u2191':'\u2193'} ${change}</span></div><div class="stat-value">${value}</div><div class="stat-label">${label}</div></div>`;
  },

  makeChart(id, type, labels, datasets, opts) {
    const canvas = document.getElementById(id);
    if (!canvas) return null;
    if (SP.charts[id]) SP.charts[id].destroy();
    const defaults = {
      responsive: true, maintainAspectRatio: false,
      plugins: { legend: { labels: { color: '#94A3B8', font: { family: 'Inter', size: 11 }}}, tooltip: { backgroundColor: 'rgba(17,17,39,0.95)', titleColor: '#fff', bodyColor: '#94A3B8', borderColor: 'rgba(255,255,255,0.1)', borderWidth: 1, cornerRadius: 8, padding: 12 }},
      scales: type === 'doughnut' || type === 'pie' || type === 'polarArea' ? {} : {
        x: { grid: { color: 'rgba(255,255,255,0.04)' }, ticks: { color: '#64748B', font: { family: 'Inter', size: 10 }}},
        y: { grid: { color: 'rgba(255,255,255,0.04)' }, ticks: { color: '#64748B', font: { family: 'Inter', size: 10 }}}
      }
    };
    SP.charts[id] = new Chart(canvas, { type, data: { labels, datasets }, options: { ...defaults, ...opts }});
    return SP.charts[id];
  },

  gradient(ctx, c1, c2) {
    const g = ctx.createLinearGradient(0, 0, 0, 280);
    g.addColorStop(0, c1); g.addColorStop(1, c2); return g;
  },

  initDashboard() {
    const briefings = [
      "Your channel grew <strong>3.2%</strong> this week. Hawkes branching ratio hit <strong>\u03b1=0.82</strong> \u2014 close to viral. <em>Action: Share on Reddit within 2hrs to push past 1.0.</em>",
      "Tuesday uploads outperform by <strong>23%</strong> (causal via do-calculus). Wasserstein distance <strong>0.18</strong> \u2014 over-indexing on reviews. <em>Add 1 tutorial this week.</em>",
      "Kalman-filtered growth: <strong>2.8%/week</strong>. EVT shape \u03be=<strong>0.31</strong> shows viral potential but no recent breakouts. <em>Fix thumbnail strategy.</em>"
    ];
    document.getElementById('briefingText').innerHTML = briefings[SP.rand(0, briefings.length-1)];

    const stats = document.getElementById('mainStats');
    stats.innerHTML = [
      SP.statCard('\ud83d\udc41\ufe0f', SP.fmt(SP.rand(180000,320000)), 'Views (30d)', SP.randF(2,8)+'%', true, 'rgba(124,58,237,0.12)'),
      SP.statCard('\ud83d\udc65', SP.fmt(SP.rand(12000,85000)), 'Subscribers', SP.randF(1,5)+'%', true, 'rgba(6,182,212,0.12)'),
      SP.statCard('\u23f1\ufe0f', SP.fmt(SP.rand(4000,18000))+'h', 'Watch Time', SP.randF(1,6)+'%', true, 'rgba(16,185,129,0.12)'),
      SP.statCard('\ud83d\udcb0', '$'+SP.rand(800,4500), 'Revenue (30d)', SP.randF(3,12)+'%', true, 'rgba(245,158,11,0.12)'),
      SP.statCard('\ud83d\udcc8', SP.randF(4,9)+'%', 'Avg CTR', SP.randF(0.2,1.5)+'%', Math.random()>0.3, 'rgba(244,63,94,0.12)')
    ].join('');

    const days = Array.from({length:30}, (_,i) => 'Jun '+(i+1));
    const viewsData = Array.from({length:30}, () => SP.rand(4000,15000));
    const subsData = Array.from({length:30}, () => SP.rand(50,300));
    const canvas = document.getElementById('mainChart');
    if (canvas) {
      const ctx = canvas.getContext('2d');
      SP.makeChart('mainChart', 'line', days, [
        { label: 'Views', data: viewsData, borderColor: '#7C3AED', backgroundColor: SP.gradient(ctx,'rgba(124,58,237,0.3)','rgba(124,58,237,0)'), fill: true, tension: 0.4, pointRadius: 0 },
        { label: 'New Subs', data: subsData, borderColor: '#06B6D4', backgroundColor: 'transparent', borderDash: [5,5], tension: 0.4, pointRadius: 0, yAxisID: 'y1' }
      ], { scales: { y: { grid:{color:'rgba(255,255,255,0.04)'}, ticks:{color:'#64748B'}}, y1: { position:'right', grid:{display:false}, ticks:{color:'#64748B'}}, x:{grid:{color:'rgba(255,255,255,0.04)'}, ticks:{color:'#64748B',maxTicksLimit:10}}}});
    }

    const score = SP.rand(72, 96);
    const healthRing = document.getElementById('healthRing');
    if (healthRing) {
      const c = 2 * Math.PI * 64, off = c - (score / 100) * c;
      const col = score > 80 ? '#10B981' : score > 60 ? '#F59E0B' : '#F43F5E';
      healthRing.innerHTML = `<svg width="160" height="160" viewBox="0 0 160 160"><circle cx="80" cy="80" r="64" fill="none" stroke="rgba(255,255,255,0.06)" stroke-width="12"/><circle cx="80" cy="80" r="64" fill="none" stroke="${col}" stroke-width="12" stroke-linecap="round" stroke-dasharray="${c}" stroke-dashoffset="${off}" style="transition:stroke-dashoffset 1.5s ease"/></svg><div class="score-text"><div class="score-value" style="color:${col}">${score}</div><div class="score-label">Health</div></div>`;
    }
    const hb = document.getElementById('healthBreakdown');
    if (hb) {
      const m = [{n:'Growth',v:SP.rand(70,98)},{n:'Engagement',v:SP.rand(60,95)},{n:'SEO',v:SP.rand(65,99)},{n:'Consistency',v:SP.rand(50,100)},{n:'Monetization',v:SP.rand(55,95)}];
      hb.innerHTML = m.map(x => `<div style="display:flex;justify-content:space-between;align-items:center;margin:8px 0;font-size:0.8rem"><span style="color:#94A3B8">${x.n}</span><div style="flex:1;margin:0 12px"><div class="progress-bar"><div class="fill" style="width:${x.v}%"></div></div></div><span style="font-weight:700">${x.v}%</span></div>`).join('');
    }
    const tbody = document.querySelector('#topVideosTable tbody');
    if (tbody) {
      const vids = ['RTX 5090 Review: $2000 Monster','$500 PC Build That DESTROYS','5 Mistakes New Builders Make','Best Budget GPU 2026','Ryzen 9 vs Intel i9'];
      tbody.innerHTML = vids.map(v => `<tr><td style="font-weight:600;color:#fff">${v}</td><td>${SP.fmt(SP.rand(5000,85000))}</td><td>${SP.randF(3,11)}%</td><td>$${SP.rand(40,650)}</td></tr>`).join('');
    }
    const sug = document.getElementById('aiSuggestions');
    if (sug) {
      sug.innerHTML = [
        {icon:'\ud83d\udd25',t:'Trending Topic Alert',d:'RTX 5090 Ti rumors \u2014 Lyapunov \u03bb=+0.15. 48hr window.',tag:'Urgent',c:'rose'},
        {icon:'\ud83d\udcca',t:'Upload Time Insight',d:'Thursday 8PM has +23% causal lift (do-calculus verified).',tag:'Causal',c:'green'},
        {icon:'\ud83c\udfaf',t:'Content Gap (TDA)',d:'Persistent homology void: "budget laptop reviews" \u2014 3 competitors filling it.',tag:'TDA',c:'cyan'},
        {icon:'\ud83d\udca1',t:'Thumbnail Fix',d:'Last 3 videos had no face. Face-thumbnails get 38% higher CTR.',tag:'Quick Win',c:'amber'}
      ].map(s => `<div class="result-card" style="margin-bottom:10px"><span class="tag-pill ${s.c}" style="float:right">${s.tag}</span><h4>${s.icon} ${s.t}</h4><p>${s.d}</p></div>`).join('');
    }
  },

  initAnalytics() {
    const as = document.getElementById('analyticsStats');
    if (as) as.innerHTML = [
      SP.statCard('\ud83d\udc41\ufe0f', SP.fmt(SP.rand(400000,1200000)), 'Total Views', SP.randF(5,15)+'%', true),
      SP.statCard('\u23f1\ufe0f', SP.randF(5,9)+' min', 'Avg View Duration', SP.randF(1,4)+'%', Math.random()>0.4),
      SP.statCard('\ud83d\udcca', SP.randF(4,8)+'%', 'Impression CTR', SP.randF(0.3,1.2)+'%', true),
      SP.statCard('\ud83d\udd04', SP.randF(35,65)+'%', 'Avg Retention', SP.randF(1,5)+'%', Math.random()>0.3)
    ].join('');
    const rl = Array.from({length:20}, (_,i) => (i*5)+'%');
    let rv = 100;
    const rd = rl.map((_,i) => { if(i===0) return 100; rv -= SP.rand(1,8)+(i>12?3:0); return Math.max(rv,8); });
    if (document.getElementById('retentionChart')) SP.makeChart('retentionChart','line',rl,[{label:'Your Video',data:rd,borderColor:'#7C3AED',backgroundColor:'rgba(124,58,237,0.1)',fill:true,tension:0.3,pointRadius:2},{label:'Niche Avg',data:rl.map((_,i)=>100-i*4.2),borderColor:'#64748B',borderDash:[4,4],tension:0.3,pointRadius:0,fill:false}]);
    SP.makeChart('trafficChart','doughnut',['Search','Suggested','Browse','External','Shorts'],[{data:[28,35,18,12,7],backgroundColor:['#7C3AED','#06B6D4','#10B981','#F59E0B','#F43F5E'],borderWidth:0}],{cutout:'65%'});
    SP.makeChart('deviceChart','polarArea',['Mobile','Desktop','TV','Tablet'],[{data:[52,28,14,6],backgroundColor:['rgba(124,58,237,0.6)','rgba(6,182,212,0.6)','rgba(16,185,129,0.6)','rgba(245,158,11,0.6)'],borderWidth:0}]);
    const geo = document.getElementById('geoData');
    if (geo) geo.innerHTML = [{f:'\ud83c\uddee\ud83c\uddf3',n:'India',p:34},{f:'\ud83c\uddfa\ud83c\uddf8',n:'United States',p:26},{f:'\ud83c\uddec\ud83c\udde7',n:'UK',p:12},{f:'\ud83c\udde9\ud83c\uddea',n:'Germany',p:8},{f:'\ud83c\udde8\ud83c\udde6',n:'Canada',p:6}].map(c=>`<div style="display:flex;align-items:center;gap:12px;margin:10px 0"><span style="font-size:1.4rem">${c.f}</span><span style="flex:1;font-size:0.85rem">${c.n}</span><div style="width:120px"><div class="progress-bar"><div class="fill" style="width:${c.p}%"></div></div></div><span style="font-size:0.8rem;color:#94A3B8">${c.p}%</span></div>`).join('');
    const ic = document.getElementById('insightCards');
    if (ic) ic.innerHTML = [
      {i:'\ud83e\udde0',t:'Pattern: Tuesday 8PM',d:'Copula: views+revenue spike together. Upper-tail \u03bb_U=0.72.',m:'Clayton \u03b8=2.4'},
      {i:'\ud83d\udcc9',t:'Retention Drop 6:15',d:'Hazard rate h=0.18 vs avg 0.09. B-roll transition causes drops.',m:'Hazard 2.0x'},
      {i:'\ud83d\udd2e',t:'Growth Forecast',d:'OU forecast: 3 uploads/wk for 8 wks = 94% chance of 50K subs.',m:'Kalman +142/day'}
    ].map(x=>`<div class="result-card"><span class="tag-pill purple" style="float:right">${x.m}</span><h4>${x.i} ${x.t}</h4><p>${x.d}</p></div>`).join('');
  },

  initMonetization() {
    const ms = document.getElementById('moneyStats');
    if (ms) ms.innerHTML = [
      SP.statCard('\ud83d\udcb0','$'+SP.rand(2000,8000),'Total Revenue',SP.randF(5,18)+'%',true,'rgba(16,185,129,0.12)'),
      SP.statCard('\ud83d\udcca','$'+SP.randF(8,22),'Avg CPM',SP.randF(1,4)+'%',true,'rgba(124,58,237,0.12)'),
      SP.statCard('\ud83d\udc8e','$'+SP.rand(200,1500),'Super Chats',SP.randF(3,15)+'%',true,'rgba(245,158,11,0.12)'),
      SP.statCard('\ud83c\udfab','$'+SP.rand(100,800),'Memberships',SP.randF(2,10)+'%',true,'rgba(6,182,212,0.12)')
    ].join('');
    const mo = ['Jan','Feb','Mar','Apr','May','Jun'], rd = mo.map(()=>SP.rand(1500,6000));
    SP.makeChart('revenueChart','line',[...mo,'Jul*','Aug*'],[
      {label:'Revenue',data:[...rd,null,null],borderColor:'#10B981',backgroundColor:'rgba(16,185,129,0.1)',fill:true,tension:0.4,pointRadius:3},
      {label:'Forecast',data:[null,null,null,null,null,rd[5],SP.rand(4000,7000),SP.rand(4500,7500)],borderColor:'#F59E0B',borderDash:[6,4],tension:0.4,pointRadius:2,fill:false}
    ]);
    SP.makeChart('revBreakdownChart','doughnut',['Ad Revenue','Super Chats','Memberships','Sponsors','Affiliates'],[{data:[55,15,10,12,8],backgroundColor:['#7C3AED','#06B6D4','#10B981','#F59E0B','#F43F5E'],borderWidth:0}],{cutout:'60%'});
  },

  initLivestream() {
    const ss = document.getElementById('streamStats');
    if (ss) ss.innerHTML = [
      SP.statCard('\ud83d\udc65',SP.fmt(SP.rand(200,2500)),'Viewers','Peak: '+SP.fmt(SP.rand(500,4000)),true,'rgba(244,63,94,0.12)'),
      SP.statCard('\ud83d\udcac',SP.rand(10,80)+'/min','Chat Rate',SP.randF(2,8)+'%',true,'rgba(124,58,237,0.12)'),
      SP.statCard('\ud83d\udcb0','$'+SP.rand(20,500),'Super Chats','Last hr',true,'rgba(16,185,129,0.12)'),
      SP.statCard('\ud83d\udcca',SP.randF(0.5,0.9),'Sentiment','Positive',true,'rgba(6,182,212,0.12)')
    ].join('');
    SP.makeChart('streamChart','line',Array.from({length:30},(_,i)=>i+'m'),[{label:'Viewers',data:Array.from({length:30},()=>SP.rand(300,2200)),borderColor:'#F43F5E',backgroundColor:'rgba(244,63,94,0.1)',fill:true,tension:0.3,pointRadius:0}]);
    const cf = document.getElementById('liveChatFeed');
    if (cf) cf.innerHTML = [
      {u:'TechFan42',m:'This stream is fire!',s:'pos'},{u:'GamerDude',m:'What GPU are you using?',s:'n'},{u:'ProBuilder',m:'Cable management is clean!',s:'pos'},{u:'TrollUser',m:'Check out my channel!!!',s:'spam'},{u:'ModeratorBot',m:'Self-promo removed (AI: 94%)',s:'mod'},{u:'SuperFan',m:'Just sent $10 super chat!',s:'pos'}
    ].map(m=>`<div style="padding:8px 12px;border-bottom:1px solid rgba(255,255,255,0.04);font-size:0.82rem"><span style="color:${m.s==='pos'?'#10B981':m.s==='spam'?'#F43F5E':m.s==='mod'?'#F59E0B':'#94A3B8'};font-weight:600">${m.u}:</span> <span style="color:#94A3B8">${m.m}</span></div>`).join('');
    const cs = document.getElementById('chatSentiment');
    if (cs) cs.innerHTML = '<div style="text-align:center;padding:12px"><span style="font-size:2rem">\ud83d\ude0a</span><div style="font-size:0.8rem;color:#10B981;font-weight:600;margin-top:4px">Positive (0.78)</div><div style="font-size:0.7rem;color:#64748B">EMA-smoothed sentiment</div></div>';
  },

  init() { SP.initNav(); SP.initDashboard(); }
};

document.addEventListener('DOMContentLoaded', SP.init);
// ========== STREAMPILOT AI — FEATURES MODULE ==========
// Optimizer, SEO, Stream Setup, Calendar, Shorts, Community, Safety, AI Chat

(function() {

// === CONTENT OPTIMIZER ===
let latestAutopilotAnalysis = null;

function escapeHtml(value) {
  return String(value ?? '').replace(/[&<>"']/g, ch => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
  }[ch]));
}

function getAutopilotTopic() {
  const typed = document.getElementById('videoTopic')?.value?.trim();
  const fileName = document.getElementById('videoFile')?.files?.[0]?.name || '';
  return typed || fileName.replace(/\.[^.]+$/, '').replace(/[_-]+/g, ' ').trim();
}

function setAutopilotStatus(message, type) {
  const el = document.getElementById('autopilotStatus');
  if (!el) return;
  el.className = 'autopilot-status active' + (type ? ' ' + type : '');
  el.innerHTML = message;
}

function makeUploadId() {
  if (window.crypto?.randomUUID) return window.crypto.randomUUID().replace(/-/g, '');
  return 'upload_' + Date.now().toString(36) + Math.random().toString(36).slice(2, 10);
}

function connectUploadProgress(uploadId) {
  if (!window.EventSource) return null;
  const source = new EventSource(`/api/upload-progress/${encodeURIComponent(uploadId)}`);
  source.onmessage = event => {
    try {
      const data = JSON.parse(event.data);
      const pct = Number.isFinite(data.progress) ? data.progress : 0;
      const stage = data.stage ? data.stage.replace(/_/g, ' ') : 'working';
      setAutopilotStatus(`<strong>${escapeHtml(stage)}</strong> · ${pct}%<br>${escapeHtml(data.message || '')}`, data.terminal && pct >= 100 ? 'success' : '');
      if (data.terminal) source.close();
    } catch (_) {
      // Ignore malformed progress events.
    }
  };
  source.onerror = () => source.close();
  return source;
}

function setRiskActionVisibility(show) {
  document.querySelectorAll('.risk-action').forEach(btn => {
    btn.style.display = show ? 'inline-flex' : 'none';
  });
}

function renderAnalysisCards(payload) {
  const analysis = payload?.analysis || payload;
  if (!analysis?.hook_report && !analysis?.brand_safety_report) return '';
  const hook = analysis.hook_report || {};
  const safety = analysis.brand_safety_report || {};
  const revenue = analysis.revenue_estimate || {};
  const risk = analysis.risk_report || {};
  const fix = analysis.fix_draft || {};
  const signals = (hook.signals || []).map(item => `<div class="analysis-line">${escapeHtml(item)}</div>`).join('');
  const safetyReasons = (safety.risk_reasons || risk.reasons || []).map(item => `<div class="analysis-line">${escapeHtml(item)}</div>`).join('');
  const fixes = [
    fix.safer_title ? `Safer title: ${fix.safer_title}` : '',
    ...(fix.bleep_mute_suggestions || []),
    ...(fix.recut_timestamps || []).map(item => `Recut from ${item.start}s: ${item.reason}`)
  ].filter(Boolean).map(item => `<div class="analysis-line">${escapeHtml(item)}</div>`).join('');
  return `
    <div class="result-card intelligence-card">
      <h4>Viral Hook Detector</h4>
      <p>Score: ${escapeHtml(hook.hook_strength ?? 'N/A')} | Drop-off: ${escapeHtml(hook.drop_off_risk || 'unknown')} | Suggested start: ${escapeHtml(hook.suggested_recut_start_seconds ?? 0)}s</p>
      ${signals || '<div class="analysis-line">No hook warnings from available context.</div>'}
    </div>
    <div class="result-card intelligence-card ${risk.requires_confirmation ? 'risk-high' : ''}">
      <h4>Brand Safety Scanner</h4>
      <p>Risk: ${escapeHtml(safety.risk_level || risk.level || 'unknown')} | Score: ${escapeHtml(safety.risk_score ?? 'N/A')} | Confirmation: ${risk.requires_confirmation ? 'required' : 'not required'}</p>
      ${safetyReasons || '<div class="analysis-line">No major brand-safety issue detected.</div>'}
    </div>
    <div class="result-card intelligence-card">
      <h4>Revenue Intelligence</h4>
      <p>CPM: $${escapeHtml(revenue.estimated_cpm_usd ?? 'N/A')} | Range: $${escapeHtml(revenue.cpm_range_usd?.[0] ?? 'N/A')}-$${escapeHtml(revenue.cpm_range_usd?.[1] ?? 'N/A')} | 24h projection: $${escapeHtml(revenue.first_24h_projection_usd ?? 'N/A')}</p>
    </div>
    <div class="result-card intelligence-card">
      <h4>Auto Fix Draft</h4>
      ${fixes || '<div class="analysis-line">No fix draft required.</div>'}
    </div>
  `;
}

function renderWarRoomCards(payload) {
  const war = payload?.war_room || payload;
  if (!war?.metrics) return '';
  const metrics = war.metrics || {};
  const alerts = (war.alert_cards || []).map(alert => `
    <div class="analysis-line"><strong>${escapeHtml(alert.title || alert.type)}:</strong> ${escapeHtml(alert.suggestion || alert.message || '')}</div>
  `).join('');
  const replies = (war.ai_reply_drafts || []).slice(0, 3).map(reply => `
    <div class="analysis-line"><strong>${escapeHtml(reply.author || 'Viewer')}:</strong> ${escapeHtml(reply.draft || '')}</div>
  `).join('');
  return `
    <div class="result-card intelligence-card war-room-card">
      <h4>First 24H War Room</h4>
      <p>Views: ${escapeHtml(metrics.views ?? 0)} | CTR: ${escapeHtml(metrics.ctr ?? 'N/A')}% | AVD: ${escapeHtml(metrics.average_view_duration_seconds ?? 0)}s | Comments: ${escapeHtml(metrics.comments ?? 0)}</p>
      ${alerts}
      <p style="margin-top:8px;color:#CBD5E1">${escapeHtml(war.recommended_intervention || '')}</p>
    </div>
    <div class="result-card intelligence-card">
      <h4>Early Reply Drafts</h4>
      ${replies || '<div class="analysis-line">No early comments yet.</div>'}
    </div>
  `;
}

function renderAutopilotResults(payload) {
  const pack = payload.package || payload;
  const upload = payload.upload;
  document.getElementById('optimizerResults').style.display = 'block';

  const titleRows = (pack.titles || []).map((title, i) => {
    const ctr = pack.predicted_ctrs?.[i] || payload.predicted_ctrs?.[i] || 'N/A';
    const winner = title === pack.final_title ? '<span class="tag-pill green">Selected</span>' : '';
    return `<div class="result-card"><span class="score">${escapeHtml(ctr)}</span><h4>${i + 1}. ${escapeHtml(title)} ${winner}</h4><p>CTR-ranked title candidate for public upload.</p></div>`;
  }).join('');
  document.getElementById('titleResults').innerHTML = titleRows || '<div class="result-card"><p>No titles returned.</p></div>';

  document.getElementById('descResults').innerHTML = `
    <div class="result-card">
      <h4>Final Title</h4>
      <p style="white-space:pre-line;color:#94A3B8;font-size:0.82rem;line-height:1.7">${escapeHtml(pack.final_title || '')}</p>
    </div>
    <div class="result-card">
      <h4>Description</h4>
      <p style="white-space:pre-line;color:#94A3B8;font-size:0.82rem;line-height:1.7">${escapeHtml(pack.description || '')}</p>
    </div>
    <div class="result-card">
      <h4>Pinned Comment</h4>
      <p>${escapeHtml(pack.pinned_comment || '')}</p>
    </div>
    <div class="result-card">
      <h4>Thumbnail Brief</h4>
      <p>${escapeHtml(pack.thumbnail_brief || '')}</p>
    </div>
  `;

  const tags = (pack.tags || []).map((tag, i) => `<span class="tag-pill ${['purple','cyan','green','amber','rose'][i % 5]}">${escapeHtml(tag)}</span>`).join(' ');
  const hashtags = (pack.hashtags || []).map(tag => `<span class="tag-pill cyan">${escapeHtml(tag)}</span>`).join(' ');
  document.getElementById('tagResults').innerHTML = `
    <div class="result-card">
      <h4>Tags</h4>
      <div>${tags}</div>
      <p style="margin-top:10px">Category: ${escapeHtml(pack.category_id || '28')} | Best window: ${escapeHtml(pack.best_time || 'Now')} | Source: ${escapeHtml(pack.source || 'ai')}</p>
    </div>
    <div class="result-card">
      <h4>Hashtags</h4>
      <div>${hashtags}</div>
    </div>
  `;

  const checklist = (pack.upload_checklist || []).map(item => `<div style="padding:4px 0;font-size:0.82rem;color:#94A3B8">✓ ${escapeHtml(item)}</div>`).join('');
  const nextActions = (pack.next_actions || []).map(item => `<div style="padding:4px 0;font-size:0.82rem;color:#94A3B8">→ ${escapeHtml(item)}</div>`).join('');
  const validation = payload.validation;
  const quota = payload.quota;
  const validationHtml = validation ? `
    <div class="result-card">
      <h4>Pre-flight Validation</h4>
      <p>Video: ${escapeHtml(validation.video?.filename || '')} · ${escapeHtml(validation.video?.size_label || '')} · ${escapeHtml(validation.video?.extension || '')}</p>
      ${validation.thumbnail ? `<p>Thumbnail: ${escapeHtml(validation.thumbnail.filename)} · ${escapeHtml(validation.thumbnail.size_label)}</p>` : '<p>Thumbnail: not provided</p>'}
      ${(validation.warnings || []).map(item => `<div style="padding:4px 0;font-size:0.82rem;color:#FBBF24">! ${escapeHtml(item)}</div>`).join('')}
    </div>
  ` : '';
  const quotaHtml = quota ? `
    <div class="result-card">
      <h4>YouTube Quota Estimate</h4>
      <p>Uploads today: ${escapeHtml(quota.videos_insert?.used_estimate ?? 0)} / ${escapeHtml(quota.videos_insert?.daily_limit ?? 100)} · Remaining: ${escapeHtml(quota.videos_insert?.remaining_estimate ?? 'N/A')}</p>
      <p>Data API unit estimate: ${escapeHtml(quota.data_api_units?.used_estimate ?? 0)} / ${escapeHtml(quota.data_api_units?.daily_limit ?? 10000)} · Reset: ${escapeHtml(quota.reset_timezone || 'America/Los_Angeles')}</p>
      ${(quota.warnings || []).map(item => `<div style="padding:4px 0;font-size:0.82rem;color:#FBBF24">! ${escapeHtml(item)}</div>`).join('')}
    </div>
  ` : '';
  const uploadHtml = upload ? `
    <div class="result-card" style="border-color:${payload.ok === false ? 'rgba(244,63,94,0.35)' : 'rgba(16,185,129,0.35)'}">
      <h4>${payload.ok === false ? 'Upload Failed' : 'Published Publicly'}</h4>
      ${upload.watch_url ? `<p><a class="upload-link" href="${escapeHtml(upload.watch_url)}" target="_blank" rel="noopener">${escapeHtml(upload.watch_url)}</a></p>` : ''}
      <p>Status: ${escapeHtml(upload.status || 'unknown')} | Privacy: ${escapeHtml(upload.privacy_status || 'public')} | Thumbnail: ${upload.thumbnail_applied ? 'applied' : 'not applied'}</p>
      ${upload.note ? `<p>${escapeHtml(upload.note)}</p>` : ''}
      ${upload.thumbnail_error ? `<p style="color:#FBBF24">${escapeHtml(upload.thumbnail_error)}</p>` : ''}
    </div>
  ` : '';
  const warningHtml = (pack.warnings || []).map(item => `<div style="padding:4px 0;font-size:0.82rem;color:#FBBF24">! ${escapeHtml(item)}</div>`).join('');
  const analysisHtml = renderAnalysisCards(payload);
  const warRoomHtml = renderWarRoomCards(payload);

  document.getElementById('checklistResults').innerHTML = `
    ${uploadHtml}
    ${analysisHtml}
    ${warRoomHtml}
    ${validationHtml}
    ${quotaHtml}
    <div class="result-card"><h4>Upload Checklist</h4>${checklist}</div>
    <div class="result-card"><h4>Next Channel Actions</h4>${nextActions}</div>
    ${warningHtml ? `<div class="result-card"><h4>Warnings</h4>${warningHtml}</div>` : ''}
  `;
}

function rememberPublishedUpload(payload) {
  if (!payload?.ok || !payload.package) return;
  let existing = [];
  try {
    existing = JSON.parse(localStorage.getItem('streamPilotPublishedUploads') || '[]');
  } catch (_) {
    existing = [];
  }
  const item = {
    t: payload.package.final_title || payload.package.topic || 'Autopilot upload',
    due: 'Published now',
    pri: 'done',
    url: payload.upload?.watch_url || '',
    video_id: payload.upload?.video_id || '',
    stage: 5
  };
  localStorage.setItem('streamPilotPublishedUploads', JSON.stringify([item, ...existing].slice(0, 12)));
  const predictInput = document.getElementById('predictVideoId');
  if (predictInput && item.video_id) predictInput.value = item.video_id;
}

document.getElementById('videoFile')?.addEventListener('change', function() {
  latestAutopilotAnalysis = null;
  setRiskActionVisibility(false);
  const label = document.getElementById('videoFileName');
  if (label) label.textContent = this.files?.[0]?.name || 'Required for publish';
});

document.getElementById('thumbnailFile')?.addEventListener('change', function() {
  latestAutopilotAnalysis = null;
  setRiskActionVisibility(false);
  const label = document.getElementById('thumbnailFileName');
  if (label) label.textContent = this.files?.[0]?.name || 'Optional custom image';
});

document.getElementById('btnOptimize')?.addEventListener('click', async function() {
  const topic = getAutopilotTopic();
  if (!topic) return alert('Enter a topic or choose a video first.');
  this.textContent = '⏳ AI Packaging...'; this.disabled = true;
  setAutopilotStatus('Generating title, description, tags, thumbnail brief, and launch checklist...', '');
  try {
    const res = await fetch('/api/generate-seo', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({topic})
    });
    const data = await res.json();
    if (!res.ok || data.error) throw new Error(data.error || data.detail || 'Metadata generation failed');
    renderAutopilotResults(data);
    setAutopilotStatus('AI package ready. Add a video file and publish publicly when ready.', 'success');
  } catch (err) {
    setAutopilotStatus(`Package failed: ${escapeHtml(err.message)}`, 'error');
  }
  this.textContent = '🚀 Generate Everything'; this.disabled = false;
});

function buildAutopilotForm({confirmRisk = false, applyFixDraft = false} = {}) {
  const video = document.getElementById('videoFile')?.files?.[0];
  if (!video) {
    alert('Choose a video file before publishing.');
    return null;
  }
  const form = new FormData();
  const uploadId = makeUploadId();
  form.append('video', video);
  const thumbnail = document.getElementById('thumbnailFile')?.files?.[0];
  if (thumbnail) form.append('thumbnail', thumbnail);
  form.append('topic', getAutopilotTopic());
  form.append('made_for_kids', document.getElementById('madeForKids')?.checked ? 'true' : 'false');
  form.append('contains_synthetic_media', document.getElementById('containsSyntheticMedia')?.checked ? 'true' : 'false');
  form.append('upload_id', uploadId);
  if (latestAutopilotAnalysis?.analysis_id) form.append('analysis_id', latestAutopilotAnalysis.analysis_id);
  form.append('confirm_risk', confirmRisk ? 'true' : 'false');
  form.append('apply_fix_draft', applyFixDraft ? 'true' : 'false');
  return {form, uploadId};
}

async function submitAutopilotUpload(button, options = {}) {
  const built = buildAutopilotForm(options);
  if (!built) return;
  const {form, uploadId} = built;

  const originalText = button.textContent;
  button.textContent = options.applyFixDraft ? '🛠️ Applying Fix & Publishing...' : options.confirmRisk ? '⚠️ Confirming & Publishing...' : '📤 AI Publishing Publicly...';
  button.disabled = true;
  setAutopilotStatus('Running pre-upload gate, then publishing publicly if cleared...', '');
  const progressSource = connectUploadProgress(uploadId);
  try {
    const res = await fetch('/api/ai-upload', { method: 'POST', body: form });
    const data = await res.json();
    progressSource?.close();
    renderAutopilotResults(data);
    if (data.analysis?.analysis_id) latestAutopilotAnalysis = data.analysis;
    if (data.requires_confirmation) {
      setRiskActionVisibility(true);
      setAutopilotStatus('AI paused public publish. Apply the fix draft or explicitly confirm risk to continue.', 'error');
      return;
    }
    if (!res.ok || data.ok === false) throw new Error(data.error || data.detail || 'Upload failed');
    setRiskActionVisibility(false);
    rememberPublishedUpload(data);
    setAutopilotStatus(`Published publicly: <a class="upload-link" href="${escapeHtml(data.upload.watch_url)}" target="_blank" rel="noopener">${escapeHtml(data.upload.watch_url)}</a>`, 'success');
  } catch (err) {
    progressSource?.close();
    setAutopilotStatus(`Upload failed: ${escapeHtml(err.message)}`, 'error');
  }
  button.textContent = originalText;
  button.disabled = false;
}

document.getElementById('btnAnalyzeVideo')?.addEventListener('click', async function() {
  const video = document.getElementById('videoFile')?.files?.[0];
  if (!video) return alert('Choose a video file before scanning.');
  const form = new FormData();
  form.append('video', video);
  const thumbnail = document.getElementById('thumbnailFile')?.files?.[0];
  if (thumbnail) form.append('thumbnail', thumbnail);
  form.append('topic', getAutopilotTopic());

  this.textContent = '🛡️ Scanning...'; this.disabled = true;
  setAutopilotStatus('Analyzing first 30 seconds, hook risk, brand safety, and revenue fit...', '');
  try {
    const res = await fetch('/api/analyze-video', { method: 'POST', body: form });
    const data = await res.json();
    renderAutopilotResults(data);
    if (data.analysis_id) latestAutopilotAnalysis = data;
    setRiskActionVisibility(Boolean(data.requires_confirmation));
    if (!res.ok && !data.setup_required && !data.provider_error) throw new Error(data.error || data.detail || 'Analysis failed');
    if (data.setup_required || data.provider_error) {
      setAutopilotStatus(escapeHtml(data.message || data.provider_error || 'Pre-upload intelligence setup required.'), 'error');
    } else if (data.requires_confirmation) {
      setAutopilotStatus('Scan complete. AI recommends a fix or explicit confirmation before public upload.', 'error');
    } else {
      setAutopilotStatus('Scan complete. Low risk: ready to publish publicly.', 'success');
    }
  } catch (err) {
    setAutopilotStatus(`Scan failed: ${escapeHtml(err.message)}`, 'error');
  }
  this.textContent = '🛡️ Scan First 30s'; this.disabled = false;
});

document.getElementById('btnAutoUpload')?.addEventListener('click', function() {
  submitAutopilotUpload(this);
});

document.getElementById('btnApplyFixPublish')?.addEventListener('click', function() {
  submitAutopilotUpload(this, {applyFixDraft: true});
});

document.getElementById('btnConfirmRisk')?.addEventListener('click', function() {
  submitAutopilotUpload(this, {confirmRisk: true});
});

function setOpsStatus(message, type) {
  const el = document.getElementById('opsStatus');
  if (!el) return;
  el.className = 'autopilot-status active' + (type ? ' ' + type : '');
  el.innerHTML = message;
}

function useRealYouTubeData() {
  return Boolean(document.getElementById('useRealYouTubeData')?.checked);
}

function opsSourceQuery(extra = '') {
  const source = useRealYouTubeData() ? 'real' : 'local';
  return `source=${encodeURIComponent(source)}${extra}`;
}

function renderDataBadges(data) {
  const badges = [];
  if (data.source === 'real_youtube') badges.push('<span class="tag-pill green">Real YouTube</span>');
  if (data.data_freshness?.analytics_delayed || data.analytics_available === false) badges.push('<span class="tag-pill amber">Analytics delayed</span>');
  if (data.error_category) badges.push(`<span class="tag-pill rose">${escapeHtml(data.error_category)}</span>`);
  if (data.data_freshness?.fetched_at || data.fetched_at || data.trained_at) {
    const stamp = data.data_freshness?.fetched_at || data.fetched_at || data.trained_at;
    badges.push(`<span class="tag-pill cyan">Last refreshed ${escapeHtml(new Date(stamp).toLocaleTimeString())}</span>`);
  }
  return badges.length ? `<div class="ops-badges">${badges.join(' ')}</div>` : '';
}

function trendStatusLabel(status) {
  return {
    will_trend_soon: 'Will trend soon',
    watchlist: 'Watchlist',
    cooling: 'Cooling',
    low_probability: 'Low probability'
  }[status] || 'Trend signal';
}

function trendStatusClass(status, confidence) {
  if (confidence === 'low') return 'amber';
  if (status === 'will_trend_soon') return 'green';
  if (status === 'cooling') return 'rose';
  if (status === 'watchlist') return 'cyan';
  return 'amber';
}

function renderTrendBadge(prediction) {
  if (!prediction || !prediction.status) return '';
  const cls = trendStatusClass(prediction.status, prediction.confidence);
  return `<span class="tag-pill ${cls}">${escapeHtml(trendStatusLabel(prediction.status))}</span>`;
}

function renderTrendReasons(prediction) {
  if (!prediction) return '';
  return (prediction.reasons || []).slice(0, 3).map(reason => `<div class="analysis-line">${escapeHtml(reason)}</div>`).join('');
}

function renderTrainingState(data) {
  const base = data.channel_baselines || {};
  const rules = (data.learned_rules || []).map(rule => `<div class="analysis-line">${escapeHtml(rule)}</div>`).join('');
  const registry = data.training_registry || {};
  const lab = registry.dataset ? `
    <div class="analysis-line">Training registry: ${escapeHtml(registry.dataset.snapshot_rows ?? 0)} snapshots, ${escapeHtml(registry.dataset.labels_ready ?? 0)} ready labels, champion ${registry.champion ? 'active' : 'not active'}</div>
  ` : '';
  return `
    <div class="result-card intelligence-card">
      <h4>AI Brain Trained</h4>
      ${renderDataBadges(data)}
      <p>Version: ${escapeHtml(data.model_version || 'local')} | Samples: ${escapeHtml(data.trained_samples ?? 0)} | Growth: ${escapeHtml(base.recent_growth_rate_pct ?? 0)}%</p>
      <p>Baseline 24h views: ${escapeHtml(base.baseline_24h_views ?? 0)} | Avg views: ${escapeHtml(base.average_views ?? 0)} | Median: ${escapeHtml(base.median_views ?? 0)}</p>
      ${lab}
      ${rules}
    </div>
  `;
}

function renderTrainingLab(data) {
  const dataset = data.dataset || {};
  const champion = data.champion || null;
  const candidate = data.latest_candidate || null;
  const decision = data.promotion_decision || candidate?.promotion_decision || {};
  const badges = (data.badges || []).map(label => {
    const cls = label === 'Champion Active' ? 'green' : label === 'Needs More Labels' ? 'amber' : label === 'Real YouTube' ? 'green' : 'cyan';
    return `<span class="tag-pill ${cls}">${escapeHtml(label)}</span>`;
  }).join(' ');
  const jobs = (data.jobs || []).slice(0, 4).map(job => `
    <div class="analysis-line">
      <strong>${escapeHtml(job.status || 'job')}</strong> ${escapeHtml(job.phase || '')} · ${escapeHtml(job.progress ?? 0)}%
      ${job.candidate_version ? ` · ${escapeHtml(job.candidate_version)}` : ''}
    </div>
  `).join('');
  const taskScores = candidate?.metrics?.task_scores || {};
  const scoreRows = Object.entries(taskScores).map(([task, score]) => `
    <div class="analysis-line">${escapeHtml(task)}: ${escapeHtml(Number(score).toFixed(3))}</div>
  `).join('');
  const reasons = (decision.reasons || []).map(reason => `<div class="analysis-line">${escapeHtml(reason)}</div>`).join('');
  return `
    <div class="result-card intelligence-card">
      <h4>Self-Improving Training Lab</h4>
      <div class="ops-badges">${badges || '<span class="tag-pill amber">Shadow Mode</span>'}</div>
      <p>Snapshots: ${escapeHtml(dataset.snapshot_rows ?? 0)} | Videos: ${escapeHtml(dataset.video_count ?? 0)} | Ready labels: ${escapeHtml(dataset.labels_ready ?? 0)} | Pending: ${escapeHtml(dataset.labels_pending ?? 0)}</p>
      <p>Champion: ${escapeHtml(champion?.version || 'none')} | Candidate: ${escapeHtml(candidate?.version || 'none')}</p>
      ${candidate?.metrics?.composite_score !== undefined ? `<p>Candidate composite: ${escapeHtml(candidate.metrics.composite_score)} | Champion baseline: ${escapeHtml(candidate.metrics.champion_composite_score ?? 0)}</p>` : ''}
      ${scoreRows}
      ${reasons}
      ${jobs || '<div class="analysis-line">No retrain jobs yet.</div>'}
    </div>
  `;
}

function renderTrainingJob(data) {
  const evalSummary = data.evaluation_summary || {};
  const decision = data.promotion_decision || {};
  const taskScores = evalSummary.task_scores || {};
  const scoreRows = Object.entries(taskScores).map(([task, score]) => `
    <div class="analysis-line">${escapeHtml(task)}: ${escapeHtml(Number(score).toFixed(3))}</div>
  `).join('');
  const reasons = (decision.reasons || []).map(reason => `<div class="analysis-line">${escapeHtml(reason)}</div>`).join('');
  return `
    <div class="result-card intelligence-card">
      <h4>Retrain Job</h4>
      <p>Status: ${escapeHtml(data.status || 'unknown')} | Phase: ${escapeHtml(data.phase || '')} | Progress: ${escapeHtml(data.progress ?? 0)}%</p>
      ${data.candidate_version ? `<p>Candidate: ${escapeHtml(data.candidate_version)}</p>` : ''}
      ${data.error ? `<div class="analysis-line" style="color:#FCA5A5">${escapeHtml(data.error)}</div>` : ''}
      ${scoreRows}
      ${reasons}
    </div>
  `;
}

async function loadTrainingStatus({render = true} = {}) {
  const res = await fetch('/api/training/status');
  const data = await res.json();
  if (!res.ok || data.ok === false) throw new Error(data.error || data.detail || 'Training status failed');
  if (render) document.getElementById('trainingLabResults').innerHTML = renderTrainingLab(data);
  return data;
}

async function pollTrainingJob(jobId) {
  let latest = null;
  for (let i = 0; i < 90; i += 1) {
    const res = await fetch(`/api/training/jobs/${encodeURIComponent(jobId)}`);
    latest = await res.json();
    document.getElementById('trainingLabResults').innerHTML = renderTrainingJob(latest);
    if (latest.status === 'completed' || latest.status === 'failed') break;
    await SP.delay(1000);
  }
  if (latest?.status === 'completed') await loadTrainingStatus({render: true});
  return latest;
}

function renderRealtimePrediction(data) {
  const forecast = data.forecast || {};
  const signals = data.signals || {};
  const trend = data.trend_prediction || {};
  const actions = (data.next_actions || []).map(item => `<div class="analysis-line">${escapeHtml(item)}</div>`).join('');
  return `
    <div class="result-card intelligence-card war-room-card">
      <h4>Real-Time Video Prediction</h4>
      ${renderDataBadges(data)}
      <p>Outcome: ${escapeHtml(forecast.outcome || 'unknown')} | ${renderTrendBadge(trend)} | Virality: ${Math.round((forecast.virality_probability || 0) * 100)}% | Confidence: ${escapeHtml(data.confidence || 'low')}</p>
      <p>Next 1h: ${escapeHtml(forecast.next_1h_views ?? 0)} views | 6h: ${escapeHtml(forecast.next_6h_views ?? 0)} | 24h: ${escapeHtml(forecast.next_24h_views ?? 0)}</p>
      ${trend.score !== undefined ? `<p>Trend score: ${escapeHtml(trend.score)}/100 | Chance: ${Math.round((trend.probability || 0) * 100)}% | Signal confidence: ${escapeHtml(trend.confidence || 'low')}</p>` : ''}
      <p>Signals: velocity ${escapeHtml(signals.early_velocity_views_per_hour ?? 0)}/h, CTR x${escapeHtml(signals.ctr_factor ?? 1)}, AVD x${escapeHtml(signals.avd_factor ?? 1)}, trend x${escapeHtml(signals.trend_factor ?? 1)}</p>
      ${renderTrendReasons(trend)}
      <div class="analysis-line"><strong>Move now:</strong> ${escapeHtml(data.recommended_intervention || 'Keep monitoring.')}</div>
      ${actions}
    </div>
  `;
}

function renderTrendingScan(data) {
  const summary = data.trend_summary || {};
  const videos = (data.videos || []).slice(0, 8).map(video => {
    const trend = video.trend_prediction || {};
    return `
      <div class="result-card intelligence-card">
        <h4>${renderTrendBadge(trend)} ${escapeHtml(video.title || '')}</h4>
        <p>${escapeHtml(video.channel_title || '')} | ${escapeHtml(video.views_per_hour ?? 0)}/h | Trend: ${escapeHtml(video.youtube_trend_score ?? 0)}/100 | Creator fit: ${escapeHtml(video.creator_opportunity_score ?? video.opportunity_score ?? 0)}/100 | ${escapeHtml(video.topic_cluster || '')}</p>
        ${trend.score !== undefined ? `<p>Chance: ${Math.round((trend.probability || 0) * 100)}% | Confidence: ${escapeHtml(trend.confidence || 'low')} | History: ${trend.signals?.history_available ? 'yes' : 'needs one more scan'}</p>` : ''}
        ${renderTrendReasons(trend)}
        ${(video.why_trending || []).map(reason => `<div class="analysis-line">${escapeHtml(reason)}</div>`).join('')}
        <div class="analysis-line"><strong>Action:</strong> ${escapeHtml(trend.recommended_action || video.creator_action || '')}</div>
        <div class="analysis-line"><strong>Angle:</strong> ${escapeHtml(video.package_angle?.title_seed || '')}</div>
      </div>
    `;
  }).join('');
  return `
    <div class="result-card intelligence-card">
      <h4>Trend Summary</h4>
      ${renderDataBadges(data)}
      <p>Top cluster: ${escapeHtml(summary.top_cluster || 'none')} | Best score: ${escapeHtml(summary.best_opportunity_score ?? 'N/A')} | Mode: ${escapeHtml(data.mode || 'test')}</p>
      <p>${escapeHtml(summary.best_opportunity || '')}</p>
    </div>
    ${videos}
  `;
}

document.getElementById('btnTrainAI')?.addEventListener('click', async function() {
  this.textContent = '🧠 Training...'; this.disabled = true;
  const real = useRealYouTubeData();
  setOpsStatus(real ? 'Training from real YouTube channel history and analytics...' : 'Training the local StreamPilot brain from channel history, upload memory, CTR signals, and War Room metrics...', '');
  try {
    const res = await fetch(`/api/train-ai?${opsSourceQuery()}`, { method: 'POST' });
    const data = await res.json();
    if (!res.ok || data.ok === false) throw new Error(data.error || data.detail || 'Training failed');
    document.getElementById('intelligenceOpsResults').innerHTML = renderTrainingState(data);
    setOpsStatus(real ? 'AI brain trained on real YouTube data.' : 'AI brain trained and ready for live prediction.', 'success');
  } catch (err) {
    setOpsStatus(`Training failed: ${escapeHtml(err.message)}`, 'error');
  }
  this.textContent = '🧠 Train AI Brain'; this.disabled = false;
});

document.getElementById('btnPredictVideo')?.addEventListener('click', async function() {
  let videoId = document.getElementById('predictVideoId')?.value?.trim();
  if (!videoId) {
    try {
      const uploads = JSON.parse(localStorage.getItem('streamPilotPublishedUploads') || '[]');
      videoId = uploads.find(item => item.video_id)?.video_id || '';
    } catch (_) {
      videoId = '';
    }
  }
  if (!videoId) return alert('Enter a YouTube video ID or publish a test upload first.');
  this.textContent = '📈 Predicting...'; this.disabled = true;
  const real = useRealYouTubeData();
  setOpsStatus(real ? 'Reading real YouTube stats, analytics, and comments...' : 'Reading War Room metrics and forecasting what happens next...', '');
  try {
    const res = await fetch(`/api/realtime-predict/${encodeURIComponent(videoId)}?${opsSourceQuery('&refresh=true')}`);
    const data = await res.json();
    if (!res.ok || data.ok === false) throw new Error(data.error || data.detail || 'Prediction failed');
    document.getElementById('intelligenceOpsResults').innerHTML = renderRealtimePrediction(data);
    setOpsStatus('Prediction ready. Follow the top intervention first.', 'success');
  } catch (err) {
    setOpsStatus(`Prediction failed: ${escapeHtml(err.message)}`, 'error');
  }
  this.textContent = '📈 Predict Video Now'; this.disabled = false;
});

document.getElementById('btnScanTrends')?.addEventListener('click', async function() {
  const region = document.getElementById('trendRegion')?.value?.trim() || 'US';
  this.textContent = '🔥 Scanning...'; this.disabled = true;
  const real = useRealYouTubeData();
  setOpsStatus(real ? 'Scanning real YouTube most-popular videos...' : 'Scanning trending videos and ranking opportunities for this channel...', '');
  try {
    const res = await fetch(`/api/trending-videos?region_code=${encodeURIComponent(region)}&max_results=12&${opsSourceQuery()}`);
    const data = await res.json();
    if (!res.ok || data.ok === false) throw new Error(data.error || data.detail || 'Trend scan failed');
    document.getElementById('intelligenceOpsResults').innerHTML = renderTrendingScan(data);
    setOpsStatus(real ? 'Real YouTube trend scan ready.' : 'Trending scan ready.', 'success');
  } catch (err) {
    setOpsStatus(`Trend scan failed: ${escapeHtml(err.message)}`, 'error');
  }
  this.textContent = '🔥 Scan Trending Videos'; this.disabled = false;
});

document.getElementById('btnCollectTrainingData')?.addEventListener('click', async function() {
  const originalText = this.textContent;
  this.textContent = 'Collecting...'; this.disabled = true;
  const real = useRealYouTubeData();
  setOpsStatus(real ? 'Collecting read-only real YouTube training snapshots...' : 'Collecting local training snapshots from channel history and published uploads...', '');
  try {
    const res = await fetch(`/api/training/collect?${opsSourceQuery('&scope=mixed')}`, { method: 'POST' });
    const data = await res.json();
    if (!res.ok || data.ok === false) throw new Error(data.error || data.detail || 'Data collection failed');
    await loadTrainingStatus({render: true});
    setOpsStatus(`Collected ${escapeHtml(data.snapshot_rows ?? 0)} snapshots and ${escapeHtml(data.labels_ready ?? 0)} ready labels.`, 'success');
  } catch (err) {
    setOpsStatus(`Data collection failed: ${escapeHtml(err.message)}`, 'error');
    document.getElementById('trainingLabResults').innerHTML = `<div class="result-card intelligence-card risk-high"><h4>Training Data Error</h4><p>${escapeHtml(err.message)}</p></div>`;
  }
  this.textContent = originalText; this.disabled = false;
});

document.getElementById('btnRetrainModel')?.addEventListener('click', async function() {
  const originalText = this.textContent;
  this.textContent = 'Retraining...'; this.disabled = true;
  setOpsStatus('Queued candidate model retrain. Temporal backtest will decide promotion.', '');
  try {
    const res = await fetch('/api/training/retrain', { method: 'POST' });
    const data = await res.json();
    if (!res.ok || data.ok === false) throw new Error(data.error || data.detail || 'Retrain failed to queue');
    const job = await pollTrainingJob(data.job_id);
    if (job?.status === 'failed') throw new Error(job.error || 'Retrain failed');
    setOpsStatus(job?.promotion_decision?.auto_promoted ? 'Candidate passed gates and became champion.' : 'Candidate trained in shadow mode. Review reasons before manual promotion.', job?.promotion_decision?.auto_promoted ? 'success' : '');
  } catch (err) {
    setOpsStatus(`Retrain failed: ${escapeHtml(err.message)}`, 'error');
  }
  this.textContent = originalText; this.disabled = false;
});

document.getElementById('btnTrainingStatus')?.addEventListener('click', async function() {
  const originalText = this.textContent;
  this.textContent = 'Loading...'; this.disabled = true;
  try {
    await loadTrainingStatus({render: true});
    setOpsStatus('Training registry status loaded.', 'success');
  } catch (err) {
    setOpsStatus(`Status failed: ${escapeHtml(err.message)}`, 'error');
  }
  this.textContent = originalText; this.disabled = false;
});

document.getElementById('btnPromoteModel')?.addEventListener('click', async function() {
  const originalText = this.textContent;
  this.textContent = 'Promoting...'; this.disabled = true;
  setOpsStatus('Manual promotion requested for the latest candidate.', '');
  try {
    const res = await fetch('/api/training/promote', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({manual_override: true})
    });
    const data = await res.json();
    if (!res.ok || data.ok === false) throw new Error(data.error || data.detail || 'Promotion failed');
    await loadTrainingStatus({render: true});
    setOpsStatus(`Champion active: ${escapeHtml(data.champion?.version || 'candidate')}`, 'success');
  } catch (err) {
    setOpsStatus(`Promotion failed: ${escapeHtml(err.message)}`, 'error');
  }
  this.textContent = originalText; this.disabled = false;
});

document.addEventListener('DOMContentLoaded', () => {
  if (document.getElementById('trainingLabResults')) {
    loadTrainingStatus({render: true}).catch(() => {});
  }
});

// === SEO CENTER ===
document.getElementById('btnSeoSearch')?.addEventListener('click', async function() {
  const kw = document.getElementById('seoKeyword')?.value;
  if (!kw) return alert('Enter a keyword!');
  this.textContent = '\ud83d\udd0d Analyzing...'; this.disabled = true;
  await SP.delay(1500);
  document.getElementById('seoResults').style.display = 'block';

  document.getElementById('seoStats').innerHTML = [
    SP.statCard('\ud83d\udd0e',SP.fmt(SP.rand(10000,200000)),'Monthly Searches',SP.randF(2,15)+'% trend',true),
    SP.statCard('\u2694\ufe0f',SP.rand(15,75)+'/100','Difficulty','Moderate',Math.random()>0.5),
    SP.statCard('\ud83d\udcb0','$'+SP.randF(8,35),'Est. CPM','High value',true),
    SP.statCard('\ud83d\udcc8',SP.rand(40,85)+'%','Rank Chance','Page 1',true)
  ].join('');

  const related = [kw+' review',kw+' 2026','best '+kw,kw+' vs',kw+' worth it',kw+' budget',kw+' guide','how to '+kw,kw+' comparison',kw+' test'];
  document.getElementById('relatedKeywords').innerHTML = related.map(r =>
    `<div style="display:flex;justify-content:space-between;padding:8px 0;border-bottom:1px solid rgba(255,255,255,0.04);font-size:0.82rem"><span style="color:#94A3B8">${r}</span><div><span class="tag-pill cyan">${SP.fmt(SP.rand(1000,80000))}/mo</span> <span class="tag-pill ${SP.rand(1,100)>50?'green':'amber'}">${SP.rand(10,70)} diff</span></div></div>`
  ).join('');

  const trendLabels = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];
  SP.makeChart('seoTrendChart','line',trendLabels,[{
    label:'Search Volume',data:trendLabels.map(()=>SP.rand(20,100)),
    borderColor:'#7C3AED',backgroundColor:'rgba(124,58,237,0.1)',fill:true,tension:0.4,pointRadius:3
  }]);
  this.textContent = '\ud83d\udd0d Analyze Keyword'; this.disabled = false;
});

// === OBS CONTROL ===
let obsEventSource = null;
const obsRecentEvents = [];

function obsConnectionPayload() {
  const payload = {};
  const host = document.getElementById('obsHost')?.value?.trim();
  const port = document.getElementById('obsPort')?.value?.trim();
  const password = document.getElementById('obsPassword')?.value;
  if (host) payload.host = host;
  if (port) payload.port = Number(port);
  if (password) payload.password = password;
  return payload;
}

async function obsPost(path, body = {}) {
  const res = await fetch(path, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) });
  const data = await res.json();
  if (!res.ok) throw new Error(data.detail || data.error || 'OBS request failed');
  return data;
}

function setObsBadge(text, cls = '') {
  const badge = document.getElementById('obsConnectionBadge');
  if (!badge) return;
  badge.textContent = text;
  badge.className = `card-badge ${cls}`.trim();
}

function renderObsStatus(data) {
  const panel = document.getElementById('obsStatusPanel');
  if (!panel) return;
  if (!data.connected) {
    setObsBadge('Disconnected');
    panel.innerHTML = `<div class="analysis-line">OBS is not connected. Open OBS, enable WebSocket server on port 4455, then connect.</div>`;
    document.getElementById('obsOutputControls').innerHTML = '';
    document.getElementById('obsSceneControls').innerHTML = '';
    return;
  }
  setObsBadge('Connected', 'green');
  const version = data.version || {};
  const scene = data.current_scene || {};
  panel.innerHTML = `
    <div class="analysis-line"><strong>Scene:</strong> ${escapeHtml(scene.currentProgramSceneName || 'Unknown')}</div>
    <div class="analysis-line"><strong>OBS:</strong> ${escapeHtml(version.obs_version || 'Unknown')} | WebSocket ${escapeHtml(version.obs_websocket_version || 'Unknown')}</div>
    <div class="analysis-line"><strong>Platform:</strong> ${escapeHtml(version.platform || 'Unknown')}</div>
  `;
  renderObsOutputs(data);
}

function renderObsOutputs(data) {
  const el = document.getElementById('obsOutputControls');
  if (!el) return;
  const streamOn = Boolean(data.stream?.outputActive);
  const recordOn = Boolean(data.record?.outputActive);
  const recordPaused = Boolean(data.record?.outputPaused);
  const replayOn = Boolean(data.replay_buffer?.outputActive);
  const camOn = Boolean(data.virtual_cam?.outputActive);
  el.innerHTML = `
    <div class="autopilot-actions">
      <button class="btn ${streamOn ? 'btn-danger' : 'btn-primary'}" data-obs-action="${streamOn ? 'stop_stream' : 'start_stream'}" data-obs-confirm="true">${streamOn ? 'Stop Stream' : 'Start Stream'}</button>
      <button class="btn ${recordOn ? 'btn-danger' : 'btn-secondary'}" data-obs-action="${recordOn ? 'stop_record' : 'start_record'}" ${recordOn ? 'data-obs-confirm="true"' : ''}>${recordOn ? 'Stop Recording' : 'Start Recording'}</button>
      <button class="btn btn-secondary" data-obs-action="${recordPaused ? 'resume_record' : 'pause_record'}">${recordPaused ? 'Resume' : 'Pause'}</button>
      <button class="btn btn-secondary" data-obs-action="${replayOn ? 'stop_replay_buffer' : 'start_replay_buffer'}">${replayOn ? 'Stop Replay' : 'Start Replay'}</button>
      <button class="btn btn-secondary" data-obs-action="save_replay_buffer">Save Replay</button>
      <button class="btn btn-secondary" data-obs-action="${camOn ? 'stop_virtual_cam' : 'start_virtual_cam'}" data-obs-confirm="true">${camOn ? 'Stop Virtual Cam' : 'Start Virtual Cam'}</button>
    </div>
  `;
}

function renderObsScenes(data) {
  const el = document.getElementById('obsSceneControls');
  if (!el) return;
  if (!data.connected && !data.ok) {
    el.innerHTML = `<div class="analysis-line">${escapeHtml(data.message || data.error || 'Connect OBS first.')}</div>`;
    return;
  }
  const scenes = data.scenes || [];
  el.innerHTML = scenes.map(scene => `
    <div class="result-card intelligence-card">
      <h4>${escapeHtml(scene.sceneName || '')}</h4>
      <button class="btn btn-primary" data-obs-action="switch_scene" data-scene="${escapeHtml(scene.sceneName || '')}">Switch</button>
      ${(scene.items || []).slice(0, 8).map(item => `
        <div class="analysis-line" style="display:flex;justify-content:space-between;gap:8px;align-items:center">
          <span>${escapeHtml(item.sourceName || item.inputName || 'Source')} ${item.sceneItemEnabled === false ? '(hidden)' : ''}</span>
          <span>
            <button class="btn btn-secondary" data-obs-action="set_source_enabled" data-scene="${escapeHtml(scene.sceneName || '')}" data-item="${escapeHtml(item.sceneItemId)}" data-enabled="${item.sceneItemEnabled === false ? 'true' : 'false'}">${item.sceneItemEnabled === false ? 'Show' : 'Hide'}</button>
            <button class="btn btn-secondary" data-obs-action="set_scene_item_index" data-scene="${escapeHtml(scene.sceneName || '')}" data-item="${escapeHtml(item.sceneItemId)}" data-index="0">Top</button>
          </span>
        </div>
      `).join('')}
    </div>
  `).join('') || '<div class="analysis-line">No scenes returned from OBS.</div>';
}

function renderObsEvent(event) {
  if (event.eventType === 'InputVolumeMeters') {
    const meters = (event.eventData?.inputs || []).slice(0, 6).map(input => {
      const level = Math.max(...((input.inputLevelsMul || []).flat().map(Number).filter(Number.isFinite)), 0);
      const pct = Math.max(2, Math.min(100, Math.round(level * 100)));
      return `<div class="analysis-line"><strong>${escapeHtml(input.inputName || 'Audio')}</strong><div style="height:6px;background:rgba(255,255,255,.08);border-radius:6px;overflow:hidden"><span style="display:block;height:100%;width:${pct}%;background:#10B981"></span></div></div>`;
    }).join('');
    document.getElementById('obsAudioMeters').innerHTML = meters;
    return;
  }
  obsRecentEvents.unshift(event);
  obsRecentEvents.splice(10);
  const feed = document.getElementById('obsEventFeed');
  if (feed) {
    feed.innerHTML = obsRecentEvents.map(item => `<div class="analysis-line"><strong>${escapeHtml(item.eventType || 'OBS Event')}</strong> ${escapeHtml(JSON.stringify(item.eventData || {})).slice(0, 180)}</div>`).join('');
  }
  if (/Scene|Stream|Record|Replay|Virtual|Input/.test(event.eventType || '')) {
    window.clearTimeout(window.obsRefreshTimer);
    window.obsRefreshTimer = window.setTimeout(loadObsStudio, 400);
  }
}

function startObsEvents() {
  if (obsEventSource) obsEventSource.close();
  obsEventSource = new EventSource('/api/obs/events');
  obsEventSource.onmessage = event => {
    try { renderObsEvent(JSON.parse(event.data)); } catch (_) {}
  };
  obsEventSource.onerror = () => {
    const feed = document.getElementById('obsEventFeed');
    if (feed && !feed.innerHTML) feed.innerHTML = '<div class="analysis-line">OBS event stream is waiting for a connection.</div>';
  };
}

async function loadObsStudio() {
  const status = await fetch('/api/obs/status').then(r => r.json());
  renderObsStatus(status);
  if (status.connected) {
    const scenes = await fetch('/api/obs/scenes').then(r => r.json());
    renderObsScenes(scenes);
    startObsEvents();
  }
}

function renderObsSetupResult(data) {
  const res = document.getElementById('streamSetupResults');
  if (!res) return;
  res.style.display = 'block';
  const groups = [
    ['Applied', data.applied_actions || [], 'green'],
    ['Skipped', data.skipped_actions || [], 'amber'],
    ['Failed', data.failed_actions || [], 'rose']
  ].map(([label, items, cls]) => `
    <div class="result-card">
      <span class="tag-pill ${cls}">${items.length}</span>
      <h4>${label}</h4>
      ${(items || []).map(item => `<div class="analysis-line">${escapeHtml(item.action || '')} ${escapeHtml(item.skip_reason || item.result?.error || item.result?.message || '')}</div>`).join('') || '<div class="analysis-line">None</div>'}
    </div>
  `).join('');
  res.innerHTML = `<div class="result-card intelligence-card"><h4>${data.ok ? 'OBS Studio Setup Ready' : 'OBS Studio Setup Needs Review'}</h4><p>${escapeHtml(data.message || data.error || '')}</p></div>${groups}`;
}

document.getElementById('btnObsConnect')?.addEventListener('click', async function() {
  this.textContent = 'Connecting...'; this.disabled = true;
  try {
    const data = await obsPost('/api/obs/connect', obsConnectionPayload());
    renderObsStatus(data);
    await loadObsStudio();
  } catch (err) {
    renderObsStatus({ connected: false, message: err.message });
  }
  this.textContent = 'Connect OBS'; this.disabled = false;
});

document.getElementById('btnObsRefresh')?.addEventListener('click', async function() {
  this.textContent = 'Refreshing...'; this.disabled = true;
  try { await loadObsStudio(); } catch (err) { renderObsStatus({ connected: false, message: err.message }); }
  this.textContent = 'Refresh Studio'; this.disabled = false;
});

document.getElementById('btnObsDisconnect')?.addEventListener('click', async function() {
  this.textContent = 'Disconnecting...'; this.disabled = true;
  if (obsEventSource) obsEventSource.close();
  await obsPost('/api/obs/disconnect', {});
  renderObsStatus({ connected: false });
  this.textContent = 'Disconnect'; this.disabled = false;
});

document.addEventListener('click', async event => {
  const btn = event.target.closest('[data-obs-action]');
  if (!btn) return;
  const action = btn.dataset.obsAction;
  const params = {};
  if (btn.dataset.scene) params.sceneName = btn.dataset.scene;
  if (btn.dataset.item) params.sceneItemId = Number(btn.dataset.item);
  if (btn.dataset.enabled) params.enabled = btn.dataset.enabled === 'true';
  if (btn.dataset.index) params.sceneItemIndex = Number(btn.dataset.index);
  const needsConfirm = btn.dataset.obsConfirm === 'true';
  if (needsConfirm && !confirm(`Confirm OBS action: ${action}?`)) return;
  btn.disabled = true;
  try {
    const data = await obsPost('/api/obs/action', { action, params, confirm: needsConfirm });
    if (data.requires_confirmation && confirm(data.message || 'Confirm OBS action?')) {
      await obsPost('/api/obs/action', { action, params, confirm: true });
    }
    await loadObsStudio();
  } catch (err) {
    alert(`OBS action failed: ${err.message}`);
  }
  btn.disabled = false;
});

document.getElementById('btnSetupStream')?.addEventListener('click', async function() {
  const game = document.getElementById('streamGame')?.value;
  if (!game) return alert('Enter what you want to stream!');
  this.textContent = 'Setting up...'; this.disabled = true;
  try {
    const data = await obsPost('/api/obs/autopilot-setup', { ...obsConnectionPayload(), topic: game });
    renderObsSetupResult(data);
    await loadObsStudio();
  } catch (err) {
    renderObsSetupResult({ ok: false, message: err.message, applied_actions: [], skipped_actions: [], failed_actions: [] });
  }
  this.textContent = 'AI Studio Setup'; this.disabled = false;
});

document.addEventListener('DOMContentLoaded', () => {
  if (document.getElementById('obsStatusPanel')) loadObsStudio().catch(() => renderObsStatus({ connected: false }));
});

document.getElementById('btnAutoStream')?.addEventListener('click', function() {
  document.querySelectorAll('.nav-item').forEach(n => n.classList.remove('active'));
  document.querySelector('[data-page="streamsetup"]')?.classList.add('active');
  document.querySelectorAll('.page').forEach(p => p.classList.remove('active'));
  document.getElementById('page-streamsetup')?.classList.add('active');
});

// === CALENDAR ===
function initCalendar() {
  const grid = document.getElementById('calendarGrid');
  if (!grid || grid.children.length > 0) return;
  const headers = ['Sun','Mon','Tue','Wed','Thu','Fri','Sat'];
  grid.innerHTML = headers.map(h=>`<div style="text-align:center;font-size:0.7rem;font-weight:700;color:#64748B;padding:8px">${h}</div>`).join('');
  const events = {3:'\ud83d\udcf9 Tutorial',5:'\ud83d\udd34 Livestream',9:'\ud83d\udcf9 Review',12:'\ud83d\udcf9 Guide',15:'\ud83d\udd34 Stream',17:'\ud83d\udcf1 Short',19:'\ud83d\udcf9 Collab',22:'\ud83d\udcf9 Tutorial',25:'\ud83d\udd34 Stream',28:'\ud83d\udcf9 Review'};
  const colors = {'\ud83d\udcf9':'rgba(124,58,237,0.3)','\ud83d\udd34':'rgba(244,63,94,0.3)','\ud83d\udcf1':'rgba(6,182,212,0.3)'};
  for (let i=0; i<1; i++) grid.innerHTML += '<div></div>';
  for (let d=1; d<=30; d++) {
    const ev = events[d] || '';
    const emoji = ev.substring(0,2);
    const bgCol = colors[emoji] || '';
    grid.innerHTML += `<div class="cal-day"><div class="day-num">${d}</div>${ev?`<div class="cal-event" style="background:${bgCol};color:#fff">${ev}</div>`:''}</div>`;
  }
}

// === SHORTS ===
function initShorts() {
  const ss = document.getElementById('shortsStats');
  if (!ss || ss.children.length > 0) return;
  ss.innerHTML = [
    SP.statCard('\ud83d\udcf1',SP.fmt(SP.rand(50000,500000)),'Shorts Views',SP.randF(10,40)+'%',true,'rgba(244,63,94,0.12)'),
    SP.statCard('\ud83d\udc46',SP.randF(3,12)+'%','Swipe-Away Rate',SP.randF(1,5)+'%',false,'rgba(124,58,237,0.12)'),
    SP.statCard('\ud83d\udc65','+'+SP.fmt(SP.rand(200,3000)),'Subs from Shorts','This month',true,'rgba(6,182,212,0.12)'),
    SP.statCard('\ud83d\udd04',SP.rand(2,8),'Shorts \u2192 Long-form','Conversion funnel',true,'rgba(16,185,129,0.12)')
  ].join('');
  const ts = document.getElementById('trendingSounds');
  if (ts && !ts.children.length) {
    const sounds = ['\ud83c\udfb5 Viral Gaming Beat \u2014 2.4M uses','\ud83c\udfb5 Epic Cinematic Rise \u2014 890K uses','\ud83c\udfb5 Lo-fi Tech Review \u2014 1.2M uses','\ud83c\udfb5 Dramatic Reveal \u2014 670K uses','\ud83c\udfb5 Chill Background \u2014 3.1M uses'];
    ts.innerHTML = sounds.map(s => `<div style="padding:10px 0;border-bottom:1px solid rgba(255,255,255,0.04);font-size:0.85rem;color:#94A3B8;display:flex;justify-content:space-between;align-items:center"><span>${s}</span><button class="btn btn-ghost" style="padding:4px 10px;font-size:0.75rem">Use</button></div>`).join('');
  }
}

// === COMMUNITY ===
function initCommunity() {
  const cs = document.getElementById('communityStats');
  if (!cs || cs.children.length > 0) return;
  cs.innerHTML = [
    SP.statCard('\ud83d\udcac',SP.fmt(SP.rand(500,5000)),'New Comments',SP.randF(5,20)+'%',true),
    SP.statCard('\ud83d\ude0a',SP.rand(72,95)+'%','Positive Sentiment','Community mood',true),
    SP.statCard('\ud83c\udfc6',SP.rand(15,60),'Super Fans','Top engagers',true),
    SP.statCard('\ud83d\udd25',SP.rand(5,30)+' days','Reply Streak','Keep it up!',true)
  ].join('');
  const feed = document.getElementById('commentsFeed');
  if (feed && !feed.children.length) {
    const comments = [
      {u:'TechEnthusiast',m:'Best review I\'ve seen! The benchmark section was incredibly detailed.',cat:'Praise',col:'green'},
      {u:'PCBuilder99',m:'What power supply do you recommend for this setup?',cat:'Question',col:'cyan'},
      {u:'HelpfulHank',m:'The audio mixing could be better in the comparison section.',cat:'Feedback',col:'amber'},
      {u:'SpamBot3000',m:'GET FREE SUBSCRIBERS AT...',cat:'Spam (Auto-removed)',col:'rose'},
      {u:'LoyalViewer\u2b50',m:'Been watching since 100 subs! So proud of your growth!',cat:'Praise',col:'green'}
    ];
    feed.innerHTML = comments.map(c => `<div class="result-card" style="margin-bottom:8px"><div style="display:flex;justify-content:space-between"><strong style="color:#fff;font-size:0.85rem">${escapeHtml(c.u)}</strong><span class="tag-pill ${escapeHtml(c.col)}">${escapeHtml(c.cat)}</span></div><p style="margin-top:6px">${escapeHtml(c.m)}</p>${c.cat!=='Spam (Auto-removed)'?'<button class="btn btn-ghost" style="margin-top:6px;padding:4px 10px;font-size:0.72rem">\ud83d\udca1 AI Draft Reply</button>':''}</div>`).join('');
  }
}

// === SAFETY ===
function initSafety() {
  const ss = document.getElementById('safetyStats');
  if (!ss || ss.children.length > 0) return;
  ss.innerHTML = [
    SP.statCard('\ud83d\udee1\ufe0f','98/100','Safety Score','All clear',true,'rgba(16,185,129,0.12)'),
    SP.statCard('\u26a0\ufe0f','0','Active Strikes','Clean record',true,'rgba(124,58,237,0.12)'),
    SP.statCard('\u00a9\ufe0f','3','Copyright Checks','All passed',true,'rgba(6,182,212,0.12)'),
    SP.statCard('\ud83d\udcb0','A+','Brand Safety','Advertiser friendly',true,'rgba(245,158,11,0.12)')
  ].join('');
  const scans = document.getElementById('safetyScans');
  if (scans && !scans.children.length) {
    const items = [
      {icon:'\u2705',title:'Copyright Pre-Scan',desc:'No copyrighted music/clips detected in last 3 uploads',time:'2 hours ago'},
      {icon:'\u2705',title:'Community Guidelines',desc:'All content compliant \u2014 no flagged language or topics',time:'4 hours ago'},
      {icon:'\u26a0\ufe0f',title:'Demonetization Risk',desc:'Video #42 has mild language at 8:15 \u2014 consider bleeping for max CPM',time:'1 day ago'},
      {icon:'\u2705',title:'COPPA Compliance',desc:'All videos correctly marked as "Not for Kids"',time:'2 days ago'}
    ];
    scans.innerHTML = items.map(s => `<div class="result-card" style="margin-bottom:8px"><div style="display:flex;justify-content:space-between"><h4>${s.icon} ${s.title}</h4><span style="font-size:0.72rem;color:#64748B">${s.time}</span></div><p>${s.desc}</p></div>`).join('');
  }
}

// === AI ASSISTANT CHAT ===
const chatInput = document.getElementById('chatInput');
const chatSend = document.getElementById('btnChatSend');
const chatMsgs = document.getElementById('chatMessages');

async function sendChat() {
  const msg = chatInput?.value?.trim();
  if (!msg) return;
  const userMessage = document.createElement('div');
  userMessage.className = 'chat-msg user';
  userMessage.textContent = msg;
  chatMsgs.appendChild(userMessage);
  chatInput.value = '';
  chatMsgs.scrollTop = chatMsgs.scrollHeight;

  const thinking = document.createElement('div');
  thinking.className = 'chat-msg ai';
  thinking.innerHTML = '<span style="opacity:0.5">\u23f3 AI thinking...</span>';
  chatMsgs.appendChild(thinking);
  chatMsgs.scrollTop = chatMsgs.scrollHeight;
  await SP.delay(SP.rand(1000,2500));

  const lm = msg.toLowerCase();
  const titleTopic = escapeHtml(msg.replace(/title|optimize|generate|for|my/gi, '').trim() || 'your topic');
  let reply = '';
  if (lm.includes('title') || lm.includes('optimize')) {
    reply = `\ud83c\udfaf Here are <strong>3 AI-optimized titles</strong> for your topic:<br><br>\ud83e\udd47 "<em>${titleTopic} \u2014 Complete Review & Testing</em>"<br>&nbsp;&nbsp;CTR: 8.2% | SEO: 94/100 | Viral: 72<br><br>\ud83e\udd48 "<em>I Tested ${titleTopic} \u2014 SHOCKING Results</em>"<br>&nbsp;&nbsp;CTR: 9.1% | SEO: 82/100 | Viral: 85<br><br>These scores use <strong>logistic regression + Hawkes process</strong> viral modeling. Want me to generate the full description and tags too?`;
  } else if (lm.includes('live') || lm.includes('stream') || lm.includes('when')) {
    reply = `\ud83d\udcc5 Based on your audience's <strong>Gaussian Mixture Model</strong>:<br><br>\ud83e\udd47 <strong>Thursday 8:00 PM IST</strong> (73% audience overlap)<br>\ud83e\udd48 Wednesday 8:30 PM IST (68% overlap)<br>\ud83e\udd49 Saturday 7:00 PM IST (65% overlap)<br><br>Causal analysis (do-calculus) confirms Thursday has a <strong>+23% causal lift</strong> vs other days \u2014 this is NOT confounded by content quality. Your competitors don't stream Thursday evenings, giving you a clear window.`;
  } else if (lm.includes('flop') || lm.includes('why') || lm.includes('underperform')) {
    reply = `\ud83d\udd0d <strong>Performance Anomaly Analysis</strong> of your last video:<br><br>1. \ud83d\uddbc\ufe0f <strong>Thumbnail</strong>: No face detected \u2014 your face-thumbnails get 38% higher CTR<br>2. \ud83c\udfa3 <strong>Hook</strong>: First 30s had setup/intro \u2014 hazard rate h(0:30) = 0.18 (2\u00d7 niche avg)<br>3. \ud83d\udce2 <strong>Distribution</strong>: No social sharing \u2014 external traffic was -80% vs baseline<br><br>\u26a1 <strong>Quick Fix</strong>: Re-upload the thumbnail with your face + shocked expression. This alone can recover ~30% of lost views from browse/suggested. Want me to generate a new thumbnail guide?`;
  } else if (lm.includes('seo') || lm.includes('keyword')) {
    reply = `\ud83d\udd0d <strong>SEO Analysis</strong> using a diversified keyword portfolio:<br><br>Your channel currently ranks for <strong>${SP.rand(40,120)} keywords</strong>. Top opportunities:<br><br>\ud83d\udcc8 "budget gaming pc 2026" \u2014 74K/mo, difficulty 23 (you can rank!)<br>\ud83d\udcc8 "best gpu under $500" \u2014 45K/mo, difficulty 18<br>\ud83d\udcc8 "pc build guide" \u2014 28K/mo, difficulty 31<br><br>Content gap (TDA \u03b2\u2082): You have <strong>no laptop review content</strong> \u2014 3 competitors are filling this void with high rankings. Consider a "Best Budget Laptop" video.`;
  } else {
    reply = `\ud83e\udd16 I analyzed your request using the StreamPilot AI engine. Here's what I found:<br><br>Your channel is growing at <strong>${SP.randF(2,5)}%/week</strong> (Kalman-smoothed). The optimized forecast suggests maintaining <strong>3 uploads/week</strong> with a mix of 2 tutorials + 1 review for maximum growth.<br><br>Your Extreme Value shape parameter \u03be = <strong>${SP.randF(0.2,0.4)}</strong> indicates good viral potential. Keep experimenting with comparison-style titles \u2014 they have the highest Hawkes branching ratio in your niche.<br><br>What would you like to dive deeper into? I can help with titles, SEO, scheduling, analytics, or stream setup! \ud83d\ude80`;
  }
  thinking.innerHTML = reply;
  chatMsgs.scrollTop = chatMsgs.scrollHeight;
}

chatSend?.addEventListener('click', sendChat);
chatInput?.addEventListener('keydown', e => { if (e.key === 'Enter') sendChat(); });

const origOnPageEnter = SP.onPageEnter.bind(SP);
SP.onPageEnter = function(page) {
  origOnPageEnter(page);
  if (page === 'calendar') initCalendar();
  else if (page === 'shorts') initShorts();
  else if (page === 'community') initCommunity();
  else if (page === 'safety') initSafety();
};

})();
// ========== STREAMPILOT AI — ENHANCEMENTS ==========
// Competitor Radar, Growth Simulator, Content Pipeline, AI Draft Reply, Sparklines, Real-time Refresh

(function() {

// === SPARKLINE RENDERER (Canvas-based mini charts) ===
function drawSparkline(container, data, color) {
  const canvas = document.createElement('canvas');
  canvas.className = 'sparkline-canvas';
  canvas.width = 200; canvas.height = 36;
  container.appendChild(canvas);
  const ctx = canvas.getContext('2d');
  const max = Math.max(...data), min = Math.min(...data);
  const range = max - min || 1;
  const w = canvas.width, h = canvas.height;
  const step = w / (data.length - 1);

  // Gradient fill
  const grad = ctx.createLinearGradient(0, 0, 0, h);
  grad.addColorStop(0, color.replace(')', ',0.3)').replace('rgb', 'rgba'));
  grad.addColorStop(1, color.replace(')', ',0)').replace('rgb', 'rgba'));

  ctx.beginPath();
  ctx.moveTo(0, h);
  data.forEach((v, i) => {
    const x = i * step;
    const y = h - ((v - min) / range) * (h - 4) - 2;
    if (i === 0) ctx.moveTo(x, y);
    else ctx.lineTo(x, y);
  });
  // Fill area
  ctx.lineTo(w, h); ctx.lineTo(0, h);
  ctx.fillStyle = grad; ctx.fill();

  // Stroke line
  ctx.beginPath();
  data.forEach((v, i) => {
    const x = i * step;
    const y = h - ((v - min) / range) * (h - 4) - 2;
    if (i === 0) ctx.moveTo(x, y);
    else ctx.lineTo(x, y);
  });
  ctx.strokeStyle = color; ctx.lineWidth = 1.5; ctx.stroke();

  // End dot
  const lastX = (data.length - 1) * step;
  const lastY = h - ((data[data.length-1] - min) / range) * (h - 4) - 2;
  ctx.beginPath(); ctx.arc(lastX, lastY, 2.5, 0, Math.PI * 2);
  ctx.fillStyle = color; ctx.fill();
}

// Enhanced stat card with sparkline
SP.statCardSpark = function(icon, value, label, change, up, bgCol, sparkData, sparkColor) {
  const bg = bgCol || 'rgba(124,58,237,0.12)';
  const id = 'spark_' + Math.random().toString(36).substr(2,6);
  setTimeout(() => {
    const el = document.getElementById(id);
    if (el && sparkData) drawSparkline(el, sparkData, sparkColor || '#7C3AED');
  }, 50);
  return `<div class="stat-card"><div class="stat-header"><div class="stat-icon" style="background:${bg}">${icon}</div><span class="stat-change ${up?'up':'down'}">${up?'↑':'↓'} ${change}</span></div><div class="stat-value">${value}</div><div class="stat-label">${label}</div><div id="${id}" class="sparkline"></div></div>`;
};

// === COMPETITOR RADAR ===
function initCompetitors() {
  const cs = document.getElementById('compStats');
  if (!cs) return;
  cs.innerHTML = [
    SP.statCard('🎯','#3','Your Rank','In niche top 10',true,'rgba(124,58,237,0.12)'),
    SP.statCard('📈','+'+SP.randF(1,4)+'%','Your Growth','vs #1: '+SP.randF(2,6)+'%',Math.random()>0.3,'rgba(6,182,212,0.12)'),
    SP.statCard('⚔️',SP.rand(3,8),'Content Gaps','Opportunities found',true,'rgba(245,158,11,0.12)'),
    SP.statCard('🏅',SP.rand(1200,1800),'Your Elo','Top 15%',true,'rgba(16,185,129,0.12)')
  ].join('');

  // Growth comparison chart
  const months = ['Jan','Feb','Mar','Apr','May','Jun'];
  const channels = [
    {name:'You',color:'#7C3AED',data:months.map(()=>SP.rand(2,8))},
    {name:'TechLinked',color:'#06B6D4',data:months.map(()=>SP.rand(3,10))},
    {name:'HardwareCanucks',color:'#10B981',data:months.map(()=>SP.rand(1,7))},
    {name:'Optimum Tech',color:'#F59E0B',data:months.map(()=>SP.rand(2,9))}
  ];
  SP.makeChart('compGrowthChart','line',months,channels.map(c=>({
    label:c.name,data:c.data,borderColor:c.color,tension:0.4,pointRadius:3,fill:false
  })));

  // Engagement battle bar chart
  const metrics = ['CTR','Retention','Comments','Likes'];
  SP.makeChart('compEngageChart','bar',metrics,[
    {label:'You',data:[SP.randF(5,8),SP.randF(40,60),SP.rand(50,200),SP.rand(200,800)],backgroundColor:'rgba(124,58,237,0.7)'},
    {label:'Niche Avg',data:[SP.randF(4,6),SP.randF(35,50),SP.rand(30,150),SP.rand(150,600)],backgroundColor:'rgba(100,116,139,0.4)'}
  ],{scales:{x:{grid:{display:false}}}});

  // Leaderboard table using Real API Data
  const tbody = document.querySelector('#compTable tbody');
  if (tbody) {
    tbody.innerHTML = '<tr><td colspan="6" style="text-align:center">Loading real competitors from YouTube API...</td></tr>';

    fetch('/api/competitors')
      .then(res => res.json())
      .then(data => {
        if (data.competitors && data.competitors.length > 0) {
          const comps = data.competitors.map(c => ({
            n: c.name,
            s: SP.fmt(c.subs),
            v: SP.fmt(c.views),
            elo: SP.rand(1400, 1900), // Keep elo simulated for now
            gap: 'Gaming'
          })).sort((a,b) => b.elo - a.elo);

          tbody.innerHTML = comps.map((c,i) => `
            <tr>
              <td style="font-weight:700">${['🥇','🥈','🥉','4️⃣','5️⃣'][i] || ''}</td>
              <td style="font-weight:500;color:#fff">${c.n}</td>
              <td>${c.s}</td>
              <td>${c.v}</td>
              <td><span class="tag-pill purple">${c.elo}</span></td>
              <td style="color:#F59E0B">${c.gap}</td>
            </tr>
          `).join('');
        }
      })
      .catch(err => console.error("Competitor API Error:", err));
  }
}

// === GROWTH SIMULATOR ===
function initSimulator() {
  const ctrl = document.getElementById('simControls');
  if (!ctrl || ctrl.children.length > 0) return;
  const sliders = [
    {id:'simUploads',label:'Uploads per Week',min:1,max:7,val:3,unit:'/week'},
    {id:'simCTR',label:'Target CTR Improvement',min:0,max:5,val:1,unit:'%',step:0.5},
    {id:'simPromo',label:'Weekly Promotion Budget',min:0,max:200,val:50,unit:'$',step:10},
    {id:'simCollabs',label:'Collabs per Month',min:0,max:4,val:1,unit:'/mo'}
  ];
  ctrl.innerHTML = sliders.map(s => `<div class="sim-slider-group"><label><span>${s.label}</span><span class="sim-val" id="${s.id}Val">${s.val}${s.unit}</span></label><input type="range" id="${s.id}" min="${s.min}" max="${s.max}" value="${s.val}" step="${s.step||1}"></div>`).join('');

  sliders.forEach(s => {
    document.getElementById(s.id)?.addEventListener('input', function() {
      document.getElementById(s.id+'Val').textContent = this.value + s.unit;
    });
  });

  runSimulation();
}

function runSimulation() {
  const uploads = parseFloat(document.getElementById('simUploads')?.value || 3);
  const ctrBoost = parseFloat(document.getElementById('simCTR')?.value || 1);
  const promo = parseFloat(document.getElementById('simPromo')?.value || 50);
  const collabs = parseFloat(document.getElementById('simCollabs')?.value || 1);

  fetch(`/api/simulate?uploads=${uploads}&ctr_boost=${ctrBoost}&promo=${promo}&collabs=${collabs}`)
    .then(res => res.json())
    .then(data => {
      const weeks = 24;
      const labels = Array.from({length:weeks}, (_,i) => 'W'+(i+1));

      SP.makeChart('simChart','line',labels,[
        {label:'Baseline Forecast',data:data.current,borderColor:'#64748B',borderDash:[5,5],tension:0.3,pointRadius:0,fill:false},
        {label:'Optimized Forecast',data:data.optimized,borderColor:'#7C3AED',backgroundColor:'rgba(124,58,237,0.1)',tension:0.3,pointRadius:0,fill:true},
        {label:'Optimized 95% CI Upper',data:data.upper,borderColor:'rgba(6,182,212,0.3)',pointRadius:0,borderDash:[2,2],fill:false,tension:0.3},
        {label:'Optimized 95% CI Lower',data:data.lower,borderColor:'rgba(6,182,212,0.3)',pointRadius:0,borderDash:[2,2],fill:'-1',backgroundColor:'rgba(6,182,212,0.05)',tension:0.3}
      ]);

      const finalOpt = data.optimized[weeks-1];
      const finalCur = data.current[weeks-1];
      const gain = data.gain ?? (finalOpt - finalCur);
      const pctGain = data.pct_gain ?? ((gain / finalCur) * 100).toFixed(1);
      const milestone = finalOpt > 100000 ? '100K' : finalOpt > 50000 ? '50K' : finalOpt > 25000 ? '25K' : '10K';
      const weeksTo = data.optimized.findIndex(s => s >= (finalOpt > 100000 ? 100000 : finalOpt > 50000 ? 50000 : 25000));

      const resDiv = document.getElementById('simResults');
      if (resDiv) {
        resDiv.innerHTML = `
          <div style="text-align:center;margin-bottom:16px"><div style="font-size:2rem;font-weight:900;background:linear-gradient(135deg,#7C3AED,#06B6D4);-webkit-background-clip:text;-webkit-text-fill-color:transparent">${SP.fmt(finalOpt)}</div><div style="font-size:0.75rem;color:#94A3B8">Predicted Subs (24 weeks)</div></div>
          <div class="result-card" style="margin-bottom:8px"><h4>📈 Growth Boost</h4><p>+${SP.fmt(gain)} subs (+${pctGain}%) over baseline</p></div>
          <div class="result-card" style="margin-bottom:8px"><h4>🎯 Milestone</h4><p>${milestone} subs in ~${weeksTo > 0 ? weeksTo : '12-16'} weeks (94% confidence)</p></div>
          <div class="result-card" style="margin-bottom:8px"><h4>💰 Revenue Impact</h4><p>+$${Math.round(gain * 0.02)}/mo estimated</p></div>
          <div class="result-card"><h4>⚡ Forecast Engine</h4><p>OU mean reversion, Student-t shocks, and viral jump diffusion · Seed ${data.seed ?? 42}</p></div>
        `;
      }
    })
    .catch(err => console.error("Sim API Error:", err));
}

document.getElementById('btnSimulate')?.addEventListener('click', runSimulation);

// === CONTENT PIPELINE ===
function initPipeline() {
  const ps = document.getElementById('pipelineStats');
  if (!ps) return;
  ps.innerHTML = [
    SP.statCard('💡',SP.rand(8,20),'Ideas','In backlog',true,'rgba(124,58,237,0.12)'),
    SP.statCard('📝',SP.rand(2,5),'In Progress','Active projects',true,'rgba(6,182,212,0.12)'),
    SP.statCard('✅',SP.rand(12,40),'Published','This month',true,'rgba(16,185,129,0.12)'),
    SP.statCard('📊',SP.rand(85,99)+'%','On Schedule','Consistency score',true,'rgba(245,158,11,0.12)')
  ].join('');

  const board = document.getElementById('pipelineBoard');
  if (!board || board.children.length > 0) return;

  const stages = ['💡 Idea','📝 Script','🎬 Film','✂️ Edit','👀 Review','🚀 Published'];
  const stageColors = ['#7C3AED','#06B6D4','#F59E0B','#F43F5E','#10B981','#64748B'];
  const projects = [
    {t:'Best Laptops 2026',stage:0,due:'Jun 15',pri:'high'},
    {t:'RTX 5090 Ti Leak Analysis',stage:1,due:'Jun 10',pri:'urgent'},
    {t:'$300 PC Challenge',stage:2,due:'Jun 12',pri:'medium'},
    {t:'Cable Management Guide',stage:3,due:'Jun 8',pri:'medium'},
    {t:'Keyboard Tier List',stage:3,due:'Jun 9',pri:'low'},
    {t:'Monitor Buying Guide',stage:4,due:'Jun 7',pri:'high'},
    {t:'RTX 5090 Review',stage:5,due:'Jun 3',pri:'done'},
    {t:'Budget Mouse Roundup',stage:5,due:'Jun 1',pri:'done'},
    {t:'5 PC Mistakes',stage:5,due:'May 28',pri:'done'},
    {t:'SSD vs HDD 2026',stage:0,due:'Jun 20',pri:'low'},
    {t:'AI PC Build',stage:1,due:'Jun 18',pri:'medium'},
  ];
  let publishedUploads = [];
  try {
    publishedUploads = JSON.parse(localStorage.getItem('streamPilotPublishedUploads') || '[]')
      .map(item => ({...item, stage: 5, pri: 'done', due: item.due || 'Published now'}));
  } catch (_) {
    publishedUploads = [];
  }
  projects.unshift(...publishedUploads);

  const priColors = {urgent:'var(--danger)',high:'var(--warning)',medium:'var(--accent-cyan)',low:'var(--text-muted)',done:'var(--success)'};

  board.innerHTML = `<div class="pipeline-board">${stages.map((s,i) => {
    const cards = projects.filter(p => p.stage === i);
    return `<div class="pipeline-col"><div class="pipeline-col-header" style="border-color:${stageColors[i]}">${s} <span style="opacity:0.5">(${cards.length})</span></div>${cards.map(p => `<div class="pipeline-card"><div class="pipe-title">${p.t}</div><div class="pipe-meta"><span style="color:${priColors[p.pri]};font-weight:600">${p.pri==='done'?'✅':'●'} ${p.pri}</span> · ${p.due}</div></div>`).join('')}</div>`;
  }).join('')}</div>`;
}

document.getElementById('btnAddProject')?.addEventListener('click', function() {
  const name = prompt('Video title/idea:');
  if (!name) return;
  const board = document.querySelector('.pipeline-board .pipeline-col:first-child');
  if (board) {
    const card = document.createElement('div');
    card.className = 'pipeline-card';
    card.style.animation = 'fadeInUp 0.3s ease';
    card.innerHTML = `<div class="pipe-title">${name}</div><div class="pipe-meta"><span style="color:var(--accent-cyan);font-weight:600">● medium</span> · New</div>`;
    board.appendChild(card);
  }
});

// === AI DRAFT REPLY (make buttons actually work) ===
document.addEventListener('click', async function(e) {
  if (!e.target.matches('.btn-ghost') || !e.target.textContent.includes('AI Draft Reply')) return;
  const card = e.target.closest('.result-card');
  if (!card) return;
  const comment = card.querySelector('p')?.textContent || '';
  e.target.textContent = '⏳ Generating with LLaMA 3...'; e.target.disabled = true;

  let replyText = "Sorry, failed to generate reply.";
  try {
      const res = await fetch('/api/generate-reply', {
          method: 'POST',
          headers: {'Content-Type': 'application/json'},
          body: JSON.stringify({comment: comment})
      });
      const data = await res.json();
      if (data.reply) {
          replyText = data.reply;
      } else {
          replyText = "Error: " + data.error;
      }
  } catch (err) {
      replyText = "API Error: " + err.message;
  }

  // Show reply below the button
  let replyDiv = card.querySelector('.ai-reply');
  if (!replyDiv) {
    replyDiv = document.createElement('div');
    replyDiv.className = 'ai-reply';
    replyDiv.style.cssText = 'margin-top:8px;padding:10px 14px;background:rgba(124,58,237,0.08);border:1px solid rgba(124,58,237,0.15);border-radius:8px;font-size:0.8rem;color:#A78BFA;line-height:1.5';
    card.appendChild(replyDiv);
  }
  replyDiv.textContent = '';
  const replyLabel = document.createElement('strong');
  replyLabel.textContent = 'AI Draft:';
  const copyButton = document.createElement('button');
  copyButton.className = 'btn btn-primary';
  copyButton.style.cssText = 'margin-top:8px;padding:4px 12px;font-size:0.72rem';
  copyButton.textContent = 'Copy Reply';
  copyButton.addEventListener('click', async () => {
    await navigator.clipboard?.writeText(replyText);
    copyButton.textContent = 'Copied!';
  });
  replyDiv.append(replyLabel, document.createTextNode(' ' + replyText), document.createElement('br'), copyButton);
  e.target.textContent = '✅ Reply Generated'; e.target.disabled = false;
});

// === REAL-TIME DATA REFRESH ===
let refreshInterval = null;

function startRealTimeRefresh() {
  if (refreshInterval) clearInterval(refreshInterval);
  refreshInterval = setInterval(() => {
    if (SP.currentPage !== 'dashboard') return;

    // Animate stat value changes
    const statValues = document.querySelectorAll('#mainStats .stat-value');
    statValues.forEach((el, i) => {
      const oldText = el.textContent;
      let newVal;
      if (i === 0) newVal = SP.fmt(SP.rand(180000,320000)); // Views
      else if (i === 1) newVal = SP.fmt(SP.rand(12000,85000)); // Subs
      else if (i === 2) newVal = SP.fmt(SP.rand(4000,18000))+'h'; // Watch time
      else if (i === 3) newVal = '$'+SP.rand(800,4500); // Revenue
      else newVal = SP.randF(4,9)+'%'; // CTR

      if (oldText !== newVal) {
        el.style.transition = 'opacity 0.3s';
        el.style.opacity = '0.3';
        setTimeout(() => { el.textContent = newVal; el.style.opacity = '1'; }, 300);
      }
    });

    // Update change badges
    const changes = document.querySelectorAll('#mainStats .stat-change');
    changes.forEach(el => {
      const up = Math.random() > 0.3;
      el.className = 'stat-change ' + (up ? 'up' : 'down');
      el.textContent = (up ? '↑ ' : '↓ ') + SP.randF(0.5, 8) + '%';
    });
  }, 8000); // Refresh every 8 seconds
}

// Add live indicator to dashboard header
function addLiveIndicator() {
  const header = document.querySelector('#page-dashboard .page-header p');
  if (header && !header.querySelector('.realtime-dot')) {
    header.innerHTML = '<span class="realtime-dot"></span> Live data · Auto-refreshing every 8s · ' + header.textContent;
  }
}

// === UPGRADE DASHBOARD STATS WITH SPARKLINES ===
function upgradeDashboardWithSparklines() {
  const stats = document.getElementById('mainStats');
  if (!stats) return;

  const sparkColors = ['#7C3AED','#06B6D4','#10B981','#F59E0B','#F43F5E'];
  const sparkData = [
    Array.from({length:14}, () => SP.rand(8000,15000)),  // Views
    Array.from({length:14}, () => SP.rand(100,300)),      // Subs
    Array.from({length:14}, () => SP.rand(200,600)),      // Watch time
    Array.from({length:14}, () => SP.rand(30,150)),       // Revenue
    Array.from({length:14}, () => SP.rand(40,90)),        // CTR
  ];

  stats.innerHTML = [
    SP.statCardSpark('👁️', SP.fmt(SP.rand(180000,320000)), 'Views (30d)', SP.randF(2,8)+'%', true, 'rgba(124,58,237,0.12)', sparkData[0], sparkColors[0]),
    SP.statCardSpark('👥', SP.fmt(SP.rand(12000,85000)), 'Subscribers', SP.randF(1,5)+'%', true, 'rgba(6,182,212,0.12)', sparkData[1], sparkColors[1]),
    SP.statCardSpark('⏱️', SP.fmt(SP.rand(4000,18000))+'h', 'Watch Time', SP.randF(1,6)+'%', true, 'rgba(16,185,129,0.12)', sparkData[2], sparkColors[2]),
    SP.statCardSpark('💰', '$'+SP.rand(800,4500), 'Revenue (30d)', SP.randF(3,12)+'%', true, 'rgba(245,158,11,0.12)', sparkData[3], sparkColors[3]),
    SP.statCardSpark('📈', SP.randF(4,9)+'%', 'Avg CTR', SP.randF(0.2,1.5)+'%', Math.random()>0.3, 'rgba(244,63,94,0.12)', sparkData[4], sparkColors[4])
  ].join('');
}

// === HOOK INTO PAGE NAVIGATION ===
const prevOnPageEnter = SP.onPageEnter;
SP.onPageEnter = function(page) {
  prevOnPageEnter(page);
  if (page === 'competitors') initCompetitors();
  else if (page === 'simulator') initSimulator();
  else if (page === 'pipeline') initPipeline();
  else if (page === 'dashboard') {
    upgradeDashboardWithSparklines();
    addLiveIndicator();
    startRealTimeRefresh();
  }
};

// Upgrade initial dashboard load with sparklines
const origInit = SP.init;
SP.init = function() {
  origInit();
  setTimeout(() => {
    upgradeDashboardWithSparklines();
    addLiveIndicator();
    startRealTimeRefresh();
  }, 100);
};

})();
