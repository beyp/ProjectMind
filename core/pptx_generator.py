"""Generateur PowerPoint Weekly Status — template TMM."""
import os
from datetime import date
from pathlib import Path

import aiosqlite

from core.database import DB_PATH
from core.fiscal_year import get_fiscal_period

TEMPLATE_PATH = Path(__file__).parent.parent / "templates" / "weekly_template.pptx"
OUTPUT_DIR    = Path("data/exports")


async def generate_weekly_pptx(project_id: int) -> str:
    """Genere le PPTX weekly status et retourne son chemin."""
    from pptx import Presentation
    from pptx.util import Pt
    from pptx.dml.color import RGBColor

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    if not TEMPLATE_PATH.exists():
        raise FileNotFoundError(f"Template introuvable : {TEMPLATE_PATH}")

    # Charger les donnees du projet
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM projects WHERE id=?", (project_id,)) as c:
            project = dict(await c.fetchone() or {})
        if not project:
            raise ValueError(f"Projet {project_id} introuvable")
        async with db.execute(
            "SELECT * FROM weekly_reports WHERE project_id=? ORDER BY report_date DESC LIMIT 1",
            (project_id,)
        ) as c:
            report = dict(await c.fetchone() or {})

    prs    = Presentation(str(TEMPLATE_PATH))
    slide  = prs.slides[0]
    today  = date.today()
    fiscal = get_fiscal_period(today)

    KPI_COLORS = {"G": "4CAF50", "Y": "FFC107", "R": "F44336"}

    def set_text(cell, text, bold=False, color=None, size=9):
        tf = cell.text_frame
        tf.clear()
        run = tf.paragraphs[0].add_run()
        run.text       = str(text or "")
        run.font.bold  = bold
        run.font.size  = Pt(size)
        if color:
            run.font.color.rgb = RGBColor.from_string(color)

    for shape in slide.shapes:
        # Titre + nom projet
        if shape.name == "Title 1" and shape.has_text_frame:
            for para in shape.text_frame.paragraphs:
                for run in para.runs:
                    run.text = run.text.replace("[Project Name]", project.get("name", ""))

        # Date
        if shape.name == "TextBox 12" and shape.has_text_frame:
            for para in shape.text_frame.paragraphs:
                for run in para.runs:
                    run.text = f"  {today.strftime('%B %d, %Y')}  |  {fiscal.label}"

        # Go-Live
        if shape.name == "TextBox 1" and shape.has_text_frame:
            for para in shape.text_frame.paragraphs:
                for run in para.runs:
                    if "Go" in run.text:
                        run.text = f"Go-Live : {project.get('go_live_date', 'TBD')}"

        # KPIs
        if shape.name == "Table 26" and shape.has_table:
            kpi_keys = [
                "kpi_cost", "kpi_scope", "kpi_schedule",
                "kpi_resources", "kpi_risk", "kpi_transition",
            ]
            for i, key in enumerate(kpi_keys, 1):
                if i < len(shape.table.rows):
                    val = report.get(key, "G") if report else "G"
                    set_text(
                        shape.table.rows[i].cells[2],
                        val, bold=True, color=KPI_COLORS.get(val, "000000"),
                    )

        # Sections texte
        text_sections = {
            "Table 7":  "summary",
            "Table 25": "last_period_achievements",
            "Table 13": "planned_activities",
            "Table 15": "watch_items",
            "Table 20": "risks_issues",
        }
        if shape.name in text_sections and shape.has_table and len(shape.table.rows) > 1:
            key = text_sections[shape.name]
            set_text(shape.table.rows[1].cells[0], report.get(key, "") if report else "")

    output_path = OUTPUT_DIR / f"weekly_{project_id}_{today}.pptx"
    prs.save(str(output_path))
    return str(output_path)
