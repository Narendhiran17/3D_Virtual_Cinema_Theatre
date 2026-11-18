# Horizon Grand Cineplex • 3D Virtual Cinema Theatre

An interactive, photorealistic 3D virtual cinema screening room experience powered by **Three.js**, **CSS3D YouTube projection synchronization**, and an **interactive 2D auditorium seating matrix**.

---

## 🌟 Key Features

1. **Lobby Entrance & Custom Movie Trailer Setup:**
   - Input any custom **Movie Title** and **YouTube Trailer URL** (or Video ID).
   - One-click popular 4K presets: *Interstellar (IMAX 70mm)*, *Dune: Part Two*, *Avatar: The Way of Water*, *Top Gun: Maverick*, and *The Batman*.

2. **Auditorium 2D Interactive Seating Chart (105 Seats):**
   - Curved **2.39:1 CinemaScope Screen** arch orientation at the front of the matrix.
   - Rows **A through G** with 15 seats per row (Left Block 3, Center Block 9, Right Block 3, separated by aisles).
   - Categorized seat types:
     - ♿ **Row A**: Wheelchair Accessible spaces
     - ⭐ **Seat D-8**: Acoustic Sweet Spot (optimal audio/visual center)
     - 👑 **Row G**: VIP Luxury Recliners (elevated rear tier with gold highlights)
     - **Rows B, C, E, F**: Premium Burgundy Velvet cinema seats
   - Real-time gold glow selection badge and dynamic CTA update (`ENTER THEATRE • ROW X, SEAT Y`).
   - Quick seat selection buttons and Random Seat selector.

3. **3D Virtual Auditorium & YouTube CinemaScope Screen:**
   - Seamless transition into the 3D theatre with camera positioning at the exact physical seat chosen on the 2D chart.
   - Real YouTube IFrame rendered directly onto the curved 2.39:1 CinemaScope screen geometry using Three.js CSS3DRenderer synchronized with WebGL alpha blending.

4. **In-Theatre Top HUD & Floating Seat Map:**
   - Top HUD showing current movie title, active seat number, and classification.
   - **🪑 Seat Map Button**: Opens an in-theatre floating 2D seating modal to instantly switch seats and glide the camera to any perspective in real time.
   - Quick Lighting Modes: *🎬 Cinema Mode*, *💡 House Lights*, *🌑 Blackout*.
   - Screen controls: *⏯️ Play/Pause*, *🎯 Center View*.

---

## 📁 Project Directory Structure

```
3D_Virtual_Cinema_Theatre/
├── start_cinema.bat            # 1-Click launcher (starts server & opens browser)
├── package.json                # Root proxy scripts for npm run dev / build
├── README.md                   # This project guide
│
├── app/                        # Web Application (Three.js + Vite)
│   ├── index.html              # Main HTML entry with lobby modal & in-theatre HUD
│   ├── style.css               # Luxury cinema glassmorphism & 2D seating styles
│   ├── main.js                 # Three.js WebGL & CSS3D scene, camera & seat map logic
│   ├── vite.config.js          # Vite development server configuration
│   ├── package.json            # Node.js dependencies (three, vite)
│   ├── dist/                   # Production build files
│   └── assets/
│       ├── cinema_theatre_auditorium.glb  # 3D GLB model with 105 named seats
│       └── cinema_layout_metadata.json    # Exact seat 3D coordinates & metadata
│
├── blender_source/             # Blender 3D Source Files & Scripts
│   ├── cinema_theatre_auditorium.blend    # Original Blender 3D scene (10.8 MB)
│   ├── cinema_theatre_auditorium.glb      # Master exported GLTF/GLB
│   ├── cinema_layout_metadata.json        # Seat matrix coordinates metadata
│   ├── cinema_asset_manifest.json         # Asset specification manifest
│   ├── build_cinema_auditorium_photoreal.py # Blender Python procedural generator
│   ├── generate_film_still.py             # Script generating movie textures
│   └── renders/                           # High-resolution rendered stills
│       ├── render_seat_d08_view.png       # View from Row D, Seat 8 Sweet Spot
│       ├── render_screen_facing.png       # Front-facing view of the screen
│       └── render_overview.png            # High rear auditorium overview
│
└── docs/                       # Technical Specifications & Build Plans
    └── 3D_Cinema_Theatre_Build_Prompts_v1.0.md
```

---

## 🚀 How to Run

### Method 1: One-Click Launcher (Easiest)
Simply double-click `start_cinema.bat` inside this folder. It will launch the local development server and open your default web browser to [http://localhost:3000/](http://localhost:3000/).

### Method 2: Command Line (Vite)
Open a terminal in this directory and run:
```bash
npm run dev
```
Then visit **http://localhost:3000/** in your browser.

### Method 3: Run From Inside `app/` Directory
```bash
cd app
npm run dev
```

---

## 🛠️ Tech Stack
- **Three.js** (WebGL 3D Rendering & OrbitControls)
- **CSS3DRenderer** (Transforms YouTube iframe natively into 3D perspective)
- **Blender 4.2+ Python API** (Procedural architecture, tiered risers, seat matrix generation)
- **Vite** (Next-generation lightning-fast frontend tooling)
