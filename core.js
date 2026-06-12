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
      {i:'\ud83d\udd2e',t:'Growth Forecast',d:'MPC trajectory: 3 uploads/wk for 8 wks = 94% chance of 50K subs.',m:'Kalman +142/day'}
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
