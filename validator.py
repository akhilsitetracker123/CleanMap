"""Core validation and cleansing logic for legacy Excel files."""

from __future__ import annotations

import io
import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

import pandas as pd
import yaml
from dateutil import parser as date_parser

from excel_io import open_excel_file, read_excel_auto
from ui_theme import APP_NAME


@dataclass
class ValidationIssue:
    row: int
    column: str
    value: Any
    rule: str
    message: str
    severity: str = "error"  # error | warning


@dataclass
class ValidationResult:
    total_rows: int
    total_columns: int
    issues: list[ValidationIssue] = field(default_factory=list)
    cleansed_df: pd.DataFrame | None = None

    @property
    def error_count(self) -> int:
        return sum(1 for i in self.issues if i.severity == "error")

    @property
    def warning_count(self) -> int:
        return sum(1 for i in self.issues if i.severity == "warning")

    @property
    def is_valid(self) -> bool:
        return self.error_count == 0


EMAIL_PATTERN = re.compile(r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$")
PHONE_PATTERN = re.compile(r"^\+?[\d\s\-().]{7,20}$")
SALESFORCE_ID_PATTERN = re.compile(r"^00[a-zA-Z0-9]{16}$")
STATE_CODE_PATTERN = re.compile(r"^[A-Z]{2}$")
WEBSITE_PATTERN = re.compile(
    r"^(https?://)?[\w.-]+(\.[\w.-]+)+(/?[\w./?=&%#{}~+\-]*)?$",
    re.IGNORECASE,
)
OUTPUT_DATE_FORMAT = "%Y-%m-%d"
ISO_DATE_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}$")
# e.g. 09/082026 → missing "/" before year → 09/08/2026
MISSING_YEAR_SLASH_PATTERN = re.compile(r"^(\d{1,2})/(\d{2})(\d{4})$")
# e.g. 09/82026 → single-digit month run into year → 9/8/2026
MISSING_YEAR_SLASH_SHORT_MONTH = re.compile(r"^(\d{1,2})/(\d{1,2})(\d{4})$")
DATE_NAME_PATTERN = re.compile(
    r"(^date$|date$|^date|_date|date_|dob|birth|expir|deadline|timestamp|created|updated|start.?date|end.?date)",
    re.IGNORECASE,
)
EXCEL_NA_VALUES = {"#n/a", "n/a", "#na", "na", "#null!", "#ref!", "#value!"}
CHECKBOX_TRUE_VALUES = {"true", "yes", "y", "1", "on"}
CHECKBOX_FALSE_VALUES = {"false", "no", "n", "0", "off"}


def load_rules(path: str) -> dict:
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def read_excel(file, sheet_name: str | int | None = None) -> pd.DataFrame:
    """Read Excel file (simple mode — use read_excel_with_schema for type detection)."""
    if sheet_name is None:
        xl = open_excel_file(file)
        sheet_name = "Map" if "Map" in xl.sheet_names else 0

    df = read_excel_auto(file, sheet_name=sheet_name)
    df.columns = [str(c).strip() for c in df.columns]
    df = df.dropna(how="all").reset_index(drop=True)
    return df


def _is_excel_na(value: Any) -> bool:
    if isinstance(value, str):
        return value.strip().lower() in EXCEL_NA_VALUES
    return False


def _normalize_na_value(value: Any) -> Any:
    if _is_excel_na(value):
        return pd.NA
    return value


def _value_to_text(value: Any) -> Any:
    """Coerce numbers to text for string/text fields."""
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return value
    if isinstance(value, bool):
        return str(value)
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        return str(int(value)) if value.is_integer() else str(value)
    return value


