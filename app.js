/**
 * Face Inteligente — Versão Web Client-Side
 * Processamento 100% no navegador via MediaPipe FaceMesh & Web APIs.
 */

'use strict';

// Constantes de marcos anatômicos dos olhos (EAR)
const LEFT_EYE = [33, 160, 158, 133, 153, 144];
const RIGHT_EYE = [362, 385, 387, 263, 373, 380];

// Utilidades matemáticas
function clamp(val, min = 0, max = 1) {
  return Math.max(min, Math.min(max, val));
}

function euclideanDist(p1, p2) {
  return Math.hypot(p1.x - p2.x, p1.y - p2.y);
}

function calculateEAR(landmarks, indices) {
  const [p1, p2, p3, p4, p5, p6] = indices.map(idx => landmarks[idx]);
  if (!p1 || !p2 || !p3 || !p4 || !p5 || !p6) return null;
  const horizontal = 2.0 * euclideanDist(p1, p4);
  if (horizontal < 1e-6) return null;
  return (euclideanDist(p2, p6) + euclideanDist(p3, p5)) / horizontal;
}

// Classe de Detecção de Piscadas
class WebBlinkDetector {
  constructor(threshold = 0.21, minFrames = 2) {
    this.threshold = threshold;
    this.minFrames = minFrames;
    this.closedFrames = 0;
    this.total = 0;
    this.events = [];
    this.firstTimestamp = null;
  }

  reset() {
    this.closedFrames = 0;
    this.total = 0;
    this.events = [];
    this.firstTimestamp = null;
  }

  update(landmarks, timestampSec) {
    if (this.firstTimestamp === null) {
      this.firstTimestamp = timestampSec;
    }
    const left = calculateEAR(landmarks, LEFT_EYE);
    const right = calculateEAR(landmarks, RIGHT_EYE);
    if (left === null || right === null) return { blink: false, ear: null, rate: null };

    const ear = (left + right) / 2.0;
    let blink = false;
    if (ear < this.threshold) {
      this.closedFrames++;
    } else {
      if (this.closedFrames >= this.minFrames) {
        this.total++;
        this.events.push(timestampSec);
        blink = true;
      }
      this.closedFrames = 0;
    }

    // Janela de 60 segundos
    while (this.events.length > 0 && timestampSec - this.events[0] > 60.0) {
      this.events.shift();
    }

    const elapsed = Math.max(5.0, Math.min(60.0, timestampSec - this.firstTimestamp));
    const rate = this.events.length > 0 ? (this.events.length / elapsed) * 60.0 : 0.0;
    return { blink, ear, rate: Math.round(rate * 10) / 10 };
  }
}

// Analisador de Movimento Relativo
class WebMotionAnalyzer {
  constructor(smoothing = 12) {
    this.smoothing = smoothing;
    this.previous = null;
    this.values = [];
  }

  reset() {
    this.previous = null;
    this.values = [];
  }

  update(bbox) {
    if (!bbox) {
      this.previous = null;
      this.values = [];
      return null;
    }
    const { x, y, width, height } = bbox;
    const current = {
      cx: x + width / 2.0,
      cy: y + height / 2.0,
      scale: Math.max(width, height, 1)
    };

    if (!this.previous) {
      this.previous = current;
      return 0.0;
    }

    const displacement = Math.hypot(current.cx - this.previous.cx, current.cy - this.previous.cy) /
                         Math.max(this.previous.scale, current.scale, 1);
    this.previous = current;

    this.values.push(displacement);
    if (this.values.length > this.smoothing) this.values.shift();

    const avg = this.values.reduce((a, b) => a + b, 0) / this.values.length;
    return avg;
  }

  static stability(motion) {
    if (motion === null) return 0.0;
    return clamp(1.0 - motion * 12.0);
  }
}

// Estimador de Pulso rPPG em Javascript
class WebPulseEstimator {
  constructor(windowSeconds = 12.0) {
    this.windowSeconds = windowSeconds;
    this.times = [];
    this.greens = [];
  }

  reset() {
    this.times = [];
    this.greens = [];
  }

