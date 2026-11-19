import * as THREE from 'three';
import { OrbitControls } from 'three/examples/jsm/controls/OrbitControls.js';
import { GLTFLoader } from 'three/examples/jsm/loaders/GLTFLoader.js';
import { DRACOLoader } from 'three/examples/jsm/loaders/DRACOLoader.js';
import { CSS3DRenderer, CSS3DObject } from 'three/examples/jsm/renderers/CSS3DRenderer.js';
import { VRButton } from 'three/examples/jsm/webxr/VRButton.js';

// =============================================================================
// STATE & CONFIGURATION
// =============================================================================
const state = {
  movieTitle: "Interstellar • IMAX 70mm Special Presentation",
  youtubeUrl: "https://www.youtube.com/watch?v=zSWdZVtXT7E",
  youtubeVideoId: "zSWdZVtXT7E",
  currentVideoSource: { type: 'youtube', id: 'zSWdZVtXT7E' },
  currentSeatId: "D-008",
  lightingMode: "cinema", // 'cinema' | 'house' | 'blackout'
  inTheatre: false,
  isOrbitMode: false,

  // Feature 1: Dynamic Screen Ambilight
  ambilightEnabled: true,

  // Feature 2: Multiplayer Watch Party
  watchParty: {
    active: false,
    roomId: null,
    channel: null,
    userId: 'user_' + Math.random().toString(36).substring(2, 8),
    userName: 'Viewer ' + Math.floor(100 + Math.random() * 900),
    remoteMembers: new Map(), // userId -> { seatId, name, color }
  },

  // Feature 3: Spatial 3D Audio
  spatialAudioEnabled: true,

  // Feature 6: Concessions Snack Pack
  snackPack: 'butter', // 'butter' | 'caramel' | 'vip'
  popcornBites: 0,
  sodaSips: 0,
  isMuted: false,
  pendingYouTubeLoad: null,
  waitingForYouTubeClipboard: false,
};

let scene, cssScene, camera, cameraRig, renderer, cssRenderer, controls;
let screenMesh = null;
let cssScreenObj = null;
let iframeElement = null;
let html5VideoElement = null;
let ytPlayer = null;
let ytPlayerReady = false;
let isVideoPlaying = true;
let auditoriumModel = null;
let layoutMetadata = null;
const seatMeshMap = new Map(); // seat_id -> THREE.Object3D
const allLights = [];

// Screen Ambilight Lights
let screenBounceLight = null;
let screenAmbilightLeft = null;
let screenAmbilightRight = null;
let ambilightCanvas = null;
let ambilightCtx = null;
let ambilightSampleTimer = 0;
const currentAmbilightColor = new THREE.Color(0x7ea8f8);
const targetAmbilightColor = new THREE.Color(0x7ea8f8);

// Web Audio API & Spatial Audio Nodes
let audioCtx = null;
let screenPannerNode = null;
let sweetSpotFilterNode = null;
let mediaSourceConnected = false;

// 3D Interactive Concessions
let concessionsGroup = null;
let popcornTubMesh = null;
let sodaCupMesh = null;
let popcornKernelsGroup = null;

// 3D Floating Reaction Sprites
const activeReactions = [];

// Camera transition interpolation state
const camTarget = {
  pos: new THREE.Vector3(0, 2.67, -7.6),
  lookAt: new THREE.Vector3(0, 3.95, 2.3),
  active: false,
  duration: 1.8,
  elapsed: 0,
  startPos: new THREE.Vector3(),
  startLookAt: new THREE.Vector3(),
};

// Raycasting for interactive seat and concession picking
const raycaster = new THREE.Raycaster();
const mouse = new THREE.Vector2();
let hoveredSeat = null;
let hoveredConcession = null;
const originalMaterialMap = new Map();

// Highlighting material for hovered/selected seat
const highlightMaterial = new THREE.MeshStandardMaterial({
  color: 0xffcc33,
  roughness: 0.3,
  metalness: 0.2,
  emissive: 0xaa7700,
  emissiveIntensity: 0.4,
});

// =============================================================================
// VIDEO PARSING & TOAST UTILITIES
// =============================================================================
function showToast(message, duration = 4000) {
  const toast = document.getElementById('theatre-toast');
  if (!toast) return;
  toast.textContent = message;
  toast.classList.add('active');
  setTimeout(() => {
    toast.classList.remove('active');
  }, duration);
}

