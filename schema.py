"""Detect Salesforce field types from legacy Excel files."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

import pandas as pd

from excel_io import open_excel_file, read_excel_auto

# Salesforce field type → internal validator type
SF_TYPE_MAP: dict[str, str] = {
    "text": "string",
    "string": "string",
    "textarea": "string",
    "long text area": "string",
    "longtextarea": "string",
    "picklist": "picklist",
    "multipicklist": "multipicklist",
    "combobox": "string",
    "formula": "string",
    "location": "string",
    "date": "date",
    "datetime": "date",
    "date/time": "date",
    "number": "float",
    "currency": "float",
    "percent": "float",
    "double": "float",
    "decimal": "float",
    "int": "integer",
    "integer": "integer",
    "boolean": "boolean",
    "checkbox": "boolean",
    "email": "email",
    "phone": "phone",
    "url": "website",
    "website": "website",
    "id": "salesforce_id",
    "reference": "salesforce_id",
    "lookup": "salesforce_id",
    "master-detail": "salesforce_id",
    "master detail": "salesforce_id",
}

VALIDATOR_TYPES = [
    "string",
    "date",
    "integer",
    "float",
    "boolean",
    "email",
    "phone",
    "website",
    "salesforce_id",
    "lookup",
    "picklist",
    "multipicklist",
    "state_code",
]

DATE_NAME_PATTERN = re.compile(
    r"(^date$|date$|^date|_date|date_|dob|birth|expir|deadline|timestamp|created|updated|start.?date|end.?date|_cod__c$)",
    re.IGNORECASE,
)
EMAIL_NAME_PATTERN = re.compile(r"email|e-mail", re.IGNORECASE)
PHONE_NAME_PATTERN = re.compile(r"phone|mobile|fax", re.IGNORECASE)
URL_NAME_PATTERN = re.compile(r"website|url|^web$", re.IGNORECASE)
ID_NAME_PATTERN = re.compile(r"(^id$|id$|__c$|ownerid$|accountid$|contactid$)", re.IGNORECASE)
SF_ID_VALUE_PATTERN = re.compile(r"^00[a-zA-Z0-9]{16}$")
API_NAME_PATTERN = re.compile(r"^[A-Za-z][A-Za-z0-9_]*(__c|__r|__s)?$")
LOOKUP_TYPE_PATTERN = re.compile(r"^lookup\s*\(([^)]+)\)\s*$", re.IGNORECASE)


@dataclass
class ExcelSchema:
    df: pd.DataFrame
    column_types: dict[str, str]
    detection_method: str
    data_sheet: str
    field_labels: dict[str, str] = field(default_factory=dict)
    raw_types: dict[str, str] = field(default_factory=dict)
    lookup_fields: dict[str, str] = field(default_factory=dict)  # column api -> referenced object


def parse_lookup_reference(raw_type: Any) -> str | None:
    """Extract referenced object from types like 'Lookup (Account)'."""
    if raw_type is None or (isinstance(raw_type, float) and pd.isna(raw_type)):
        return None
    text = str(raw_type).strip()
    match = LOOKUP_TYPE_PATTERN.match(text)
    if match:
        return match.group(1).strip()
    return None


def normalize_sf_type(raw_type: Any) -> str | None:
    if raw_type is None or (isinstance(raw_type, float) and pd.isna(raw_type)):
        return None
    text_raw = str(raw_type).strip().lower()
    if not text_raw:
        return None
    if "picklist" in text_raw and "multi" in text_raw:
        return "multipicklist"
    text = re.sub(r"\(.*\)", "", text_raw).strip()
    text = text.replace("-", " ").replace("_", " ")
    text = re.sub(r"\s+", " ", text).strip()
    if text in SF_TYPE_MAP:
        return SF_TYPE_MAP[text]
    for key, mapped in SF_TYPE_MAP.items():
        if text.startswith(key):
            return mapped
    if text in VALIDATOR_TYPES:
        return text
    return None


def _is_likely_type_token(value: Any) -> bool:
    return normalize_sf_type(value) is not None


def _detect_type_row(raw_row: pd.Series) -> bool:
    non_empty = [v for v in raw_row if str(v).strip() not in ("", "nan")]
    if len(non_empty) < 2:
        return False
    type_hits = sum(1 for v in non_empty if _is_likely_type_token(v))
    return type_hits / len(non_empty) >= 0.6


def _looks_like_api_name(value: Any) -> bool:
    text = str(value).strip()
    if not text or text.lower() in ("nan", "api name", "name"):
        return False
    if text in ("Name", "Id"):
        return True
    return bool(API_NAME_PATTERN.match(text) or text.endswith("Id") or "__" in text)


def _has_row_metadata_column(preview: pd.DataFrame) -> bool:
    if preview.shape[0] < 3 or preview.shape[1] < 2:
        return False
    r0 = str(preview.iloc[0, 0]).strip().lower()
    r1 = str(preview.iloc[1, 0]).strip().lower()
    r2 = str(preview.iloc[2, 0]).strip().lower()
    return "field label" in r0 and "api name" in r1 and "data type" in r2


def _detect_sf_three_row_header(preview: pd.DataFrame) -> bool:
    """Detect row1=label, row2=API name, row3=data type format (e.g. TestFile3.xlsx)."""
    if len(preview) < 3:
        return False
    if _has_row_metadata_column(preview):
        return True

    if not _detect_type_row(preview.iloc[2]):
        return False

    start_col = 1 if _has_row_metadata_column(preview) else 0
    api_cells = preview.iloc[1, start_col:]
    non_empty = [v for v in api_cells if str(v).strip() not in ("", "nan", "API Name")]
    if len(non_empty) < 2:
        return False
    api_hits = sum(1 for v in non_empty if _looks_like_api_name(v))
    return api_hits / len(non_empty) >= 0.5


def _pick_data_sheet(xl: pd.ExcelFile, config: dict) -> str:
    schema_names = {s.lower() for s in config.get("schema_sheet_names", [])}
    for name in xl.sheet_names:
        if name.lower() in schema_names:
            continue
        if name == "Map":
            return name
    for name in xl.sheet_names:
        if name.lower() not in schema_names:
            return name
    return xl.sheet_names[0]


def _read_schema_sheet(xl: pd.ExcelFile, config: dict) -> dict[str, str] | None:
    schema_names = config.get("schema_sheet_names", [])
    name_lookup = {n.lower(): n for n in xl.sheet_names}

    for candidate in schema_names:
        if candidate.lower() not in name_lookup:
            continue
        sheet = name_lookup[candidate.lower()]
        schema_df = read_excel_auto(xl, sheet_name=sheet)
        schema_df.columns = [str(c).strip().lower() for c in schema_df.columns]

        field_col = next(
            (c for c in schema_df.columns if c in ("field", "column", "field name", "column name", "api name", "name")),
            None,
        )
        type_col = next(
            (c for c in schema_df.columns if c in ("type", "data type", "field type", "salesforce type")),
            None,
        )
        if not field_col or not type_col:
            continue

        types: dict[str, str] = {}
        for _, row in schema_df.iterrows():
            field_name = str(row[field_col]).strip()
            mapped = normalize_sf_type(row[type_col])
            if field_name and mapped:
                types[field_name] = mapped
        if types:
            return types
    return None


def _load_sf_three_row_header(
    xl: pd.ExcelFile, data_sheet: str, preview: pd.DataFrame
) -> tuple[pd.DataFrame, dict[str, str], dict[str, str]]:
    start_col = 1 if _has_row_metadata_column(preview) else 0

    labels = [str(v).strip() for v in preview.iloc[0, start_col:].tolist()]
    api_names = [str(v).strip() for v in preview.iloc[1, start_col:].tolist()]
    type_row = preview.iloc[2, start_col:].tolist()

    df = read_excel_auto(xl, sheet_name=data_sheet, skiprows=3, header=None)
    if start_col > 0 and df.shape[1] > start_col:
        df = df.iloc[:, start_col:]

    num_cols = min(len(api_names), df.shape[1])
    api_names = api_names[:num_cols]
    df = df.iloc[:, :num_cols]
    df.columns = api_names

    column_types: dict[str, str] = {}
    field_labels: dict[str, str] = {}
    raw_types: dict[str, str] = {}
    lookup_fields: dict[str, str] = {}
    for i, col in enumerate(api_names):
        if not col or col.lower() == "nan":
            continue
        raw_type = str(type_row[i]).strip() if i < len(type_row) else ""
        raw_types[col] = raw_type
        lookup_ref = parse_lookup_reference(type_row[i] if i < len(type_row) else None)
        if lookup_ref:
            column_types[col] = "lookup"
            lookup_fields[col] = lookup_ref
        else:
            mapped = normalize_sf_type(type_row[i]) if i < len(type_row) else None
            column_types[col] = mapped or infer_column_type(col, df[col])
        if i < len(labels) and labels[i] and labels[i].lower() not in ("field label", "nan"):
            field_labels[col] = labels[i]

    return df, column_types, field_labels, raw_types, lookup_fields


def infer_column_type(col_name: str, series: pd.Series) -> str:
    if pd.api.types.is_datetime64_any_dtype(series):
        return "date"
    if pd.api.types.is_bool_dtype(series):
        return "boolean"
    if pd.api.types.is_integer_dtype(series):
        return "integer"
    if pd.api.types.is_float_dtype(series):
        return "float"

    if DATE_NAME_PATTERN.search(col_name):
        return "date"
    if EMAIL_NAME_PATTERN.search(col_name):
        return "email"
    if PHONE_NAME_PATTERN.search(col_name):
        return "phone"
    if URL_NAME_PATTERN.search(col_name):
        return "website"
    if ID_NAME_PATTERN.search(col_name) or col_name.endswith("Id"):
        non_empty = series.dropna().astype(str).str.strip()
        non_empty = non_empty[non_empty != ""]
        if len(non_empty) > 0:
            sf_id_ratio = non_empty.str.match(SF_ID_VALUE_PATTERN).mean()
            if sf_id_ratio >= 0.8:
                return "salesforce_id"

    non_empty = series.dropna()
    non_empty = non_empty[non_empty.astype(str).str.strip() != ""]
    if len(non_empty) > 0:
        sample = non_empty.head(20).astype(str)
        if sample.str.match(SF_ID_VALUE_PATTERN).mean() >= 0.8:
            return "salesforce_id"

    return "string"


def build_column_rules(
    column_types: dict[str, str],
    lookup_fields: dict[str, str] | None = None,
) -> dict[str, dict]:
    lookup_fields = lookup_fields or {}
    rules: dict[str, dict] = {}
    for name, dtype in column_types.items():
        rule: dict[str, Any] = {"name": name, "type": dtype, "source": "file"}
        if dtype == "lookup" and name in lookup_fields:
            rule["lookup_object"] = lookup_fields[name]
        rules[name] = rule
    return rules


def read_excel_with_schema(file, config: dict | None = None) -> ExcelSchema:
    """Load data and field types from a legacy Salesforce migration Excel file."""
    config = config or {}
    xl = open_excel_file(file)
    data_sheet = _pick_data_sheet(xl, config)
    detection_mode = config.get("schema_detection", "auto")

    preview = read_excel_auto(xl, sheet_name=data_sheet, header=None, nrows=4)
    field_labels: dict[str, str] = {}

    if detection_mode in ("auto", "sf_three_row_header") and _detect_sf_three_row_header(preview):
        df, column_types, field_labels, raw_types, lookup_fields = _load_sf_three_row_header(
            xl, data_sheet, preview
        )
        method = "sf_three_row_header"
    else:
        raw_types = {}
        lookup_fields = {}
        schema_from_sheet = None
        if detection_mode in ("auto", "schema_sheet"):
            schema_from_sheet = _read_schema_sheet(xl, config)

        use_type_row = False
        if detection_mode in ("auto", "type_row") and len(preview) >= 2:
            use_type_row = _detect_type_row(preview.iloc[1])

        if use_type_row:
            headers = [str(v).strip() for v in preview.iloc[0].tolist()]
            type_row = preview.iloc[1].tolist()
            df = read_excel_auto(xl, sheet_name=data_sheet, skiprows=2, header=None)
            df.columns = headers[: len(df.columns)]
            column_types = {}
            for i, col in enumerate(df.columns):
                raw_type = str(type_row[i]).strip() if i < len(type_row) else ""
                raw_types[col] = raw_type
                lookup_ref = parse_lookup_reference(type_row[i] if i < len(type_row) else None)
                if lookup_ref:
                    column_types[col] = "lookup"
                    lookup_fields[col] = lookup_ref
                else:
                    mapped = normalize_sf_type(type_row[i]) if i < len(type_row) else None
                    column_types[col] = mapped or infer_column_type(col, df[col])
            method = "type_row"
        else:
            df = read_excel_auto(xl, sheet_name=data_sheet)
            df.columns = [str(c).strip() for c in df.columns]
            if schema_from_sheet:
                column_types = {
                    col: schema_from_sheet.get(col) or infer_column_type(col, df[col])
                    for col in df.columns
                }
                method = "schema_sheet"
            else:
                column_types = {col: infer_column_type(col, df[col]) for col in df.columns}
                method = "inferred"

    df = df.dropna(how="all").reset_index(drop=True)
    return ExcelSchema(
        df=df,
        column_types=column_types,
        detection_method=method,
        data_sheet=data_sheet,
        field_labels=field_labels,
        raw_types=raw_types,
        lookup_fields=lookup_fields,
    )


def date_columns_from_types(column_types: dict[str, str]) -> list[str]:
    return sorted(col for col, dtype in column_types.items() if dtype == "date")