  add(timestampSec, greenMean) {
    if (greenMean === null || !isFinite(greenMean)) return { bpm: null, quality: 0.0 };

    this.times.push(timestampSec);
    this.greens.push(greenMean);

    while (this.times.length > 0 && timestampSec - this.times[0] > this.windowSeconds) {
      this.times.shift();
      this.greens.shift();
    }

    if (this.times.length < 80 || this.times[this.times.length - 1] - this.times[0] < 8.0) {
      return { bpm: null, quality: 0.0 };
    }

    const N = this.times.length;
    const duration = this.times[N - 1] - this.times[0];
    const fps = (N - 1) / Math.max(duration, 1e-6);
    if (fps < 10) return { bpm: null, quality: 0.0 };

    // Média e desvio padrão
    const mean = this.greens.reduce((a, b) => a + b, 0) / N;
    const variance = this.greens.reduce((a, b) => a + Math.pow(b - mean, 2), 0) / N;
    const std = Math.sqrt(variance);
    if (std < 0.05) return { bpm: null, quality: 0.0 };

    // Remoção de tendência linear e janela de Hanning
    const signal = new Float64Array(N);
    const slope = (this.greens[N - 1] - this.greens[0]) / Math.max(N - 1, 1);
    for (let i = 0; i < N; i++) {
      const detrended = (this.greens[i] - (this.greens[0] + slope * i));
      const hanning = 0.5 * (1 - Math.cos((2 * Math.PI * i) / (N - 1)));
      signal[i] = detrended * hanning;
    }

    // Discrete Fourier Transform (DFT) nas frequências cardíacas (0.75 Hz a 3.0 Hz => 45 a 180 BPM)
    const minFreq = 0.75;
    const maxFreq = 3.0;
    const freqStep = 0.02; // resolução de 1.2 BPM
    let maxPower = 0;
    let totalPower = 0;
    let bestFreq = 0;

    for (let f = minFreq; f <= maxFreq; f += freqStep) {
      let real = 0;
      let imag = 0;
      for (let i = 0; i < N; i++) {
        const angle = 2 * Math.PI * f * (this.times[i] - this.times[0]);
        real += signal[i] * Math.cos(angle);
        imag -= signal[i] * Math.sin(angle);
      }
      const power = real * real + imag * imag;
      totalPower += power;
      if (power > maxPower) {
        maxPower = power;
        bestFreq = f;
      }
    }

    const quality = totalPower > 1e-9 ? maxPower / totalPower : 0;
    const bpm = bestFreq * 60.0;

    if (quality < 0.35 || bpm < 45 || bpm > 180) {
      return { bpm: null, quality: Math.round(quality * 1000) / 1000 };
    }
    return { bpm: Math.round(bpm * 10) / 10, quality: Math.min(1.0, Math.round(quality * 1000) / 1000) };
  }
}

// Avaliação de Qualidade de Imagem e Sinal
function assessQuality(facePresent, brightness, blur, fps, stability) {
  const reasons = [];
  if (!facePresent) {
    return { score: 0.0, sufficient: false, reasons: ['rosto não encontrado'] };
  }

  const light = clamp(1.0 - Math.abs(brightness - 130.0) / 110.0);
  const sharpness = clamp(blur / 120.0);
  const cadence = clamp(fps / 20.0);
  const stable = clamp(stability);

  if (brightness < 45) reasons.push('ambiente escuro');
  else if (brightness > 225) reasons.push('luz excessiva');
  if (blur < 35) reasons.push('imagem desfocada');
  if (fps < 10) reasons.push('taxa de quadros baixa');
  if (stability < 0.45) reasons.push('movimento excessivo');

  const score = 0.25 * light + 0.25 * sharpness + 0.2 * cadence + 0.3 * stable;
  const hardFailure = brightness < 25 || brightness > 245 || blur < 15 || fps < 5;
  return {
    score: Math.round(clamp(score) * 100) / 100,
    sufficient: score >= 0.55 && !hardFailure,
    reasons
  };
}

// Calibrador de Linha de Base Individual
class WebCalibrator {
  constructor(durationSeconds = 60) {
    this.durationSeconds = durationSeconds;
    this.startedAt = null;
    this.samples = { blink_rate: [], head_motion: [], pulse_bpm: [] };
    this.baseline = {};
  }

  start(nowSec) {
    this.startedAt = nowSec;
    this.samples = { blink_rate: [], head_motion: [], pulse_bpm: [] };
    this.baseline = {};
  }

  get active() {
    return this.startedAt !== null && Object.keys(this.baseline).length === 0;
  }

  progress(nowSec) {
    if (this.startedAt === null) return 0;
    return Math.min(1.0, Math.max(0.0, (nowSec - this.startedAt) / this.durationSeconds));
  }

  add(metrics, quality) {
    if (!this.active || quality < 0.55) return;
    for (const [key, val] of Object.entries(metrics)) {
      if (val !== null && isFinite(val) && this.samples[key]) {
        this.samples[key].push(val);
      }
    }
  }

  finish() {
    const result = {};
    for (const [key, vals] of Object.entries(this.samples)) {
      if (vals.length >= 5) {
        const mean = vals.reduce((a, b) => a + b, 0) / vals.length;
        const variance = vals.reduce((a, b) => a + Math.pow(b - mean, 2), 0) / Math.max(vals.length - 1, 1);
        const std = Math.max(Math.sqrt(variance), 0.05);
        result[key] = { mean, std, count: vals.length };
      }
    }
    this.baseline = result;
    this.startedAt = null;
    return result;
  }
}

