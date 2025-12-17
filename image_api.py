import io
import os
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Callable, Dict, Iterable, Optional, Tuple

from PIL import Image

from config import AppConfig, EXTENSION_MAP, SUPPORTED_FORMATS

# Optional: register HEIC/HEIF support
try:
    from pillow_heif import register_heif_opener

    register_heif_opener()
except ImportError:
    pass


LogCallback = Callable[[str], None]
ProgressCallback = Callable[[int, int], None]


class ProcessingController:
    """Thread-friendly controls for pause/resume/skip/stop."""

    def __init__(self):
        self._pause = threading.Event()
        self._stop = threading.Event()
        self._skip = threading.Event()

    def pause(self):
        self._pause.set()

    def resume(self):
        self._pause.clear()

    def stop(self):
        self._stop.set()

    def request_skip(self):
        self._skip.set()

    def wait_if_paused(self):
        while self._pause.is_set() and not self._stop.is_set():
            time.sleep(0.1)

    def should_stop(self) -> bool:
        return self._stop.is_set()

    def consume_skip(self) -> bool:
        if self._skip.is_set():
            self._skip.clear()
            return True
        return False


class StopProcessing(Exception):
    """Raised to signal a stop request."""


class SkipProcessing(Exception):
    """Raised to signal skip of the current item."""


def create_folders(config: AppConfig) -> None:
    Path(config.input_folder).mkdir(exist_ok=True)
    Path(config.output_folder).mkdir(exist_ok=True)
    Path(config.log_folder).mkdir(exist_ok=True)


def get_file_size_kb(file_path: Path) -> float:
    return os.path.getsize(file_path) / 1024


def prepare_image(img: Image.Image, output_format: str) -> Image.Image:
    """Handle alpha preservation depending on output format."""
    supports_alpha = output_format.upper() in ["PNG", "WEBP"]
    has_alpha = "A" in img.getbands()

    # If target format does NOT support alpha, flatten image to white background
    if has_alpha and not supports_alpha:
        bg = Image.new("RGB", img.size, (255, 255, 255))  # white background
        bg.paste(img, mask=img.split()[-1])  # paste using alpha mask
        return bg

    # If image mode is P or LA and format does support alpha, convert to RGBA
    if img.mode in ("P", "LA"):
        return img.convert("RGBA" if supports_alpha else "RGB")

    return img


