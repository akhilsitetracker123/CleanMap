"""Generate CleanMap V1 vs V2 Word document from CLEANMAP_V1_VS_V2.md sections."""

from pathlib import Path

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.shared import Pt, RGBColor

OUTPUT = "CleanMap V1 vs V2.docx"


def add_title(doc: Document, text: str) -> None:
    p = doc.add_heading(text, level=0)
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER


def add_heading(doc: Document, text: str, level: int = 1) -> None:
    doc.add_heading(text, level=level)


def add_para(doc: Document, text: str) -> None:
    doc.add_paragraph(text)


def add_table(doc: Document, headers: list[str], rows: list[list[str]]) -> None:
    table = doc.add_table(rows=1, cols=len(headers))
    table.style = "Table Grid"
    for i, h in enumerate(headers):
        table.rows[0].cells[i].text = h
    for row in rows:
        cells = table.add_row().cells
        for i, val in enumerate(row):
            cells[i].text = val


def build() -> Document:
    doc = Document()

    add_title(doc, "CleanMap — Version 1 vs Version 2")
    sub = doc.add_paragraph("Comparison for stakeholders and migration teams")
    sub.alignment = WD_ALIGN_PARAGRAPH.CENTER
    sub.runs[0].font.size = Pt(12)
    sub.runs[0].font.color.rgb = RGBColor(80, 80, 80)
    doc.add_paragraph("")
    meta = doc.add_paragraph("V1 = cleanmap-demo (local demo)  ·  V2 = excel-validator / cleanmap-v2 (online)")
    meta.alignment = WD_ALIGN_PARAGRAPH.CENTER
    doc.add_page_break()

    add_heading(doc, "At a glance")
    add_table(
        doc,
        ["", "V1 — Demo", "V2 — Production"],
        [
            ["Folder", "cleanmap-demo/", "excel-validator/"],
            ["Login", "None", "Username / password"],
            ["File storage", "Local session only", "Supabase Storage (per user)"],
            ["GitHub", "Not deploy target", "github.com/akhilsitetracker123/CleanMap (branch cleanmap-v2)"],
            ["Hosting", "Localhost only", "Streamlit Community Cloud + optional local dev"],
        ],
    )
    add_para(
        doc,
        "V2 uses Supabase for file storage and Streamlit Cloud for hosting the app. "
        "Secrets hold auth and Supabase keys (never committed to git).",
    )

    add_heading(doc, "Shared core (V1 and V2)")
    bullets = [
        "Salesforce three-row header schema detection",
        "Validation, cleansing, mandatory columns, Status (Ready / Not Ready)",
        "Lookup resolution and Inspector-ready export",
        "Picklist validation from object field definition files",
        "Unresolved lookup warnings (optional)",
        "Date normalization; reject 0, 1899-12-30, and year-only values like 2027",
        "Cleansed Excel download with optional error/warning highlighting",
        ".xlsx and .xls support; local file path for large files",
    ]
    for b in bullets:
        doc.add_paragraph(b, style="List Bullet")

    add_heading(doc, "V2-only features")
    add_heading(doc, "Online access", level=2)
    for b in [
        "Sign-in page (streamlit-authenticator)",
        "Logout; session and cookie handling for Streamlit Cloud",
        "Optional local mode when auth is not configured",
    ]:
        doc.add_paragraph(b, style="List Bullet")

    add_heading(doc, "Supabase cloud storage", level=2)
    for b in [
        "Private bucket (e.g. cleanmap-files) with per-user folders",
        "Sidebar toggle: Upload files to cloud",
        "List all cloud files; download and delete",
        "Save cleansed output to cloud after validation",
    ]:
        doc.add_paragraph(b, style="List Bullet")

    add_heading(doc, "GitHub and deployment", level=2)
    for b in [
        "Repository: akhilsitetracker123/CleanMap",
        "Recommended branch: cleanmap-v2; main file: app.py",
        "Streamlit Cloud connected to GitHub; secrets in dashboard",
        "CLOUD_SETUP.md and .devcontainer for onboarding",
        "Documentation/presentation generators in repo",
    ]:
        doc.add_paragraph(b, style="List Bullet")

    add_heading(doc, "New modules in V2")
    add_table(
        doc,
        ["File", "Purpose"],
        [
            ["auth.py", "Login, logout, cookies"],
            ["cloud_storage.py", "Supabase upload/list/delete"],
            ["cloud_ui.py", "Sidebar cloud file manager"],
        ],
    )

    add_heading(doc, "How to run")
    add_heading(doc, "V1 — Demo", level=2)
    add_para(
        doc,
        "cd cleanmap-demo → python3 -m venv .venv → activate → pip install -r requirements.txt → streamlit run app.py",
    )
    add_heading(doc, "V2 — Local or Cloud", level=2)
    add_para(
        doc,
        "Local: excel-validator with .streamlit/secrets.toml (auth + cloud). "
        "Cloud: share.streamlit.io, branch cleanmap-v2, paste secrets. See CLOUD_SETUP.md.",
    )

    add_heading(doc, "Which version to use")
    add_table(
        doc,
        ["Scenario", "Version"],
        [
            ["Demo video, no login", "V1 (cleanmap-demo)"],
            ["Team online access + cloud files", "V2 (Streamlit Cloud + Supabase)"],
            ["Ongoing product development", "V2 repo (excel-validator)"],
        ],
    )

    add_heading(doc, "Summary")
    add_para(
        doc,
        "V1 is the documentation-aligned local demo. V2 is the same validation engine "
        "plus GitHub delivery, Streamlit Cloud hosting, login, and Supabase file storage "
        "for production-style use.",
    )
    doc.add_paragraph("")
    footer = doc.add_paragraph("— End of CleanMap V1 vs V2 —")
    footer.alignment = WD_ALIGN_PARAGRAPH.CENTER
    return doc


if __name__ == "__main__":
    out = Path(__file__).parent / OUTPUT
    build().save(out)
    print(f"Created: {out}")