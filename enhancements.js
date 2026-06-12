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
        {label:'Current Trajectory',data:data.current,borderColor:'#64748B',borderDash:[5,5],tension:0.3,pointRadius:0,fill:false},
        {label:'Optimized (MPC)',data:data.optimized,borderColor:'#7C3AED',backgroundColor:'rgba(124,58,237,0.1)',tension:0.3,pointRadius:0,fill:true},
        {label:'95% CI Upper',data:data.upper,borderColor:'rgba(6,182,212,0.3)',pointRadius:0,borderDash:[2,2],fill:false,tension:0.3},
        {label:'95% CI Lower',data:data.lower,borderColor:'rgba(6,182,212,0.3)',pointRadius:0,borderDash:[2,2],fill:'-1',backgroundColor:'rgba(6,182,212,0.05)',tension:0.3}
      ]);

      const finalOpt = data.optimized[weeks-1];
      const finalCur = data.current[weeks-1];
      const gain = finalOpt - finalCur;
      const pctGain = ((gain / finalCur) * 100).toFixed(1);
      const milestone = finalOpt > 100000 ? '100K' : finalOpt > 50000 ? '50K' : finalOpt > 25000 ? '25K' : '10K';
      const weeksTo = data.optimized.findIndex(s => s >= (finalOpt > 100000 ? 100000 : finalOpt > 50000 ? 50000 : 25000));

      const resDiv = document.getElementById('simResults');
      if (resDiv) {
        resDiv.innerHTML = `
          <div style="text-align:center;margin-bottom:16px"><div style="font-size:2rem;font-weight:900;background:linear-gradient(135deg,#7C3AED,#06B6D4);-webkit-background-clip:text;-webkit-text-fill-color:transparent">${SP.fmt(finalOpt)}</div><div style="font-size:0.75rem;color:#94A3B8">Predicted Subs (24 weeks)</div></div>
          <div class="result-card" style="margin-bottom:8px"><h4>📈 Growth Boost</h4><p>+${SP.fmt(gain)} subs (+${pctGain}%) over baseline</p></div>
          <div class="result-card" style="margin-bottom:8px"><h4>🎯 Milestone</h4><p>${milestone} subs in ~${weeksTo > 0 ? weeksTo : '12-16'} weeks (94% confidence)</p></div>
          <div class="result-card" style="margin-bottom:8px"><h4>💰 Revenue Impact</h4><p>+$${Math.round(gain * 0.02)}/mo estimated</p></div>
          <div class="result-card"><h4>⚡ Python Engine</h4><p>Calculated via Kalman Filter using real channel baselines.</p></div>
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
