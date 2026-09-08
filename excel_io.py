"""Read Excel files in both .xlsx (openpyxl) and legacy .xls (xlrd) formats."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd


def excel_engine_for_path(path: str) -> str:
    lower = str(path).lower()
    if lower.endswith(".xls") and not lower.endswith(".xlsx"):
        return "xlrd"
    return "openpyxl"


def detect_excel_engine(file: Any) -> str:
    if hasattr(file, "name") and file.name:
        return excel_engine_for_path(file.name)
    if isinstance(file, (str, Path)):
        return excel_engine_for_path(str(file))
    return "openpyxl"


def open_excel_file(file: Any) -> pd.ExcelFile:
    engine = detect_excel_engine(file)
    try:
        return pd.ExcelFile(file, engine=engine)
    except Exception:
        if hasattr(file, "seek"):
            file.seek(0)
        fallback = "xlrd" if engine == "openpyxl" else "openpyxl"
        return pd.ExcelFile(file, engine=fallback)


def read_excel_auto(file: Any, **kwargs) -> pd.DataFrame:
    engine = detect_excel_engine(file)
    try:
        return pd.read_excel(file, engine=engine, **kwargs)
    except Exception as first_error:
        if hasattr(file, "seek"):
            file.seek(0)
        fallback = "xlrd" if engine == "openpyxl" else "openpyxl"
        try:
            return pd.read_excel(file, engine=fallback, **kwargs)
        except Exception:
            raise first_error