// Modelo Transparente de Ativação Ponderada
class WebActivationModel {
  constructor() {
    this.weights = { blink_rate: 0.25, head_motion: 0.35, pulse_bpm: 0.40 };
  }

  evaluate(metrics, baseline, quality) {
    if (quality < 0.55) {
      return { level: 'medição insuficiente', score: null, explanation: 'qualidade insuficiente' };
    }

    let availableWeight = 0;
    let sumContributions = 0;

    for (const [key, weight] of Object.entries(this.weights)) {
      const val = metrics[key];
      const ref = baseline[key];
      if (val === null || !ref) continue;

      const z = (val - ref.mean) / Math.max(ref.std, 0.05);
      const contribution = clamp(Math.max(0, z) / 3.0) * weight;
      sumContributions += contribution;
      availableWeight += weight;
    }

    if (availableWeight < 0.25) {
      return { level: 'medição insuficiente', score: null, explanation: 'linha de base incompleta' };
    }

    const score = clamp(sumContributions / availableWeight);
    let level = 'estável';
    if (score >= 0.62) level = 'elevada';
    else if (score >= 0.28) level = 'moderada';

    return { level, score: Math.round(score * 1000) / 1000, explanation: 'desvio relativo individual' };
  }
}

// Aplicação Principal
class FaceInteligenteWebApp {
  constructor() {
    this.videoElement = document.getElementById('videoElement');
    this.outputCanvas = document.getElementById('outputCanvas');
    this.canvasCtx = this.outputCanvas.getContext('2d', { willReadFrequently: true });
    this.chartCanvas = document.getElementById('realtimeChart');
    this.chartCtx = this.chartCanvas.getContext('2d');

    this.blinkDetector = new WebBlinkDetector();
    this.motionAnalyzer = new WebMotionAnalyzer();
    this.pulseEstimator = new WebPulseEstimator();
    this.calibrator = new WebCalibrator(60);
    this.activationModel = new WebActivationModel();

    this.stream = null;
    this.faceMesh = null;
    this.cameraUtils = null;
    this.isRunning = false;
    this.frameTimes = [];
    this.samples = [];
    this.sessionStart = null;
    this.lastFps = 0;

    this.initElements();
    this.initEventListeners();
    this.initChart();
    this.loadSessions();
  }

  initElements() {
    this.startCamBtn = document.getElementById('startCamBtn');
    this.stopCamBtn = document.getElementById('stopCamBtn');
    this.startCalibBtn = document.getElementById('startCalibBtn');
    this.durationInput = document.getElementById('durationInput');
    this.calibProgress = document.getElementById('calibProgress');
    this.calibProgressText = document.getElementById('calibProgressText');
    this.saveMetricsCheck = document.getElementById('saveMetricsCheck');
    this.videoPlaceholder = document.getElementById('videoPlaceholder');
    this.activationBadge = document.getElementById('activationBadge');
    this.statusDetailText = document.getElementById('statusDetailText');

    // Cards
    this.valFace = document.getElementById('valFace');
    this.valQuality = document.getElementById('valQuality');
    this.valLight = document.getElementById('valLight');
    this.valBlur = document.getElementById('valBlur');
    this.valFps = document.getElementById('valFps');
    this.valStability = document.getElementById('valStability');
    this.valBlink = document.getElementById('valBlink');
    this.valPulse = document.getElementById('valPulse');

    // Dialogs
    this.consentModal = document.getElementById('consentModal');
    this.consentCheckbox = document.getElementById('consentCheckbox');
    this.consentAcceptBtn = document.getElementById('consentAcceptBtn');
    this.consentCancelBtn = document.getElementById('consentCancelBtn');
    this.summaryModal = document.getElementById('summaryModal');
    this.summaryBody = document.getElementById('summaryBody');
    this.summaryCloseBtn = document.getElementById('summaryCloseBtn');

    // Tabs
    this.tabButtons = document.querySelectorAll('.tab-btn');
    this.tabPanes = document.querySelectorAll('.tab-pane');
  }

