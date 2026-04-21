// ── DOM Refs ────────────────────────────────────────────────────────
const uploadZone   = document.getElementById('uploadZone');
const imageInput   = document.getElementById('imageInput');
const previewImg   = document.getElementById('previewImg');
const cityInput    = document.getElementById('cityInput');
const sleepInput   = document.getElementById('sleepInput');
const skinTypeInput= document.getElementById('skinTypeInput');
const hormonalInput= document.getElementById('hormonalInput');
const stressInput  = document.getElementById('stressInput');
const stressVal    = document.getElementById('stressVal');
const analyzeBtn   = document.getElementById('analyzeBtn');
const btnText      = document.getElementById('btnText');
const btnLoader    = document.getElementById('btnLoader');
const resultsPanel = document.getElementById('resultsPanel');

// ── Upload Zone ─────────────────────────────────────────────────────
uploadZone.addEventListener('click', () => imageInput.click());

uploadZone.addEventListener('dragover', e => {
  e.preventDefault();
  uploadZone.classList.add('dragover');
});
uploadZone.addEventListener('dragleave', () => uploadZone.classList.remove('dragover'));
uploadZone.addEventListener('drop', e => {
  e.preventDefault();
  uploadZone.classList.remove('dragover');
  const f = e.dataTransfer.files[0];
  if (f) handleFile(f);
});

imageInput.addEventListener('change', e => {
  if (e.target.files[0]) handleFile(e.target.files[0]);
});

function handleFile(file) {
  if (!file.type.startsWith('image/')) return alert('Please upload an image file.');
  const reader = new FileReader();
  reader.onload = ev => {
    previewImg.src = ev.target.result;
    previewImg.style.display = 'block';
    uploadZone.querySelector('.upload-icon').style.display = 'none';
    uploadZone.querySelector('.upload-text').style.display = 'none';
    uploadZone.querySelector('.upload-hint').style.display = 'none';
  };
  reader.readAsDataURL(file);
}

// ── Stress Slider ───────────────────────────────────────────────────
stressInput.addEventListener('input', () => {
  stressVal.textContent = stressInput.value;
});

// ── Analyze Button ──────────────────────────────────────────────────
analyzeBtn.addEventListener('click', runAnalysis);

async function runAnalysis() {
  analyzeBtn.disabled = true;
  btnText.style.display = 'none';
  btnLoader.style.display = 'flex';

  const formData = new FormData();
  formData.append('city',            cityInput.value || 'Mumbai');
  formData.append('sleep',           sleepInput.value || '7');
  formData.append('skin_type',       skinTypeInput.value);
  formData.append('hormonal_phase',  hormonalInput.value);
  formData.append('stress',          stressInput.value);

  if (imageInput.files[0]) {
    formData.append('image', imageInput.files[0]);
  }

  try {
    const resp = await fetch('/analyze', { method: 'POST', body: formData });
    const data = await resp.json();

    if (data.success) {
      renderResults(data);
      resultsPanel.style.display = 'block';
      setTimeout(() => {
        resultsPanel.scrollIntoView({ behavior: 'smooth', block: 'start' });
      }, 100);
    } else {
      alert('Analysis failed: ' + (data.error || 'Unknown error'));
    }
  } catch (err) {
    alert('Network error: ' + err.message);
  } finally {
    analyzeBtn.disabled = false;
    btnText.style.display = 'inline';
    btnLoader.style.display = 'none';
  }
}