def _normalize_checkbox_value(value: Any) -> str | Any:
    """Normalize checkbox values to Salesforce TRUE/FALSE."""
    if isinstance(value, str):
        text = value.strip()
        if not text or text.lower() in EXCEL_NA_VALUES:
            return "FALSE"
        if text.upper() in ("TRUE", "FALSE"):
            return text.upper()
        lower = text.lower()
        if lower in CHECKBOX_TRUE_VALUES:
            return "TRUE"
        if lower in CHECKBOX_FALSE_VALUES:
            return "FALSE"
        return value

    if value is None:
        return "FALSE"
    try:
        if pd.isna(value):
            return "FALSE"
    except (ValueError, TypeError):
        pass

    if isinstance(value, bool):
        return "TRUE" if value else "FALSE"

    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return "TRUE" if value != 0 else "FALSE"

    return value


def cleanse_dataframe(df: pd.DataFrame, column_rules: dict[str, dict] | None = None) -> pd.DataFrame:
    """Apply safe, automatic fixes for common legacy data issues."""
    cleaned = df.copy()
    column_rules = column_rules or {}

    for col in cleaned.columns:
        cleaned[col] = cleaned[col].apply(_normalize_na_value)

        if pd.api.types.is_string_dtype(cleaned[col]) or cleaned[col].dtype == object:
            cleaned[col] = cleaned[col].apply(
                lambda v: v.strip() if isinstance(v, str) else v
            )
            cleaned[col] = cleaned[col].replace({"": pd.NA, "nan": pd.NA, "None": pd.NA})

        col_type = column_rules.get(col, {}).get("type")
        if col_type == "string":
            cleaned[col] = cleaned[col].apply(_value_to_text)

        if col_type == "boolean":
            cleaned[col] = cleaned[col].apply(_normalize_checkbox_value)

        if col_type == "website" and (
            pd.api.types.is_string_dtype(cleaned[col]) or cleaned[col].dtype == object
        ):
            cleaned[col] = cleaned[col].apply(
                lambda v: re.sub(r"\s+", "", v) if isinstance(v, str) else v
            )

    return cleaned


def _is_empty(value: Any) -> bool:
    if _is_excel_na(value):
        return True
    if value is None:
        return True
    try:
        if pd.isna(value):
            return True
    except (ValueError, TypeError):
        pass
    return isinstance(value, str) and value.strip() == ""


def _repair_malformed_date_string(text: str) -> tuple[str, bool] | None:
    """Fix common legacy typos. Returns (repaired_text, use_dayfirst) or None."""
    match = MISSING_YEAR_SLASH_PATTERN.match(text)
    if match:
        day, month, year = match.groups()
        return f"{day}/{month}/{year}", True

    match = MISSING_YEAR_SLASH_SHORT_MONTH.match(text)
    if match:
        first, second, year = match.groups()
        # Prefer DD/M/YYYY when a 2-digit month is glued to the year (e.g. 9/82026).
        if len(second) == 1:
            return f"{first}/{second}/{year}", True
        # Avoid rewriting valid slash dates like 09/08/2026.
        if len(second) == 2 and len(first) <= 2:
            return f"{first}/{second}/{year}", True

    return None


def _fix_zero_month_day(text: str) -> str:
    """Replace month or day values of 0 with 1 (e.g. 1/0/1900 → 1/1/1900)."""
    text = text.strip()

    iso_match = re.match(r"^(\d{4})-(\d{1,2})-(\d{1,2})$", text)
    if iso_match:
        year, month, day = iso_match.groups()
        month = 1 if int(month) == 0 else int(month)
        day = 1 if int(day) == 0 else int(day)
        return f"{year}-{month:02d}-{day:02d}"

    sep_match = re.match(r"^(\d{1,2})([/\-])(\d{1,2})\2(\d{2,4})$", text)
    if sep_match:
        first, sep, second, year = sep_match.groups()
        first = 1 if int(first) == 0 else int(first)
        second = 1 if int(second) == 0 else int(second)
        return f"{first}{sep}{second}{sep}{year}"

    return text


