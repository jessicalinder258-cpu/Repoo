from __future__ import annotations

import re
from collections import OrderedDict
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping

import pymupdf


PLACEHOLDER_PATTERN = re.compile(r"(?<![\w$=])([=$][A-Za-z][A-Za-z0-9_]*)")


class TemplateError(RuntimeError):
    """Raised when a PDF cannot be used as a template."""


@dataclass(frozen=True)
class Placeholder:
    name: str
    markers: tuple[str, ...]


@dataclass(frozen=True)
class TextStyle:
    baseline: float
    font_size: float
    color: tuple[float, float, float]


def discover_placeholders(pdf_path: str | Path) -> list[Placeholder]:
    """Return placeholders in the order they first appear in the PDF."""
    grouped: OrderedDict[str, list[str]] = OrderedDict()

    try:
        with pymupdf.open(pdf_path) as document:
            if document.page_count == 0:
                raise TemplateError("The selected PDF has no pages.")

            for page in document:
                for marker in PLACEHOLDER_PATTERN.findall(page.get_text("text")):
                    name = marker[1:]
                    markers = grouped.setdefault(name, [])
                    if marker not in markers:
                        markers.append(marker)
    except TemplateError:
        raise
    except Exception as exc:
        raise TemplateError(f"Could not open the PDF: {exc}") from exc

    return [Placeholder(name, tuple(markers)) for name, markers in grouped.items()]


def export_template_as_jpg(
    pdf_path: str | Path,
    values: Mapping[str, str],
    output_path: str | Path,
    font_path: str | Path,
    *,
    dpi: int = 200,
) -> list[Path]:
    """Replace template markers and render every page as a JPEG."""
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    created_files: list[Path] = []

    try:
        with pymupdf.open(pdf_path) as document:
            placeholders = discover_placeholders(pdf_path)
            marker_values = {
                marker: str(values.get(placeholder.name, ""))
                for placeholder in placeholders
                for marker in placeholder.markers
            }

            for page in document:
                replacements: list[tuple[pymupdf.Rect, str, TextStyle]] = []

                for marker, value in marker_values.items():
                    for rectangle in page.search_for(marker):
                        replacements.append(
                            (rectangle, value, _style_at_rectangle(page, rectangle))
                        )
                        page.add_redact_annot(rectangle, fill=(1, 1, 1))

                if replacements:
                    page.apply_redactions()
                    for rectangle, value, style in replacements:
                        if value:
                            page.insert_text(
                                (rectangle.x0, style.baseline),
                                value,
                                fontsize=style.font_size,
                                fontname="templatefont",
                                fontfile=str(font_path),
                                color=style.color,
                                overlay=True,
                            )

            for page_number, page in enumerate(document, start=1):
                page_output = _page_output_path(
                    output_path, page_number, document.page_count
                )
                pixmap = page.get_pixmap(dpi=dpi, alpha=False)
                pixmap.save(page_output, jpg_quality=95)
                created_files.append(page_output)
    except Exception as exc:
        for created_file in created_files:
            created_file.unlink(missing_ok=True)
        if isinstance(exc, TemplateError):
            raise
        raise TemplateError(f"Could not create the JPG: {exc}") from exc

    return created_files


def _page_output_path(base: Path, page_number: int, page_count: int) -> Path:
    if page_count == 1:
        return base.with_suffix(".jpg")
    return base.with_name(f"{base.stem}_page_{page_number}.jpg")


def _style_at_rectangle(page: pymupdf.Page, rectangle: pymupdf.Rect) -> TextStyle:
    for block in page.get_text("dict").get("blocks", []):
        for line in block.get("lines", []):
            for span in line.get("spans", []):
                span_rectangle = pymupdf.Rect(span["bbox"])
                if span_rectangle.intersects(rectangle):
                    return TextStyle(
                        baseline=float(span["origin"][1]),
                        font_size=max(4.0, float(span["size"])),
                        color=_pdf_color(int(span.get("color", 0))),
                    )

    return TextStyle(
        baseline=rectangle.y1 - max(1.0, rectangle.height * 0.18),
        font_size=max(4.0, rectangle.height * 0.75),
        color=(0.0, 0.0, 0.0),
    )


def _pdf_color(value: int) -> tuple[float, float, float]:
    return (
        ((value >> 16) & 255) / 255,
        ((value >> 8) & 255) / 255,
        (value & 255) / 255,
    )
