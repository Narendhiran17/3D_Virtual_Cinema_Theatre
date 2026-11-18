import * as THREE from 'three';
import { OrbitControls } from 'three/examples/jsm/controls/OrbitControls.js';
import { GLTFLoader } from 'three/examples/jsm/loaders/GLTFLoader.js';
import { DRACOLoader } from 'three/examples/jsm/loaders/DRACOLoader.js';
import { CSS3DRenderer, CSS3DObject } from 'three/examples/jsm/renderers/CSS3DRenderer.js';

// =============================================================================
// STATE & CONFIGURATION
// =============================================================================
const BACKEND_URL = (import.meta.env.VITE_BACKEND_URL || '').replace(/\/$/, '');

const state = {
  movieTitle: import.meta.env.VITE_DEFAULT_MOVIE_TITLE || "Interstellar • IMAX 70mm Special Presentation",
  youtubeUrl: import.meta.env.VITE_DEFAULT_YOUTUBE_URL || "https://www.youtube.com/watch?v=zSWdZVtXT7E",
  youtubeVideoId: import.meta.env.VITE_DEFAULT_YOUTUBE_VIDEO_ID || "zSWdZVtXT7E",
  currentSeatId: import.meta.env.VITE_DEFAULT_SEAT_ID || "D-008",
  lightingMode: "cinema", // 'cinema' | 'house' | 'blackout'
  inTheatre: false,
  isOrbitMode: false,
};

let scene, cssScene, camera, renderer, cssRenderer, controls;
let screenMesh = null;
let cssScreenObj = null;
let iframeElement = null;
let auditoriumModel = null;
let layoutMetadata = null;
const seatMeshMap = new Map(); // seat_id -> THREE.Object3D
const allLights = [];

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

// Raycasting for interactive seat picking
const raycaster = new THREE.Raycaster();
const mouse = new THREE.Vector2();
let hoveredSeat = null;
let originalMaterialMap = new Map();

// Highlighting material for hovered/selected seat
const highlightMaterial = new THREE.MeshStandardMaterial({
  color: 0xffcc33,
  roughness: 0.3,
  metalness: 0.2,
  emissive: 0xaa7700,
  emissiveIntensity: 0.4,
});

// =============================================================================
// YOUTUBE VIDEO ID EXTRACTION
// =============================================================================
function extractYouTubeId(urlOrId) {
  if (!urlOrId) return "zSWdZVtXT7E";
  const trimmed = urlOrId.trim();

  // If already an 11-char ID
  if (/^[a-zA-Z0-9_-]{11}$/.test(trimmed)) {
    return trimmed;
  }

  // Handle standard youtube URLs, youtu.be, embed, shorts
  const patterns = [
    /(?:youtu\.be\/|youtube\.com\/(?:embed\/|v\/|watch\?v=|watch\?.+&v=|shorts\/))([\w-]{11})/,
    /[?&]v=([^&#]+)/,
  ];

  for (const regex of patterns) {
    const match = trimmed.match(regex);
    if (match && match[1]) {
      return match[1];
    }
  }
  return trimmed;
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

  // 2. Camera
  camera = new THREE.PerspectiveCamera(60, window.innerWidth / window.innerHeight, 0.1, 200);
  camera.position.set(0, 6.8, -13.5); // Start at high rear overview
  camera.lookAt(0, 3.8, 2.3);

  // 3. WebGL Renderer
  renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true, powerPreference: 'high-performance' });
  renderer.setSize(window.innerWidth, window.innerHeight);
  renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
  renderer.toneMapping = THREE.ACESFilmicToneMapping;
  renderer.toneMappingExposure = 1.05;
  renderer.shadowMap.enabled = true;
  renderer.shadowMap.type = THREE.PCFSoftShadowMap;
  webglContainer.appendChild(renderer.domElement);

  // 4. CSS3D Renderer (mounts HTML iframe directly in 3D space)
  cssRenderer = new CSS3DRenderer();
  cssRenderer.setSize(window.innerWidth, window.innerHeight);
  cssRenderer.domElement.style.position = 'absolute';
  cssRenderer.domElement.style.top = '0';
  cssRenderer.domElement.style.left = '0';
  css3dContainer.appendChild(cssRenderer.domElement);

  // 5. OrbitControls
  controls = new OrbitControls(camera, renderer.domElement);
  controls.enableDamping = true;
  controls.dampingFactor = 0.05;
  controls.maxPolarAngle = Math.PI / 2 + 0.05; // Prevent flipping below floor
  controls.minDistance = 1.0;
  controls.maxDistance = 35.0;

  // 6. Lighting Setup
  setupAuditoriumLights();

  // 7. Render 2D Interactive Seating Maps
  render2DSeatMap('lobby-seat-map', false);
  render2DSeatMap('in-theatre-seat-map', true);
  selectSeat('D-008', false);

  // 8. Load Metadata & 3D GLB Model
  loadMetadataAndAuditorium();

  // 9. Event Listeners
  setupEventListeners();

  // 10. Start Render Loop
  requestAnimationFrame(animate);
}

