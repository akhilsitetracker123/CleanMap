"""Read Salesforce object field definition files and validate picklist values."""

from __future__ import annotations

import io
import re
import zipfile
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from typing import Any

import pandas as pd

from excel_io import read_excel_auto
from validator import ValidationIssue, _is_empty

PICKLIST_VALUE_SEPARATOR = ";"
XLSX_NS = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
API_NAME_HEADERS = ("api name",)
PICKLIST_HEADERS = ("picklist values",)
DATA_TYPE_HEADERS = ("data type",)


@dataclass
class ObjectFieldDefinition:
    object_label: str = ""
    object_api_name: str = ""
    picklist_fields: dict[str, set[str]] = field(default_factory=dict)
    multipicklist_fields: dict[str, set[str]] = field(default_factory=dict)

    @property
    def validated_field_count(self) -> int:
        return len(self.picklist_fields) + len(self.multipicklist_fields)


def read_object_field_definition(file) -> ObjectFieldDefinition:
    """Load picklist allowed values keyed by field API name."""
    try:
        if hasattr(file, "seek"):
            file.seek(0)
        df = read_excel_auto(file, header=None)
        return _parse_definition_dataframe(df)
    except Exception:
        if hasattr(file, "seek"):
            file.seek(0)
        rows = _read_xlsx_rows_without_styles(file)
        return _parse_definition_rows(rows)


def _parse_definition_dataframe(df: pd.DataFrame) -> ObjectFieldDefinition:
    rows = [
        ["" if pd.isna(v) else str(v).strip() for v in row.tolist()]
        for _, row in df.iterrows()
    ]
    return _parse_definition_rows(rows)


def _parse_definition_rows(rows: list[list[str]]) -> ObjectFieldDefinition:
    object_label = ""
    object_api_name = ""
    for row in rows[:5]:
        if row and str(row[0]).strip().lower() == "object" and len(row) > 2:
            object_label = str(row[2]).strip()
        if row and str(row[0]).strip().lower() == "api name" and len(row) > 2:
            object_api_name = str(row[2]).strip()

    header_idx = _find_header_row(rows)
    if header_idx is None:
        raise ValueError(
            "Could not find a header row with 'API Name' and 'Picklist Values' columns."
        )

    headers = [_normalize_header(h) for h in rows[header_idx]]
    api_idx = _find_column_index(headers, API_NAME_HEADERS)
    picklist_idx = _find_column_index(headers, PICKLIST_HEADERS)
    data_type_idx = _find_column_index(headers, DATA_TYPE_HEADERS)

    if api_idx is None or picklist_idx is None:
        raise ValueError(
            "Object field definition must include 'API Name' and 'Picklist Values' columns."
        )

    picklist_fields: dict[str, set[str]] = {}
    multipicklist_fields: dict[str, set[str]] = {}

    for row in rows[header_idx + 1 :]:
        api_name = _cell(row, api_idx)
        if not api_name or api_name.lower() in ("api name", "nan"):
            continue

        allowed = parse_picklist_values(_cell(row, picklist_idx))
        if not allowed:
            continue

        data_type = _cell(row, data_type_idx).lower() if data_type_idx is not None else ""
        if "multi" in data_type and "picklist" in data_type:
            multipicklist_fields[api_name] = allowed
        else:
            picklist_fields[api_name] = allowed

    if not picklist_fields and not multipicklist_fields:
        raise ValueError(
            "No picklist fields with values were found in the object field definition file."
        )

    return ObjectFieldDefinition(
        object_label=object_label,
        object_api_name=object_api_name,
        picklist_fields=picklist_fields,
        multipicklist_fields=multipicklist_fields,
    )


def parse_picklist_values(raw: Any) -> set[str]:
    if _is_empty(raw):
        return set()
    return {part.strip() for part in str(raw).split(PICKLIST_VALUE_SEPARATOR) if part.strip()}


def split_multipicklist_value(raw: Any) -> list[str]:
    if _is_empty(raw):
        return []
    return [part.strip() for part in str(raw).split(PICKLIST_VALUE_SEPARATOR) if part.strip()]


def validate_picklist_fields(
    df: pd.DataFrame,
    field_definition: ObjectFieldDefinition,
) -> list[ValidationIssue]:
    """Validate main-sheet picklist values against object field definition."""
    issues: list[ValidationIssue] = []

    for col, allowed in field_definition.picklist_fields.items():
        if col not in df.columns:
            continue
        issues.extend(_validate_picklist_column(df, col, allowed, multipicklist=False))

    for col, allowed in field_definition.multipicklist_fields.items():
        if col not in df.columns:
            continue
        issues.extend(_validate_picklist_column(df, col, allowed, multipicklist=True))

    return issues


