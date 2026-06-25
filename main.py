"""ProjectMind - Point d entree principal."""
import logging
import os
from contextlib import asynccontextmanager
from datetime import date, datetime
from pathlib import Path

from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from core.models import (
    init_db, get_all_projects, get_project, create_project, delete_project,
    get_categories, create_category,
    get_tasks, create_task, update_task, delete_task,
    get_kpis,
    get_weekly_note,
    get_milestones, create_milestone, delete_milestone,
    get_risks, create_risk, delete_risk,
    get_db,
    STATUS_COLORS, STATUSES, KPI_ITEMS,
    get_fiscal_quarter, get_fiscal_year,
)
from ai.task_parser import TaskParser

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
task_parser  = TaskParser(GROQ_API_KEY)

TEMPLATES_DIR = Path("templates")
templates     = Jinja2Templates(directory=str(TEMPLATES_DIR))

# Jinja2 helpers
templates.env.globals["STATUS_COLORS"]     = STATUS_COLORS
templates.env.globals["STATUSES"]          = STATUSES
templates.env.globals["KPI_ITEMS"]         = KPI_ITEMS
templates.env.globals["get_fiscal_quarter"] = get_fiscal_quarter
templates.env.globals["today"]             = date.today


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    Path("data").mkdir(exist_ok=True)
    Path("logs").mkdir(exist_ok=True)
    logger.info("ProjectMind started")
    yield
    logger.info("ProjectMind stopped")


app = FastAPI(title="ProjectMind", version="0.2.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], allow_methods=["*"], allow_headers=["*"],
)

if Path("static").exists():
    app.mount("/static", StaticFiles(directory="static"), name="static")


# ═══════════════════════════════════════════════════════════════════════════════
# Pages HTML
# ═══════════════════════════════════════════════════════════════════════════════

@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    projects = get_all_projects()
    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={"projects": projects, "today": date.today()},
    )


@app.get("/project/{project_id}", response_class=HTMLResponse)
async def project_view(request: Request, project_id: int):
    project = get_project(project_id)
    if not project:
        raise HTTPException(404, "Projet introuvable")
    categories  = get_categories(project_id)
    tasks       = get_tasks(project_id)
    kpis        = get_kpis(project_id)
    milestones  = get_milestones(project_id)
    risks       = get_risks(project_id)
    weekly_note = get_weekly_note(project_id)

    tasks_by_cat: dict = {}
    for task in tasks:
        cat_id = task.get("category_id") or 0
        tasks_by_cat.setdefault(cat_id, []).append(task)

    return templates.TemplateResponse(
        request=request,
        name="project.html",
        context={
            "project":      project,
            "categories":   categories,
            "tasks_by_cat": tasks_by_cat,
            "kpis":         kpis,
            "milestones":   milestones,
            "risks":        risks,
            "weekly_note":  weekly_note,
            "today":        date.today(),
            "fiscal_q":     get_fiscal_quarter(),
        },
    )


@app.get("/project/{project_id}/gantt", response_class=HTMLResponse)
async def gantt_view(request: Request, project_id: int):
    project = get_project(project_id)
    if not project:
        raise HTTPException(404, "Projet introuvable")
    tasks      = get_tasks(project_id)
    categories = get_categories(project_id)
    cat_map    = {c["id"]: c["name"] for c in categories}
    gantt_tasks = []
    for t in tasks:
        if t.get("start_date") or t.get("end_date"):
            gantt_tasks.append({
                "id":         t["id"],
                "text":       t["title"],
                "start_date": t.get("start_date", ""),
                "end_date":   t.get("end_date", ""),
                "progress":   (t.get("progress") or 0) / 100,
                "category":   cat_map.get(t.get("category_id"), ""),
            })
    return templates.TemplateResponse(
        request=request,
        name="gantt.html",
        context={
            "project":     project,
            "gantt_tasks": gantt_tasks,
            "fiscal_q":    get_fiscal_quarter(),
            "fiscal_y":    get_fiscal_year(),
        },
    )


# ═══════════════════════════════════════════════════════════════════════════════
# API — Projets
# ═══════════════════════════════════════════════════════════════════════════════

@app.get("/api/projects")
async def api_projects():
    return get_all_projects()


@app.post("/api/projects")
async def api_create_project(request: Request):
    data = await request.json()
    project_id = create_project(
        name          = data.get("name", "Nouveau projet"),
        description   = data.get("description", ""),
        language      = data.get("language", "fr"),
        go_live_date  = data.get("go_live_date", ""),
        ado_project   = data.get("ado_project", ""),
        ado_area_path = data.get("ado_area_path", ""),
    )
    return {"id": project_id, "ok": True}


