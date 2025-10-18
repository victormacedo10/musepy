# MusePy Build Specifications

This document explains the PyInstaller spec files for building MusePy executables on Windows and macOS.

## Files Overview

- `musepy_windows.spec` - PyInstaller specification for Windows builds
- `musepy_mac.spec` - PyInstaller specification for macOS builds
- `build_executable.py` - Automated build script that uses these spec files

## What's Included

### Core Dependencies
- **PySide6** - GUI framework and Qt bindings
- **NumPy & Pandas** - Data processing and analysis
- **SciPy** - Scientific computing functions
- **Matplotlib & PyQtGraph** - Data visualization and plotting
- **BrainFlow** - EEG data acquisition from Muse devices

### Google Drive Integration
- **Google Auth Libraries** - Authentication and API access
- **Google Drive API Client** - File upload functionality
- All necessary OAuth and HTTP libraries

### Application Assets
- **Source Code** (`src/` directory) - All Python modules
- **Assets** (`assets/` directory) - Icons and images including Google Drive logo
- **Configuration** (`google_drive/` directory) - Google Drive setup files
- **Data Directory** (`data/` directory) - Default data storage location
- **Sessions** (`sessions/` directory) - Session management files

## Platform-Specific Features

### Windows (`musepy_windows.spec`)
- Includes BrainFlow DLL files from `brainflow/lib/`
- Windows-optimized binary handling
- Console disabled for clean GUI experience
- UPX compression enabled for smaller executables

### macOS (`musepy_mac.spec`)
- Includes BrainFlow dynamic libraries (.dylib files)
- macOS-specific binary paths
- Code signing support (when certificates are available)
- Console disabled for clean GUI experience

## Building Executables

### Using the Build Script (Recommended)
```bash
python build_executable.py
```
This script will:
1. Check for PyInstaller installation
2. Clean previous builds
3. Let you choose target platform
4. Build using the appropriate spec file

### Manual Building
```bash
# Windows
pyinstaller --clean musepy_windows.spec

# macOS
pyinstaller --clean musepy_mac.spec
```

## Output Structure

After building, you'll find:
```
dist/
├── MusePy_Windows/          # Windows build
│   ├── MusePy.exe          # Main executable
│   ├── brainflow/          # BrainFlow libraries
│   ├── src/                # Application source
│   ├── assets/             # Icons and images
│   ├── google_drive/       # Google Drive config
│   └── [other dependencies]
└── MusePy_Mac/             # macOS build
    ├── MusePy              # Main executable
    └── [same structure as Windows]
```

## Google Drive Setup for Distributions

When distributing the built executable:

1. **Google Drive libraries are included** in the build (no separate installation needed)

2. **Configuration files** (already in `google_drive/` folder):
   - `service_account.json` - Service account key for authentication
   - `folder_id.txt` - Target Google Drive folder ID

3. **No user authentication required**:
   - Service account authentication is automatic
   - No browser login needed
   - All uploads go to the configured Drive folder

## Troubleshooting

### Common Issues

1. **Missing BrainFlow libraries**:
   - Ensure BrainFlow is properly installed
   - Check that lib files exist in `brainflow/lib/`

2. **Google Drive not working**:
   - Verify all Google Drive libraries are installed
   - Check service_account.json is valid and in the correct location
   - Ensure folder_id.txt contains a valid Google Drive folder ID
   - Verify the service account email has Editor access to the Drive folder

3. **Large executable size**:
   - The spec files exclude unnecessary modules (tkinter, tests, etc.)
   - UPX compression is enabled to reduce size
   - Consider removing unused dependencies from requirements.txt

4. **Platform-specific errors**:
   - Windows: Ensure Visual C++ Redistributable is installed
   - macOS: May need to allow the app in Security & Privacy settings

### Debugging

To enable console output for debugging, change in the spec files:
```python
console=True,  # Instead of console=False
```

## Customization

### Adding New Dependencies
1. Add to `hiddenimports` list in both spec files
2. Add any binary files to `binaries` list
3. Add data files to `datas` list

### Changing Output Names
Modify the `name` parameter in the `EXE()` and `COLLECT()` sections.

### Including Additional Files
Add entries to the `datas` list:
```python
('path/to/source', 'destination/in/executable'),
```

## Performance Optimization

- **UPX compression** is enabled to reduce executable size
- **Unnecessary modules** are excluded to minimize size
- **Binary optimization** is enabled for faster startup
- **Single-file builds** are not used to maintain reasonable file sizes

## Security Considerations

- Service account key file should be kept secure
- Built executables should be code-signed for distribution
- Service account only has access to folders explicitly shared with it
- Distribute executables through secure channels
