'use strict';
const $ = id => document.getElementById(id);
const form = $('audio-form');
const input = $('audio-input');
const colors = ['#678d49', '#487e99', '#b08054', '#8976ae', '#b56c80', '#4f978b', '#c19a3a', '#5f6fb8'];
let selected = null, previewUrl = null, report = null, speakerNames = [], segmentView = [], visibleSegments = 0, busy = false;
const allowed = new Set(input.accept.split(','));
const formatSeconds = value => `${Number(value).toLocaleString('es-CL', {maximumFractionDigits: 2})} s`;
function time(value) {
  const ms = Math.round(value * 1000);
  return `${Math.floor(ms / 60000)}:${String(Math.floor(ms / 1000) % 60).padStart(2,'0')}.${String(ms % 1000).padStart(3,'0')}`;
}
function clock(value) {
  const total = Math.round(value), h = Math.floor(total / 3600), m = Math.floor(total / 60) % 60, s = total % 60;
  return h ? `${h}:${String(m).padStart(2,'0')}:${String(s).padStart(2,'0')}` : `${m}:${String(s).padStart(2,'0')}`;
}
const speakerColor = name => colors[Math.max(0, speakerNames.indexOf(name)) % colors.length];
function error(message) { $('error').textContent = message; $('error').hidden = !message; }
function element(tag, text, className) {
  const node = document.createElement(tag); if (text !== undefined) node.textContent = text; if (className) node.className = className; return node;
}
function svg(tag, attrs = {}, text) {
  const node = document.createElementNS('http://www.w3.org/2000/svg', tag);
  for (const [key, value] of Object.entries(attrs)) node.setAttribute(key, value);
  if (text !== undefined) node.textContent = text;
  return node;
}
function dot(name) { const node = element('span', undefined, 'speaker-dot'); node.style.background = speakerColor(name); return node; }
function nameLabel(name) { const label = element('span', undefined, 'speaker-name'); label.append(dot(name), document.createTextNode(name)); return label; }
function playButton(key, label) {
  const button = element('button', '▶', 'play-button'); button.type = 'button'; button.dataset.playKey = key; button.setAttribute('aria-label', label); return button;
}
function tickStep(duration, maxTicks = 8) {
  for (const step of [1, 2, 5, 10, 15, 30, 60, 120, 300, 600, 900, 1800, 3600, 7200]) if (duration / step <= maxTicks) return step;
  return 7200;
}