function extractYouTubeId(urlOrId) {
  if (!urlOrId) return "zSWdZVtXT7E";
  let str = urlOrId.trim();

  // If user pasted full iframe embed code snippet:
  const iframeSrcMatch = str.match(/src=["']([^"']+)["']/i);
  if (iframeSrcMatch) str = iframeSrcMatch[1];

  // Strip leading/trailing quotes, brackets, or html tags
  str = str.replace(/^["'<(\[]+|[>"')\]]+$/g, '').trim();

  // Direct 11-character video ID
  if (/^[a-zA-Z0-9_-]{11}$/.test(str)) {
    return str;
  }

  // Comprehensive YouTube URL matchers
  const patterns = [
    // youtu.be/<id>
    /youtu\.be\/([a-zA-Z0-9_-]{11})/i,
    // youtube.com/embed/<id> or youtube-nocookie.com/embed/<id>
    /youtube(?:-nocookie)?\.com\/embed\/([a-zA-Z0-9_-]{11})/i,
    // youtube.com/shorts/<id>
    /youtube\.com\/shorts\/([a-zA-Z0-9_-]{11})/i,
    // youtube.com/live/<id>
    /youtube\.com\/live\/([a-zA-Z0-9_-]{11})/i,
    // youtube.com/v/<id>
    /youtube\.com\/v\/([a-zA-Z0-9_-]{11})/i,
    // Parameter v=<id> anywhere in query string (?v=... or &v=...)
    /[?&]v=([a-zA-Z0-9_-]{11})/i,
  ];

  for (const regex of patterns) {
    const match = str.match(regex);
    if (match && match[1]) {
      return match[1];
    }
  }

  return null;
}

function extractStartTime(url) {
  if (!url) return 0;
  const match = url.match(/[?&](?:t|start)=([0-9hms]+)/i);
  if (!match) return 0;
  const val = match[1];
  if (/^\d+$/.test(val)) return parseInt(val, 10);
  let seconds = 0;
  const hours = val.match(/(\d+)h/i);
  const minutes = val.match(/(\d+)m/i);
  const secs = val.match(/(\d+)s/i);
  if (hours) seconds += parseInt(hours[1], 10) * 3600;
  if (minutes) seconds += parseInt(minutes[1], 10) * 60;
  if (secs) seconds += parseInt(secs[1], 10);
  return seconds;
}

function parseVideoSource(input) {
  if (!input) {
    return { type: 'youtube', id: 'zSWdZVtXT7E', start: 0 };
  }
  const trimmed = input.trim();

  // Local object URL or base64 data video
  if (trimmed.startsWith('blob:') || trimmed.startsWith('data:video/')) {
    return { type: 'direct', src: trimmed };
  }

  // Direct video file extension check
  const cleanUrl = trimmed.split('?')[0].toLowerCase();
  if (/\.(mp4|webm|ogv|ogg|mov|m4v|m3u8)$/i.test(cleanUrl)) {
    return { type: 'direct', src: trimmed };
  }

  // YouTube match first (handles full URLs, shorts, share links, embeds, and raw IDs)
  const ytId = extractYouTubeId(trimmed);
  if (ytId) {
    return { type: 'youtube', id: ytId, start: extractStartTime(trimmed) };
  }

  // Vimeo match
  const vimeoMatch = trimmed.match(/(?:vimeo\.com\/|player\.vimeo\.com\/video\/)(\d+)/);
  if (vimeoMatch && vimeoMatch[1]) {
    return { type: 'vimeo', id: vimeoMatch[1] };
  }

  if (/^https?:\/\//i.test(trimmed)) {
    return { type: 'direct', src: trimmed };
  }

  return { type: 'youtube', id: 'zSWdZVtXT7E', start: 0 };
}

function buildYouTubeEmbedUrl(videoId, autoplay = false, start = 0) {
  const autoplayParam = autoplay ? '1' : '0';
  const startParam = start ? `&start=${start}` : '';
  let originParam = '';
  // Avoid origin parameter on localhost or file:// to prevent YouTube iframe CORS Error 150
  if (
    window.location.protocol.startsWith('http') &&
    window.location.hostname !== 'localhost' &&
    window.location.hostname !== '127.0.0.1' &&
    window.location.origin &&
    window.location.origin !== 'null'
  ) {
    originParam = `&origin=${encodeURIComponent(window.location.origin)}`;
  }

  return `https://www.youtube.com/embed/${videoId}?autoplay=${autoplayParam}&enablejsapi=1&rel=0&modestbranding=1&controls=1&playsinline=1&fs=1&loop=1${startParam}${originParam}`;
}

// =============================================================================
// FEATURE 3: PROCEDURAL AUDIO SYNTHESIZERS & 3D SPATIAL AUDIO ENGINE
// =============================================================================
function initSpatialAudio() {
  if (audioCtx) {
    if (audioCtx.state === 'suspended') {
      audioCtx.resume();
    }
    return;
  }

  try {
    const AudioContextClass = window.AudioContext || window.webkitAudioContext;
    if (!AudioContextClass) return;

    audioCtx = new AudioContextClass();

    // 3D Positional Screen Panner Node
    screenPannerNode = audioCtx.createPanner();
    screenPannerNode.panningModel = 'HRTF';
    screenPannerNode.distanceModel = 'inverse';
    screenPannerNode.refDistance = 4.0;
    screenPannerNode.maxDistance = 25.0;
    screenPannerNode.rolloffFactor = 1.15;
    screenPannerNode.positionX.setValueAtTime(0, audioCtx.currentTime);
    screenPannerNode.positionY.setValueAtTime(3.95, audioCtx.currentTime);
    screenPannerNode.positionZ.setValueAtTime(2.3, audioCtx.currentTime);

    // Dolby Atmos Acoustic Sweet-Spot Filter (Presence EQ + Warm Room Resonance)
    sweetSpotFilterNode = audioCtx.createBiquadFilter();
    sweetSpotFilterNode.type = 'peaking';
    sweetSpotFilterNode.frequency.setValueAtTime(2800, audioCtx.currentTime);
    sweetSpotFilterNode.gain.setValueAtTime(3.2, audioCtx.currentTime);
    sweetSpotFilterNode.Q.setValueAtTime(1.1, audioCtx.currentTime);

    screenPannerNode.connect(sweetSpotFilterNode);
    sweetSpotFilterNode.connect(audioCtx.destination);

    console.log('Web Audio API 3D Spatial Audio & Dolby Atmos Simulation initialized');
  } catch (err) {
    console.warn('Could not initialize Web Audio API:', err);
  }
}

function updateSpatialAudio() {
  if (!audioCtx || !state.spatialAudioEnabled || !audioCtx.listener) return;

  const pos = camera.position;
  const now = audioCtx.currentTime;

  if (audioCtx.listener.positionX) {
    audioCtx.listener.positionX.setValueAtTime(pos.x, now);
    audioCtx.listener.positionY.setValueAtTime(pos.y, now);
    audioCtx.listener.positionZ.setValueAtTime(pos.z, now);

    const forward = new THREE.Vector3();
    camera.getWorldDirection(forward);
    audioCtx.listener.forwardX.setValueAtTime(forward.x, now);
    audioCtx.listener.forwardY.setValueAtTime(forward.y, now);
    audioCtx.listener.forwardZ.setValueAtTime(forward.z, now);

    const up = camera.up;
    audioCtx.listener.upX.setValueAtTime(up.x, now);
    audioCtx.listener.upY.setValueAtTime(up.y, now);
    audioCtx.listener.upZ.setValueAtTime(up.z, now);
  }
}

function connectVideoToSpatialAudio() {
  if (!audioCtx || !html5VideoElement || mediaSourceConnected) return;
  try {
    const source = audioCtx.createMediaElementSource(html5VideoElement);
    source.connect(screenPannerNode);
    mediaSourceConnected = true;
    console.log('Direct HTML5 video routed into 3D Spatial PannerNode');
  } catch (err) {
    console.warn('MediaElementSource audio route error:', err);
  }
}

// Procedural Popcorn Crunch Sound (synthesized burst of bandpass filtered noise)
function playPopcornCrunchSound() {
  initSpatialAudio();
  if (!audioCtx) return;
  if (audioCtx.state === 'suspended') audioCtx.resume();

  const now = audioCtx.currentTime;
  const bufferSize = Math.floor(audioCtx.sampleRate * 0.14);
  const buffer = audioCtx.createBuffer(1, bufferSize, audioCtx.sampleRate);
  const data = buffer.getChannelData(0);

  for (let i = 0; i < bufferSize; i++) {
    const decay = Math.exp(-i / (bufferSize * 0.22));
    data[i] = (Math.random() * 2 - 1) * decay;
  }

  const noise = audioCtx.createBufferSource();
  noise.buffer = buffer;

  const filter = audioCtx.createBiquadFilter();
  filter.type = 'bandpass';
  filter.frequency.setValueAtTime(1600 + (Math.random() - 0.5) * 500, now);
  filter.Q.setValueAtTime(3.5, now);

  const gain = audioCtx.createGain();
  gain.gain.setValueAtTime(0.5, now);
  gain.gain.exponentialRampToValueAtTime(0.01, now + 0.14);

  noise.connect(filter);
  filter.connect(gain);
  gain.connect(audioCtx.destination);
  noise.start(now);
}

// Procedural Soda Straw Sip Sound (frequency-modulated liquid slurp)
function playSodaSipSound() {
  initSpatialAudio();
  if (!audioCtx) return;
  if (audioCtx.state === 'suspended') audioCtx.resume();

  const now = audioCtx.currentTime;
  const osc = audioCtx.createOscillator();
  const gain = audioCtx.createGain();
  const filter = audioCtx.createBiquadFilter();

  osc.type = 'triangle';
  osc.frequency.setValueAtTime(320, now);
  osc.frequency.linearRampToValueAtTime(680, now + 0.08);
  osc.frequency.exponentialRampToValueAtTime(240, now + 0.22);

  filter.type = 'bandpass';
  filter.frequency.setValueAtTime(800, now);
  filter.Q.setValueAtTime(4.0, now);

  gain.gain.setValueAtTime(0.01, now);
  gain.gain.linearRampToValueAtTime(0.35, now + 0.04);
  gain.gain.exponentialRampToValueAtTime(0.01, now + 0.22);

  osc.connect(filter);
  filter.connect(gain);
  gain.connect(audioCtx.destination);

  osc.start(now);
  osc.stop(now + 0.22);
}

// Procedural Cinema Dolby/IMAX Intro Chime
function playCinemaIntroChime() {
  initSpatialAudio();
  if (!audioCtx) return;
  if (audioCtx.state === 'suspended') audioCtx.resume();

  const now = audioCtx.currentTime;

  // Deep Sub Bass Rumble (45Hz -> 80Hz)
  const subOsc = audioCtx.createOscillator();
  const subGain = audioCtx.createGain();
  subOsc.type = 'sine';
  subOsc.frequency.setValueAtTime(45, now);
  subOsc.frequency.exponentialRampToValueAtTime(85, now + 1.2);

  subGain.gain.setValueAtTime(0.01, now);
  subGain.gain.linearRampToValueAtTime(0.65, now + 0.3);
  subGain.gain.exponentialRampToValueAtTime(0.01, now + 2.0);

  subOsc.connect(subGain);
  subGain.connect(audioCtx.destination);
  subOsc.start(now);
  subOsc.stop(now + 2.0);

  // Shimmering High Chord Chime (A Major 9th harmonics)
  const freqs = [440, 554.37, 659.25, 830.61, 1108.73];
  freqs.forEach((freq, idx) => {
    const chordOsc = audioCtx.createOscillator();
    const chordGain = audioCtx.createGain();
    chordOsc.type = 'sine';
    chordOsc.frequency.setValueAtTime(freq, now + 0.1 * idx);

    chordGain.gain.setValueAtTime(0.01, now + 0.1 * idx);
    chordGain.gain.linearRampToValueAtTime(0.12, now + 0.3 + 0.1 * idx);
    chordGain.gain.exponentialRampToValueAtTime(0.001, now + 2.4);

    chordOsc.connect(chordGain);
    chordGain.connect(audioCtx.destination);
    chordOsc.start(now + 0.1 * idx);
    chordOsc.stop(now + 2.5);
  });
}

// Procedural Reaction Pop
function playReactionPop() {
  initSpatialAudio();
  if (!audioCtx) return;
  if (audioCtx.state === 'suspended') audioCtx.resume();

  const now = audioCtx.currentTime;
  const osc = audioCtx.createOscillator();
  const gain = audioCtx.createGain();

  osc.type = 'sine';
  osc.frequency.setValueAtTime(520, now);
  osc.frequency.exponentialRampToValueAtTime(980, now + 0.08);

  gain.gain.setValueAtTime(0.25, now);
  gain.gain.exponentialRampToValueAtTime(0.01, now + 0.09);

  osc.connect(gain);
  gain.connect(audioCtx.destination);
  osc.start(now);
  osc.stop(now + 0.09);
}

// =============================================================================
// FEATURE 6: INTERACTIVE 3D CINEMA CONCESSIONS (POPCORN TUB & SODA CUP)
// =============================================================================
function buildCinemaConcessions() {
  concessionsGroup = new THREE.Group();
  concessionsGroup.name = "CINEMA_CONCESSIONS";

  // 1. Popcorn Tub Canvas Striped Texture
  const tubCanvas = document.createElement('canvas');
  tubCanvas.width = 256;
  tubCanvas.height = 256;
  const tCtx = tubCanvas.getContext('2d');

  // Red and Cream Stripes
  const stripeCount = 16;
  const stripeW = 256 / stripeCount;
  for (let i = 0; i < stripeCount; i++) {
    tCtx.fillStyle = (i % 2 === 0) ? '#c81d34' : '#f8f4eb';
    tCtx.fillRect(i * stripeW, 0, stripeW, 256);
  }
  // Gold Cineplex Banner across tub
  tCtx.fillStyle = '#e5b958';
  tCtx.fillRect(0, 100, 256, 56);
  tCtx.fillStyle = '#101118';
  tCtx.font = 'bold 24px Cinzel, serif';
  tCtx.textAlign = 'center';
  tCtx.fillText('POPCORN', 128, 138);

  const tubTex = new THREE.CanvasTexture(tubCanvas);

  // Popcorn Tub Cylinder Geometry
  const tubGeo = new THREE.CylinderGeometry(0.095, 0.07, 0.19, 24);
  const tubMat = new THREE.MeshStandardMaterial({
    map: tubTex,
    roughness: 0.45,
    metalness: 0.1,
  });
  popcornTubMesh = new THREE.Mesh(tubGeo, tubMat);
  popcornTubMesh.position.set(-0.08, 0.095, 0);
  popcornTubMesh.castShadow = true;
  popcornTubMesh.receiveShadow = true;
  popcornTubMesh.userData.concessionType = 'popcorn';
  concessionsGroup.add(popcornTubMesh);

  // Golden Popped Corn Kernels Cluster
  popcornKernelsGroup = new THREE.Group();
  popcornKernelsGroup.userData.concessionType = 'popcorn';
  const kernelGeo = new THREE.DodecahedronGeometry(0.022, 1);
  const kernelMat = new THREE.MeshStandardMaterial({
    color: 0xffd970, // Rich warm butter gold
    roughness: 0.7,
    metalness: 0.05,
    bumpScale: 0.04,
  });

  // Procedural cluster of buttered kernels
  for (let i = 0; i < 22; i++) {
    const kMesh = new THREE.Mesh(kernelGeo, kernelMat);
    const rad = Math.random() * 0.075;
    const ang = Math.random() * Math.PI * 2;
    const kx = Math.cos(ang) * rad;
    const kz = Math.sin(ang) * rad;
    const ky = 0.195 + Math.random() * 0.035 - (rad * 0.2);
    kMesh.position.set(-0.08 + kx, ky, kz);
    kMesh.rotation.set(Math.random() * Math.PI, Math.random() * Math.PI, Math.random() * Math.PI);
    kMesh.scale.set(0.85 + Math.random() * 0.4, 0.85 + Math.random() * 0.4, 0.85 + Math.random() * 0.4);
    kMesh.castShadow = true;
    kMesh.userData.concessionType = 'popcorn';
    popcornKernelsGroup.add(kMesh);
  }
  concessionsGroup.add(popcornKernelsGroup);

  // 2. Luxury Cinema Cold Drink / Soda Cup
  const cupGeo = new THREE.CylinderGeometry(0.05, 0.038, 0.17, 20);
  const cupMat = new THREE.MeshStandardMaterial({
    color: 0x1b2030,
    roughness: 0.25,
    metalness: 0.35,
  });
  sodaCupMesh = new THREE.Mesh(cupGeo, cupMat);
  sodaCupMesh.position.set(0.08, 0.085, 0);
  sodaCupMesh.castShadow = true;
  sodaCupMesh.userData.concessionType = 'soda';
  concessionsGroup.add(sodaCupMesh);

  // Soda Cup Lid
  const lidGeo = new THREE.CylinderGeometry(0.053, 0.052, 0.02, 20);
  const lidMat = new THREE.MeshStandardMaterial({
    color: 0x0a0c14,
    roughness: 0.15,
    metalness: 0.8,
  });
  const lidMesh = new THREE.Mesh(lidGeo, lidMat);
  lidMesh.position.set(0.08, 0.175, 0);
  lidMesh.userData.concessionType = 'soda';
  concessionsGroup.add(lidMesh);

  // Angled Translucent Red Straw
  const strawGeo = new THREE.CylinderGeometry(0.005, 0.005, 0.11, 12);
  const strawMat = new THREE.MeshStandardMaterial({
    color: 0xef4444,
    roughness: 0.2,
    metalness: 0.2,
  });
  const strawMesh = new THREE.Mesh(strawGeo, strawMat);
  strawMesh.position.set(0.08, 0.22, 0.01);
  strawMesh.rotation.set(0.18, 0, -0.15);
  strawMesh.userData.concessionType = 'soda';
  concessionsGroup.add(strawMesh);

  // Cupholder Tray Mount Base
  const trayGeo = new THREE.CylinderGeometry(0.17, 0.17, 0.015, 24);
  const trayMat = new THREE.MeshStandardMaterial({
    color: 0x10121a,
    roughness: 0.6,
    metalness: 0.4,
  });
  const trayMesh = new THREE.Mesh(trayGeo, trayMat);
  trayMesh.position.set(0, 0.008, 0);
  trayMesh.receiveShadow = true;
  concessionsGroup.add(trayMesh);

  scene.add(concessionsGroup);
  updateConcessionsPosition(state.currentSeatId);
}

function updateConcessionsPosition(seatId) {
  if (!concessionsGroup || !layoutMetadata?.seats) return;
  const seat = layoutMetadata.seats.find(s => s.seat_id === seatId);
  if (!seat) return;

  const [bx, by, bz] = seat.eye_point;
  // Position on right armrest cupholder:
  // Three.js: X is right (+0.38m), Y is vertical (armrest is ~0.42m below eye point), Z is depth (-by + 0.25m)
  concessionsGroup.position.set(bx + 0.38, bz - 0.42, -by + 0.25);
  concessionsGroup.visible = true;
}

function updateConcessionAppearance() {
  if (!popcornKernelsGroup) return;
  const pack = state.snackPack;

  popcornKernelsGroup.children.forEach(child => {
    if (child.isMesh && child.material) {
      if (pack === 'caramel') {
        child.material.color.setHex(0xb45309); // Deep rich caramel
      } else if (pack === 'vip') {
        child.material.color.setHex(0xfffbeb); // White truffle parmesan
      } else {
        child.material.color.setHex(0xffd970); // Classic butter gold
      }
    }
  });

  if (sodaCupMesh && sodaCupMesh.material) {
    if (pack === 'vip') {
      sodaCupMesh.material.color.setHex(0xca8a04); // Gold champagne flute style
      sodaCupMesh.material.metalness = 0.8;
    } else {
      sodaCupMesh.material.color.setHex(0x1b2030);
      sodaCupMesh.material.metalness = 0.35;
    }
  }
}

function eatPopcorn() {
  state.popcornBites++;
  playPopcornCrunchSound();
  spawnFloatingReaction('🍿', state.currentSeatId);
  updateSnackHUD();
  showToast(`🍿 *Crunch!* Delicious butter popcorn (${state.popcornBites} bites enjoyed)`);
}

function sipSoda() {
  state.sodaSips++;
  playSodaSipSound();
  spawnFloatingReaction('🥤', state.currentSeatId);
  updateSnackHUD();
  showToast(`🥤 *Sip!* Refreshing cold cinema soda (${state.sodaSips} sips taken)`);
}

function updateSnackHUD() {
  const label = document.getElementById('hud-snack-text');
  if (label) {
    label.textContent = `🍿 Bites: ${state.popcornBites} | 🥤 Sips: ${state.sodaSips}`;
  }
}

// =============================================================================
// FEATURE 2: MULTIPLAYER WATCH PARTY & 3D FLOATING REACTION ENGINE
// =============================================================================
function initWatchParty() {
  const urlParams = new URLSearchParams(window.location.search);
  let roomId = urlParams.get('room');
  if (!roomId) {
    roomId = 'CINE-' + Math.floor(1000 + Math.random() * 9000);
  }
  state.watchParty.roomId = roomId;

  try {
    const channel = new BroadcastChannel('virtual_cinema_party_' + roomId);
    state.watchParty.channel = channel;
    state.watchParty.active = true;

    channel.onmessage = handleWatchPartyMessage;

    // Announce entry into room
    broadcastPartyMessage({
      type: 'JOIN',
      userId: state.watchParty.userId,
      userName: state.watchParty.userName,
      seatId: state.currentSeatId,
      movieTitle: state.movieTitle,
      videoSource: state.currentVideoSource,
    });
  } catch (err) {
    console.warn('BroadcastChannel not supported in this environment:', err);
  }

  updateWatchPartyUI();
}

function updateWatchPartyUI() {
  const roomNameEl = document.getElementById('party-room-name');
  if (roomNameEl) {
    roomNameEl.textContent = `Room: ${state.watchParty.roomId}`;
  }

  const linkInput = document.getElementById('watch-party-link-input');
  if (linkInput) {
    const baseUrl = window.location.origin + window.location.pathname;
    linkInput.value = `${baseUrl}?room=${state.watchParty.roomId}`;
  }

  const viewersCountEl = document.getElementById('party-viewers-text');
  if (viewersCountEl) {
    const count = 1 + state.watchParty.remoteMembers.size;
    viewersCountEl.textContent = `👥 ${count} Cinephile${count > 1 ? 's' : ''} Connected`;
  }
}

function broadcastPartyMessage(msg) {
  if (state.watchParty.channel) {
    try {
      state.watchParty.channel.postMessage({
        ...msg,
        senderId: state.watchParty.userId,
        timestamp: Date.now(),
      });
    } catch (e) {
      console.warn('Broadcast error:', e);
    }
  }
}

function handleWatchPartyMessage(event) {
  const data = event.data;
  if (!data || data.senderId === state.watchParty.userId) return;

  console.log('Received Watch Party message:', data);

  if (data.type === 'JOIN') {
    state.watchParty.remoteMembers.set(data.senderId, {
      name: data.userName || 'Guest',
      seatId: data.seatId || 'D-007',
    });
    updateWatchPartyUI();
    render2DSeatMap('lobby-seat-map', false);
    render2DSeatMap('in-theatre-seat-map', true);
    showToast(`👥 ${data.userName || 'A friend'} joined the Watch Party!`);

    // Reply with our presence
    broadcastPartyMessage({
      type: 'PRESENCE_SYNC',
      userId: state.watchParty.userId,
      userName: state.watchParty.userName,
      seatId: state.currentSeatId,
    });
  } else if (data.type === 'PRESENCE_SYNC') {
    state.watchParty.remoteMembers.set(data.senderId, {
      name: data.userName || 'Guest',
      seatId: data.seatId || 'D-007',
    });
    updateWatchPartyUI();
    render2DSeatMap('lobby-seat-map', false);
    render2DSeatMap('in-theatre-seat-map', true);
  } else if (data.type === 'SEAT') {
    const member = state.watchParty.remoteMembers.get(data.senderId);
    if (member) member.seatId = data.seatId;
    render2DSeatMap('lobby-seat-map', false);
    render2DSeatMap('in-theatre-seat-map', true);
  } else if (data.type === 'REACTION') {
    spawnFloatingReaction(data.emoji, data.seatId);
  } else if (data.type === 'SYNC_PLAY') {
    if (html5VideoElement && state.currentVideoSource.type === 'direct') {
      html5VideoElement.play();
    } else if (ytPlayer && typeof ytPlayer.playVideo === 'function') {
      ytPlayer.playVideo();
    }
    isVideoPlaying = true;
    updatePlayPauseButton(true);
    showToast(`▶️ Host resumed playback for everyone`);
  } else if (data.type === 'SYNC_PAUSE') {
    if (html5VideoElement && state.currentVideoSource.type === 'direct') {
      html5VideoElement.pause();
    } else if (ytPlayer && typeof ytPlayer.pauseVideo === 'function') {
      ytPlayer.pauseVideo();
    }
    isVideoPlaying = false;
    updatePlayPauseButton(false);
    showToast(`⏸️ Host paused playback`);
  }
}

// 3D Floating Reaction Spawner (creates 3D billboard sprite with physics wobble & fade)
function spawnFloatingReaction(emoji, seatId = state.currentSeatId) {
  const cv = document.createElement('canvas');
  cv.width = 128;
  cv.height = 128;
  const ctx = cv.getContext('2d');
  ctx.font = '72px sans-serif';
  ctx.textAlign = 'center';
  ctx.textBaseline = 'middle';
  ctx.shadowColor = 'rgba(255, 215, 0, 0.85)';
  ctx.shadowBlur = 18;
  ctx.fillText(emoji, 64, 64);

  const tex = new THREE.CanvasTexture(cv);
  const mat = new THREE.SpriteMaterial({
    map: tex,
    transparent: true,
    opacity: 1.0,
    depthWrite: false,
  });
  const sprite = new THREE.Sprite(mat);
  sprite.scale.set(0.65, 0.65, 1);

  // Position above the reacting seat
  const seat = layoutMetadata?.seats?.find(s => s.seat_id === seatId);
  if (seat) {
    const [bx, by, bz] = seat.eye_point;
    sprite.position.set(bx + (Math.random() - 0.5) * 0.35, bz + 0.35, -by + (Math.random() - 0.5) * 0.35);
  } else {
    sprite.position.copy(camera.position).add(new THREE.Vector3(0, 0.3, -1.0));
  }

  scene.add(sprite);

  activeReactions.push({
    sprite,
    birth: clock.getElapsedTime(),
    maxLife: 2.6,
    riseSpeed: 0.65 + Math.random() * 0.35,
    wobbleSpeed: 4.5 + Math.random() * 3.0,
    wobbleAmp: 0.08 + Math.random() * 0.04,
    initialX: sprite.position.x,
  });

  playReactionPop();
}

function updateFloatingReactions(delta) {
  const now = clock.getElapsedTime();
  for (let i = activeReactions.length - 1; i >= 0; i--) {
    const r = activeReactions[i];
    const age = now - r.birth;

    if (age >= r.maxLife) {
      scene.remove(r.sprite);
      r.sprite.material.map.dispose();
      r.sprite.material.dispose();
      activeReactions.splice(i, 1);
    } else {
      const t = age / r.maxLife;
      r.sprite.position.y += r.riseSpeed * delta;
      r.sprite.position.x = r.initialX + Math.sin(age * r.wobbleSpeed) * r.wobbleAmp;

      // Smooth fade out
      r.sprite.material.opacity = Math.max(0, 1.0 - Math.pow(t, 2.2));

      // Pop and gentle float scale
      const currentScale = 0.65 + t * 0.28;
      r.sprite.scale.set(currentScale, currentScale, 1);
    }
  }
}

function triggerUserReaction(emoji) {
  spawnFloatingReaction(emoji, state.currentSeatId);
  broadcastPartyMessage({
    type: 'REACTION',
    emoji: emoji,
    seatId: state.currentSeatId,
  });
}

// =============================================================================
// FEATURE 1: DYNAMIC REACTIVE SCREEN AMBILIGHT
// =============================================================================
function setupAmbilight() {
  ambilightCanvas = document.createElement('canvas');
  ambilightCanvas.width = 16;
  ambilightCanvas.height = 9;
  ambilightCtx = ambilightCanvas.getContext('2d', { willReadFrequently: true });
}

function updateAmbilight(delta) {
  if (!state.ambilightEnabled || state.lightingMode === 'blackout') {
    // In blackout or disabled mode, keep side ambilight off and return bounce light to standard
    if (screenAmbilightLeft) screenAmbilightLeft.intensity = 0;
    if (screenAmbilightRight) screenAmbilightRight.intensity = 0;
    return;
  }

  ambilightSampleTimer += delta;

  // Sample every ~80ms for optimal balance of responsiveness and performance
  if (ambilightSampleTimer >= 0.08) {
    ambilightSampleTimer = 0;

    if (state.currentVideoSource.type === 'direct' && html5VideoElement && !html5VideoElement.paused && html5VideoElement.readyState >= 2) {
      // Direct HTML5 Video: sample real pixel colors!
      try {
        ambilightCtx.drawImage(html5VideoElement, 0, 0, 16, 9);
        const data = ambilightCtx.getImageData(0, 0, 16, 9).data;
        let rSum = 0, gSum = 0, bSum = 0;
        const totalPixels = 16 * 9;

        for (let i = 0; i < data.length; i += 4) {
          rSum += data[i];
          gSum += data[i + 1];
          bSum += data[i + 2];
        }

        const avgR = (rSum / totalPixels) / 255;
        const avgG = (gSum / totalPixels) / 255;
        const avgB = (bSum / totalPixels) / 255;

        // Boost saturation slightly for dramatic cinematic wall reflection
        const maxC = Math.max(avgR, avgG, avgB);
        const boost = maxC > 0 ? 1.25 : 1.0;

        targetAmbilightColor.setRGB(
          Math.min(1.0, avgR * boost),
          Math.min(1.0, avgG * boost),
          Math.min(1.0, avgB * boost)
        );
      } catch (e) {
        // Fallback to cinematic cycle if cross-origin canvas read is restricted
        computeProceduralCinemaColor();
      }
    } else {
      // YouTube / Vimeo: Procedural dynamic cinematic harmony color engine
      computeProceduralCinemaColor();
    }
  }

  // Smooth exponential color interpolation (lerp)
  currentAmbilightColor.lerp(targetAmbilightColor, delta * 3.5);

  if (screenBounceLight) {
    screenBounceLight.color.copy(currentAmbilightColor);
  }
  if (screenAmbilightLeft) {
    screenAmbilightLeft.color.copy(currentAmbilightColor);
    screenAmbilightLeft.intensity = (state.lightingMode === 'cinema') ? 14 : 4;
  }
  if (screenAmbilightRight) {
    screenAmbilightRight.color.copy(currentAmbilightColor);
    screenAmbilightRight.intensity = (state.lightingMode === 'cinema') ? 14 : 4;
  }
}

function computeProceduralCinemaColor() {
  const t = clock.getElapsedTime() * 0.35;
  // Shifts smoothly between cinematic palette: deep sci-fi cyan, warm tungsten amber, rich violet, golden crimson
  const r = 0.5 + 0.45 * Math.sin(t);
  const g = 0.4 + 0.35 * Math.sin(t + 2.0);
  const b = 0.7 + 0.3 * Math.sin(t + 4.0);
  targetAmbilightColor.setRGB(r, g, b);
}

// =============================================================================
// INITIALIZATION
// =============================================================================
function init() {
  const container = document.getElementById('viewport-container');
  const webglContainer = document.getElementById('webgl-container');
  const css3dContainer = document.getElementById('css3d-container');

  // 1. WebGL Scene & CSS3D Scene
  scene = new THREE.Scene();
  scene.background = new THREE.Color(0x060608);

  cssScene = new THREE.Scene();

  // 2. Camera & WebXR Rig
  camera = new THREE.PerspectiveCamera(60, window.innerWidth / window.innerHeight, 0.1, 200);
  camera.position.set(0, 5.2, -11.5); // Start safely inside high rear auditorium
  camera.lookAt(0, 3.8, 2.3);

  cameraRig = new THREE.Group();
  cameraRig.name = "VR_CAMERA_RIG";
  scene.add(cameraRig);
  cameraRig.add(camera);

  // 3. WebGL Renderer with WebXR VR Enabled
  renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true, powerPreference: 'high-performance' });
  renderer.setSize(window.innerWidth, window.innerHeight);
  renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
  renderer.toneMapping = THREE.ACESFilmicToneMapping;
  renderer.toneMappingExposure = 1.05;
  renderer.shadowMap.enabled = true;
  renderer.shadowMap.type = THREE.PCFSoftShadowMap;

  // Feature 5: Enable WebXR
  renderer.xr.enabled = true;
  renderer.xr.setReferenceSpaceType('local-floor');
  webglContainer.appendChild(renderer.domElement);

  // 4. CSS3D Renderer (mounts HTML iframe directly in 3D space)
  cssRenderer = new CSS3DRenderer();
  cssRenderer.setSize(window.innerWidth, window.innerHeight);
  cssRenderer.domElement.style.position = 'absolute';
  cssRenderer.domElement.style.top = '0';
  cssRenderer.domElement.style.left = '0';
  css3dContainer.appendChild(cssRenderer.domElement);

  // 5. OrbitControls (Strictly bounded to auditorium interior)
  controls = new OrbitControls(camera, renderer.domElement);
  controls.enableDamping = true;
  controls.dampingFactor = 0.05;
  controls.enablePan = false; // Strictly prevent panning camera through meshes/walls
  controls.minDistance = 0.5;
  controls.maxDistance = 14.0; // Strictly prevent zooming out behind rear wall
  controls.minPolarAngle = 0.15; // Prevent flipping over ceiling
  controls.maxPolarAngle = Math.PI / 2 + 0.02; // Prevent flipping below floor

  // 6. Lighting Setup & Ambilight
  setupAuditoriumLights();
  setupAmbilight();

  // 7. Interactive Concessions
  buildCinemaConcessions();

  // 8. Multiplayer Watch Party
  initWatchParty();

  // 9. Render 2D Interactive Seating Maps
  render2DSeatMap('lobby-seat-map', false);
  render2DSeatMap('in-theatre-seat-map', true);
  selectSeat('D-008', false);

  // 10. Load Metadata & 3D GLB Model
  loadMetadataAndAuditorium();

  // 11. Event Listeners & WebXR Session Handlers
  setupEventListeners();
  setupWebXRSession();

  // 12. Start Universal Render Loop (supports WebXR and Standard Desktop)
  renderer.setAnimationLoop(animate);
}

