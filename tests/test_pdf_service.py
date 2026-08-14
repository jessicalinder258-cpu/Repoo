from pathlib import Path

import pymupdf

from pdf_template_editor.pdf_service import (
    discover_placeholders,
    export_template_as_jpg,
)


FONT_PATH = Path(__file__).parents[1] / "assets" / "DejaVuSans.ttf"


def make_template(path: Path, pages: int = 1) -> None:
    document = pymupdf.open()
    for page_number in range(pages):
        page = document.new_page(width=400, height=250)
        page.insert_text((30, 50), "Customer: $name", fontsize=12)
        page.insert_text((30, 80), "Birth date: =dob", fontsize=12)
        if page_number == 0:
            page.insert_text((30, 110), "Reference: =var and again =var", fontsize=12)
    document.save(path)
    document.close()


def test_discovers_unique_fields_in_document_order(tmp_path: Path) -> None:
    template = tmp_path / "template.pdf"
    make_template(template)

    placeholders = discover_placeholders(template)

    assert [placeholder.name for placeholder in placeholders] == [
        "name",
        "dob",
        "var",
    ]
    assert placeholders[0].markers == ("$name",)


def test_exports_single_page_to_selected_jpg(tmp_path: Path) -> None:
    template = tmp_path / "template.pdf"
    make_template(template)
    output = tmp_path / "completed.jpg"

    files = export_template_as_jpg(
        template,
        {"name": "José Smith", "dob": "2000-01-31", "var": "ABC-123"},
        output,
        FONT_PATH,
        dpi=100,
    )

    assert files == [output]
    assert output.is_file()
    image = pymupdf.open(output)
    assert image.page_count == 1
    assert image[0].rect.width > 0
    image.close()


def test_exports_multiple_pages_with_numbered_names(tmp_path: Path) -> None:
    template = tmp_path / "template.pdf"
    make_template(template, pages=2)

    files = export_template_as_jpg(
        template,
        {"name": "Test", "dob": "Today", "var": ""},
        tmp_path / "completed.jpg",
        FONT_PATH,
        dpi=72,
    )

    assert [path.name for path in files] == [
        "completed_page_1.jpg",
        "completed_page_2.jpg",
    ]
    assert all(path.is_file() for path in files)
