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
    "LOG_FILE": "Log file name",
    "SCALE_MODE": "Off: No resizing.\nBy Percentage: Scale image by a percentage.\nBy Target Dimensions: Resize to fit within a specific width/height, maintaining aspect ratio.",
    "SCALE_PERCENT": "The percentage to scale the image resolution by (e.g., 50%).",
    "SCALE_WIDTH": "The target width in pixels.",
    "SCALE_HEIGHT": "The target height in pixels.",
    "SCALE_CONDITION": "Enable or disable conditional scaling.",
    "SCALE_COND_WIDTH": "Only scale if image width is greater than this value.",
    "SCALE_COND_HEIGHT": "Only scale if image height is greater than this value.",
    "SCALE_COND_LOGIC": "OR: Scale if any condition is met.\nAND: Scale only if all conditions are met."
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
            
            # Get scaling settings from GUI
            scale_settings = {
                "mode": scale_mode_var.get(),
                "percent": int(scale_percent_var.get()),
                "width": int(scale_width_var.get()) if scale_width_var.get() else 0,
                "height": int(scale_height_var.get()) if scale_height_var.get() else 0,
                "condition": scale_condition_var.get(),
                "cond_width": int(scale_cond_width_var.get()) if scale_cond_width_var.get() else 0,
                "cond_height": int(scale_cond_height_var.get()) if scale_cond_height_var.get() else 0,
                "cond_logic": scale_cond_logic_var.get()
            }

        except Exception as e:
            messagebox.showerror("Error", f"Invalid input: {e}")
            return
        
        # Reset UI for new run
        log_console.delete('1.0', tk.END)
        total_progress['value'] = 0
        root.update_idletasks()
        
        run_btn.config(state="disabled")
        threading.Thread(target=process_images_gui, args=(scale_settings,), daemon=True).start()

    def process_images_gui(scale_settings):
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
            
            def log_to_all(message, end="\n"):
                log_console.insert(tk.END, message + end)
                log_console.see(tk.END)
                log.write(message + end)

            log_to_all(f"Image Compression Log", end="\n")
            log_to_all(f"Date: {datetime.now()}", end="\n")
            log_to_all(f"Target Size: {TARGET_FILE_SIZE_KB} KB | Format: {OUTPUT_FORMAT.upper()} | Mode: {OUTPUT_NAMING_MODE}", end="\n")
            log_to_all("-" * 60, end="\n")

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

                log_to_all(f"Processing: {str(rel_path)}", end="\n")
                root.update_idletasks()

                try:
                    original_size_kb = get_file_size_kb(image_file)
                    log_to_all(f"  Original size: {original_size_kb:.2f} KB", end="\n")
                    root.update_idletasks()

                    if original_size_kb <= TARGET_FILE_SIZE_KB:
                        with open(image_file, 'rb') as src, open(output_file, 'wb') as dst:
                            dst.write(src.read())
                        log_to_all(f"  No compression needed - copied to output", end="\n")
                        log_to_all(f"  Output size: {original_size_kb:.2f} KB", end="\n")
                        t1 = time.time()
                        ws.append([
                            str(rel_path), f"{original_size_kb:.2f}", "-", f"{original_size_kb:.2f}", "0.0", str(output_file.relative_to(output_path)), f"{t1-t0:.2f}"
                        ])
                    else:
                        log_to_all(f"  Compressing...", end="\n")
                        root.update_idletasks()
                        
                        buffered_log = ""
                        def log_quality(q):
                            nonlocal buffered_log
                            log_console.insert(tk.END, f"    {q}")
                            log_console.see(tk.END)
                            root.update_idletasks()
                            buffered_log = f"    {q}"

                        def log_size(q):
                            nonlocal buffered_log
                            log_console.insert(tk.END, f"({q})\n")
                            log_console.see(tk.END)
                            root.update_idletasks()
                            log.write(f"{buffered_log}({q})\n")

                        # Better initial quality guess
                        # Use a factor of 1.5 because quality vs. size is not linear
                        initial_quality_guess = int(max(1, min(100, 100 * (TARGET_FILE_SIZE_KB / original_size_kb) * 1.5)))

                        compressed_bytes, quality, final_size_kb = compress_image(
                            image_file, 
                            TARGET_FILE_SIZE_KB, 
                            log_quality=log_quality, 
                            log_size=log_size, 
                            initial_quality=initial_quality_guess,
                            scale_settings=scale_settings
                        )
                        with open(output_file, 'wb') as f:
                            f.write(compressed_bytes)
                        reduction = (1 - final_size_kb / original_size_kb) * 100
                        log_to_all(f"  Compressed with quality: {quality}", end="\n")
                        log_to_all(f"  Output size: {final_size_kb:.2f} KB", end="\n")
                        log_to_all(f"  Size reduction: {reduction:.1f}%", end="\n")
                        t1 = time.time()
                        ws.append([
                            str(rel_path), f"{original_size_kb:.2f}", str(quality), f"{final_size_kb:.2f}", f"{reduction:.1f}", str(output_file.relative_to(output_path)), f"{t1-t0:.2f}"
                        ])
                    log_to_all(f"  Saved as: {output_file.relative_to(output_path)}", end="\n\n")
                    root.update_idletasks()
                except Exception as e:
                    log_to_all(f"  Error processing {str(rel_path)}: {e}", end="\n\n")
                    root.update_idletasks()
                completed_steps += 1
                total_progress['value'] = completed_steps
                root.update_idletasks()

            run_btn.config(state="normal")

            excel_path = Path(LOG_FOLDER) / Path(LOG_FILE).with_suffix('.xlsx')
            wb.save(excel_path)
            log_to_all(f"✅ Done! Log written to: {log_path} and {excel_path}", end="\n")
            run_btn.config(state="normal")


    try:
        root = tk.Tk()
        root.title("Image Resizer Settings")
        frm = tk.Frame(root, padx=12, pady=12)
        frm.pack(fill=tk.BOTH, expand=True)

        # --- Basic Settings ---
        settings_frame = ttk.LabelFrame(frm, text="Basic Settings", padding=(10, 5))
        settings_frame.grid(row=0, column=0, columnspan=3, sticky="ew", pady=5)
        
        # Target file size
        tk.Label(settings_frame, text="Target File Size (KB):").grid(row=0, column=0, sticky="e", pady=2)
        file_size_var = tk.StringVar(value=str(TARGET_FILE_SIZE_KB))
        file_size_entry = tk.Entry(settings_frame, textvariable=file_size_var, width=10)
        file_size_entry.grid(row=0, column=1, sticky="w", pady=2)
        ToolTip(file_size_entry, TOOLTIPS["TARGET_FILE_SIZE_KB"])

        # Input folder
        tk.Label(settings_frame, text="Input Folder:").grid(row=1, column=0, sticky="e", pady=2)
        in_folder_var = tk.StringVar(value=INPUT_FOLDER)
        in_folder_entry = tk.Entry(settings_frame, textvariable=in_folder_var, width=40)
        in_folder_entry.grid(row=1, column=1, sticky="w", pady=2)
        ToolTip(in_folder_entry, TOOLTIPS["INPUT_FOLDER"])
        def browse_in():
            folder = filedialog.askdirectory()
            if folder:
                in_folder_var.set(folder)
        tk.Button(settings_frame, text="Browse", command=browse_in).grid(row=1, column=2, sticky="w", padx=5)

        # Output folder
        tk.Label(settings_frame, text="Output Folder:").grid(row=2, column=0, sticky="e", pady=2)
        out_folder_var = tk.StringVar(value=OUTPUT_FOLDER)
        out_folder_entry = tk.Entry(settings_frame, textvariable=out_folder_var, width=40)
        out_folder_entry.grid(row=2, column=1, sticky="w", pady=2)
        ToolTip(out_folder_entry, TOOLTIPS["OUTPUT_FOLDER"])
        def browse_out():
            folder = filedialog.askdirectory()
            if folder:
                out_folder_var.set(folder)
        tk.Button(settings_frame, text="Browse", command=browse_out).grid(row=2, column=2, sticky="w", padx=5)

        # Output format
        tk.Label(settings_frame, text="Output Format:").grid(row=3, column=0, sticky="e", pady=2)
        format_var = tk.StringVar(value=OUTPUT_FORMAT)
        format_combo = ttk.Combobox(settings_frame, textvariable=format_var, values=["JPEG", "PNG", "WEBP", "HEIF"], state="readonly", width=10)
        format_combo.grid(row=3, column=1, sticky="w", pady=2)
        ToolTip(format_combo, TOOLTIPS["OUTPUT_FORMAT"])

        # Output naming method
        tk.Label(settings_frame, text="Output Naming Method:").grid(row=4, column=0, sticky="e", pady=2)
        naming_var = tk.StringVar(value=OUTPUT_NAMING_MODE)
        naming_combo = ttk.Combobox(settings_frame, textvariable=naming_var, values=["prefix", "folder"], state="readonly", width=10)
        naming_combo.grid(row=4, column=1, sticky="w", pady=2)
        ToolTip(naming_combo, TOOLTIPS["OUTPUT_NAMING_MODE"])

        # --- Resolution Scaling ---
        scaling_frame = ttk.LabelFrame(frm, text="Resolution Scaling", padding=(10, 5))
        scaling_frame.grid(row=1, column=0, columnspan=3, sticky="ew", pady=5)
        
        tk.Label(scaling_frame, text="Mode:").grid(row=0, column=0, sticky="e", pady=2)
        scale_mode_var = tk.StringVar(value="Off")
        scale_mode_combo = ttk.Combobox(scaling_frame, textvariable=scale_mode_var, values=["Off", "By Percentage", "By Target Dimensions"], state="readonly", width=20)
        scale_mode_combo.grid(row=0, column=1, sticky="w", pady=2)
        ToolTip(scale_mode_combo, TOOLTIPS["SCALE_MODE"])

        # Scaling by percentage
        tk.Label(scaling_frame, text="Scale by (%):").grid(row=1, column=0, sticky="e", pady=2)
        scale_percent_var = tk.StringVar(value="50")
        scale_percent_slider = ttk.Scale(scaling_frame, from_=1, to=100, orient=tk.HORIZONTAL, length=150, variable=scale_percent_var)
        scale_percent_slider.grid(row=1, column=1, sticky="w", pady=2)
        scale_percent_entry = tk.Entry(scaling_frame, textvariable=scale_percent_var, width=5)
        scale_percent_entry.grid(row=1, column=2, sticky="w", padx=5)
        ToolTip(scale_percent_slider, TOOLTIPS["SCALE_PERCENT"])
        
        # Scaling by dimensions
        tk.Label(scaling_frame, text="Target Width (px):").grid(row=2, column=0, sticky="e", pady=2)
        scale_width_var = tk.StringVar(value="")
        scale_width_entry = tk.Entry(scaling_frame, textvariable=scale_width_var, width=8)
        scale_width_entry.grid(row=2, column=1, sticky="w", pady=2)
        ToolTip(scale_width_entry, TOOLTIPS["SCALE_WIDTH"])
        
        tk.Label(scaling_frame, text="Target Height (px):").grid(row=2, column=2, sticky="e", padx=5)
        scale_height_var = tk.StringVar(value="")
        scale_height_entry = tk.Entry(scaling_frame, textvariable=scale_height_var, width=8)
        scale_height_entry.grid(row=2, column=3, sticky="w", pady=2)
        ToolTip(scale_height_entry, TOOLTIPS["SCALE_HEIGHT"])

        # --- Conditional Scaling ---
        cond_frame = ttk.LabelFrame(frm, text="Conditional Scaling", padding=(10, 5))
        cond_frame.grid(row=2, column=0, columnspan=3, sticky="ew", pady=5)

        scale_condition_var = tk.StringVar(value="Off")
        cond_check = tk.Checkbutton(cond_frame, text="Only scale if:", variable=scale_condition_var, onvalue="On", offvalue="Off")
        cond_check.grid(row=0, column=0, sticky="w")
        ToolTip(cond_check, TOOLTIPS["SCALE_CONDITION"])
        
        tk.Label(cond_frame, text="Logic:").grid(row=0, column=1, sticky="e", padx=5)
        scale_cond_logic_var = tk.StringVar(value="AND (All conditions met)")
        scale_cond_logic_combo = ttk.Combobox(cond_frame, textvariable=scale_cond_logic_var, values=["AND (All conditions met)", "OR (Any condition met)"], state="readonly", width=22)
        scale_cond_logic_combo.grid(row=0, column=2, columnspan=2, sticky="w")
        ToolTip(scale_cond_logic_combo, TOOLTIPS["SCALE_COND_LOGIC"])

        tk.Label(cond_frame, text="Width >").grid(row=1, column=0, sticky="e", pady=2)
        scale_cond_width_var = tk.StringVar(value="")
        scale_cond_width_entry = tk.Entry(cond_frame, textvariable=scale_cond_width_var, width=8)
        scale_cond_width_entry.grid(row=1, column=1, sticky="w", pady=2)
        ToolTip(scale_cond_width_entry, TOOLTIPS["SCALE_COND_WIDTH"])
        
        tk.Label(cond_frame, text="Height >").grid(row=1, column=2, sticky="e", padx=5)
        scale_cond_height_var = tk.StringVar(value="")
        scale_cond_height_entry = tk.Entry(cond_frame, textvariable=scale_cond_height_var, width=8)
        scale_cond_height_entry.grid(row=1, column=3, sticky="w", pady=2)
        ToolTip(scale_cond_height_entry, TOOLTIPS["SCALE_COND_HEIGHT"])
        

        # --- Folder Settings ---
        folder_frame = ttk.LabelFrame(frm, text="Folder Settings", padding=(10, 5))
        folder_frame.grid(row=3, column=0, columnspan=3, sticky="ew", pady=5)

        # Log folder
        tk.Label(folder_frame, text="Log Folder:").grid(row=0, column=0, sticky="e", pady=2)
        log_folder_var = tk.StringVar(value=LOG_FOLDER)
        log_folder_entry = tk.Entry(folder_frame, textvariable=log_folder_var, width=40)
        log_folder_entry.grid(row=0, column=1, sticky="w", pady=2)
        ToolTip(log_folder_entry, TOOLTIPS["LOG_FOLDER"])
        def browse_log():
            folder = filedialog.askdirectory()
            if folder:
                log_folder_var.set(folder)
        tk.Button(folder_frame, text="Browse", command=browse_log).grid(row=0, column=2, sticky="w", padx=5)

        # Log file
        tk.Label(folder_frame, text="Log File:").grid(row=1, column=0, sticky="e", pady=2)
        log_file_var = tk.StringVar(value=LOG_FILE)
        log_file_entry = tk.Entry(folder_frame, textvariable=log_file_var, width=40)
        log_file_entry.grid(row=1, column=1, sticky="w", pady=2)
        ToolTip(log_file_entry, TOOLTIPS["LOG_FILE"])

        # --- Progress and Logging ---
        progress_frame = ttk.LabelFrame(frm, text="Progress and Logging", padding=(10, 5))
        progress_frame.grid(row=4, column=0, columnspan=3, sticky="ew", pady=5)

        tk.Label(progress_frame, text="Total Progress:").grid(row=0, column=0, sticky="e", pady=5)
        total_progress = ttk.Progressbar(progress_frame, length=400, mode="determinate")
        total_progress.grid(row=0, column=1, columnspan=2, sticky="w", pady=5, padx=5)

        tk.Label(progress_frame, text="Log:").grid(row=1, column=0, sticky="ne", pady=5)
        log_console = tk.Text(progress_frame, height=12, width=80, state="normal")
        log_console.grid(row=1, column=1, columnspan=2, sticky="w", pady=5, padx=5)

        # --- Run Button ---
        run_btn = tk.Button(frm, text="Run", command=run_process, bg="#4CAF50", fg="white", padx=10, pady=5, font=("sans-serif", 10, "bold"))
        run_btn.grid(row=5, column=0, columnspan=3, pady=12)

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