// ---------- Reproductor de tramos ----------
const player = {
  audio: $('preview'), queue: [], pos: -1, key: null, raf: 0,
  play(ranges, key, title) {
    if (this.key === key) return this.stop();
    this.stop();
    if (!ranges.length) return;
    this.queue = ranges; this.pos = 0; this.key = key;
    $('player-title').textContent = title; $('player').hidden = false; $('player-error').hidden = true;
    for (const node of document.querySelectorAll(`[data-play-key="${CSS.escape(key)}"]`)) { node.classList.add('playing'); if (node.tagName === 'BUTTON') node.textContent = '■'; }
    this.start();
  },
  start() {
    const range = this.queue[this.pos];
    this.mark(range.segment);
    $('player-range').textContent = `${range.hablante} · ${time(range.inicio)} → ${time(range.fin)}${this.queue.length > 1 ? ` · tramo ${this.pos + 1} de ${this.queue.length}` : ''}`;
    seekAndPlay(this.audio, range.inicio).then(() => { cancelAnimationFrame(this.raf); this.tick(); }).catch(err => {
      this.stop();
      $('player-error').textContent = err && err.name === 'NotAllowedError' ? 'El navegador bloqueó la reproducción. Vuelve a pulsar ▶.' : 'Tu navegador no puede reproducir este formato de audio. Prueba con WAV, MP3 o M4A.';
      $('player-error').hidden = false;
    });
  },
  tick() {
    if (this.key === null) return;
    const range = this.queue[this.pos], audio = this.audio;
    if (audio.paused && !audio.seeking) return this.stop();
    const total = range.fin - range.inicio;
    $('player-progress').style.width = `${Math.min(100, Math.max(0, 100 * (audio.currentTime - range.inicio) / (total || 1)))}%`;
    if (audio.currentTime >= range.fin - 0.02 || audio.ended) {
      if (this.pos + 1 < this.queue.length) { this.pos += 1; return this.start(); }
      audio.pause(); return this.stop();
    }
    this.raf = requestAnimationFrame(() => this.tick());
  },
  mark(segment) {
    for (const node of document.querySelectorAll('.segment-now')) node.classList.remove('segment-now');
    if (segment === undefined) return;
    for (const node of document.querySelectorAll(`[data-segment="${segment}"]`)) node.classList.add('segment-now');
  },
  stop() {
    cancelAnimationFrame(this.raf);
    if (this.key !== null && !this.audio.paused) this.audio.pause();
    this.key = null; this.queue = []; this.pos = -1; this.mark();
    for (const node of document.querySelectorAll('.playing')) { node.classList.remove('playing'); if (node.tagName === 'BUTTON') node.textContent = '▶'; }
    $('player').hidden = true; $('player-progress').style.width = '0';
  },
};
function seekAndPlay(audio, seconds) {
  const go = () => { audio.currentTime = seconds; return audio.play(); };
  if (audio.readyState >= 1) return go();
  if (audio.error) return Promise.reject(audio.error);
  return new Promise((resolve, reject) => {
    const done = () => { audio.removeEventListener('loadedmetadata', done); audio.removeEventListener('error', fail); go().then(resolve, reject); };
    const fail = () => { audio.removeEventListener('loadedmetadata', done); audio.removeEventListener('error', fail); reject(audio.error); };
    audio.addEventListener('loadedmetadata', done); audio.addEventListener('error', fail);
  });
}
function segmentRange(index) { const s = report.segmentos[index]; return {inicio: s.inicio, fin: s.fin, hablante: s.hablante, segment: index}; }
document.addEventListener('click', e => {
  const button = e.target.closest('[data-play-key]'); if (!button || !report) return;
  const [kind, value] = button.dataset.playKey.split(':');
  if (kind === 'segment') player.play([segmentRange(Number(value))], button.dataset.playKey, 'Reproduciendo un turno');
  else if (kind === 'speaker') player.play(report.segmentos.map((s, i) => s.hablante === value ? segmentRange(i) : null).filter(Boolean), button.dataset.playKey, `Escuchando solo a ${value}`);
});
$('player-stop').addEventListener('click', () => player.stop());
player.audio.addEventListener('timeupdate', () => updatePlayhead(player.audio.currentTime));
player.audio.addEventListener('ended', () => updatePlayhead(null));

// ---------- Selección de archivo ----------
function selectFile(file) {
  if (busy || !file) return;
  player.stop();
  error(''); report = null; $('results').hidden = true; $('empty-results').hidden = false;
  if (previewUrl) URL.revokeObjectURL(previewUrl);
  previewUrl = null; $('preview').pause(); $('preview').removeAttribute('src'); $('preview').load(); $('preview').hidden = true;
  selected = null; $('analyze').disabled = true;
  $('file-title').textContent = 'Arrastra tu audio aquí';
  $('file-subtitle').textContent = 'o selecciona un archivo de tu equipo';
  const ext = '.' + file.name.split('.').pop().toLowerCase();
  if (!allowed.has(ext)) { error('Selecciona un archivo de audio compatible. Por ahora no se admiten videos.'); return; }
  if (!file.size) { error('El archivo está vacío. Selecciona otro audio.'); return; }
  if (file.size > Number(form.dataset.maxMb) * 1024 * 1024) { error(`El archivo supera ${form.dataset.maxMb} MB.`); return; }
  selected = file;
  $('file-title').textContent = file.name;
  $('file-subtitle').textContent = `${(file.size / 1024 / 1024).toFixed(2)} MB · Haz clic para cambiar de audio`;
  previewUrl = URL.createObjectURL(file); $('preview').src = previewUrl; $('preview').hidden = false;
  $('analyze').disabled = false;
}
input.addEventListener('change', () => selectFile(input.files[0]));
for (const event of ['dragenter','dragover']) $('dropzone').addEventListener(event, e => { e.preventDefault(); if (!busy) $('dropzone').classList.add('dragging'); });
for (const event of ['dragleave','drop']) $('dropzone').addEventListener(event, e => { e.preventDefault(); $('dropzone').classList.remove('dragging'); });
$('dropzone').addEventListener('drop', e => {
  if (e.dataTransfer.files.length > 1) { error('Selecciona un solo audio por análisis.'); return; }
  selectFile(e.dataTransfer.files[0]);
});

