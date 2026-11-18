"""Generate an ultra-high-definition, photorealistic 2.39:1 CinemaScope film frame
to be projected on the screen in the cinema auditorium scene.
"""

import math
from pathlib import Path
import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

OUTPUT_PATH = Path("output/cinema_screen_film_still.png")
OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)

WIDTH = 3840
HEIGHT = 1608  # exact 2.39:1 CinemaScope aspect ratio

# Create base HDR image array in float32
y_indices, x_indices = np.indices((HEIGHT, WIDTH))
x_norm = x_indices / WIDTH
y_norm = y_indices / HEIGHT

# Cosmic deep space / nebula background gradient
# Deep midnight navy -> galactic cyan -> warm stellar gold horizon
bg_r = 0.02 + 0.08 * (1.0 - y_norm)**2 + 0.15 * np.exp(-((x_norm - 0.45)**2 + (y_norm - 0.55)**2) / 0.12)
bg_g = 0.04 + 0.14 * (1.0 - y_norm)**1.8 + 0.25 * np.exp(-((x_norm - 0.48)**2 + (y_norm - 0.50)**2) / 0.10)
bg_b = 0.10 + 0.35 * (1.0 - y_norm)**1.5 + 0.45 * np.exp(-((x_norm - 0.52)**2 + (y_norm - 0.45)**2) / 0.15)

# Alien ringed planet on the left
planet_cx = int(0.28 * WIDTH)
planet_cy = int(0.48 * HEIGHT)
planet_r = int(0.24 * HEIGHT)

dist_sq = (x_indices - planet_cx)**2 + (y_indices - planet_cy)**2
planet_mask = dist_sq <= planet_r**2

# Planet shading (spherical lighting from upper-right sun)
nx = (x_indices - planet_cx) / planet_r
ny = (y_indices - planet_cy) / planet_r
nz_sq = 1.0 - nx**2 - ny**2
nz = np.sqrt(np.maximum(0.0, nz_sq))

# Light direction vector (from top right, slightly forward)
lx, ly, lz = 0.6, -0.4, 0.7
light_len = math.sqrt(lx**2 + ly**2 + lz**2)
lx, ly, lz = lx / light_len, ly / light_len, lz / light_len

dot = nx * lx + ny * ly + nz * lz
diffuse = np.maximum(0.0, dot)
atmosphere_rim = np.maximum(0.0, 1.0 - nz)**3 * 1.5

# Apply planet texture & shading
planet_tex_r = 0.75 * diffuse + 0.3 * atmosphere_rim
planet_tex_g = 0.45 * diffuse + 0.6 * atmosphere_rim
planet_tex_b = 0.25 * diffuse + 0.9 * atmosphere_rim

bg_r[planet_mask] = planet_tex_r[planet_mask]
bg_g[planet_mask] = planet_tex_g[planet_mask]
bg_b[planet_mask] = planet_tex_b[planet_mask]

# Brilliant eclipsing star / anamorphic lens flare at (0.68, 0.42)
flare_cx = int(0.68 * WIDTH)
flare_cy = int(0.42 * HEIGHT)

# Radial flare core
flare_dist_sq = (x_indices - flare_cx)**2 + (y_indices - flare_cy)**2
flare_radial = np.exp(-flare_dist_sq / (2.0 * (0.04 * HEIGHT)**2)) * 2.5
flare_glow = np.exp(-flare_dist_sq / (2.0 * (0.25 * HEIGHT)**2)) * 0.8

# Horizontal anamorphic blue/cyan lens flare streak
anamorphic_streak = np.exp(-((y_indices - flare_cy)**2) / (2.0 * (0.008 * HEIGHT)**2)) * np.exp(-((x_indices - flare_cx)**2) / (2.0 * (0.45 * WIDTH)**2)) * 1.8

bg_r += flare_radial * 1.0 + flare_glow * 0.95 + anamorphic_streak * 0.3
bg_g += flare_radial * 0.92 + flare_glow * 0.75 + anamorphic_streak * 0.65
bg_b += flare_radial * 0.78 + flare_glow * 0.55 + anamorphic_streak * 1.1

