import threading
import tkinter as tk
from typing import Optional
from tkinter import filedialog, messagebox, ttk

from config import AppConfig
from image_api import ProcessingController, process_images

# Tooltip texts used across the UI
TOOLTIPS = {
    "TARGET_FILE_SIZE_KB": "Output target size in KB",
    "INPUT_FOLDER": "Input folder containing images",
    "OUTPUT_FOLDER": "Output folder for resized images",
    "OUTPUT_FORMAT": "The format to use for saving the output images.",
    "OUTPUT_NAMING_MODE": "How output files are named and organized.",
    "LOG_FOLDER": "Folder for logs",
    "LOG_FILE": "Log file name",
    "WEBP_METHOD": "WEBP compression method (0=fastest, 6=best).\nControls the trade-off between encoding speed and file size.",
    "METHOD_TUNING_THRESHOLD": "Only tune WEBP method if the best found size is below this percentage of the target.\n(e.g., 95 means tuning will only run if size is < 95% of target). Avoids tuning when already very close.",
    "SCALE_MODE": "Off: No resizing.\nBy Percentage: Scale image by a percentage.\nBy Target Dimensions: Resize to fit within a specific width/height, maintaining aspect ratio.",
    "SCALE_PERCENT": "The percentage to scale the image resolution by (e.g., 50%).",
    "SCALE_WIDTH": "The target width in pixels.",
    "SCALE_HEIGHT": "The target height in pixels.",
    "SCALE_CONDITION": "Enable or disable conditional scaling.",
    "SCALE_COND_WIDTH": "Only scale if image width is greater than this value.",
    "SCALE_COND_HEIGHT": "Only scale if image height is greater than this value.",
    "SCALE_COND_LOGIC": "OR: Scale if any condition is met.\nAND: Scale only if all conditions are met.",
}


class ToolTip:
    def __init__(self, widget, text: str):
        self.widget = widget
        self.text = text
        self.tipwindow = None
        widget.bind("<Enter>", self.show_tip)
        widget.bind("<Leave>", self.hide_tip)

    def show_tip(self, _event=None):
        if self.tipwindow or not self.text:
            return
        try:
            x, y, cx, cy = self.widget.bbox("insert")
        except Exception:
            x, y = 0, 0
        x = x + self.widget.winfo_rootx() + 25
        y = y + self.widget.winfo_rooty() + 20
        self.tipwindow = tw = tk.Toplevel(self.widget)
        tw.wm_overrideredirect(True)
        tw.wm_geometry(f"+{x}+{y}")
        label = tk.Label(
            tw,
            text=self.text,
            justify=tk.LEFT,
            background="#ffffe0",
            relief=tk.SOLID,
            borderwidth=1,
            font=("tahoma", "8", "normal"),
        )
        label.pack(ipadx=1)

    def hide_tip(self, _event=None):
        tw = self.tipwindow
        self.tipwindow = None
        if tw:
            tw.destroy()