// ---------- Tarjetas y participación ----------
function renderStats(data) {
  const r = data.resumen || {};
  const cards = [[data.hablantes_detectados, 'Hablantes estimados'], [formatSeconds(data.duracion_total_archivo_seg), 'Duración del audio'],
    [formatSeconds(data.tiempo_total_voz_seg), `Tiempo de voz · ${r.porcentaje_voz_archivo ?? 0}% del archivo`], [formatSeconds(data.tiempo_silencio_seg), 'Sin voz atribuida'],
    [r.turnos_totales ?? 0, 'Turnos de habla'], [r.cambios_de_hablante ?? 0, 'Cambios de hablante'],
    [formatSeconds(r.turno_medio_seg ?? 0), 'Duración media de un turno'], [r.pausa_mas_larga ? formatSeconds(r.pausa_mas_larga.duracion_seg) : '—', r.pausa_mas_larga ? `Pausa más larga · en ${clock(r.pausa_mas_larga.inicio)}` : 'Pausa más larga']];
  $('stats').replaceChildren(...cards.map(([value, label]) => { const card = element('div', undefined, 'stat'); card.append(element('strong', String(value)), element('span', label)); return card; }));
}
function renderDonut(data) {
  const node = $('donut'); node.replaceChildren();
  const entries = Object.entries(data.hablantes); if (!entries.length) return;
  const size = 150, r = 54, c = 2 * Math.PI * r, chart = svg('svg', {viewBox: `0 0 ${size} ${size}`, width: size, height: size});
  let offset = 0;
  for (const [name, info] of entries) {
    const share = Math.max(0, Math.min(1, info.porcentaje / 100)) * c;
    const ring = svg('circle', {cx: size / 2, cy: size / 2, r, fill: 'none', stroke: speakerColor(name), 'stroke-width': 22, 'stroke-dasharray': `${share} ${c - share}`, 'stroke-dashoffset': -offset, transform: `rotate(-90 ${size / 2} ${size / 2})`});
    ring.append(svg('title', {}, `${name}: ${info.porcentaje}% (${formatSeconds(info.segundos)})`));
    chart.append(ring); offset += share;
  }
  chart.append(svg('text', {x: size / 2, y: size / 2 - 4, 'text-anchor': 'middle', class: 'donut-number'}, String(entries.length)));
  chart.append(svg('text', {x: size / 2, y: size / 2 + 16, 'text-anchor': 'middle', class: 'donut-label'}, entries.length === 1 ? 'voz' : 'voces'));
  node.append(chart);
}
function renderSpeakers(data) {
  $('speakers').replaceChildren();
  for (const [name, info] of Object.entries(data.hablantes)) {
    const row = element('div', undefined, 'speaker-row');
    const head = element('div', undefined, 'speaker-head'); head.append(playButton(`speaker:${name}`, `Escuchar solo a ${name}`), nameLabel(name));
    const bar = element('div', undefined, 'bar'), fill = element('span'); fill.style.width = `${Math.min(100, Math.max(0, info.porcentaje))}%`; fill.style.background = speakerColor(name); bar.append(fill); bar.setAttribute('aria-hidden','true');
    const meta = element('span', `${info.turnos} ${info.turnos === 1 ? 'turno' : 'turnos'} · ${info.porcentaje_archivo}% del archivo · habla desde ${clock(info.primera_intervencion_seg)} hasta ${clock(info.ultima_intervencion_seg)}`, 'speaker-meta');
    row.append(head, bar, element('span', `${formatSeconds(info.segundos)} · ${info.porcentaje}%`, 'speaker-time'), meta); $('speakers').append(row);
  }
  if (!Object.keys(data.hablantes).length) $('speakers').append(element('p', 'No se encontró voz suficiente para distinguir hablantes.', 'subtle'));
}
function renderComposition(data) {
  const node = $('composition'); node.replaceChildren();
  const vad = data.deteccion_voz || {}, total = data.duracion_total_archivo_seg || 0;
  const parts = [['Voz atribuida a hablantes', data.tiempo_total_voz_seg, '#678d49'], ['Voz descartada por ser muy breve', vad.tiempo_voz_descartada_seg ?? 0, '#d9b44a'], ['Silencio o ruido sin voz', vad.tiempo_sin_voz_seg ?? data.tiempo_silencio_seg, '#c9d0c4']];
  const bar = element('div', undefined, 'stack-bar'); bar.setAttribute('aria-hidden', 'true');
  for (const [label, value, color] of parts) { const piece = element('span'); piece.style.width = `${total ? 100 * value / total : 0}%`; piece.style.background = color; piece.title = `${label}: ${formatSeconds(value)}`; bar.append(piece); }
  node.append(bar);
  const list = element('ul', undefined, 'composition-list');
  for (const [label, value, color] of parts) {
    const item = element('li'), swatch = element('i'); swatch.style.background = color;
    item.append(swatch, element('span', label), element('strong', `${formatSeconds(value)} · ${total ? (100 * value / total).toFixed(1) : 0}%`)); list.append(item);
  }
  node.append(list);
  if (vad.regiones_detectadas !== undefined) node.append(element('p', `El detector de voz encontró ${vad.regiones_detectadas} regiones con habla; tras unir pausas muy cortas quedaron ${vad.contextos_utilizados} contextos lo bastante largos para extraer huellas vocales.`, 'subtle small'));
}