def parse_date_value(value: Any) -> tuple[str | None, str | None]:
    """Parse a date from many formats and return (YYYY-MM-DD, error_message)."""
    if _is_empty(value):
        return None, None

    if isinstance(value, pd.Timestamp):
        return value.strftime(OUTPUT_DATE_FORMAT), None

    if isinstance(value, datetime):
        return value.strftime(OUTPUT_DATE_FORMAT), None

    if hasattr(value, "to_pydatetime"):
        try:
            return value.to_pydatetime().strftime(OUTPUT_DATE_FORMAT), None
        except (ValueError, TypeError, AttributeError):
            pass

    if isinstance(value, (int, float)) and not isinstance(value, bool):
        try:
            parsed = pd.Timestamp("1899-12-30") + pd.Timedelta(days=float(value))
            return parsed.strftime(OUTPUT_DATE_FORMAT), None
        except (ValueError, OverflowError):
            return None, f"Could not parse Excel date number: '{value}'"

    if isinstance(value, str):
        text = _fix_zero_month_day(value.strip())
        if ISO_DATE_PATTERN.match(text):
            try:
                datetime.strptime(text, OUTPUT_DATE_FORMAT)
                return text, None
            except ValueError:
                return None, f"Invalid date: '{value}'"

        repaired = _repair_malformed_date_string(text)
        if repaired:
            repaired_text, use_dayfirst = repaired
            try:
                parsed = date_parser.parse(repaired_text, dayfirst=use_dayfirst)
                return parsed.strftime(OUTPUT_DATE_FORMAT), None
            except (ValueError, TypeError, OverflowError):
                pass

        for dayfirst in (False, True):
            try:
                parsed = date_parser.parse(text, dayfirst=dayfirst)
                return parsed.strftime(OUTPUT_DATE_FORMAT), None
            except (ValueError, TypeError, OverflowError):
                continue

        return None, f"Could not parse date: '{value}'"

    return None, f"Could not parse date: '{value}'"


def detect_date_columns(
    df: pd.DataFrame,
    column_rules: dict[str, dict] | None = None,
) -> list[str]:
    """Suggest date columns from detected/inferred field types."""
    column_rules = column_rules or {}
    date_cols: set[str] = set()

    for col, rule in column_rules.items():
        if rule.get("type") == "date" and col in df.columns:
            date_cols.add(col)

    for col in df.columns:
        if col.startswith("__"):
            continue
        if col in date_cols:
            continue
        if DATE_NAME_PATTERN.search(col):
            date_cols.add(col)
        elif pd.api.types.is_datetime64_any_dtype(df[col]):
            date_cols.add(col)

    return sorted(date_cols)


def normalize_date_columns(
    df: pd.DataFrame, date_columns: list[str]
) -> tuple[pd.DataFrame, list[ValidationIssue]]:
    """Convert date column values to YYYY-MM-DD strings."""
    normalized = df.copy()
    issues: list[ValidationIssue] = []

    for col in date_columns:
        if col not in normalized.columns:
            continue

        converted: list[Any] = []
        for idx, value in normalized[col].items():
            formatted, error = parse_date_value(value)
            if error:
                issues.append(
                    ValidationIssue(
                        row=int(idx) + 2,
                        column=col,
                        value=value,
                        rule="date_format",
                        message=error,
                    )
                )
                converted.append(value)
            elif formatted is None:
                converted.append(pd.NA)
            else:
                converted.append(formatted)

        normalized[col] = converted

    return normalized, issues


