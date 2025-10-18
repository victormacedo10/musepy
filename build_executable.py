#!/usr/bin/env python3
"""
Build script for creating MusePy executables using PyInstaller
"""

import os
import sys
import platform
import subprocess
import shutil
from pathlib import Path

def check_pyinstaller():
    """Check if PyInstaller is installed"""
    try:
        import PyInstaller
        print(f"PyInstaller version: {PyInstaller.__version__}")
        return True
    except ImportError:
        print("PyInstaller not found. Installing...")
        try:
            subprocess.check_call([sys.executable, '-m', 'pip', 'install', 'pyinstaller'])
            print("PyInstaller installed successfully!")
            return True
        except subprocess.CalledProcessError:
            print("Failed to install PyInstaller")
            return False

def clean_build_dirs():
    """Clean previous build directories"""
    dirs_to_clean = ['build', 'dist', '__pycache__']
    for dir_name in dirs_to_clean:
        if os.path.exists(dir_name):
            print(f"Cleaning {dir_name}...")
            shutil.rmtree(dir_name)
    
    # Clean .spec files in current directory
    for spec_file in Path('.').glob('*.spec'):
        if spec_file.name.startswith('musepy_'):
            print(f"Removing old spec file: {spec_file}")
            spec_file.unlink()

def build_executable(platform_name):
    """Build executable for the specified platform"""
    
    # Determine the correct spec file
    if platform_name.lower() == 'windows':
        spec_file = 'musepy_windows.spec'
    elif platform_name.lower() == 'mac':
        spec_file = 'musepy_mac.spec'
    else:
        print(f"Unsupported platform: {platform_name}")
        return False
    
    if not os.path.exists(spec_file):
        print(f"Spec file not found: {spec_file}")
        return False
    
    print(f"Building executable for {platform_name}...")
    print(f"Using spec file: {spec_file}")
    
    try:
        # Run PyInstaller
        cmd = [sys.executable, '-m', 'PyInstaller', '--clean', spec_file]
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        if result.returncode == 0:
            print("Build successful!")
            
            # Find the output directory
            dist_dir = Path('dist')
            if dist_dir.exists():
                folders = [f for f in dist_dir.iterdir() if f.is_dir()]
                if folders:
                    output_folder = folders[0]
                    print(f"Executable created in: {output_folder}")
                    print(f"Size: {get_folder_size(output_folder):.1f} MB")
                    
                    # List contents
                    print("\nContents:")
                    for item in sorted(output_folder.iterdir()):
                        if item.is_file():
                            print(f"  📄 {item.name} ({item.stat().st_size / 1024:.1f} KB)")
                        else:
                            print(f"  📁 {item.name}/")
            
            return True
        else:
            print("Build failed!")
            print("STDOUT:", result.stdout)
            print("STDERR:", result.stderr)
            return False
            
    except Exception as e:
        print(f"Error during build: {e}")
        return False

def get_folder_size(folder_path):
    """Get the total size of a folder in MB"""
    total_size = 0
    for dirpath, dirnames, filenames in os.walk(folder_path):
        for filename in filenames:
            filepath = os.path.join(dirpath, filename)
            if os.path.exists(filepath):
                total_size += os.path.getsize(filepath)
    return total_size / (1024 * 1024)  # Convert to MB

def main():
    """Main build function"""
    print("MusePy Executable Builder")
    print("=" * 40)
    
    # Check current platform
    current_platform = platform.system()
    print(f"Current platform: {current_platform}")
    
    # Check PyInstaller
    if not check_pyinstaller():
        return
    
    # Clean previous builds
    clean_build_dirs()
    
    # Ask user for target platform
    print("\nAvailable platforms:")
    print("1. Windows")
    print("2. Mac")
    print("3. Current platform only")
    
    choice = input("\nSelect platform (1-3): ").strip()
    
    if choice == '1':
        platforms = ['windows']
    elif choice == '2':
        platforms = ['mac']
    elif choice == '3':
        if current_platform.lower() == 'windows':
            platforms = ['windows']
        elif current_platform.lower() == 'darwin':
            platforms = ['mac']
        else:
            print(f"Unsupported current platform: {current_platform}")
            return
    else:
        print("Invalid choice")
        return
    
    # Build for selected platforms
    success_count = 0
    for platform_name in platforms:
        print(f"\n{'='*20} {platform_name.upper()} {'='*20}")
        if build_executable(platform_name):
            success_count += 1
        print()
    
    # Summary
    print("=" * 40)
    print(f"Build completed: {success_count}/{len(platforms)} successful")
    
    if success_count > 0:
        print("\nBuild artifacts:")
        print("📁 dist/ - Contains the built executables")
        print("📁 build/ - Contains build cache (can be deleted)")
        print("\nTo run the executable:")
        if 'windows' in platforms:
            print("  Windows: Navigate to dist/MusePy_Windows/ and run MusePy.exe")
        if 'mac' in platforms:
            print("  Mac: Navigate to dist/MusePy_Mac/ and run MusePy")

if __name__ == '__main__':
    main()