def compress_image(
    image_path: Path,
    config: AppConfig,
    target_size_kb: int,
    log_quality: Optional[LogCallback] = None,
    log_size: Optional[LogCallback] = None,
    initial_quality: int = 95,
    scale_settings: Optional[Dict] = None,
    controller: Optional[ProcessingController] = None,
) -> Tuple[bytes, int, float, int]:
    import math

    output_format_upper = config.output_format.upper()
    webp_method_default = (
        scale_settings.get("webp_method", config.webp_method) if scale_settings else config.webp_method
    )

    def ensure_running():
        if controller:
            controller.wait_if_paused()
            if controller.should_stop():
                raise StopProcessing()
            if controller.consume_skip():
                raise SkipProcessing()

    def interpolate_quality(q_low, s_low, q_high, s_high, s_target):
        if s_high == s_low:
            return q_low
        B = (math.log(s_high) - math.log(s_low)) / (q_high - q_low)
        if B == 0:
            return q_low
        ln_A = math.log(s_low) - B * q_low
        q_target = (math.log(s_target) - ln_A) / B
        return q_target

    with Image.open(image_path) as img:
        ensure_running()
        # --- Image Scaling ---
        if scale_settings and scale_settings.get("mode") != "Off":
            apply_scale = False
            if scale_settings.get("condition") != "On":
                apply_scale = True
            else:
                cond_w = scale_settings.get("cond_width", 0)
                cond_h = scale_settings.get("cond_height", 0)
                cond_logic = scale_settings.get("cond_logic")

                w_cond_active = cond_w > 0
                h_cond_active = cond_h > 0
                w_cond_met = img.width > cond_w
                h_cond_met = img.height > cond_h

                if cond_logic == "OR (Any condition met)":
                    if (w_cond_active and w_cond_met) or (h_cond_active and h_cond_met):
                        apply_scale = True
                elif cond_logic == "AND (All conditions met)":
                    passes_w = (not w_cond_active) or w_cond_met
                    passes_h = (not h_cond_active) or h_cond_met
                    if passes_w and passes_h and (w_cond_active or h_cond_active):
                        apply_scale = True

            if apply_scale:
                if scale_settings.get("mode") == "By Percentage":
                    percent = scale_settings.get("percent", 100)
                    new_w = int(img.width * percent / 100)
                    new_h = int(img.height * percent / 100)
                    img = img.resize((new_w, new_h), Image.Resampling.LANCZOS)
                elif scale_settings.get("mode") == "By Target Dimensions":
                    target_w = scale_settings.get("width", img.width)
                    target_h = scale_settings.get("height", img.height)
                    img.thumbnail((target_w, target_h), Image.Resampling.LANCZOS)

        img = prepare_image(img, config.output_format)

        min_quality = 1
        max_quality = 100

        is_lossless = output_format_upper in ["PNG"]
        is_heif = output_format_upper in ["HEIF", "HEIC"]

        # For lossless formats, just save once
        if is_lossless:
            buffer = io.BytesIO()
            img.save(buffer, format="PNG", optimize=True, compress_level=9)
            current_size_kb = len(buffer.getvalue()) / 1024
            return buffer.getvalue(), 100, current_size_kb, -1

        def get_size_for_quality(quality, method=webp_method_default):
            buffer = io.BytesIO()
            save_kwargs = {}
            if output_format_upper == "WEBP":
                save_kwargs = {"format": "WEBP", "quality": quality, "method": method}
            elif is_heif:
                save_kwargs = {"format": "HEIF", "quality": quality}
            else:  # JPEG
                save_kwargs = {"format": "JPEG", "quality": quality, "optimize": True}

            try:
                img.save(buffer, **save_kwargs)
            except Exception as e:
                # Fallback for older Pillow versions that might not support 'method'
                if "method" in str(e) and output_format_upper == "WEBP":
                    save_kwargs.pop("method", None)
                    img.save(buffer, **save_kwargs)
                else:
                    raise RuntimeError(f"Failed saving as {config.output_format}: {e}")

            b = buffer.getvalue()
            s = len(b) / 1024
            return b, s

        tried = set()
        history = []  # Store (quality, size, bytes)

        q_initial = max(min_quality, min(max_quality, initial_quality))
        ensure_running()
        if log_quality:
            log_quality(f"Trying quality: {q_initial}")
        bytes_initial, size_initial = get_size_for_quality(q_initial)
        if log_size:
            log_size(f"{size_initial:.2f} KB")

        history.append((q_initial, size_initial, bytes_initial))
        tried.add(q_initial)

        if size_initial > target_size_kb:
            q_low = 1
            if q_low not in tried:
                ensure_running()
                if log_quality:
                    log_quality(f"Trying quality: {q_low}")
                bytes_low, size_low = get_size_for_quality(q_low)
                if log_size:
                    log_size(f"{size_low:.2f} KB")
                history.append((q_low, size_low, bytes_low))
                tried.add(q_low)
                if size_low > target_size_kb:
                    return bytes_low, q_low, size_low, webp_method_default
        else:
            q_high = max_quality
            if q_high not in tried:
                ensure_running()
                if log_quality:
                    log_quality(f"Trying quality: {q_high}")
                bytes_high, size_high = get_size_for_quality(q_high)
                if log_size:
                    log_size(f"{size_high:.2f} KB")
                history.append((q_high, size_high, bytes_high))
                tried.add(q_high)
                if size_high <= target_size_kb:
                    return bytes_high, q_high, size_high, webp_method_default

        step = 50.0
        try_count = len(tried)
        lower_bound, higher_bound = None, None

        while step >= 1 and try_count <= 10:
            try_count += 1

            lower_bound, higher_bound = None, None
            for q, s, b in history:
                if s <= target_size_kb:
                    if lower_bound is None or q > lower_bound[0]:
                        lower_bound = (q, s, b)
                elif s > target_size_kb:
                    if higher_bound is None or q < higher_bound[0]:
                        higher_bound = (q, s, b)

            if lower_bound and higher_bound and (higher_bound[0] - lower_bound[0] <= 1):
                break

            if lower_bound and higher_bound:
                q_low, s_low, _ = lower_bound
                q_high, s_high, _ = higher_bound
                predicted_quality = interpolate_quality(q_low, s_low, q_high, s_high, target_size_kb)
                next_quality = max(min_quality, min(max_quality, int(round(predicted_quality))))
            elif lower_bound:
                next_quality = min(max_quality, lower_bound[0] + int(step))
            elif higher_bound:
                next_quality = max(min_quality, higher_bound[0] - int(step))
            else:
                next_quality = (min_quality + max_quality) // 2

            if next_quality in tried:
                if lower_bound and higher_bound:
                    next_quality = (lower_bound[0] + higher_bound[0]) // 2
                else:  # Halve step if stuck
                    step /= 2
                    continue
            if next_quality in tried:  # If still stuck
                step /= 2
                continue

            ensure_running()
            if log_quality:
                log_quality(f"Trying quality: {next_quality}")
            current_bytes, current_size_kb = get_size_for_quality(next_quality)
            if log_size:
                log_size(f"{current_size_kb:.2f} KB")

            history.append((next_quality, current_size_kb, current_bytes))
            tried.add(next_quality)

            offset_margin = target_size_kb * 0.10
            if abs(current_size_kb - target_size_kb) < offset_margin:
                step = 1
            else:
                step = max(1, step / 2)

        # --- Final Selection ---
        best_under = None
        for q, s, b in history:
            if s <= target_size_kb:
                if best_under is None or s > best_under[1]:
                    best_under = (q, s, b)

        if best_under is None:  # If all are over, return smallest
            q, s, b = min(history, key=lambda x: x[1])
            return b, q, s, webp_method_default

        # --- Method Tuning for WEBP ---
        best_quality, best_size, best_bytes = best_under
        best_method = webp_method_default
        tuning_threshold = (
            scale_settings.get("tuning_threshold", config.method_tuning_threshold / 100.0)
            if scale_settings
            else config.method_tuning_threshold / 100.0
        )

        if output_format_upper == "WEBP" and best_size < (target_size_kb * tuning_threshold):
            for method in range(webp_method_default - 1, -1, -1):
                ensure_running()
                if log_quality:
                    log_quality(f"Tuning method for Q{best_quality}: {method}")
                tuned_bytes, tuned_size = get_size_for_quality(best_quality, method=method)
                if log_size:
                    log_size(f"{tuned_size:.2f} KB")

                if tuned_size <= target_size_kb:
                    if tuned_size > best_size:  # Found a better size
                        best_size = tuned_size
                        best_bytes = tuned_bytes
                        best_method = method
                else:
                    # This method is too big, so the previous one was the best.
                    break

        return best_bytes, best_quality, best_size, best_method


