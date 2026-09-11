"""Generate CleanMap Word documentation."""

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import parse_xml
from docx.oxml.ns import nsdecls
from docx.shared import Pt, RGBColor

OUTPUT = "CleanMap Documentation.docx"


def add_title(doc: Document, text: str) -> None:
    p = doc.add_heading(text, level=0)
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER


def add_heading(doc: Document, text: str, level: int = 1) -> None:
    doc.add_heading(text, level=level)


def add_para(doc: Document, text: str, bold: bool = False) -> None:
    p = doc.add_paragraph()
    run = p.add_run(text)
    run.bold = bold


def add_bullets(doc: Document, items: list[str]) -> None:
    for item in items:
        doc.add_paragraph(item, style="List Bullet")


def add_numbered(doc: Document, items: list[str]) -> None:
    for item in items:
        doc.add_paragraph(item, style="List Number")


def shade_cell(cell, fill: str = "D9D9D9") -> None:
    shading = parse_xml(rf'<w:shd {nsdecls("w")} w:fill="{fill}"/>')
    cell._tc.get_or_add_tcPr().append(shading)


def add_summary_box(doc: Document, title: str, items: list[str]) -> None:
    """Highlighted summary box listing key capabilities."""
    table = doc.add_table(rows=1, cols=1)
    table.style = "Table Grid"
    cell = table.rows[0].cells[0]
    shade_cell(cell, "E8E8EA")

    title_p = cell.paragraphs[0]
    title_run = title_p.add_run(title)
    title_run.bold = True
    title_run.font.size = Pt(13)
    title_run.font.color.rgb = RGBColor(30, 30, 30)

    intro = cell.add_paragraph(
        "CleanMap is a pre-import quality tool for Salesforce Excel migrations. "
        "At a glance, it can:"
    )
    intro.runs[0].font.size = Pt(10)

    for item in items:
        p = cell.add_paragraph(item, style="List Bullet")
        for run in p.runs:
            run.font.size = Pt(10)

    doc.add_paragraph("")


SUMMARY_CAPABILITIES = [
    "Read and validate legacy Excel migration files (.xlsx and .xls).",
    "Auto-detect Salesforce field types from three-row headers (Label, API Name, Data Type).",
    "Accept all columns dynamically — no fixed column list required.",
    "Cleanse data automatically: trim whitespace, fix blanks, and normalize #N/A values.",
    "Convert date fields to YYYY-MM-DD and repair common legacy date typos.",
    "Normalize checkbox fields to Salesforce TRUE/FALSE values.",
    "Let you choose which columns are mandatory and flag empty required values.",
    "Detect lookup fields and optionally resolve names to Salesforce Ids using reference files.",
    "Validate picklist and multi-select picklist values against object field definition files.",
    "Add a row Status column: Ready (no errors) or Not Ready (has errors).",
    "Export cleansed Excel files ready for Salesforce Inspector import.",
    "Prefix lookup name columns with _ and keep Id columns on original API names for import.",
    "Highlight error cells in downloaded Excel with descriptive comments.",
    "Handle large files via configurable upload limit or local file path loading.",
    "Show validation metrics, issue reports, and summary-by-column breakdowns.",
]


def add_table(doc: Document, headers: list[str], rows: list[list[str]]) -> None:
    table = doc.add_table(rows=1, cols=len(headers))
    table.style = "Table Grid"
    hdr = table.rows[0].cells
    for i, h in enumerate(headers):
        hdr[i].text = h
    for row in rows:
        cells = table.add_row().cells
        for i, val in enumerate(row):
            cells[i].text = val


