# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for Structura.app"""

from pathlib import Path

block_cipher = None
ROOT = Path.cwd()

a = Analysis(
    ['src/main.py'],
    pathex=[str(ROOT)],
    binaries=[],
    datas=[
        (str(ROOT / 'assets' / 'Structura.icns'), 'assets'),
    ],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['tkinter', 'unittest', 'email', 'http', 'xml',
              'pydoc', 'doctest', 'difflib'],
    noarchive=False,
    optimize=2,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='Structura',
    debug=False,
    bootloader_ignore_signals=False,
    strip=True,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    target_arch='arm64',
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=True,
    upx=False,
    name='Structura',
)

app = BUNDLE(
    coll,
    name='Structura.app',
    icon='assets/Structura.icns',
    bundle_identifier='com.github.razorbackroar.structura',
    info_plist={
        'CFBundleName': 'Structura',
        'CFBundleDisplayName': 'Structura',
        'CFBundleShortVersionString': '1.0.0',
        'CFBundleVersion': '1.0.0',
        'CFBundleGetInfoString': 'Structura 1.0.0, © 2026 RazorBackRoar',
        'NSHighResolutionCapable': True,
        'LSMinimumSystemVersion': '12.0',
        'NSHumanReadableCopyright': '© 2026 RazorBackRoar. MIT License.',
    },
)