// ---------- Línea de tiempo ----------
let playheadLine = null, timelineScale = null;
function renderTimeline(data) {
  const node = $('timeline'); node.replaceChildren(); playheadLine = null; timelineScale = null;
  const duration = data.duracion_total_archivo_seg; if (!duration) return;
  const width = Math.max(320, node.clientWidth || 800), left = 92, right = 12, waveHeight = 60, laneHeight = 22, axisHeight = 26, top = 6;
  const lanes = speakerNames.length, height = top + waveHeight + 8 + lanes * laneHeight + axisHeight;
  const chart = svg('svg', {viewBox: `0 0 ${width} ${height}`, width, height, class: 'timeline-svg'});
  const x = t => left + (width - left - right) * t / duration;
  timelineScale = {x, left, width: width - left - right, duration};
  const background = svg('rect', {x: left, y: top, width: width - left - right, height: height - top - axisHeight, fill: '#f8faf5', class: 'seek-area'});
  background.append(svg('title', {}, 'Pulsa para saltar a este instante'));
  background.addEventListener('click', e => {
    const box = chart.getBoundingClientRect(), t = (e.clientX - box.left) * width / box.width;
    player.stop(); seekAndPlay(player.audio, Math.max(0, Math.min(duration, (t - left) / (width - left - right) * duration))).catch(() => {});
  });
  chart.append(background);
  // Forma de onda coloreada según el hablante activo en cada instante.
  const envelope = data.envolvente || {valores: []}, segments = data.segmentos, mid = top + waveHeight / 2;
  let cursor = 0;
  envelope.valores.forEach((value, i) => {
    const t0 = i * envelope.paso_seg, t1 = t0 + envelope.paso_seg, centre = (t0 + t1) / 2;
    while (cursor < segments.length && segments[cursor].fin <= centre) cursor += 1;
    const current = segments[cursor] && segments[cursor].inicio <= centre ? segments[cursor] : null;
    const h = Math.max(1.5, value * (waveHeight - 6));
    chart.append(svg('rect', {x: x(t0), y: mid - h / 2, width: Math.max(1, x(t1) - x(t0)), height: h, fill: current ? speakerColor(current.hablante) : '#cfd5c9', opacity: current ? 0.85 : 0.6}));
  });
  chart.append(svg('text', {x: left - 8, y: mid + 4, 'text-anchor': 'end', class: 'axis-label'}, 'Audio'));
  speakerNames.forEach((name, i) => {
    const y = top + waveHeight + 8 + i * laneHeight;
    chart.append(svg('text', {x: left - 8, y: y + laneHeight / 2 + 4, 'text-anchor': 'end', class: 'axis-label'}, name));
    chart.append(svg('line', {x1: left, x2: width - right, y1: y + laneHeight, y2: y + laneHeight, stroke: '#e6eae1'}));
  });
  segments.forEach((s, i) => {
    const y = top + waveHeight + 8 + speakerNames.indexOf(s.hablante) * laneHeight;
    const rect = svg('rect', {x: x(s.inicio), y: y + 3, width: Math.max(1.5, x(s.fin) - x(s.inicio)), height: laneHeight - 6, rx: 2, fill: speakerColor(s.hablante), class: 'segment-rect', 'data-play-key': `segment:${i}`, 'data-segment': i, tabindex: 0, role: 'button'});
    rect.append(svg('title', {}, `${s.hablante} · ${time(s.inicio)} → ${time(s.fin)} (${formatSeconds(s.fin - s.inicio)}) · pulsa para reproducir`));
    rect.addEventListener('keydown', e => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); rect.dispatchEvent(new MouseEvent('click', {bubbles: true})); } });
    chart.append(rect);
  });
  const axisY = height - axisHeight + 8, step = tickStep(duration, Math.max(3, Math.floor((width - left - right) / 70)));
  for (let t = 0; t <= duration + 1e-9; t += step) {
    chart.append(svg('line', {x1: x(t), x2: x(t), y1: axisY - 6, y2: axisY - 2, stroke: '#9aa596'}));
    chart.append(svg('text', {x: x(t), y: axisY + 10, 'text-anchor': t === 0 ? 'start' : 'middle', class: 'axis-label'}, clock(t)));
  }
  playheadLine = svg('line', {x1: left, x2: left, y1: top, y2: height - axisHeight, stroke: '#172d2a', 'stroke-width': 1.5, class: 'playhead', visibility: 'hidden'});
  chart.append(playheadLine);
  node.append(chart);
  updatePlayhead(player.audio.currentTime || null);
  $('legend').replaceChildren(...speakerNames.map(name => nameLabel(name)));
}
function updatePlayhead(seconds) {
  if (!playheadLine || !timelineScale) return;
  if (seconds === null || !Number.isFinite(seconds)) { playheadLine.setAttribute('visibility', 'hidden'); return; }
  const px = timelineScale.x(Math.max(0, Math.min(timelineScale.duration, seconds)));
  playheadLine.setAttribute('x1', px); playheadLine.setAttribute('x2', px); playheadLine.setAttribute('visibility', 'visible');
}

