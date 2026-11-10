'use strict';

// Opciones de hablantes: Automático, 1 a 6, u otra cantidad positiva.
let speakerMode = 'auto';
function selectedSpeakerCount() {
  return speakerMode === 'auto' ? '' : speakerMode === 'other' ? speakerInput.value : speakerMode;
}
for (const button of document.querySelectorAll('[data-speakers]')) {
  button.addEventListener('click', () => {
    if (busy) return;
    speakerMode = button.dataset.speakers;
    for (const choice of document.querySelectorAll('[data-speakers]')) {
      const active = choice === button;
      choice.classList.toggle('selected', active);
      choice.setAttribute('aria-pressed', String(active));
    }
    const custom = speakerMode === 'other';
    speakerInput.hidden = !custom;
    speakerInput.required = custom;
    if (!custom) speakerInput.value = '';
    else speakerInput.focus();
    error('');
  });
}

// El archivo subido conserva su selector y su vista previa actuales.
let sourceMode = 'upload';
let recording = null;
let requestingMicrophone = false;
let processingRecording = false;
function setControlsBusy(disabled) {
  const locked = disabled || requestingMicrophone || processingRecording || recording !== null;
  $('upload-tab').disabled = locked;
  $('record-tab').disabled = locked;
  $('start-record').disabled = locked;
  for (const choice of document.querySelectorAll('[data-speakers]')) choice.disabled = disabled;
  speakerInput.disabled = disabled;
}
function chooseSource(mode) {
  if (busy || requestingMicrophone || processingRecording || recording) return;
  if (mode !== sourceMode) resetSelection();
  sourceMode = mode;
  $('dropzone').hidden = mode !== 'upload';
  $('record-panel').hidden = mode !== 'record';
  for (const [id, active] of [['upload-tab', mode === 'upload'], ['record-tab', mode === 'record']]) {
    $(id).classList.toggle('active', active);
    $(id).setAttribute('aria-pressed', String(active));
  }
  $('source-description').textContent = mode === 'upload'
    ? 'Sube un audio o grábalo ahora para comenzar el análisis.'
    : 'Graba tu voz con el micrófono de tu equipo.';
  if (mode === 'record') {
    $('record-prompt').textContent = 'Presiona para grabar';
    $('record-hint').textContent = 'Se usará el micrófono de tu equipo · el navegador pedirá permiso.';
    $('start-record').setAttribute('aria-label', 'Empezar a grabar');
  }
  error('');
}
$('upload-tab').addEventListener('click', () => chooseSource('upload'));
$('record-tab').addEventListener('click', () => chooseSource('record'));

