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

    # ── Resources ─────────────────────────────────────────────────────────────
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

    # ── Capacity planning (fraction par ressource par semaine calendaire) ─────
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

# ── CRUD Resources ────────────────────────────────────────────────────────────

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


# ── CRUD Capacity ─────────────────────────────────────────────────────────────

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
        INSERT INTO capacity (project_id, resource_id, task_id, category_id, year, week, fraction)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(resource_id, task_id, year, week)
        DO UPDATE SET fraction=excluded.fraction, category_id=excluded.category_id
    """, (project_id, resource_id, task_id, category_id, year, week, fraction))
    conn.commit()
    conn.close()


# ── CRUD Categories (update + reorder) ────────────────────────────────────────

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
    # Remettre les tâches sans catégorie
    conn.execute("UPDATE tasks SET category_id=NULL WHERE category_id=?", (category_id,))
    c = conn.cursor()
    c.execute("DELETE FROM categories WHERE id=?", (category_id,))
    deleted = c.rowcount > 0
    conn.commit()
    conn.close()
    return deleted


def reorder_categories(project_id: int, ordered_ids: list[int]) -> None:
    """Met à jour l ordre des catégories."""
    conn = get_db()
    for idx, cat_id in enumerate(ordered_ids):
        conn.execute(
            "UPDATE categories SET sort_order=? WHERE id=? AND project_id=?",
            (idx, cat_id, project_id)
        )
    conn.commit()
    conn.close()


# ── CRUD Tasks (update + delete) ──────────────────────────────────────────────

def delete_task(task_id: int) -> bool:
    conn = get_db()
    c    = conn.cursor()
    c.execute("DELETE FROM tasks WHERE id=?", (task_id,))
    deleted = c.rowcount > 0
    conn.commit()
    conn.close()
    return deleted


def get_task(task_id: int) -> dict | None:
    conn = get_db()
    row  = conn.execute("SELECT * FROM tasks WHERE id=?", (task_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


# ── Capacity helpers ──────────────────────────────────────────────────────────

def get_capacity_matrix(project_id: int, year: int) -> dict:
    """
    Retourne la matrice capacity sous forme :
    { resource_id: { week: fraction, ... }, ... }
    avec les totaux par ressource et par semaine.
    """
    from collections import defaultdict
    rows     = get_capacity(project_id, year)
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

    # Totaux par semaine
    week_totals: dict[int, float] = {}
    for week in weeks:
        week_totals[week] = sum(matrix.get(r["id"], {}).get(week, 0.0) for r in resources)

    return {
        "matrix":      {str(k): v for k, v in matrix.items()},
        "weeks":       weeks,
        "resources":   resources,
        "week_totals": week_totals,
    }