def launch_gui():
    controller: Optional[ProcessingController] = None
    run_bg_default = pause_bg_default = continue_bg_default = skip_bg_default = stop_bg_default = None

    def set_running_state(running: bool, paused: bool = False):
        run_btn.config(state="disabled" if running else "normal")
        pause_btn.config(state="normal" if running and not paused else "disabled")
        continue_btn.config(state="normal" if running and paused else "disabled")
        skip_btn.config(state="normal" if running else "disabled")
        stop_btn.config(state="normal" if running else "disabled")

        # Visual feedback
        if paused:
            pause_btn.config(bg="#f0ad4e", fg="black")  # amber
            continue_btn.config(bg="#0275d8", fg="white")  # blue
        else:
            pause_btn.config(bg=pause_bg_default, fg="black")
            continue_btn.config(bg=continue_bg_default, fg="black")

        if running and not paused:
            run_btn.config(bg="#5cb85c", fg="white")  # green
        else:
            run_btn.config(bg=run_bg_default, fg="black")

        if running:
            skip_btn.config(bg="#5bc0de", fg="white")  # light blue
            stop_btn.config(bg="#d9534f", fg="white")  # red
        else:
            skip_btn.config(bg=skip_bg_default, fg="black")
            stop_btn.config(bg=stop_bg_default, fg="black")

    def on_pause():
        if controller:
            controller.pause()
            set_running_state(running=True, paused=True)

    def on_continue():
        if controller:
            controller.resume()
            set_running_state(running=True, paused=False)

    def on_skip():
        if controller:
            controller.request_skip()

    def on_stop():
        if controller:
            controller.stop()

    def run_process():
        nonlocal controller
        try:
            cfg = AppConfig(
                target_file_size_kb=int(file_size_var.get()),
                input_folder=in_folder_var.get(),
                output_folder=out_folder_var.get(),
                output_format=format_var.get(),
                output_naming_mode=naming_var.get(),
                webp_method=int(webp_method_var.get()),
                method_tuning_threshold=int(tuning_threshold_var.get()),
            )

            scale_settings = {
                "mode": scale_mode_var.get(),
                "percent": int(scale_percent_var.get()) if scale_percent_var.get() else 0,
                "width": int(scale_width_var.get()) if scale_width_var.get() else 0,
                "height": int(scale_height_var.get()) if scale_height_var.get() else 0,
                "condition": scale_condition_var.get(),
                "cond_width": int(scale_cond_width_var.get()) if scale_cond_width_var.get() else 0,
                "cond_height": int(scale_cond_height_var.get()) if scale_cond_height_var.get() else 0,
                "cond_logic": scale_cond_logic_var.get(),
                "webp_method": int(webp_method_var.get()),
                "tuning_threshold": int(tuning_threshold_var.get()) / 100.0,
            }
        except Exception as e:
            messagebox.showerror("Error", f"Invalid input: {e}")
            return

        controller = ProcessingController()
        log_console.delete("1.0", tk.END)
        total_progress["value"] = 0
        total_progress["maximum"] = 0
        root.update_idletasks()

        set_running_state(running=True, paused=False)
        threading.Thread(target=process_images_gui, args=(cfg, scale_settings, controller), daemon=True).start()

    def process_images_gui(cfg: AppConfig, scale_settings, controller: ProcessingController):
        def log_to_console(message: str):
            def _append():
                log_console.insert(tk.END, message + "\n")
                log_console.see(tk.END)
            root.after(0, _append)

        def log_quality(message: str):
            def _append():
                log_console.insert(tk.END, f"    {message}")
                log_console.see(tk.END)
            root.after(0, _append)

        def log_size(message: str):
            def _append():
                log_console.insert(tk.END, f"({message})\n")
                log_console.see(tk.END)
            root.after(0, _append)

        def update_progress(current: int, total: int):
            def _update():
                total_progress["maximum"] = max(total, 1)
                total_progress["value"] = current
            root.after(0, _update)

        try:
            process_images(
                cfg,
                scale_settings=scale_settings,
                on_log=log_to_console,
                on_quality=log_quality,
                on_size=log_size,
                on_progress=update_progress,
                controller=controller,
            )
        except Exception as exc:
            root.after(0, lambda: messagebox.showerror("Error", str(exc)))
        finally:
            root.after(0, lambda: set_running_state(running=False))

    # Build UI
    root = tk.Tk()
    root.title("Image Resizer Settings")
    frm = tk.Frame(root, padx=12, pady=12)
    frm.pack(fill=tk.BOTH, expand=True)

    # --- Basic Settings ---
    settings_frame = ttk.LabelFrame(frm, text="Basic Settings", padding=(10, 5))
    settings_frame.grid(row=0, column=0, columnspan=3, sticky="ew", pady=5)

    tk.Label(settings_frame, text="Target File Size (KB):").grid(row=0, column=0, sticky="e", pady=2)
    file_size_var = tk.StringVar(value="200")
    file_size_entry = tk.Entry(settings_frame, textvariable=file_size_var, width=10)
    file_size_entry.grid(row=0, column=1, sticky="w", pady=2)
    ToolTip(file_size_entry, TOOLTIPS["TARGET_FILE_SIZE_KB"])

    tk.Label(settings_frame, text="Input Folder:").grid(row=1, column=0, sticky="e", pady=2)
    in_folder_var = tk.StringVar(value="in")
    in_folder_entry = tk.Entry(settings_frame, textvariable=in_folder_var, width=40)
    in_folder_entry.grid(row=1, column=1, sticky="w", pady=2)
    ToolTip(in_folder_entry, TOOLTIPS["INPUT_FOLDER"])

    def browse_in():
        folder = filedialog.askdirectory()
        if folder:
            in_folder_var.set(folder)

    tk.Button(settings_frame, text="Browse", command=browse_in).grid(row=1, column=2, sticky="w", padx=5)

    tk.Label(settings_frame, text="Output Folder:").grid(row=2, column=0, sticky="e", pady=2)
    out_folder_var = tk.StringVar(value="out")
    out_folder_entry = tk.Entry(settings_frame, textvariable=out_folder_var, width=40)
    out_folder_entry.grid(row=2, column=1, sticky="w", pady=2)
    ToolTip(out_folder_entry, TOOLTIPS["OUTPUT_FOLDER"])

    def browse_out():
        folder = filedialog.askdirectory()
        if folder:
            out_folder_var.set(folder)

    tk.Button(settings_frame, text="Browse", command=browse_out).grid(row=2, column=2, sticky="w", padx=5)

    tk.Label(settings_frame, text="Output Format:").grid(row=3, column=0, sticky="e", pady=2)
    format_var = tk.StringVar(value="WEBP")
    format_combo = ttk.Combobox(settings_frame, textvariable=format_var, values=["JPEG", "PNG", "WEBP", "HEIF"], state="readonly", width=10)
    format_combo.grid(row=3, column=1, sticky="w", pady=2)
    ToolTip(format_combo, TOOLTIPS["OUTPUT_FORMAT"])

    tk.Label(settings_frame, text="Output Naming Method:").grid(row=4, column=0, sticky="e", pady=2)
    naming_var = tk.StringVar(value="folder")
    naming_combo = ttk.Combobox(settings_frame, textvariable=naming_var, values=["prefix", "folder"], state="readonly", width=10)
    naming_combo.grid(row=4, column=1, sticky="w", pady=2)
    ToolTip(naming_combo, TOOLTIPS["OUTPUT_NAMING_MODE"])

    tk.Label(settings_frame, text="WEBP Method:").grid(row=5, column=0, sticky="e", pady=2)
    webp_method_var = tk.StringVar(value="6")
    webp_method_combo = ttk.Combobox(settings_frame, textvariable=webp_method_var, values=[str(i) for i in range(7)], state="readonly", width=10)
    webp_method_combo.grid(row=5, column=1, sticky="w", pady=2)
    ToolTip(webp_method_combo, TOOLTIPS["WEBP_METHOD"])

    tk.Label(settings_frame, text="Tuning Threshold (%):").grid(row=6, column=0, sticky="e", pady=2)
    tuning_threshold_var = tk.StringVar(value="95")
    tuning_threshold_entry = tk.Entry(settings_frame, textvariable=tuning_threshold_var, width=10)
    tuning_threshold_entry.grid(row=6, column=1, sticky="w", pady=2)
    ToolTip(tuning_threshold_entry, TOOLTIPS["METHOD_TUNING_THRESHOLD"])

    # --- Resolution Scaling ---
    scaling_frame = ttk.LabelFrame(frm, text="Resolution Scaling", padding=(10, 5))
    scaling_frame.grid(row=1, column=0, columnspan=3, sticky="ew", pady=5)

    tk.Label(scaling_frame, text="Mode:").grid(row=0, column=0, sticky="e", pady=2)
    scale_mode_var = tk.StringVar(value="Off")
    scale_mode_combo = ttk.Combobox(scaling_frame, textvariable=scale_mode_var, values=["Off", "By Percentage", "By Target Dimensions"], state="readonly", width=20)
    scale_mode_combo.grid(row=0, column=1, sticky="w", pady=2)
    ToolTip(scale_mode_combo, TOOLTIPS["SCALE_MODE"])

    tk.Label(scaling_frame, text="Scale by (%):").grid(row=1, column=0, sticky="e", pady=2)
    scale_percent_var = tk.StringVar(value="50")
    scale_percent_slider = ttk.Scale(scaling_frame, from_=1, to=100, orient=tk.HORIZONTAL, length=150, variable=scale_percent_var)
    scale_percent_slider.grid(row=1, column=1, sticky="w", pady=2)
    scale_percent_entry = tk.Entry(scaling_frame, textvariable=scale_percent_var, width=5)
    scale_percent_entry.grid(row=1, column=2, sticky="w", padx=5)
    ToolTip(scale_percent_slider, TOOLTIPS["SCALE_PERCENT"])

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

    # --- Progress and Logging ---
    progress_frame = ttk.LabelFrame(frm, text="Progress and Logging", padding=(10, 5))
    progress_frame.grid(row=3, column=0, columnspan=3, sticky="ew", pady=5)

    tk.Label(progress_frame, text="Total Progress:").grid(row=0, column=0, sticky="e", pady=5)
    total_progress = ttk.Progressbar(progress_frame, length=400, mode="determinate")
    total_progress.grid(row=0, column=1, columnspan=2, sticky="w", pady=5, padx=5)

    tk.Label(progress_frame, text="Log:").grid(row=1, column=0, sticky="ne", pady=5)
    log_console = tk.Text(progress_frame, height=12, width=80, state="normal")
    log_console.grid(row=1, column=1, columnspan=2, sticky="w", pady=5, padx=5)

    # --- Controls ---
    controls_frame = tk.Frame(frm, pady=10)
    controls_frame.grid(row=4, column=0, columnspan=3)

    run_btn = tk.Button(controls_frame, text="Run", command=run_process, padx=10, pady=5, font=("sans-serif", 10, "bold"))
    run_btn.grid(row=0, column=0, padx=5)

    pause_btn = tk.Button(controls_frame, text="Pause", command=on_pause, padx=8, pady=5, state="disabled")
    pause_btn.grid(row=0, column=1, padx=5)

    continue_btn = tk.Button(controls_frame, text="Continue", command=on_continue, padx=8, pady=5, state="disabled")
    continue_btn.grid(row=0, column=2, padx=5)

    skip_btn = tk.Button(controls_frame, text="Skip", command=on_skip, padx=8, pady=5, state="disabled")
    skip_btn.grid(row=0, column=3, padx=5)

    stop_btn = tk.Button(controls_frame, text="Stop", command=on_stop, padx=8, pady=5, state="disabled")
    stop_btn.grid(row=0, column=4, padx=5)

    # Capture default colors after creation
    run_bg_default = run_btn.cget("bg")
    pause_bg_default = pause_btn.cget("bg")
    continue_bg_default = continue_btn.cget("bg")
    skip_bg_default = skip_btn.cget("bg")
    stop_bg_default = stop_btn.cget("bg")

    root.mainloop()


__all__ = ["launch_gui"]