// =============================================================================
// AUDITORIUM LIGHTING & AMBILIGHT SETUP
// =============================================================================
function setupAuditoriumLights() {
  // Ambient fill
  const ambientLight = new THREE.AmbientLight(0x181a24, 0.5);
  scene.add(ambientLight);
  allLights.push({ light: ambientLight, baseIntensity: 0.5, type: 'ambient' });

  // Screen Projector Bounce Light
  screenBounceLight = new THREE.PointLight(0x7ea8f8, 35, 18, 1.2);
  screenBounceLight.position.set(0, 3.8, 1.6);
  scene.add(screenBounceLight);
  allLights.push({ light: screenBounceLight, baseIntensity: 35, type: 'screen' });

  // Left & Right Reactive Screen Ambilight Lights (illuminates side walls)
  screenAmbilightLeft = new THREE.PointLight(0x7ea8f8, 14, 12, 1.3);
  screenAmbilightLeft.position.set(-5.8, 3.8, 0.5);
  scene.add(screenAmbilightLeft);
  allLights.push({ light: screenAmbilightLeft, baseIntensity: 14, type: 'screen' });

  screenAmbilightRight = new THREE.PointLight(0x7ea8f8, 14, 12, 1.3);
  screenAmbilightRight.position.set(5.8, 3.8, 0.5);
  scene.add(screenAmbilightRight);
  allLights.push({ light: screenAmbilightRight, baseIntensity: 14, type: 'screen' });

  // Ceiling Downlights
  const downlightPositions = [
    [-4.5, 7.2, 0.0], [0, 7.2, 0.0], [4.5, 7.2, 0.0],
    [-4.5, 7.2, -4.5], [0, 7.2, -4.5], [4.5, 7.2, -4.5],
    [-4.5, 7.2, -9.0], [0, 7.2, -9.0], [4.5, 7.2, -9.0],
  ];

  downlightPositions.forEach(([x, y, z]) => {
    const dLight = new THREE.PointLight(0xffecd0, 18, 12, 1.4);
    dLight.position.set(x, y, z);
    scene.add(dLight);
    allLights.push({ light: dLight, baseIntensity: 18, type: 'house' });
  });

  // Aisle LED Accent Glow
  const aisleLeftLight = new THREE.PointLight(0xffa834, 12, 8, 1.5);
  aisleLeftLight.position.set(-2.6, 1.2, -5.0);
  scene.add(aisleLeftLight);
  allLights.push({ light: aisleLeftLight, baseIntensity: 12, type: 'step' });

  const aisleRightLight = new THREE.PointLight(0xffa834, 12, 8, 1.5);
  aisleRightLight.position.set(2.6, 1.2, -5.0);
  scene.add(aisleRightLight);
  allLights.push({ light: aisleRightLight, baseIntensity: 12, type: 'step' });

  applyLightingMode('cinema');
}

