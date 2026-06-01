# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_data_files, collect_submodules, collect_dynamic_libs

block_cipher = None

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=collect_dynamic_libs('pygame') + collect_dynamic_libs('PIL'),
    datas=[
        ('assets', 'assets'),
    ],
    hiddenimports=(
        collect_submodules('pygame') +
        collect_submodules('PIL') +
        collect_submodules('pkg_resources') +
        collect_submodules('numpy') +
        ['PIL', 'PIL.Image', 'PIL.ImageDraw', 'PIL.ImageFont',
         'PIL.ImageFilter', 'PIL.ImageOps', 'PIL._imaging',
         'numpy', 'numpy.core', 'numpy.core._multiarray_umath',
         'email', 'email.mime', 'email.mime.text',
         'html', 'http', 'http.client',
         'xml', 'xml.etree', 'xml.etree.ElementTree',
         'logging', 'logging.handlers',
         'importlib', 'importlib.metadata',
         'pkg_resources', 'pkg_resources.extern',
         'ctypes', 'ctypes.util']
    ),
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['tkinter'],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='CardKnight',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='CardKnight',
)