// ---------- Actividad por tramos ----------
function renderActivity(data) {
  const node = $('activity'); node.replaceChildren();
  const line = data.linea_tiempo || {tramos: []}; if (!line.tramos.length || !speakerNames.length) { node.append(element('p', 'No hay voz atribuida para mostrar.', 'subtle')); return; }
  const width = Math.max(320, node.clientWidth || 800), height = 190, left = 44, right = 10, top = 10, bottom = 30;
  const chart = svg('svg', {viewBox: `0 0 ${width} ${height}`, width, height, class: 'activity-svg'});
  const plotW = width - left - right, plotH = height - top - bottom, step = line.paso_seg;
  const maxY = Math.max(step, ...line.tramos.map(t => Object.values(t.hablantes).reduce((a, b) => a + b, 0)));
  const yScale = v => top + plotH - plotH * v / maxY;
  for (const frac of [0, 0.5, 1]) {
    const y = yScale(maxY * frac);
    chart.append(svg('line', {x1: left, x2: width - right, y1: y, y2: y, stroke: '#e6eae1'}));
    chart.append(svg('text', {x: left - 6, y: y + 4, 'text-anchor': 'end', class: 'axis-label'}, `${Math.round(maxY * frac)} s`));
  }
  const barW = plotW / line.tramos.length, gap = Math.min(3, barW * 0.2);
  line.tramos.forEach((tramo, i) => {
    let acc = 0;
    const x = left + i * barW + gap / 2;
    for (const name of speakerNames) {
      const value = tramo.hablantes[name]; if (!value) continue;
      const rect = svg('rect', {x, y: yScale(acc + value), width: Math.max(1, barW - gap), height: yScale(acc) - yScale(acc + value), fill: speakerColor(name)});
      rect.append(svg('title', {}, `${clock(tramo.inicio)} – ${clock(tramo.fin)} · ${name}: ${formatSeconds(value)}`));
      chart.append(rect); acc += value;
    }
    if (!Object.keys(tramo.hablantes).length) {
      const rect = svg('rect', {x, y: yScale(0) - 2, width: Math.max(1, barW - gap), height: 2, fill: '#d6dbd0'});
      rect.append(svg('title', {}, `${clock(tramo.inicio)} – ${clock(tramo.fin)} · sin voz atribuida`)); chart.append(rect);
    }
  });
  const every = Math.max(1, Math.ceil(line.tramos.length / Math.max(3, Math.floor(plotW / 70))));
  line.tramos.forEach((tramo, i) => {
    if (i % every) return;
    chart.append(svg('text', {x: left + i * barW, y: height - bottom + 16, 'text-anchor': 'start', class: 'axis-label'}, clock(tramo.inicio)));
  });
  node.append(chart);
  $('activity-caption').textContent = `Segundos de voz de cada hablante por tramo de ${step >= 60 ? `${step / 60} min` : `${step} s`}.`;
}

