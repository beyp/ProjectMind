"""ProjectMind - Point d entrée principal."""
import logging
import os
from contextlib import asynccontextmanager
from datetime import date, datetime
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI, Request, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from core.models import (
    init_db, get_all_projects, get_project, create_project,
    get_categories, create_category, get_tasks, create_task, update_task,
    get_kpis, get_weekly_note, get_milestones, get_risks,
    get_resources, create_resource, update_resource, delete_resource,
    reorder_resources, get_capacity, upsert_capacity, get_capacity_matrix,
    get_task_assignments, get_project_assignments,
    upsert_task_assignment, delete_task_assignment, compute_task_end_date,
    STATUS_COLORS, STATUSES, KPI_ITEMS, get_fiscal_quarter, get_fiscal_year,
    get_db, delete_project
)
from ai.task_parser import TaskParser, VisionTaskParser

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
task_parser        = TaskParser(GROQ_API_KEY)
vision_task_parser = VisionTaskParser(GROQ_API_KEY)

TEMPLATES_DIR = Path("templates")
templates     = Jinja2Templates(directory=str(TEMPLATES_DIR))

# Jinja2 helpers
templates.env.globals["STATUS_COLORS"]      = STATUS_COLORS
templates.env.globals["STATUSES"]           = STATUSES
templates.env.globals["KPI_ITEMS"]          = KPI_ITEMS
templates.env.globals["get_fiscal_quarter"] = get_fiscal_quarter
templates.env.globals["today"]              = date.today()  # valeur, pas callable

# Filtre urlencode pour les URLs ADO
from urllib.parse import quote as _url_quote
templates.env.filters["urlencode"] = lambda s: _url_quote(str(s), safe="")


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    Path("data").mkdir(exist_ok=True)
    Path("logs").mkdir(exist_ok=True)
    logger.info("ProjectMind started")
    yield
    logger.info("ProjectMind stopped")


app = FastAPI(title="ProjectMind", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], allow_methods=["*"], allow_headers=["*"],
)

if Path("static").exists():
    app.mount("/static", StaticFiles(directory="static"), name="static")


# ══════════════════════════════════════════════════════════════════════════════
# Pages principales
# ══════════════════════════════════════════════════════════════════════════════

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
    categories = get_categories(project_id)
    tasks      = get_tasks(project_id)
    kpis       = get_kpis(project_id)
    milestones = get_milestones(project_id)
    risks      = get_risks(project_id)
    weekly_note = get_weekly_note(project_id)
    # Grouper les tâches par catégorie
    tasks_by_cat: dict[int, list] = {}
    for task in tasks:
        cat_id = task.get("category_id") or 0
        tasks_by_cat.setdefault(cat_id, []).append(task)

    resources = get_resources(project_id)

    return templates.TemplateResponse(
        request=request,
        name="project.html",
        context={
            "project":      project,
            "categories":   categories,
            "tasks_by_cat": tasks_by_cat,
            "tasks_flat":   tasks,
            "kpis":         kpis,
            "milestones":   milestones,
            "risks":        risks,
            "weekly_note":  weekly_note,
            "resources":    resources,
            "today":        date.today(),
            "fiscal_q":     get_fiscal_quarter(),
        },
    )


@app.get("/project/{project_id}/gantt", response_class=HTMLResponse)
async def gantt_view(request: Request, project_id: int):
    from datetime import date as dt, timedelta
    project = get_project(project_id)
    if not project:
        raise HTTPException(404, "Projet introuvable")
    tasks      = get_tasks(project_id)
    categories = get_categories(project_id)
    cat_map    = {c["id"]: c["name"] for c in categories}

    # Construire les données Gantt
    # Inclure TOUTES les tâches (pas seulement celles avec dates)
    today_str = dt.today().isoformat()
    gantt_tasks = []
    for i, t in enumerate(tasks):
        start = t.get("start_date") or ""
        end   = t.get("end_date")   or ""
        # Si pas de dates → tâche "flottante" à partir d'aujourd'hui
        if not start:
            start = today_str
        if not end:
            # Durée par défaut : 7 jours
            from datetime import date as d2
            end = (d2.fromisoformat(start) + timedelta(days=7)).isoformat()
        gantt_tasks.append({
            "id":         t["id"],
            "text":       t["title"],
            "start_date": start,
            "end_date":   end,
            "progress":   (t.get("progress") or 0) / 100,
            "category":   cat_map.get(t.get("category_id"), ""),
            "has_dates":  bool(t.get("start_date") or t.get("end_date")),
        })
    return templates.TemplateResponse(
        request=request,
        name="gantt.html",
        context={
            "project":    project,
            "gantt_tasks": gantt_tasks,
            "fiscal_q":   get_fiscal_quarter(),
            "fiscal_y":   get_fiscal_year(),
        },
    )