// =============================================================================
// AUDITORIUM LIGHTING
// =============================================================================
function setupAuditoriumLights() {
  // Ambient fill
  const ambientLight = new THREE.AmbientLight(0x181a24, 0.5);
  scene.add(ambientLight);
  allLights.push({ light: ambientLight, baseIntensity: 0.5 });

  // Screen Projector Bounce Light (illuminates front auditorium with movie glow)
  const screenBounceLight = new THREE.PointLight(0x7ea8f8, 35, 18, 1.2);
  screenBounceLight.position.set(0, 4.0, 1.5);
  scene.add(screenBounceLight);
  allLights.push({ light: screenBounceLight, baseIntensity: 35, type: 'screen' });

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
      if (type === 'house') light.intensity = baseIntensity * 0.15; // Dim warm cove
      else if (type === 'step') light.intensity = baseIntensity * 0.8; // Warm steps
      else if (type === 'screen') light.intensity = baseIntensity * 1.0; // Movie bounce
      else light.intensity = baseIntensity * 0.4;
    } else if (mode === 'house') {
      light.intensity = baseIntensity * 1.2; // Full architectural lights
    } else if (mode === 'blackout') {
      if (type === 'screen') light.intensity = baseIntensity * 0.6;
      else if (type === 'step') light.intensity = baseIntensity * 0.2;
      else light.intensity = 0.0;
    }
  });

  // Update HUD active button
  document.querySelectorAll('#theatre-hud-bottom .hud-dock-group:nth-child(3) .dock-btn').forEach(btn => {
    btn.classList.toggle('active', btn.id.includes(mode));
  });
}

