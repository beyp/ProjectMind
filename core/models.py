"""
ProjectMind - Modeles de données SQLite.
"""
from collections import defaultdict
from datetime import datetime, date
from pathlib import Path
from typing import Any
import sqlite3
import json

DB_PATH = Path("data/projectmind.db")

# ── Constantes ────────────────────────────────────────────────────────────────

STATUSES = {
    "fr": ["En cours", "Réalisé", "A planifier", "Bloqué", "Annulé", "En retard", "En revue"],
    "en": ["In Progress", "Completed", "To Plan", "Blocked", "Cancelled", "Delayed", "In Review"],
}

STATUS_COLORS = {
    "En cours":    "#1E90FF", "In Progress": "#1E90FF",
    "Réalisé":     "#41B449", "Completed":   "#41B449",
    "A planifier": "#888888", "To Plan":     "#888888",
    "Bloqué":      "#FF4444", "Blocked":     "#FF4444",
    "Annulé":      "#999999", "Cancelled":   "#999999",
    "En retard":   "#FF8C00", "Delayed":     "#FF8C00",
    "En revue":    "#9C27B0", "In Review":   "#9C27B0",
}

KPI_ITEMS = ["COST", "SCOPE", "SCHEDULE", "RESOURCES", "RISK", "TRANSITION"]


def get_db() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    """Initialise la base de données avec toutes les tables."""
    conn = get_db()
    c    = conn.cursor()

    c.execute("""
        CREATE TABLE IF NOT EXISTS projects (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            name          TEXT NOT NULL,
            description   TEXT,
            language      TEXT DEFAULT 'fr',
            go_live_date  TEXT,
            ado_project   TEXT,
            ado_area_path TEXT,
            created_at    TEXT DEFAULT (datetime('now')),
            updated_at    TEXT DEFAULT (datetime('now'))
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS project_kpis (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
            kpi_name   TEXT NOT NULL,
            prev_value TEXT DEFAULT 'G',
            curr_value TEXT DEFAULT 'G',
            week_date  TEXT DEFAULT (date('now')),
            UNIQUE(project_id, kpi_name, week_date)
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS categories (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
            name       TEXT NOT NULL,
            name_en    TEXT,
            color      TEXT DEFAULT '#041E42',
            sort_order INTEGER DEFAULT 0,
            created_at TEXT DEFAULT (datetime('now'))
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS tasks (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id    INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
            category_id   INTEGER REFERENCES categories(id) ON DELETE SET NULL,
            title         TEXT NOT NULL,
            title_en      TEXT,
            description   TEXT,
            status        TEXT DEFAULT 'A planifier',
            date_label    TEXT,
            start_date    TEXT,
            end_date      TEXT,
            progress      INTEGER DEFAULT 0,
            ado_item_id   INTEGER,
            ado_project   TEXT,
            ado_area_path TEXT,
            sort_order    INTEGER DEFAULT 0,
            created_at    TEXT DEFAULT (datetime('now')),
            updated_at    TEXT DEFAULT (datetime('now'))
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS milestones (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id    INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
            title         TEXT NOT NULL,
            baseline_date TEXT,
            current_date  TEXT,
            status        TEXT DEFAULT 'In progress',
            sort_order    INTEGER DEFAULT 0
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS risks (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
            risk_type  TEXT DEFAULT 'I',
            description TEXT NOT NULL,
            owner      TEXT,
            status     TEXT DEFAULT 'Open',
            created_at TEXT DEFAULT (datetime('now'))
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS weekly_notes (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id   INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
            week_date    TEXT DEFAULT (date('now')),
            summary      TEXT,
            achievements TEXT,
            planned      TEXT,
            watch_items  TEXT,
            created_at   TEXT DEFAULT (datetime('now'))
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS resources (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id   INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
            acronym      TEXT NOT NULL,
            full_name    TEXT,
            is_external  INTEGER DEFAULT 0,
            max_fraction REAL    DEFAULT 1.0,
            color        TEXT    DEFAULT '#1E90FF',
            sort_order   INTEGER DEFAULT 0
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS capacity (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id  INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
            resource_id INTEGER NOT NULL REFERENCES resources(id) ON DELETE CASCADE,
            task_id     INTEGER REFERENCES tasks(id) ON DELETE SET NULL,
            category_id INTEGER REFERENCES categories(id) ON DELETE SET NULL,
            year        INTEGER NOT NULL,
            week        INTEGER NOT NULL,
            fraction    REAL    DEFAULT 0.0,
            UNIQUE(resource_id, task_id, year, week)
        )
    """)

    conn.commit()
    conn.close()


