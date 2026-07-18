# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_all

datas = [('E:\\Code\\project\\rock_kingdom_s3_check\\check.json', '.'), ('E:\\Code\\project\\rock_kingdom_s3_check\\icon.ico', '.'), ('E:\\Code\\project\\rock_kingdom_s3_check\\.venv\\Lib\\site-packages\\rapidocr_onnxruntime\\models\\ch_PP-OCRv3_det_infer.onnx', 'rapidocr_onnxruntime/models'), ('E:\\Code\\project\\rock_kingdom_s3_check\\.venv\\Lib\\site-packages\\rapidocr_onnxruntime\\models\\ch_PP-OCRv3_rec_infer.onnx', 'rapidocr_onnxruntime/models'), ('E:\\Code\\project\\rock_kingdom_s3_check\\.venv\\Lib\\site-packages\\rapidocr_onnxruntime\\models\\ch_ppocr_mobile_v2.0_cls_infer.onnx', 'rapidocr_onnxruntime/models'), ('E:\\Code\\project\\rock_kingdom_s3_check\\.venv\\Lib\\site-packages\\rapidocr_onnxruntime\\config.yaml', 'rapidocr_onnxruntime'), ('E:\\Code\\project\\rock_kingdom_s3_check\\.venv\\Lib\\site-packages\\rapidocr_onnxruntime\\ch_ppocr_v3_det\\config.yaml', 'rapidocr_onnxruntime/ch_ppocr_v3_det'), ('E:\\Code\\project\\rock_kingdom_s3_check\\.venv\\Lib\\site-packages\\rapidocr_onnxruntime\\ch_ppocr_v3_rec\\config.yaml', 'rapidocr_onnxruntime/ch_ppocr_v3_rec'), ('E:\\Code\\project\\rock_kingdom_s3_check\\.venv\\Lib\\site-packages\\rapidocr_onnxruntime\\ch_ppocr_v2_cls\\config.yaml', 'rapidocr_onnxruntime/ch_ppocr_v2_cls'), ('E:\\Code\\project\\rock_kingdom_s3_check\\.venv\\Lib\\site-packages\\onnxruntime\\capi\\onnxruntime.dll', 'onnxruntime/capi'), ('E:\\Code\\project\\rock_kingdom_s3_check\\.venv\\Lib\\site-packages\\onnxruntime\\capi\\onnxruntime_providers_shared.dll', 'onnxruntime/capi'), ('E:\\Code\\project\\rock_kingdom_s3_check\\.venv\\Lib\\site-packages\\onnxruntime\\capi\\onnxruntime_pybind11_state.pyd', 'onnxruntime/capi')]
binaries = []
hiddenimports = ['rapidocr_onnxruntime', 'rapidocr_onnxruntime.ch_ppocr_v3_det', 'rapidocr_onnxruntime.ch_ppocr_v3_rec', 'rapidocr_onnxruntime.ch_ppocr_v2_cls', 'onnxruntime', 'onnxruntime.capi', 'onnxruntime.capi.onnxruntime_pybind11_state', 'PIL', 'PIL.Image', 'win32gui', 'win32ui', 'win32con', 'ctypes.wintypes']
tmp_ret = collect_all('rapidocr_onnxruntime')
datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]
tmp_ret = collect_all('onnxruntime')
datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]


a = Analysis(
    ['E:\\Code\\project\\rock_kingdom_s3_check\\main.py'],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='加尔小助手',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=['E:\\Code\\project\\rock_kingdom_s3_check\\icon.ico'],
)