def compress_image(image_path, target_size_kb, log_quality=None, log_size=None, initial_quality=95, scale_settings=None):
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
        # --- Image Scaling ---
        if scale_settings and scale_settings["mode"] != "Off":
            apply_scale = False
            if scale_settings["condition"] != "On":
                apply_scale = True
            else:
                cond_w = scale_settings["cond_width"]
                cond_h = scale_settings["cond_height"]
                cond_logic = scale_settings["cond_logic"]

                w_cond_active = cond_w > 0
                h_cond_active = cond_h > 0
                w_cond_met = img.width > cond_w
                h_cond_met = img.height > cond_h

                if cond_logic == "OR (Any condition met)":
                    if (w_cond_active and w_cond_met) or \
                       (h_cond_active and h_cond_met):
                        apply_scale = True
                elif cond_logic == "AND (All conditions met)":
                    passes_w = not w_cond_active or w_cond_met
                    passes_h = not h_cond_active or h_cond_met
                    if passes_w and passes_h and (w_cond_active or h_cond_active):
                        apply_scale = True
            
            if apply_scale:
                original_dims = img.size
                if scale_settings["mode"] == "By Percentage":
                    percent = scale_settings["percent"]
                    new_w = int(img.width * percent / 100)
                    new_h = int(img.height * percent / 100)
                    img = img.resize((new_w, new_h), Image.Resampling.LANCZOS)
                elif scale_settings["mode"] == "By Target Dimensions":
                    target_w = scale_settings["width"]
                    target_h = scale_settings["height"]
                    img.thumbnail((target_w, target_h), Image.Resampling.LANCZOS)

        img = prepare_image(img, OUTPUT_FORMAT)

        min_quality = 1
        output_format_upper = OUTPUT_FORMAT.upper()
        max_quality = 100
        
        is_lossless = output_format_upper in ['PNG']
        is_heif = output_format_upper in ['HEIF', 'HEIC']
        
        # For lossless formats, just save once
        if is_lossless:
            buffer = io.BytesIO()
            img.save(buffer, format='PNG', optimize=True, compress_level=9)
            current_size_kb = len(buffer.getvalue()) / 1024
            return buffer.getvalue(), 100, current_size_kb
        
        def get_size_for_quality(quality):
            buffer = io.BytesIO()
            save_kwargs = {}
            if output_format_upper == "WEBP":
                save_kwargs = {'format': 'WEBP', 'quality': quality, 'method': 6}
            elif is_heif:
                save_kwargs = {'format': 'HEIF', 'quality': quality}
            else: # JPEG
                save_kwargs = {'format': 'JPEG', 'quality': quality, 'optimize': True}
            
            try:
                img.save(buffer, **save_kwargs)
            except Exception as e:
                raise RuntimeError(f"Failed saving as {OUTPUT_FORMAT}: {e}")
            
            b = buffer.getvalue()
            s = len(b) / 1024
            return b, s

        tried = set()
        history = []  # Store (quality, size, bytes)
        last_two = []  # Track last two results for bracketing check

        # Step 1: Start with the initial guess
        q_initial = max(min_quality, min(max_quality, initial_quality))
        if log_quality: log_quality(f"Trying quality: {q_initial}")
        bytes_initial, size_initial = get_size_for_quality(q_initial)
        if log_size: log_size(f"{size_initial:.2f} KB")
        
        history.append((q_initial, size_initial, bytes_initial))
        last_two.append((q_initial, size_initial, bytes_initial))
        tried.add(q_initial)
        
        # Step 2: Establish bounds based on the initial try
        if size_initial > target_size_kb:
            # Guess is too large, so we need to find a quality that results in a smaller size.
            # The best lower bound is quality 1.
            q_low = 1
            if q_low not in tried:
                if log_quality: log_quality(f"Trying quality: {q_low}")
                bytes_low, size_low = get_size_for_quality(q_low)
                if log_size: log_size(f"{size_low:.2f} KB")
                history.append((q_low, size_low, bytes_low))
                last_two.append((q_low, size_low, bytes_low)); last_two.pop(0)
                tried.add(q_low)
                
                if size_low > target_size_kb:
                    return bytes_low, q_low, size_low # Even lowest quality is too big
        else:
            # Guess is smaller or equal, so we might be able to get higher quality.
            # The best upper bound is max_quality.
            q_high = max_quality
            if q_high not in tried:
                if log_quality: log_quality(f"Trying quality: {q_high}")
                bytes_high, size_high = get_size_for_quality(q_high)
                if log_size: log_size(f"{size_high:.2f} KB")
                history.append((q_high, size_high, bytes_high))
                last_two.append((q_high, size_high, bytes_high)); last_two.pop(0)
                tried.add(q_high)

                if size_high <= target_size_kb:
                    return bytes_high, q_high, size_high # Max quality is under target

        # Step 3 and onwards: Use interpolation
        step = 50.0 # Start with a larger step
        try_count = len(tried)
        
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
            
            current_bytes, current_size_kb = get_size_for_quality(next_quality)

            history.append((next_quality, current_size_kb, current_bytes))
            last_two.append((next_quality, current_size_kb, current_bytes))
            if len(last_two) > 2:
                last_two.pop(0)
            tried.add(next_quality)
            
            if log_size:
                log_size(f"{current_size_kb:.2f} KB")
            
            # Check if last two consecutive tries bracket the target
            if len(last_two) == 2 and try_count >= 2: # Check earlier
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
                    initial_quality_guess = int(max(1, min(100, 100 * (TARGET_FILE_SIZE_KB / original_size_kb) * 1.5)))
                    compressed_bytes, quality, final_size_kb = compress_image(
                        image_file, 
                        TARGET_FILE_SIZE_KB,
                        initial_quality=initial_quality_guess
                    )
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