// ── Render Results ──────────────────────────────────────────────────
function renderResults(data) {
  const { skin_analysis: sa, aqi_data: aqi, recommendations: recs } = data;

  // Risk badge
  const rb = document.getElementById('riskBadge');
  rb.textContent = recs.overall_risk.emoji + ' ' + recs.overall_risk.level + ' Risk';
  rb.style.background  = recs.overall_risk.color + '22';
  rb.style.border      = '1px solid ' + recs.overall_risk.color + '55';
  rb.style.color       = recs.overall_risk.color;

  // Big score ring animation
  const score = Math.round(sa.health_score);
  document.getElementById('bigScoreVal').textContent = score;
  const arc = document.getElementById('scoreArc');
  const circumference = 364.4;
  const offset = circumference - (score / 100) * circumference;
  setTimeout(() => {
    arc.style.transition = 'stroke-dashoffset 1.2s ease';
    arc.style.strokeDashoffset = offset;
  }, 100);

  // Score color
  const scoreColor = score >= 75 ? '#27ae60' : score >= 50 ? '#f39c12' : '#e74c3c';
  arc.style.stroke = scoreColor;
  document.getElementById('bigScoreVal').style.color = scoreColor;

  // Face detect note
  const fdn = document.getElementById('faceDetectNote');
  fdn.textContent = sa.face_detected
    ? '✅ Face detected — analysis on facial skin region'
    : '🔍 No face detected — used center region for analysis';

  // AQI info
  const aqiLabel = ['','Good','Fair','Moderate','Poor','Very Poor'][aqi.aqi] || 'Unknown';
  const aqiSource = aqi.source === 'live' ? 'Live' : 'Estimated';
  document.getElementById('aqiInfo').textContent =
    `📍 ${aqi.city} · AQI: ${aqiLabel} (${aqi.aqi}/5) · PM2.5: ${aqi.pm2_5} µg/m³ · ${aqiSource} data`;

  // Metrics
  const metricsGrid = document.getElementById('metricsGrid');
  const metrics = [
    { label: 'Redness',    val: sa.redness,            color: '#e74c3c' },
    { label: 'Oiliness',   val: sa.oiliness,           color: '#f39c12' },
    { label: 'Texture',    val: sa.texture_roughness,  color: '#9b59b6' },
    { label: 'Moisture',   val: sa.moisture,           color: '#3498db' },
    { label: 'Dark Spots', val: sa.dark_spots,         color: '#8e44ad' },
    { label: 'Tone Even',  val: 100 - sa.tone_unevenness, color: '#27ae60' },
  ];
  metricsGrid.innerHTML = metrics.map(m => `
    <div class="metric-card">
      <div class="metric-label">${m.label}</div>
      <div class="metric-val" style="color:${m.color}">${Math.round(m.val)}</div>
      <div class="metric-bar">
        <div class="metric-bar-fill" style="width:${Math.round(m.val)}%;background:${m.color}"></div>
      </div>
    </div>
  `).join('');

  // SPF
  document.getElementById('spfValue').textContent = recs.spf;

  // Ingredients
  const ingBlock = document.getElementById('ingredientsBlock');
  const ingList  = document.getElementById('ingredientsList');
  if (recs.active_ingredients && recs.active_ingredients.length) {
    ingList.innerHTML = recs.active_ingredients
      .map(i => `<span class="ingredient-tag">${i}</span>`).join('');
    ingBlock.style.display = 'block';
  }

  // Recommendations
  const recsBlock = document.getElementById('recsBlock');
  const recsList  = document.getElementById('recsList');
  if (recs.recommendations && recs.recommendations.length) {
    recsList.innerHTML = recs.recommendations.map(r => `<li>${r}</li>`).join('');
    recsBlock.style.display = 'block';
  }

  // Warnings
  const warnBlock = document.getElementById('warningsBlock');
  const warnList  = document.getElementById('warningsList');
  if (recs.warnings && recs.warnings.length) {
    warnList.innerHTML = recs.warnings.map(w => `<li>${w}</li>`).join('');
    warnBlock.style.display = 'block';
  } else {
    warnBlock.style.display = 'none';
  }

  // Lifestyle
  const lifeBlock = document.getElementById('lifestyleBlock');
  const lifeList  = document.getElementById('lifestyleList');
  if (recs.lifestyle && recs.lifestyle.length) {
    lifeList.innerHTML = recs.lifestyle.map(l => `<li>${l}</li>`).join('');
    lifeBlock.style.display = 'block';
  }
}

// ── Smooth nav link active state ────────────────────────────────────
document.querySelectorAll('.nav-links a, .hero-btn, .nav-cta').forEach(a => {
  a.addEventListener('click', e => {
    const href = a.getAttribute('href');
    if (href && href.startsWith('#')) {
      e.preventDefault();
      document.querySelector(href)?.scrollIntoView({ behavior: 'smooth' });
    }
  });
});