function applyLightingMode(mode) {
  state.lightingMode = mode;

  allLights.forEach(({ light, baseIntensity, type }) => {
    if (mode === 'cinema') {
      if (type === 'house') {
        light.intensity = 0.0;
      } else if (type === 'step') {
        light.intensity = baseIntensity * 0.08;
      } else if (type === 'screen') {
        light.intensity = baseIntensity * 0.95;
        light.distance = 16.0;
      } else {
        light.intensity = baseIntensity * 0.05;
      }
    } else if (mode === 'house') {
      if (type === 'house') light.intensity = baseIntensity * 1.2;
      else if (type === 'step') light.intensity = baseIntensity * 1.0;
      else if (type === 'screen') light.intensity = baseIntensity * 0.2;
      else light.intensity = baseIntensity * 1.0;
    } else if (mode === 'blackout') {
      // Dark Mode (Blackout): Completely dark! NO light shown except movie screen reflection directly in front of the screen
      if (type === 'screen' && light === screenBounceLight) {
        light.intensity = baseIntensity * 0.85;
        light.distance = 8.0;
      } else {
        light.intensity = 0.0;
      }
    }
  });

  if (scene) {
    if (mode === 'blackout') {
      scene.background.setHex(0x000000);
    } else if (mode === 'cinema') {
      scene.background.setHex(0x010103);
    } else {
      scene.background.setHex(0x0a0c14);
    }
  }

  // Update HUD active button
  document.querySelectorAll('#theatre-hud-bottom .dock-btn').forEach(btn => {
    if (btn.id.startsWith('btn-light-')) {
      btn.classList.toggle('active', btn.id.includes(mode));
    }
  });
}

// =============================================================================
// FEATURE 5: WEBXR / VR SESSION MANAGEMENT
// =============================================================================
function setupWebXRSession() {
  renderer.xr.addEventListener('sessionstart', () => {
    console.log('WebXR Session Started');
    showToast('🕶️ Welcome to Virtual Reality Cinema! Look around naturally.');

    if (state.currentSeatId && layoutMetadata?.seats) {
      const seat = layoutMetadata.seats.find(s => s.seat_id === state.currentSeatId);
      if (seat) {
        const [bx, by, bz] = seat.eye_point;
        cameraRig.position.set(bx, bz, -by);
        cameraRig.rotation.set(0, Math.PI, 0); // Face the cinema screen
      }
    }
    controls.enabled = false;
  });

  renderer.xr.addEventListener('sessionend', () => {
    console.log('WebXR Session Ended');
    cameraRig.position.set(0, 0, 0);
    cameraRig.rotation.set(0, 0, 0);
    controls.enabled = true;
  });
}

// =============================================================================
// ASSET LOADING: METADATA & 3D GLB
// =============================================================================
async function loadMetadataAndAuditorium() {
  const progressBar = document.getElementById('loader-progress-fill');

  try {
    const metaRes = await fetch('./assets/cinema_layout_metadata.json');
    layoutMetadata = await metaRes.json();
    progressBar.style.width = '35%';

    const dracoLoader = new DRACOLoader();
    dracoLoader.setDecoderPath('./draco/');

    const gltfLoader = new GLTFLoader();
    gltfLoader.setDRACOLoader(dracoLoader);

    gltfLoader.load(
      './assets/cinema_theatre_auditorium.glb',
      (gltf) => {
        auditoriumModel = gltf.scene;
        progressBar.style.width = '80%';

        auditoriumModel.traverse((child) => {
          if (child.isMesh) {
            child.castShadow = true;
            child.receiveShadow = true;

            // Screen Mesh: punch transparent alpha hole in WebGL so CSS3D YouTube iframe shows through!
            if (child.name === 'SCREEN_MAIN') {
              screenMesh = child;
              child.material = new THREE.MeshBasicMaterial({
                color: 0x000000,
                opacity: 0.0,
                transparent: true,
                blending: THREE.NoBlending,
              });
            }

            // Identify seat meshes for picking
            if (child.name.startsWith('SEAT_')) {
              const match = child.name.match(/SEAT_([A-G])_(\d{3})/);
              if (match) {
                const seatId = `${match[1]}-${match[2]}`;
                child.userData.seatId = seatId;
                if (!seatMeshMap.has(seatId)) {
                  seatMeshMap.set(seatId, child);
                }
              }
            }
          }
        });

        scene.add(auditoriumModel);
        progressBar.style.width = '100%';

        // Setup CSS3D Screen Plane
        setupCSS3DScreen();

        // Reposition concessions on starting seat
        updateConcessionsPosition(state.currentSeatId);

        // Dismiss Loader
        setTimeout(() => {
          document.getElementById('loader-overlay').classList.remove('active');
        }, 500);
      },
      (xhr) => {
        if (xhr.lengthComputable) {
          const percent = 35 + (xhr.loaded / xhr.total) * 45;
          progressBar.style.width = `${percent}%`;
        }
      },
      (error) => {
        console.error('Error loading 3D Auditorium GLB:', error);
      }
    );
  } catch (err) {
    console.error('Failed to load auditorium assets:', err);
  }
}

// =============================================================================
// CSS3D DUAL-ENGINE SCREEN SETUP (YOUTUBE / DIRECT MP4 / LOCAL FILE)
// =============================================================================
function setupCSS3DScreen() {
  if (!screenMesh) {
    console.warn('Screen mesh SCREEN_MAIN not found in 3D model.');
    return;
  }

  const screenBox = new THREE.Box3().setFromObject(screenMesh);
  const size = new THREE.Vector3();
  screenBox.getSize(size);

  const screenWidth = size.x || 13.5;
  const screenW = 1920;
  const screenH = Math.round(screenW / 2.39); // ~803px

  const container = document.createElement('div');
  container.id = 'theatre-screen-container';
  container.style.width = `${screenW}px`;
  container.style.height = `${screenH}px`;
  container.style.backgroundColor = '#000000';
  container.style.position = 'relative';
  container.style.overflow = 'hidden';

  // 1. YouTube / Vimeo IFrame Player
  ensureYouTubeIframe(container);

  // 2. HTML5 Video Player
  const video = document.createElement('video');
  video.id = 'theatre-html5-player';
  video.style.width = '100%';
  video.style.height = '100%';
  video.style.border = '0';
  video.style.display = 'none';
  video.style.position = 'absolute';
  video.style.top = '0';
  video.style.left = '0';
  video.style.backgroundColor = '#000';
  video.style.objectFit = 'contain';
  video.playsInline = true;
  video.controls = true;
  video.autoplay = true;
  video.loop = true;

  video.addEventListener('error', () => {
    if (!video.src || video.src === window.location.href || !video.getAttribute('src')) return;
    console.error('HTML5 Video Error:', video.error);
    showToast('⚠️ External video failed to load. Check that the video URL is accessible and directly streams video.');
  });

  video.addEventListener('play', () => {
    isVideoPlaying = true;
    updatePlayPauseButton(true);
    connectVideoToSpatialAudio();
  });

  video.addEventListener('pause', () => {
    isVideoPlaying = false;
    updatePlayPauseButton(false);
  });

  video.addEventListener('ended', () => {
    console.log('Video duration reached. Recursively replaying from start...');
    video.currentTime = 0;
    video.play().catch(e => {
      console.warn('Auto-loop play retry with muted fallback:', e);
      video.muted = true;
      video.play();
    });
  });

  container.appendChild(video);
  html5VideoElement = video;

  cssScreenObj = new CSS3DObject(container);
  cssScreenObj.position.set(0, 3.95, 2.29);
  cssScreenObj.rotation.set(0, Math.PI, 0);

  const scale = screenWidth / screenW;
  cssScreenObj.scale.set(scale, scale, scale);

  cssScene.add(cssScreenObj);
  console.log('CSS3D Dual-Engine Screen initialized at:', cssScreenObj.position, 'Scale:', scale);

  bindYouTubePlayer();
  playTrailer(state.youtubeUrl || state.youtubeVideoId, false);
}

function ensureYouTubeIframe(parentContainer) {
  let iframe = document.getElementById('theatre-youtube-player');
  const container = parentContainer || document.getElementById('theatre-screen-container');

  if (!iframe) {
    iframe = document.createElement('iframe');
    iframe.id = 'theatre-youtube-player';
    iframe.style.width = '100%';
    iframe.style.height = '100%';
    iframe.style.border = '0';
    iframe.style.display = 'block';
    iframe.style.position = 'absolute';
    iframe.style.top = '0';
    iframe.style.left = '0';
    iframe.style.backgroundColor = '#000';
    iframe.allow = 'accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture; web-share';
    iframe.allowFullscreen = true;
    iframe.setAttribute('referrerpolicy', 'strict-origin-when-cross-origin');
    if (container) {
      container.appendChild(iframe);
    }
  } else if (container && !container.contains(iframe)) {
    container.appendChild(iframe);
  }
  iframeElement = iframe;
  return iframe;
}

