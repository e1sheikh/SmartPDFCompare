"""Optional, dependency-free Tk desktop viewer for one PDF comparison.

Importing this module never creates a window or imports Tk.  Call
``launch_viewer`` (or the separate console script) on a desktop Python build.
"""
from __future__ import annotations

from pathlib import Path
from typing import Sequence

import pymupdf

from .api import ComparisonOptions, compare_pdfs
from .exceptions import PDFComparisonError
from .highlighting import highlight_differences


def launch_viewer(old_pdf: str | Path | None = None, new_pdf: str | Path | None = None, *, options: ComparisonOptions | None = None) -> None:
    """Open a two-pane, page-synchronized comparison viewer.

    Tk is intentionally imported only here so headless/core consumers never
    require it. The viewer reuses ``compare_pdfs`` and its change geometry.
    """
    try:
        import tkinter as tk
        from tkinter import filedialog, messagebox, ttk
    except ImportError as exc:  # pragma: no cover - platform Python build
        raise RuntimeError("The optional viewer requires a Python build with tkinter.") from exc

    root = tk.Tk()
    root.title("SmartPDFCompare Viewer")
    root.geometry("1200x760")
    if old_pdf is None:
        old_pdf = filedialog.askopenfilename(title="Select original PDF", filetypes=[("PDF", "*.pdf")])
    if new_pdf is None:
        new_pdf = filedialog.askopenfilename(title="Select revised PDF", filetypes=[("PDF", "*.pdf")])
    if not old_pdf or not new_pdf:
        root.destroy()
        return

    try:
        result = compare_pdfs(old_pdf, new_pdf, options=options)
    except PDFComparisonError as exc:
        root.destroy()
        raise RuntimeError(f"Unable to compare PDFs: {exc}") from exc

    class _Viewer:
        def __init__(self) -> None:
            self.old_pdf, self.new_pdf, self.result = Path(old_pdf), Path(new_pdf), result
            self.changes = [mark for mark in result._markup if mark.changed]
            self.index = 0
            self.zoom = [1.0, 1.0]
            self.sync_zoom = tk.BooleanVar(value=True)
            self.sync_scroll = tk.BooleanVar(value=True)
            self.style = tk.StringVar(value="highlight")
            self._syncing = False
            self._photos: list[object | None] = [None, None]
            toolbar = ttk.Frame(root, padding=8)
            toolbar.pack(fill="x")
            ttk.Button(toolbar, text="‹ Previous change", command=lambda: self.move(-1)).pack(side="left")
            ttk.Button(toolbar, text="Next change ›", command=lambda: self.move(1)).pack(side="left", padx=(4, 16))
            ttk.Checkbutton(toolbar, text="Sync zoom", variable=self.sync_zoom).pack(side="left")
            ttk.Checkbutton(toolbar, text="Sync scroll", variable=self.sync_scroll).pack(side="left", padx=(8, 16))
            ttk.Button(toolbar, text="−", command=lambda: self.change_zoom(0, -0.15)).pack(side="left")
            ttk.Label(toolbar, text="Left zoom").pack(side="left")
            ttk.Button(toolbar, text="+", command=lambda: self.change_zoom(0, 0.15)).pack(side="left")
            ttk.Button(toolbar, text="−", command=lambda: self.change_zoom(1, -0.15)).pack(side="left", padx=(16, 0))
            ttk.Label(toolbar, text="Right zoom").pack(side="left")
            ttk.Button(toolbar, text="+", command=lambda: self.change_zoom(1, 0.15)).pack(side="left")
            ttk.Button(toolbar, text="Fit", command=self.fit_width).pack(side="left", padx=12)
            ttk.Combobox(toolbar, textvariable=self.style, values=("highlight", "box"), width=10, state="readonly").pack(side="right")
            ttk.Button(toolbar, text="Save annotated copies…", command=self.save).pack(side="right", padx=8)
            self.status = ttk.Label(root, anchor="w", padding=(8, 0))
            self.status.pack(fill="x")
            panes = ttk.Panedwindow(root, orient="horizontal")
            panes.pack(fill="both", expand=True, padx=8, pady=8)
            self.canvas: list[tk.Canvas] = []
            self.scrollbars: list[ttk.Scrollbar] = []
            for side, label in enumerate((f"Original — {self.old_pdf.name}", f"Revised — {self.new_pdf.name}")):
                frame = ttk.Labelframe(panes, text=label, padding=3)
                panes.add(frame, weight=1)
                scrollbar = ttk.Scrollbar(frame, orient="vertical")
                canvas = tk.Canvas(frame, background="#f1f5f9", highlightthickness=0)
                scrollbar.config(command=canvas.yview)
                canvas.config(yscrollcommand=lambda first, last, s=side: self.on_scroll(s, first, last))
                scrollbar.pack(side="right", fill="y")
                canvas.pack(fill="both", expand=True)
                canvas.bind("<Control-MouseWheel>", lambda event, s=side: self.wheel_zoom(event, s))
                canvas.bind("<MouseWheel>", lambda event, s=side: self.wheel_scroll(event, s))
                canvas.bind("<ButtonPress-1>", lambda event, s=side: self.begin_pan(event, s))
                canvas.bind("<B1-Motion>", lambda event, s=side: self.pan(event, s))
                self.canvas.append(canvas)
                self.scrollbars.append(scrollbar)
            self.render()

        def change_zoom(self, side: int, delta: float) -> None:
            value = min(3.0, max(0.35, self.zoom[side] + delta))
            self.zoom[side] = value
            if self.sync_zoom.get():
                self.zoom[1 - side] = value
            self.render()

        def wheel_zoom(self, event, side: int) -> str:
            self.change_zoom(side, 0.1 if event.delta > 0 else -0.1)
            return "break"

        def wheel_scroll(self, event, side: int) -> str:
            self.canvas[side].yview_scroll(-1 * (event.delta // 120), "units")
            return "break"

        def begin_pan(self, event, side: int) -> None:
            self.canvas[side].scan_mark(event.x, event.y)

        def pan(self, event, side: int) -> None:
            self.canvas[side].scan_dragto(event.x, event.y, gain=1)

        def fit_width(self) -> None:
            mark = self.changes[self.index] if self.changes else None
            for side, page_number in enumerate((mark.old_page if mark else 0, mark.new_page if mark else 0)):
                path = self.old_pdf if side == 0 else self.new_pdf
                if page_number is not None:
                    with pymupdf.open(path) as document:
                        self.zoom[side] = max(0.35, min(3.0, (self.canvas[side].winfo_width() - 16) / document[page_number].rect.width))
            if self.sync_zoom.get():
                shared = min(self.zoom)
                self.zoom = [shared, shared]
            self.render()

        def move(self, direction: int) -> None:
            if not self.changes:
                return
            self.index = min(max(self.index + direction, 0), len(self.changes) - 1)
            self.render()

        def on_scroll(self, side: int, first: str, last: str) -> None:
            self.scrollbars[side].set(first, last)
            if self.sync_scroll.get() and not self._syncing:
                self._syncing = True
                self.canvas[1 - side].yview_moveto(first)
                self._syncing = False

        def _render_side(self, side: int, page_number: int | None, rects: list[tuple[float, float, float, float]]) -> None:
            canvas = self.canvas[side]
            canvas.delete("all")
            if page_number is None:
                canvas.create_text(20, 20, anchor="nw", text="No matching page", fill="#64748b", font=("TkDefaultFont", 13))
                canvas.config(scrollregion=(0, 0, 400, 300))
                return
            path = self.old_pdf if side == 0 else self.new_pdf
            scale = self.zoom[side]
            with pymupdf.open(path) as document:
                page = document[page_number]
                pixmap = page.get_pixmap(matrix=pymupdf.Matrix(scale, scale), colorspace=pymupdf.csRGB, alpha=False)
            photo = tk.PhotoImage(data=pixmap.tobytes("png"))
            self._photos[side] = photo
            canvas.create_image(0, 0, anchor="nw", image=photo)
            color = "#dc2626" if side == 0 else "#16a34a"
            for x0, y0, x1, y1 in rects:
                canvas.create_rectangle(x0 * scale, y0 * scale, x1 * scale, y1 * scale, outline=color, width=2)
            canvas.config(scrollregion=(0, 0, pixmap.width, pixmap.height))

        def render(self) -> None:
            mark = self.changes[self.index] if self.changes else None
            self._render_side(0, mark.old_page if mark else 0, mark.old_rects if mark else [])
            self._render_side(1, mark.new_page if mark else 0, mark.new_rects if mark else [])
            if mark:
                self.status.config(text=f"Change {self.index + 1} of {len(self.changes)}")
            else:
                self.status.config(text="No text changes detected")

        def save(self) -> None:
            directory = filedialog.askdirectory(title="Save annotated PDF copies")
            if not directory:
                return
            try:
                outputs = highlight_differences(self.old_pdf, self.new_pdf, directory, result=self.result, style=self.style.get())
            except (OSError, PDFComparisonError) as exc:
                messagebox.showerror("Save failed", str(exc))
                return
            messagebox.showinfo("Saved", f"Saved:\n{outputs.original}\n{outputs.revised}")

    _Viewer()
    root.mainloop()


def main(argv: Sequence[str] | None = None) -> int:
    """Console entry point for the optional desktop viewer."""
    import argparse

    parser = argparse.ArgumentParser(prog="smart-pdf-compare-viewer")
    parser.add_argument("original", nargs="?")
    parser.add_argument("revised", nargs="?")
    args = parser.parse_args(argv)
    launch_viewer(args.original, args.revised)
    return 0


if __name__ == "__main__":  # pragma: no cover - interactive entry point
    raise SystemExit(main())
