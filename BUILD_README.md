# MusePy Executable Build Guide

This guide explains how to create standalone executables for MusePy using PyInstaller.

## Prerequisites

1. **Python Environment**: Ensure you have Python 3.8+ installed
2. **Dependencies**: Install all required packages from `requirements.txt`
3. **PyInstaller**: Will be automatically installed if not present

## Quick Build

Run the automated build script:

```bash
python build_executable.py
```

This script will:
- Check and install PyInstaller if needed
- Clean previous build artifacts
- Ask you to select the target platform
- Build the executable
- Show build results and file locations

## Manual Build

### Windows

```bash
# Install PyInstaller (if not already installed)
pip install pyinstaller

# Build using the Windows spec file
pyinstaller --clean musepy_windows.spec
```

### Mac

```bash
# Install PyInstaller (if not already installed)
pip install pyinstaller

# Build using the Mac spec file
pyinstaller --clean musepy_mac.spec
```

## Build Output

The build process creates:

- **`dist/MusePy_Windows/`** (Windows) or **`dist/MusePy_Mac/`** (Mac) - Contains the executable and all dependencies
- **`build/`** - Build cache (can be deleted after successful build)

## Executable Features

### Default Scripts
- **Data Processing**: Uses `experiments/neuro_v1/processing.py` by default
- **Data Visualization**: Uses `experiments/neuro_v1/visualization.py` by default
- **No Python Required**: Default scripts work without external Python installation

### External Script Support
- **Python Detection**: Automatically detects if Python is available on the target system
- **Conditional Loading**: External script loading is disabled if Python is not available
- **Fallback**: Always falls back to default scripts when external scripts can't be loaded

### Included Data
- **Experiments Folder**: Contains all processing and visualization scripts
- **Data Folder**: Empty folder for user recordings
- **Sessions Folder**: Empty folder for saved sessions
- **Documentation**: README.md and LICENSE included

## Distribution

### Windows
1. Zip the entire `dist/MusePy_Windows/` folder
2. Distribute the zip file
3. Users extract and run `MusePy.exe`

### Mac
1. Zip the entire `dist/MusePy_Mac/` folder
2. Distribute the zip file
3. Users extract and run `MusePy`

## Troubleshooting

### Build Fails
1. Ensure all dependencies are installed: `pip install -r requirements.txt`
2. Check that PyInstaller is installed: `pip install pyinstaller`
3. Try building with console enabled (edit .spec file: `console=True`)

### Executable Doesn't Start
1. Check if all required DLLs/libraries are included
2. Run from command line to see error messages
3. Ensure target system has required system libraries

### External Scripts Don't Work
1. Check if Python is installed on target system
2. Verify script paths are correct
3. Default scripts should always work regardless of Python availability

## File Structure

```
dist/
├── MusePy_Windows/          # Windows executable
│   ├── MusePy.exe          # Main executable
│   ├── experiments/        # Processing/visualization scripts
│   ├── data/              # User data folder
│   ├── sessions/          # Session storage
│   └── [dependencies]     # All required libraries
└── MusePy_Mac/             # Mac executable
    ├── MusePy              # Main executable
    ├── experiments/        # Processing/visualization scripts
    ├── data/              # User data folder
    ├── sessions/          # Session storage
    └── [dependencies]     # All required libraries
```

## Notes

- **File Size**: Expect 200-500MB executables due to included dependencies
- **Performance**: First startup may be slower as PyInstaller extracts files
- **Updates**: Rebuild executable when updating MusePy code
- **Compatibility**: Test on target systems before distribution
