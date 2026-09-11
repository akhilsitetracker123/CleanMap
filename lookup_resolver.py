"""Resolve Salesforce lookup fields using reference export files."""

from __future__ import annotations

import io
import re
from typing import Any

import pandas as pd

from excel_io import read_excel_auto
from schema import SF_ID_VALUE_PATTERN
from validator import ValidationIssue, _is_empty

RESOLVED_ID_SUFFIX = "_Salesforce_Id"
LOOKUP_NAME_EXPORT_PREFIX = "_"

NAME_COLUMN_CANDIDATES = (
    "name",
    "account name",
    "full name",
    "display name",
    "record name",
    "title",
    "label",
)
ID_COLUMN_CANDIDATES = (
    "id",
    "salesforce id",
    "salesforce_id",
    "sf id",
    "sfid",
    "record id",
    "18 char id",
    "18-char id",
)


def read_lookup_reference_file(file) -> pd.DataFrame:
    """Read a lookup reference file with Name and Salesforce Id columns."""
    df = read_excel_auto(file)
    df.columns = [str(c).strip() for c in df.columns]
    df = df.dropna(how="all").reset_index(drop=True)

    if df.empty:
        raise ValueError("Lookup file is empty.")

    lowered = {str(c).strip().lower(): c for c in df.columns}
    id_col = _find_column(lowered, ID_COLUMN_CANDIDATES)
    name_col = _find_column(lowered, NAME_COLUMN_CANDIDATES, exclude={id_col} if id_col else set())

    if not id_col:
        id_col = _detect_id_column(df)
    if not name_col:
        name_col = _detect_name_column(df, exclude={id_col} if id_col else set())

    if not id_col or not name_col:
        raise ValueError(
            "Could not find Name and Id columns. Expected headers like "
            "'Name' and 'Id' (or 'Salesforce Id')."
        )

    ref = df[[name_col, id_col]].copy()
    ref.columns = ["Name", "Id"]
    ref["Name"] = ref["Name"].astype(str).str.strip()
    ref["Id"] = ref["Id"].astype(str).str.strip()
    ref = ref[(ref["Name"] != "") & (ref["Id"] != "")]
    ref = ref.drop_duplicates(subset=["Name"], keep="first")
    return ref.reset_index(drop=True)


def _find_column(
    lowered: dict[str, str],
    candidates: tuple[str, ...],
    exclude: set[str] | None = None,
) -> str | None:
    exclude = exclude or set()
    for candidate in candidates:
        if candidate in lowered and lowered[candidate] not in exclude:
            return lowered[candidate]
    return None


def _detect_id_column(df: pd.DataFrame) -> str | None:
    best_col = None
    best_ratio = 0.0
    for col in df.columns:
        series = df[col].dropna().astype(str).str.strip()
        series = series[series != ""]
        if len(series) == 0:
            continue
        ratio = series.str.match(SF_ID_VALUE_PATTERN).mean()
        if ratio > best_ratio:
            best_ratio = ratio
            best_col = col
    return best_col if best_ratio >= 0.8 else None


def _detect_name_column(df: pd.DataFrame, exclude: set[str]) -> str | None:
    for col in df.columns:
        if col in exclude:
            continue
        if pd.api.types.is_string_dtype(df[col]) or df[col].dtype == object:
            non_empty = df[col].dropna().astype(str).str.strip()
            if (non_empty != "").sum() > 0:
                return col
    return None


def build_name_to_id_map(reference_df: pd.DataFrame) -> dict[str, str]:
    mapping: dict[str, str] = {}
    for _, row in reference_df.iterrows():
        name = str(row["Name"]).strip()
        sf_id = str(row["Id"]).strip()
        if name and sf_id:
            mapping[name.lower()] = sf_id
    return mapping


def resolve_lookup_value(value: Any, name_to_id: dict[str, str]) -> Any:
    if _is_empty(value):
        return pd.NA
    text = str(value).strip()
    if SF_ID_VALUE_PATTERN.match(text):
        return text
    return name_to_id.get(text.lower(), pd.NA)


