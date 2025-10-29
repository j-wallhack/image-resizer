#!/bin/bash

# Image Resizer - macOS Build Script using PyInstaller
# This script builds a standalone executable for macOS

set -e  # Exit on any error

echo "🍎 Image Resizer - macOS Build Script"
echo "====================================="

# Check if Python is installed
if ! command -v python3 &> /dev/null; then
    echo "❌ Error: Python 3 is not installed or not in PATH"
    echo "Please install Python 3 from https://www.python.org/downloads/mac-osx/"
    exit 1
fi

echo "✅ Python 3 found: $(python3 --version)"

# Check if pip is available
if ! command -v pip3 &> /dev/null; then
    echo "❌ Error: pip3 is not installed"
    echo "Please install pip3 or use 'python3 -m ensurepip'"
    exit 1
fi

echo "✅ pip3 found"

# Create virtual environment if it doesn't exist
if [ ! -d "venv" ]; then
    echo "📦 Creating virtual environment..."
    python3 -m venv venv
else
    echo "✅ Virtual environment already exists"
fi

# Activate virtual environment
echo "🔧 Activating virtual environment..."
source venv/bin/activate

# Upgrade pip
echo "⬆️  Upgrading pip..."
pip install --upgrade pip

# Install dependencies
echo "📋 Installing dependencies..."
if [ -f "requirements.txt" ]; then
    pip install -r requirements.txt
else
    echo "❌ Error: requirements.txt not found"
    echo "Please ensure requirements.txt exists in the project directory"
    exit 1
fi

# Install PyInstaller
echo "🔨 Installing PyInstaller..."
pip install pyinstaller

# Clean previous builds
echo "🧹 Cleaning previous builds..."
rm -rf build/ dist/ *.spec

# Create the executable
echo "🏗️  Building executable with PyInstaller..."
pyinstaller \
    --onefile \
    --name "ImageResizer" \
    --add-data "requirements.txt:." \
    --hidden-import "pillow_heif" \
    --hidden-import "openpyxl" \
    --hidden-import "tqdm" \
    --collect-submodules "pillow_heif" \
    --noconfirm \
    image_resizer.py

# Check if build was successful
if [ -f "dist/ImageResizer" ]; then
    echo "✅ Build successful!"
    echo "📱 Executable created: dist/ImageResizer"
    
    # Make sure it's executable
    chmod +x dist/ImageResizer
    
    # Get file size
    FILE_SIZE=$(du -h dist/ImageResizer | cut -f1)
    echo "📊 File size: $FILE_SIZE"
    
    echo ""
    echo "🚀 Usage Instructions:"
    echo "1. Copy the 'dist/ImageResizer' file to your desired location"
    echo "2. Create an 'in' folder next to the executable"
    echo "3. Place your images in the 'in' folder"
    echo "4. Run the executable: ./ImageResizer"
    echo "5. Compressed images will appear in the 'out' folder"
    echo ""
    echo "📁 Output structure:"
    echo "  ImageResizer        (executable)"
    echo "  in/                 (input images folder)"
    echo "  out/                (output images folder)"
    echo "  logs/               (processing logs)"
    
else
    echo "❌ Build failed! Check the output above for errors."
    exit 1
fi

# Deactivate virtual environment
deactivate

echo ""
echo "🎉 Build process completed!"
echo "The standalone executable is ready for distribution on macOS." 