"""Professional black & grey UI styling for the Streamlit app."""

from __future__ import annotations

import streamlit as st

APP_NAME = "CleanMap"

THEME_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');

:root {
    --bg-primary: #0B0B0C;
    --bg-secondary: #141416;
    --bg-elevated: #1C1C1F;
    --bg-muted: #242428;
    --border-subtle: #2E2E33;
    --border-strong: #3A3A40;
    --text-primary: #F2F2F3;
    --text-secondary: #A1A1A8;
    --text-muted: #6B6B73;
    --accent: #FFFFFF;
    --accent-soft: #D9D9DE;
}

html, body, [class*="css"] {
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
}

[data-testid="stAppViewContainer"] {
    background: linear-gradient(180deg, #0B0B0C 0%, #101012 100%);
}

[data-testid="stHeader"] {
    background: rgba(11, 11, 12, 0.92);
    border-bottom: 1px solid var(--border-subtle);
}

[data-testid="stSidebar"] {
    background: linear-gradient(180deg, #0E0E10 0%, #121214 100%);
    border-right: 1px solid var(--border-subtle);
}

[data-testid="stSidebar"] > div:first-child {
    background: transparent;
}

[data-testid="stSidebar"] [data-testid="stMarkdownContainer"] h1,
[data-testid="stSidebar"] [data-testid="stMarkdownContainer"] h2,
[data-testid="stSidebar"] [data-testid="stMarkdownContainer"] h3 {
    color: var(--text-primary);
    letter-spacing: -0.02em;
}

.main .block-container {
    padding-top: 2rem;
    padding-bottom: 3rem;
    max-width: 1180px;
}

.app-hero {
    background: linear-gradient(135deg, #151517 0%, #1A1A1D 55%, #111113 100%);
    border: 1px solid var(--border-subtle);
    border-radius: 16px;
    padding: 2rem 2rem 2.25rem 2rem;
    margin-bottom: 1.75rem;
    box-shadow: 0 18px 48px rgba(0, 0, 0, 0.35);
    text-align: center;
}

.app-hero-kicker {
    color: var(--text-muted);
    font-size: 0.72rem;
    font-weight: 600;
    letter-spacing: 0.14em;
    text-transform: uppercase;
    margin-bottom: 0.75rem;
}

.app-hero-title {
    color: var(--text-primary);
    font-size: 2.35rem;
    font-weight: 700;
    letter-spacing: -0.03em;
    line-height: 1.1;
    margin: 0 auto;
    text-align: center;
}

.app-hero-subtitle {
    color: var(--text-secondary);
    font-size: 0.98rem;
    line-height: 1.65;
    margin: 0;
    max-width: 720px;
    text-align: center;
}

.app-hero-copy {
    display: flex;
    justify-content: center;
    align-items: center;
    width: 100%;
    margin-top: 1.85rem;
    padding-top: 0.35rem;
}

.app-hero [data-testid="stMarkdownContainer"] .app-hero-subtitle,
.app-hero-copy .app-hero-subtitle,
.app-hero-copy p {
    color: var(--text-secondary) !important;
    text-align: center !important;
    margin-left: auto !important;
    margin-right: auto !important;
}

.sidebar-brand {
    background: var(--bg-elevated);
    border: 1px solid var(--border-subtle);
    border-radius: 12px;
    padding: 1rem 1rem 0.85rem 1rem;
    margin-bottom: 1rem;
}

.sidebar-brand-title {
    color: var(--text-primary);
    font-size: 0.95rem;
    font-weight: 700;
    margin: 0 0 0.25rem 0;
}

.sidebar-brand-copy {
    color: var(--text-muted);
    font-size: 0.78rem;
    line-height: 1.45;
    margin: 0;
}

.section-heading {
    display: flex;
    align-items: center;
    gap: 0.85rem;
    margin: 1.35rem 0 0.85rem 0;
    padding-bottom: 0.65rem;
    border-bottom: 1px solid var(--border-subtle);
}

.section-badge {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    min-width: 2rem;
    height: 2rem;
    padding: 0 0.55rem;
    border-radius: 999px;
    background: var(--bg-muted);
    border: 1px solid var(--border-strong);
    color: var(--accent-soft);
    font-size: 0.78rem;
    font-weight: 700;
    letter-spacing: 0.04em;
}

.section-title {
    color: var(--text-primary);
    font-size: 1.08rem;
    font-weight: 600;
    letter-spacing: -0.02em;
    margin: 0;
}

.panel-card {
    background: var(--bg-secondary);
    border: 1px solid var(--border-subtle);
    border-radius: 14px;
    padding: 1rem 1.15rem;
    margin: 0.35rem 0 1rem 0;
}

.panel-card h4 {
    color: var(--text-primary);
    font-size: 0.92rem;
    font-weight: 600;
    margin: 0 0 0.45rem 0;
}

.panel-card p, .panel-card li {
    color: var(--text-secondary);
    font-size: 0.88rem;
    line-height: 1.55;
}

.workflow-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
    gap: 0.85rem;
    margin-top: 0.75rem;
}

.workflow-item {
    background: var(--bg-secondary);
    border: 1px solid var(--border-subtle);
    border-radius: 12px;
    padding: 0.95rem 1rem;
}

.workflow-item strong {
    display: block;
    color: var(--text-primary);
    font-size: 0.84rem;
    margin-bottom: 0.35rem;
}

.workflow-item span {
    color: var(--text-secondary);
    font-size: 0.8rem;
    line-height: 1.45;
}

[data-testid="stMetric"] {
    background: var(--bg-secondary);
    border: 1px solid var(--border-subtle);
    border-radius: 14px;
    padding: 0.95rem 1rem;
    box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.02);
}

[data-testid="stMetricLabel"] {
    color: var(--text-muted) !important;
    font-size: 0.78rem !important;
    font-weight: 600 !important;
    letter-spacing: 0.06em;
    text-transform: uppercase;
}

[data-testid="stMetricValue"] {
    color: var(--text-primary) !important;
    font-weight: 700 !important;
    letter-spacing: -0.02em;
}

[data-testid="stAlert"] {
    border-radius: 12px;
    border: 1px solid var(--border-subtle);
    background: var(--bg-secondary);
}

[data-testid="stFileUploader"] section {
    background: var(--bg-secondary);
    border: 1px dashed var(--border-strong);
    border-radius: 14px;
}

[data-testid="stFileUploader"] section:hover {
    border-color: #5A5A62;
    background: var(--bg-elevated);
}

[data-testid="stTabs"] [data-baseweb="tab-list"] {
    gap: 0.35rem;
    background: transparent;
    border-bottom: 1px solid var(--border-subtle);
}

[data-testid="stTabs"] button[data-baseweb="tab"] {
    background: transparent;
    color: var(--text-secondary);
    border-radius: 10px 10px 0 0;
    padding-top: 0.65rem;
    padding-bottom: 0.65rem;
}

[data-testid="stTabs"] button[data-baseweb="tab"][aria-selected="true"] {
    background: var(--bg-secondary);
    color: var(--text-primary);
    border: 1px solid var(--border-subtle);
    border-bottom-color: transparent;
}

.stButton > button {
    border-radius: 10px;
    border: 1px solid var(--border-strong);
    background: var(--bg-muted);
    color: var(--text-primary);
    font-weight: 600;
    transition: all 0.18s ease;
}

.stButton > button:hover {
    border-color: #66666E;
    background: #2C2C31;
    color: var(--accent);
}

.stButton > button[kind="primary"],
.stButton > button[data-testid="baseButton-primary"] {
    background: linear-gradient(180deg, #F5F5F7 0%, #D9D9DE 100%);
    color: #111114;
    border: 1px solid #ECECF0;
}

.stButton > button[kind="primary"]:hover,
.stButton > button[data-testid="baseButton-primary"]:hover {
    background: linear-gradient(180deg, #FFFFFF 0%, #E5E5EA 100%);
    color: #09090A;
}

[data-testid="stExpander"] {
    background: var(--bg-secondary);
    border: 1px solid var(--border-subtle);
    border-radius: 12px;
}

[data-testid="stDataFrame"], [data-testid="stDataEditor"] {
    border: 1px solid var(--border-subtle);
    border-radius: 12px;
    overflow: hidden;
}

[data-testid="stCaptionContainer"] {
    color: var(--text-muted) !important;
}

h1, h2, h3, h4, h5, h6, label, p, span, div {
    color-scheme: dark;
}

hr {
    border-color: var(--border-subtle);
}

#MainMenu { visibility: hidden; }
footer { visibility: hidden; }
</style>
"""


def inject_theme() -> None:
    st.markdown(THEME_CSS, unsafe_allow_html=True)


def render_app_header() -> None:
    st.markdown(
        f"""
        <div class="app-hero">
            <div class="app-hero-title">{APP_NAME}</div>
            <div class="app-hero-copy">
                <p class="app-hero-subtitle">
                    {APP_NAME} validates and cleanses legacy Excel imports before loading into Salesforce.
                    Field types, lookups, and picklists are checked against your source files.
                </p>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_sidebar_brand() -> None:
    st.markdown(
        f"""
        <div class="sidebar-brand">
            <div class="sidebar-brand-title">{APP_NAME}</div>
            <p class="sidebar-brand-copy">
                Configure cleansing options and choose how large files are loaded.
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_section_heading(step: str, title: str) -> None:
    st.markdown(
        f"""
        <div class="section-heading">
            <span class="section-badge">{step}</span>
            <h3 class="section-title">{title}</h3>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_workflow_intro() -> None:
    st.markdown(
        """
        <div class="panel-card">
            <h4>Getting started</h4>
            <p>Upload your main Excel file or load one from a local path to begin validation.</p>
            <div class="workflow-grid">
                <div class="workflow-item"><strong>1. Load data</strong><span>Upload the migration workbook or point to a local file path.</span></div>
                <div class="workflow-item"><strong>2. Review fields</strong><span>Confirm detected Salesforce field types from the source sheet.</span></div>
                <div class="workflow-item"><strong>3. Resolve lookups</strong><span>Optionally attach reference files for lookup ID resolution.</span></div>
                <div class="workflow-item"><strong>4. Validate picklists</strong><span>Optionally attach object field definitions for picklist checks.</span></div>
                <div class="workflow-item"><strong>5. Run validation</strong><span>Generate cleansed output, issue reports, and row status.</span></div>
                <div class="workflow-item"><strong>6. Download</strong><span>Export the prepared file for Salesforce Inspector import.</span></div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_results_heading() -> None:
    st.markdown(
        """
        <div class="section-heading" style="margin-top: 0;">
            <span class="section-badge">✓</span>
            <h3 class="section-title">Validation Results</h3>
        </div>
        """,
        unsafe_allow_html=True,
    )
