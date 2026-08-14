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
    font_name: str | None
    opacity: float


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
            _apply_marker_values(document, marker_values, font_path)

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


def _apply_marker_values(
    document: pymupdf.Document,
    marker_values: Mapping[str, str],
    font_path: str | Path,
) -> None:
    for page in document:
        replacements: list[tuple[pymupdf.Rect, str, TextStyle]] = []

        for marker, value in marker_values.items():
            for rectangle in page.search_for(marker):
                replacements.append(
                    (rectangle, value, _style_at_rectangle(page, rectangle))
                )
                page.add_redact_annot(
                    rectangle,
                    fill=False,
                    cross_out=False,
                )

        if replacements:
            # Remove only the placeholder glyphs. Images, vector graphics, and
            # the original page background must remain untouched.
            page.apply_redactions(images=0, graphics=0)
            for rectangle, value, style in replacements:
                if value:
                    _insert_replacement(page, rectangle, value, style, font_path)


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
                        font_name=_font_resource(page, str(span.get("font", ""))),
                        opacity=max(
                            0.0, min(1.0, float(span.get("alpha", 255)) / 255)
                        ),
                    )

    return TextStyle(
        baseline=rectangle.y1 - max(1.0, rectangle.height * 0.18),
        font_size=max(4.0, rectangle.height * 0.75),
        color=(0.0, 0.0, 0.0),
        font_name=None,
        opacity=1.0,
    )


def _insert_replacement(
    page: pymupdf.Page,
    rectangle: pymupdf.Rect,
    value: str,
    style: TextStyle,
    fallback_font_path: str | Path,
) -> None:
    font_arguments: dict[str, str] = {}
    if style.font_name:
        # Reuse the font resource already embedded in this PDF page. This keeps
        # weight, italics, glyph widths, and typeface identical to the marker.
        font_arguments["fontname"] = style.font_name
    else:
        font_arguments["fontname"] = "templatefont"
        font_arguments["fontfile"] = str(fallback_font_path)

    page.insert_text(
        (rectangle.x0, style.baseline),
        value,
        fontsize=style.font_size,
        color=style.color,
        fill_opacity=style.opacity,
        overlay=True,
        **font_arguments,
    )


def _font_resource(page: pymupdf.Page, span_font_name: str) -> str | None:
    target = _normalized_font_name(span_font_name)
    if not target:
        return None

    for font in page.get_fonts(full=True):
        base_font_name = str(font[3])
        resource_name = str(font[4])
        if _normalized_font_name(base_font_name) == target:
            return resource_name
    return None


def _normalized_font_name(font_name: str) -> str:
    # Embedded subset names commonly look like "ABCDEF+Arial-BoldMT".
    font_name = re.sub(r"^[A-Z]{6}\+", "", font_name)
    return re.sub(r"[^a-z0-9]", "", font_name.lower())


def _pdf_color(value: int) -> tuple[float, float, float]:
    return (
        ((value >> 16) & 255) / 255,
        ((value >> 8) & 255) / 255,
        (value & 255) / 255,
    )
