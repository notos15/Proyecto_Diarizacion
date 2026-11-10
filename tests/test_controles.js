'use strict';
const assert = require('node:assert/strict');
const {test} = require('node:test');
const {readFileSync} = require('node:fs');
const vm = require('node:vm');
const {File} = require('node:buffer');
const {performance} = require('node:perf_hooks');

function node(id) {
  const classes = new Set();
  return {
    id, hidden: false, disabled: false, value: '', textContent: '', required: false,
    dataset: {}, children: [], attributes: {},
    style: {setProperty() {}},
    classList: {toggle(name, on) { if (on) classes.add(name); else classes.delete(name); }, contains(name) { return classes.has(name); }},
    addEventListener(type, listener) { this[`on_${type}`] = listener; },
    setAttribute(name, value) { this.attributes[name] = value; },
    append(child) { this.children.push(child); },
    click() { this.on_click?.(); },
    focus() { this.focused = true; },
  };
}

class FakeRecorder {
  static isTypeSupported(type) { return type === 'audio/webm;codecs=opus'; }
  constructor(_stream, options) { this.state = 'inactive'; this.mimeType = options?.mimeType || 'audio/webm'; this.listeners = {}; }
  addEventListener(type, listener) { this.listeners[type] = listener; }
  start() { this.state = 'recording'; }
  pause() { this.state = 'paused'; }
  resume() { this.state = 'recording'; }
  stop() {
    this.state = 'inactive';
    this.listeners.dataavailable({data: new Blob(['captura'], {type: this.mimeType})});
    this.stopped = this.listeners.stop();
  }
}

class FakeAudioContext {
  async decodeAudioData() {
    return {sampleRate: 16000, length: 2, numberOfChannels: 2,
      getChannelData(channel) { return channel === 0 ? Float32Array.of(.5, -.5) : Float32Array.of(.5, -.5); }};
  }
  async close() {}
}

test('grabar, pausar, reanudar, terminar y preparar un WAV para el análisis', async () => {
  const ids = ['upload-tab', 'record-tab', 'start-record', 'pause-record', 'stop-record', 'dropzone',
    'record-panel', 'record-idle', 'record-active', 'record-status', 'record-timer', 'record-wave',
    'record-prompt', 'record-hint', 'source-description'];
  const nodes = Object.fromEntries(ids.map(id => [id, node(id)]));
  const choices = ['auto', '1', '2', '3', '4', '5', '6', 'other'].map(value => {
    const choice = node(value); choice.dataset.speakers = value; return choice;
  });
  const speakerInput = node('num-speakers');
  const track = {stopped: false, addEventListener() {}, stop() { this.stopped = true; }};
  const stream = {getTracks: () => [track], getAudioTracks: () => [track]};
  let selectedFile = null, lastError = '';
  const context = vm.createContext({
    document: {querySelectorAll: () => choices, createElement: () => node('bar')},
    $: id => nodes[id], speakerInput, form: {dataset: {maxMb: '200'}}, busy: false,
    error: message => { lastError = message; },
    resetSelection: () => { selectedFile = null; },
    selectFile: file => { selectedFile = file; },
    navigator: {mediaDevices: {getUserMedia: async () => stream}},
    window: {MediaRecorder: FakeRecorder, AudioContext: FakeAudioContext},
    MediaRecorder: FakeRecorder, File, Blob, ArrayBuffer, DataView, Float32Array,
    performance, Date, setInterval, clearInterval,
  });
  vm.runInContext(readFileSync('web/static/controles.js', 'utf8'), context);
  assert.equal(vm.runInContext('selectedSpeakerCount()', context), '');
  choices[3].click();
  assert.equal(vm.runInContext('selectedSpeakerCount()', context), '3');
  choices[7].click(); speakerInput.value = '8';
  assert.equal(vm.runInContext('selectedSpeakerCount()', context), '8');
  assert.equal(speakerInput.hidden, false);
  choices[0].click();
  assert.equal(vm.runInContext('selectedSpeakerCount()', context), '');
  nodes['record-tab'].click();
  assert.equal(nodes['record-panel'].hidden, false);
  assert.equal(nodes.dropzone.hidden, true);
  await context.startRecording();
  assert.equal(nodes['record-idle'].hidden, true);
  assert.equal(nodes['record-tab'].disabled, true);
  nodes['pause-record'].click();
  assert.match(nodes['pause-record'].textContent, /Reanudar/);
  nodes['pause-record'].click();
  assert.match(nodes['pause-record'].textContent, /Pausar/);
  nodes['stop-record'].click();
  await new Promise(resolve => setImmediate(resolve));
  assert.equal(lastError, '');
  assert.equal(track.stopped, true);
  assert.equal(nodes['record-idle'].hidden, false);
  assert.equal(nodes['record-tab'].disabled, false);
  assert.match(selectedFile.name, /^grabacion-\d+\.wav$/);
  const wav = Buffer.from(await selectedFile.arrayBuffer());
  assert.equal(wav.toString('ascii', 0, 4), 'RIFF');
  assert.equal(wav.toString('ascii', 8, 12), 'WAVE');
  assert.equal(wav.readUInt32LE(24), 16000);
  assert.equal(wav.readInt16LE(44), 16383);
  nodes['upload-tab'].click();
  assert.equal(nodes.dropzone.hidden, false);
  assert.equal(nodes['record-panel'].hidden, true);
});