def _validate_picklist_column(
    df: pd.DataFrame,
    col: str,
    allowed: set[str],
    multipicklist: bool,
) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    allowed_display = _format_allowed_values(allowed)

    for idx, value in df[col].items():
        if _is_empty(value):
            continue

        values = split_multipicklist_value(value) if multipicklist else [str(value).strip()]
        for selected in values:
            if selected not in allowed:
                issues.append(
                    ValidationIssue(
                        row=int(idx) + 2,
                        column=col,
                        value=selected,
                        rule="picklist_value",
                        message=(
                            f"Invalid picklist value '{selected}'. "
                            f"Allowed values: {allowed_display}"
                        ),
                    )
                )
    return issues


def _format_allowed_values(allowed: set[str], limit: int = 12) -> str:
    ordered = sorted(allowed)
    if len(ordered) <= limit:
        return "; ".join(ordered)
    shown = "; ".join(ordered[:limit])
    return f"{shown}; ... ({len(ordered)} total)"


def _find_header_row(rows: list[list[str]]) -> int | None:
    for idx, row in enumerate(rows):
        headers = [_normalize_header(cell) for cell in row]
        if _find_column_index(headers, API_NAME_HEADERS) is not None and _find_column_index(
            headers, PICKLIST_HEADERS
        ) is not None:
            return idx
    return None


def _find_column_index(headers: list[str], candidates: tuple[str, ...]) -> int | None:
    for idx, header in enumerate(headers):
        if header in candidates:
            return idx
    return None


def _normalize_header(value: Any) -> str:
    return str(value).strip().lower()


def _cell(row: list[str], index: int) -> str:
    if index >= len(row):
        return ""
    return str(row[index]).strip()


def _read_xlsx_rows_without_styles(file) -> list[list[str]]:
    """Read the first worksheet from an .xlsx file without parsing styles."""
    if isinstance(file, (str, bytes)):
        data = file if isinstance(file, bytes) else open(file, "rb").read()
    elif hasattr(file, "read"):
        data = file.read()
    else:
        raise ValueError("Unsupported file type for object field definition.")

    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        shared_strings = _read_shared_strings(archive)
        sheet_name = _first_worksheet_path(archive)
        return _read_worksheet_rows(archive, sheet_name, shared_strings)


def _first_worksheet_path(archive: zipfile.ZipFile) -> str:
    for name in archive.namelist():
        if name.startswith("xl/worksheets/sheet") and name.endswith(".xml"):
            return name
    raise ValueError("No worksheet found in Excel file.")


def _read_shared_strings(archive: zipfile.ZipFile) -> list[str]:
    if "xl/sharedStrings.xml" not in archive.namelist():
        return []
    root = ET.fromstring(archive.read("xl/sharedStrings.xml"))
    strings: list[str] = []
    for item in root.findall(f"{{{XLSX_NS}}}si"):
        parts = [node.text or "" for node in item.findall(f".//{{{XLSX_NS}}}t")]
        strings.append("".join(parts))
    return strings


def _read_worksheet_rows(
    archive: zipfile.ZipFile,
    sheet_path: str,
    shared_strings: list[str],
) -> list[list[str]]:
    root = ET.fromstring(archive.read(sheet_path))
    cell_map: dict[tuple[int, int], str] = {}
    max_row = max_col = 0

    for cell in root.findall(f".//{{{XLSX_NS}}}c"):
        ref = cell.get("r")
        if not ref:
            continue
        col_idx, row_idx = _parse_cell_ref(ref)
        value_node = cell.find(f"{{{XLSX_NS}}}v")
        if value_node is None or value_node.text is None:
            value = ""
        elif cell.get("t") == "s":
            value = shared_strings[int(value_node.text)]
        else:
            value = value_node.text
        cell_map[(row_idx, col_idx)] = value
        max_row = max(max_row, row_idx)
        max_col = max(max_col, col_idx)

    return [
        [cell_map.get((row_idx, col_idx), "") for col_idx in range(max_col + 1)]
        for row_idx in range(max_row + 1)
    ]


def _parse_cell_ref(ref: str) -> tuple[int, int]:
    match = re.match(r"([A-Z]+)(\d+)", ref)
    if not match:
        raise ValueError(f"Invalid cell reference: {ref}")
    col = match.group(1)
    row = int(match.group(2)) - 1
    col_idx = 0
    for char in col:
        col_idx = col_idx * 26 + (ord(char) - 64)
    return col_idx - 1, row
