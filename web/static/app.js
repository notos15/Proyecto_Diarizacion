'use strict';
const $ = id => document.getElementById(id);
const form = $('audio-form');
const input = $('audio-input');
const colors = ['#678d49', '#487e99', '#b08054', '#8976ae', '#b56c80', '#4f978b'];
let selected = null, previewUrl = null, report = null, visibleSegments = 0, busy = false;
const allowed = new Set(input.accept.split(','));
const formatSeconds = value => `${Number(value).toLocaleString('es-CL', {maximumFractionDigits: 2})} s`;
function time(value) {
  const ms = Math.round(value * 1000);
  return `${Math.floor(ms / 60000)}:${String(Math.floor(ms / 1000) % 60).padStart(2,'0')}.${String(ms % 1000).padStart(3,'0')}`;
}
function error(message) { $('error').textContent = message; $('error').hidden = !message; }
function selectFile(file) {
  if (busy || !file) return;
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
function element(tag, text, className) {
  const node = document.createElement(tag); if (text !== undefined) node.textContent = text; if (className) node.className = className; return node;
}
function moreSegments() {
  const end = Math.min(visibleSegments + 100, report.segmentos.length);
  const fragment = document.createDocumentFragment();
  for (const s of report.segmentos.slice(visibleSegments, end)) {
    const row = element('tr');
    for (const value of [s.hablante, time(s.inicio), time(s.fin), formatSeconds(s.fin - s.inicio)]) row.append(element('td', value));
    fragment.append(row);
  }
  $('segments-body').append(fragment); visibleSegments = end;
  $('more').hidden = end >= report.segmentos.length;
}
function render(data) {
  report = data; $('result-file').textContent = data.nombre_archivo;
  $('stats').replaceChildren();
  for (const [value, label] of [[data.hablantes_detectados, 'Hablantes estimados'], [formatSeconds(data.duracion_total_archivo_seg), 'Duración del audio'], [formatSeconds(data.tiempo_total_voz_seg), 'Tiempo de voz'], [formatSeconds(data.tiempo_silencio_seg), 'Sin voz atribuida']]) {
    const card = element('div', undefined, 'stat'); card.append(element('strong', value), element('span', label)); $('stats').append(card);
  }
  $('speakers').replaceChildren();
  Object.entries(data.hablantes).forEach(([name, info], i) => {
    const color = colors[i % colors.length], row = element('div', undefined, 'speaker-row');
    const label = element('div', undefined, 'speaker-name'), dot = element('span', undefined, 'speaker-dot'); dot.style.background = color; label.append(dot, document.createTextNode(name));
    const bar = element('div', undefined, 'bar'), fill = element('span'); fill.style.width = `${Math.min(100, Math.max(0, info.porcentaje))}%`; fill.style.background = color; bar.append(fill); bar.setAttribute('aria-hidden','true');
    row.append(label, bar, element('span', `${formatSeconds(info.segundos)} · ${info.porcentaje}%`, 'speaker-time')); $('speakers').append(row);
  });
  if (!Object.keys(data.hablantes).length) $('speakers').append(element('p', 'No se encontró voz suficiente para distinguir hablantes.', 'subtle'));
  $('warnings-list').replaceChildren(...data.advertencias.map(message => element('li', `⚠ ${message}`)));
  $('segment-count').textContent = `${data.segmentos.length} turnos`;
  $('segments-body').replaceChildren(); visibleSegments = 0; moreSegments();
  $('method').textContent = `Método de análisis: ${data.metodo}`;
  $('empty-results').hidden = true; $('results').hidden = false;
  $('results').focus({preventScroll:true}); $('results').scrollIntoView({behavior:'smooth', block:'start'});
}
form.addEventListener('submit', async e => {
  e.preventDefault(); if (!selected || busy) return;
  busy = true; error(''); $('analyze').disabled = true; input.disabled = true;
  $('progress').hidden = false; form.setAttribute('aria-busy','true');
  $('results').hidden = true; $('empty-results').hidden = true;
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
$('download').addEventListener('click', () => {
  if (!report) return;
  const url = URL.createObjectURL(new Blob([JSON.stringify(report, null, 2)], {type:'application/json;charset=utf-8'}));
  const link = element('a'); link.href = url; link.download = `${report.nombre_archivo.replace(/\.[^.]+$/, '')}-diarizacion.json`; link.click(); setTimeout(() => URL.revokeObjectURL(url), 1000);
});