# Atmospheric planetary horizon / mountain silhouettes at bottom
mountain_y = HEIGHT * 0.78 + np.sin(x_norm * 18.0) * 25.0 + np.sin(x_norm * 45.0) * 12.0
mountain_mask = y_indices >= mountain_y

mountain_fog = np.exp(-((y_indices - HEIGHT * 0.75)**2) / (2.0 * (0.05 * HEIGHT)**2)) * 0.4
bg_r += mountain_fog * 0.6
bg_g += mountain_fog * 0.4
bg_b += mountain_fog * 0.7

bg_r[mountain_mask] = 0.02 + 0.03 * (y_norm[mountain_mask] - 0.78)
bg_g[mountain_mask] = 0.02 + 0.03 * (y_norm[mountain_mask] - 0.78)
bg_b[mountain_mask] = 0.03 + 0.04 * (y_norm[mountain_mask] - 0.78)

# Convert to 8-bit RGB with tonemapping
r_tonemapped = 1.0 - np.exp(-bg_r * 1.2)
g_tonemapped = 1.0 - np.exp(-bg_g * 1.2)
b_tonemapped = 1.0 - np.exp(-bg_b * 1.2)

rgb_array = np.dstack([
    np.clip(r_tonemapped * 255.0, 0, 255).astype(np.uint8),
    np.clip(g_tonemapped * 255.0, 0, 255).astype(np.uint8),
    np.clip(b_tonemapped * 255.0, 0, 255).astype(np.uint8)
])

img = Image.fromarray(rgb_array, mode="RGB")
draw = ImageDraw.Draw(img)

# Cinematic title text watermark in lower center
try:
    font_large = ImageFont.truetype("arial.ttf", 64)
    font_sub = ImageFont.truetype("arial.ttf", 28)
except Exception:
    font_large = ImageFont.load_default()
    font_sub = ImageFont.load_default()

title = "H O R I Z O N :   B E Y O N D   T H E   S T A R S"
subtitle = "EXPERIENCE IT IN CINEMASCOPE 2.39:1 • DOLBY ATMOS 64-CHANNEL REFERENCE AUDIO"

# Draw title with soft shadow
draw.text((WIDTH / 2.0 + 2, HEIGHT * 0.88 + 2), title, fill=(10, 15, 25), font=font_large, anchor="mm")
draw.text((WIDTH / 2.0, HEIGHT * 0.88), title, fill=(240, 245, 255), font=font_large, anchor="mm")

draw.text((WIDTH / 2.0 + 1, HEIGHT * 0.93 + 1), subtitle, fill=(10, 15, 25), font=font_sub, anchor="mm")
draw.text((WIDTH / 2.0, HEIGHT * 0.93), subtitle, fill=(180, 200, 230), font=font_sub, anchor="mm")

# Subtle scope crosshair alignment markers at screen corners
corner_len = 60
pad = 40
c_col = (120, 160, 220, 180)
# Top-left
draw.line([(pad, pad), (pad + corner_len, pad)], fill=c_col, width=3)
draw.line([(pad, pad), (pad, pad + corner_len)], fill=c_col, width=3)
# Top-right
draw.line([(WIDTH - pad, pad), (WIDTH - pad - corner_len, pad)], fill=c_col, width=3)
draw.line([(WIDTH - pad, pad), (WIDTH - pad, pad + corner_len)], fill=c_col, width=3)
# Bottom-left
draw.line([(pad, HEIGHT - pad), (pad + corner_len, HEIGHT - pad)], fill=c_col, width=3)
draw.line([(pad, HEIGHT - pad), (pad, HEIGHT - pad - corner_len)], fill=c_col, width=3)
# Bottom-right
draw.line([(WIDTH - pad, HEIGHT - pad), (WIDTH - pad - corner_len, HEIGHT - pad)], fill=c_col, width=3)
draw.line([(WIDTH - pad, HEIGHT - pad), (WIDTH - pad, HEIGHT - pad - corner_len)], fill=c_col, width=3)

img.save(OUTPUT_PATH, quality=95)
print(f"Generated film still image: {OUTPUT_PATH} ({OUTPUT_PATH.stat().st_size:,} bytes)")
