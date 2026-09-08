# CleanMap

CleanMap validates and cleanses legacy Excel imports before loading into Salesforce. Field types, lookups, and picklists are checked against your source files.

## Features

- Dynamic schema detection from Salesforce-style Excel headers (label / API name / data type)
- Field validation, auto-cleansing, and date normalization
- Lookup resolution with optional reference files
- Picklist validation against object field definition files
- Row **Status** column (`Ready` / `Not Ready`) in export
- Salesforce Inspector-ready export (lookup name columns prefixed with `_`)

## Quick start

```bash
cd CleanMap
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
streamlit run app.py
```

Open http://localhost:8501 in your browser.

## Large files

- Increase upload limit in `.streamlit/config.toml` → `server.maxUploadSize` (MB)
- Or enable **Load from local file path** in the sidebar for files on your machine

## Configuration

Global settings live in `rules.yaml`. Column types are read from the uploaded Excel file (row 3), not from a fixed column list.

## Project structure

| File | Purpose |
|------|---------|
| `app.py` | Streamlit UI |
| `validator.py` | Validation, cleansing, export |
| `schema.py` | Salesforce header and field type detection |
| `lookup_resolver.py` | Lookup reference resolution |
| `field_definition.py` | Picklist validation from object field definitions |
| `excel_io.py` | `.xlsx` and `.xls` support |
| `ui_theme.py` | UI styling |
