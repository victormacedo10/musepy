# -*- mode: python ; coding: utf-8 -*-

import os
import sys
from pathlib import Path

# Get the current directory
current_dir = Path.cwd()

# Define the main script
main_script = str(current_dir / 'app.py')

# Hidden imports for all dependencies
hidden_imports = [
    # Core PySide6 modules
    'PySide6.QtCore',
    'PySide6.QtGui', 
    'PySide6.QtWidgets',
    'PySide6.QtOpenGL',
    'PySide6.QtCharts',
    
    # Data processing
    'numpy',
    'pandas',
    'scipy',
    'scipy.sparse',
    'scipy.sparse.csgraph',
    'scipy.special',
    'scipy.linalg',
    'scipy.optimize',
    'scipy.integrate',
    'scipy.stats',
    
    # Visualization
    'matplotlib',
    'matplotlib.backends.backend_qt5agg',
    'matplotlib.backends.backend_agg',
    'matplotlib.figure',
    'matplotlib.pyplot',
    'matplotlib.patches',
    'matplotlib.collections',
    'matplotlib.text',
    'matplotlib.font_manager',
    'pyqtgraph',
    'pyqtgraph.opengl',
    
    # EEG Data Acquisition
    'brainflow',
    'brainflow.board_shim',
    'brainflow.data_filter',
    'brainflow.ml_model',
    'brainflow.utils',
    
    # Google Drive Integration (optional)
    'google.auth',
    'google.auth.transport.requests',
    'google.oauth2.credentials',
    'google_auth_oauthlib.flow',
    'googleapiclient.discovery',
    'googleapiclient.errors',
    'googleapiclient.http',
    
    # Standard library modules that might be missed
    'pickle',
    'pathlib',
    'datetime',
    'io',
    'json',
    'csv',
    'threading',
    'queue',
    'time',
    'os',
    'sys',
    'collections',
    'itertools',
    'functools',
    'typing',
]

# Data files to include
datas = [
    # Include the entire src directory
    (str(current_dir / 'src'), 'src'),
    # Include assets directory
    (str(current_dir / 'assets'), 'assets'),
    # Include google_drive directory (for configuration)
    (str(current_dir / 'google_drive'), 'google_drive'),
    # Include data directory (for default data folder)
    (str(current_dir / 'data'), 'data'),
    # Include sessions directory
    (str(current_dir / 'sessions'), 'sessions'),
]

# Binaries to include (macOS-specific)
binaries = []

# macOS-specific binary paths for BrainFlow
if os.name == 'posix' and sys.platform == 'darwin':  # macOS
    try:
        import brainflow
        brainflow_path = Path(brainflow.__file__).parent
        lib_path = brainflow_path / 'lib'
        if lib_path.exists():
            # Include all .dylib files from BrainFlow lib directory
            for dylib_file in lib_path.glob('*.dylib'):
                binaries.append((str(dylib_file), 'brainflow/lib'))
    except ImportError:
        pass

# Analysis
a = Analysis(
    [main_script],
    pathex=[str(current_dir)],
    binaries=binaries,
    datas=datas,
    hiddenimports=hidden_imports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        # Exclude unnecessary modules to reduce size
        'tkinter',
        'unittest',
        'test',
        'tests',
        'pytest',
        'IPython',
        'jupyter',
        'notebook',
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=None,
    noarchive=False,
)

# Remove duplicate entries
a.datas = list(set(a.datas))
a.binaries = list(set(a.binaries))
a.hiddenimports = list(set(a.hiddenimports))

# PYZ
pyz = PYZ(a.pure, a.zipped_data, cipher=None)

# Executable
exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='MusePy',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,  # Set to True for debugging
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=str(current_dir / 'assets' / 'gd_logo.png') if (current_dir / 'assets' / 'gd_logo.png').exists() else None,
)

# Distribution
coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='MusePy_Mac'
)
