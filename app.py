"""Streamlit app for Salesforce legacy Excel validation and cleansing."""

import importlib
import io
from pathlib import Path
from typing import Any

import pandas as pd
import streamlit as st

import field_definition
import lookup_resolver
import schema
import ui_theme
import validator
import excel_io

importlib.reload(excel_io)
importlib.reload(ui_theme)
importlib.reload(schema)
importlib.reload(lookup_resolver)
importlib.reload(field_definition)
importlib.reload(validator)

from field_definition import ObjectFieldDefinition, read_object_field_definition

from lookup_resolver import (
    apply_lookup_resolution,
    build_lookup_export_rename,
    group_lookup_fields_by_object,
    lookup_resolution_issues,
    prepare_lookup_export_dataframe,
    read_lookup_reference_file,
    resolved_id_column,
)
from schema import VALIDATOR_TYPES, build_column_rules, date_columns_from_types, read_excel_with_schema
from validator import (
    count_highlighted_cells,
    export_excel_with_highlights,
    issues_to_dataframe,
    load_rules,
    validate_dataframe,
)
from ui_theme import (
    APP_NAME,
    inject_theme,
    render_app_header,
    render_results_heading,
    render_section_heading,
    render_sidebar_brand,
    render_workflow_intro,
)

CONFIG_PATH = Path(__file__).parent / "rules.yaml"

st.set_page_config(
    page_title=APP_NAME,
    page_icon="◆",
    layout="wide",
    initial_sidebar_state="expanded",
)
inject_theme()
render_app_header()


def _load_config() -> dict:
    if CONFIG_PATH.exists():
        return load_rules(str(CONFIG_PATH))
    return {"ignore_column_prefixes": ["__"]}


def _file_key(uploaded_file) -> str:
    return f"{uploaded_file.name}:{uploaded_file.size}"


def _local_file_key(path: Path) -> str:
    stat = path.stat()
    return f"local:{path}:{stat.st_mtime_ns}:{stat.st_size}"


def _resolve_main_file(
    use_local_path: bool,
    local_path: str,
    uploaded_file,
) -> tuple[Any, str | None]:
    """Return (file source, cache key) from upload or local disk path."""
    if use_local_path:
        path_text = local_path.strip()
        if not path_text:
            return None, None
        path = Path(path_text).expanduser()
        if not path.is_file():
            st.error(f"File not found: {path}")
            return None, None
        if path.suffix.lower() not in {".xlsx", ".xls"}:
            st.warning("Expected a `.xlsx` or `.xls` file.")
        return path, _local_file_key(path)

    if uploaded_file is None:
        return None, None
    return uploaded_file, _file_key(uploaded_file)


def _rules_with_resolved_ids(column_rules: dict, lookup_fields: dict[str, str]) -> dict:
    rules = dict(column_rules)
    for col in lookup_fields:
        id_col = resolved_id_column(col)
        rules[id_col] = {"name": id_col, "type": "salesforce_id", "source": "lookup_resolve"}
    return rules


config = _load_config()

with st.sidebar:
    render_sidebar_brand()
    st.markdown("##### Processing options")
    apply_cleansing = st.checkbox(
        "Auto-cleanse (trim whitespace, normalize blanks)",
        value=True,
        key="apply_cleansing",
    )
    normalize_dates = st.checkbox(
        "Convert date fields to YYYY-MM-DD",
        value=True,
        key="normalize_dates",
    )
    st.divider()
    st.markdown("##### Large files")
    use_local_path = st.checkbox(
        "Load from local file path",
        value=False,
        help="Bypass the browser upload limit by reading a file already on this machine.",
        key="use_local_path",
    )
    local_path = ""
    if use_local_path:
        local_path = st.text_input(
            "Full path to Excel file",
            placeholder="/Users/you/data/migration.xlsx",
            key="local_file_path",
        )
    else:
        st.caption(
            "Browser uploads are limited by `server.maxUploadSize` in `.streamlit/config.toml` "
            "(currently 1024 MB). Restart Streamlit after changing it."
        )

if use_local_path:
    uploaded_file = None
    render_section_heading("01", "Load main Excel file")
    st.caption("Using local file path — no browser upload.")
else:
    render_section_heading("01", "Upload main Excel file")
    uploaded_file = st.file_uploader(
        "Step 1 — Upload main Excel file (.xlsx or .xls)",
        type=["xlsx", "xls"],
        key="main_file_uploader",
    )