def apply_lookup_resolution(
    df: pd.DataFrame,
    lookup_fields: dict[str, str],
    lookup_tables: dict[str, pd.DataFrame],
) -> tuple[pd.DataFrame, dict[str, dict[str, int]]]:
    """
    Insert a Salesforce Id column immediately after each lookup column.
    lookup_tables is keyed by referenced object name (e.g. Account, User).
    """
    result = pd.DataFrame()
    stats: dict[str, dict[str, int]] = {}

    for col in df.columns:
        result[col] = df[col]
        if col not in lookup_fields:
            continue

        object_name = lookup_fields[col]
        id_col = resolved_id_column(col)
        reference = lookup_tables.get(object_name)

        if reference is None or reference.empty:
            resolved_values = []
            empty = already_id = 0
            for value in df[col]:
                if _is_empty(value):
                    empty += 1
                    resolved_values.append(pd.NA)
                elif SF_ID_VALUE_PATTERN.match(str(value).strip()):
                    already_id += 1
                    resolved_values.append(str(value).strip())
                else:
                    resolved_values.append(pd.NA)
            result[id_col] = resolved_values
            stats[col] = {
                "matched": 0,
                "unresolved": 0,
                "empty": empty,
                "already_id": already_id,
                "reference_loaded": False,
            }
            continue

        name_to_id = build_name_to_id_map(reference)
        matched = unresolved = empty = already_id = 0
        resolved_values: list[Any] = []

        for value in df[col]:
            if _is_empty(value):
                empty += 1
                resolved_values.append(pd.NA)
                continue
            text = str(value).strip()
            if SF_ID_VALUE_PATTERN.match(text):
                already_id += 1
                resolved_values.append(text)
                continue
            sf_id = name_to_id.get(text.lower())
            if sf_id:
                matched += 1
                resolved_values.append(sf_id)
            else:
                unresolved += 1
                resolved_values.append(pd.NA)

        result[id_col] = resolved_values
        stats[col] = {
            "matched": matched,
            "unresolved": unresolved,
            "empty": empty,
            "already_id": already_id,
            "reference_loaded": True,
        }

    return result, stats


def lookup_resolution_issues(
    df: pd.DataFrame,
    lookup_fields: dict[str, str],
    lookup_tables: dict[str, pd.DataFrame] | None = None,
    warn_unresolved: bool = False,
) -> list[ValidationIssue]:
    """
    Optionally flag lookup names that could not be resolved.

    When warn_unresolved is True and a reference file was loaded for the object,
    unmatched names produce warnings (not errors) so Status stays Ready unless
    other errors exist. Unresolved Id cells remain blank for export.
    """
    if not warn_unresolved:
        return []

    lookup_tables = lookup_tables or {}
    issues: list[ValidationIssue] = []

    for col, object_name in lookup_fields.items():
        reference = lookup_tables.get(object_name)
        if reference is None or reference.empty:
            continue

        id_col = resolved_id_column(col)
        if id_col not in df.columns:
            continue

        for idx, row in df.iterrows():
            source = row[col]
            resolved = row[id_col]
            if _is_empty(source):
                continue
            text = str(source).strip()
            if SF_ID_VALUE_PATTERN.match(text):
                continue
            if _is_empty(resolved):
                issues.append(
                    ValidationIssue(
                        row=int(idx) + 2,
                        column=col,
                        value=source,
                        rule="lookup_unresolved",
                        message=(
                            f"Lookup name '{text}' did not match any {object_name} "
                            "record in the reference file"
                        ),
                        severity="warning",
                    )
                )

    return issues


def lookup_name_export_column(column: str) -> str:
    """Prefix lookup name columns so Salesforce Inspector skips them on import."""
    if column.startswith(LOOKUP_NAME_EXPORT_PREFIX):
        return column
    return f"{LOOKUP_NAME_EXPORT_PREFIX}{column}"


def resolved_id_column(lookup_col: str) -> str:
    """Internal column name for resolved Salesforce Ids (before export rename)."""
    return f"{lookup_col}{RESOLVED_ID_SUFFIX}"


def build_lookup_export_rename(
    df: pd.DataFrame,
    lookup_fields: dict[str, str],
) -> dict[str, str]:
    """
    Export rename map for Salesforce Inspector:
    - lookup name column -> _{api_name}
    - internal id column -> {api_name} (no suffix)
    """
    rename: dict[str, str] = {}
    for col in lookup_fields:
        if col in df.columns:
            rename[col] = lookup_name_export_column(col)
        id_col = resolved_id_column(col)
        if id_col in df.columns:
            rename[id_col] = col
    return rename


def build_lookup_name_export_rename(
    df: pd.DataFrame,
    lookup_fields: dict[str, str],
) -> dict[str, str]:
    """Map validation issue columns to export headers."""
    return build_lookup_export_rename(df, lookup_fields)


def prepare_lookup_export_dataframe(
    df: pd.DataFrame,
    lookup_fields: dict[str, str],
) -> pd.DataFrame:
    """Rename lookup columns for Salesforce Inspector export."""
    rename = build_lookup_export_rename(df, lookup_fields)
    return df.rename(columns=rename) if rename else df


def group_lookup_fields_by_object(lookup_fields: dict[str, str]) -> dict[str, list[str]]:
    grouped: dict[str, list[str]] = {}
    for col, obj in lookup_fields.items():
        grouped.setdefault(obj, []).append(col)
    return dict(sorted(grouped.items()))