  initEventListeners() {
    // Tabs Navigation
    this.tabButtons.forEach(btn => {
      btn.addEventListener('click', () => {
        this.tabButtons.forEach(b => b.classList.remove('active'));
        this.tabPanes.forEach(p => p.classList.remove('active'));
        btn.classList.add('active');
        document.getElementById(btn.dataset.tab).classList.add('active');
      });
    });

    // Start / Stop
    this.startCamBtn.addEventListener('click', () => this.promptConsent());
    this.stopCamBtn.addEventListener('click', () => this.stopCamera());
    this.startCalibBtn.addEventListener('click', () => this.startCalibration());

    // Consent Modal
    this.consentCheckbox.addEventListener('change', () => {
      this.consentAcceptBtn.disabled = !this.consentCheckbox.checked;
    });
    this.consentCancelBtn.addEventListener('click', () => this.consentModal.close());
    this.consentAcceptBtn.addEventListener('click', () => {
      this.consentModal.close();
      this.startCamera();
    });

    this.summaryCloseBtn.addEventListener('click', () => this.summaryModal.close());

    // History Actions
    document.getElementById('exportCsvBtn').addEventListener('click', () => this.exportCsv());
    document.getElementById('clearHistoryBtn').addEventListener('click', () => this.clearHistory());

    // Keyboard Shortcut (Space bar)
    window.addEventListener('keydown', (e) => {
      if (e.code === 'Space' && e.target === document.body) {
        e.preventDefault();
        if (this.isRunning) this.stopCamera();
        else this.promptConsent();
      }
    });

    this.populateCameraDevices();
  }

  async populateCameraDevices() {
    try {
      if (!navigator.mediaDevices || !navigator.mediaDevices.enumerateDevices) return;
      const devices = await navigator.mediaDevices.enumerateDevices();
      const videoDevices = devices.filter(d => d.kind === 'videoinput');
      const select = document.getElementById('cameraSelect');
      if (videoDevices.length > 0) {
        select.innerHTML = '';
        videoDevices.forEach((d, idx) => {
          const opt = document.createElement('option');
          opt.value = d.deviceId;
          opt.textContent = d.label || `Câmera ${idx + 1}`;
          select.appendChild(opt);
        });
      }
    } catch (e) {
      console.warn('Erro ao listar câmeras:', e);
    }
  }

  promptConsent() {
    this.consentCheckbox.checked = false;
    this.consentAcceptBtn.disabled = true;
    this.consentModal.showModal();
  }

  async startCamera() {
    try {
      const select = document.getElementById('cameraSelect');
      const deviceId = select.value !== 'default' ? { exact: select.value } : undefined;

      const constraints = {
        video: {
          deviceId,
          width: { ideal: 640 },
          height: { ideal: 480 },
          facingMode: 'user'
        },
        audio: false
      };

      this.stream = await navigator.mediaDevices.getUserMedia(constraints);
      this.videoElement.srcObject = this.stream;
      await this.videoElement.play();

      this.isRunning = true;
      this.samples = [];
      this.sessionStart = performance.now();
      this.blinkDetector.reset();
      this.motionAnalyzer.reset();
      this.pulseEstimator.reset();

      this.startCamBtn.disabled = true;
      this.stopCamBtn.disabled = false;
      this.startCalibBtn.disabled = false;
      this.videoPlaceholder.style.display = 'none';
      this.statusDetailText.textContent = 'Câmera ativa. Posicione seu rosto e inicie a calibração.';

      await this.initFaceMesh();
    } catch (err) {
      alert(`Falha ao acessar a câmera: ${err.message}. Verifique as permissões de vídeo.`);
    }
  }

  async initFaceMesh() {
    if (window.FaceMesh) {
      this.faceMesh = new window.FaceMesh({
        locateFile: (file) => `https://cdn.jsdelivr.net/npm/@mediapipe/face_mesh/${file}`
      });

      this.faceMesh.setOptions({
        maxNumFaces: 1,
        refineLandmarks: true,
        minDetectionConfidence: 0.5,
        minTrackingConfidence: 0.5
      });

      this.faceMesh.onResults((results) => this.onFaceMeshResults(results));

      this.processVideoLoop();
    } else {
      document.getElementById('backendBadge').textContent = 'Modo Reduzido (Canvas)';
      this.processVideoLoopFallback();
    }
  }

  async processVideoLoop() {
    if (!this.isRunning) return;
    try {
      if (this.videoElement.readyState >= 2) {
        await this.faceMesh.send({ image: this.videoElement });
      }
    } catch (e) {
      console.warn('Erro FaceMesh loop:', e);
    }
    if (this.isRunning) {
      requestAnimationFrame(() => this.processVideoLoop());
    }
  }