// ---------- Turnos y transiciones ----------
function renderTurns(data) {
  const node = $('turns'); node.replaceChildren();
  const entries = Object.entries(data.hablantes); if (!entries.length) { node.append(element('p', 'Sin turnos que mostrar.', 'subtle')); return; }
  const r = data.resumen || {}, maxTurns = Math.max(...entries.map(([, info]) => info.turnos));
  const table = element('table', undefined, 'mini-table'), head = element('tr');
  for (const title of ['Hablante', 'Turnos', 'Turno medio', 'Turno más largo', 'Primera · última intervención']) head.append(element('th', title));
  { const thead = element('thead'); thead.append(head); table.append(thead); }
  const body = element('tbody');
  for (const [name, info] of entries) {
    const row = element('tr'), nameCell = element('td'); nameCell.append(nameLabel(name));
    const turnsCell = element('td'), bar = element('div', undefined, 'bar small-bar'), fill = element('span'); fill.style.width = `${100 * info.turnos / maxTurns}%`; fill.style.background = speakerColor(name); bar.append(fill);
    turnsCell.append(element('strong', String(info.turnos)), bar);
    row.append(nameCell, turnsCell, element('td', formatSeconds(info.turno_medio_seg)), element('td', formatSeconds(info.turno_mas_largo_seg)), element('td', `${clock(info.primera_intervencion_seg)} · ${clock(info.ultima_intervencion_seg)}`));
    body.append(row);
  }
  table.append(body); const scroll = element('div', undefined, 'scroll-x'); scroll.append(table); node.append(scroll);
  const facts = [];
  if (r.turno_mas_largo) facts.push(`El turno más largo es de ${r.turno_mas_largo.hablante} (${formatSeconds(r.turno_mas_largo.duracion_seg)}, en ${clock(r.turno_mas_largo.inicio)}).`);
  if (r.pausas_entre_turnos) facts.push(`Hay ${r.pausas_entre_turnos} pausas entre turnos, de ${formatSeconds(r.pausa_media_seg)} en promedio.`);
  if (r.equilibrio_participacion !== undefined) facts.push(`Equilibrio de participación: ${r.equilibrio_participacion} / 100 (100 significa que todas las voces hablan lo mismo).`);
  if (r.hablante_principal) facts.push(`Voz principal: ${r.hablante_principal}.`);
  node.append(element('p', facts.join(' '), 'subtle small'));
}
function renderTransitions(data) {
  const node = $('transitions'); node.replaceChildren();
  const matrix = data.transiciones || {};
  if (speakerNames.length < 2) { node.append(element('p', 'Se necesitan al menos dos voces para ver la alternancia.', 'subtle')); return; }
  const max = Math.max(1, ...speakerNames.flatMap(a => speakerNames.map(b => (matrix[a] || {})[b] || 0)));
  const table = element('table', undefined, 'matrix'), head = element('tr'); head.append(element('th', 'De ↓ · A →'));
  for (const name of speakerNames) { const th = element('th'); th.append(nameLabel(name)); head.append(th); }
  { const thead = element('thead'); thead.append(head); table.append(thead); }
  const body = element('tbody');
  for (const from of speakerNames) {
    const row = element('tr'), th = element('th'); th.append(nameLabel(from)); row.append(th);
    for (const to of speakerNames) {
      const value = (matrix[from] || {})[to] || 0, cell = element('td', String(value));
      cell.style.background = `rgba(103, 141, 73, ${value ? 0.12 + 0.55 * value / max : 0})`;
      cell.title = from === to ? `${from} retoma la palabra tras una pausa: ${value}` : `${to} habla después de ${from}: ${value} veces`;
      row.append(cell);
    }
    body.append(row);
  }
  table.append(body); const scroll = element('div', undefined, 'scroll-x'); scroll.append(table); node.append(scroll);
  node.append(element('p', 'La diagonal cuenta las veces que una misma voz retoma la palabra tras una pausa.', 'subtle small'));
}