def _check_type(value: Any, col_rule: dict) -> str | None:
    dtype = col_rule.get("type", "string")

    if _is_empty(value):
        return None

    if dtype == "string":
        if isinstance(value, (str, int, float, bool)):
            return None
        return f"Expected text, got {type(value).__name__}"

    if dtype == "integer":
        if isinstance(value, bool):
            return "Expected whole number, got boolean"
        if isinstance(value, int):
            return None
        if isinstance(value, float) and value.is_integer():
            return None
        return f"Expected whole number, got '{value}'"

    if dtype == "float":
        if isinstance(value, bool):
            return "Expected number, got boolean"
        if isinstance(value, (int, float)):
            return None
        return f"Expected number, got '{value}'"

    if dtype == "date":
        formatted, error = parse_date_value(value)
        if error:
            return error
        if formatted and ISO_DATE_PATTERN.match(formatted):
            return None
        return f"Expected date in format YYYY-MM-DD, got '{value}'"

    if dtype == "email":
        if not isinstance(value, str) or not EMAIL_PATTERN.match(value.strip()):
            return f"Invalid email format: '{value}'"
        return None

    if dtype == "phone":
        if not isinstance(value, str) or not PHONE_PATTERN.match(value.strip()):
            return f"Invalid phone format: '{value}'"
        return None

    if dtype == "boolean":
        normalized = _normalize_checkbox_value(value)
        if normalized in ("TRUE", "FALSE"):
            return None
        return f"Expected TRUE or FALSE, got '{value}'"

    if dtype == "lookup":
        if isinstance(value, (str, int, float, bool)):
            return None
        return f"Expected lookup name/text, got {type(value).__name__}"

    if dtype in ("picklist", "multipicklist"):
        if isinstance(value, (str, int, float, bool)):
            return None
        return f"Expected picklist text, got {type(value).__name__}"

    if dtype == "salesforce_id":
        if _is_empty(value):
            return None
        if not isinstance(value, str) or not SALESFORCE_ID_PATTERN.match(value.strip()):
            return f"Expected Salesforce ID (18 chars, starts with 00), got '{value}'"
        return None

    if dtype == "state_code":
        if not isinstance(value, str) or not STATE_CODE_PATTERN.match(value.strip()):
            return f"Expected 2-letter state/province code (e.g. MS, CA), got '{value}'"
        return None

    if dtype == "website":
        if not isinstance(value, str) or not WEBSITE_PATTERN.match(value.strip()):
            return f"Invalid website/URL format: '{value}'"
        return None

    return None