main_file, file_key = _resolve_main_file(use_local_path, local_path, uploaded_file)

if main_file:
    try:
        if st.session_state.get("file_key") != file_key:
            st.session_state["file_key"] = file_key
            st.session_state.pop("validation_result", None)
            st.session_state.pop("mandatory_columns", None)
            st.session_state.pop("mandatory_columns_select", None)
            st.session_state.pop("column_types", None)
            st.session_state.pop("lookup_tables", None)
            st.session_state.pop("lookup_stats", None)
            st.session_state.pop("field_definition", None)

        if hasattr(main_file, "seek"):
            main_file.seek(0)
        excel_schema = read_excel_with_schema(main_file, config)
        df = excel_schema.df
        lookup_fields = dict(excel_schema.lookup_fields)

        import_columns = [c for c in df.columns if not c.startswith("__")]
        if not import_columns:
            st.warning("No import columns found in the uploaded file.")
            st.stop()

        st.info(
            f"Loaded **{len(df)}** rows from sheet **'{excel_schema.data_sheet}'** · "
            f"Types detected via **{excel_schema.detection_method.replace('_', ' ')}**"
        )

        # --- Field types ---
        render_section_heading("02", "Review field types")
        if st.session_state.get("column_types") is None:
            st.session_state["column_types"] = dict(excel_schema.column_types)

        type_rows = []
        for col in import_columns:
            raw_type = excel_schema.raw_types.get(col, "")
            type_rows.append(
                {
                    "API Name": col,
                    "Field Label": excel_schema.field_labels.get(col, ""),
                    "SF Data Type": raw_type,
                    "Data type": st.session_state["column_types"].get(
                        col, excel_schema.column_types.get(col, "string")
                    ),
                }
            )

        edited_types = st.data_editor(
            pd.DataFrame(type_rows),
            column_config={
                "API Name": st.column_config.TextColumn(disabled=True),
                "Field Label": st.column_config.TextColumn(disabled=True),
                "SF Data Type": st.column_config.TextColumn(disabled=True),
                "Data type": st.column_config.SelectboxColumn(options=VALIDATOR_TYPES, required=True),
            },
            hide_index=True,
            use_container_width=True,
            key="type_editor",
        )

        column_types = {row["API Name"]: row["Data type"] for _, row in edited_types.iterrows()}
        st.session_state["column_types"] = column_types
        column_rules = build_column_rules(column_types, lookup_fields)
        date_columns = date_columns_from_types(column_types)

        if date_columns:
            st.success(f"**{len(date_columns)} date field(s)** detected — will convert to YYYY-MM-DD.")
            with st.expander("View date fields"):
                st.write(", ".join(date_columns))

        # --- Lookup fields (optional reference uploads) ---
        render_section_heading("03", "Lookup field resolution (optional)")
        lookup_tables: dict[str, pd.DataFrame] = st.session_state.get("lookup_tables") or {}

        if lookup_fields:
            grouped = group_lookup_fields_by_object(lookup_fields)
            st.info(
                f"Found **{len(lookup_fields)} lookup field(s)** across "
                f"**{len(grouped)} object type(s)**. Upload reference files for the objects "
                "you want to resolve — **uploads are optional**. "
                f"On **Run validation**, Salesforce Ids are resolved next to each lookup field. "
                "On download, lookup **name** columns are prefixed with `_` and **Id** columns "
                "keep the original API name for Salesforce Inspector."
            )

            lookup_overview = pd.DataFrame(
                [
                    {
                        "API Name": col,
                        "Name export": f"_{col}" if not col.startswith("_") else col,
                        "Id export": col,
                        "Field Label": excel_schema.field_labels.get(col, col),
                        "SF Data Type": excel_schema.raw_types.get(col, f"Lookup ({obj})"),
                        "References Object": obj,
                    }
                    for col, obj in lookup_fields.items()
                ]
            )
            st.dataframe(lookup_overview, use_container_width=True, hide_index=True)

            for object_name, columns in grouped.items():
                st.markdown(f"#### **{object_name}** lookup file (optional)")
                st.caption(
                    f"Used for: {', '.join(columns)} · "
                    "File must contain **Name** and **Id** columns."
                )
                lookup_upload = st.file_uploader(
                    f"{object_name} reference file",
                    type=["xlsx", "xls"],
                    key=f"lookup_upload_{object_name}",
                )
                if lookup_upload:
                    try:
                        lookup_upload.seek(0)
                        ref_df = read_lookup_reference_file(lookup_upload)
                        lookup_tables[object_name] = ref_df
                        st.session_state["lookup_tables"] = lookup_tables
                        st.success(f"Loaded **{len(ref_df)}** {object_name} records.")
                    except Exception as exc:
                        st.error(f"Could not read {object_name} lookup file: {exc}")

                if object_name in lookup_tables:
                    st.caption(
                        f"✓ {object_name} reference ready ({len(lookup_tables[object_name])} rows)"
                    )
        else:
            st.caption("No lookup fields detected in row 3 data types.")

        # --- Object field definition (optional picklist validation) ---
        render_section_heading("04", "Object field definition (optional)")
        field_def: ObjectFieldDefinition | None = st.session_state.get("field_definition")
        picklist_columns = [
            col
            for col in import_columns
            if "picklist" in str(excel_schema.raw_types.get(col, "")).lower()
        ]

        st.caption(
            "Upload an object field definition file with **API Name** and **Picklist Values** "
            "columns. Picklist values in the main sheet are validated against this file using "
            "field API names."
        )
        if picklist_columns:
            st.info(
                f"Detected **{len(picklist_columns)} picklist field(s)** in the main file."
            )
            with st.expander("View picklist fields in main file"):
                st.write(", ".join(picklist_columns))

        field_def_upload = st.file_uploader(
            "Object field definition file",
            type=["xlsx", "xls"],
            key="field_definition_upload",
        )
        if field_def_upload:
            try:
                field_def_upload.seek(0)
                field_def = read_object_field_definition(field_def_upload)
                st.session_state["field_definition"] = field_def
                matched = [
                    col
                    for col in picklist_columns
                    if col in field_def.picklist_fields or col in field_def.multipicklist_fields
                ]
                st.success(
                    f"Loaded field definition for **{field_def.object_label or 'object'}** "
                    f"(`{field_def.object_api_name or 'n/a'}`) with "
                    f"**{field_def.validated_field_count}** picklist field(s)."
                )
                if matched:
                    st.caption(
                        f"**{len(matched)}** picklist field(s) match between the main file "
                        "and definition file."
                    )
                overview_rows = []
                for col in sorted(set(field_def.picklist_fields) | set(field_def.multipicklist_fields)):
                    overview_rows.append(
                        {
                            "API Name": col,
                            "Field kind": (
                                "Multi-select"
                                if col in field_def.multipicklist_fields
                                else "Picklist"
                            ),
                            "In main file": "Yes" if col in import_columns else "No",
                            "Allowed values": len(
                                field_def.multipicklist_fields.get(col)
                                or field_def.picklist_fields.get(col)
                                or []
                            ),
                        }
                    )
                with st.expander("Picklist fields in definition file"):
                    st.dataframe(
                        pd.DataFrame(overview_rows),
                        use_container_width=True,
                        hide_index=True,
                    )
            except Exception as exc:
                st.error(f"Could not read object field definition file: {exc}")
        elif field_def:
            st.caption(
                f"✓ Field definition ready — {field_def.validated_field_count} picklist field(s) loaded."
            )

        # --- Mandatory columns ---
        render_section_heading("05", "Select mandatory columns")
        col_left, _ = st.columns([1, 3])
        with col_left:
            if st.button("Select all mandatory", key="select_all_mandatory"):
                st.session_state["mandatory_columns_select"] = import_columns
            if st.button("Clear all mandatory", key="clear_all_mandatory"):
                st.session_state["mandatory_columns_select"] = []

        mandatory_options = [c for c in import_columns if not c.startswith("__")]
        if "mandatory_columns_select" not in st.session_state:
            legacy = st.session_state.get("mandatory_columns", [])
            st.session_state["mandatory_columns_select"] = [
                c for c in legacy if c in mandatory_options
            ]

        mandatory_columns = st.multiselect(
            "Mandatory columns",
            options=mandatory_options,
            key="mandatory_columns_select",
        )

        # --- Validate ---
        render_section_heading("06", "Validate")
        if st.button("Run validation", type="primary", key="run_validation"):
            working_df = df
            lookup_stats: dict = {}

            if lookup_fields:
                working_df, lookup_stats = apply_lookup_resolution(
                    df, lookup_fields, lookup_tables
                )

            validation_rules = _rules_with_resolved_ids(column_rules, lookup_fields)
            result = validate_dataframe(
                working_df,
                validation_rules,
                config=config,
                apply_cleansing=apply_cleansing,
                mandatory_columns=mandatory_columns,
                date_columns=date_columns,
                normalize_dates=normalize_dates,
                field_definition=field_def,
            )
            if lookup_fields:
                result.issues.extend(
                    lookup_resolution_issues(working_df, lookup_fields, lookup_tables)
                )
            st.session_state["validation_result"] = result
            st.session_state["lookup_stats"] = lookup_stats

        result = st.session_state.get("validation_result")

        if result:
            st.divider()
            render_results_heading()

            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Total Rows", result.total_rows)
            c2.metric("Total Columns", result.total_columns)
            c3.metric("Errors", result.error_count)
            c4.metric("Warnings", result.warning_count)

            if result.is_valid:
                st.success("All checks passed.")
            else:
                st.error(f"Found {result.error_count} error(s).")

            if lookup_fields:
                lookup_stats = st.session_state.get("lookup_stats", {})
                if lookup_stats:
                    stats_rows = []
                    for col, s in lookup_stats.items():
                        stats_rows.append(
                            {
                                "Lookup column": col,
                                "Object": lookup_fields[col],
                                "Reference loaded": "Yes" if s.get("reference_loaded") else "No",
                                "Matched": s["matched"],
                                "Already Id": s["already_id"],
                                "Unresolved": s["unresolved"],
                                "Empty": s["empty"],
                            }
                        )
                    with st.expander("Lookup resolution summary"):
                        st.dataframe(
                            pd.DataFrame(stats_rows), use_container_width=True, hide_index=True
                        )

            tab_preview, tab_errors, tab_summary = st.tabs(
                ["Data Preview", "Issues", "Summary by Column"]
            )

            with tab_preview:
                st.dataframe(result.cleansed_df, use_container_width=True)
                st.caption(
                    "The **Status** column shows **Ready** when a row has no validation errors, "
                    "otherwise **Not Ready**."
                )
                if lookup_fields:
                    st.caption(
                        "Lookup name columns are prefixed with `_` in the download; "
                        "Id columns use the original API name (e.g. `Title_Checklist_Preparer__c`)."
                    )

            with tab_errors:
                issues_df = issues_to_dataframe(result.issues)
                if not issues_df.empty:
                    st.dataframe(issues_df, use_container_width=True)
                else:
                    st.success("No issues found.")

            with tab_summary:
                if result.issues:
                    summary = (
                        issues_to_dataframe(result.issues)
                        .groupby(["Column", "Rule"])
                        .size()
                        .reset_index(name="Count")
                    )
                    st.dataframe(summary, use_container_width=True)

            if result.cleansed_df is not None:
                render_section_heading("DL", "Download cleansed file")
                error_cells = count_highlighted_cells(result.issues)
                highlight_errors = st.checkbox(
                    "Highlight error cells in Excel (red fill + comment on each issue)",
                    value=result.error_count > 0,
                    key="highlight_errors",
                )
                highlight_warnings = st.checkbox(
                    "Also highlight warnings (yellow fill)",
                    value=False,
                    key="highlight_warnings",
                )

                if highlight_errors and error_cells:
                    st.caption(f"**{error_cells}** cell(s) will be highlighted in the download.")

                export_rename = build_lookup_export_rename(result.cleansed_df, lookup_fields)
                export_df = prepare_lookup_export_dataframe(result.cleansed_df, lookup_fields)

                if highlight_errors or highlight_warnings:
                    excel_bytes = export_excel_with_highlights(
                        export_df,
                        result.issues,
                        highlight_errors=highlight_errors,
                        highlight_warnings=highlight_warnings,
                        column_rename=export_rename,
                    )
                    file_name = "cleansed_output_highlighted.xlsx"
                else:
                    buffer = io.BytesIO()
                    export_df.to_excel(buffer, index=False, engine="openpyxl")
                    excel_bytes = buffer.getvalue()
                    file_name = "cleansed_output.xlsx"

                st.download_button(
                    "Download Cleansed Excel",
                    data=excel_bytes,
                    file_name=file_name,
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                )
        else:
            st.info("Review field types, upload lookup files if needed, then click **Run validation**.")

    except Exception as e:
        st.error(f"Failed to process file: {e}")

else:
    render_workflow_intro()
