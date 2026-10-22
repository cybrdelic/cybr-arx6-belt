"""Resolve presentation fonts without depending on Linux font paths."""
import os
from pathlib import Path
from PIL import ImageFont

def load_font(size, bold=False, mono=False):
    names = (["DejaVuSansMono.ttf", "consola.ttf", "Menlo.ttc"] if mono else
             ["DejaVuSans-Bold.ttf", "arialbd.ttf", "Arial Bold.ttf"] if bold else
             ["DejaVuSans.ttf", "arial.ttf", "Arial.ttf"])
    roots = [Path(os.environ.get("ARX_FONT_DIR", ".")), Path(os.environ.get("WINDIR", "C:/Windows"))/"Fonts",
             Path("/usr/share/fonts/truetype/dejavu"), Path("/System/Library/Fonts/Supplemental"), Path("/System/Library/Fonts")]
    for name in names:
        for path in [Path(name)] + [root/name for root in roots]:
            try:
                return ImageFont.truetype(str(path), size)
            except OSError:
                pass
    return ImageFont.load_default(size=size)