def build() -> Document:
    doc = Document()

    # Title page
    add_title(doc, "CleanMap")
    sub = doc.add_paragraph("Complete Product Documentation")
    sub.alignment = WD_ALIGN_PARAGRAPH.CENTER
    sub.runs[0].font.size = Pt(14)
    sub.runs[0].font.color.rgb = RGBColor(80, 80, 80)
    doc.add_paragraph("")
    meta = doc.add_paragraph(
        "Salesforce Excel Import Validator & Cleansing Tool\n"
        "Version 1.0 | Streamlit Application"
    )
    meta.alignment = WD_ALIGN_PARAGRAPH.CENTER
    doc.add_page_break()

    add_summary_box(doc, "Summary — What CleanMap Can Do", SUMMARY_CAPABILITIES)

    add_heading(doc, "Detailed Documentation")
    add_para(
        doc,
        "The sections below provide full explanations of each feature, workflow step, "
        "configuration option, and best practice.",
    )
    doc.add_paragraph("")

    add_heading(doc, "1. Introduction")
    add_para(
        doc,
        "CleanMap is a desktop web application built with Python and Streamlit. It validates, "
        "cleanses, and prepares legacy Excel migration files before they are loaded into "
        "Salesforce using tools such as Salesforce Inspector or Data Loader.",
    )
    add_para(
        doc,
        "Legacy migration spreadsheets often contain inconsistent dates, invalid picklist values, "
        "unresolved lookup names, extra whitespace, Excel error values (#N/A), and mixed data types. "
        "CleanMap automates detection and correction of these issues so migration teams spend less "
        "time fixing data manually and more time importing clean records.",
    )

    add_heading(doc, "2. Why CleanMap Is Useful")
    add_bullets(
        doc,
        [
            "Reduces failed Salesforce imports caused by bad data.",
            "Automatically reads Salesforce field types from the Excel file itself — no hardcoded column list.",
            "Resolves lookup names to Salesforce Ids using optional reference files.",
            "Validates picklist values against official object field definition exports.",
            "Produces a row-level Status column (Ready / Not Ready) for import readiness.",
            "Exports files formatted for Salesforce Inspector (lookup name columns prefixed with _).",
            "Supports both modern .xlsx and legacy .xls Excel formats.",
            "Optional error highlighting in downloaded Excel with cell comments.",
        ],
    )

    add_heading(doc, "3. Key Features")
    add_heading(doc, "3.1 Dynamic Schema Detection", level=2)
    add_para(
        doc,
        "CleanMap detects field types from the uploaded Excel file. The primary format is the "
        "Salesforce three-row header pattern:",
    )
    add_bullets(
        doc,
        [
            "Row 1: Field Label",
            "Row 2: API Name (used as column headers)",
            "Row 3: Salesforce Data Type (Text, Date, Lookup (Account), Picklist, etc.)",
            "Row 4+: Data rows",
        ],
    )

    add_heading(doc, "3.2 Field Validation & Cleansing", level=2)
    add_bullets(
        doc,
        [
            "Required field validation (user selects mandatory columns in the UI).",
            "Type validation: string, date, integer, float, boolean, email, phone, website, lookup, picklist, multipicklist, salesforce_id.",
            "Auto-cleanse: trim whitespace, normalize blanks and #N/A values.",
            "Date normalization to YYYY-MM-DD with repair of common legacy typos.",
            "Checkbox normalization to TRUE/FALSE.",
            "Text fields accept numeric values and coerce them to strings.",
        ],
    )

    add_heading(doc, "3.3 Lookup Resolution", level=2)
    add_para(
        doc,
        "When row 3 contains types like Lookup (Account) or Lookup (User), CleanMap detects "
        "lookup fields automatically. You may optionally upload reference files per object "
        "(Account, User, Site, etc.) containing Name and Id columns.",
    )
    add_bullets(
        doc,
        [
            "Reference file uploads are optional — not all lookup objects need a file.",
            "On Run validation, Salesforce Ids are resolved next to each lookup field.",
            "If no reference is uploaded, lookup Id columns are left blank (no error).",
            "If a value is already a valid 18-character Salesforce Id, it is preserved.",
            "Unresolved lookup names are left blank without raising errors.",
        ],
    )
    add_para(doc, "Export behavior for Salesforce Inspector:", bold=True)
    add_table(
        doc,
        ["Column type", "In downloaded file"],
        [
            ["Lookup name column (e.g. AccountId)", "_AccountId (prefixed with _ so Inspector skips it)"],
            ["Lookup Id column", "Original API name (e.g. AccountId) — no _Salesforce_Id suffix"],
        ],
    )

    add_heading(doc, "3.4 Picklist Validation", level=2)
    add_para(
        doc,
        "Optionally upload an Object Field Definition file (e.g. Site Object Fields Definition.xlsx) "
        "with API Name and Picklist Values columns. CleanMap matches fields by API name and validates "
        "each cell value against allowed picklist entries.",
    )
    add_bullets(
        doc,
        [
            "Single-select picklists: entire cell value must match an allowed value.",
            "Multi-select picklists: values split by semicolon (;) are each validated.",
            "Invalid picklist values are flagged as errors.",
            "Empty cells are skipped unless the column is marked mandatory.",
        ],
    )

    add_heading(doc, "3.5 Row Status Column", level=2)
    add_para(
        doc,
        "After validation, a Status column is appended as the last column in the output:",
    )
    add_table(
        doc,
        ["Status", "Meaning"],
        [
            ["Ready", "No validation errors in any field for that row."],
            ["Not Ready", "At least one validation error exists in that row."],
        ],
    )

    add_heading(doc, "3.6 Download & Error Highlighting", level=2)
    add_bullets(
        doc,
        [
            "Download cleansed Excel file after validation.",
            "Optional red cell highlighting for errors with comments describing each issue.",
            "Optional yellow highlighting for warnings.",
        ],
    )

    add_heading(doc, "4. Application Workflow")
    add_numbered(
        doc,
        [
            "Upload main Excel file (.xlsx or .xls) — or load from a local file path for large files.",
            "Review field types detected from row 3; adjust types in the editor if needed.",
            "Optionally upload lookup reference files for objects you want to resolve.",
            "Optionally upload object field definition file for picklist validation.",
            "Select mandatory columns (fields that must not be empty).",
            "Click Run validation.",
            "Review results: metrics, issues tab, data preview, and download cleansed file.",
        ],
    )

    add_heading(doc, "5. Supported File Formats")
    add_table(
        doc,
        ["Format", "Engine", "Notes"],
        [
            [".xlsx", "openpyxl", "Modern Excel workbooks"],
            [".xls", "xlrd", "Legacy Excel 97-2003 workbooks"],
            ["Object field definition .xlsx", "Custom reader", "Handles styled exports that fail standard openpyxl parsing"],
        ],
    )

    add_heading(doc, "6. Sidebar Options")
    add_table(
        doc,
        ["Option", "Description"],
        [
            ["Auto-cleanse", "Trim whitespace, normalize blanks and Excel #N/A values."],
            ["Convert date fields to YYYY-MM-DD", "Normalize all detected date columns to ISO format."],
            ["Load from local file path", "Bypass browser upload limit; read file directly from disk."],
        ],
    )
    add_para(
        doc,
        "Large file upload limit: configured in .streamlit/config.toml as server.maxUploadSize (default 1024 MB). "
        "Restart Streamlit after changing this value.",
    )

    add_heading(doc, "7. Validation Types Reference")
    add_table(
        doc,
        ["Type", "Validation behavior"],
        [
            ["string", "Accepts text and numbers (numbers coerced to string on cleanse)."],
            ["date", "Parsed and converted to YYYY-MM-DD; malformed dates repaired where possible."],
            ["integer", "Whole numbers only."],
            ["float", "Numeric values."],
            ["boolean", "Normalized to TRUE or FALSE (yes/no/blank supported)."],
            ["email", "Valid email format."],
            ["phone", "Valid phone format."],
            ["website", "Valid URL format."],
            ["lookup", "Accepts lookup name or text; Id resolved separately."],
            ["picklist", "Validated against object field definition when uploaded."],
            ["multipicklist", "Semicolon-separated values each validated against definition."],
            ["salesforce_id", "18-character Id starting with 00; blank values allowed."],
            ["state_code", "Two-letter state/province code."],
        ],
    )

    add_heading(doc, "8. Lookup Reference File Format")
    add_para(doc, "Each lookup reference file should contain at minimum:")
    add_bullets(
        doc,
        [
            "A Name column (Account Name, Name, Full Name, etc.)",
            "An Id column (Id, Salesforce Id, SF Id, etc.)",
            "One row per Salesforce record",
        ],
    )
    add_para(doc, "Column headers are auto-detected. Supported formats: .xlsx and .xls.")

    add_heading(doc, "9. Object Field Definition File Format")
    add_para(doc, "Expected structure (Salesforce field export style):")
    add_bullets(
        doc,
        [
            "Header row containing API Name and Picklist Values columns.",
            "Data Type column used to distinguish Picklist vs Picklist (Multi-Select).",
            "Picklist Values separated by semicolons (;).",
            "Fields with empty picklist values are skipped.",
        ],
    )

    add_heading(doc, "10. Configuration (rules.yaml)")
    add_para(doc, "Global settings only — column types are NOT hardcoded in rules.yaml.")
    add_bullets(
        doc,
        [
            "ignore_column_prefixes: columns starting with these prefixes are skipped (default: __).",
            "schema_detection: auto | sf_three_row_header | type_row | schema_sheet | infer.",
            "schema_sheet_names: sheet names to search for a separate schema sheet.",
        ],
    )

    add_heading(doc, "11. Project Structure")
    add_table(
        doc,
        ["File", "Purpose"],
        [
            ["app.py", "Streamlit UI and workflow orchestration"],
            ["validator.py", "Validation, cleansing, date parsing, Status column, Excel export"],
            ["schema.py", "Salesforce header detection and field type mapping"],
            ["lookup_resolver.py", "Lookup reference loading and Id resolution"],
            ["field_definition.py", "Object field definition parsing and picklist validation"],
            ["excel_io.py", "Auto engine selection for .xlsx and .xls"],
            ["ui_theme.py", "Professional black/grey UI styling"],
            ["rules.yaml", "Global configuration"],
            ["requirements.txt", "Python dependencies"],
            [".streamlit/config.toml", "Streamlit server and theme settings"],
        ],
    )

    add_heading(doc, "12. Installation & Running")
    add_para(doc, "Prerequisites: Python 3.10+ recommended.")
    add_numbered(
        doc,
        [
            "Open terminal and navigate to the project folder.",
            "Create virtual environment: python -m venv .venv",
            "Activate: source .venv/bin/activate (macOS/Linux) or .venv\\Scripts\\activate (Windows).",
            "Install dependencies: pip install -r requirements.txt",
            "Start app: streamlit run app.py",
            "Open browser at http://localhost:8501",
        ],
    )

    add_heading(doc, "13. Sample Files Included")
    add_table(
        doc,
        ["File", "Purpose"],
        [
            ["TestFile3.xlsx", "Sample main migration file with lookup and picklist fields"],
            ["Site Object Fields Definition.xlsx", "Sample object field definition for picklist validation"],
            ["accountlookup.xls", "Sample Account lookup reference file"],
            ["Accounts Import Map.xlsx", "Sample accounts import template"],
        ],
    )

    add_heading(doc, "14. Validation Results Screen")
    add_bullets(
        doc,
        [
            "Metrics: Total Rows, Total Columns, Errors, Warnings.",
            "Data Preview tab: cleansed data including Status column.",
            "Issues tab: row, column, value, rule, and error message for each issue.",
            "Summary by Column tab: grouped error counts by column and rule.",
            "Lookup resolution summary expander (when lookup fields exist).",
            "Download section with optional error highlighting.",
        ],
    )

    add_heading(doc, "15. Troubleshooting")
    add_table(
        doc,
        ["Issue", "Solution"],
        [
            ["Upload limit exceeded", "Increase maxUploadSize in .streamlit/config.toml or use local file path."],
            ["Picklist errors for Territory_RTO__c", "Ensure main file values match definition file exactly (case-sensitive)."],
            ["Lookup Id column blank", "Upload reference file for that object, or value had no match — left blank by design."],
            ["Streamlit shows old UI/name", "Restart Streamlit completely (Ctrl+C then streamlit run app.py)."],
            [".xls file won't open", "Ensure xlrd is installed: pip install xlrd"],
        ],
    )

    add_heading(doc, "16. Best Practices")
    add_numbered(
        doc,
        [
            "Always review detected field types before running validation.",
            "Upload object field definition files for objects with many picklist fields.",
            "Upload lookup reference files only for objects you need to resolve.",
            "Mark only truly required fields as mandatory.",
            "Use Status = Ready rows for first-wave imports; fix Not Ready rows separately.",
            "Download with error highlighting when sharing issues with data owners.",
        ],
    )

    add_heading(doc, "17. Summary")
    add_para(
        doc,
        "CleanMap is a complete pre-import quality gate for Salesforce Excel migrations. "
        "It combines schema-aware validation, lookup Id resolution, picklist conformance checking, "
        "automatic data cleansing, and Salesforce Inspector-ready export formatting — all through "
        "a simple six-step web interface. By catching data problems before import, CleanMap saves "
        "time, reduces load errors, and improves migration success rates.",
    )

    doc.add_paragraph("")
    footer = doc.add_paragraph("— End of CleanMap Documentation —")
    footer.alignment = WD_ALIGN_PARAGRAPH.CENTER

    return doc


if __name__ == "__main__":
    document = build()
    document.save(OUTPUT)
    print(f"Created: {OUTPUT}")
