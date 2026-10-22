"""Portable locations for the P5 engineering and shader release.

The full source ZIP places ARX-6-P5-Engineering next to this
ARX-6-P5-Shader directory. Current and legacy environment overrides
support other layouts; the P2/P3 variable names remain import-compatible.
"""
import os
from pathlib import Path
P3 = Path(os.environ.get('ARX_P5_SHADER_ROOT', os.environ.get('ARX_P3_ROOT', Path(__file__).resolve().parents[1]))).resolve()
P2 = Path(os.environ.get('ARX_P5_ENGINEERING_ROOT', os.environ.get('ARX_P2_ROOT', P3.parent / 'ARX-6-P5-Engineering'))).resolve()