  onFaceMeshResults(results) {
    if (!this.isRunning) return;

    const now = performance.now();
    const nowSec = now / 1000.0;
    this.frameTimes.push(now);
    if (this.frameTimes.length > 30) this.frameTimes.shift();

    let fps = 0;
    if (this.frameTimes.length > 1) {
      fps = (this.frameTimes.length - 1) / ((this.frameTimes[this.frameTimes.length - 1] - this.frameTimes[0]) / 1000.0);
    }
    this.lastFps = fps;

    const width = this.outputCanvas.width;
    const height = this.outputCanvas.height;

    // Desenha o vídeo no canvas
    this.canvasCtx.save();
    this.canvasCtx.clearRect(0, 0, width, height);
    this.canvasCtx.drawImage(this.videoElement, 0, 0, width, height);

    let facePresent = false;
    let bbox = null;
    let landmarks = null;
    let foreheadRoi = null;

    if (results.multiFaceLandmarks && results.multiFaceLandmarks.length > 0) {
      facePresent = true;
      const raw = results.multiFaceLandmarks[0];
      landmarks = raw.map(p => ({ x: p.x * width, y: p.y * height }));

      // Calcula Bounding Box
      const xs = landmarks.map(p => p.x);
      const ys = landmarks.map(p => p.y);
      const minX = Math.min(...xs);
      const maxX = Math.max(...xs);
      const minY = Math.min(...ys);
      const maxY = Math.max(...ys);
      bbox = { x: minX, y: minY, width: maxX - minX, height: maxY - minY };

      // Extrai ROI da testa (pontos anatômicos 10, 9, 109, 338)
      if (landmarks[10] && landmarks[9] && landmarks[109] && landmarks[338]) {
        const xMin = Math.min(landmarks[109].x, landmarks[67] ? landmarks[67].x : landmarks[109].x);
        const xMax = Math.max(landmarks[338].x, landmarks[297] ? landmarks[297].x : landmarks[338].x);
        const yTop = landmarks[10].y;
        const yBottom = landmarks[9].y;
        const dx = (xMax - xMin) * 0.18;
        const dy = (yBottom - yTop) * 0.15;
        foreheadRoi = {
          x1: Math.max(0, Math.floor(xMin + dx)),
          x2: Math.min(width, Math.floor(xMax - dx)),
          y1: Math.max(0, Math.floor(yTop + dy)),
          y2: Math.min(height, Math.floor(yBottom - dy))
        };
      }
    }

    // Métricas de imagem
    const { brightness, blur } = this.calculateImageStats(width, height);
    const headMotion = this.motionAnalyzer.update(bbox);
    const stability = WebMotionAnalyzer.stability(headMotion);
    const { blink, ear, rate: blinkRate } = landmarks
      ? this.blinkDetector.update(landmarks, nowSec)
      : { blink: false, ear: null, rate: null };

    // Canal verde da testa para rPPG
    const greenMean = foreheadRoi ? this.getForeheadGreen(foreheadRoi) : null;
    const { bpm: pulseBpm, quality: pulseQuality } = this.pulseEstimator.add(
      nowSec,
      stability > 0.65 ? greenMean : null
    );

    const qualityResult = assessQuality(facePresent, brightness, blur, fps, stability);

    const rawMetrics = { blink_rate: blinkRate, head_motion: headMotion, pulse_bpm: pulseBpm };

    // Calibração
    if (this.calibrator.active) {
      this.calibrator.add(rawMetrics, qualityResult.score);
      const progress = this.calibrator.progress(nowSec);
      this.calibProgress.style.width = `${Math.round(progress * 100)}%`;
      this.calibProgressText.textContent = `${Math.round(progress * 100)}%`;

      if (progress >= 1.0) {
        const baseline = this.calibrator.finish();
        this.startCalibBtn.disabled = false;
        if (Object.keys(baseline).length > 0) {
          this.statusDetailText.textContent = 'Linha de base concluída! Monitorando ativação individual.';
        } else {
          this.statusDetailText.textContent = 'Calibração insuficiente. Tente manter o rosto imóvel e com boa luz.';
        }
      }
    }

    const activation = this.activationModel.evaluate(rawMetrics, this.calibrator.baseline, qualityResult.score);

    // Desenha overlays no canvas
    this.drawOverlays(facePresent, bbox, qualityResult.sufficient, foreheadRoi);
    this.canvasCtx.restore();

    // Atualiza interface
    const frameMetrics = {
      timestamp: (now - this.sessionStart) / 1000.0,
      facePresent,
      brightness,
      blur,
      fps,
      stability,
      blinkRate,
      pulseBpm,
      pulseQuality,
      quality: qualityResult.score,
      activationScore: activation.score,
      activationLevel: activation.level,
      notes: qualityResult.reasons
    };

    this.samples.push(frameMetrics);
    this.updateUI(frameMetrics);
    this.updateChart();
  }