function bindYouTubePlayer() {
  const iframe = ensureYouTubeIframe();
  if (!iframe) return;

  if (window.YT && window.YT.Player) {
    try {
      // If player already exists and API is intact, do NOT destroy it!
      if (ytPlayer && typeof ytPlayer.getPlayerState === 'function') {
        ytPlayerReady = true;
        return;
      }

      ytPlayer = new YT.Player('theatre-youtube-player', {
        events: {
          'onReady': () => {
            console.log('YouTube Player bound successfully via official API');
            ytPlayerReady = true;
            if (state.pendingYouTubeLoad) {
              const { id, autoplay, start } = state.pendingYouTubeLoad;
              state.pendingYouTubeLoad = null;
              loadYouTubeVideoInPlayer(id, autoplay, start);
            }
          },
          'onStateChange': (event) => {
            if (event.data === 1) { // PLAYING
              isVideoPlaying = true;
              updatePlayPauseButton(true);
            } else if (event.data === 2) { // PAUSED
              isVideoPlaying = false;
              updatePlayPauseButton(false);
            } else if (event.data === 0) { // ENDED
              console.log('YouTube video duration reached. Looping trailer from start...');
              try {
                if (ytPlayer && typeof ytPlayer.seekTo === 'function') {
                  ytPlayer.seekTo(0, true);
                  ytPlayer.playVideo();
                }
              } catch (e) {
                console.warn('Auto-loop error:', e);
              }
              isVideoPlaying = true;
              updatePlayPauseButton(true);
            }
          },
          'onError': (event) => {
            handleYouTubeError(event.data);
          }
        }
      });
    } catch (e) {
      console.warn('Could not bind YT.Player instance:', e);
    }
  }
}

function handleYouTubeError(errorCode) {
  console.warn('YouTube Player reported error code:', errorCode);
  let errorMsg = '⚠️ YouTube Video playback error.';
  let showFallback = false;

  switch (errorCode) {
    case 2:
      errorMsg = '⚠️ Invalid YouTube link or Video ID. Please verify the URL.';
      break;
    case 5:
      errorMsg = '⚠️ HTML5 player playback error for this YouTube stream.';
      break;
    case 100:
      errorMsg = '⚠️ Video not found (it may have been deleted or set to Private).';
      showFallback = true;
      break;
    case 101:
    case 150:
      errorMsg = '⚠️ Video publisher has disabled embedded playback on 3rd-party sites (Error 150/101).';
      showFallback = true;
      break;
    default:
      errorMsg = `⚠️ YouTube playback issue (Error code: ${errorCode}).`;
  }

  showToast(errorMsg, 5000);

  if (showFallback) {
    showEmbedRestrictedBanner(state.youtubeVideoId);
  }
}

function showEmbedRestrictedBanner(videoId) {
  const card = document.getElementById('embed-restriction-card');
  if (!card) return;
  const link = document.getElementById('btn-restriction-watch-yt');
  if (link && videoId) {
    link.href = `https://www.youtube.com/watch?v=${videoId}`;
  }
  card.classList.remove('hide');
}

function hideEmbedRestrictedBanner() {
  const card = document.getElementById('embed-restriction-card');
  if (card) {
    card.classList.add('hide');
  }
}

function loadYouTubeVideoInPlayer(videoId, autoplay, start = 0) {
  hideEmbedRestrictedBanner();

  if (ytPlayer && ytPlayerReady && typeof ytPlayer.loadVideoById === 'function') {
    try {
      if (autoplay) {
        ytPlayer.loadVideoById({
          videoId: videoId,
          startSeconds: start || 0,
        });

        // Test if autoplay succeeded or was blocked by browser audio policy
        setTimeout(() => {
          if (ytPlayer && typeof ytPlayer.getPlayerState === 'function') {
            const ps = ytPlayer.getPlayerState();
            // If not playing (1) or buffering (3), try muted play fallback
            if (ps !== 1 && ps !== 3) {
              console.log('Attempting muted autoplay fallback for YouTube...');
              if (typeof ytPlayer.mute === 'function') {
                ytPlayer.mute();
                ytPlayer.playVideo();
                state.isMuted = true;
                updateMuteButton(true);
                showToast('🔊 Trailer started muted due to browser policy. Click screen or press Unmute.', 4000);
              }
            }
          }
        }, 1200);
      } else {
        ytPlayer.cueVideoById({
          videoId: videoId,
          startSeconds: start || 0,
        });
      }
      return;
    } catch (err) {
      console.warn('ytPlayer.loadVideoById error, falling back to iframe src:', err);
    }
  }

  // Fallback: direct src update
  const newSrc = buildYouTubeEmbedUrl(videoId, autoplay, start);
  if (iframeElement && iframeElement.src !== newSrc) {
    iframeElement.src = newSrc;
  }
}

window.onYouTubeIframeAPIReady = function() {
  bindYouTubePlayer();
};

function unloadHTML5Video() {
  if (!html5VideoElement) return;
  if (!html5VideoElement.paused) html5VideoElement.pause();
  html5VideoElement.removeAttribute('src');
  html5VideoElement.load();
  html5VideoElement.style.display = 'none';
}

function playTrailer(sourceInput, autoplay = true) {
  const parsed = parseVideoSource(sourceInput);
  state.currentVideoSource = parsed;
  console.log('Playing trailer source:', parsed);

  hideEmbedRestrictedBanner();

  if (!iframeElement || !html5VideoElement) return;

  const autoplayParam = autoplay ? '1' : '0';

  if (parsed.type === 'direct') {
    iframeElement.style.display = 'none';
    if (ytPlayer && typeof ytPlayer.pauseVideo === 'function') {
      try { ytPlayer.pauseVideo(); } catch (e) {}
    }
    iframeElement.src = 'about:blank';

    html5VideoElement.style.display = 'block';
    html5VideoElement.src = parsed.src;
    html5VideoElement.currentTime = 0;

    if (autoplay) {
      const playPromise = html5VideoElement.play();
      if (playPromise !== undefined) {
        playPromise.then(() => {
          isVideoPlaying = true;
          updatePlayPauseButton(true);
          connectVideoToSpatialAudio();
        }).catch(err => {
          console.warn('Autoplay blocked by browser policy, muting audio to proceed:', err);
          html5VideoElement.muted = true;
          state.isMuted = true;
          updateMuteButton(true);
          html5VideoElement.play().then(() => {
            isVideoPlaying = true;
            updatePlayPauseButton(true);
            showToast('🔊 Trailer auto-muted by browser. Click screen or use controls to unmute.');
          }).catch(e => {
            console.error('HTML5 video failed to play:', e);
            isVideoPlaying = false;
            updatePlayPauseButton(false);
          });
        });
      }
    } else {
      isVideoPlaying = false;
      updatePlayPauseButton(false);
    }
  } else if (parsed.type === 'vimeo') {
    unloadHTML5Video();
    ensureYouTubeIframe();
    iframeElement.style.display = 'block';
    iframeElement.src = `https://player.vimeo.com/video/${parsed.id}?autoplay=${autoplayParam}&loop=1&title=0&byline=0&portrait=0`;
    isVideoPlaying = autoplay;
    updatePlayPauseButton(autoplay);
  } else {
    // YouTube
    unloadHTML5Video();
    ensureYouTubeIframe();
    iframeElement.style.display = 'block';

    state.youtubeVideoId = parsed.id;

    if (ytPlayer && ytPlayerReady && typeof ytPlayer.loadVideoById === 'function') {
      loadYouTubeVideoInPlayer(parsed.id, autoplay, parsed.start);
    } else {
      state.pendingYouTubeLoad = { id: parsed.id, autoplay, start: parsed.start };
      const newSrc = buildYouTubeEmbedUrl(parsed.id, autoplay, parsed.start);
      if (iframeElement.src !== newSrc) {
        iframeElement.src = newSrc;
      }
      bindYouTubePlayer();
    }
    isVideoPlaying = autoplay;
    updatePlayPauseButton(autoplay);
  }
}

function updatePlayPauseButton(isPlaying) {
  const btn = document.getElementById('btn-toggle-video');
  if (!btn) return;
  if (isPlaying) {
    btn.innerHTML = '⏸️ Pause Trailer';
  } else {
    btn.innerHTML = '▶️ Play Trailer';
  }
}

function updateMuteButton(isMuted) {
  const btn = document.getElementById('btn-toggle-mute');
  if (!btn) return;
  btn.innerHTML = isMuted ? '🔇 Unmute' : '🔊 Mute';
  btn.classList.toggle('active', !isMuted);
}

function toggleTrailerMute() {
  if (state.currentVideoSource && state.currentVideoSource.type === 'direct' && html5VideoElement) {
    html5VideoElement.muted = !html5VideoElement.muted;
    state.isMuted = html5VideoElement.muted;
    updateMuteButton(state.isMuted);
    showToast(state.isMuted ? '🔇 Audio muted' : '🔊 Audio unmuted', 2000);
    return;
  }

  if (ytPlayer) {
    try {
      if (typeof ytPlayer.isMuted === 'function') {
        const muted = ytPlayer.isMuted();
        if (muted) {
          ytPlayer.unMute();
          state.isMuted = false;
          updateMuteButton(false);
          showToast('🔊 Audio unmuted', 2000);
        } else {
          ytPlayer.mute();
          state.isMuted = true;
          updateMuteButton(true);
          showToast('🔇 Audio muted', 2000);
        }
        return;
      }
    } catch (e) {
      console.warn('ytPlayer mute toggle error:', e);
    }
  }

  if (iframeElement && iframeElement.contentWindow) {
    state.isMuted = !state.isMuted;
    const func = state.isMuted ? 'mute' : 'unMute';
    iframeElement.contentWindow.postMessage(JSON.stringify({ event: 'command', func }), '*');
    updateMuteButton(state.isMuted);
    showToast(state.isMuted ? '🔇 Audio muted' : '🔊 Audio unmuted', 2000);
  }
}

function reloadTrailer() {
  showToast('🔄 Reloading trailer stream...', 2000);
  playTrailer(state.youtubeUrl || state.youtubeVideoId, isVideoPlaying);
}

function toggleTrailerPlayback() {
  if (state.currentVideoSource && state.currentVideoSource.type === 'direct' && html5VideoElement) {
    if (html5VideoElement.paused || html5VideoElement.ended) {
      const playPromise = html5VideoElement.play();
      if (playPromise !== undefined) {
        playPromise.then(() => {
          isVideoPlaying = true;
          updatePlayPauseButton(true);
          broadcastPartyMessage({ type: 'SYNC_PLAY' });
        }).catch(err => {
          console.warn('Direct video play blocked by browser policy, muting to resume:', err);
          html5VideoElement.muted = true;
          state.isMuted = true;
          updateMuteButton(true);
          html5VideoElement.play().then(() => {
            isVideoPlaying = true;
            updatePlayPauseButton(true);
            broadcastPartyMessage({ type: 'SYNC_PLAY' });
          });
        });
      }
    } else {
      html5VideoElement.pause();
      isVideoPlaying = false;
      updatePlayPauseButton(false);
      broadcastPartyMessage({ type: 'SYNC_PAUSE' });
    }
    return;
  }

  if (ytPlayer && typeof ytPlayer.getPlayerState === 'function') {
    try {
      const playerState = ytPlayer.getPlayerState();
      if (playerState === 1 || playerState === 3) {
        ytPlayer.pauseVideo();
        isVideoPlaying = false;
        updatePlayPauseButton(false);
        broadcastPartyMessage({ type: 'SYNC_PAUSE' });
      } else {
        ytPlayer.playVideo();
        if (ytPlayer.isMuted && ytPlayer.isMuted() && !state.isMuted) {
          try { ytPlayer.unMute(); } catch (e) {}
        }
        isVideoPlaying = true;
        updatePlayPauseButton(true);
        broadcastPartyMessage({ type: 'SYNC_PLAY' });
      }
      return;
    } catch (e) {
      console.warn('YT.Player call failed, falling back to postMessage:', e);
    }
  }

  if (iframeElement && iframeElement.contentWindow) {
    const action = isVideoPlaying ? 'pauseVideo' : 'playVideo';
    const payloads = [
      JSON.stringify({ event: 'command', func: action, args: [] }),
      JSON.stringify({ event: 'command', func: action, args: '' }),
      JSON.stringify({ event: 'command', func: action }),
    ];
    payloads.forEach(p => {
      try {
        iframeElement.contentWindow.postMessage(p, '*');
      } catch (err) {}
    });

    isVideoPlaying = !isVideoPlaying;
    updatePlayPauseButton(isVideoPlaying);
    broadcastPartyMessage({ type: isVideoPlaying ? 'SYNC_PLAY' : 'SYNC_PAUSE' });
  }
}

