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
from core.updater import ProjectMindUpdater

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


# Instance globale updater
_updater = ProjectMindUpdater(mode="notify", check_interval=3600)

@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    Path("data").mkdir(exist_ok=True)
    Path("logs").mkdir(exist_ok=True)
    _updater.start()
    logger.info("ProjectMind started")
    yield
    _updater.stop()
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


# ═══════════════════════════════════════════════════════════════════════════════
# API — Docker Config (healthcheck, port, restart)
# ═══════════════════════════════════════════════════════════════════════════════

@app.get("/api/projects/{project_id}/docker-config")
async def api_get_docker_config(project_id: int):
    """Retourne la config Docker sauvegardee pour ce projet."""
    import json as _json
    conn = get_db()
    # Migration safe: ajouter colonne si manquante
    try:
        conn.execute("ALTER TABLE projects ADD COLUMN docker_config TEXT")
        conn.commit()
    except Exception:
        pass
    row = conn.execute("SELECT docker_config FROM projects WHERE id=?", (project_id,)).fetchone()
    conn.close()
    if not row:
        raise HTTPException(404, "Projet introuvable")
    try:
        cfg = _json.loads(row["docker_config"] or "{}")
    except Exception:
        cfg = {}
    return {
        "port":        cfg.get("port",        8766),
        "restart":     cfg.get("restart",     "unless-stopped"),
        "hc_interval": cfg.get("hc_interval", 60),
        "hc_timeout":  cfg.get("hc_timeout",  10),
        "hc_retries":  cfg.get("hc_retries",  3),
        "hc_start":    cfg.get("hc_start",    15),
    }


@app.post("/api/projects/{project_id}/docker-config")
async def api_save_docker_config(project_id: int, request: Request):
    """Sauvegarde la config Docker et regenere docker-compose.yml."""
    import json as _json
    data = await request.json()
    cfg  = {
        "port":        int(data.get("port",        8766)),
        "restart":     data.get("restart",          "unless-stopped"),
        "hc_interval": int(data.get("hc_interval", 60)),
        "hc_timeout":  int(data.get("hc_timeout",  10)),
        "hc_retries":  int(data.get("hc_retries",  3)),
        "hc_start":    int(data.get("hc_start",    15)),
    }
    conn = get_db()
    try:
        conn.execute("ALTER TABLE projects ADD COLUMN docker_config TEXT")
        conn.commit()
    except Exception:
        pass
    conn.execute("UPDATE projects SET docker_config=? WHERE id=?", (_json.dumps(cfg), project_id))
    conn.commit()
    conn.close()
    _regen_docker_compose(cfg)
    return {"ok": True, "config": cfg}


def _regen_docker_compose(cfg: dict) -> None:
    """Regenere docker-compose.yml avec la config fournie."""
    port     = cfg.get("port",        8766)
    restart  = cfg.get("restart",     "unless-stopped")
    interval = cfg.get("hc_interval", 60)
    timeout  = cfg.get("hc_timeout",  10)
    retries  = cfg.get("hc_retries",  3)
    start    = cfg.get("hc_start",    15)
    content  = f"""services:
  projectmind:
    build: .
    container_name: projectmind
    ports:
      - "{port}:{port}"
    volumes:
      - ./data:/app/data
      - ./templates:/app/templates
      - ./logs:/app/logs
    env_file:
      - .env
    restart: {restart}
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:{port}/api/projects"]
      interval: {interval}s
      timeout: {timeout}s
      retries: {retries}
      start_period: {start}s

networks:
  default:
    name: projectmind-network
"""
    try:
        dc_path = Path(__file__).parent / "docker-compose.yml"
        dc_path.write_text(content, encoding="utf-8")
        logger.info("docker-compose.yml regenere (port=%s, hc=%ss)", port, interval)
    except Exception as e:
        logger.warning("Impossible regenerer docker-compose.yml: %s", e)

# Lancement uvicorn par python .\main.py
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8766, reload=True)


# ── IA : parse image → tâches (llama-4-scout vision) ──────────────────────────