// ---------- Tabla de turnos ----------
function applySegmentFilter() {
  const chosen = $('segment-filter').value;
  segmentView = report.segmentos.map((s, i) => [s, i]).filter(([s]) => !chosen || s.hablante === chosen);
  $('segment-count').textContent = chosen ? `${segmentView.length} de ${report.segmentos.length} turnos` : `${report.segmentos.length} turnos`;
  $('segments-body').replaceChildren(); visibleSegments = 0; moreSegments();
}
function moreSegments() {
  const end = Math.min(visibleSegments + 100, segmentView.length);
  const fragment = document.createDocumentFragment();
  for (const [s, i] of segmentView.slice(visibleSegments, end)) {
    const row = element('tr'); row.dataset.segment = i;
    const playCell = element('td'); playCell.append(playButton(`segment:${i}`, `Reproducir turno ${i + 1}, ${s.hablante}, de ${time(s.inicio)} a ${time(s.fin)}`));
    const nameCell = element('td'); nameCell.append(nameLabel(s.hablante));
    row.append(playCell, element('td', String(i + 1)), nameCell, element('td', time(s.inicio)), element('td', time(s.fin)), element('td', formatSeconds(s.fin - s.inicio)));
    fragment.append(row);
  }
  $('segments-body').append(fragment); visibleSegments = end;
  $('more').hidden = end >= segmentView.length;
}
$('segment-filter').addEventListener('change', () => { if (report) applySegmentFilter(); });

// ---------- Diagnóstico técnico ----------
function renderDiagnostics(data) {
  const node = $('diagnostics'); node.replaceChildren();
  const diag = data.diagnostico_conteo || {};
  if (!Object.keys(diag).length) { node.append(element('p', 'No hubo suficiente voz para estimar el conteo.', 'subtle')); return; }
  const items = [];
  if (diag.huellas_extraidas !== undefined) items.push(['Huellas vocales extraídas', `${diag.huellas_extraidas} (${diag.huellas_fiables} de más de 1,2 s)`]);
  if (diag.referencias_totales !== undefined) items.push(['Referencias usadas para el conteo', `${diag.referencias_utilizadas} de ${diag.referencias_totales}`]);
  if (diag.estrategia) items.push(['Estrategia de agrupamiento', diag.estrategia === 'jerarquico_promedio_coseno' ? 'Jerárquica, enlace promedio, distancia coseno' : diag.estrategia]);
  if (diag.umbral_distancia !== undefined) items.push(['Umbral de distancia', String(diag.umbral_distancia)]);
  if (diag.corte_adaptado !== undefined) items.push(['Corte adaptado del árbol', `${diag.corte_adaptado} (salto ${diag.salto_fusion})`]);
  const list = element('dl', undefined, 'diag-list');
  for (const [label, value] of items) { list.append(element('dt', label), element('dd', value)); }
  node.append(list);
  if (diag.silueta_elegida !== undefined) {
    const s = diag.silueta_elegida, level = s < 0.35 ? 'débil' : s < 0.6 ? 'moderada' : 'clara';
    const wrap = element('div', undefined, 'meter-wrap'); wrap.append(element('strong', `Separación entre grupos (silueta): ${s} · ${level}`));
    const meter = element('div', undefined, 'meter'), fill = element('span'); fill.style.width = `${Math.max(0, Math.min(100, s * 100))}%`; fill.className = level; meter.append(fill); meter.setAttribute('aria-hidden', 'true');
    wrap.append(meter, element('p', 'Valor orientativo entre 0 y 1: más alto significa grupos de voz más compactos y distintos entre sí. No es una probabilidad.', 'subtle small'));
    node.append(wrap);
  }
  const distances = diag.distancias_entre_hablantes;
  if (distances && speakerNames.length > 1) {
    node.append(element('h4', 'Distancia entre las voces'));
    const table = element('table', undefined, 'matrix'), head = element('tr'); head.append(element('th', ''));
    for (const name of speakerNames) { const th = element('th'); th.append(nameLabel(name)); head.append(th); }
    { const thead = element('thead'); thead.append(head); table.append(thead); }
    const body = element('tbody');
    for (const a of speakerNames) {
      const row = element('tr'), th = element('th'); th.append(nameLabel(a)); row.append(th);
      for (const b of speakerNames) {
        const value = (distances[a] || {})[b], cell = element('td', value === undefined ? '—' : value.toFixed(2));
        if (a !== b && value !== undefined) { const close = diag.umbral_distancia !== undefined && value < diag.umbral_distancia; cell.className = close ? 'close' : 'far'; cell.title = close ? 'Voces parecidas: podrían ser la misma persona' : 'Voces claramente distintas'; }
        row.append(cell);
      }
      body.append(row);
    }
    table.append(body); const scroll = element('div', undefined, 'scroll-x'); scroll.append(table); node.append(scroll);
    node.append(element('p', 'Distancia coseno entre las huellas promedio (0 = idénticas, 2 = opuestas). Valores por debajo del umbral indican voces difíciles de separar.', 'subtle small'));
  }
  if (diag.candidatos && diag.candidatos.length) {
    node.append(element('h4', 'Candidatos evaluados'));
    const table = element('table', undefined, 'mini-table'), head = element('tr');
    for (const title of ['Hablantes', 'Silueta', 'Separación mínima']) head.append(element('th', title));
    { const thead = element('thead'); thead.append(head); table.append(thead); }
    const body = element('tbody');
    for (const c of diag.candidatos) { const row = element('tr'); row.append(element('td', String(c.hablantes)), element('td', String(c.silueta)), element('td', String(c.separacion))); body.append(row); }
    table.append(body); node.append(table);
  }
}