// =============================================================================
// ASSET LOADING: METADATA & 3D GLB
// =============================================================================
async function loadMetadataAndAuditorium() {
  const progressBar = document.getElementById('loader-progress-fill');

  try {
    // 1. Connect to backend if configured
    if (BACKEND_URL) {
      try {
        const backendHealth = await fetch(`${BACKEND_URL}/health/live`).then(r => r.json()).catch(() => null);
        if (backendHealth) {
          console.log('[Cinema Backend] Connected to Render API:', backendHealth);
        }
      } catch (err) {
        console.warn('[Cinema Backend] Offline, using local fallback:', err);
      }
    }

    // 2. Fetch normalized seat layout metadata
    const metaRes = await fetch('./assets/cinema_layout_metadata.json');
    layoutMetadata = await metaRes.json();
    progressBar.style.width = '35%';

    // 2. Setup GLTFLoader with DRACOLoader
    const dracoLoader = new DRACOLoader();
    dracoLoader.setDecoderPath('./draco/');

    const gltfLoader = new GLTFLoader();
    gltfLoader.setDRACOLoader(dracoLoader);

    gltfLoader.load(
      './assets/cinema_theatre_auditorium.glb',
      (gltf) => {
        auditoriumModel = gltf.scene;
        progressBar.style.width = '80%';

        // Process model hierarchy and materials
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
                blending: THREE.NoBlending, // Punches through WebGL canvas
              });
            }

            // Identify seat meshes for picking
            if (child.name.startsWith('SEAT_')) {
              // Extract row and seat number
              // e.g. "SEAT_D_008_Cushion" or "SEAT_D_008"
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

        // Setup CSS3D YouTube Screen Plane
        setupCSS3DScreen();

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
// CSS3D YOUTUBE SCREEN SETUP
// =============================================================================
function setupCSS3DScreen() {
  if (!screenMesh) {
    console.warn('Screen mesh SCREEN_MAIN not found in 3D model.');
    return;
  }

  // Calculate screen position and bounding dimensions in Three.js world coordinates
  const screenBox = new THREE.Box3().setFromObject(screenMesh);
  const size = new THREE.Vector3();
  screenBox.getSize(size);

  const screenWidth = size.x || 13.5;
  const screenHeight = size.y || 5.65;

  const worldPos = new THREE.Vector3();
  screenMesh.getWorldPosition(worldPos);

  const worldQuat = new THREE.Quaternion();
  screenMesh.getWorldQuaternion(worldQuat);

  // IFrame native resolution: 1920 x 803 (exact 2.39:1 CinemaScope aspect ratio)
  const iframeW = 1920;
  const iframeH = Math.round(iframeW / 2.39); // ~803px

  // Create YouTube IFrame
  const iframe = document.createElement('iframe');
  iframe.id = 'theatre-youtube-player';
  iframe.style.width = `${iframeW}px`;
  iframe.style.height = `${iframeH}px`;
  iframe.style.border = '0';
  iframe.style.backgroundColor = '#000';
  iframe.allow = 'accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture; web-share';
  iframe.allowFullscreen = true;

  iframeElement = iframe;
  updateYouTubeIFrameSrc(state.youtubeVideoId, false);

  // Wrap in CSS3DObject
  cssScreenObj = new CSS3DObject(iframe);
  cssScreenObj.position.set(0, 3.95, 2.29);
  cssScreenObj.rotation.set(0, Math.PI, 0);

  // Scale: matches 1920px to physical screen width (13.5m)
  const scale = screenWidth / iframeW;
  cssScreenObj.scale.set(scale, scale, scale);

  cssScene.add(cssScreenObj);
  console.log('CSS3D YouTube Screen initialized at:', cssScreenObj.position, 'Scale:', scale);
}

function updateYouTubeIFrameSrc(videoId, autoplay = true) {
  if (!iframeElement) return;
  const autoplayParam = autoplay ? '1' : '0';
  iframeElement.src = `https://www.youtube.com/embed/${videoId}?autoplay=${autoplayParam}&enablejsapi=1&rel=0&modestbranding=1&controls=1&playsinline=1&fs=1`;
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

  // Convert Blender coordinates [X, Y, Z] to Three.js coordinates [X, Z, -Y]
  // Blender: Z is up, -Y is forward (towards screen)
  // Three.js: Y is up, +Z is forward towards screen at +2.3m, -Z is rear seating
  const [bx, by, bz] = seatData.eye_point;
  const targetX = bx;
  const targetY = bz;
  const targetZ = -by; // Blender +Y maps to Three.js -Z

  // Aim at screen center
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

  // Update HUD info
  const seatTypeLabel = seatData.seat_type === 'VIP_RECLINER' ? '👑 VIP Luxury Recliner' :
                        (seatData.seat_type === 'ACCESSIBLE' ? '♿ Wheelchair Space' : '⭐ Standard');
  document.getElementById('hud-seat-info').textContent = `Row ${seatData.row_label}, Seat ${seatData.seat_number} (${seatTypeLabel})`;

  // Update Bottom Dock Active state
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
  camTarget.pos.set(0, 6.8, -13.5);
  camTarget.lookAt.set(0, 3.8, 2.3);
  camTarget.duration = 1.8;
  camTarget.elapsed = 0;
  camTarget.active = true;
  controls.enabled = false;

  document.getElementById('hud-seat-info').textContent = '🌐 Orbit Perspective (Free Camera)';
  document.querySelectorAll('#theatre-hud-bottom .dock-buttons:first-child .dock-btn').forEach(btn => {
    btn.classList.toggle('active', btn.id === 'btn-cam-overview');
  });
}

// =============================================================================
// SEAT INTERACTION: RAYCASTING & HOVER
// =============================================================================
function handlePointerMove(event) {
  if (!state.inTheatre) return;

  mouse.x = (event.clientX / window.innerWidth) * 2 - 1;
  mouse.y = -(event.clientY / window.innerHeight) * 2 + 1;

  raycaster.setFromCamera(mouse, camera);

  if (!auditoriumModel) return;

  const intersects = raycaster.intersectObjects(auditoriumModel.children, true);
  const tooltip = document.getElementById('seat-tooltip');

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
    if (hoveredSeat !== foundSeat.object) {
      // Restore previous
      if (hoveredSeat && originalMaterialMap.has(hoveredSeat)) {
        hoveredSeat.material = originalMaterialMap.get(hoveredSeat);
      }
      // Apply highlight
      hoveredSeat = foundSeat.object;
      if (!originalMaterialMap.has(hoveredSeat)) {
        originalMaterialMap.set(hoveredSeat, hoveredSeat.material);
      }
      hoveredSeat.material = highlightMaterial;
    }

    // Update Tooltip
    const seatData = layoutMetadata?.seats?.find(s => s.seat_id === foundSeat.seatId);
    tooltip.querySelector('.tooltip-id').textContent = `Seat ${foundSeat.seatId}`;
    tooltip.querySelector('.tooltip-type').textContent = seatData ? `${seatData.seat_type}` : 'Cinema Seat';
    tooltip.style.left = `${event.clientX}px`;
    tooltip.style.top = `${event.clientY}px`;
    tooltip.classList.remove('hide');
  } else {
    if (hoveredSeat && originalMaterialMap.has(hoveredSeat)) {
      hoveredSeat.material = originalMaterialMap.get(hoveredSeat);
      hoveredSeat = null;
    }
    tooltip.classList.add('hide');
  }
}

function handlePointerDown(event) {
  if (!state.inTheatre) return;

  mouse.x = (event.clientX / window.innerWidth) * 2 - 1;
  mouse.y = -(event.clientY / window.innerHeight) * 2 + 1;

  raycaster.setFromCamera(mouse, camera);
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
  }

  seatEl.title = `Row ${rowLetter}, Seat ${num} (${getSeatTypeTitle(seatId, seatType)})`;

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

  // If in-theatre, glide camera immediately
  if (triggerCameraMove && state.inTheatre) {
    moveToSeat(seatId, 1.4);
    // Auto-close floating seat map after selection
    const inTheatreModal = document.getElementById('theatre-seatmap-modal');
    if (inTheatreModal) inTheatreModal.classList.remove('active');
  }
}