@app.post("/api/projects/{project_id}/ai/parse-image")
async def api_ai_parse_image(project_id: int, request: Request):
    """Groq llama-4-scout analyse une image et extrait les taches."""
    project = get_project(project_id)
    if not project:
        raise HTTPException(404, "Projet introuvable")
    data = await request.json()
    image_data   = data.get("image_data", "")    # base64
    image_mime   = data.get("image_mime", "image/png")
    text_context = data.get("text_context", "")
    language     = data.get("language", project.get("language", "fr"))

    if not image_data:
        return {"tasks": [], "error": "Aucune image fournie"}

    # Nettoyer le préfixe data URI si présent (ex: data:image/png;base64,xxx)
    if "," in image_data:
        image_data = image_data.split(",", 1)[1]

    try:
        from ai.task_parser import VisionTaskParser
        vision_parser = VisionTaskParser(GROQ_API_KEY)
        tasks = vision_parser.parse_image(
            image_data   = image_data,
            image_mime   = image_mime,
            text_context = text_context,
            language     = language,
        )
        model_used = "llama-4-scout (vision)"
        return {"tasks": tasks, "model": model_used, "ok": True}
    except Exception as e:
        logger.error("parse-image error: %s", e)
        return {"tasks": [], "error": str(e)}

# ═══ IA Agent CRUD ═══

@app.get("/api/projects/{project_id}/context")
async def api_project_context(project_id: int):
    project = get_project(project_id)
    if not project: raise HTTPException(404)
    return {"project":project,"categories":get_categories(project_id),"tasks":get_tasks(project_id),"milestones":get_milestones(project_id),"risks":get_risks(project_id),"kpis":get_kpis(project_id)}

@app.patch("/api/projects/{project_id}/categories/{cat_id}")
async def api_update_category(project_id:int,cat_id:int,request:Request):
    data=await request.json(); allowed={"name","name_en","color","sort_order"}; fields={k:v for k,v in data.items() if k in allowed}
    if fields:
        conn=get_db(); sets=", ".join(f"{k}=?" for k in fields); conn.execute(f"UPDATE categories SET {sets} WHERE id=? AND project_id=?",list(fields.values())+[cat_id,project_id]); conn.commit(); conn.close()
    return {"ok":True}

@app.delete("/api/projects/{project_id}/categories/{cat_id}")
async def api_delete_category(project_id:int,cat_id:int):
    conn=get_db(); conn.execute("UPDATE tasks SET category_id=NULL WHERE category_id=? AND project_id=?",(cat_id,project_id)); conn.execute("DELETE FROM categories WHERE id=? AND project_id=?",(cat_id,project_id)); conn.commit(); conn.close(); return {"ok":True}

@app.post("/api/projects/{project_id}/categories/reorder")
async def api_reorder_categories(project_id:int,request:Request):
    data=await request.json(); order=data.get("order",[]); conn=get_db()
    for idx,cid in enumerate(order): conn.execute("UPDATE categories SET sort_order=? WHERE id=? AND project_id=?",(idx,cid,project_id))
    conn.commit(); conn.close(); return {"ok":True}

@app.post("/api/projects/{project_id}/tasks/reorder")
async def api_reorder_tasks(project_id:int,request:Request):
    data=await request.json(); order=data.get("order",[]); conn=get_db()
    for idx,tid in enumerate(order): conn.execute("UPDATE tasks SET sort_order=? WHERE id=? AND project_id=?",(idx,tid,project_id))
    conn.commit(); conn.close(); return {"ok":True}

@app.post("/api/projects/{project_id}/tasks/bulk-update")
async def api_bulk_update_tasks(project_id:int,request:Request):
    data=await request.json(); updates=data.get("updates",[]); conn=get_db()
    allowed={"title","title_en","status","progress","date_label","start_date","end_date","category_id","description","ado_item_id","sort_order"}; updated=0
    for upd in updates:
        tid=upd.get("id"); fields={k:v for k,v in upd.items() if k in allowed}
        if tid and fields:
            fields["updated_at"]=date.today().isoformat(); sets=", ".join(f"{k}=?" for k in fields)
            conn.execute(f"UPDATE tasks SET {sets} WHERE id=? AND project_id=?",list(fields.values())+[tid,project_id]); updated+=1
    conn.commit(); conn.close(); return {"ok":True,"updated":updated}

