"""Generate CleanMap team presentation (PowerPoint)."""

from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
from pptx.util import Inches, Pt

OUTPUT = "CleanMap Presentation.pptx"

# CleanMap black & grey theme
BG_DARK = RGBColor(0x0B, 0x0B, 0x0C)
BG_PANEL = RGBColor(0x1C, 0x1C, 0x1F)
TEXT_PRIMARY = RGBColor(0xF2, 0xF2, 0xF3)
TEXT_SECONDARY = RGBColor(0xA1, 0xA1, 0xA8)
TEXT_MUTED = RGBColor(0x6B, 0x6B, 0x73)
ACCENT = RGBColor(0xFF, 0xFF, 0xFF)


def set_slide_background(slide, color: RGBColor) -> None:
    fill = slide.background.fill
    fill.solid()
    fill.fore_color.rgb = color


def add_textbox(
    slide,
    left,
    top,
    width,
    height,
    text: str,
    font_size: int = 18,
    bold: bool = False,
    color: RGBColor = TEXT_PRIMARY,
    align=PP_ALIGN.LEFT,
) -> None:
    box = slide.shapes.add_textbox(left, top, width, height)
    tf = box.text_frame
    tf.word_wrap = True
    p = tf.paragraphs[0]
    p.alignment = align
    run = p.add_run()
    run.text = text
    run.font.size = Pt(font_size)
    run.font.bold = bold
    run.font.color.rgb = color
    run.font.name = "Calibri"


def add_bullets(
    slide,
    left,
    top,
    width,
    height,
    items: list[str],
    font_size: int = 16,
    color: RGBColor = TEXT_SECONDARY,
) -> None:
    box = slide.shapes.add_textbox(left, top, width, height)
    tf = box.text_frame
    tf.word_wrap = True
    for i, item in enumerate(items):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.level = 0
        p.space_after = Pt(8)
        run = p.add_run()
        run.text = item
        run.font.size = Pt(font_size)
        run.font.color.rgb = color
        run.font.name = "Calibri"


def add_notes(slide, text: str) -> None:
    notes = slide.notes_slide.notes_text_frame
    notes.text = text


def add_header_bar(slide, title: str) -> None:
    bar = slide.shapes.add_shape(
        1, Inches(0), Inches(0), Inches(10), Inches(0.08)
    )
    bar.fill.solid()
    bar.fill.fore_color.rgb = RGBColor(0x3A, 0x3A, 0x40)
    bar.line.fill.background()

    add_textbox(
        slide,
        Inches(0.6),
        Inches(0.35),
        Inches(8.8),
        Inches(0.7),
        title,
        font_size=28,
        bold=True,
        color=TEXT_PRIMARY,
    )


def add_footer(slide, text: str = "CleanMap | Salesforce Excel Import Validator") -> None:
    add_textbox(
        slide,
        Inches(0.6),
        Inches(7.0),
        Inches(8.8),
        Inches(0.4),
        text,
        font_size=10,
        color=TEXT_MUTED,
        align=PP_ALIGN.CENTER,
    )