  calculateImageStats(w, h) {
    try {
      // Amostra reduzida para velocidade
      const imgData = this.canvasCtx.getImageData(0, 0, w, h);
      const data = imgData.data;
      let sumLum = 0;
      let varianceSum = 0;
      const step = 8;
      let count = 0;

      for (let i = 0; i < data.length; i += 4 * step) {
        const lum = 0.299 * data[i] + 0.587 * data[i + 1] + 0.114 * data[i + 2];
        sumLum += lum;
        count++;
      }
      const meanLum = sumLum / Math.max(count, 1);

      // Variância como proxy de nitidez/desfoque
      for (let i = 0; i < data.length; i += 4 * step) {
        const lum = 0.299 * data[i] + 0.587 * data[i + 1] + 0.114 * data[i + 2];
        varianceSum += Math.pow(lum - meanLum, 2);
      }
      const blur = Math.sqrt(varianceSum / Math.max(count, 1)) * 2.0;

      return { brightness: meanLum, blur };
    } catch (e) {
      return { brightness: 120, blur: 50 };
    }
  }

  getForeheadGreen(roi) {
    try {
      const rw = roi.x2 - roi.x1;
      const rh = roi.y2 - roi.y1;
      if (rw <= 0 || rh <= 0) return null;
      const imgData = this.canvasCtx.getImageData(roi.x1, roi.y1, rw, rh);
      const data = imgData.data;
      let sumGreen = 0;
      let count = 0;
      for (let i = 1; i < data.length; i += 4) {
        sumGreen += data[i];
        count++;
      }
      return count > 0 ? sumGreen / count : null;
    } catch (e) {
      return null;
    }
  }

  drawOverlays(facePresent, bbox, sufficient, foreheadRoi) {
    if (facePresent && bbox) {
      this.canvasCtx.strokeStyle = sufficient ? '#44d19d' : '#f6c85f';
      this.canvasCtx.lineWidth = 2;
      this.canvasCtx.strokeRect(bbox.x, bbox.y, bbox.width, bbox.height);

      this.canvasCtx.fillStyle = sufficient ? '#44d19d' : '#f6c85f';
      this.canvasCtx.font = '13px Inter, sans-serif';
      this.canvasCtx.fillText(
        sufficient ? 'sinal adequado' : 'ajuste o sinal',
        bbox.x,
        Math.max(20, bbox.y - 8)
      );

      if (foreheadRoi) {
        this.canvasCtx.strokeStyle = '#58a6ff';
        this.canvasCtx.lineWidth = 1.5;
        this.canvasCtx.strokeRect(
          foreheadRoi.x1,
          foreheadRoi.y1,
          foreheadRoi.x2 - foreheadRoi.x1,
          foreheadRoi.y2 - foreheadRoi.y1
        );
        this.canvasCtx.fillStyle = '#58a6ff';
        this.canvasCtx.font = '11px Inter, sans-serif';
        this.canvasCtx.fillText('rPPG', foreheadRoi.x1, Math.max(14, foreheadRoi.y1 - 4));
      }
    } else {
      this.canvasCtx.fillStyle = '#f6c85f';
      this.canvasCtx.font = '16px Inter, sans-serif';
      this.canvasCtx.fillText('Posicione o rosto no centro', 24, 40);
    }
  }

  updateUI(m) {
    this.valFace.textContent = m.facePresent ? 'presente' : 'ausente';
    this.valFace.className = `card-val ${m.facePresent ? 'val-good' : 'val-bad'}`;

    const goodQuality = m.quality >= 0.55;
    this.valQuality.textContent = `${Math.round(m.quality * 100)}%`;
    this.valQuality.className = `card-val ${goodQuality ? 'val-good' : 'val-warn'}`;

    const goodLight = m.brightness >= 45 && m.brightness <= 225;
    this.valLight.textContent = Math.round(m.brightness);
    this.valLight.className = `card-val ${goodLight ? 'val-good' : 'val-warn'}`;

    this.valBlur.textContent = Math.round(m.blur);
    this.valBlur.className = `card-val ${m.blur >= 35 ? 'val-good' : 'val-warn'}`;

    this.valFps.textContent = m.fps.toFixed(1);
    this.valFps.className = `card-val ${m.fps >= 15 ? 'val-good' : 'val-warn'}`;

    this.valStability.textContent = `${Math.round(m.stability * 100)}%`;
    this.valStability.className = `card-val ${m.stability >= 0.55 ? 'val-good' : 'val-warn'}`;

    this.valBlink.textContent = m.blinkRate !== null ? m.blinkRate.toFixed(0) : '—';

    if (m.pulseBpm !== null) {
      this.valPulse.textContent = `${m.pulseBpm.toFixed(0)} bpm (${Math.round(m.pulseQuality * 100)}%)`;
      this.valPulse.className = 'card-val val-good';
    } else {
      this.valPulse.textContent = 'oculto (ruído)';
      this.valPulse.className = 'card-val';
    }

    // Badge de Ativação
    this.activationBadge.textContent = m.activationLevel;
    this.activationBadge.className = 'activation-badge';
    if (m.activationLevel === 'estável') this.activationBadge.classList.add('status-stable');
    else if (m.activationLevel === 'moderada') this.activationBadge.classList.add('status-moderate');
    else if (m.activationLevel === 'elevada') this.activationBadge.classList.add('status-elevated');
    else this.activationBadge.classList.add('status-insufficient');

    if (m.notes && m.notes.length > 0) {
      this.statusDetailText.textContent = `Atenção: ${m.notes.join(', ')}.`;
    }
  }