@app.patch("/api/projects/{project_id}/milestones/{ms_id}")
async def api_update_milestone(project_id:int,ms_id:int,request:Request):
    data=await request.json(); allowed={"title","baseline_date","current_date","status","sort_order"}; fields={k:v for k,v in data.items() if k in allowed}
    if fields:
        conn=get_db(); sets=", ".join(f"{k}=?" for k in fields); conn.execute(f"UPDATE milestones SET {sets} WHERE id=? AND project_id=?",list(fields.values())+[ms_id,project_id]); conn.commit(); conn.close()
    return {"ok":True}

@app.patch("/api/projects/{project_id}/risks/{risk_id}")
async def api_update_risk(project_id:int,risk_id:int,request:Request):
    data=await request.json(); allowed={"risk_type","description","owner","status"}; fields={k:v for k,v in data.items() if k in allowed}
    if fields:
        conn=get_db(); sets=", ".join(f"{k}=?" for k in fields); conn.execute(f"UPDATE risks SET {sets} WHERE id=? AND project_id=?",list(fields.values())+[risk_id,project_id]); conn.commit(); conn.close()
    return {"ok":True}

@app.post("/api/projects/{project_id}/ai/agent")
async def api_ai_agent(project_id:int,request:Request):
    import json as _json
    project=get_project(project_id)
    if not project: raise HTTPException(404)
    data=await request.json(); message=data.get("message",""); language=data.get("language",project.get("language","fr")); history=data.get("history",[])
    if not message.strip(): return {"reply":"Que puis-je faire ?","actions":[],"reload":False}
    categories=get_categories(project_id); tasks=get_tasks(project_id); milestones=get_milestones(project_id); risks=get_risks(project_id)
    context={"project_id":project_id,"project_name":project.get("name"),"language":language,
        "categories":[{"id":c["id"],"name":c["name"],"color":c.get("color")} for c in categories],
        "tasks":[{"id":t["id"],"title":t["title"],"category_id":t.get("category_id"),"status":t.get("status"),"progress":t.get("progress",0),"start_date":t.get("start_date"),"end_date":t.get("end_date"),"date_label":t.get("date_label")} for t in tasks],
        "milestones":[{"id":m["id"],"title":m["title"],"baseline_date":m.get("baseline_date"),"current_date":m.get("current_date"),"status":m.get("status")} for m in milestones],
        "risks":[{"id":r["id"],"description":r["description"],"owner":r.get("owner"),"risk_type":r.get("risk_type"),"status":r.get("status")} for r in risks]}
    from ai.task_parser import AgentParser
    agent=AgentParser(os.getenv("GROQ_API_KEY","")); result=agent.run(message=message,context=context,history=history,language=language)
    executed=[]; reload_needed=False
    allowed_t={"title","title_en","status","progress","date_label","start_date","end_date","category_id","description","ado_item_id","sort_order"}
    for action in result.get("actions",[]):
        atype=action.get("type","")
        try:
            if atype=="create_task":
                p=action.get("params",{}); tid=create_task(project_id=project_id,**{k:v for k,v in p.items() if k in {"title","category_id","status","progress","date_label","start_date","end_date","description","ado_item_id"}}); executed.append({"type":atype,"id":tid,"ok":True}); reload_needed=True
            elif atype=="update_task":
                tid=action.get("id"); p=action.get("params",{})
                if tid: update_task(tid,**{k:v for k,v in p.items() if k in allowed_t})
                executed.append({"type":atype,"id":tid,"ok":True}); reload_needed=True
            elif atype=="delete_task":
                tid=action.get("id")
                if tid: delete_task(tid)
                executed.append({"type":atype,"id":tid,"ok":True}); reload_needed=True
            elif atype=="bulk_update_tasks":
                updates=action.get("updates",[]); conn=get_db()
                for upd in updates:
                    tid=upd.get("id"); fields={k:v for k,v in upd.items() if k in allowed_t}
                    if tid and fields:
                        fields["updated_at"]=date.today().isoformat(); sets=", ".join(f"{k}=?" for k in fields)
                        conn.execute(f"UPDATE tasks SET {sets} WHERE id=? AND project_id=?",list(fields.values())+[tid,project_id])
                conn.commit(); conn.close(); executed.append({"type":atype,"count":len(updates),"ok":True}); reload_needed=True
            elif atype=="create_category":
                p=action.get("params",{}); cid=create_category(project_id,p.get("name",""),p.get("name_en",""),p.get("color","#041E42")); executed.append({"type":atype,"id":cid,"ok":True}); reload_needed=True
            elif atype=="update_category":
                cid=action.get("id"); p=action.get("params",{}); fields={k:v for k,v in p.items() if k in {"name","name_en","color","sort_order"}}
                if cid and fields:
                    conn=get_db(); sets=", ".join(f"{k}=?" for k in fields); conn.execute(f"UPDATE categories SET {sets} WHERE id=? AND project_id=?",list(fields.values())+[cid,project_id]); conn.commit(); conn.close()
                executed.append({"type":atype,"id":cid,"ok":True}); reload_needed=True
            elif atype=="delete_category":
                cid=action.get("id")
                if cid:
                    conn=get_db(); conn.execute("UPDATE tasks SET category_id=NULL WHERE category_id=? AND project_id=?",(cid,project_id)); conn.execute("DELETE FROM categories WHERE id=? AND project_id=?",(cid,project_id)); conn.commit(); conn.close()
                executed.append({"type":atype,"id":cid,"ok":True}); reload_needed=True
            elif atype=="reorder_categories":
                order=action.get("order",[]); conn=get_db()
                for idx,cid in enumerate(order): conn.execute("UPDATE categories SET sort_order=? WHERE id=? AND project_id=?",(idx,cid,project_id))
                conn.commit(); conn.close(); executed.append({"type":atype,"ok":True}); reload_needed=True
            elif atype=="create_milestone":
                p=action.get("params",{}); mid=create_milestone(project_id,p.get("title",""),p.get("baseline_date",""),p.get("current_date",""),p.get("status","In progress")); executed.append({"type":atype,"id":mid,"ok":True}); reload_needed=True
            elif atype=="update_milestone":
                mid=action.get("id"); p=action.get("params",{}); fields={k:v for k,v in p.items() if k in {"title","baseline_date","current_date","status"}}
                if mid and fields:
                    conn=get_db(); sets=", ".join(f"{k}=?" for k in fields); conn.execute(f"UPDATE milestones SET {sets} WHERE id=? AND project_id=?",list(fields.values())+[mid,project_id]); conn.commit(); conn.close()
                executed.append({"type":atype,"id":mid,"ok":True}); reload_needed=True
            elif atype=="create_risk":
                p=action.get("params",{}); rid=create_risk(project_id,p.get("description",""),p.get("owner",""),p.get("risk_type","I")); executed.append({"type":atype,"id":rid,"ok":True}); reload_needed=True
            elif atype=="update_risk":
                rid=action.get("id"); p=action.get("params",{}); fields={k:v for k,v in p.items() if k in {"risk_type","description","owner","status"}}
                if rid and fields:
                    conn=get_db(); sets=", ".join(f"{k}=?" for k in fields); conn.execute(f"UPDATE risks SET {sets} WHERE id=? AND project_id=?",list(fields.values())+[rid,project_id]); conn.commit(); conn.close()
                executed.append({"type":atype,"id":rid,"ok":True}); reload_needed=True
        except Exception as ex:
            executed.append({"type":atype,"ok":False,"error":str(ex)})
    return {"reply":result.get("reply",""),"actions":executed,"reload":reload_needed}


# ═══════════════════════════════════════════════════════════════════════════════
# API — Mise à jour
# ═══════════════════════════════════════════════════════════════════════════════

@app.get("/api/update/status")
async def api_update_status():
    return _updater.get_state()

@app.post("/api/update/check")
async def api_update_check():
    return _updater.check_now()

@app.post("/api/update/apply")
async def api_update_apply():
    return _updater.apply_update()

