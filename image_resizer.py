import os
import io
from PIL import Image
from pathlib import Path
from tqdm import tqdm
from datetime import datetime
# ==== GUI IMPORTS ====
import tkinter as tk
from tkinter import filedialog, ttk, messagebox

# Simple tooltip class for tkinter widgets
class ToolTip(object):
    def __init__(self, widget, text):
        self.widget = widget
        self.text = text
        self.tipwindow = None
        widget.bind("<Enter>", self.show_tip)
        widget.bind("<Leave>", self.hide_tip)

    def show_tip(self, event=None):
        if self.tipwindow or not self.text:
            return
        # Try to get widget position, fallback if not possible
        try:
            x, y, cx, cy = self.widget.bbox("insert")
        except Exception:
            x, y = 0, 0
        x = x + self.widget.winfo_rootx() + 25
        y = y + self.widget.winfo_rooty() + 20
        self.tipwindow = tw = tk.Toplevel(self.widget)
        tw.wm_overrideredirect(True)
        tw.wm_geometry(f"+{x}+{y}")
        label = tk.Label(tw, text=self.text, justify=tk.LEFT,
                         background="#ffffe0", relief=tk.SOLID, borderwidth=1,
                         font=("tahoma", "8", "normal"))
        label.pack(ipadx=1)

    def hide_tip(self, event=None):
        tw = self.tipwindow
        self.tipwindow = None
        if tw:
            tw.destroy()



# ==== CONFIGURATION ====
TARGET_FILE_SIZE_KB = 200 # Output target size in KB
INPUT_FOLDER = "in" # Input folder containing images
OUTPUT_FOLDER = "out" # Output folder for resized images
OUTPUT_FORMAT = "WEBP"  # Output file format. Options: 'JPEG', 'PNG', 'WEBP', 'HEIF'
OUTPUT_NAMING_MODE = "folder"  # Output method. Options: 'prefix' or 'folder'
LOG_FOLDER = "logs"
LOG_FILE = "log.txt"
# ========================

# ==== GUI TOOLTIP TEXTS ====
TOOLTIPS = {
    "TARGET_FILE_SIZE_KB": "Output target size in KB",
    "INPUT_FOLDER": "Input folder containing images",
    "OUTPUT_FOLDER": "Output folder for resized images",
    "OUTPUT_FORMAT": "The format to use for saving the output images.",
    "OUTPUT_NAMING_MODE": "How output files are named and organized.",
    "LOG_FOLDER": "Folder for logs",
    "LOG_FILE": "Log file name"
}