  initChart() {
    this.chartCanvas.width = this.chartCanvas.parentElement.clientWidth || 640;
  }

  updateChart() {
    const ctx = this.chartCtx;
    const w = this.chartCanvas.width;
    const h = this.chartCanvas.height;
    ctx.clearRect(0, 0, w, h);

    // Linhas de grade
    ctx.strokeStyle = '#21262d';
    ctx.lineWidth = 1;
    ctx.beginPath();
    ctx.moveTo(0, h * 0.28); ctx.lineTo(w, h * 0.28);
    ctx.moveTo(0, h * 0.62); ctx.lineTo(w, h * 0.62);
    ctx.stroke();

    const recent = this.samples.slice(-200);
    if (recent.length < 2) return;

    const stepX = w / (recent.length - 1);

    // Curva de Qualidade (#58a6ff)
    ctx.strokeStyle = '#58a6ff';
    ctx.lineWidth = 2;
    ctx.beginPath();
    recent.forEach((pt, i) => {
      const x = i * stepX;
      const y = h - pt.quality * h;
      if (i === 0) ctx.moveTo(x, y);
      else ctx.lineTo(x, y);
    });
    ctx.stroke();

    // Curva de Ativação (#f0883e)
    ctx.strokeStyle = '#f0883e';
    ctx.lineWidth = 2.5;
    ctx.beginPath();
    recent.forEach((pt, i) => {
      const score = pt.activationScore !== null ? pt.activationScore : 0;
      const x = i * stepX;
      const y = h - score * h;
      if (i === 0) ctx.moveTo(x, y);
      else ctx.lineTo(x, y);
    });
    ctx.stroke();
  }

  startCalibration() {
    const duration = parseFloat(this.durationInput.value) || 60;
    this.calibrator.durationSeconds = duration;
    this.calibrator.start(performance.now() / 1000.0);
    this.startCalibBtn.disabled = true;
    this.calibProgress.style.width = '0%';
    this.calibProgressText.textContent = '0%';
    this.statusDetailText.textContent = 'Calibrando: permaneça confortável e em repouso olhando para a tela.';
  }

  stopCamera() {
    if (!this.isRunning) return;
    this.isRunning = false;

    if (this.stream) {
      this.stream.getTracks().forEach(track => track.stop());
      this.stream = null;
    }

    const durationSec = Math.max(0, (performance.now() - this.sessionStart) / 1000.0);
    const count = this.samples.length;
    const avgQuality = count > 0 ? this.samples.reduce((a, b) => a + b.quality, 0) / count : 0;

    // Contagem de estados
    const stateCounts = {};
    this.samples.forEach(s => {
      stateCounts[s.activationLevel] = (stateCounts[s.activationLevel] || 0) + 1;
    });

    const summary = {
      id: Date.now(),
      startedAt: new Date(Date.now() - durationSec * 1000).toLocaleString('pt-BR'),
      durationSeconds: Math.round(durationSec),
      sampleCount: count,
      meanQuality: Math.round(avgQuality * 100) / 100,
      blinkCount: this.blinkDetector.total,
      levelCounts: stateCounts
    };

    if (this.saveMetricsCheck.checked && count > 0) {
      this.saveSession(summary, this.samples);
    }

    // Reset UI
    this.startCamBtn.disabled = false;
    this.stopCamBtn.disabled = true;
    this.startCalibBtn.disabled = true;
    this.videoPlaceholder.style.display = 'flex';
    this.canvasCtx.clearRect(0, 0, this.outputCanvas.width, this.outputCanvas.height);
    this.activationBadge.className = 'activation-badge status-insufficient';
    this.activationBadge.textContent = 'medição insuficiente';

    this.showSummaryModal(summary);
  }

