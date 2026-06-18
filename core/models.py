"""
ProjectMind - Modeles de données SQLite.
"""
import sqlite3
from datetime import datetime, date
from pathlib import Path
from typing import Any

DB_PATH = Path("data/projectmind.db")

# ── Statuts disponibles ────────────────────────────────────────────────────────
STATUSES = {
    "fr": ["En cours", "Réalisé", "A planifier", "Bloqué", "Annulé", "En retard", "En revue"],
    "en": ["In Progress", "Completed", "To Plan", "Blocked", "Cancelled", "Delayed", "In Review"],
}

STATUS_COLORS = {
    "En cours":    "#1E90FF",
    "In Progress": "#1E90FF",
    "Réalisé":     "#41B449",
    "Completed":   "#41B449",
    "A planifier": "#888888",
    "To Plan":     "#888888",
    "Bloqué":      "#FF4444",
    "Blocked":     "#FF4444",
    "Annulé":      "#999999",
    "Cancelled":   "#999999",
    "En retard":   "#FF8C00",
    "Delayed":     "#FF8C00",
    "En revue":    "#9C27B0",
    "In Review":   "#9C27B0",
}

# KPI couleurs
KPI_COLORS = {
    "G": {"label": "Green",  "hex": "#92D050"},
    "Y": {"label": "Yellow", "hex": "#FFFF00"},
    "R": {"label": "Red",    "hex": "#FF0000"},
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
    c = conn.cursor()

    # ── Projects ──────────────────────────────────────────────────────────────
    c.execute("""
        CREATE TABLE IF NOT EXISTS projects (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            name        TEXT NOT NULL,
            description TEXT,
            language    TEXT DEFAULT 'fr',
            go_live_date TEXT,
            ado_project TEXT,
            ado_area_path TEXT,
            created_at  TEXT DEFAULT (datetime('now')),
            updated_at  TEXT DEFAULT (datetime('now'))
        )
    """)

    # ── KPIs par projet ────────────────────────────────────────────────────────
    c.execute("""
        CREATE TABLE IF NOT EXISTS project_kpis (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id  INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
            kpi_name    TEXT NOT NULL,
            prev_value  TEXT DEFAULT 'G',
            curr_value  TEXT DEFAULT 'G',
            week_date   TEXT DEFAULT (date('now')),
            UNIQUE(project_id, kpi_name, week_date)
        )
    """)

    # ── Categories (livrables) ─────────────────────────────────────────────────
    c.execute("""
        CREATE TABLE IF NOT EXISTS categories (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id  INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
            name        TEXT NOT NULL,
            name_en     TEXT,
            color       TEXT DEFAULT '#041E42',
            sort_order  INTEGER DEFAULT 0,
            created_at  TEXT DEFAULT (datetime('now'))
        )
    """)

    # ── Tasks (tâches/activités) ───────────────────────────────────────────────
    c.execute("""
        CREATE TABLE IF NOT EXISTS tasks (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id   INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
            category_id  INTEGER REFERENCES categories(id) ON DELETE SET NULL,
            title        TEXT NOT NULL,
            title_en     TEXT,
            description  TEXT,
            status       TEXT DEFAULT 'A planifier',
            date_label   TEXT,
            start_date   TEXT,
            end_date     TEXT,
            progress     INTEGER DEFAULT 0,
            ado_item_id  INTEGER,
            ado_project  TEXT,
            ado_area_path TEXT,
            sort_order   INTEGER DEFAULT 0,
            created_at   TEXT DEFAULT (datetime('now')),
            updated_at   TEXT DEFAULT (datetime('now'))
        )
    """)

    # ── Milestones (jalons 4 semaines) ────────────────────────────────────────
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

    # ── Risks / Issues ────────────────────────────────────────────────────────
    c.execute("""
        CREATE TABLE IF NOT EXISTS risks (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id  INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
            risk_type   TEXT DEFAULT 'I',
            description TEXT NOT NULL,
            owner       TEXT,
            status      TEXT DEFAULT 'Open',
            created_at  TEXT DEFAULT (datetime('now'))
        )
    """)

    # ── Weekly notes ──────────────────────────────────────────────────────────
    c.execute("""
        CREATE TABLE IF NOT EXISTS weekly_notes (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id      INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
            week_date       TEXT DEFAULT (date('now')),
            summary         TEXT,
            achievements    TEXT,
            planned         TEXT,
            watch_items     TEXT,
            created_at      TEXT DEFAULT (datetime('now'))
        )
    """)

    # ── Migration : ajouter la colonne role si elle n existe pas
    try:
        conn.execute("ALTER TABLE resources ADD COLUMN role TEXT DEFAULT ''")
        conn.commit()
    except Exception:
        pass  # Colonne deja presente

    conn.commit()
    conn.close()


# ── CRUD helpers ──────────────────────────────────────────────────────────────

def get_all_projects() -> list[dict]:
    conn = get_db()
    rows = conn.execute("SELECT * FROM projects ORDER BY created_at DESC").fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_project(project_id: int) -> dict | None:
    conn = get_db()
    row = conn.execute("SELECT * FROM projects WHERE id=?", (project_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def create_project(name: str, description: str = "", language: str = "fr",
                   go_live_date: str = "", ado_project: str = "",
                   ado_area_path: str = "") -> int:
    conn = get_db()
    c = conn.cursor()
    c.execute("""
        INSERT INTO projects (name, description, language, go_live_date, ado_project, ado_area_path)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (name, description, language, go_live_date, ado_project, ado_area_path))
    project_id = c.lastrowid
    # Initialiser les KPIs par défaut
    for kpi in KPI_ITEMS:
        c.execute("""
            INSERT OR IGNORE INTO project_kpis (project_id, kpi_name)
            VALUES (?, ?)
        """, (project_id, kpi))
    conn.commit()
    conn.close()
    return project_id


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
    c = conn.cursor()
    c.execute("""
        INSERT INTO categories (project_id, name, name_en, color)
        VALUES (?, ?, ?, ?)
    """, (project_id, name, name_en, color))
    cat_id = c.lastrowid
    conn.commit()
    conn.close()
    return cat_id


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


def create_task(project_id: int, title: str, category_id: int | None = None,
                status: str = "A planifier", date_label: str = "",
                start_date: str = "", end_date: str = "",
                description: str = "", ado_item_id: int | None = None) -> int:
    conn = get_db()
    c = conn.cursor()
    c.execute("""
        INSERT INTO tasks
        (project_id, category_id, title, status, date_label,
         start_date, end_date, description, ado_item_id)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (project_id, category_id, title, status, date_label,
          start_date, end_date, description, ado_item_id))
    task_id = c.lastrowid
    conn.commit()
    conn.close()
    return task_id


def update_task(task_id: int, **kwargs) -> None:
    if not kwargs:
        return
    kwargs["updated_at"] = datetime.now().isoformat()
    sets  = ", ".join(f"{k}=?" for k in kwargs)
    vals  = list(kwargs.values()) + [task_id]
    conn  = get_db()
    conn.execute(f"UPDATE tasks SET {sets} WHERE id=?", vals)
    conn.commit()
    conn.close()


def get_kpis(project_id: int) -> list[dict]:
    """Retourne UN seul enregistrement par KPI (le plus recent)."""
    conn = get_db()
    rows = conn.execute("""
        SELECT * FROM project_kpis
        WHERE project_id=?
        GROUP BY kpi_name
        HAVING MAX(week_date)
        ORDER BY id
    """, (project_id,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_weekly_note(project_id: int) -> dict | None:
    conn = get_db()
    row = conn.execute(
        "SELECT * FROM weekly_notes WHERE project_id=? ORDER BY week_date DESC LIMIT 1",
        (project_id,)
    ).fetchone()
    conn.close()
    return dict(row) if row else None


def get_milestones(project_id: int) -> list[dict]:
    conn = get_db()
    rows = conn.execute(
        "SELECT * FROM milestones WHERE project_id=? ORDER BY sort_order, id",
        (project_id,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_risks(project_id: int) -> list[dict]:
    conn = get_db()
    rows = conn.execute(
        "SELECT * FROM risks WHERE project_id=? AND status='Open' ORDER BY id",
        (project_id,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ── Fiscal Year helpers ────────────────────────────────────────────────────────

def delete_project(project_id: int) -> bool:
    """Supprime un projet et toutes ses donnees (CASCADE)."""
    conn = get_db()
    c    = conn.cursor()
    c.execute("DELETE FROM projects WHERE id=?", (project_id,))
    deleted = c.rowcount > 0
    conn.commit()
    conn.close()
    return deleted


def get_task_assignments(task_id: int) -> list[dict]:
    """Retourne les ressources assignées à une tâche."""
    conn = get_db()
    rows = conn.execute("""
        SELECT ta.*, r.acronym, r.full_name, r.color, r.max_fraction
        FROM task_assignments ta
        JOIN resources r ON ta.resource_id = r.id
        WHERE ta.task_id=?
        ORDER BY r.acronym
    """, (task_id,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_project_assignments(project_id: int) -> list[dict]:
    """Retourne toutes les assignations d'un projet."""
    conn = get_db()
    rows = conn.execute("""
        SELECT ta.*, r.acronym, r.full_name, r.color, t.title as task_title,
               t.start_date, t.end_date, t.progress
        FROM task_assignments ta
        JOIN resources r ON ta.resource_id = r.id
        JOIN tasks t ON ta.task_id = t.id
        WHERE t.project_id=?
        ORDER BY r.acronym, t.id
    """, (project_id,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def upsert_task_assignment(task_id: int, resource_id: int,
                           hours: float = 0.0, fraction: float = 0.0,
                           notes: str = "") -> int:
    """Crée ou met à jour une assignation ressource ↔ tâche."""
    conn = get_db()
    c    = conn.cursor()
    c.execute("""
        INSERT INTO task_assignments (task_id, resource_id, hours, fraction, notes)
        VALUES (?, ?, ?, ?, ?)
        ON CONFLICT(task_id, resource_id)
        DO UPDATE SET hours=excluded.hours,
                      fraction=excluded.fraction,
                      notes=excluded.notes
    """, (task_id, resource_id, hours, fraction, notes))
    aid = c.lastrowid
    conn.commit()
    conn.close()
    return aid


def delete_task_assignment(task_id: int, resource_id: int) -> bool:
    conn = get_db()
    c    = conn.cursor()
    c.execute("DELETE FROM task_assignments WHERE task_id=? AND resource_id=?",
              (task_id, resource_id))
    deleted = c.rowcount > 0
    conn.commit()
    conn.close()
    return deleted


def compute_task_end_date(task_id: int) -> str | None:
    """
    Calcule la date de fin estimée d'une tâche
    basée sur les assignations de ressources et le start_date.
    Logique : total_hours / (sum des fractions * 40h/sem) → nb semaines.
    """
    from datetime import date, timedelta
    conn  = get_db()
    task  = conn.execute("SELECT * FROM tasks WHERE id=?", (task_id,)).fetchone()
    if not task or not task["start_date"]:
        conn.close()
        return None

    assigns = conn.execute("""
        SELECT ta.hours, ta.fraction, r.max_fraction
        FROM task_assignments ta
        JOIN resources r ON ta.resource_id = r.id
        WHERE ta.task_id=?
    """, (task_id,)).fetchall()
    conn.close()

    if not assigns:
        return None

    # Heures totales nécessaires
    total_hours = sum(a["hours"] for a in assigns if a["hours"] > 0)
    if total_hours == 0:
        return None

    # Capacité hebdomadaire totale des ressources assignées (en heures/sem)
    weekly_capacity = sum(
        (a["fraction"] if a["fraction"] > 0 else a["max_fraction"]) * 40
        for a in assigns
    )
    if weekly_capacity == 0:
        return None

    weeks_needed = total_hours / weekly_capacity
    try:
        start = date.fromisoformat(task["start_date"])
        end   = start + timedelta(weeks=weeks_needed)
        return end.isoformat()
    except Exception:
        return None


def get_resources(project_id: int) -> list[dict]:
    conn = get_db()
    rows = conn.execute(
        "SELECT * FROM resources WHERE project_id=? ORDER BY sort_order, id",
        (project_id,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def create_resource(project_id: int, acronym: str, full_name: str = "",
                    role: str = "", is_external: bool = False,
                    max_fraction: float = 1.0, color: str = "#1E90FF") -> int:
    conn = get_db()
    c    = conn.cursor()
    c.execute("""
        INSERT INTO resources
        (project_id, acronym, full_name, role, is_external, max_fraction, color)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (project_id, acronym, full_name, role, int(is_external), max_fraction, color))
    rid = c.lastrowid
    conn.commit()
    conn.close()
    return rid


def update_resource(resource_id: int, **kwargs) -> None:
    if not kwargs:
        return
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


def reorder_resources(project_id: int, ordered_ids: list[int]) -> None:
    conn = get_db()
    for idx, rid in enumerate(ordered_ids):
        conn.execute(
            "UPDATE resources SET sort_order=? WHERE id=? AND project_id=?",
            (idx, rid, project_id)
        )
    conn.commit()
    conn.close()


def get_capacity(project_id: int, year: int | None = None) -> list[dict]:
    conn = get_db()
    if year:
        rows = conn.execute("""
            SELECT c.*, r.acronym, r.full_name, r.max_fraction, r.color
            FROM capacity c
            JOIN resources r ON c.resource_id = r.id
            WHERE c.project_id=? AND c.year=?
            ORDER BY r.sort_order, r.id, c.week
        """, (project_id, year)).fetchall()
    else:
        rows = conn.execute("""
            SELECT c.*, r.acronym, r.full_name, r.max_fraction, r.color
            FROM capacity c
            JOIN resources r ON c.resource_id = r.id
            WHERE c.project_id=?
            ORDER BY r.sort_order, r.id, c.year, c.week
        """, (project_id,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def upsert_capacity(project_id: int, resource_id: int, year: int, week: int,
                    fraction: float) -> None:
    """Insère ou met à jour une cellule capacity."""
    conn = get_db()
    # Utiliser INSERT OR REPLACE pour compatibilité SQLite
    conn.execute("""
        INSERT INTO capacity (project_id, resource_id, year, week, fraction)
        VALUES (?, ?, ?, ?, ?)
        ON CONFLICT(resource_id, task_id, year, week)
        DO UPDATE SET fraction=excluded.fraction
    """, (project_id, resource_id, year, week, fraction))
    conn.commit()
    conn.close()


def get_capacity_matrix(project_id: int, year: int) -> dict:
    """
    Retourne matrix[str(resource_id)][week] = fraction
    pour affichage dans le tableau capacity.
    """
    rows      = get_capacity(project_id, year)
    resources = get_resources(project_id)
    matrix: dict[str, dict[int, float]] = {}

    for row in rows:
        rid  = str(row["resource_id"])
        week = row["week"]
        frac = row["fraction"]
        if rid not in matrix:
            matrix[rid] = {}
        matrix[rid][week] = matrix[rid].get(week, 0.0) + frac

    return {
        "matrix":    matrix,
        "resources": resources,
    }


def get_fiscal_year(d: date | None = None) -> str:
    """Retourne le Fiscal Year pour une date (ex: FY27)."""
    if d is None:
        d = date.today()
    # FY commence le 1er mars
    if d.month >= 3:
        fy = d.year + 1
    else:
        fy = d.year
    return f"FY{str(fy)[2:]}"


def get_fiscal_quarter(d: date | None = None) -> str:
    """Retourne le quarter fiscal (ex: FY27-Q1)."""
    if d is None:
        d = date.today()
    fy = get_fiscal_year(d)
    month = d.month
    # Q1: mars-mai, Q2: juin-août, Q3: sept-nov, Q4: déc-fév
    if month in (3, 4, 5):
        q = "Q1"
    elif month in (6, 7, 8):
        q = "Q2"
    elif month in (9, 10, 11):
        q = "Q3"
    else:
        q = "Q4"
    return f"{fy}-{q}"