# ==== GUI FUNCTION ====
def launch_gui():
    import threading
    def run_process():
        global TARGET_FILE_SIZE_KB, INPUT_FOLDER, OUTPUT_FOLDER, OUTPUT_FORMAT, OUTPUT_NAMING_MODE, LOG_FOLDER, LOG_FILE
        try:
            TARGET_FILE_SIZE_KB = int(file_size_var.get())
            INPUT_FOLDER = in_folder_var.get()
            OUTPUT_FOLDER = out_folder_var.get()
            OUTPUT_FORMAT = format_var.get()
            OUTPUT_NAMING_MODE = naming_var.get()
            LOG_FOLDER = log_folder_var.get()
            LOG_FILE = log_file_var.get()
        except Exception as e:
            messagebox.showerror("Error", f"Invalid input: {e}")
            return
        run_btn.config(state="disabled")
        threading.Thread(target=process_images_gui, daemon=True).start()

    def process_images_gui():
        import time
        from openpyxl import Workbook
        create_folders()
        Path(LOG_FOLDER).mkdir(exist_ok=True)
        input_path = Path(INPUT_FOLDER)
        output_path = Path(OUTPUT_FOLDER)
        image_files = [f for f in input_path.rglob('*') if f.suffix.lower() in SUPPORTED_FORMATS and f.is_file()]
        num_images = len(image_files)
        if not image_files:
            log_console.insert(tk.END, f"No supported image files found in '{INPUT_FOLDER}' folder.\n")
            run_btn.config(state="normal")
            return

        wb = Workbook()
        ws = wb.active
        ws.title = "Image Compression Log"
        ws.append([
            "Filename", "Original Size (KB)", "Compressed Quality", "Output Size (KB)", "Size Reduction (%)", "Output Filename", "Processing Time (s)"
        ])

        log_path = Path(LOG_FOLDER) / LOG_FILE
        with open(log_path, 'w', encoding='utf-8') as log:
            log.write(f"Image Compression Log\n")
            log.write(f"Date: {datetime.now()}\n")
            log.write(f"Target Size: {TARGET_FILE_SIZE_KB} KB | Format: {OUTPUT_FORMAT.upper()} | Mode: {OUTPUT_NAMING_MODE}\n")
            log.write("-" * 60 + "\n")


            steps_per_file = 6  # 1 for copy, 5 for simulated compression steps
            total_steps = num_images * steps_per_file
            total_progress['maximum'] = num_images
            completed_steps = 0
            for idx, image_file in enumerate(image_files):
                t0 = time.time()
                rel_path = image_file.relative_to(input_path)
                file_stem = image_file.stem
                extension_map = {'JPEG': '.jpg', 'PNG': '.png', 'WEBP': '.webp', 'HEIF': '.heic', 'HEIC': '.heic'}
                output_ext = extension_map.get(OUTPUT_FORMAT.upper(), '.jpg')
                rel_folder = rel_path.parent
                if OUTPUT_NAMING_MODE == "prefix":
                    output_filename = f"{file_stem}_{TARGET_FILE_SIZE_KB}kb{output_ext}"
                else:
                    output_filename = f"{file_stem}{output_ext}"
                if OUTPUT_NAMING_MODE == "prefix":
                    output_file = output_path / rel_folder / output_filename
                else:
                    size_folder = output_path / str(TARGET_FILE_SIZE_KB) / rel_folder
                    size_folder.mkdir(parents=True, exist_ok=True)
                    output_file = size_folder / output_filename
                (output_file.parent).mkdir(parents=True, exist_ok=True)

                log_console.insert(tk.END, f"Processing: {str(rel_path)}\n")
                log_console.see(tk.END)
                try:
                    original_size_kb = get_file_size_kb(image_file)
                    log_console.insert(tk.END, f"  Original size: {original_size_kb:.2f} KB\n")
                    log_console.see(tk.END)
                    if original_size_kb <= TARGET_FILE_SIZE_KB:
                        with open(image_file, 'rb') as src, open(output_file, 'wb') as dst:
                            dst.write(src.read())
                        log_console.insert(tk.END, f"  No compression needed - copied to output\n")
                        log_console.insert(tk.END, f"  Output size: {original_size_kb:.2f} KB\n")
                        t1 = time.time()
                        ws.append([
                            str(rel_path), f"{original_size_kb:.2f}", "-", f"{original_size_kb:.2f}", "0.0", str(output_file.relative_to(output_path)), f"{t1-t0:.2f}"
                        ])
                    else:
                        log_console.insert(tk.END, f"  Compressing...\n")
                        log_console.see(tk.END)
                        root.update_idletasks()
                        def log_quality(q):
                            log_console.insert(tk.END, f"    {q}")
                            log_console.see(tk.END)
                            root.update_idletasks()
                        def log_size(q):
                            log_console.insert(tk.END, f"({q})\n")
                            log_console.see(tk.END)
                            root.update_idletasks()
                        compressed_bytes, quality, final_size_kb = compress_image(
                            image_file, TARGET_FILE_SIZE_KB, log_quality=log_quality, log_size=log_size, initial_quality=int(max(1, min(95, 95 * (TARGET_FILE_SIZE_KB / original_size_kb) * 2)))
                        )
                        with open(output_file, 'wb') as f:
                            f.write(compressed_bytes)
                        reduction = (1 - final_size_kb / original_size_kb) * 100
                        log_console.insert(tk.END, f"  Compressed with quality: {quality}\n")
                        log_console.insert(tk.END, f"  Output size: {final_size_kb:.2f} KB\n")
                        log_console.insert(tk.END, f"  Size reduction: {reduction:.1f}%\n")
                        t1 = time.time()
                        ws.append([
                            str(rel_path), f"{original_size_kb:.2f}", str(quality), f"{final_size_kb:.2f}", f"{reduction:.1f}", str(output_file.relative_to(output_path)), f"{t1-t0:.2f}"
                        ])
                    log_console.insert(tk.END, f"  Saved as: {output_file.relative_to(output_path)}\n\n")
                    log_console.see(tk.END)
                except Exception as e:
                    log_console.insert(tk.END, f"  Error processing {str(rel_path)}: {e}\n\n")
                    log_console.see(tk.END)
                completed_steps += 1
                total_progress['value'] = completed_steps
                root.update_idletasks()

            run_btn.config(state="normal")

            excel_path = Path(LOG_FOLDER) / Path(LOG_FILE).with_suffix('.xlsx')
            wb.save(excel_path)
            log_console.insert(tk.END, f"✅ Done! Log written to: {log_path} and {excel_path}\n")
            log_console.see(tk.END)
            run_btn.config(state="normal")


    try:
        root = tk.Tk()
        root.title("Image Resizer Settings")
        frm = tk.Frame(root, padx=12, pady=12)
        frm.pack(fill=tk.BOTH, expand=True)

        # Target file size
        tk.Label(frm, text="Target File Size (KB):").grid(row=0, column=0, sticky="e")
        file_size_var = tk.StringVar(value=str(TARGET_FILE_SIZE_KB))
        file_size_entry = tk.Entry(frm, textvariable=file_size_var, width=10)
        file_size_entry.grid(row=0, column=1, sticky="w")
        ToolTip(file_size_entry, TOOLTIPS["TARGET_FILE_SIZE_KB"])

        # Input folder
        tk.Label(frm, text="Input Folder:").grid(row=1, column=0, sticky="e")
        in_folder_var = tk.StringVar(value=INPUT_FOLDER)
        in_folder_entry = tk.Entry(frm, textvariable=in_folder_var, width=20)
        in_folder_entry.grid(row=1, column=1, sticky="w")
        ToolTip(in_folder_entry, TOOLTIPS["INPUT_FOLDER"])
        def browse_in():
            folder = filedialog.askdirectory()
            if folder:
                in_folder_var.set(folder)
        tk.Button(frm, text="Browse", command=browse_in).grid(row=1, column=2, sticky="w")

        # Output folder
        tk.Label(frm, text="Output Folder:").grid(row=2, column=0, sticky="e")
        out_folder_var = tk.StringVar(value=OUTPUT_FOLDER)
        out_folder_entry = tk.Entry(frm, textvariable=out_folder_var, width=20)
        out_folder_entry.grid(row=2, column=1, sticky="w")
        ToolTip(out_folder_entry, TOOLTIPS["OUTPUT_FOLDER"])
        def browse_out():
            folder = filedialog.askdirectory()
            if folder:
                out_folder_var.set(folder)
        tk.Button(frm, text="Browse", command=browse_out).grid(row=2, column=2, sticky="w")

        # Output format
        tk.Label(frm, text="Output Format:").grid(row=3, column=0, sticky="e")
        format_var = tk.StringVar(value=OUTPUT_FORMAT)
        format_combo = ttk.Combobox(frm, textvariable=format_var, values=["JPEG", "PNG", "WEBP", "HEIF"], state="readonly", width=10)
        format_combo.grid(row=3, column=1, sticky="w")
        ToolTip(format_combo, TOOLTIPS["OUTPUT_FORMAT"])

        # Output naming method
        tk.Label(frm, text="Output Naming Method:").grid(row=4, column=0, sticky="e")
        naming_var = tk.StringVar(value=OUTPUT_NAMING_MODE)
        naming_combo = ttk.Combobox(frm, textvariable=naming_var, values=["prefix", "folder"], state="readonly", width=10)
        naming_combo.grid(row=4, column=1, sticky="w")
        ToolTip(naming_combo, TOOLTIPS["OUTPUT_NAMING_MODE"])

        # Log folder
        tk.Label(frm, text="Log Folder:").grid(row=5, column=0, sticky="e")
        log_folder_var = tk.StringVar(value=LOG_FOLDER)
        log_folder_entry = tk.Entry(frm, textvariable=log_folder_var, width=20)
        log_folder_entry.grid(row=5, column=1, sticky="w")
        ToolTip(log_folder_entry, TOOLTIPS["LOG_FOLDER"])
        def browse_log():
            folder = filedialog.askdirectory()
            if folder:
                log_folder_var.set(folder)
        tk.Button(frm, text="Browse", command=browse_log).grid(row=5, column=2, sticky="w")

        # Log file
        tk.Label(frm, text="Log File:").grid(row=6, column=0, sticky="e")
        log_file_var = tk.StringVar(value=LOG_FILE)
        log_file_entry = tk.Entry(frm, textvariable=log_file_var, width=20)
        log_file_entry.grid(row=6, column=1, sticky="w")
        ToolTip(log_file_entry, TOOLTIPS["LOG_FILE"])

        # Progress bars and log console
        tk.Label(frm, text="Total Progress:").grid(row=7, column=0, sticky="e")
        total_progress = ttk.Progressbar(frm, length=200, mode="determinate")
        total_progress.grid(row=7, column=1, columnspan=2, sticky="w")

        tk.Label(frm, text="Log:").grid(row=8, column=0, sticky="ne")
        log_console = tk.Text(frm, height=12, width=60, state="normal")
        log_console.grid(row=8, column=1, columnspan=2, sticky="w")

        # Run button
        run_btn = tk.Button(frm, text="Run", command=run_process, bg="#4CAF50", fg="white", padx=10, pady=5)
        run_btn.grid(row=9, column=0, columnspan=3, pady=12)

        root.mainloop()
    except Exception as e:
        print(f"GUI Error: {e}")



