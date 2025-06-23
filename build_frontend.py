#!/usr/bin/env python3
"""
Build script for TrackStudio React frontend

This script builds the React frontend and copies it to the package's static directory.
It's used during package installation to ensure the frontend is available.
"""

import os
import shutil
import subprocess  # nosec B404
import sys
from pathlib import Path


def build_frontend():
    """Build the React frontend and copy to static directory"""

    # Get paths
    root_dir = Path(__file__).parent
    web_dir = root_dir / "web"
    static_dir = root_dir / "trackstudio" / "static"

    print("🏗️  Building TrackStudio frontend...")

    # Check if web directory exists
    if not web_dir.exists():
        print("❌ Error: web/ directory not found!")
        print("   Make sure you're running this from the project root")
        return False

    # Change to web directory
    os.chdir(web_dir)

    # Install npm dependencies if needed
    if not (web_dir / "node_modules").exists():
        print("📦 Installing npm dependencies...")
        try:
            subprocess.run(["npm", "install"], check=True)
        except subprocess.CalledProcessError as e:
            print(f"❌ Error installing dependencies: {e}")
            return False
        except FileNotFoundError:
            print("❌ Error: npm not found! Please install Node.js first.")
            return False

    # Build the React app
    print("⚡ Building React app...")
    try:
        subprocess.run(["npm", "run", "build"], check=True)
    except subprocess.CalledProcessError as e:
        print(f"❌ Error building React app: {e}")
        return False

    # Clear static directory (except .gitkeep)
    print("🧹 Clearing static directory...")
    if static_dir.exists():
        for item in static_dir.iterdir():
            if item.name != ".gitkeep":
                if item.is_dir():
                    shutil.rmtree(item)
                else:
                    item.unlink()
    else:
        static_dir.mkdir(parents=True, exist_ok=True)

    # Copy built files to static directory
    print("📁 Copying built files to static directory...")
    dist_dir = web_dir / "dist"
    if not dist_dir.exists():
        print("❌ Error: dist/ directory not found after build!")
        return False

    # Copy all files from dist to static
    for item in dist_dir.iterdir():
        if item.is_dir():
            shutil.copytree(item, static_dir / item.name)
        else:
            shutil.copy2(item, static_dir / item.name)

    print("✅ Frontend build complete!")
    print(f"   Files copied to: {static_dir}")

    return True


if __name__ == "__main__":
    # This is called during pip install via setup.py
    success = build_frontend()
    if not success:
        print("\n⚠️  Warning: Frontend build failed!")
        print("   The package will still install, but the UI won't be available.")
        print("   You can manually build later by running: python build_frontend.py")
        # Don't fail the installation
        sys.exit(0)
