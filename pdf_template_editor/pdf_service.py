from __future__ import annotations

import os
import re
from collections import OrderedDict
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping

import pymupdf


PLACEHOLDER_PATTERN = re.compile(r"(?<![\w$=])([=$][A-Za-z][A-Za-z0-9_]*)")
SUPPORTED_MARKERS = ("$name", "=var", "=dob")


class TemplateError(RuntimeError):
    """Raised when a PDF cannot be used as a template."""


@dataclass(frozen=True)
class Placeholder:
    name: str
    markers: tuple[str, ...]


@dataclass(frozen=True)
class TemplateField:
    name: str
    target: str
    append: bool = False
    first_match_only: bool = True


ORIG_0734_FIELDS = (
    TemplateField("name", "HAY"),
    TemplateField("name2", "BRIA"),
    TemplateField("dob", "07/21"),
    TemplateField("NO", "080717", append=True),
    TemplateField("NO2", "000175365990716037938"),
)


@dataclass(frozen=True)
class TextStyle:
    baseline: float
    font_size: float
    color: tuple[float, float, float]
    font_family: str
    opacity: float


def discover_placeholders(pdf_path: str | Path) -> list[Placeholder]:
    """Return placeholders in the order they first appear in the PDF."""
    grouped: OrderedDict[str, list[str]] = OrderedDict()
    pymupdf.TOOLS.set_small_glyph_heights(True)

    try:
        with pymupdf.open(pdf_path) as document:
            if document.page_count == 0:
                raise TemplateError("The selected PDF has no pages.")

            template_fields = _template_fields(document)
            if template_fields:
                return [
                    Placeholder(
                        field.name,
                        (
                            f"after {field.target}"
                            if field.append
                            else field.target,
                        ),
                    )
                    for field in template_fields
                ]

            for page in document:
                for marker in PLACEHOLDER_PATTERN.findall(page.get_text("text")):
                    if marker not in SUPPORTED_MARKERS:
                        continue
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
        pymupdf.TOOLS.set_small_glyph_heights(True)
        with pymupdf.open(pdf_path) as document:
            template_fields = _template_fields(document)
            if template_fields:
                _apply_template_fields(document, template_fields, values, font_path)
            else:
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


def _template_fields(
    document: pymupdf.Document,
) -> tuple[TemplateField, ...] | None:
    document_text = "\n".join(page.get_text("text") for page in document)
    if all(field.target in document_text for field in ORIG_0734_FIELDS):
        return ORIG_0734_FIELDS
    return None


def _apply_template_fields(
    document: pymupdf.Document,
    fields: tuple[TemplateField, ...],
    values: Mapping[str, str],
    font_path: str | Path,
) -> None:
    for page in document:
        replacements: list[
            tuple[pymupdf.Rect, str, str, TextStyle, float, bool]
        ] = []

        for field in fields:
            rectangles = page.search_for(field.target)
            if field.first_match_only and rectangles:
                rectangles = [min(rectangles, key=lambda rectangle: rectangle.y0)]

            for rectangle in rectangles:
                replacements.append(
                    (
                        rectangle,
                        field.target,
                        str(values.get(field.name, "")),
                        _style_at_rectangle(page, rectangle),
                        rectangle.x1 if field.append else rectangle.x0,
                        not field.append,
                    )
                )
                if not field.append:
                    page.add_redact_annot(
                        _redaction_hit_box(rectangle),
                        fill=False,
                        cross_out=False,
                    )

        if any(replacement[-1] for replacement in replacements):
            page.apply_redactions(images=0, graphics=0)

        for rectangle, target, value, style, origin_x, _redacted in replacements:
            if value:
                _insert_replacement(
                    page,
                    rectangle,
                    target,
                    value,
                    style,
                    font_path,
                    origin_x=origin_x,
                )


def _apply_marker_values(
    document: pymupdf.Document,
    marker_values: Mapping[str, str],
    font_path: str | Path,
) -> None:
    for page in document:
        replacements: list[tuple[pymupdf.Rect, str, str, TextStyle]] = []

        for marker, value in marker_values.items():
            for rectangle in page.search_for(marker):
                replacements.append(
                    (
                        rectangle,
                        marker,
                        value,
                        _style_at_rectangle(page, rectangle),
                    )
                )
                redaction_box = _redaction_hit_box(rectangle)
                page.add_redact_annot(
                    redaction_box,
                    fill=False,
                    cross_out=False,
                )

        if replacements:
            # Remove only the placeholder glyphs. Images, vector graphics, and
            # the original page background must remain untouched.
            page.apply_redactions(images=0, graphics=0)
            for rectangle, marker, value, style in replacements:
                if value:
                    _insert_replacement(
                        page,
                        rectangle,
                        marker,
                        value,
                        style,
                        font_path,
                    )