# Optional: register HEIC/HEIF support
try:
    from pillow_heif import register_heif_opener
    register_heif_opener()
except ImportError:
    pass

# Supported image formats
SUPPORTED_FORMATS = {'.jpg', '.jpeg', '.png', '.webp', '.tiff', '.bmp', '.heic', '.heif'}

def create_folders():
    Path(INPUT_FOLDER).mkdir(exist_ok=True)
    Path(OUTPUT_FOLDER).mkdir(exist_ok=True)

def get_file_size_kb(file_path):
    return os.path.getsize(file_path) / 1024

def prepare_image(img, output_format):
    """
    Handle alpha preservation depending on output format.
    """
    supports_alpha = output_format.upper() in ['PNG', 'WEBP']
    has_alpha = 'A' in img.getbands()

    # If target format does NOT support alpha, flatten image to white background
    if has_alpha and not supports_alpha:
        bg = Image.new("RGB", img.size, (255, 255, 255))  # white background
        bg.paste(img, mask=img.split()[-1])  # paste using alpha mask
        return bg

    # If image mode is P or LA and format does support alpha, convert to RGBA
    if img.mode in ('P', 'LA'):
        return img.convert('RGBA' if supports_alpha else 'RGB')

    return img

def compress_image(image_path, target_size_kb, log_quality=None, log_size=None, initial_quality=95):
    import math
    
    def interpolate_quality(q_low, s_low, q_high, s_high, s_target):
        import math
        # ln(S) = ln(A) + B * Q
        # B = (ln(s_high) - ln(s_low)) / (q_high - q_low)
        # ln(A) = ln(s_low) - B * q_low
        B = (math.log(s_high) - math.log(s_low)) / (q_high - q_low)
        ln_A = math.log(s_low) - B * q_low
        # Now, for target:
        q_target = (math.log(s_target) - ln_A) / B
        return q_target


    
    with Image.open(image_path) as img:
        img = prepare_image(img, OUTPUT_FORMAT)

        min_quality = 1
        max_quality = 95
        is_lossless = OUTPUT_FORMAT.upper() in ['PNG']
        is_heif = OUTPUT_FORMAT.upper() in ['HEIF', 'HEIC']
        
        # For lossless formats, just save once
        if is_lossless:
            buffer = io.BytesIO()
            img.save(buffer, format='PNG', optimize=True, compress_level=9)
            current_size_kb = len(buffer.getvalue()) / 1024
            return buffer.getvalue(), 95, current_size_kb
        
        tried = set()
        history = []  # Store (quality, size, bytes)
        last_two = []  # Track last two results for bracketing check
        
        # Step 1: Try quality 95
        quality_95 = 95
        if log_quality:
            log_quality(f"Trying quality: {quality_95}")
        
        buffer = io.BytesIO()
        save_kwargs = {}
        if OUTPUT_FORMAT.upper() == "WEBP":
            save_kwargs = {'format': 'WEBP', 'quality': quality_95, 'method': 6}
        elif is_heif:
            save_kwargs = {'format': 'HEIF', 'quality': quality_95}
        else:
            save_kwargs = {'format': 'JPEG', 'quality': quality_95, 'optimize': True}
        
        try:
            img.save(buffer, **save_kwargs)
        except Exception as e:
            raise RuntimeError(f"Failed saving as {OUTPUT_FORMAT}: {e}")
        
        size_95 = len(buffer.getvalue()) / 1024
        bytes_95 = buffer.getvalue()
        history.append((quality_95, size_95, bytes_95))
        last_two.append((quality_95, size_95, bytes_95))
        tried.add(quality_95)
        
        if log_size:
            log_size(f"{size_95:.2f} KB")
        
        # If quality 95 is already under target, return it
        if size_95 <= target_size_kb:
            return bytes_95, quality_95, size_95
        
        # Step 2: Try quality 1
        quality_1 = 1
        if log_quality:
            log_quality(f"Trying quality: {quality_1}")
        
        buffer = io.BytesIO()
        if OUTPUT_FORMAT.upper() == "WEBP":
            save_kwargs = {'format': 'WEBP', 'quality': quality_1, 'method': 6}
        elif is_heif:
            save_kwargs = {'format': 'HEIF', 'quality': quality_1}
        else:
            save_kwargs = {'format': 'JPEG', 'quality': quality_1, 'optimize': True}
        
        try:
            img.save(buffer, **save_kwargs)
        except Exception as e:
            raise RuntimeError(f"Failed saving as {OUTPUT_FORMAT}: {e}")
        
        size_1 = len(buffer.getvalue()) / 1024
        bytes_1 = buffer.getvalue()
        history.append((quality_1, size_1, bytes_1))
        last_two.append((quality_1, size_1, bytes_1))
        if len(last_two) > 2:
            last_two.pop(0)
        tried.add(quality_1)
        
        if log_size:
            log_size(f"{size_1:.2f} KB")
        
        # If quality 1 is over target, return it (best we can do)
        if size_1 > target_size_kb:
            return bytes_1, quality_1, size_1
        
        # Step 3 and onwards: Use interpolation
        step = 25.0
        try_count = 2  # We've already tried 2 qualities
        
        while step >= 1:
            try_count += 1
            
            # Calculate quality using interpolation based on history
            if len(history) >= 2:
                # Find best lower and higher bounds
                lower_bound = None
                higher_bound = None
                
                for q, s, b in sorted(history, key=lambda x: x[0], reverse=True):
                    if s <= target_size_kb and (lower_bound is None or q > lower_bound[0]):
                        lower_bound = (q, s, b)
                    elif s > target_size_kb and (higher_bound is None or q < higher_bound[0]):
                        higher_bound = (q, s, b)
                
                if lower_bound and higher_bound:
                    # Interpolate between bounds
                    q_low, s_low, _ = lower_bound
                    q_high, s_high, _ = higher_bound
                    predicted_quality = interpolate_quality(q_low, s_low, q_high, s_high, target_size_kb)
                    predicted_quality = max(min_quality, min(max_quality, int(round(predicted_quality))))
                    next_quality = predicted_quality
                elif lower_bound:
                    # Only have lower bound, try slightly higher
                    next_quality = min(max_quality, lower_bound[0] + int(step))
                elif higher_bound:
                    # Only have higher bound, try slightly lower
                    next_quality = max(min_quality, higher_bound[0] - int(step))
                else:
                    # Fallback to midpoint
                    next_quality = (min_quality + max_quality) // 2
            else:
                # Fallback to midpoint
                next_quality = (min_quality + max_quality) // 2
            
            # Skip if already tried
            if next_quality in tried:
                if step <= 1:
                    break
                step = step / 2
                continue
            
            if log_quality:
                log_quality(f"Trying quality: {next_quality}")
            
            buffer = io.BytesIO()
            if OUTPUT_FORMAT.upper() == "WEBP":
                save_kwargs = {'format': 'WEBP', 'quality': next_quality, 'method': 6}
            elif is_heif:
                save_kwargs = {'format': 'HEIF', 'quality': next_quality}
            else:
                save_kwargs = {'format': 'JPEG', 'quality': next_quality, 'optimize': True}
            
            try:
                img.save(buffer, **save_kwargs)
            except Exception as e:
                raise RuntimeError(f"Failed saving as {OUTPUT_FORMAT}: {e}")
            
            current_size_kb = len(buffer.getvalue()) / 1024
            current_bytes = buffer.getvalue()
            history.append((next_quality, current_size_kb, current_bytes))
            last_two.append((next_quality, current_size_kb, current_bytes))
            if len(last_two) > 2:
                last_two.pop(0)
            tried.add(next_quality)
            
            if log_size:
                log_size(f"{current_size_kb:.2f} KB")
            
            # Check if last two consecutive tries bracket the target
            if len(last_two) == 2 and try_count >= 4:
                q1, s1, b1 = last_two[0]
                q2, s2, b2 = last_two[1]
                
                # Check if target is between the two sizes
                if (s1 <= target_size_kb <= s2) or (s2 <= target_size_kb <= s1):
                    # Return the one that's ≤ target
                    if s1 <= target_size_kb and s2 <= target_size_kb:
                        # Both are under, return the larger one (closer to target)
                        if s1 >= s2:
                            return b1, q1, s1
                        else:
                            return b2, q2, s2
                    elif s1 <= target_size_kb:
                        return b1, q1, s1
                    elif s2 <= target_size_kb:
                        return b2, q2, s2
            
            # Check if we're within 10% offset of target - if so, set step to 1
            offset_10_percent = target_size_kb * 0.10
            if target_size_kb - offset_10_percent <= current_size_kb <= target_size_kb + offset_10_percent:
                step = 1
            else:
                step = step / 2
            
            # If we're very close or have tried many times, stop
            if step < 1 or try_count > 10:
                break
        
        # Fallback: pick the best quality that's ≤ target size
        best_under = None
        best_under_quality = None
        best_size = None
        
        for q, s, b in sorted(history, key=lambda x: x[0], reverse=True):
            if s <= target_size_kb:
                best_under = b
                best_under_quality = q
                best_size = s
                break
        
        if best_under is not None:
            return best_under, best_under_quality, best_size
        else:
            # If all are over target, return the smallest one
            q, s, b = min(history, key=lambda x: x[1])
            return b, q, s

