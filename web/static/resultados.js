'use strict';
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
  if (diag.estrategia) items.push(['Estrategia de agrupamiento', ({jerarquico_promedio_coseno: 'Jerárquica, enlace promedio, distancia coseno', kmeans_cantidad_fija: 'KMeans con cantidad indicada', cantidad_fija: 'Una sola voz indicada'})[diag.estrategia] || diag.estrategia]);
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
  $('result-file').textContent = `${data.nombre_archivo} · ${data.hablantes_solicitados === null ? 'Cantidad estimada automáticamente' : `Cantidad indicada: ${data.hablantes_solicitados}`}`;
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
  const speakerCount = selectedSpeakerCount();
  if (speakerMode !== 'auto' && !/^[1-9][0-9]*$/.test(speakerCount)) {
    error('La cantidad de hablantes debe ser un entero positivo.'); speakerInput.focus(); return;
  }
  busy = true; error(''); $('analyze').disabled = true; input.disabled = true; setControlsBusy(true);
  $('progress').hidden = false; form.setAttribute('aria-busy','true');
  player.stop(); $('results').hidden = true; $('empty-results').hidden = true;
  const start = Date.now();
  $('elapsed').textContent = 'Puede tardar según la duración del audio. Mantén esta página abierta.';
  const timer = setInterval(() => { $('elapsed').textContent = `${Math.floor((Date.now()-start)/1000)} s transcurridos · Mantén esta página abierta.`; }, 1000);
  try {
    const body = new FormData(); body.append('audio', selected);
    if (speakerCount) body.append('num_speakers', speakerCount);
    const response = await fetch('/api/diarizar', {method:'POST', body});
    const data = await response.json();
    if (!response.ok) throw new Error(data.error || 'No se pudo analizar el audio.');
    render(data);
  } catch (err) {
    error(err instanceof TypeError || err instanceof SyntaxError ? 'No se pudo conectar con el servidor. Comprueba que sigue abierto e inténtalo de nuevo.' : err.message);
    $('empty-results').hidden = false;
  } finally {
    clearInterval(timer); busy = false; input.disabled = false; setControlsBusy(false); $('analyze').disabled = !selected;
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