@app.delete("/api/projects/{project_id}")
async def api_delete_project(project_id: int):
    ok = delete_project(project_id)
    if not ok:
        raise HTTPException(404, "Projet introuvable")
    return {"ok": True}


# ═══════════════════════════════════════════════════════════════════════════════
# API — Catégories
# ═══════════════════════════════════════════════════════════════════════════════

@app.get("/api/projects/{project_id}/categories")
async def api_categories(project_id: int):
    return get_categories(project_id)


@app.post("/api/projects/{project_id}/categories")
async def api_create_category(project_id: int, request: Request):
    data   = await request.json()
    cat_id = create_category(
        project_id = project_id,
        name       = data.get("name", ""),
        name_en    = data.get("name_en", ""),
        color      = data.get("color", "#041E42"),
    )
    return {"id": cat_id, "ok": True}


# ═══════════════════════════════════════════════════════════════════════════════
# API — Tâches
# ═══════════════════════════════════════════════════════════════════════════════

@app.get("/api/projects/{project_id}/tasks")
async def api_tasks(project_id: int):
    return get_tasks(project_id)


@app.post("/api/projects/{project_id}/tasks")
async def api_create_task(project_id: int, request: Request):
    data    = await request.json()
    task_id = create_task(
        project_id  = project_id,
        title       = data.get("title", ""),
        category_id = data.get("category_id"),
        status      = data.get("status", "A planifier"),
        date_label  = data.get("date_label", ""),
        start_date  = data.get("start_date", ""),
        end_date    = data.get("end_date", ""),
        description = data.get("description", ""),
        ado_item_id = data.get("ado_item_id"),
    )
    return {"id": task_id, "ok": True}


@app.patch("/api/tasks/{task_id}")
async def api_update_task(task_id: int, request: Request):
    data = await request.json()
    update_task(task_id, **data)
    return {"ok": True}


@app.delete("/api/tasks/{task_id}")
async def api_delete_task(task_id: int):
    ok = delete_task(task_id)
    if not ok:
        raise HTTPException(404, "Tache introuvable")
    return {"ok": True}


# ═══════════════════════════════════════════════════════════════════════════════
# API — Notes hebdomadaires
# ═══════════════════════════════════════════════════════════════════════════════

@app.post("/api/projects/{project_id}/weekly-note")
async def api_save_weekly_note(project_id: int, request: Request):
    data = await request.json()
    conn = get_db()
    today_str = date.today().isoformat()
    conn.execute("""
        INSERT INTO weekly_notes
            (project_id, week_date, summary, achievements, planned, watch_items)
        VALUES (?, ?, ?, ?, ?, ?)
        ON CONFLICT(project_id, week_date)
        DO UPDATE SET
            summary=excluded.summary,
            achievements=excluded.achievements,
            planned=excluded.planned,
            watch_items=excluded.watch_items
    """, (project_id, today_str,
          data.get("summary", ""), data.get("achievements", ""),
          data.get("planned", ""), data.get("watch_items", "")))
    conn.commit()
    conn.close()
    return {"ok": True}


# ═══════════════════════════════════════════════════════════════════════════════
# API — KPIs
# ═══════════════════════════════════════════════════════════════════════════════

@app.post("/api/projects/{project_id}/kpis")
async def api_update_kpis(project_id: int, request: Request):
    data = await request.json()
    conn = get_db()
    today_str = date.today().isoformat()
    for kpi_name, values in data.items():
        conn.execute("""
            INSERT INTO project_kpis (project_id, kpi_name, prev_value, curr_value, week_date)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(project_id, kpi_name, week_date)
            DO UPDATE SET
                prev_value=excluded.prev_value,
                curr_value=excluded.curr_value
        """, (project_id, kpi_name,
              values.get("prev_value", "G"), values.get("curr_value", "G"),
              today_str))
    conn.commit()
    conn.close()
    return {"ok": True}


# ═══════════════════════════════════════════════════════════════════════════════
# API — Jalons (Milestones)
# ═══════════════════════════════════════════════════════════════════════════════

@app.post("/api/projects/{project_id}/milestones")
async def api_create_milestone(project_id: int, request: Request):
    data = await request.json()
    mid = create_milestone(
        project_id    = project_id,
        title         = data.get("title", ""),
        baseline_date = data.get("baseline_date", ""),
        current_date  = data.get("current_date", ""),
        status        = data.get("status", "In progress"),
    )
    return {"id": mid, "ok": True}