function sync2DSeatMapSelection(seatId) {
  // Update all 2D seat elements across lobby and in-theatre modals
  document.querySelectorAll('.seat-cell').forEach(el => {
    el.classList.toggle('selected', el.dataset.seatId === seatId);
  });

  // Parse row and number
  const [row, numStr] = seatId.split('-');
  const num = parseInt(numStr, 10);
  let typeTitle = 'Standard Velvet';
  if (seatId === 'D-008') typeTitle = 'Acoustic Sweet Spot';
  else if (row === 'G') typeTitle = 'VIP Luxury Recliner';
  else if (row === 'A') typeTitle = 'Wheelchair Accessible';

  // Update lobby selected seat label
  const labelEl = document.getElementById('lobby-selected-seat-text');
  if (labelEl) {
    labelEl.textContent = `Row ${row}, Seat ${num} • ${typeTitle}`;
  }

  // Update CTA button text
  const ctaText = document.getElementById('btn-enter-theatre-text');
  if (ctaText) {
    ctaText.textContent = `ENTER THEATRE • ROW ${row}, SEAT ${num}`;
  }

  // Update quick preset chips active state
  document.querySelectorAll('.seat-quick-btn').forEach(btn => {
    btn.classList.toggle('active', btn.dataset.seat === seatId);
  });
}

