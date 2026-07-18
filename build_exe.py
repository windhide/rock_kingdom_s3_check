"""Build standalone exe with PyInstaller — includes OCR models, no downloads needed."""
from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path

import PyInstaller.__main__

HERE = Path(__file__).resolve().parent
VENV = HERE / ".venv"
SITE_PACKAGES = VENV / "Lib" / "site-packages"

# RapidOCR models (ONNX files that are normally auto-downloaded)
RAPIDOCR = SITE_PACKAGES / "rapidocr_onnxruntime"
MODELS_DIR = RAPIDOCR / "models"
MODEL_FILES = [
    "ch_PP-OCRv3_det_infer.onnx",
    "ch_PP-OCRv3_rec_infer.onnx",
    "ch_ppocr_mobile_v2.0_cls_infer.onnx",
]

# YAML configs
CONFIG_FILES = [
    "config.yaml",
    "ch_ppocr_v3_det/config.yaml",
    "ch_ppocr_v3_rec/config.yaml",
    "ch_ppocr_v2_cls/config.yaml",
]

# ONNX Runtime DLLs
ONNX_CAPI = SITE_PACKAGES / "onnxruntime" / "capi"
ONNX_DLLS = [
    "onnxruntime.dll",
    "onnxruntime_providers_shared.dll",
    "onnxruntime_pybind11_state.pyd",
]


def _datas_str(src: Path, dest_rel: str) -> str:
    """PyInstaller --add-data format: source;dest"""
    return f"{src}{os.pathsep}{dest_rel}"


def main() -> None:
    # Clean
    for d in ("build", "dist"):
        p = HERE / d
        if p.exists():
            shutil.rmtree(p)

    spec = HERE / "加尔小助手.spec"
    if spec.exists():
        spec.unlink()

    add_data: list[str] = []

    # icon
    ico = HERE / "icon.ico"
    if ico.exists():
        add_data.append(_datas_str(ico, "."))

    # RapidOCR models
    for name in MODEL_FILES:
        src = MODELS_DIR / name
        if src.exists():
            add_data.append(_datas_str(src, f"rapidocr_onnxruntime/models"))

    # RapidOCR configs
    for name in CONFIG_FILES:
        src = RAPIDOCR / name
        if src.exists():
            dest = f"rapidocr_onnxruntime/{name.replace(chr(92), '/')}"
            add_data.append(_datas_str(src, os.path.dirname(dest)))

    # ONNX Runtime DLLs
    for name in ONNX_DLLS:
        src = ONNX_CAPI / name
        if src.exists():
            add_data.append(_datas_str(src, "onnxruntime/capi"))

    # Build
    args = [
        str(HERE / "main.py"),
        "--name=加尔小助手",
        "--onefile",
        "--noconsole",
        "--clean",
    ]
    if ico.exists():
        args.extend(["--icon", str(ico)])
    for d in add_data:
        args.extend(["--add-data", d])

    # Hidden imports
    args.extend([
        "--hidden-import", "rapidocr_onnxruntime",
        "--hidden-import", "rapidocr_onnxruntime.ch_ppocr_v3_det",
        "--hidden-import", "rapidocr_onnxruntime.ch_ppocr_v3_rec",
        "--hidden-import", "rapidocr_onnxruntime.ch_ppocr_v2_cls",
        "--hidden-import", "onnxruntime",
        "--hidden-import", "onnxruntime.capi",
        "--hidden-import", "onnxruntime.capi.onnxruntime_pybind11_state",
        "--hidden-import", "PIL",
        "--hidden-import", "PIL.Image",
        "--hidden-import", "win32gui",
        "--hidden-import", "win32ui",
        "--hidden-import", "win32con",
        "--hidden-import", "ctypes.wintypes",
        "--collect-all", "rapidocr_onnxruntime",
        "--collect-all", "onnxruntime",
    ])

    print("Running PyInstaller...")
    PyInstaller.__main__.run(args)

    dist_exe = HERE / "dist" / "加尔小助手.exe"
    if dist_exe.exists():
        print(f"\nDone! Output: {dist_exe} ({dist_exe.stat().st_size // (1024*1024)}MB)")
    else:
        # PyInstaller may have appended .exe already
        alt = HERE / "dist" / "加尔小助手"
        if alt.with_suffix(".exe").exists():
            print(f"\nDone! Output: {alt.with_suffix('.exe')}")


if __name__ == "__main__":
    main()