def validate_dataframe(
    df: pd.DataFrame,
    column_rules: dict[str, dict],
    config: dict | None = None,
    apply_cleansing: bool = True,
    mandatory_columns: list[str] | None = None,
    date_columns: list[str] | None = None,
    normalize_dates: bool = True,
    field_definition: Any | None = None,
) -> ValidationResult:
    issues: list[ValidationIssue] = []
    config = config or {}
    column_rules = {k: dict(v) for k, v in column_rules.items()}
    working_df = cleanse_dataframe(df, column_rules) if apply_cleansing else df.copy()
    mandatory_set = set(mandatory_columns or [])
    ignore_prefixes = config.get("ignore_column_prefixes", [])

    def _should_ignore_column(col_name: str) -> bool:
        return any(col_name.startswith(prefix) for prefix in ignore_prefixes)

    # Build rules for every column in the file (accept all columns)
    for col in working_df.columns:
        if col not in column_rules and not _should_ignore_column(col):
            column_rules[col] = {"name": col, "type": "string", "source": "default"}

    date_column_set = set(date_columns) if date_columns is not None else {
        col for col, rule in column_rules.items() if rule.get("type") == "date"
    }
    date_column_set -= {c for c in working_df.columns if _should_ignore_column(c)}

    cols_to_validate = {
        c for c in working_df.columns if not _should_ignore_column(c)
    }

    if normalize_dates and date_column_set:
        working_df, date_issues = normalize_date_columns(working_df, sorted(date_column_set))
        issues.extend(date_issues)

    for col_name in sorted(cols_to_validate):
        if col_name not in working_df.columns:
            continue

        col_rule = column_rules.get(col_name, {"name": col_name, "type": "string"})
        series = working_df[col_name]
        is_required = col_name in mandatory_set

        # Required check (driven by UI selection only)
        if is_required:
            empty_mask = series.apply(_is_empty)
            for idx in series[empty_mask].index:
                issues.append(
                    ValidationIssue(
                        row=int(idx) + 2,  # +2 for 1-based index + header row
                        column=col_name,
                        value=series[idx],
                        rule="required",
                        message="Value is required but empty",
                    )
                )

        # Unique check
        if col_rule.get("unique", False):
            non_empty = series.dropna()
            non_empty = non_empty[non_empty.astype(str).str.strip() != ""]
            duplicates = non_empty[non_empty.duplicated(keep=False)]
            for idx in duplicates.index:
                issues.append(
                    ValidationIssue(
                        row=int(idx) + 2,
                        column=col_name,
                        value=series[idx],
                        rule="unique",
                        message="Duplicate value found (must be unique)",
                    )
                )

        if col_name in date_column_set:
            if not normalize_dates:
                for idx, value in series.items():
                    if _is_empty(value):
                        continue
                    _, error = parse_date_value(value)
                    if error:
                        issues.append(
                            ValidationIssue(
                                row=int(idx) + 2,
                                column=col_name,
                                value=value,
                                rule="date_format",
                                message=error,
                            )
                        )
            continue

        # Per-row type and format checks
        for idx, value in series.items():
            if _is_empty(value):
                continue

            type_error = _check_type(value, col_rule)
            if type_error:
                issues.append(
                    ValidationIssue(
                        row=int(idx) + 2,
                        column=col_name,
                        value=value,
                        rule="type",
                        message=type_error,
                    )
                )
                continue

            str_value = str(value).strip() if not isinstance(value, (int, float, bool)) else value

            if "min_length" in col_rule and isinstance(str_value, str):
                if len(str_value) < col_rule["min_length"]:
                    issues.append(
                        ValidationIssue(
                            row=int(idx) + 2,
                            column=col_name,
                            value=value,
                            rule="min_length",
                            message=f"Minimum length is {col_rule['min_length']}",
                        )
                    )

            if "max_length" in col_rule and isinstance(str_value, str):
                if len(str_value) > col_rule["max_length"]:
                    issues.append(
                        ValidationIssue(
                            row=int(idx) + 2,
                            column=col_name,
                            value=value,
                            rule="max_length",
                            message=f"Maximum length is {col_rule['max_length']}",
                        )
                    )

            if "min_value" in col_rule and isinstance(value, (int, float)):
                if value < col_rule["min_value"]:
                    issues.append(
                        ValidationIssue(
                            row=int(idx) + 2,
                            column=col_name,
                            value=value,
                            rule="min_value",
                            message=f"Minimum value is {col_rule['min_value']}",
                        )
                    )

            if "max_value" in col_rule and isinstance(value, (int, float)):
                if value > col_rule["max_value"]:
                    issues.append(
                        ValidationIssue(
                            row=int(idx) + 2,
                            column=col_name,
                            value=value,
                            rule="max_value",
                            message=f"Maximum value is {col_rule['max_value']}",
                        )
                    )

            if "allowed_values" in col_rule:
                normalized = str(value).strip().lower() if isinstance(value, str) else value
                allowed = [v.lower() if isinstance(v, str) else v for v in col_rule["allowed_values"]]
                if normalized not in allowed:
                    issues.append(
                        ValidationIssue(
                            row=int(idx) + 2,
                            column=col_name,
                            value=value,
                            rule="allowed_values",
                            message=f"Value must be one of: {col_rule['allowed_values']}",
                        )
                    )

            if "pattern" in col_rule and isinstance(value, str):
                if not re.match(col_rule["pattern"], value.strip()):
                    issues.append(
                        ValidationIssue(
                            row=int(idx) + 2,
                            column=col_name,
                            value=value,
                            rule="pattern",
                            message=f"Value does not match required pattern",
                        )
                    )

    if field_definition is not None:
        from field_definition import validate_picklist_fields

        issues.extend(validate_picklist_fields(working_df, field_definition))

    return ValidationResult(
        total_rows=len(working_df),
        total_columns=len(working_df.columns),
        issues=issues,
        cleansed_df=append_row_status_column(working_df, issues),
    )