// =============================================================================
// UI EVENT LISTENERS
// =============================================================================
function setupEventListeners() {
  window.addEventListener('resize', onWindowResize);
  window.addEventListener('pointermove', handlePointerMove);
  window.addEventListener('pointerdown', handlePointerDown);

  // Preset Buttons in Lobby
  const presetBtns = document.querySelectorAll('.preset-btn');
  presetBtns.forEach(btn => {
    btn.addEventListener('click', () => {
      presetBtns.forEach(b => b.classList.remove('active'));
      btn.classList.add('active');

      const title = btn.getAttribute('data-title');
      const url = btn.getAttribute('data-url');
      document.getElementById('input-movie-title').value = title;
      document.getElementById('input-youtube-url').value = url;
    });
  });

  // Quick Preset Seat buttons (D-8, G-8, A-8)
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
    if (iframeElement) {
      // Post message to YouTube Iframe API
      iframeElement.contentWindow.postMessage('{"event":"command","func":"pauseVideo","args":""}', '*');
    }
  });

  // Center View
  document.getElementById('btn-recenter').addEventListener('click', () => {
    if (state.currentSeatId) moveToSeat(state.currentSeatId, 1.0);
    else moveToOverview();
  });
}

function enterTheatre() {
  const movieTitleInput = document.getElementById('input-movie-title').value.trim();
  const youtubeUrlInput = document.getElementById('input-youtube-url').value.trim();

  state.movieTitle = movieTitleInput || "Cinema Presentation";
  state.youtubeUrl = youtubeUrlInput;
  state.youtubeVideoId = extractYouTubeId(youtubeUrlInput);

  const initialSeat = state.currentSeatId || "D-008";

  // Hide Lobby Modal & Show HUDs
  document.getElementById('lobby-modal').classList.remove('active');
  document.getElementById('theatre-hud-top').classList.remove('hide');
  document.getElementById('theatre-hud-bottom').classList.remove('hide');
  document.getElementById('hud-movie-title').textContent = state.movieTitle;

  state.inTheatre = true;

  // Start YouTube Trailer
  updateYouTubeIFrameSrc(state.youtubeVideoId, true);

  // Transition camera to starting seat
  setTimeout(() => {
    moveToSeat(initialSeat, 2.2);
    applyLightingMode('cinema');
  }, 300);
}

function onWindowResize() {
  camera.aspect = window.innerWidth / window.innerHeight;
  camera.updateProjectionMatrix();

  renderer.setSize(window.innerWidth, window.innerHeight);
  cssRenderer.setSize(window.innerWidth, window.innerHeight);
}

// =============================================================================
// MAIN ANIMATION LOOP
// =============================================================================
const clock = new THREE.Clock();

function animate() {
  requestAnimationFrame(animate);

  const delta = clock.getDelta();

  // Smooth camera interpolation
  if (camTarget.active) {
    camTarget.elapsed += delta;
    const progress = Math.min(camTarget.elapsed / camTarget.duration, 1.0);
    // Smooth easeInOutCubic curve
    const t = progress < 0.5
      ? 4 * progress * progress * progress
      : 1 - Math.pow(-2 * progress + 2, 3) / 2;

    camera.position.lerpVectors(camTarget.startPos, camTarget.pos, t);
    controls.target.lerpVectors(camTarget.startLookAt, camTarget.lookAt, t);

    if (progress >= 1.0) {
      camTarget.active = false;
      controls.enabled = true;
    }
  } else {
    controls.update();
  }

  // Render both WebGL and CSS3D scenes
  cssRenderer.render(cssScene, camera);
  renderer.render(scene, camera);
}

// Launch application on DOM load
window.addEventListener('DOMContentLoaded', init);