def process_images():
    import time
    from openpyxl import Workbook
    start_time = time.time()
    create_folders()
    Path(LOG_FOLDER).mkdir(exist_ok=True)
    input_path = Path(INPUT_FOLDER)
    output_path = Path(OUTPUT_FOLDER)

    # Recursively find all supported image files
    image_files = [f for f in input_path.rglob('*') if f.suffix.lower() in SUPPORTED_FORMATS and f.is_file()]
    num_images = len(image_files)
    if not image_files:
        print(f"No supported image files found in '{INPUT_FOLDER}' folder.")
        return

    wb = Workbook()
    ws = wb.active
    ws.title = "Image Compression Log"
    ws.append([
        "Filename", "Original Size (KB)", "Compressed Quality", "Output Size (KB)", "Size Reduction (%)", "Output Filename", "Processing Time (s)"
    ])

    log_path = Path(LOG_FOLDER) / LOG_FILE
    with open(log_path, 'w', encoding='utf-8') as log:
        log.write(f"Image Compression Log\n")
        log.write(f"Date: {datetime.now()}\n")
        log.write(f"Target Size: {TARGET_FILE_SIZE_KB} KB | Format: {OUTPUT_FORMAT.upper()} | Mode: {OUTPUT_NAMING_MODE}\n")
        log.write("-" * 60 + "\n")

        for image_file in tqdm(image_files, desc="Compressing Images", unit="file"):
            try:
                t0 = time.time()
                original_size_kb = get_file_size_kb(image_file)
                file_stem = image_file.stem
                extension_map = {'JPEG': '.jpg', 'PNG': '.png', 'WEBP': '.webp', 'HEIF': '.heic', 'HEIC': '.heic'}
                output_ext = extension_map.get(OUTPUT_FORMAT.upper(), '.jpg')

                # Calculate relative path for output
                rel_path = image_file.relative_to(input_path)
                rel_folder = rel_path.parent
                if OUTPUT_NAMING_MODE == "prefix":
                    output_filename = f"{file_stem}_{TARGET_FILE_SIZE_KB}kb{output_ext}"
                else:
                    output_filename = f"{file_stem}{output_ext}"

                # Output folder structure
                if OUTPUT_NAMING_MODE == "prefix":
                    output_file = output_path / rel_folder / output_filename
                else:
                    size_folder = output_path / str(TARGET_FILE_SIZE_KB) / rel_folder
                    size_folder.mkdir(parents=True, exist_ok=True)
                    output_file = size_folder / output_filename

                (output_file.parent).mkdir(parents=True, exist_ok=True)

                log.write(f"Processing: {str(rel_path)}\n")
                log.write(f"  Original size: {original_size_kb:.2f} KB\n")

                if original_size_kb <= TARGET_FILE_SIZE_KB:
                    with open(image_file, 'rb') as src, open(output_file, 'wb') as dst:
                        dst.write(src.read())
                    log.write(f"  No compression needed - copied to output\n")
                    log.write(f"  Output size: {original_size_kb:.2f} KB\n")
                    t1 = time.time()
                    ws.append([
                        str(rel_path), f"{original_size_kb:.2f}", "-", f"{original_size_kb:.2f}", "0.0", str(output_file.relative_to(output_path)), f"{t1-t0:.2f}"
                    ])
                else:
                    compressed_bytes, quality, final_size_kb = compress_image(image_file, TARGET_FILE_SIZE_KB)
                    with open(output_file, 'wb') as f:
                        f.write(compressed_bytes)
                    reduction = (1 - final_size_kb / original_size_kb) * 100
                    log.write(f"  Compressed with quality: {quality}\n")
                    log.write(f"  Output size: {final_size_kb:.2f} KB\n")
                    log.write(f"  Size reduction: {reduction:.1f}%\n")
                    t1 = time.time()
                    ws.append([
                        str(rel_path), f"{original_size_kb:.2f}", str(quality), f"{final_size_kb:.2f}", f"{reduction:.1f}", str(output_file.relative_to(output_path)), f"{t1-t0:.2f}"
                    ])

                log.write(f"  Saved as: {output_file.relative_to(output_path)}\n\n")

            except Exception as e:
                log.write(f"  Error processing {str(rel_path)}: {e}\n\n")
                print(f"Error: {str(rel_path)} - {e}")

    excel_path = Path(LOG_FOLDER) / Path(LOG_FILE).with_suffix('.xlsx')
    wb.save(excel_path)
    print(f"✅ Done! Log written to: {log_path} and {excel_path}")
    elapsed = time.time() - start_time
    avg = elapsed / num_images if num_images > 0 else 0
    formatted_elapsed = format_duration(elapsed)
    print(f"Total processing time: {formatted_elapsed}")
    print(f"Average per image: {avg:.2f} seconds")
    with open(log_path, 'a', encoding='utf-8') as log:
        log.write(f"Total processing time: {formatted_elapsed}\n")
        log.write(f"Average per image: {avg:.2f} seconds\n")

def format_duration(seconds):
    seconds = int(round(seconds))
    if seconds >= 3600:
        h = seconds // 3600
        m = (seconds % 3600) // 60
        s = seconds % 60
        return f"{h:02}:{m:02}:{s:02} (hh:mm:ss)"
    elif seconds >= 60:
        m = seconds // 60
        s = seconds % 60
        return f"{m:02}:{s:02} (mm:ss)"
    else:
        return f"{seconds:.2f} seconds"

if __name__ == "__main__":
    launch_gui()
