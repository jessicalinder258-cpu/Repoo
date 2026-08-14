from __future__ import annotations

import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from .pdf_service import (
    Placeholder,
    TemplateError,
    discover_placeholders,
    export_template_as_jpg,
)
from .resources import resource_path


class PdfTemplateEditor(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("PDF Template Editor")
        self.geometry("640x600")
        self.minsize(520, 420)

        self.pdf_path: Path | None = None
        self.placeholders: list[Placeholder] = []
        self.field_values: dict[str, tk.StringVar] = {}

        self._build_window()

    def _build_window(self) -> None:
        container = ttk.Frame(self, padding=20)
        container.pack(fill="both", expand=True)
        container.columnconfigure(0, weight=1)
        container.rowconfigure(2, weight=1)

        ttk.Label(
            container,
            text="PDF Template Editor",
            font=("Segoe UI", 18, "bold"),
        ).grid(row=0, column=0, sticky="w")
        ttk.Label(
            container,
            text=(
                "Choose a PDF containing placeholders such as $name, =var, "
                "or =dob."
            ),
            wraplength=580,
        ).grid(row=1, column=0, sticky="w", pady=(4, 16))

        fields_panel = ttk.LabelFrame(container, text="Template values", padding=12)
        fields_panel.grid(row=2, column=0, sticky="nsew")
        fields_panel.columnconfigure(0, weight=1)
        fields_panel.rowconfigure(1, weight=1)

        select_row = ttk.Frame(fields_panel)
        select_row.grid(row=0, column=0, sticky="ew", pady=(0, 10))
        select_row.columnconfigure(1, weight=1)
        ttk.Button(
            select_row, text="Choose PDF…", command=self._choose_pdf
        ).grid(row=0, column=0, padx=(0, 10))
        self.file_label = ttk.Label(select_row, text="No PDF selected")
        self.file_label.grid(row=0, column=1, sticky="w")

        self.canvas = tk.Canvas(fields_panel, highlightthickness=0)
        scrollbar = ttk.Scrollbar(
            fields_panel, orient="vertical", command=self.canvas.yview
        )
        self.fields_frame = ttk.Frame(self.canvas)
        self.fields_window = self.canvas.create_window(
            (0, 0), window=self.fields_frame, anchor="nw"
        )
        self.canvas.configure(yscrollcommand=scrollbar.set)
        self.canvas.grid(row=1, column=0, sticky="nsew")
        scrollbar.grid(row=1, column=1, sticky="ns")
        self.fields_frame.bind("<Configure>", self._update_scroll_region)
        self.canvas.bind("<Configure>", self._resize_fields_frame)

        self.empty_label = ttk.Label(
            self.fields_frame,
            text="Select a template to show its fields.",
            foreground="#666666",
        )
        self.empty_label.grid(row=0, column=0, sticky="w", pady=8)

        footer = ttk.Frame(container)
        footer.grid(row=3, column=0, sticky="ew", pady=(16, 0))
        footer.columnconfigure(0, weight=1)
        self.status_label = ttk.Label(footer, text="Ready")
        self.status_label.grid(row=0, column=0, sticky="w")
        self.submit_button = ttk.Button(
            footer,
            text="Submit and export JPG",
            command=self._export,
            state="disabled",
        )
        self.submit_button.grid(row=0, column=1)

    def _choose_pdf(self) -> None:
        selected = filedialog.askopenfilename(
            title="Choose a PDF template",
            filetypes=[("PDF files", "*.pdf"), ("All files", "*.*")],
        )
        if not selected:
            return

        try:
            placeholders = discover_placeholders(selected)
        except TemplateError as exc:
            messagebox.showerror("Cannot open template", str(exc), parent=self)
            return

        if not placeholders:
            messagebox.showwarning(
                "No placeholders found",
                "This PDF does not contain fields such as $name, =var, or =dob.",
                parent=self,
            )
            return

        self.pdf_path = Path(selected)
        self.placeholders = placeholders
        self.file_label.configure(text=self.pdf_path.name)
        self.status_label.configure(
            text=f"Found {len(placeholders)} field(s)"
        )
        self.submit_button.configure(state="normal")
        self._show_fields()

    def _show_fields(self) -> None:
        for child in self.fields_frame.winfo_children():
            child.destroy()

        self.field_values.clear()
        self.fields_frame.columnconfigure(1, weight=1)
        for row, placeholder in enumerate(self.placeholders):
            markers = " / ".join(placeholder.markers)
            ttk.Label(
                self.fields_frame,
                text=placeholder.name.replace("_", " ").title(),
            ).grid(row=row, column=0, sticky="w", padx=(0, 12), pady=6)
            value = tk.StringVar()
            self.field_values[placeholder.name] = value
            entry = ttk.Entry(self.fields_frame, textvariable=value)
            entry.grid(row=row, column=1, sticky="ew", pady=6)
            ttk.Label(
                self.fields_frame,
                text=markers,
                foreground="#666666",
            ).grid(row=row, column=2, sticky="w", padx=(10, 0), pady=6)
            if row == 0:
                entry.focus_set()

    def _export(self) -> None:
        if self.pdf_path is None:
            return

        suggested_name = f"{self.pdf_path.stem}_edited.jpg"
        selected = filedialog.asksaveasfilename(
            title="Save JPG",
            initialfile=suggested_name,
            defaultextension=".jpg",
            filetypes=[("JPEG image", "*.jpg")],
        )
        if not selected:
            return

        self.submit_button.configure(state="disabled")
        self.status_label.configure(text="Creating JPG…")
        self.update_idletasks()
        try:
            files = export_template_as_jpg(
                self.pdf_path,
                {name: value.get() for name, value in self.field_values.items()},
                selected,
                resource_path("assets/Arimo-Bold.ttf"),
            )
        except TemplateError as exc:
            messagebox.showerror("Export failed", str(exc), parent=self)
            self.status_label.configure(text="Export failed")
        else:
            self.status_label.configure(text=f"Created {len(files)} JPG file(s)")
            file_list = "\n".join(str(path) for path in files)
            messagebox.showinfo(
                "Export complete",
                f"The edited template was exported successfully:\n\n{file_list}",
                parent=self,
            )
        finally:
            self.submit_button.configure(state="normal")

    def _update_scroll_region(self, _event: tk.Event) -> None:
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))

    def _resize_fields_frame(self, event: tk.Event) -> None:
        self.canvas.itemconfigure(self.fields_window, width=event.width)


def run() -> None:
    app = PdfTemplateEditor()
    app.mainloop()