@app.delete("/api/milestones/{milestone_id}")
async def api_delete_milestone(milestone_id: int):
    ok = delete_milestone(milestone_id)
    if not ok:
        raise HTTPException(404, "Jalon introuvable")
    return {"ok": True}


# ═══════════════════════════════════════════════════════════════════════════════
# API — Risques
# ═══════════════════════════════════════════════════════════════════════════════

@app.post("/api/projects/{project_id}/risks")
async def api_create_risk(project_id: int, request: Request):
    data = await request.json()
    rid = create_risk(
        project_id  = project_id,
        description = data.get("description", ""),
        owner       = data.get("owner", ""),
        risk_type   = data.get("risk_type", "I"),
    )
    return {"id": rid, "ok": True}


@app.delete("/api/risks/{risk_id}")
async def api_delete_risk(risk_id: int):
    ok = delete_risk(risk_id)
    if not ok:
        raise HTTPException(404, "Risque introuvable")
    return {"ok": True}


# ═══════════════════════════════════════════════════════════════════════════════
# API — IA (Groq)
# ═══════════════════════════════════════════════════════════════════════════════

@app.post("/api/projects/{project_id}/ai/parse")
async def api_ai_parse(project_id: int, request: Request):
    """Groq parse texte brut → tâches structurées."""
    project = get_project(project_id)
    if not project:
        raise HTTPException(404, "Projet introuvable")
    data     = await request.json()
    text     = data.get("text", "")
    language = data.get("language", project.get("language", "fr"))
    if not text.strip():
        return {"tasks": [], "error": "Texte vide"}
    tasks = task_parser.parse_text(text, language)
    return {"tasks": tasks}


@app.post("/api/projects/{project_id}/ai/restructure")
async def api_ai_restructure(project_id: int):
    """Groq restructure les tâches existantes."""
    project = get_project(project_id)
    if not project:
        raise HTTPException(404, "Projet introuvable")
    tasks    = get_tasks(project_id)
    language = project.get("language", "fr")
    restructured = task_parser.restructure_tasks(tasks, language)
    return {"tasks": restructured}


@app.post("/api/projects/{project_id}/ai/import")
async def api_ai_import(project_id: int, request: Request):
    """Importe les tâches parsées par l IA dans la base."""
    data     = await request.json()
    tasks    = data.get("tasks", [])
    language = data.get("language", "fr")
    project  = get_project(project_id)
    if not project:
        raise HTTPException(404)
    categories = {c["name"]: c["id"] for c in get_categories(project_id)}
    imported = 0
    for t in tasks:
        if "error" in t:
            continue
        cat_name = t.get("category", "")
        cat_id   = None
        if cat_name:
            if cat_name not in categories:
                cat_id = create_category(project_id, cat_name)
                categories[cat_name] = cat_id
            else:
                cat_id = categories[cat_name]
        create_task(
            project_id  = project_id,
            title       = t.get("title", ""),
            category_id = cat_id,
            status      = t.get("status", "A planifier"),
            date_label  = t.get("date_label", ""),
            description = t.get("description", ""),
            ado_item_id = t.get("ado_item_id"),
        )
        imported += 1
    return {"imported": imported, "ok": True}


# ═══════════════════════════════════════════════════════════════════════════════
# API — Export PowerPoint
# ═══════════════════════════════════════════════════════════════════════════════

@app.get("/api/projects/{project_id}/export/pptx")
async def api_export_pptx(project_id: int):
    project = get_project(project_id)
    if not project:
        raise HTTPException(404, "Projet introuvable")
    try:
        from core.pptx_generator import generate_pptx
        pptx_bytes = generate_pptx(
            project     = project,
            kpis        = get_kpis(project_id),
            milestones  = get_milestones(project_id),
            risks       = get_risks(project_id),
            weekly_note = get_weekly_note(project_id),
        )
        filename = f"weekly_{project['name'].replace(' ', '_')}_{date.today()}.pptx"
        return Response(
            content     = pptx_bytes,
            media_type  = "application/vnd.openxmlformats-officedocument.presentationml.presentation",
            headers     = {"Content-Disposition": f"attachment; filename=\"{filename}\""},
        )
    except Exception as e:
        logger.error("Export PPTX error: %s", e)
        raise HTTPException(500, f"Erreur export PPTX: {e}")
