"""
backend/marketplace/impact_reports.py
Generates downloadable, printable ESG & Sustainability Impact PDF summaries using ReportLab.
Strictly scoped to the calling tenant organization.
"""
import io
from datetime import datetime
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
    HRFlowable,
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle


def generate_impact_pdf(
    org_name: str,
    org_type: str,
    period_label: str,
    metrics: dict,
    category_breakdown: list,
    constants: dict,
) -> bytes:
    """
    Builds a professional, clean printable PDF report for ESG & Sustainability Impact telemetry.
    """
    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=letter,
        leftMargin=36,
        rightMargin=36,
        topMargin=36,
        bottomMargin=36,
    )

    styles = getSampleStyleSheet()

    # Brand Colors
    primary_color = colors.HexColor("#059669")  # Emerald 600
    dark_text = colors.HexColor("#0f172a")     # Slate 900
    muted_text = colors.HexColor("#64748b")    # Slate 500
    card_bg = colors.HexColor("#f8fafc")       # Slate 50
    border_color = colors.HexColor("#e2e8f0")  # Slate 200

    title_style = ParagraphStyle(
        "DocTitle",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=20,
        leading=24,
        textColor=primary_color,
    )
    subtitle_style = ParagraphStyle(
        "DocSubtitle",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=10,
        leading=14,
        textColor=muted_text,
    )
    meta_style = ParagraphStyle(
        "MetaText",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=9,
        leading=12,
        textColor=dark_text,
    )
    section_heading = ParagraphStyle(
        "SectionHeading",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=12,
        leading=16,
        textColor=dark_text,
    )
    table_cell = ParagraphStyle(
        "TableCell",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=9,
        leading=12,
        textColor=dark_text,
    )
    table_cell_bold = ParagraphStyle(
        "TableCellBold",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=9,
        leading=12,
        textColor=dark_text,
    )
    citation_style = ParagraphStyle(
        "CitationText",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=8,
        leading=11,
        textColor=muted_text,
    )

    story = []

    # 1. Header & Title Banner
    story.append(Paragraph("SurplusSync &mdash; ESG & Sustainability Impact Report", title_style))
    story.append(Paragraph("Official Empirical Telemetry & Carbon Abatement Audit", subtitle_style))
    story.append(Spacer(1, 10))
    story.append(HRFlowable(width="100%", thickness=1.5, color=primary_color, spaceAfter=12))

    # 2. Organization Context Table
    now_str = datetime.now().strftime("%B %d, %Y %H:%M UTC")
    meta_data = [
        [
            Paragraph(f"<b>Organization:</b> {org_name}", meta_style),
            Paragraph(f"<b>Reporting Period:</b> {period_label}", meta_style),
        ],
        [
            Paragraph(f"<b>Type:</b> {org_type.title()}", meta_style),
            Paragraph(f"<b>Generated At:</b> {now_str}", meta_style),
        ],
    ]
    meta_table = Table(meta_data, colWidths=[270, 270])
    meta_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), card_bg),
        ("BOX", (0, 0), (-1, -1), 0.5, border_color),
        ("INNERGRID", (0, 0), (-1, -1), 0.5, border_color),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("LEFTPADDING", (0, 0), (-1, -1), 10),
        ("RIGHTPADDING", (0, 0), (-1, -1), 10),
    ]))
    story.append(meta_table)
    story.append(Spacer(1, 16))

    # 3. Key Impact KPI Grid
    story.append(Paragraph("Primary Sustainability & Humanitarian Metrics", section_heading))
    story.append(Spacer(1, 6))

    kpi_data = [
        [
            Paragraph("<b>Metric</b>", table_cell_bold),
            Paragraph("<b>Quantified Impact</b>", table_cell_bold),
            Paragraph("<b>Scientific Standard / Benchmark</b>", table_cell_bold),
        ],
        [
            Paragraph("Total Food Diverted from Landfill", table_cell),
            Paragraph(f"<b>{metrics.get('total_quantity_donated_kg', 0):,.2f} kg</b>", table_cell),
            Paragraph("Verified Completed Redistributed Inventory", table_cell),
        ],
        [
            Paragraph("Nutritious Meals Provided", table_cell),
            Paragraph(f"<b>{metrics.get('meals_provided', 0):,} meals</b>", table_cell),
            Paragraph(f"{constants.get('meal_kg_factor', 0.42)} kg per meal (WRAP & FAO Guidelines)", table_cell),
        ],
        [
            Paragraph("Greenhouse Gas (CO₂e) Abated", table_cell),
            Paragraph(f"<b>{metrics.get('co2_diverted_kg', 0):,.2f} kg CO₂e</b>", table_cell),
            Paragraph(f"{constants.get('co2e_kg_factor', 2.5)} kg CO₂e / kg saved (FAO Food Wastage Footprint)", table_cell),
        ],
        [
            Paragraph("Agricultural Water Conserved", table_cell),
            Paragraph(f"<b>{metrics.get('water_saved_liters', 0):,} Liters</b>", table_cell),
            Paragraph("1,000 L / kg saved (Mekonnen & Hoekstra / FAO Water Footprint)", table_cell),
        ],
        [
            Paragraph("Estimated Financial Value Saved", table_cell),
            Paragraph(f"<b>₹{metrics.get('financial_value_saved', 0):,.2f}</b>", table_cell),
            Paragraph("Benchmark: ~₹150 / kg wholesome inventory", table_cell),
        ],
        [
            Paragraph("Completed Donation Dispatches", table_cell),
            Paragraph(f"<b>{metrics.get('total_donations_completed', 0):,} transfers</b>", table_cell),
            Paragraph("100% Counterparty Verified Handover", table_cell),
        ],
    ]
    kpi_table = Table(kpi_data, colWidths=[180, 140, 220])
    kpi_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), primary_color),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("GRID", (0, 0), (-1, -1), 0.5, border_color),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, card_bg]),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
    ]))
    story.append(kpi_table)
    story.append(Spacer(1, 16))

    # 4. Category Breakdown
    if category_breakdown:
        story.append(Paragraph("Diversion Composition by Food Category", section_heading))
        story.append(Spacer(1, 6))

        cat_rows = [
            [
                Paragraph("<b>Category</b>", table_cell_bold),
                Paragraph("<b>Rescued Volume (kg)</b>", table_cell_bold),
                Paragraph("<b>Share of Total</b>", table_cell_bold),
            ]
        ]
        for cat in category_breakdown:
            cat_rows.append([
                Paragraph(str(cat.get("category_name", "Uncategorized")), table_cell),
                Paragraph(f"{cat.get('quantity_kg', 0):,.2f} kg", table_cell),
                Paragraph(f"{cat.get('percentage', 0):.1f}%", table_cell),
            ])

        cat_table = Table(cat_rows, colWidths=[240, 150, 150])
        cat_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#047857")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("GRID", (0, 0), (-1, -1), 0.5, border_color),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, card_bg]),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ("LEFTPADDING", (0, 0), (-1, -1), 8),
            ("RIGHTPADDING", (0, 0), (-1, -1), 8),
        ]))
        story.append(cat_table)
        story.append(Spacer(1, 16))

    # 5. Methodology & Citations Panel ("How We Calculate This")
    story.append(Paragraph("Methodology, Constants & Academic Citations", section_heading))
    story.append(Spacer(1, 6))

    caveat_text = (
        "<b>Notice & Verification:</b> All telemetry figures are computed exclusively from completed, "
        "reconciled donation transfers recorded in the SurplusSync cryptographic inventory ledger. "
        "Calculations use international empirical standards published by WRAP UK and the UN FAO: "
        f"1 meal equivalent = {constants.get('meal_kg_factor', 0.42)} kg of wholesome food; "
        f"1 kg organic food diverted = {constants.get('co2e_kg_factor', 2.5)} kg CO₂ equivalent greenhouse gas emissions avoided "
        "(methane mitigation from anaerobic decomposition in municipal landfills). "
        "Agricultural water footprint conservation benchmark: 1,000 Liters / kg (Mekonnen & Hoekstra, 2011). "
        "All figures represent empirical mathematical estimates."
    )
    story.append(Paragraph(caveat_text, citation_style))
    story.append(Spacer(1, 12))

    # Footer signature line
    story.append(HRFlowable(width="100%", thickness=0.5, color=border_color, spaceAfter=8))
    story.append(Paragraph(
        f"SurplusSync Platform &bull; Certified ESG Telemetry &bull; Scope 3 Emission Diversion &bull; Generated for {org_name}",
        citation_style,
    ))

    doc.build(story)
    return buf.getvalue()
