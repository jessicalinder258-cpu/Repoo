# PDF Template Editor

A small Windows desktop program that fills placeholders in a PDF template and
exports the finished document as JPG images.

## Use the program

1. Open `PDF-Template-Editor.exe`.
2. Click **Choose PDF** and select your template.
3. Enter a value for every field found in the template.
4. Click **Submit and export JPG** and choose where to save the result.

A one-page PDF produces the selected `.jpg` file. A PDF with multiple pages
produces files such as `document_page_1.jpg`, `document_page_2.jpg`, and so on.

## Create a template

Put placeholder text directly into the PDF:

- `$name`
- `=var`
- `=dob`
- Any other name that starts with `$` or `=` and contains letters, numbers, or
  underscores, such as `$customer_name`.

The entered value inherits the placeholder's original font, size, color, and
position. Only the placeholder text is removed; other text, images, graphics,
and the page background are preserved.

The PDF must contain real selectable text. Placeholders in a scanned image
cannot be detected. Leave enough blank space after each placeholder for the
replacement value.

## Download the Windows executable

Every push builds a standalone executable in GitHub Actions. Open the completed
**Build Windows executable** workflow, download the
`PDF-Template-Editor-Windows` artifact, unzip it, and run the `.exe`. Python is
not required on the Windows computer.

Windows may show a SmartScreen warning because the executable is not
code-signed.

## Development

Requires Python 3.10 or newer.

```bash
python -m pip install -r requirements-dev.txt
python -m pytest
python -m pdf_template_editor
```

To build on Windows:

```powershell
./build-windows.ps1
```

The executable is written to `dist/PDF-Template-Editor.exe`.