def _default_log(message: str) -> None:
    print(message)


def process_images(
    config: AppConfig,
    scale_settings: Optional[Dict] = None,
    on_log: Optional[LogCallback] = None,
    on_quality: Optional[LogCallback] = None,
    on_size: Optional[LogCallback] = None,
    on_progress: Optional[ProgressCallback] = None,
    controller: Optional[ProcessingController] = None,
) -> Dict[str, int]:
    from openpyxl import Workbook
    from tqdm import tqdm

    log_fn = on_log or _default_log
    quality_fn = on_quality
    size_fn = on_size
    progress_fn = on_progress

    create_folders(config)

    input_path = Path(config.input_folder)
    output_path = Path(config.output_folder)

    # Recursively find all supported image files
    image_files: Iterable[Path] = [
        f for f in input_path.rglob("*") if f.suffix.lower() in SUPPORTED_FORMATS and f.is_file()
    ]
    image_files = list(image_files)
    num_images = len(image_files)

    if progress_fn:
        progress_fn(0, num_images)

    if not image_files:
        log_fn(f"No supported image files found in '{config.input_folder}' folder.")
        return {"processed": 0, "skipped": 0}

    wb = Workbook()
    ws = wb.active
    ws.title = "Image Compression Log"
    ws.append(
        [
            "Filename",
            "Original Size (KB)",
            "Compressed Quality",
            "Method",
            "Output Size (KB)",
            "Size Reduction (%)",
            "Output Filename",
            "Processing Time (s)",
        ]
    )

    log_path = config.log_path()
    excel_path = config.excel_path()
    quality_buffer = {"last": ""}

    with open(log_path, "w", encoding="utf-8") as log:
        def log_line(message: str) -> None:
            log.write(message + "\n")
            log_fn(message)

        def log_quality(message: str) -> None:
            quality_buffer["last"] = message.strip()
            if quality_fn:
                quality_fn(message)

        def log_size(message: str) -> None:
            if size_fn:
                size_fn(message)
            if quality_buffer["last"]:
                log.write(f"{quality_buffer['last']}({message})\n")
            else:
                log.write(f"{message}\n")

        log_line("Image Compression Log")
        log_line(f"Date: {datetime.now()}")
        log_line(
            f"Target Size: {config.target_file_size_kb} KB | Format: {config.output_format.upper()} | Mode: {config.output_naming_mode}"
        )
        log_line("-" * 60)

        iterator = image_files
        if not on_log and not on_progress:
            # If no UI callbacks, keep CLI progress bar behavior
            iterator = tqdm(image_files, desc="Compressing Images", unit="file")

        for idx, image_file in enumerate(iterator):
            if controller:
                controller.wait_if_paused()
                if controller.should_stop():
                    log_line("Stopped by user")
                    break
            try:
                t0 = datetime.now().timestamp()
                original_size_kb = get_file_size_kb(image_file)
                file_stem = image_file.stem
                output_ext = EXTENSION_MAP.get(config.output_format.upper(), ".jpg")

                # Calculate relative path for output
                rel_path = image_file.relative_to(input_path)
                rel_folder = rel_path.parent

                if controller and controller.consume_skip():
                    log_line(f"Skipped by user: {str(rel_path)}")
                    if progress_fn:
                        progress_fn(idx + 1, num_images)
                    continue

                if config.output_naming_mode == "prefix":
                    output_filename = f"{file_stem}_{config.target_file_size_kb}kb{output_ext}"
                else:
                    output_filename = f"{file_stem}{output_ext}"

                # Output folder structure
                if config.output_naming_mode == "prefix":
                    output_file = output_path / rel_folder / output_filename
                else:
                    size_folder = output_path / str(config.target_file_size_kb) / rel_folder
                    size_folder.mkdir(parents=True, exist_ok=True)
                    output_file = size_folder / output_filename

                (output_file.parent).mkdir(parents=True, exist_ok=True)

                log_line(f"Processing: {str(rel_path)}")
                log_line(f"  Original size: {original_size_kb:.2f} KB")

                if original_size_kb <= config.target_file_size_kb:
                    with open(image_file, "rb") as src, open(output_file, "wb") as dst:
                        dst.write(src.read())
                    log_line("  No compression needed - copied to output")
                    log_line(f"  Output size: {original_size_kb:.2f} KB")
                    t1 = datetime.now().timestamp()
                    ws.append(
                        [
                            str(rel_path),
                            f"{original_size_kb:.2f}",
                            "-",
                            "-",
                            f"{original_size_kb:.2f}",
                            "0.0",
                            str(output_file.relative_to(output_path)),
                            f"{t1 - t0:.2f}",
                        ]
                    )
                else:
                    initial_quality_guess = int(
                        max(1, min(100, 100 * (config.target_file_size_kb / original_size_kb) * 1.5))
                    )
                    compressed_bytes, quality, final_size_kb, method = compress_image(
                        image_file,
                        config,
                        config.target_file_size_kb,
                        log_quality=log_quality,
                        log_size=log_size,
                        initial_quality=initial_quality_guess,
                        scale_settings=scale_settings,
                        controller=controller,
                    )
                    with open(output_file, "wb") as f:
                        f.write(compressed_bytes)
                    reduction = (1 - final_size_kb / original_size_kb) * 100
                    log_line(f"  Compressed with quality: {quality} (method: {method if method != -1 else 'N/A'})")
                    log_line(f"  Output size: {final_size_kb:.2f} KB")
                    log_line(f"  Size reduction: {reduction:.1f}%")
                    t1 = datetime.now().timestamp()
                    ws.append(
                        [
                            str(rel_path),
                            f"{original_size_kb:.2f}",
                            str(quality),
                            str(method if method != -1 else "N/A"),
                            f"{final_size_kb:.2f}",
                            f"{reduction:.1f}",
                            str(output_file.relative_to(output_path)),
                            f"{t1 - t0:.2f}",
                        ]
                    )

                log_line(f"  Saved as: {output_file.relative_to(output_path)}")

            except SkipProcessing:
                log_line(f"Skipped by user: {str(rel_path)}")
                if progress_fn:
                    progress_fn(idx + 1, num_images)
                continue
            except StopProcessing:
                log_line("Stopped by user")
                break
            except Exception as e:
                log_line(f"  Error processing {str(rel_path)}: {e}")

            if progress_fn:
                progress_fn(idx + 1, num_images)

    wb.save(excel_path)
    log_fn(f"✅ Done! Log written to: {log_path} and {excel_path}")

    return {"processed": num_images, "skipped": 0}