STATUS_COLUMN = "Status"
STATUS_READY = "Ready"
STATUS_NOT_READY = "Not Ready"


def append_row_status_column(
    df: pd.DataFrame,
    issues: list[ValidationIssue],
    errors_only: bool = True,
) -> pd.DataFrame:
    """Append a Status column: Ready when the row has no errors, else Not Ready."""
    result = df.copy()
    if STATUS_COLUMN in result.columns:
        result = result.drop(columns=[STATUS_COLUMN])

    statuses = [STATUS_READY] * len(result)
    for issue in issues:
        if errors_only and issue.severity != "error":
            continue
        if issue.row <= 0:
            continue
        row_index = issue.row - 2
        if 0 <= row_index < len(statuses):
            statuses[row_index] = STATUS_NOT_READY

    result[STATUS_COLUMN] = statuses
    return result


def issues_to_dataframe(issues: list[ValidationIssue]) -> pd.DataFrame:
    if not issues:
        return pd.DataFrame(columns=["Row", "Column", "Value", "Rule", "Severity", "Message"])
    return pd.DataFrame(
        [
            {
                "Row": i.row,
                "Column": i.column,
                "Value": i.value,
                "Rule": i.rule,
                "Severity": i.severity,
                "Message": i.message,
            }
            for i in issues
        ]
    )


ERROR_FILL_COLOR = "FFC7CE"  # light red
WARNING_FILL_COLOR = "FFEB9C"  # light yellow


def export_excel_with_highlights(
    df: pd.DataFrame,
    issues: list[ValidationIssue],
    highlight_errors: bool = True,
    highlight_warnings: bool = False,
    column_rename: dict[str, str] | None = None,
) -> bytes:
    """Write Excel bytes with validation issue cells highlighted."""
    from openpyxl import load_workbook
    from openpyxl.comments import Comment
    from openpyxl.styles import PatternFill

    column_rename = column_rename or {}

    buffer = io.BytesIO()
    df.to_excel(buffer, index=False, engine="openpyxl")
    buffer.seek(0)

    wb = load_workbook(buffer)
    ws = wb.active
    col_index = {name: idx + 1 for idx, name in enumerate(df.columns)}

    error_fill = PatternFill(start_color=ERROR_FILL_COLOR, end_color=ERROR_FILL_COLOR, fill_type="solid")
    warning_fill = PatternFill(start_color=WARNING_FILL_COLOR, end_color=WARNING_FILL_COLOR, fill_type="solid")

    for issue in issues:
        if issue.severity == "error" and not highlight_errors:
            continue
        if issue.severity == "warning" and not highlight_warnings:
            continue
        export_column = column_rename.get(issue.column, issue.column)
        if export_column not in col_index:
            continue

        excel_row = 1 if issue.row == 0 else issue.row
        excel_col = col_index[export_column]
        cell = ws.cell(row=excel_row, column=excel_col)
        cell.fill = error_fill if issue.severity == "error" else warning_fill

        comment_text = f"{issue.rule}: {issue.message}"
        if cell.comment is None:
            cell.comment = Comment(comment_text, APP_NAME)
        else:
            cell.comment = Comment(f"{cell.comment.text}; {comment_text}", APP_NAME)

    out = io.BytesIO()
    wb.save(out)
    return out.getvalue()


def count_highlighted_cells(issues: list[ValidationIssue], include_warnings: bool = False) -> int:
    """Count unique cells that would be highlighted."""
    cells: set[tuple[int, str]] = set()
    for issue in issues:
        if issue.severity == "error" or (include_warnings and issue.severity == "warning"):
            if issue.column:
                cells.add((issue.row, issue.column))
    return len(cells)