  showSummaryModal(s) {
    const savedMsg = this.saveMetricsCheck.checked
      ? '✓ Métricas numéricas salvas no navegador.'
      : '✕ Nenhuma métrica foi salva (opção desmarcada).';

    this.summaryBody.innerHTML = `
      <p><strong>Duração:</strong> ${s.durationSeconds} segundos</p>
      <p><strong>Amostras de quadros:</strong> ${s.sampleCount}</p>
      <p><strong>Qualidade média do sinal:</strong> ${Math.round(s.meanQuality * 100)}%</p>
      <p><strong>Piscadas registradas:</strong> ${s.blinkCount}</p>
      <p><strong>Estados:</strong> ${JSON.stringify(s.levelCounts)}</p>
      <p style="margin-top: 10px; color: #44d19d;">${savedMsg}</p>
      <p style="font-size: 0.8rem; color: #8b949e; margin-top: 4px;">Nenhuma imagem ou vídeo foi gravado ou transmitido.</p>
    `;
    this.summaryModal.showModal();
  }

  saveSession(summary, samples) {
    try {
      const stored = JSON.parse(localStorage.getItem('face_inteligente_sessions') || '[]');
      stored.unshift({ ...summary, samples });
      localStorage.setItem('face_inteligente_sessions', JSON.stringify(stored));
      this.loadSessions();
    } catch (e) {
      console.error('Falha ao salvar sessão:', e);
    }
  }

  loadSessions() {
    const tbody = document.getElementById('sessionsBody');
    try {
      const stored = JSON.parse(localStorage.getItem('face_inteligente_sessions') || '[]');
      if (stored.length === 0) {
        tbody.innerHTML = '<tr><td colspan="8" class="empty-table">Nenhuma sessão salva ainda.</td></tr>';
        return;
      }
      tbody.innerHTML = '';
      stored.forEach((item, idx) => {
        const tr = document.createElement('tr');
        tr.innerHTML = `
          <td>${item.id}</td>
          <td>${item.startedAt}</td>
          <td>${item.durationSeconds} s</td>
          <td>${item.sampleCount}</td>
          <td>${Math.round(item.meanQuality * 100)}%</td>
          <td>${item.blinkCount}</td>
          <td>${JSON.stringify(item.levelCounts)}</td>
          <td><button class="action-btn-delete" data-id="${item.id}">Excluir</button></td>
        `;
        tbody.appendChild(tr);
      });

      tbody.querySelectorAll('.action-btn-delete').forEach(btn => {
        btn.addEventListener('click', (e) => {
          const id = Number(e.target.dataset.id);
          this.deleteSession(id);
        });
      });
    } catch (e) {
      tbody.innerHTML = '<tr><td colspan="8" class="empty-table">Erro ao ler sessões locais.</td></tr>';
    }
  }

  deleteSession(id) {
    if (!confirm('Deseja excluir permanentemente esta sessão local?')) return;
    const stored = JSON.parse(localStorage.getItem('face_inteligente_sessions') || '[]');
    const filtered = stored.filter(s => s.id !== id);
    localStorage.setItem('face_inteligente_sessions', JSON.stringify(filtered));
    this.loadSessions();
  }

  clearHistory() {
    if (!confirm('Excluir todas as sessões armazenadas neste navegador?')) return;
    localStorage.removeItem('face_inteligente_sessions');
    this.loadSessions();
  }

  exportCsv() {
    const stored = JSON.parse(localStorage.getItem('face_inteligente_sessions') || '[]');
    if (stored.length === 0) {
      alert('Nenhuma sessão salva para exportar.');
      return;
    }

    const headers = ['sessionId', 'timestamp', 'facePresent', 'brightness', 'blur', 'fps', 'stability', 'blinkRate', 'pulseBpm', 'pulseQuality', 'quality', 'activationScore', 'activationLevel', 'notes'];
    let csvContent = '\uFEFF' + headers.join(',') + '\n';

    stored.forEach(session => {
      (session.samples || []).forEach(row => {
        const line = [
          session.id,
          row.timestamp.toFixed(2),
          row.facePresent,
          row.brightness.toFixed(1),
          row.blur.toFixed(1),
          row.fps.toFixed(1),
          row.stability.toFixed(2),
          row.blinkRate !== null ? row.blinkRate.toFixed(1) : '',
          row.pulseBpm !== null ? row.pulseBpm.toFixed(1) : '',
          row.pulseQuality.toFixed(2),
          row.quality.toFixed(2),
          row.activationScore !== null ? row.activationScore.toFixed(3) : '',
          row.activationLevel,
          `"${(row.notes || []).join('; ')}"`
        ].join(',');
        csvContent += line + '\n';
      });
    });

    const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.setAttribute('href', url);
    link.setAttribute('download', `face-inteligente-sessoes-${Date.now()}.csv`);
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  }
}

// Inicializa quando a página carrega
window.addEventListener('DOMContentLoaded', () => {
  window.faceApp = new FaceInteligenteWebApp();
});