// ---------- Render general ----------
function render(data) {
  player.stop();
  report = data; speakerNames = Object.keys(data.hablantes);
  $('result-file').textContent = data.nombre_archivo;
  renderStats(data); renderDonut(data); renderSpeakers(data); renderComposition(data);
  $('warnings-list').replaceChildren(...data.advertencias.map(message => element('li', `⚠ ${message}`)));
  $('segment-filter').replaceChildren(element('option', 'Todos los hablantes'), ...speakerNames.map(name => { const option = element('option', name); option.value = name; return option; }));
  $('segment-filter').firstChild.value = '';
  applySegmentFilter();
  renderTurns(data); renderTransitions(data); renderDiagnostics(data);
  $('method').textContent = `Método de análisis: ${data.metodo}`;
  $('empty-results').hidden = true; $('results').hidden = false;
  renderTimeline(data); renderActivity(data);
  $('results').focus({preventScroll:true}); $('results').scrollIntoView({behavior:'smooth', block:'start'});
}
let resizeTimer = 0;
window.addEventListener('resize', () => {
  if (!report || $('results').hidden) return;
  clearTimeout(resizeTimer); resizeTimer = setTimeout(() => { renderTimeline(report); renderActivity(report); }, 150);
});
form.addEventListener('submit', async e => {
  e.preventDefault(); if (!selected || busy) return;
  busy = true; error(''); $('analyze').disabled = true; input.disabled = true;
  $('progress').hidden = false; form.setAttribute('aria-busy','true');
  player.stop(); $('results').hidden = true; $('empty-results').hidden = true;
  const start = Date.now();
  $('elapsed').textContent = 'Puede tardar según la duración del audio. Mantén esta página abierta.';
  const timer = setInterval(() => { $('elapsed').textContent = `${Math.floor((Date.now()-start)/1000)} s transcurridos · Mantén esta página abierta.`; }, 1000);
  try {
    const body = new FormData(); body.append('audio', selected);
    const response = await fetch('/api/diarizar', {method:'POST', body});
    const data = await response.json();
    if (!response.ok) throw new Error(data.error || 'No se pudo analizar el audio.');
    render(data);
  } catch (err) {
    error(err instanceof TypeError || err instanceof SyntaxError ? 'No se pudo conectar con el servidor. Comprueba que sigue abierto e inténtalo de nuevo.' : err.message);
    $('empty-results').hidden = false;
  } finally {
    clearInterval(timer); busy = false; input.disabled = false; $('analyze').disabled = !selected;
    $('progress').hidden = true; form.removeAttribute('aria-busy');
  }
});
$('more').addEventListener('click', moreSegments);
function download(content, type, suffix) {
  const url = URL.createObjectURL(new Blob([content], {type}));
  const link = element('a'); link.href = url; link.download = `${report.nombre_archivo.replace(/\.[^.]+$/, '')}-${suffix}`; link.click(); setTimeout(() => URL.revokeObjectURL(url), 1000);
}
$('download').addEventListener('click', () => { if (report) download(JSON.stringify(report, null, 2), 'application/json;charset=utf-8', 'diarizacion.json'); });
$('download-csv').addEventListener('click', () => {
  if (!report) return;
  const rows = [['turno', 'hablante', 'inicio_seg', 'fin_seg', 'duracion_seg'], ...report.segmentos.map((s, i) => [i + 1, s.hablante, s.inicio, s.fin, (s.fin - s.inicio).toFixed(4)])];
  download('﻿' + rows.map(row => row.map(v => `"${String(v).replace(/"/g, '""')}"`).join(';')).join('\r\n'), 'text/csv;charset=utf-8', 'turnos.csv');
});
