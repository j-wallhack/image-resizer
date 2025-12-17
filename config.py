from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Set

# Supported image formats and mapping for output extensions
SUPPORTED_FORMATS: Set[str] = {".jpg", ".jpeg", ".png", ".webp", ".tiff", ".bmp", ".heic", ".heif"}
EXTENSION_MAP: Dict[str, str] = {
    "JPEG": ".jpg",
    "PNG": ".png",
    "WEBP": ".webp",
    "HEIF": ".heic",
    "HEIC": ".heic",
}


@dataclass
class AppConfig:
    target_file_size_kb: int = 200  # Output target size in KB
    input_folder: str = "in"  # Input folder containing images
    output_folder: str = "out"  # Output folder for resized images
    output_format: str = "WEBP"  # Output file format
    output_naming_mode: str = "folder"  # Output method: 'prefix' or 'folder'
    log_folder: str = "logs"
    log_file: str = "log.txt"
    webp_method: int = 6  # Default WEBP method (0=fast, 6=best quality)
    method_tuning_threshold: int = 95  # Only tune method if size is below this % of target

    def log_path(self) -> Path:
        return Path(self.log_folder) / self.log_file

    def excel_path(self) -> Path:
        return Path(self.log_folder) / Path(self.log_file).with_suffix(".xlsx")

