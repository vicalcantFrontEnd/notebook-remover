"""
Tkinter GUI for NotebookLM Watermark Remover.
"""

import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from pathlib import Path
from threading import Thread
import cv2
import numpy as np
from PIL import Image, ImageTk

from watermark_remover import (
    extract_first_frame,
    detect_watermark_region,
    process_video,
    create_pixel_mask,
    create_box_mask,
    inpaint_frame,
    crop_frame,
    REMOVAL_METHODS,
)

PREVIEW_MAX_W = 800
PREVIEW_MAX_H = 480


class WatermarkRemoverApp:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("NotebookLM Watermark Remover")
        self.root.resizable(True, True)
        self.root.minsize(900, 680)

        # State
        self.video_path = None
        self.original_frame = None
        self.video_info = None
        self.region = None
        self.scale_factor = 1.0
        self.processing = False
        self.cancel_requested = False
        self._drag_start = None

        self._build_ui()

    # ------------------------------------------------------------------ UI
    def _build_ui(self):
        root = self.root
        root.configure(bg="#1e1e2e")

        style = ttk.Style()
        style.theme_use("clam")
        style.configure("TFrame", background="#1e1e2e")
        style.configure("TLabel", background="#1e1e2e", foreground="#cdd6f4", font=("Segoe UI", 10))
        style.configure("Header.TLabel", font=("Segoe UI", 13, "bold"), foreground="#89b4fa")
        style.configure("TButton", font=("Segoe UI", 10))
        style.configure("Accent.TButton", font=("Segoe UI", 10, "bold"))
        style.configure("TSpinbox", font=("Segoe UI", 10))
        style.configure("TRadiobutton", background="#1e1e2e", foreground="#cdd6f4", font=("Segoe UI", 10))

        # -- Top bar
        top = ttk.Frame(root)
        top.pack(fill="x", padx=16, pady=(16, 8))
        ttk.Label(top, text="NotebookLM Watermark Remover", style="Header.TLabel").pack(side="left")

        # -- File selection
        file_frame = ttk.Frame(root)
        file_frame.pack(fill="x", padx=16, pady=4)
        self.btn_open = ttk.Button(file_frame, text="Select Video", command=self._on_open)
        self.btn_open.pack(side="left")
        self.lbl_file = ttk.Label(file_frame, text="No file selected", foreground="#6c7086")
        self.lbl_file.pack(side="left", padx=(12, 0))

        # -- Canvas (preview)
        canvas_frame = ttk.Frame(root)
        canvas_frame.pack(fill="both", expand=True, padx=16, pady=8)
        self.canvas = tk.Canvas(
            canvas_frame, bg="#181825", highlightthickness=1,
            highlightbackground="#313244", cursor="cross",
        )
        self.canvas.pack(fill="both", expand=True)
        self.canvas.bind("<ButtonPress-1>", self._on_mouse_down)
        self.canvas.bind("<B1-Motion>", self._on_mouse_drag)
        self.canvas.bind("<ButtonRelease-1>", self._on_mouse_up)

        # -- Controls row 1: detection + preview
        ctrl1 = ttk.Frame(root)
        ctrl1.pack(fill="x", padx=16, pady=2)

        self.btn_detect = ttk.Button(ctrl1, text="Auto-detect", command=self._on_auto_detect, state="disabled")
        self.btn_detect.pack(side="left")

        self.btn_reset = ttk.Button(ctrl1, text="Reset Region", command=self._on_reset_region, state="disabled")
        self.btn_reset.pack(side="left", padx=(8, 0))

        self.btn_preview = ttk.Button(ctrl1, text="Preview Result", command=self._on_preview, state="disabled")
        self.btn_preview.pack(side="left", padx=(8, 0))

        ttk.Label(ctrl1, text="Trim final (sec):").pack(side="left", padx=(24, 4))
        self.trim_var = tk.DoubleVar(value=0.0)
        self.spin_trim = ttk.Spinbox(ctrl1, from_=0, to=30, increment=0.5,
                                     textvariable=self.trim_var, width=6, state="disabled")
        self.spin_trim.pack(side="left")

        # -- Controls row 2: method + parameters
        ctrl2 = ttk.Frame(root)
        ctrl2.pack(fill="x", padx=16, pady=2)

        ttk.Label(ctrl2, text="Method:").pack(side="left")
        self.method_var = tk.StringVar(value="pixel")
        for m in REMOVAL_METHODS:
            desc = {"pixel": "Pixel mask (best)", "box": "Box inpaint", "crop": "Crop/zoom"}[m]
            ttk.Radiobutton(ctrl2, text=desc, variable=self.method_var, value=m,
                            command=self._on_method_change).pack(side="left", padx=(8, 0))

        ttk.Label(ctrl2, text="  Sensitivity:").pack(side="left", padx=(16, 4))
        self.sensitivity_var = tk.IntVar(value=30)
        self.spin_sensitivity = ttk.Spinbox(ctrl2, from_=5, to=80, increment=5,
                                            textvariable=self.sensitivity_var, width=4, state="disabled")
        self.spin_sensitivity.pack(side="left")

        ttk.Label(ctrl2, text="  Radius:").pack(side="left", padx=(12, 4))
        self.radius_var = tk.IntVar(value=3)
        self.spin_radius = ttk.Spinbox(ctrl2, from_=1, to=15, increment=1,
                                       textvariable=self.radius_var, width=4, state="disabled")
        self.spin_radius.pack(side="left")

        # -- Progress + action
        bottom = ttk.Frame(root)
        bottom.pack(fill="x", padx=16, pady=(4, 16))

        self.progress = ttk.Progressbar(bottom, mode="determinate")
        self.progress.pack(fill="x", side="left", expand=True, padx=(0, 12))

        self.lbl_status = ttk.Label(bottom, text="Ready", foreground="#a6adc8", width=32, anchor="w")
        self.lbl_status.pack(side="left", padx=(0, 12))

        self.btn_process = ttk.Button(bottom, text="Process Video", style="Accent.TButton",
                                      command=self._on_process, state="disabled")
        self.btn_process.pack(side="right")

        self.btn_cancel = ttk.Button(bottom, text="Cancel", command=self._on_cancel, state="disabled")
        self.btn_cancel.pack(side="right", padx=(0, 8))

    # ------------------------------------------------------------ Actions
    def _on_open(self):
        path = filedialog.askopenfilename(
            title="Select MP4 Video",
            filetypes=[("MP4 Videos", "*.mp4"), ("All Videos", "*.mp4;*.mkv;*.avi;*.mov;*.webm"), ("All files", "*.*")],
        )
        if not path:
            return

        self.video_path = path
        self.lbl_file.config(text=Path(path).name)
        self.lbl_status.config(text="Loading preview...")
        self.root.update_idletasks()

        try:
            self.original_frame, self.video_info = extract_first_frame(path)
        except Exception as e:
            messagebox.showerror("Error", f"Could not load video:\n{e}")
            self.lbl_status.config(text="Ready")
            return

        self._display_preview()
        self._on_auto_detect()

        for w in (self.btn_detect, self.btn_reset, self.btn_preview, self.btn_process,
                  self.spin_trim, self.spin_radius, self.spin_sensitivity):
            w.config(state="normal")

        info = self.video_info
        self.lbl_status.config(
            text=f"{info['width']}x{info['height']}  |  {info['fps']:.1f} fps  |  {info['duration']:.1f}s"
        )

    def _on_auto_detect(self):
        if self.original_frame is None:
            return
        self.region = detect_watermark_region(self.original_frame)
        self._display_preview()
        self._draw_region()

    def _on_reset_region(self):
        self.region = None
        self._display_preview()
        self._draw_region()

    def _on_method_change(self):
        """Enable/disable controls depending on method."""
        m = self.method_var.get()
        if m == "crop":
            self.spin_sensitivity.config(state="disabled")
            self.spin_radius.config(state="disabled")
        elif m == "pixel":
            self.spin_sensitivity.config(state="normal")
            self.spin_radius.config(state="normal")
        else:
            self.spin_sensitivity.config(state="disabled")
            self.spin_radius.config(state="normal")

    def _on_preview(self):
        """Show the first frame with watermark removal applied."""
        if self.original_frame is None or not self.region:
            return

        method = self.method_var.get()
        radius = self.radius_var.get()
        sensitivity = self.sensitivity_var.get()

        if method == "pixel":
            mask = create_pixel_mask(self.original_frame, self.region, sensitivity=sensitivity)
            cleaned = inpaint_frame(self.original_frame, mask, radius)
        elif method == "box":
            mask = create_box_mask(self.original_frame.shape, self.region)
            cleaned = inpaint_frame(self.original_frame, mask, radius)
        else:
            cleaned = crop_frame(self.original_frame, self.region)

        self._show_frame(cleaned)
        self.lbl_status.config(text=f"Preview [{method}]  (Auto-detect / Reset to go back)")

    def _show_frame(self, frame_bgr):
        h, w = frame_bgr.shape[:2]
        canvas_w = self.canvas.winfo_width() or PREVIEW_MAX_W
        canvas_h = self.canvas.winfo_height() or PREVIEW_MAX_H
        scale = min(canvas_w / w, canvas_h / h, 1.0)
        self.scale_factor = scale

        new_w, new_h = int(w * scale), int(h * scale)
        rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
        resized = cv2.resize(rgb, (new_w, new_h), interpolation=cv2.INTER_AREA)

        self._preview_image = ImageTk.PhotoImage(Image.fromarray(resized))
        self.canvas.delete("all")
        self._img_offset_x = (canvas_w - new_w) // 2
        self._img_offset_y = (canvas_h - new_h) // 2
        self.canvas.create_image(
            self._img_offset_x, self._img_offset_y,
            anchor="nw", image=self._preview_image, tags="preview",
        )

    def _on_cancel(self):
        self.cancel_requested = True

    def _on_process(self):
        if self.processing or not self.video_path:
            return
        if not self.region:
            messagebox.showwarning("No region", "Draw or auto-detect a watermark region first.")
            return

        default_name = Path(self.video_path).stem + "_clean.mp4"
        output = filedialog.asksaveasfilename(
            title="Save Cleaned Video", defaultextension=".mp4",
            initialfile=default_name, filetypes=[("MP4", "*.mp4")],
        )
        if not output:
            return

        self.processing = True
        self.cancel_requested = False
        self.btn_process.config(state="disabled")
        self.btn_cancel.config(state="normal")
        self.btn_open.config(state="disabled")
        self.progress["value"] = 0

        trim = self.trim_var.get()
        radius = self.radius_var.get()
        method = self.method_var.get()
        sensitivity = self.sensitivity_var.get()

        Thread(
            target=self._run_processing,
            args=(self.video_path, output, self.region, trim, radius, method, sensitivity),
            daemon=True,
        ).start()

    def _run_processing(self, inp, out, region, trim, radius, method, sensitivity):
        def on_progress(current, total):
            if total > 0:
                pct = min(100, current / total * 100)
                self.root.after(0, self._update_progress, pct, current, total)
        try:
            count = process_video(
                inp, out, region,
                trim_end_seconds=trim,
                inpaint_radius=radius,
                method=method,
                sensitivity=sensitivity,
                progress_callback=on_progress,
                cancel_flag=lambda: self.cancel_requested,
            )
            if self.cancel_requested:
                self.root.after(0, self._processing_done, "Cancelled.", False)
            else:
                self.root.after(0, self._processing_done, f"Done! {count} frames processed.", True)
        except Exception as e:
            self.root.after(0, self._processing_done, f"Error: {e}", False)

    def _update_progress(self, pct, current, total):
        self.progress["value"] = pct
        self.lbl_status.config(text=f"Processing... {current}/{total} frames")

    def _processing_done(self, msg, success):
        self.processing = False
        self.progress["value"] = 100 if success else 0
        self.lbl_status.config(text=msg)
        self.btn_process.config(state="normal")
        self.btn_cancel.config(state="disabled")
        self.btn_open.config(state="normal")
        if success:
            messagebox.showinfo("Complete", msg)

    # ------------------------------------------------------------ Canvas
    def _display_preview(self):
        if self.original_frame is None:
            return
        self._show_frame(self.original_frame)

    def _draw_region(self):
        self.canvas.delete("region")
        self.canvas.delete("region_label")
        if not self.region:
            return

        x, y, rw, rh = self.region
        s = self.scale_factor
        ox = getattr(self, "_img_offset_x", 0)
        oy = getattr(self, "_img_offset_y", 0)

        sx = ox + x * s
        sy = oy + y * s
        ex = ox + (x + rw) * s
        ey = oy + (y + rh) * s

        self.canvas.create_rectangle(
            sx, sy, ex, ey,
            outline="#f38ba8", width=2, dash=(6, 3), tags="region",
        )
        self.canvas.create_text(
            sx, sy - 4, anchor="sw",
            text=f"Watermark  ({rw}x{rh}px)",
            fill="#f38ba8", font=("Segoe UI", 9), tags="region_label",
        )

    # Mouse handlers for rectangle selection
    def _canvas_to_frame(self, cx, cy):
        ox = getattr(self, "_img_offset_x", 0)
        oy = getattr(self, "_img_offset_y", 0)
        s = self.scale_factor or 1.0
        fx = (cx - ox) / s
        fy = (cy - oy) / s
        if self.original_frame is not None:
            h, w = self.original_frame.shape[:2]
            fx = max(0, min(fx, w))
            fy = max(0, min(fy, h))
        return fx, fy

    def _on_mouse_down(self, event):
        if self.original_frame is None or self.processing:
            return
        self._drag_start = (event.x, event.y)

    def _on_mouse_drag(self, event):
        if not self._drag_start or self.original_frame is None:
            return
        self.canvas.delete("drag_rect")
        x0, y0 = self._drag_start
        self.canvas.create_rectangle(
            x0, y0, event.x, event.y,
            outline="#a6e3a1", width=2, dash=(4, 2), tags="drag_rect",
        )

    def _on_mouse_up(self, event):
        if not self._drag_start or self.original_frame is None:
            return
        self.canvas.delete("drag_rect")
        x0, y0 = self._drag_start
        x1, y1 = event.x, event.y
        self._drag_start = None

        if abs(x1 - x0) < 8 or abs(y1 - y0) < 8:
            return

        fx0, fy0 = self._canvas_to_frame(min(x0, x1), min(y0, y1))
        fx1, fy1 = self._canvas_to_frame(max(x0, x1), max(y0, y1))
        self.region = (int(fx0), int(fy0), int(fx1 - fx0), int(fy1 - fy0))
        self._draw_region()

    # ---------------------------------------------------------------- Run
    def run(self):
        self.root.mainloop()