def build() -> Presentation:
    prs = Presentation()
    prs.slide_width = Inches(10)
    prs.slide_height = Inches(7.5)
    blank = prs.slide_layouts[6]

    # Slide 1 — Title
    slide = prs.slides.add_slide(blank)
    set_slide_background(slide, BG_DARK)
    add_textbox(
        slide, Inches(0.8), Inches(2.2), Inches(8.4), Inches(1.2),
        "CleanMap", font_size=54, bold=True, color=ACCENT, align=PP_ALIGN.CENTER,
    )
    add_textbox(
        slide, Inches(0.8), Inches(3.3), Inches(8.4), Inches(0.8),
        "Salesforce Excel Import Validator & Cleansing Tool",
        font_size=20, color=TEXT_SECONDARY, align=PP_ALIGN.CENTER,
    )
    add_textbox(
        slide, Inches(0.8), Inches(4.2), Inches(8.4), Inches(0.6),
        "Validate · Cleanse · Import with confidence",
        font_size=14, color=TEXT_MUTED, align=PP_ALIGN.CENTER,
    )
    add_footer(slide)
    add_notes(
        slide,
        "Welcome the team. Introduce CleanMap as a pre-import quality gate for Salesforce "
        "Excel migrations. Mention this deck is short — the live demo is the main event.",
    )

    # Slide 2 — The Problem
    slide = prs.slides.add_slide(blank)
    set_slide_background(slide, BG_DARK)
    add_header_bar(slide, "The Problem")
    add_bullets(
        slide, Inches(0.8), Inches(1.4), Inches(8.4), Inches(5),
        [
            "Legacy Excel migration files contain inconsistent and invalid data",
            "Failed Salesforce imports due to bad dates, picklists, and lookups",
            "Manual fixing is slow, error-prone, and hard to track row-by-row",
            "Lookup names don't match Salesforce Ids without reference files",
            "Picklist values often don't match org field definitions",
            "Teams lack a clear Ready / Not Ready view before import",
        ],
        font_size=18,
    )
    add_footer(slide)
    add_notes(
        slide,
        "Connect to pain your team already feels. Ask: 'How many import failures have we "
        "seen because of bad Excel data?' Keep this slide under 2 minutes.",
    )

    # Slide 3 — What CleanMap Does
    slide = prs.slides.add_slide(blank)
    set_slide_background(slide, BG_DARK)
    add_header_bar(slide, "What CleanMap Does")
    panel = slide.shapes.add_shape(1, Inches(0.6), Inches(1.2), Inches(8.8), Inches(5.2))
    panel.fill.solid()
    panel.fill.fore_color.rgb = BG_PANEL
    panel.line.color.rgb = RGBColor(0x2E, 0x2E, 0x33)
    add_textbox(
        slide, Inches(0.9), Inches(1.45), Inches(8.2), Inches(0.5),
        "At a glance, CleanMap can:", font_size=16, bold=True, color=TEXT_PRIMARY,
    )
    add_bullets(
        slide, Inches(0.9), Inches(1.95), Inches(8.2), Inches(4.2),
        [
            "Validate & cleanse legacy Excel files (.xlsx and .xls)",
            "Auto-detect Salesforce field types from the file itself",
            "Resolve lookup names to Salesforce Ids (optional reference files)",
            "Validate picklist values against object field definitions",
            "Add Ready / Not Ready status per row",
            "Export files formatted for Salesforce Inspector import",
        ],
        font_size=15,
        color=TEXT_SECONDARY,
    )
    add_footer(slide)
    add_notes(
        slide,
        "This is the elevator pitch. Emphasize: no hardcoded column list, optional lookup "
        "files, and Salesforce Inspector-ready export.",
    )

    # Slide 4 — Who It's For
    slide = prs.slides.add_slide(blank)
    set_slide_background(slide, BG_DARK)
    add_header_bar(slide, "Who It's For")
    add_bullets(
        slide, Inches(0.8), Inches(1.5), Inches(4.0), Inches(4.5),
        [
            "Salesforce migration teams",
            "Salesforce admins & consultants",
            "Data owners preparing import files",
            "QA reviewers before go-live",
        ],
        font_size=18,
    )
    add_textbox(
        slide, Inches(5.2), Inches(1.5), Inches(4.0), Inches(1.0),
        "Best used when:", font_size=16, bold=True, color=TEXT_PRIMARY,
    )
    add_bullets(
        slide, Inches(5.2), Inches(2.2), Inches(4.0), Inches(4),
        [
            "Migrating legacy Excel templates to Salesforce",
            "Bulk loading Accounts, Sites, or custom objects",
            "Validating files from business users before import",
        ],
        font_size=16,
    )
    add_footer(slide)
    add_notes(slide, "Tailor this to your team — name the objects you're migrating (e.g. Site).")

    # Slide 5 — How It Works
    slide = prs.slides.add_slide(blank)
    set_slide_background(slide, BG_DARK)
    add_header_bar(slide, "How It Works — 6 Steps")
    steps = [
        "1. Upload main Excel file (or load from local path)",
        "2. Review auto-detected field types",
        "3. Optionally upload lookup reference files",
        "4. Optionally upload object field definition for picklists",
        "5. Select mandatory columns & Run validation",
        "6. Download cleansed, validated Excel file",
    ]
    add_bullets(slide, Inches(0.8), Inches(1.4), Inches(8.4), Inches(5), steps, font_size=17)
    add_footer(slide)
    add_notes(
        slide,
        "Walk through quickly — you'll demonstrate these live on the next slide. "
        "Total workflow takes minutes, not hours.",
    )

    # Slide 6 — Key Features
    slide = prs.slides.add_slide(blank)
    set_slide_background(slide, BG_DARK)
    add_header_bar(slide, "Key Features")
    features = [
        ("Dynamic schema", "Reads field types from Excel row 3 — no fixed column list"),
        ("Lookup resolution", "Names → Salesforce Ids using optional reference exports"),
        ("Picklist validation", "Matches values against object field definition file"),
        ("Status column", "Ready = no errors | Not Ready = fix before import"),
        ("Salesforce Inspector export", "Lookup names prefixed with _ ; Ids keep API names"),
        ("Error highlighting", "Download Excel with red cells + comments on issues"),
    ]
    y = 1.35
    for title, desc in features:
        add_textbox(slide, Inches(0.8), Inches(y), Inches(2.4), Inches(0.4), title,
                    font_size=14, bold=True, color=ACCENT)
        add_textbox(slide, Inches(3.3), Inches(y), Inches(5.9), Inches(0.55), desc,
                    font_size=13, color=TEXT_SECONDARY)
        y += 0.72
    add_footer(slide)
    add_notes(slide, "Don't read every bullet — pick 2-3 most relevant to your project.")

    # Slide 7 — Before vs After
    slide = prs.slides.add_slide(blank)
    set_slide_background(slide, BG_DARK)
    add_header_bar(slide, "Before vs After")
    # Before column
    before_box = slide.shapes.add_shape(1, Inches(0.6), Inches(1.3), Inches(4.2), Inches(5.0))
    before_box.fill.solid()
    before_box.fill.fore_color.rgb = RGBColor(0x2A, 0x1A, 0x1A)
    before_box.line.color.rgb = RGBColor(0x5A, 0x3A, 0x3A)
    add_textbox(slide, Inches(0.9), Inches(1.5), Inches(3.6), Inches(0.4),
                "Before CleanMap", font_size=16, bold=True, color=RGBColor(0xFF, 0x99, 0x99))
    add_bullets(
        slide, Inches(0.9), Inches(2.0), Inches(3.6), Inches(4),
        ["Manual data review", "Import failures in Salesforce", "Invalid picklist values",
         "Unresolved lookup names", "No row-level readiness view"],
        font_size=14, color=TEXT_SECONDARY,
    )
    # After column
    after_box = slide.shapes.add_shape(1, Inches(5.2), Inches(1.3), Inches(4.2), Inches(5.0))
    after_box.fill.solid()
    after_box.fill.fore_color.rgb = RGBColor(0x1A, 0x2A, 0x1A)
    after_box.line.color.rgb = RGBColor(0x3A, 0x5A, 0x3A)
    add_textbox(slide, Inches(5.5), Inches(1.5), Inches(3.6), Inches(0.4),
                "After CleanMap", font_size=16, bold=True, color=RGBColor(0x99, 0xFF, 0x99))
    add_bullets(
        slide, Inches(5.5), Inches(2.0), Inches(3.6), Inches(4),
        ["Automated validation & cleansing", "Fewer failed imports", "Picklists verified against org",
         "Lookup Ids resolved automatically", "Ready / Not Ready status per row"],
        font_size=14, color=TEXT_SECONDARY,
    )
    add_footer(slide)
    add_notes(slide, "Visual contrast slide — good for managers. Keep it punchy.")

    # Slide 8 — Live Demo
    slide = prs.slides.add_slide(blank)
    set_slide_background(slide, BG_DARK)
    add_header_bar(slide, "Live Demo")
    add_textbox(
        slide, Inches(0.8), Inches(1.3), Inches(8.4), Inches(0.5),
        "Demo script — follow along in CleanMap",
        font_size=16, color=TEXT_MUTED,
    )
    demo_steps = [
        "Upload TestFile3.xlsx (Site migration sample)",
        "Review detected field types & picklist fields",
        "Upload accountlookup.xls for Account lookup resolution",
        "Upload Site Object Fields Definition.xlsx for picklist validation",
        "Select mandatory columns → Run validation",
        "Show Issues tab, Status column, and metrics",
        "Download cleansed file — show Salesforce Inspector format",
    ]
    add_bullets(slide, Inches(0.8), Inches(1.85), Inches(8.4), Inches(4.5), demo_steps, font_size=17)
    add_textbox(
        slide, Inches(0.8), Inches(6.2), Inches(8.4), Inches(0.5),
        "→ Switch to CleanMap now: streamlit run app.py",
        font_size=14, bold=True, color=ACCENT, align=PP_ALIGN.CENTER,
    )
    add_footer(slide)
    add_notes(
        slide,
        "THIS IS THE MAIN EVENT — spend 10-15 minutes here. Have files ready before the meeting. "
        "If demo fails, use screenshots as backup.",
    )

    # Slide 9 — Benefits
    slide = prs.slides.add_slide(blank)
    set_slide_background(slide, BG_DARK)
    add_header_bar(slide, "Benefits for the Team")
    benefits = [
        "Reduce failed Salesforce imports and rework cycles",
        "Save hours of manual Excel review per migration batch",
        "Clear Ready / Not Ready visibility before go-live",
        "Standardize validation across objects and team members",
        "Catch picklist and lookup issues before they hit production",
        "Faster, more confident migration delivery",
    ]
    add_bullets(slide, Inches(0.8), Inches(1.4), Inches(8.4), Inches(5), benefits, font_size=18)
    add_footer(slide)
    add_notes(slide, "Tie benefits to your project's timeline and pain points.")

    # Slide 10 — Next Steps
    slide = prs.slides.add_slide(blank)
    set_slide_background(slide, BG_DARK)
    add_header_bar(slide, "Next Steps & Q&A")
    add_bullets(
        slide, Inches(0.8), Inches(1.4), Inches(8.4), Inches(3.5),
        [
            "Pilot: Run CleanMap on Site object migration this week",
            "Share CleanMap Documentation.docx with the team",
            "Gather feedback on mandatory fields & picklist rules",
            "Plan rollout for other objects (Account, Contact, etc.)",
            "Questions?",
        ],
        font_size=18,
    )
    add_textbox(
        slide, Inches(0.8), Inches(5.2), Inches(8.4), Inches(0.8),
        "CleanMap · GitHub: github.com/akhilsitetracker123/CleanMap",
        font_size=13, color=TEXT_MUTED, align=PP_ALIGN.CENTER,
    )
    add_footer(slide)
    add_notes(
        slide,
        "End with a clear ask: approve a pilot, assign an owner, schedule follow-up. "
        "Share the Word doc and offer to run CleanMap on their files.",
    )

    return prs


if __name__ == "__main__":
    presentation = build()
    presentation.save(OUTPUT)
    print(f"Created: {OUTPUT}")