def _redaction_hit_box(rectangle: pymupdf.Rect) -> pymupdf.Rect:
    # A redaction removes an entire glyph when any part of its character box
    # intersects the annotation. OCR character boxes in the supplied template
    # overlap neighboring rows, so use a narrow band through the visual center
    # of this row instead of the full character height.
    center_y = (rectangle.y0 + rectangle.y1) / 2
    return pymupdf.Rect(rectangle.x0, center_y - 0.25, rectangle.x1, center_y + 0.25)


def _page_output_path(base: Path, page_number: int, page_count: int) -> Path:
    if page_count == 1:
        return base.with_suffix(".jpg")
    return base.with_name(f"{base.stem}_page_{page_number}.jpg")


def _style_at_rectangle(page: pymupdf.Page, rectangle: pymupdf.Rect) -> TextStyle:
    matching_spans: list[tuple[float, dict]] = []
    for block in page.get_text("dict").get("blocks", []):
        for line in block.get("lines", []):
            for span in line.get("spans", []):
                span_rectangle = pymupdf.Rect(span["bbox"])
                intersection = span_rectangle & rectangle
                if not intersection.is_empty:
                    matching_spans.append((intersection.get_area(), span))

    if matching_spans:
        # OCR PDFs often have overlapping line boxes. Selecting by maximum
        # overlap prevents a neighboring row from supplying the wrong baseline.
        span = max(matching_spans, key=lambda match: match[0])[1]
        return TextStyle(
            baseline=float(span["origin"][1]),
            font_size=max(4.0, float(span["size"])),
            color=_pdf_color(int(span.get("color", 0))),
            font_family=str(span.get("font", "")),
            opacity=max(0.0, min(1.0, float(span.get("alpha", 255)) / 255)),
        )

    return TextStyle(
        baseline=rectangle.y1 - max(1.0, rectangle.height * 0.18),
        font_size=max(4.0, rectangle.height * 0.75),
        color=(0.0, 0.0, 0.0),
        font_family="",
        opacity=1.0,
    )


def _insert_replacement(
    page: pymupdf.Page,
    rectangle: pymupdf.Rect,
    marker: str,
    value: str,
    style: TextStyle,
    fallback_font_path: str | Path,
    *,
    origin_x: float | None = None,
) -> None:
    font_path = _matching_system_font(style.font_family, fallback_font_path)
    horizontal_scale = _horizontal_scale(
        marker, rectangle.width, style.font_size, font_path
    )
    origin = pymupdf.Point(
        rectangle.x0 if origin_x is None else origin_x,
        style.baseline,
    )
    resource_name = f"replacement{_normalized_font_name(style.font_family)[:24]}"

    page.insert_text(
        origin,
        value,
        fontsize=style.font_size,
        color=style.color,
        fill_opacity=style.opacity,
        fontname=resource_name,
        fontfile=str(font_path),
        morph=(origin, pymupdf.Matrix(horizontal_scale, 1)),
        overlay=True,
    )


def _matching_system_font(
    font_family: str, fallback_font_path: str | Path
) -> Path:
    normalized = _normalized_font_name(font_family)
    windows_fonts = Path(os.environ.get("WINDIR", "C:/Windows")) / "Fonts"
    candidates: list[str] = []
    if "arial" in normalized:
        candidates.append(
            "arialbd.ttf" if "bold" in normalized else "arial.ttf"
        )
    elif "timesnewroman" in normalized:
        candidates.append(
            "timesbd.ttf" if "bold" in normalized else "times.ttf"
        )
    elif "calibri" in normalized:
        candidates.append(
            "calibrib.ttf" if "bold" in normalized else "calibri.ttf"
        )
    elif "microsoftsansserif" in normalized:
        candidates.append("micross.ttf")

    for candidate in candidates:
        path = windows_fonts / candidate
        if path.is_file():
            return path
    return Path(fallback_font_path)


def _horizontal_scale(
    marker: str,
    original_width: float,
    font_size: float,
    font_path: str | Path,
) -> float:
    font = pymupdf.Font(fontfile=str(font_path))
    natural_width = font.text_length(marker, fontsize=font_size)
    if natural_width <= 0:
        return 1.0
    return max(0.5, min(2.0, original_width / natural_width))


def _normalized_font_name(font_name: str) -> str:
    return re.sub(r"[^a-z0-9]", "", font_name.lower())


def _pdf_color(value: int) -> tuple[float, float, float]:
    return (
        ((value >> 16) & 255) / 255,
        ((value >> 8) & 255) / 255,
        (value & 255) / 255,
    )