# ══════════════════════════════════════════════════════════════════════════════
# API REST
# ══════════════════════════════════════════════════════════════════════════════

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
    """Supprime un projet et toutes ses donnees."""
    ok = delete_project(project_id)
    if not ok:
        raise HTTPException(404, "Projet introuvable")
    return {"ok": True, "deleted": project_id}


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


@app.post("/api/projects/{project_id}/weekly-note")
async def api_save_weekly_note(project_id: int, request: Request):
    data = await request.json()
    conn = get_db()
    today_str = date.today().isoformat()
    conn.execute("""
        INSERT OR REPLACE INTO weekly_notes
        (project_id, week_date, summary, achievements, planned, watch_items)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (project_id, today_str,
          data.get("summary",""), data.get("achievements",""),
          data.get("planned",""), data.get("watch_items","")))
    conn.commit()
    conn.close()
    return {"ok": True}


@app.post("/api/projects/{project_id}/kpis")
async def api_update_kpis(project_id: int, request: Request):
    data = await request.json()
    conn = get_db()
    today_str = date.today().isoformat()
    for kpi_name, values in data.items():
        conn.execute("""
            INSERT OR REPLACE INTO project_kpis
            (project_id, kpi_name, prev_value, curr_value, week_date)
            VALUES (?, ?, ?, ?, ?)
        """, (project_id, kpi_name,
              values.get("prev","G"), values.get("curr","G"), today_str))
    conn.commit()
    conn.close()
    return {"ok": True}


@app.post("/api/projects/{project_id}/milestones")
async def api_create_milestone(project_id: int, request: Request):
    data = await request.json()
    conn = get_db()
    c    = conn.cursor()
    c.execute("""
        INSERT INTO milestones (project_id, title, baseline_date, current_date, status)
        VALUES (?, ?, ?, ?, ?)
    """, (project_id, data.get("title",""),
          data.get("baseline_date",""), data.get("current_date",""),
          data.get("status","In progress")))
    mid = c.lastrowid
    conn.commit()
    conn.close()
    return {"id": mid, "ok": True}


@app.post("/api/projects/{project_id}/risks")
async def api_create_risk(project_id: int, request: Request):
    data = await request.json()
    conn = get_db()
    c    = conn.cursor()
    c.execute("""
        INSERT INTO risks (project_id, risk_type, description, owner)
        VALUES (?, ?, ?, ?)
    """, (project_id, data.get("risk_type","I"),
          data.get("description",""), data.get("owner","")))
    rid = c.lastrowid
    conn.commit()
    conn.close()
    return {"id": rid, "ok": True}


# ── IA : parse texte → tâches ─────────────────────────────────────────────────

@app.get("/api/tasks/{task_id}")
async def api_get_task(task_id: int):
    """Récupère une tâche par son ID."""
    conn   = get_db()
    row    = conn.execute("SELECT * FROM tasks WHERE id=?", (task_id,)).fetchone()
    conn.close()
    if not row:
        raise HTTPException(404, "Tache introuvable")
    return dict(row)


@app.put("/api/tasks/{task_id}")
async def api_update_task_full(task_id: int, request: Request):
    """Met à jour une tâche complètement."""
    data = await request.json()
    update_task(task_id, **data)
    return {"ok": True}


@app.delete("/api/tasks/{task_id}")
async def api_delete_task(task_id: int):
    """Supprime une tâche."""
    conn = get_db()
    c    = conn.cursor()
    c.execute("DELETE FROM tasks WHERE id=?", (task_id,))
    deleted = c.rowcount > 0
    conn.commit()
    conn.close()
    if not deleted:
        raise HTTPException(404)
    return {"ok": True}


@app.post("/api/projects/{project_id}/ai/parse")
async def api_ai_parse(project_id: int, request: Request):
    """Parse du texte libre en tâches via Groq."""
    data     = await request.json()
    text     = data.get("text", "")
    language = data.get("language", "fr")
    if not text:
        return JSONResponse({"error": "Texte vide"}, status_code=400)
    tasks = task_parser.parse_text(text, language)
    return {"tasks": tasks, "count": len(tasks)}


@app.post("/api/projects/{project_id}/ai/restructure")
async def api_ai_restructure(project_id: int, request: Request):
    """Restructure les tâches existantes via Groq."""
    project  = get_project(project_id)
    language = project.get("language", "fr") if project else "fr"
    tasks    = get_tasks(project_id)
    result   = task_parser.restructure_tasks(tasks, language)
    return {"tasks": result}


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


# ── Export PowerPoint ─────────────────────────────────────────────────────────

@app.post("/api/projects/{project_id}/ai/capacity")
async def api_ai_capacity(project_id: int, request: Request):
    """
    IA dédiée au capacity planning.
    Analyse du texte/instructions et retourne des actions structurées :
    - create_resource : créer une ressource
    - assign_resource : assigner une ressource à une tâche
    - set_capacity    : définir la fraction d une ressource sur une semaine
    """
    import os, json as _json
    from ai.task_parser import GROQ_URL

    body         = await request.json()
    text         = body.get("text", "")
    image_data   = body.get("image_data", "")
    image_mime   = body.get("image_mime", "image/jpeg")
    language     = body.get("language", "en")

    project   = get_project(project_id)
    resources = get_resources(project_id)
    tasks     = get_tasks(project_id)

    groq_key = os.getenv("GROQ_API_KEY", "")
    if not groq_key:
        return {"error": "GROQ_API_KEY non configurée", "actions": []}

    # Contexte du projet pour l IA
    res_list  = ", ".join(f"{r['acronym']} (max {r['max_fraction']})" for r in resources) or "aucune"
    task_list = ", ".join(f"#{t['id']} {t['title']}" for t in tasks[:20]) or "aucune"

    system_prompt = f"""You are a project capacity planning assistant.
The project is: {project.get('name', '')}
Existing resources: {res_list}
Existing tasks: {task_list}

Analyze the user's instructions and return a JSON array of actions to perform.
Each action has a "type" and parameters:

1. Create a resource:
   {{"type": "create_resource", "acronym": "SAMC4", "full_name": "Sam C.", "max_fraction": 1.0, "is_external": false, "color": "#1E90FF"}}

2. Set capacity (resource allocation per week):
   {{"type": "set_capacity", "acronym": "SAMC4", "fraction": 0.5, "weeks": [23,24,25,26], "year": 2026}}
   (fraction: 0.25=25%, 0.5=50%, 1.0=100%)

3. Assign resource to task:
   {{"type": "assign_resource", "acronym": "SAMC4", "task_id": 5, "hours": 20, "fraction": 0.5}}

4. Reply message to user:
   {{"type": "message", "text": "I have created SAMC4 and set 25% allocation..."}}

Rules:
- ALWAYS include at least one "message" action
- Use exact acronyms from existing resources when possible
- If resource doesn't exist, include a create_resource action first
- Default colors: internal=#1E90FF, external=#FF8C00
- Reply ONLY with a valid JSON array, no text before/after
"""

    # Construire le message
    user_content = []
    if image_data:
        user_content.append({"type": "text", "text": text or "Analyze this capacity planning image"})
        user_content.append({"type": "image_url", "image_url": {"url": f"data:{image_mime};base64,{image_data}"}})
    else:
        user_content.append({"type": "text", "text": text})

    import requests as req
    try:
        r = req.post(
            GROQ_URL,
            headers={"Authorization": f"Bearer {groq_key}", "Content-Type": "application/json"},
            json={
                "model":    "meta-llama/llama-4-scout-17b-16e-instruct" if image_data else "llama-3.3-70b-versatile",
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user",   "content": user_content if image_data else text},
                ],
                "temperature": 0.3,
                "max_tokens":  2048,
            },
            timeout=30,
        )
        r.raise_for_status()
        content = r.json()["choices"][0]["message"]["content"].strip()
        if "```json" in content:
            content = content.split("```json")[1].split("```")[0].strip()
        elif "```" in content:
            content = content.split("```")[1].split("```")[0].strip()
        actions = _json.loads(content)
        if not isinstance(actions, list):
            actions = [actions]
    except Exception as e:
        return {"error": str(e), "actions": [{"type": "message", "text": f"Erreur: {e}"}]}

    # Exécuter les actions automatiquement
    executed = []
    for action in actions:
        atype = action.get("type", "")

        if atype == "create_resource":
            # Vérifier si elle existe déjà
            existing = next((r for r in resources if r["acronym"] == action.get("acronym", "").upper()), None)
            if not existing:
                rid = create_resource(
                    project_id   = project_id,
                    acronym      = action.get("acronym", "").upper(),
                    full_name    = action.get("full_name", ""),
                    role         = action.get("role", ""),
                    is_external  = action.get("is_external", False),
                    max_fraction = float(action.get("max_fraction", 1.0)),
                    color        = action.get("color", "#1E90FF"),
                )
                action["executed"] = True
                action["id"] = rid
                resources = get_resources(project_id)  # refresh
            else:
                action["executed"] = False
                action["note"] = "already exists"
            executed.append(action)

        elif atype == "set_capacity":
            # Trouver la ressource par acronyme
            acro = action.get("acronym", "").upper()
            res  = next((r for r in resources if r["acronym"] == acro), None)
            if res:
                year     = int(action.get("year", __import__("datetime").date.today().year))
                weeks    = action.get("weeks", [])
                fraction = float(action.get("fraction", 0.5))
                for week in weeks:
                    upsert_capacity(project_id, res["id"], year, int(week), fraction)
                action["executed"] = True
                action["resource_id"] = res["id"]
            else:
                action["executed"] = False
                action["note"] = f"Resource {acro} not found"
            executed.append(action)

        elif atype == "assign_resource":
            from core.models import upsert_task_assignment
            acro = action.get("acronym", "").upper()
            res  = next((r for r in resources if r["acronym"] == acro), None)
            if res and action.get("task_id"):
                upsert_task_assignment(
                    task_id     = int(action["task_id"]),
                    resource_id = res["id"],
                    hours       = float(action.get("hours", 0)),
                    fraction    = float(action.get("fraction", 0)),
                )
                action["executed"] = True
            else:
                action["executed"] = False
                action["note"] = "Resource or task not found"
            executed.append(action)

        elif atype == "message":
            executed.append(action)

    return {"actions": executed, "ok": True}


@app.post("/api/projects/{project_id}/ai/parse-image")
async def api_ai_parse_image(project_id: int, request: Request):
    """
    Analyse une image via Groq llama-4-scout (vision) et extrait les tâches.
    Body JSON : { image_data: base64, image_mime: str, text_context: str, language: str }
    """
    project = get_project(project_id)
    if not project:
        raise HTTPException(404, "Projet introuvable")

    body      = await request.json()
    image_data  = body.get("image_data", "")
    image_mime  = body.get("image_mime", "image/jpeg")
    text_context = body.get("text_context", "")
    language    = body.get("language", project.get("language", "fr"))

    if not image_data:
        return JSONResponse({"error": "image_data manquant"}, status_code=400)

    tasks = vision_task_parser.parse_image(
        image_data   = image_data,
        image_mime   = image_mime,
        text_context = text_context,
        language     = language,
    )
    return {"tasks": tasks, "count": len(tasks), "model": "llama-4-scout-17b"}


@app.get("/capacity/{project_id}", response_class=HTMLResponse)
async def capacity_view(request: Request, project_id: int):
    """Page Capacity Planning."""
    from datetime import date as dt
    project   = get_project(project_id)
    if not project:
        raise HTTPException(404)
    resources = get_resources(project_id)
    year      = dt.today().year
    matrix    = get_capacity_matrix(project_id, year)
    return templates.TemplateResponse(
        request=request,
        name="capacity.html",
        context={
            "project":   project,
            "resources": resources,
            "matrix":    matrix,
            "year":      year,
        },
    )


@app.get("/api/projects/{project_id}/resources")
async def api_get_resources(project_id: int):
    return get_resources(project_id)


@app.post("/api/projects/{project_id}/resources")
async def api_create_resource(project_id: int, request: Request):
    data = await request.json()
    rid  = create_resource(
        project_id   = project_id,
        acronym      = data.get("acronym", "").upper(),
        full_name    = data.get("full_name", ""),
        role         = data.get("role", ""),
        is_external  = data.get("is_external", False),
        max_fraction = float(data.get("max_fraction", 1.0)),
        color        = data.get("color", "#1E90FF"),
    )
    return {"id": rid, "ok": True}


@app.patch("/api/projects/{project_id}/resources/reorder")
async def api_reorder_resources(project_id: int, request: Request):
    data = await request.json()
    reorder_resources(project_id, data.get("ordered_ids", []))
    return {"ok": True}


@app.get("/api/resources/{resource_id}")
async def api_get_resource(resource_id: int):
    """Récupère une ressource par son ID."""
    conn = get_db()
    row  = conn.execute("SELECT * FROM resources WHERE id=?", (resource_id,)).fetchone()
    conn.close()
    if not row:
        raise HTTPException(404)
    return dict(row)


@app.put("/api/resources/{resource_id}")
async def api_update_resource(resource_id: int, request: Request):
    """Met à jour une ressource."""
    data = await request.json()
    update_resource(resource_id, **data)
    return {"ok": True}


@app.delete("/api/resources/{resource_id}")
async def api_delete_resource(resource_id: int):
    ok = delete_resource(resource_id)
    return {"ok": ok}


@app.get("/api/projects/{project_id}/capacity")
async def api_get_capacity(project_id: int, year: int | None = None):
    from datetime import date as dt
    y      = year or dt.today().year
    matrix = get_capacity_matrix(project_id, y)
    return matrix


@app.post("/api/projects/{project_id}/capacity/bulk")
async def api_bulk_capacity(project_id: int, request: Request):
    """Sauvegarder plusieurs cellules capacity d un coup."""
    data    = await request.json()
    entries = data.get("entries", [])
    for e in entries:
        upsert_capacity(
            project_id  = project_id,
            resource_id = int(e["resource_id"]),
            year        = int(e["year"]),
            week        = int(e["week"]),
            fraction    = float(e.get("fraction", 0.0)),
        )
    return {"ok": True, "saved": len(entries)}


# ── Task Assignments ─────────────────────────────────────────────────────────

@app.get("/api/tasks/{task_id}/assignments")
async def api_get_assignments(task_id: int):
    from core.models import get_task_assignments
    return get_task_assignments(task_id)


@app.post("/api/tasks/{task_id}/assignments")
async def api_upsert_assignment(task_id: int, request: Request):
    from core.models import upsert_task_assignment, compute_task_end_date, update_task
    data       = await request.json()
    resource_id = int(data["resource_id"])
    hours      = float(data.get("hours", 0))
    fraction   = float(data.get("fraction", 0))
    notes      = data.get("notes", "")
    upsert_task_assignment(task_id, resource_id, hours, fraction, notes)
    # Recalculer la date de fin si pas forcée
    task = get_task(task_id) if hasattr(get_task, '__call__') else None
    if task and not task.get("end_date"):
        end = compute_task_end_date(task_id)
        if end:
            update_task(task_id, end_date=end)
    return {"ok": True}


@app.delete("/api/tasks/{task_id}/assignments/{resource_id}")
async def api_delete_assignment(task_id: int, resource_id: int):
    from core.models import delete_task_assignment
    ok = delete_task_assignment(task_id, resource_id)
    return {"ok": ok}


@app.get("/api/projects/{project_id}/assignments")
async def api_project_assignments(project_id: int):
    from core.models import get_project_assignments
    return get_project_assignments(project_id)


@app.post("/api/projects/{project_id}/ai/capacity-parse")
async def api_capacity_parse(project_id: int, request: Request):
    """
    Parse du texte pour la gestion des ressources et du capacity planning.
    Comprend : ajouter ressources, définir fractions, assigner aux tâches.
    Retourne une liste d'actions à appliquer.
    """
    import os
    from ai.task_parser import TaskParser

    data      = await request.json()
    text      = data.get("text", "")
    resources_ctx = data.get("resources", "")
    language  = data.get("language", "fr")
    project   = get_project(project_id)
    if not project:
        raise HTTPException(404)

    groq_key = os.getenv("GROQ_API_KEY", "")
    if not groq_key:
        return JSONResponse({"error": "GROQ_API_KEY non configuree"})

    # Système prompt spécialisé capacity
    system_fr = """Tu es un assistant expert en gestion de capacite de projet.
Tu analyses du texte décrivant des besoins en ressources et retournes un JSON structuré.

Ressources disponibles dans le projet: """ + resources_ctx + """

Pour chaque action identifiée, génère un objet JSON :
- Pour ajouter une ressource :
  {"type": "add_resource", "acronym": "SAMC4", "full_name": "Samuel C.", "max_fraction": 0.25, "color": "#1E90FF", "is_external": false, "message": "explication"}

- Pour définir la capacité hebdomadaire :
  {"type": "set_capacity", "acronym": "SAMC4", "fraction": 0.25, "weeks": [23,24,25,26], "year": 2026, "entries": [{"resource_id": null, "year": 2026, "week": 23, "fraction": 0.25}], "message": "explication"}

- Pour donner une information :
  {"type": "info", "message": "explication"}

Règles :
- fraction 0.25 = 25% = 10h/sem sur base 40h
- Si l'utilisateur dit "à 25%" → max_fraction = 0.25
- Si resource_id est inconnu, mettre null (à résoudre côté client)
- Retourne UNIQUEMENT un JSON valide : {"actions": [...]}
"""

    import requests as req
    try:
        r = req.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers={"Authorization": f"Bearer {groq_key}", "Content-Type": "application/json"},
            json={
                "model":    "llama-3.3-70b-versatile",
                "messages": [
                    {"role": "system",  "content": system_fr},
                    {"role": "user",    "content": text},
                ],
                "temperature": 0.2,
                "max_tokens":  1024,
            },
            timeout=30,
        )
        r.raise_for_status()
        content = r.json()["choices"][0]["message"]["content"].strip()

        import re as _re, json as _json
        # Extraire le JSON
        m = _re.search(r'\{.*\}', content, _re.DOTALL)
        if m:
            result = _json.loads(m.group(0))
            actions = result.get("actions", [])
        else:
            actions = [{"type": "info", "message": content}]

        # Résoudre les resource_id pour les actions set_capacity
        res_map = {r["acronym"].upper(): r["id"] for r in get_resources(project_id)}
        for action in actions:
            if action.get("type") == "set_capacity":
                acro = action.get("acronym", "").upper()
                rid  = res_map.get(acro)
                if rid and action.get("entries"):
                    for entry in action["entries"]:
                        entry["resource_id"] = rid

        return {"actions": actions, "count": len(actions)}

    except Exception as exc:
        return JSONResponse({"error": str(exc)})


@app.get("/api/projects/{project_id}/export/pptx")
async def export_pptx(project_id: int):
    """Génère et télécharge le Weekly Status PowerPoint."""
    project = get_project(project_id)
    if not project:
        raise HTTPException(404)
    try:
        from core.pptx_generator import generate_weekly_pptx
        pptx_bytes = generate_weekly_pptx(
            project     = project,
            tasks       = get_tasks(project_id),
            categories  = get_categories(project_id),
            kpis        = get_kpis(project_id),
            milestones  = get_milestones(project_id),
            risks       = get_risks(project_id),
            weekly_note = get_weekly_note(project_id),
            language    = project.get("language", "fr"),
        )
        filename = f"WeeklyStatus_{project['name'].replace(' ','_')}.pptx"
        return Response(
            content     = pptx_bytes,
            media_type  = "application/vnd.openxmlformats-officedocument.presentationml.presentation",
            headers     = {"Content-Disposition": f"attachment; filename={filename}"},
        )
    except Exception as e:
        logger.error("PPTX export error: %s", e)
        raise HTTPException(500, str(e))