// =============================================================================
// CAMERA NAVIGATION & SEAT FOCUS
// =============================================================================
function moveToSeat(seatId, duration = 1.6) {
  if (!layoutMetadata || !layoutMetadata.seats) return;

  const seatData = layoutMetadata.seats.find(s => s.seat_id === seatId);
  if (!seatData) return;

  state.currentSeatId = seatId;
  sync2DSeatMapSelection(seatId);

  // Position concessions on right armrest cupholder
  updateConcessionsPosition(seatId);

  // Broadcast seat move to Watch Party
  broadcastPartyMessage({
    type: 'SEAT',
    seatId: seatId,
  });

  const [bx, by, bz] = seatData.eye_point;
  const targetX = bx;
  const targetY = bz;
  const targetZ = -by;

  const screenCenter = new THREE.Vector3(0, 3.95, 2.3);

  // Start smooth camera tween
  camTarget.startPos.copy(camera.position);
  camTarget.startLookAt.copy(controls.target);
  camTarget.pos.set(targetX, targetY, targetZ);
  camTarget.lookAt.copy(screenCenter);
  camTarget.duration = duration;
  camTarget.elapsed = 0;
  camTarget.active = true;

  controls.enabled = false;

  const seatTypeLabel = seatData.seat_type === 'VIP_RECLINER' ? '👑 VIP Luxury Recliner' :
                        (seatData.seat_type === 'ACCESSIBLE' ? '♿ Wheelchair Space' : '⭐ Standard');
  document.getElementById('hud-seat-info').textContent = `Row ${seatData.row_label}, Seat ${seatData.seat_number} (${seatTypeLabel})`;

  document.querySelectorAll('#theatre-hud-bottom .dock-buttons:first-child .dock-btn').forEach(btn => {
    btn.classList.remove('active');
  });
  if (seatId === 'D-008') document.getElementById('btn-cam-sweetspot').classList.add('active');
  else if (seatId === 'G-008') document.getElementById('btn-cam-vip').classList.add('active');
  else if (seatId === 'A-008') document.getElementById('btn-cam-front').classList.add('active');
}

function moveToOverview() {
  state.isOrbitMode = true;
  camTarget.startPos.copy(camera.position);
  camTarget.startLookAt.copy(controls.target);
  camTarget.pos.set(0, 5.2, -11.5);
  camTarget.lookAt.set(0, 3.8, 2.3);
  camTarget.duration = 1.8;
  camTarget.elapsed = 0;
  camTarget.active = true;
  controls.enabled = false;

  document.getElementById('hud-seat-info').textContent = '🌐 Orbit Perspective (Inside Theatre)';
  document.querySelectorAll('#theatre-hud-bottom .dock-buttons:first-child .dock-btn').forEach(btn => {
    btn.classList.toggle('active', btn.id === 'btn-cam-overview');
  });
}

function clampCameraInsideTheatre() {
  const minX = -6.6;
  const maxX = 6.6;
  const minY = 1.35;
  const maxY = 5.8;
  const minZ = -12.2;
  const maxZ = 1.2;

  camera.position.x = THREE.MathUtils.clamp(camera.position.x, minX, maxX);
  camera.position.y = THREE.MathUtils.clamp(camera.position.y, minY, maxY);
  camera.position.z = THREE.MathUtils.clamp(camera.position.z, minZ, maxZ);

  controls.target.x = THREE.MathUtils.clamp(controls.target.x, -4.5, 4.5);
  controls.target.y = THREE.MathUtils.clamp(controls.target.y, 1.8, 5.2);
  controls.target.z = THREE.MathUtils.clamp(controls.target.z, -8.0, 2.3);
}

// =============================================================================
// SEAT & CONCESSION INTERACTION: RAYCASTING & HOVER
// =============================================================================
function isPointerOverUI(event) {
  if (!event) return false;
  const el = event.target;
  if (!el) return false;

  // Check if pointer is over any HUD dock, button, modal, form control, toast, or pill
  if (el.closest) {
    if (
      el.closest(
        '#theatre-hud-bottom, #theatre-hud-top, .hud-bottom, .hud-top, ' +
        '.modal-backdrop, .glass-panel, .embed-restriction-modal, .toast-notification, ' +
        '.seat-tooltip, .interactive-seat-map, .seat-node, .preset-btn, .concession-btn, ' +
        'button, input, select, textarea, label, a, .dock-btn, .reaction-btn, .hud-btn'
      )
    ) {
      return true;
    }
  }

  const tag = (el.tagName || '').toLowerCase();
  return ['button', 'input', 'select', 'textarea', 'label', 'a'].includes(tag);
}

function handlePointerMove(event) {
  if (!state.inTheatre) return;

  const tooltip = document.getElementById('seat-tooltip');

  // If pointer is over HUD buttons or modal, dismiss tooltip & unhighlight seat
  if (isPointerOverUI(event)) {
    if (tooltip) tooltip.classList.add('hide');
    if (hoveredSeat && originalMaterialMap.has(hoveredSeat)) {
      hoveredSeat.material = originalMaterialMap.get(hoveredSeat);
      hoveredSeat = null;
    }
    document.body.style.cursor = 'default';
    return;
  }

  mouse.x = (event.clientX / window.innerWidth) * 2 - 1;
  mouse.y = -(event.clientY / window.innerHeight) * 2 + 1;

  raycaster.setFromCamera(mouse, camera);

  // 1. Check Concessions Raycast First
  if (concessionsGroup && concessionsGroup.visible) {
    const concessionHits = raycaster.intersectObjects(concessionsGroup.children, true);
    let foundConcessionType = null;
    for (const hit of concessionHits) {
      if (hit.object.userData && hit.object.userData.concessionType) {
        foundConcessionType = hit.object.userData.concessionType;
        break;
      }
    }

    if (foundConcessionType) {
      if (hoveredSeat && originalMaterialMap.has(hoveredSeat)) {
        hoveredSeat.material = originalMaterialMap.get(hoveredSeat);
        hoveredSeat = null;
      }
      tooltip.querySelector('.tooltip-id').textContent = foundConcessionType === 'popcorn' ? '🍿 Butter Popcorn' : '🥤 Cinema Soda';
      tooltip.querySelector('.tooltip-type').textContent = foundConcessionType === 'popcorn' ? 'Click to Crunch & Eat!' : 'Click to Sip Drink!';
      tooltip.style.left = `${event.clientX}px`;
      tooltip.style.top = `${event.clientY}px`;
      tooltip.classList.remove('hide');
      document.body.style.cursor = 'pointer';
      return;
    }
  }

  // 2. Check Theatre Seats Raycast
  if (!auditoriumModel) return;

  const intersects = raycaster.intersectObjects(auditoriumModel.children, true);
  let foundSeat = null;

  for (const hit of intersects) {
    let obj = hit.object;
    while (obj && obj !== auditoriumModel) {
      if (obj.userData && obj.userData.seatId) {
        foundSeat = { object: hit.object, seatId: obj.userData.seatId };
        break;
      }
      obj = obj.parent;
    }
    if (foundSeat) break;
  }

  if (foundSeat) {
    document.body.style.cursor = 'pointer';
    if (hoveredSeat !== foundSeat.object) {
      if (hoveredSeat && originalMaterialMap.has(hoveredSeat)) {
        hoveredSeat.material = originalMaterialMap.get(hoveredSeat);
      }
      hoveredSeat = foundSeat.object;
      if (!originalMaterialMap.has(hoveredSeat)) {
        originalMaterialMap.set(hoveredSeat, hoveredSeat.material);
      }
      hoveredSeat.material = highlightMaterial;
    }

    const seatData = layoutMetadata?.seats?.find(s => s.seat_id === foundSeat.seatId);
    tooltip.querySelector('.tooltip-id').textContent = `Seat ${foundSeat.seatId}`;
    tooltip.querySelector('.tooltip-type').textContent = seatData ? `${seatData.seat_type}` : 'Cinema Seat';
    tooltip.style.left = `${event.clientX}px`;
    tooltip.style.top = `${event.clientY}px`;
    tooltip.classList.remove('hide');
  } else {
    document.body.style.cursor = 'default';
    if (hoveredSeat && originalMaterialMap.has(hoveredSeat)) {
      hoveredSeat.material = originalMaterialMap.get(hoveredSeat);
      hoveredSeat = null;
    }
    tooltip.classList.add('hide');
  }
}

function handlePointerDown(event) {
  if (!state.inTheatre) return;

  // CRITICAL FIX: If pointer is clicking on any bottom dock button, top HUD button,
  // or modal, ignore 3D raycasting so it NEVER redirects to the seat behind the button!
  if (isPointerOverUI(event)) {
    return;
  }

  mouse.x = (event.clientX / window.innerWidth) * 2 - 1;
  mouse.y = -(event.clientY / window.innerHeight) * 2 + 1;

  raycaster.setFromCamera(mouse, camera);

  // 1. Check Concession Clicks
  if (concessionsGroup && concessionsGroup.visible) {
    const concessionHits = raycaster.intersectObjects(concessionsGroup.children, true);
    for (const hit of concessionHits) {
      if (hit.object.userData && hit.object.userData.concessionType) {
        if (hit.object.userData.concessionType === 'popcorn') {
          eatPopcorn();
        } else if (hit.object.userData.concessionType === 'soda') {
          sipSoda();
        }
        return;
      }
    }
  }

  // 2. Check Screen Click to Play/Pause Trailer & Unmute
  if (screenMesh) {
    const screenHits = raycaster.intersectObject(screenMesh, false);
    if (screenHits && screenHits.length > 0) {
      toggleTrailerPlayback();
      if (ytPlayer && typeof ytPlayer.isMuted === 'function' && ytPlayer.isMuted()) {
        try {
          ytPlayer.unMute();
          state.isMuted = false;
          updateMuteButton(false);
          showToast('🔊 Audio unmuted', 2000);
        } catch (e) {}
      }
      return;
    }
  }

  // 3. Check Seat Selection Clicks
  if (!auditoriumModel) return;

  const intersects = raycaster.intersectObjects(auditoriumModel.children, true);
  for (const hit of intersects) {
    let obj = hit.object;
    while (obj && obj !== auditoriumModel) {
      if (obj.userData && obj.userData.seatId) {
        moveToSeat(obj.userData.seatId, 1.4);
        return;
      }
      obj = obj.parent;
    }
  }
}

// =============================================================================
// 2D SEAT MAP FUNCTIONS
// =============================================================================
function render2DSeatMap(containerId, isFloatingModal = false) {
  const container = document.getElementById(containerId);
  if (!container) return;
  container.innerHTML = '';

  const rows = ['A', 'B', 'C', 'D', 'E', 'F', 'G'];

  rows.forEach(rowLetter => {
    const rowEl = document.createElement('div');
    rowEl.className = 'seat-row';
    rowEl.dataset.row = rowLetter;

    // Left row letter label
    const leftLabel = document.createElement('span');
    leftLabel.className = 'seat-row-label';
    leftLabel.textContent = rowLetter;
    rowEl.appendChild(leftLabel);

    // Left Block: seats 1, 2, 3
    const leftBlock = document.createElement('div');
    leftBlock.className = 'seat-block block-left';
    for (let num = 1; num <= 3; num++) {
      leftBlock.appendChild(createSeatNode(rowLetter, num, isFloatingModal));
    }
    rowEl.appendChild(leftBlock);

    // Aisle Space Left
    const aisleLeft = document.createElement('div');
    aisleLeft.className = 'aisle-space';
    rowEl.appendChild(aisleLeft);

    // Center Block: seats 4 through 12
    const centerBlock = document.createElement('div');
    centerBlock.className = 'seat-block block-center';
    for (let num = 4; num <= 12; num++) {
      centerBlock.appendChild(createSeatNode(rowLetter, num, isFloatingModal));
    }
    rowEl.appendChild(centerBlock);

    // Aisle Space Right
    const aisleRight = document.createElement('div');
    aisleRight.className = 'aisle-space';
    rowEl.appendChild(aisleRight);

    // Right Block: seats 13 through 15
    const rightBlock = document.createElement('div');
    rightBlock.className = 'seat-block block-right';
    for (let num = 13; num <= 15; num++) {
      rightBlock.appendChild(createSeatNode(rowLetter, num, isFloatingModal));
    }
    rowEl.appendChild(rightBlock);

    // Right row letter label
    const rightLabel = document.createElement('span');
    rightLabel.className = 'seat-row-label';
    rightLabel.textContent = rowLetter;
    rowEl.appendChild(rightLabel);

    container.appendChild(rowEl);
  });
}

