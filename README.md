# Image Resizer

A user-friendly desktop application to compress images to a target file size without changing their resolution. It preserves folder structures and generates a detailed Excel report of the compression results.

## Features

- **Graphical User Interface**: Easy-to-use interface for configuring and running the compression process.
- **Target Size Compression**: Compresses images to meet a specific file size in KB.
- **Batch Processing**: Process an entire folder of images, including all subfolders.
- **Folder Structure Preservation**: Replicates the input folder structure in the output directory.
- **High-Quality Compression**: Uses an intelligent search algorithm to find the best possible quality setting for the target size.
- **Format Support**: Supports a wide range of formats: `JPEG`, `PNG`, `WEBP`, `TIFF`, `BMP`, and `HEIC/HEIF`.
- **Detailed Reporting**: Generates a log file and an Excel spreadsheet (`.xlsx`) with detailed statistics for each image.
- **Cross-Platform**: Works on both Windows and macOS.

## Getting Started

### Prerequisites

- [Python 3.8+](https://www.python.org/downloads/)

### Installation

1.  **Clone the repository:**
    ```bash
    git clone https://github.com/your-username/image-resizer.git
    cd image-resizer
    ```

2.  **Install dependencies:**
    It is recommended to use a virtual environment.
    ```bash
    # Create and activate a virtual environment (optional but recommended)
    python -m venv venv
    source venv/bin/activate  # On Windows, use `venv\Scripts\activate`

    # Install the required packages
    pip install -r requirements.txt
    ```

## How to Use

1.  **Launch the application:**
    ```bash
    python image_resizer.py
    ```
2.  **Configure the settings in the GUI:**
    - **Target File Size (KB)**: The desired file size for the output images.
    - **Input Folder**: The folder containing the images you want to compress. The application will search through all its subfolders.
    - **Output Folder**: Where the compressed images will be saved.
    - **Output Format**: Choose the desired output format (`JPEG`, `PNG`, `WEBP`, `HEIF`).
    - **Output Naming Method**:
        - `folder`: Saves images in a subfolder named after the target size (e.g., `out/200/...`).
        - `prefix`: Appends the target size to the filename (e.g., `image_200kb.jpg`).
3.  **Run the process:**
    - Click the **Run** button to start compressing.
    - Progress will be displayed in the log window.
4.  **Review the results:**
    - The compressed images will be in the specified output folder, maintaining the original folder structure.
    - A detailed log and an Excel report will be saved in the `logs` folder.

## Building an Executable

You can create a standalone executable for Windows or macOS, so you don't need to have Python installed to run the application.

### Windows

Run the `build.bat` script. It will:
1.  Create a Python virtual environment.
2.  Install all dependencies.
3.  Use PyInstaller to package the application into a single `.exe` file.
The final executable will be located in the `dist` folder.

### macOS

Run the `build_mac.sh` script. This will perform the same steps as the Windows build script, creating a standalone app bundle in the `dist` folder.

## How It Works

For each image, the application first checks if its size is already below the target. If it is, the image is copied directly to the output folder.

If the image is larger than the target size, a sophisticated search algorithm is used to find the optimal compression quality:
1.  It starts by testing high (95) and low (1) quality settings to establish initial bounds.
2.  It then uses **logarithmic interpolation** to predict the quality level that will most likely produce the target file size. This is more efficient than a simple binary search as it can find the target quality in fewer steps.
3.  The process iteratively refines the quality, narrowing down the search until it finds the best setting that produces an image at or just below the target size.

This ensures the highest possible image quality while respecting the file size constraint.

## Supported Formats

- JPEG/JPG
- PNG
- WEBP
- TIFF
- BMP
- HEIC/HEIF (requires `pillow-heif`)
