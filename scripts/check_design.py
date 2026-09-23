"""Guard the dashboard's default light, plain GridSim design."""
from pathlib import Path
import re
import sys
import colorsys

ROOT = Path(__file__).resolve().parents[1]
css = (ROOT / 'frontend/src/style.css').read_text(encoding='utf-8')
source_files = [path for path in (list((ROOT / 'frontend/src').rglob('*.ts')) + list((ROOT / 'frontend/src').rglob('*.tsx'))) if not path.name.endswith(('.test.ts', '.spec.ts'))]
source = '\n'.join(path.read_text(encoding='utf-8') for path in source_files)
errors: list[str] = []

def luminance(hex_color: str) -> float:
    values = [int(hex_color[i:i + 2], 16) / 255 for i in (1, 3, 5)]
    linear = [v / 12.92 if v <= .04045 else ((v + .055) / 1.055) ** 2.4 for v in values]
    return .2126 * linear[0] + .7152 * linear[1] + .0722 * linear[2]

for token in ('--bg', '--surface'):
    match = re.search(rf'{token}:\s*(#[0-9A-Fa-f]{{6}})', css)
    if not match or luminance(match.group(1)) < .75:
        errors.append(f'{token} must be a light surface (luminance >= .75)')
for pattern, label in ((r'box-shadow\s*:', 'box-shadow'), (r'text-shadow\s*:', 'text-shadow'), (r'filter\s*:\s*[^;]*drop-shadow', 'drop-shadow'), (r'@keyframes', 'animation keyframes')):
    if re.search(pattern, css, re.I):
        errors.append(f'forbidden styling found: {label}')
for color in re.findall(r'#[0-9a-fA-F]{6}', css):
    red, green, blue = (int(color[i:i + 2], 16) / 255 for i in (1, 3, 5))
    _, lightness, saturation = colorsys.rgb_to_hls(red, green, blue)
    if saturation > .9 and lightness < .75:
        errors.append(f'neon-style color found: {color}')
if re.search(r'https?://[^\s"\']+\.(?:png|jpg|jpeg|webp)(?:\?[^"\']*)?', source, re.I):
    errors.append('GridSim view must not contain external raster tile URLs')
if re.search(r'react-map-gl|maplibre-gl|leaflet|<Marker\b|L\.marker|marker-icon', source, re.I):
    errors.append('default map-library markers or tile map imports are forbidden in GridSim')
if 'assertNoGridTiles' not in source or 'GridSim cannot use basemap tiles' not in (ROOT / 'frontend/src/lib/mapMode.ts').read_text(encoding='utf-8'):
    errors.append('GridSim startup tile-source guard is missing')
if errors:
    print('\n'.join(errors), file=sys.stderr)
    raise SystemExit(1)
print('design checks passed')