function createSeatNode(rowLetter, num, isFloatingModal) {
  const seatId = `${rowLetter}-${String(num).padStart(3, '0')}`;
  const seatEl = document.createElement('button');
  seatEl.type = 'button';
  seatEl.className = 'seat-cell';
  seatEl.dataset.seatId = seatId;
  seatEl.dataset.row = rowLetter;
  seatEl.dataset.num = num;

  let seatType = 'STANDARD';
  if (seatId === 'D-008') {
    seatType = 'SWEET_SPOT';
    seatEl.classList.add('seat-sweet-spot');
    seatEl.innerHTML = `<span class="seat-icon">⭐</span>`;
  } else if (rowLetter === 'G') {
    seatType = 'VIP_RECLINER';
    seatEl.classList.add('seat-vip');
    seatEl.innerHTML = `<span class="seat-icon">👑</span>`;
  } else if (rowLetter === 'A') {
    seatType = 'ACCESSIBLE';
    seatEl.classList.add('seat-accessible');
    seatEl.innerHTML = `<span class="seat-icon">♿</span>`;
  } else {
    seatEl.classList.add('seat-standard');
    seatEl.textContent = num;
  }

  // Check if occupied by a remote Watch Party member
  for (const [userId, member] of state.watchParty.remoteMembers.entries()) {
    if (member.seatId === seatId) {
      seatEl.classList.add('occupied-by-guest');
      seatEl.title = `Occupied by ${member.name}`;
      break;
    }
  }

  if (!seatEl.title) {
    seatEl.title = `Row ${rowLetter}, Seat ${num} (${getSeatTypeTitle(seatId, seatType)})`;
  }

  if (seatId === state.currentSeatId) {
    seatEl.classList.add('selected');
  }

  seatEl.addEventListener('click', (e) => {
    e.preventDefault();
    selectSeat(seatId, isFloatingModal);
  });

  return seatEl;
}

function getSeatTypeTitle(seatId, seatType) {
  if (seatId === 'D-008') return 'Acoustic Sweet Spot';
  if (seatType === 'VIP_RECLINER') return 'VIP Luxury Recliner';
  if (seatType === 'ACCESSIBLE') return 'Wheelchair Accessible';
  return 'Standard Burgundy Velvet';
}

function selectSeat(seatId, triggerCameraMove = false) {
  state.currentSeatId = seatId;
  sync2DSeatMapSelection(seatId);

  if (triggerCameraMove && state.inTheatre) {
    moveToSeat(seatId, 1.4);
    const inTheatreModal = document.getElementById('theatre-seatmap-modal');
    if (inTheatreModal) inTheatreModal.classList.remove('active');
  }
}

function sync2DSeatMapSelection(seatId) {
  document.querySelectorAll('.seat-cell').forEach(el => {
    el.classList.toggle('selected', el.dataset.seatId === seatId);
  });

  const [row, numStr] = seatId.split('-');
  const num = parseInt(numStr, 10);
  let typeTitle = 'Standard Velvet';
  if (seatId === 'D-008') typeTitle = 'Acoustic Sweet Spot';
  else if (row === 'G') typeTitle = 'VIP Luxury Recliner';
  else if (row === 'A') typeTitle = 'Wheelchair Accessible';

  const labelEl = document.getElementById('lobby-selected-seat-text');
  if (labelEl) {
    labelEl.textContent = `Row ${row}, Seat ${num} • ${typeTitle}`;
  }

  const ctaText = document.getElementById('btn-enter-theatre-text');
  if (ctaText) {
    ctaText.textContent = `ENTER THEATRE • ROW ${row}, SEAT ${num}`;
  }

  document.querySelectorAll('.seat-quick-btn').forEach(btn => {
    btn.classList.toggle('active', btn.dataset.seat === seatId);
  });
}

// =============================================================================
// YOUTUBE LINK FETCHER & CLIPBOARD AUTO-DETECTION SYSTEM
// =============================================================================
function applyPastedYouTubeLink(rawText, source = 'auto') {
  if (!rawText) return false;
  const trimmed = rawText.trim();
  const ytId = extractYouTubeId(trimmed);
  if (!ytId) {
    if (source === 'manual') {
      showToast('⚠️ No valid YouTube video link found in clipboard.', 3500);
    }
    return false;
  }

  const urlInput = document.getElementById('input-youtube-url');
  if (!urlInput) return false;

  const currentVal = urlInput.value.trim();
  if (currentVal === trimmed) {
    if (source === 'manual') {
      showToast('ℹ️ This YouTube video link is already loaded!', 2500);
    }
    return true;
  }

  urlInput.value = trimmed;
  urlInput.classList.remove('input-highlight-flash');
  void urlInput.offsetWidth; // trigger reflow for CSS flash animation
  urlInput.classList.add('input-highlight-flash');

  const titleInput = document.getElementById('input-movie-title');
  showToast('📋 YouTube link auto-filled! Fetching video title...', 2500);

  // Fetch title from YouTube public oEmbed API
  fetch(`https://www.youtube.com/oembed?url=https://www.youtube.com/watch?v=${ytId}&format=json`)
    .then(r => r.json())
    .then(data => {
      if (data && data.title) {
        if (titleInput) {
          titleInput.value = data.title;
        }
        showToast(`🎬 Loaded: "${data.title}"`, 4000);
      }
    })
    .catch(() => {
      showToast('🎬 YouTube video loaded into link field!', 2500);
    });

  const banner = document.getElementById('yt-detect-banner');
  if (banner) banner.classList.add('hide');
  state.waitingForYouTubeClipboard = false;

  return true;
}