# ── Projects ──────────────────────────────────────────────────────────────────

def get_all_projects() -> list[dict]:
    conn = get_db()
    rows = conn.execute("SELECT * FROM projects ORDER BY created_at DESC").fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_project(project_id: int) -> dict | None:
    conn = get_db()
    row  = conn.execute("SELECT * FROM projects WHERE id=?", (project_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def create_project(name: str, description: str = "", language: str = "fr",
                   go_live_date: str = "", ado_project: str = "",
                   ado_area_path: str = "") -> int:
    conn = get_db()
    c    = conn.cursor()
    c.execute("""
        INSERT INTO projects (name, description, language, go_live_date, ado_project, ado_area_path)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (name, description, language, go_live_date, ado_project, ado_area_path))
    project_id = c.lastrowid
    for kpi in KPI_ITEMS:
        c.execute("INSERT OR IGNORE INTO project_kpis (project_id, kpi_name) VALUES (?, ?)",
                  (project_id, kpi))
    conn.commit()
    conn.close()
    return project_id


def delete_project(project_id: int) -> bool:
    conn = get_db()
    c    = conn.cursor()
    c.execute("DELETE FROM projects WHERE id=?", (project_id,))
    deleted = c.rowcount > 0
    conn.commit()
    conn.close()
    return deleted


# ── Categories ────────────────────────────────────────────────────────────────

def get_categories(project_id: int) -> list[dict]:
    conn = get_db()
    rows = conn.execute(
        "SELECT * FROM categories WHERE project_id=? ORDER BY sort_order, id",
        (project_id,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def create_category(project_id: int, name: str, name_en: str = "",
                    color: str = "#041E42") -> int:
    conn = get_db()
    c    = conn.cursor()
    c.execute("INSERT INTO categories (project_id, name, name_en, color) VALUES (?, ?, ?, ?)",
              (project_id, name, name_en, color))
    cat_id = c.lastrowid
    conn.commit()
    conn.close()
    return cat_id


def update_category(category_id: int, **kwargs) -> None:
    if not kwargs: return
    sets = ", ".join(f"{k}=?" for k in kwargs)
    vals = list(kwargs.values()) + [category_id]
    conn = get_db()
    conn.execute(f"UPDATE categories SET {sets} WHERE id=?", vals)
    conn.commit()
    conn.close()


def delete_category(category_id: int) -> bool:
    conn = get_db()
    conn.execute("UPDATE tasks SET category_id=NULL WHERE category_id=?", (category_id,))
    c    = conn.cursor()
    c.execute("DELETE FROM categories WHERE id=?", (category_id,))
    deleted = c.rowcount > 0
    conn.commit()
    conn.close()
    return deleted


def reorder_categories(project_id: int, ordered_ids: list[int]) -> None:
    conn = get_db()
    for idx, cat_id in enumerate(ordered_ids):
        conn.execute("UPDATE categories SET sort_order=? WHERE id=? AND project_id=?",
                     (idx, cat_id, project_id))
    conn.commit()
    conn.close()


# ── Tasks ─────────────────────────────────────────────────────────────────────

def get_tasks(project_id: int, category_id: int | None = None) -> list[dict]:
    conn = get_db()
    if category_id:
        rows = conn.execute(
            "SELECT * FROM tasks WHERE project_id=? AND category_id=? ORDER BY sort_order, id",
            (project_id, category_id)
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM tasks WHERE project_id=? ORDER BY category_id, sort_order, id",
            (project_id,)
        ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_task(task_id: int) -> dict | None:
    conn = get_db()
    row  = conn.execute("SELECT * FROM tasks WHERE id=?", (task_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def create_task(project_id: int, title: str, category_id: int | None = None,
                status: str = "A planifier", date_label: str = "",
                start_date: str = "", end_date: str = "",
                description: str = "", ado_item_id: int | None = None) -> int:
    conn = get_db()
    c    = conn.cursor()
    c.execute("""
        INSERT INTO tasks
        (project_id, category_id, title, status, date_label, start_date, end_date,
         description, ado_item_id)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (project_id, category_id, title, status, date_label,
          start_date, end_date, description, ado_item_id))
    task_id = c.lastrowid
    conn.commit()
    conn.close()
    return task_id


def update_task(task_id: int, **kwargs) -> None:
    if not kwargs: return
    kwargs["updated_at"] = datetime.now().isoformat()
    sets = ", ".join(f"{k}=?" for k in kwargs)
    vals = list(kwargs.values()) + [task_id]
    conn = get_db()
    conn.execute(f"UPDATE tasks SET {sets} WHERE id=?", vals)
    conn.commit()
    conn.close()


def delete_task(task_id: int) -> bool:
    conn = get_db()
    c    = conn.cursor()
    c.execute("DELETE FROM tasks WHERE id=?", (task_id,))
    deleted = c.rowcount > 0
    conn.commit()
    conn.close()
    return deleted


# ── KPIs ──────────────────────────────────────────────────────────────────────

def get_kpis(project_id: int) -> list[dict]:
    conn = get_db()
    rows = conn.execute(
        "SELECT * FROM project_kpis WHERE project_id=? ORDER BY id",
        (project_id,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ── Weekly notes ──────────────────────────────────────────────────────────────

def get_weekly_note(project_id: int) -> dict | None:
    conn = get_db()
    row  = conn.execute(
        "SELECT * FROM weekly_notes WHERE project_id=? ORDER BY week_date DESC LIMIT 1",
        (project_id,)
    ).fetchone()
    conn.close()
    return dict(row) if row else None


# ── Milestones ────────────────────────────────────────────────────────────────

def get_milestones(project_id: int) -> list[dict]:
    conn = get_db()
    rows = conn.execute(
        "SELECT * FROM milestones WHERE project_id=? ORDER BY sort_order, id",
        (project_id,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ── Risks ─────────────────────────────────────────────────────────────────────

def get_risks(project_id: int) -> list[dict]:
    conn = get_db()
    rows = conn.execute(
        "SELECT * FROM risks WHERE project_id=? AND status='Open' ORDER BY id",
        (project_id,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ── Resources ─────────────────────────────────────────────────────────────────

def get_resources(project_id: int) -> list[dict]:
    conn = get_db()
    rows = conn.execute(
        "SELECT * FROM resources WHERE project_id=? ORDER BY sort_order, id",
        (project_id,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def create_resource(project_id: int, acronym: str, full_name: str = "",
                    is_external: bool = False, max_fraction: float = 1.0,
                    color: str = "#1E90FF") -> int:
    conn = get_db()
    c    = conn.cursor()
    c.execute("""
        INSERT INTO resources (project_id, acronym, full_name, is_external, max_fraction, color)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (project_id, acronym, full_name, int(is_external), max_fraction, color))
    rid = c.lastrowid
    conn.commit()
    conn.close()
    return rid


def update_resource(resource_id: int, **kwargs) -> None:
    if not kwargs: return
    sets = ", ".join(f"{k}=?" for k in kwargs)
    vals = list(kwargs.values()) + [resource_id]
    conn = get_db()
    conn.execute(f"UPDATE resources SET {sets} WHERE id=?", vals)
    conn.commit()
    conn.close()


def delete_resource(resource_id: int) -> bool:
    conn = get_db()
    c    = conn.cursor()
    c.execute("DELETE FROM resources WHERE id=?", (resource_id,))
    deleted = c.rowcount > 0
    conn.commit()
    conn.close()
    return deleted


# ── Capacity ──────────────────────────────────────────────────────────────────

def get_capacity(project_id: int, year: int | None = None) -> list[dict]:
    conn = get_db()
    if year:
        rows = conn.execute("""
            SELECT c.*, r.acronym, r.full_name, r.max_fraction, r.color,
                   t.title as task_title, cat.name as category_name
            FROM capacity c
            JOIN resources r ON c.resource_id = r.id
            LEFT JOIN tasks t ON c.task_id = t.id
            LEFT JOIN categories cat ON c.category_id = cat.id
            WHERE c.project_id=? AND c.year=?
            ORDER BY r.sort_order, r.id, c.week
        """, (project_id, year)).fetchall()
    else:
        rows = conn.execute("""
            SELECT c.*, r.acronym, r.full_name, r.max_fraction, r.color,
                   t.title as task_title, cat.name as category_name
            FROM capacity c
            JOIN resources r ON c.resource_id = r.id
            LEFT JOIN tasks t ON c.task_id = t.id
            LEFT JOIN categories cat ON c.category_id = cat.id
            WHERE c.project_id=?
            ORDER BY r.sort_order, r.id, c.year, c.week
        """, (project_id,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def upsert_capacity(project_id: int, resource_id: int, year: int, week: int,
                    fraction: float, task_id: int | None = None,
                    category_id: int | None = None) -> None:
    conn = get_db()
    conn.execute("""
        INSERT INTO capacity
        (project_id, resource_id, task_id, category_id, year, week, fraction)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(resource_id, task_id, year, week)
        DO UPDATE SET fraction=excluded.fraction,
                      category_id=excluded.category_id
    """, (project_id, resource_id, task_id, category_id, year, week, fraction))
    conn.commit()
    conn.close()


def get_capacity_matrix(project_id: int, year: int) -> dict:
    """
    Retourne la matrice capacity :
    { matrix: {res_id: {week: fraction}}, weeks: [...], resources: [...] }
    """
    rows      = get_capacity(project_id, year)
    resources = get_resources(project_id)
    matrix: dict[int, dict[int, float]] = defaultdict(dict)
    weeks_set: set[int] = set()

    for row in rows:
        rid  = row["resource_id"]
        week = row["week"]
        frac = row["fraction"]
        matrix[rid][week] = matrix[rid].get(week, 0.0) + frac
        weeks_set.add(week)

    weeks = sorted(weeks_set)
    week_totals = {
        week: sum(matrix.get(r["id"], {}).get(week, 0.0) for r in resources)
        for week in weeks
    }

    return {
        "matrix":      {str(k): v for k, v in matrix.items()},
        "weeks":       weeks,
        "resources":   resources,
        "week_totals": week_totals,
    }


# ── Fiscal Year helpers ───────────────────────────────────────────────────────

def get_fiscal_year(d: date | None = None) -> str:
    if d is None: d = date.today()
    fy = d.year + 1 if d.month >= 3 else d.year
    return f"FY{str(fy)[2:]}"


def get_fiscal_quarter(d: date | None = None) -> str:
    if d is None: d = date.today()
    fy = get_fiscal_year(d)
    q  = {3:"Q1",4:"Q1",5:"Q1",6:"Q2",7:"Q2",8:"Q2",
          9:"Q3",10:"Q3",11:"Q3"}.get(d.month, "Q4")
    return f"{fy}-{q}"