// MediaRecorder captura el micrófono; al finalizar se convierte a WAV.
const wave = $('record-wave');
for (let i = 0; i < 46; i++) {
  const bar = document.createElement('i');
  bar.style.setProperty('--bar-height', `${12 + Math.round(43 * (0.35 + 0.65 * Math.abs(Math.sin(i * 0.57) * Math.cos(i * 0.19))))}px`);
  bar.style.setProperty('--delay', `${(i % 9) * -0.09}s`);
  wave.append(bar);
}
function showRecordingTime() {
  if (!recording) return;
  const ms = recording.elapsed + (recording.recorder.state === 'recording' ? performance.now() - recording.resumedAt : 0);
  const seconds = Math.floor(ms / 1000);
  $('record-timer').textContent = `${String(Math.floor(seconds / 60)).padStart(2, '0')}:${String(seconds % 60).padStart(2, '0')}.${Math.floor(ms % 1000 / 100)}`;
}
function recordingUI(state) {
  const active = state === 'recording' || state === 'paused' || state === 'finishing';
  $('record-idle').hidden = active;
  $('record-active').hidden = !active;
  $('record-panel').classList.toggle('is-paused', state === 'paused');
  $('record-status').classList.toggle('paused', state === 'paused');
  $('record-status').textContent = state === 'paused' ? 'Ⅱ EN PAUSA' : state === 'finishing' ? 'PREPARANDO AUDIO…' : '● GRABANDO';
  $('pause-record').textContent = state === 'paused' ? '♩ Reanudar' : 'Ⅱ Pausar';
  $('stop-record').textContent = state === 'paused' ? '■ Terminar' : '■ Detener';
  $('pause-record').disabled = state === 'finishing';
  $('stop-record').disabled = state === 'finishing';
  if (state === 'recording') $('source-description').textContent = 'Hablando… puedes pausar o detener cuando quieras.';
  if (state === 'paused') $('source-description').textContent = 'Grabación en pausa. Reanuda o termina para continuar.';
}
function recorderMime() {
  const candidates = ['audio/webm;codecs=opus', 'audio/mp4', 'audio/ogg;codecs=opus', 'audio/webm'];
  return candidates.find(type => MediaRecorder.isTypeSupported?.(type)) || '';
}
async function wavFile(blob) {
  const Context = window.AudioContext || window.webkitAudioContext;
  if (!Context) throw new Error('Este navegador no puede preparar la grabación. Prueba con otro navegador.');
  const context = new Context();
  try {
    const audio = await context.decodeAudioData(await blob.arrayBuffer());
    const bytes = 44 + audio.length * 2;
    if (bytes > Number(form.dataset.maxMb) * 1024 * 1024) {
      throw new Error(`La grabación supera el límite de ${form.dataset.maxMb} MB. Graba un tramo más corto.`);
    }
    const buffer = new ArrayBuffer(bytes), view = new DataView(buffer);
    const write = (offset, text) => { for (let i = 0; i < text.length; i++) view.setUint8(offset + i, text.charCodeAt(i)); };
    write(0, 'RIFF'); view.setUint32(4, bytes - 8, true); write(8, 'WAVE'); write(12, 'fmt ');
    view.setUint32(16, 16, true); view.setUint16(20, 1, true); view.setUint16(22, 1, true);
    view.setUint32(24, audio.sampleRate, true); view.setUint32(28, audio.sampleRate * 2, true);
    view.setUint16(32, 2, true); view.setUint16(34, 16, true); write(36, 'data'); view.setUint32(40, bytes - 44, true);
    const channels = Array.from({length: audio.numberOfChannels}, (_, i) => audio.getChannelData(i));
    for (let i = 0; i < audio.length; i++) {
      let value = 0;
      for (const channel of channels) value += channel[i];
      value = Math.max(-1, Math.min(1, value / channels.length));
      view.setInt16(44 + i * 2, value < 0 ? value * 32768 : value * 32767, true);
    }
    return new File([buffer], `grabacion-${Date.now()}.wav`, {type: 'audio/wav'});
  } finally {
    await context.close();
  }
}
async function startRecording() {
  if (busy || recording || requestingMicrophone || processingRecording) return;
  if (!navigator.mediaDevices?.getUserMedia || !window.MediaRecorder) {
    error('Tu navegador no permite grabar desde esta página. Usa http://127.0.0.1:8000/ o sube un archivo.');
    return;
  }
  requestingMicrophone = true; setControlsBusy(false); error('');
  let stream;
  try {
    stream = await navigator.mediaDevices.getUserMedia({audio: true, video: false});
    const mimeType = recorderMime();
    const recorder = mimeType ? new MediaRecorder(stream, {mimeType}) : new MediaRecorder(stream);
    const chunks = [];
    recorder.addEventListener('dataavailable', event => { if (event.data.size) chunks.push(event.data); });
    recorder.addEventListener('stop', async () => {
      clearInterval(recording?.timer);
      recording = null; processingRecording = true;
      stream.getTracks().forEach(track => track.stop());
      setControlsBusy(false); recordingUI('finishing');
      try {
        if (!chunks.length) throw new Error('La grabación quedó vacía. Inténtalo de nuevo.');
        const file = await wavFile(new Blob(chunks, {type: recorder.mimeType}));
        selectFile(file);
        $('record-prompt').textContent = 'Grabación lista';
        $('record-hint').textContent = 'Escúchala abajo o pulsa Diarizar audio. Puedes grabar otra vez.';
        $('start-record').setAttribute('aria-label', 'Grabar otra vez');
        $('source-description').textContent = 'Tu grabación está lista para analizar.';
      } catch (err) {
        error(err.message || 'No se pudo preparar la grabación. Inténtalo de nuevo.');
        $('source-description').textContent = 'Puedes intentar grabar otra vez.';
      } finally {
        processingRecording = false; recordingUI('idle'); setControlsBusy(false);
      }
    }, {once: true});
    recorder.start();
    resetSelection();
    recording = {recorder, stream, elapsed: 0, resumedAt: performance.now(), timer: null};
    recording.timer = setInterval(showRecordingTime, 100);
    showRecordingTime(); recordingUI('recording');
    stream.getAudioTracks()[0]?.addEventListener('ended', () => { if (recording?.recorder === recorder) stopRecording(); });
  } catch (err) {
    stream?.getTracks().forEach(track => track.stop());
    error(err.name === 'NotAllowedError' || err.name === 'PermissionDeniedError'
      ? 'Permite el acceso al micrófono en tu navegador para grabar, o sube un archivo.'
      : 'No se pudo iniciar la grabación. Revisa que el micrófono esté disponible.');
  } finally {
    requestingMicrophone = false; setControlsBusy(false);
  }
}
function pauseRecording() {
  if (!recording || recording.finishing) return;
  try {
    if (recording.recorder.state === 'recording') {
      recording.elapsed += performance.now() - recording.resumedAt;
      recording.recorder.pause(); recordingUI('paused');
    } else if (recording.recorder.state === 'paused') {
      recording.recorder.resume(); recording.resumedAt = performance.now(); recordingUI('recording');
    }
    showRecordingTime();
  } catch {
    error('No se pudo cambiar el estado de la grabación. Puedes detenerla e intentarlo otra vez.');
  }
}
function stopRecording() {
  if (!recording || recording.finishing) return;
  recording.finishing = true;
  if (recording.recorder.state === 'recording') recording.elapsed += performance.now() - recording.resumedAt;
  showRecordingTime(); recordingUI('finishing');
  try { recording.recorder.stop(); }
  catch { error('No se pudo detener la grabación. Recarga la página e inténtalo de nuevo.'); }
}
$('start-record').addEventListener('click', startRecording);
$('pause-record').addEventListener('click', pauseRecording);
$('stop-record').addEventListener('click', stopRecording);