// =============================================================================
// UI EVENT LISTENERS
// =============================================================================
function setupEventListeners() {
  window.addEventListener('resize', onWindowResize);
  window.addEventListener('pointermove', handlePointerMove);
  window.addEventListener('pointerdown', handlePointerDown);

  // "Get the YouTube Link" Button (Opens YouTube & listens for copied link)
  const btnGetYtLink = document.getElementById('btn-get-youtube-link');
  if (btnGetYtLink) {
    btnGetYtLink.addEventListener('click', () => {
      state.waitingForYouTubeClipboard = true;

      // Show listening animation banner
      const banner = document.getElementById('yt-detect-banner');
      if (banner) banner.classList.remove('hide');

      // Open YouTube in a new tab
      window.open('https://www.youtube.com', '_blank');

      showToast('🌐 Opening YouTube... Find any video, click "Share ➔ Copy Link", then switch back here!', 6000);
    });
  }

  // "Paste from Clipboard" Button
  const btnPasteClipboard = document.getElementById('btn-paste-clipboard');
  if (btnPasteClipboard) {
    btnPasteClipboard.addEventListener('click', async () => {
      if (!navigator.clipboard || !navigator.clipboard.readText) {
        showToast('⚠️ Clipboard access not supported. You can press Ctrl+V to paste into the field.', 4000);
        return;
      }

      try {
        const text = await navigator.clipboard.readText();
        const success = applyPastedYouTubeLink(text, 'manual');
        if (!success) {
          showToast('⚠️ Clipboard does not contain a YouTube link. Copy a link from YouTube first!', 4000);
        }
      } catch (err) {
        console.warn('Clipboard read error:', err);
        showToast('⚠️ Clipboard permission needed. Press Ctrl+V in the field to paste.', 4000);
      }
    });
  }

  // Automatic Clipboard Detection on Tab Focus / Window Switch
  const autoDetectClipboard = async () => {
    const lobbyModal = document.getElementById('lobby-modal');
    const isLobbyActive = lobbyModal && lobbyModal.classList.contains('active');

    // Only auto-check if user requested a link or is on the lobby screen
    if (!state.waitingForYouTubeClipboard && !isLobbyActive) return;
    if (!navigator.clipboard || !navigator.clipboard.readText) return;

    try {
      const text = await navigator.clipboard.readText();
      if (text) {
        const ytId = extractYouTubeId(text.trim());
        if (ytId) {
          applyPastedYouTubeLink(text, 'auto');
        }
      }
    } catch (err) {
      // Permission-gated background reads fail silently
    }
  };

  window.addEventListener('focus', autoDetectClipboard);
  document.addEventListener('visibilitychange', () => {
    if (document.visibilityState === 'visible') {
      autoDetectClipboard();
    }
  });

  // Concession Pack Selector in Lobby
  document.querySelectorAll('.concession-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      document.querySelectorAll('.concession-btn').forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      state.snackPack = btn.dataset.snack || 'butter';
      updateConcessionAppearance();
      showToast(`Selected Snack Pack: ${btn.textContent.trim()}`);
    });
  });

  // Local Video File Picker
  const localVideoInput = document.getElementById('input-local-video');
  if (localVideoInput) {
    localVideoInput.addEventListener('change', (e) => {
      const file = e.target.files[0];
      if (file) {
        const fileUrl = URL.createObjectURL(file);
        document.getElementById('input-youtube-url').value = fileUrl;

        const titleInput = document.getElementById('input-movie-title');
        const cleanName = file.name.replace(/\.[^/.]+$/, "");
        if (!titleInput.value || titleInput.value.includes('Interstellar')) {
          titleInput.value = cleanName;
        }

        const badge = document.getElementById('local-video-selected-badge');
        if (badge) {
          badge.textContent = `📁 Local File: ${file.name} (${(file.size / (1024 * 1024)).toFixed(1)} MB)`;
          badge.style.display = 'inline-flex';
        }

        showToast(`Loaded local trailer: ${file.name}`);
      }
    });
  }

  // Quick Preset Seat buttons
  document.querySelectorAll('.seat-quick-btn[data-seat]').forEach(btn => {
    btn.addEventListener('click', () => {
      const seatId = btn.getAttribute('data-seat');
      selectSeat(seatId, state.inTheatre);
    });
  });

  // Random Seat Generator button
  const btnRandom = document.getElementById('btn-quick-random');
  if (btnRandom) {
    btnRandom.addEventListener('click', () => {
      const rows = ['A', 'B', 'C', 'D', 'E', 'F', 'G'];
      const randomRow = rows[Math.floor(Math.random() * rows.length)];
      const randomNum = Math.floor(Math.random() * 15) + 1;
      const seatId = `${randomRow}-${String(randomNum).padStart(3, '0')}`;
      selectSeat(seatId, state.inTheatre);
    });
  }

  // Enter Theatre CTA Button
  document.getElementById('btn-enter-theatre').addEventListener('click', () => {
    enterTheatre();
  });

  // Snack Pill Click in Top HUD
  const snackPill = document.getElementById('hud-snack-pill');
  if (snackPill) {
    snackPill.addEventListener('click', () => {
      eatPopcorn();
    });
  }

  // Watch Party Modal Toggles
  const btnHudWatchParty = document.getElementById('btn-hud-watchparty');
  const watchPartyModal = document.getElementById('watch-party-modal');
  const btnCloseWatchParty = document.getElementById('btn-close-watchparty');

  if (btnHudWatchParty && watchPartyModal) {
    btnHudWatchParty.addEventListener('click', () => {
      watchPartyModal.classList.toggle('active');
      updateWatchPartyUI();
    });
  }

  if (btnCloseWatchParty && watchPartyModal) {
    btnCloseWatchParty.addEventListener('click', () => {
      watchPartyModal.classList.remove('active');
    });
  }

  // Copy Watch Party Link Button
  const btnCopyPartyLink = document.getElementById('btn-copy-party-link');
  if (btnCopyPartyLink) {
    btnCopyPartyLink.addEventListener('click', () => {
      const linkInput = document.getElementById('watch-party-link-input');
      if (linkInput) {
        linkInput.select();
        navigator.clipboard.writeText(linkInput.value).then(() => {
          showToast('📋 Watch Party invite link copied! Open in a second tab to test.');
        }).catch(() => {
          showToast('Link: ' + linkInput.value);
        });
      }
    });
  }

  // Force Sync Button in Watch Party
  const btnPartySync = document.getElementById('btn-party-sync-play');
  if (btnPartySync) {
    btnPartySync.addEventListener('click', () => {
      broadcastPartyMessage({
        type: 'SYNC_PLAY',
        movieTitle: state.movieTitle,
        videoSource: state.currentVideoSource,
      });
      showToast('🔄 Synchronized playback broadcasted to all viewers.');
    });
  }

  // Create New Room Button
  const btnPartyNewRoom = document.getElementById('btn-party-new-room');
  if (btnPartyNewRoom) {
    btnPartyNewRoom.addEventListener('click', () => {
      const newRoom = 'CINE-' + Math.floor(1000 + Math.random() * 9000);
      window.location.search = `?room=${newRoom}`;
    });
  }

  // WebXR VR Top HUD Button
  const btnHudVr = document.getElementById('btn-hud-vr');
  if (btnHudVr) {
    btnHudVr.addEventListener('click', () => {
      if (navigator.xr) {
        navigator.xr.isSessionSupported('immersive-vr').then((supported) => {
          if (supported) {
            navigator.xr.requestSession('immersive-vr', {
              optionalFeatures: ['local-floor', 'bounded-floor', 'hand-tracking']
            }).then(session => renderer.xr.setSession(session));
          } else {
            showToast('🕶️ WebXR VR requires a connected VR headset (Meta Quest, Apple Vision Pro, SteamVR).');
          }
        }).catch(() => {
          showToast('🕶️ VR headset display not detected.');
        });
      } else {
        showToast('🕶️ WebXR VR is not supported by your browser.');
      }
    });
  }

  // In-Theatre HUD Seat Map Button
  const btnHudSeatmap = document.getElementById('btn-hud-seatmap');
  const theatreSeatmapModal = document.getElementById('theatre-seatmap-modal');
  const btnCloseSeatmap = document.getElementById('btn-close-seatmap');

  if (btnHudSeatmap && theatreSeatmapModal) {
    btnHudSeatmap.addEventListener('click', () => {
      theatreSeatmapModal.classList.toggle('active');
    });
  }

  if (btnCloseSeatmap && theatreSeatmapModal) {
    btnCloseSeatmap.addEventListener('click', () => {
      theatreSeatmapModal.classList.remove('active');
    });
  }

  // Top Bar Buttons
  document.getElementById('btn-change-movie').addEventListener('click', () => {
    document.getElementById('lobby-modal').classList.add('active');
  });

  document.getElementById('btn-exit-lobby').addEventListener('click', () => {
    document.getElementById('lobby-modal').classList.add('active');
    document.getElementById('theatre-hud-top').classList.add('hide');
    document.getElementById('theatre-hud-bottom').classList.add('hide');
    state.inTheatre = false;
    moveToOverview();
  });

  // Bottom Dock: Perspectives
  document.getElementById('btn-cam-sweetspot').addEventListener('click', () => moveToSeat('D-008'));
  document.getElementById('btn-cam-vip').addEventListener('click', () => moveToSeat('G-008'));
  document.getElementById('btn-cam-front').addEventListener('click', () => moveToSeat('A-008'));
  document.getElementById('btn-cam-overview').addEventListener('click', () => moveToOverview());

  // Bottom Dock: Lighting Modes
  document.getElementById('btn-light-cinema').addEventListener('click', () => applyLightingMode('cinema'));
  document.getElementById('btn-light-house').addEventListener('click', () => applyLightingMode('house'));
  document.getElementById('btn-light-blackout').addEventListener('click', () => applyLightingMode('blackout'));

  // Bottom Dock: Screen Play/Pause
  document.getElementById('btn-toggle-video').addEventListener('click', () => {
    toggleTrailerPlayback();
  });

  // Bottom Dock: Screen Audio Mute / Unmute
  const btnToggleMute = document.getElementById('btn-toggle-mute');
  if (btnToggleMute) {
    btnToggleMute.addEventListener('click', () => {
      toggleTrailerMute();
    });
  }

  // Bottom Dock: Reload Current Trailer
  const btnReloadVideo = document.getElementById('btn-reload-video');
  if (btnReloadVideo) {
    btnReloadVideo.addEventListener('click', () => {
      reloadTrailer();
    });
  }

  // Embed Restriction Modal Action Handlers
  const btnRestrPreset = document.getElementById('btn-restriction-preset');
  if (btnRestrPreset) {
    btnRestrPreset.addEventListener('click', () => {
      hideEmbedRestrictedBanner();
      const interstellarUrl = 'https://www.youtube.com/watch?v=zSWdZVtXT7E';
      document.getElementById('input-movie-title').value = 'Interstellar • IMAX 70mm Special Presentation';
      document.getElementById('input-youtube-url').value = interstellarUrl;
      state.movieTitle = 'Interstellar • IMAX 70mm Special Presentation';
      document.getElementById('hud-movie-title').textContent = state.movieTitle;
      playTrailer(interstellarUrl, true);
    });
  }

  const btnRestrChange = document.getElementById('btn-restriction-change');
  if (btnRestrChange) {
    btnRestrChange.addEventListener('click', () => {
      hideEmbedRestrictedBanner();
      document.getElementById('lobby-modal').classList.add('active');
    });
  }

  const btnRestrDismiss = document.getElementById('btn-restriction-dismiss');
  if (btnRestrDismiss) {
    btnRestrDismiss.addEventListener('click', () => {
      hideEmbedRestrictedBanner();
    });
  }

  // Live Auto-Detection and Title Lookup for Custom YouTube Links
  const ytInput = document.getElementById('input-youtube-url');
  if (ytInput) {
    let debounceTimer = null;
    const handleUrlUpdate = () => {
      clearTimeout(debounceTimer);
      debounceTimer = setTimeout(() => {
        const val = ytInput.value.trim();
        if (!val) return;

        const parsed = parseVideoSource(val);
        if (parsed.type === 'youtube') {
          const titleInput = document.getElementById('input-movie-title');
          const isDefault = !titleInput.value ||
            titleInput.value.includes('Interstellar') ||
            titleInput.value.includes('IMAX 70mm') ||
            titleInput.value.trim() === 'Cinema Presentation';

          // Query YouTube's free, public oEmbed API to fetch real title
          fetch(`https://www.youtube.com/oembed?url=https://www.youtube.com/watch?v=${parsed.id}&format=json`)
            .then(r => r.json())
            .then(data => {
              if (data && data.title) {
                if (isDefault) {
                  titleInput.value = data.title;
                }
                showToast(`🎬 YouTube video verified: "${data.title}"`, 3500);
              }
            })
            .catch(() => {
              // Video might still be valid even if oEmbed is offline
            });
        }
      }, 400);
    };

    ytInput.addEventListener('input', handleUrlUpdate);
    ytInput.addEventListener('paste', handleUrlUpdate);
    ytInput.addEventListener('change', handleUrlUpdate);
  }

  // Bottom Dock: Ambilight Toggle
  const btnAmbilight = document.getElementById('btn-toggle-ambilight');
  if (btnAmbilight) {
    btnAmbilight.addEventListener('click', () => {
      state.ambilightEnabled = !state.ambilightEnabled;
      btnAmbilight.classList.toggle('active', state.ambilightEnabled);
      btnAmbilight.innerHTML = state.ambilightEnabled ? '✨ Ambilight' : '✨ Ambilight (Off)';
      showToast(state.ambilightEnabled ? '✨ Screen Ambilight Enabled' : 'Ambilight Disabled');
    });
  }

  // Bottom Dock: Spatial Audio Toggle
  const btnSpatial = document.getElementById('btn-toggle-spatial');
  if (btnSpatial) {
    btnSpatial.addEventListener('click', () => {
      initSpatialAudio();
      state.spatialAudioEnabled = !state.spatialAudioEnabled;
      btnSpatial.classList.toggle('active', state.spatialAudioEnabled);
      btnSpatial.innerHTML = state.spatialAudioEnabled ? '🔊 Spatial' : '🔊 Spatial (Off)';
      showToast(state.spatialAudioEnabled ? '🔊 3D Positional Audio & Dolby Atmos Sweet Spot Enabled' : 'Spatial Audio Disabled');
    });
  }

  // Prevent any click/tap on UI panels and docks from propagating into 3D scene raycasting
  const uiPanels = [
    document.getElementById('theatre-hud-bottom'),
    document.getElementById('theatre-hud-top'),
    document.getElementById('theatre-seatmap-modal'),
    document.getElementById('watch-party-modal'),
    document.getElementById('lobby-modal'),
    document.getElementById('embed-restriction-card'),
  ];
  uiPanels.forEach(panel => {
    if (panel) {
      ['pointerdown', 'mousedown', 'touchstart'].forEach(evt => {
        panel.addEventListener(evt, (e) => e.stopPropagation());
      });
    }
  });

  // Bottom Dock: 3D Floating Reaction Buttons
  document.querySelectorAll('.reaction-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      const emoji = btn.dataset.reaction;
      triggerUserReaction(emoji);
    });
  });

  // Listen to postMessage events from YouTube iframe for two-way sync
  window.addEventListener('message', (event) => {
    try {
      const data = typeof event.data === 'string' ? JSON.parse(event.data) : event.data;
      if (data && data.info && typeof data.info.playerState !== 'undefined') {
        const ps = data.info.playerState;
        if (ps === 1) {
          isVideoPlaying = true;
          updatePlayPauseButton(true);
        } else if (ps === 2) {
          isVideoPlaying = false;
          updatePlayPauseButton(false);
        } else if (ps === 0) {
          console.log('YouTube postMessage event reported ENDED. Replaying from start...');
          if (ytPlayer && typeof ytPlayer.seekTo === 'function') {
            ytPlayer.seekTo(0, true);
            ytPlayer.playVideo();
          } else if (iframeElement && iframeElement.contentWindow) {
            iframeElement.contentWindow.postMessage('{"event":"command","func":"seekTo","args":[0, true]}', '*');
            iframeElement.contentWindow.postMessage('{"event":"command","func":"playVideo","args":[]}', '*');
          }
          isVideoPlaying = true;
          updatePlayPauseButton(true);
        }
      }
    } catch (e) {}
  });

  // Center View
  document.getElementById('btn-recenter').addEventListener('click', () => {
    if (state.currentSeatId) moveToSeat(state.currentSeatId, 1.0);
    else moveToOverview();
  });
}

function enterTheatre() {
  const movieTitleInput = document.getElementById('input-movie-title').value.trim();
  const videoUrlInput = document.getElementById('input-youtube-url').value.trim();

  state.movieTitle = movieTitleInput || "Cinema Presentation";
  state.youtubeUrl = videoUrlInput;
  state.currentVideoSource = parseVideoSource(videoUrlInput);
  state.youtubeVideoId = state.currentVideoSource.id || extractYouTubeId(videoUrlInput) || "zSWdZVtXT7E";

  const initialSeat = state.currentSeatId || "D-008";
  const wasAlreadyInTheatre = state.inTheatre;

  // Hide Lobby Modal & Show HUDs
  document.getElementById('lobby-modal').classList.remove('active');
  document.getElementById('theatre-hud-top').classList.remove('hide');
  document.getElementById('theatre-hud-bottom').classList.remove('hide');
  document.getElementById('hud-movie-title').textContent = state.movieTitle;

  state.inTheatre = true;

  // Initialize Spatial Audio on user gesture
  initSpatialAudio();

  // Start Trailer Playback
  playTrailer(videoUrlInput, true);

  if (!wasAlreadyInTheatre) {
    playCinemaIntroChime();
    // Transition camera to starting seat
    setTimeout(() => {
      moveToSeat(initialSeat, 2.2);
      applyLightingMode('cinema');
    }, 300);
  } else {
    showToast(`🎬 Now Playing: ${state.movieTitle}`, 3000);
  }
}

function onWindowResize() {
  camera.aspect = window.innerWidth / window.innerHeight;
  camera.updateProjectionMatrix();

  renderer.setSize(window.innerWidth, window.innerHeight);
  cssRenderer.setSize(window.innerWidth, window.innerHeight);
}

// =============================================================================
// MAIN ANIMATION LOOP (UNIVERSAL DESKTOP & WEBXR VR)
// =============================================================================
const clock = new THREE.Clock();

function animate() {
  const delta = clock.getDelta();

  // Smooth camera interpolation
  if (camTarget.active) {
    camTarget.elapsed += delta;
    const progress = Math.min(camTarget.elapsed / camTarget.duration, 1.0);
    const t = progress < 0.5
      ? 4 * progress * progress * progress
      : 1 - Math.pow(-2 * progress + 2, 3) / 2;

    camera.position.lerpVectors(camTarget.startPos, camTarget.pos, t);
    controls.target.lerpVectors(camTarget.startLookAt, camTarget.lookAt, t);

    if (progress >= 1.0) {
      camTarget.active = false;
      controls.enabled = true;
    }
  } else if (!renderer.xr.isPresenting) {
    controls.update();
    clampCameraInsideTheatre();
  }

  // Update Feature 1: Dynamic Screen Ambilight
  updateAmbilight(delta);

  // Update Feature 3: Spatial 3D Audio Listener
  updateSpatialAudio();

  // Update Feature 2: 3D Floating Reaction Sprites
  updateFloatingReactions(delta);

  // Render both WebGL and CSS3D scenes
  cssRenderer.render(cssScene, camera);
  renderer.render(scene, camera);
}

// Launch application on DOM load
window.addEventListener('DOMContentLoaded', init);
