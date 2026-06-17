"""Base de donnees SQLite pour ProjectMind."""
import os
from pathlib import Path
import aiosqlite

DB_PATH = Path(os.getenv("DB_PATH", "data/projectmind.db"))


async def init_db():
    """Cree les tables si elles n existent pas."""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    async with aiosqlite.connect(DB_PATH) as db:
        await db.executescript("""
            CREATE TABLE IF NOT EXISTS projects (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                language TEXT DEFAULT 'fr',
                go_live_date TEXT,
                ado_project TEXT,
                ado_area_path TEXT,
                description TEXT,
                fiscal_year_start_month INTEGER DEFAULT 3,
                created_at TEXT DEFAULT (datetime('now')),
                updated_at TEXT DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS categories (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
                name TEXT NOT NULL,
                color TEXT,
                "order" INTEGER DEFAULT 0,
                created_at TEXT DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS deliverables (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
                category_id INTEGER NOT NULL REFERENCES categories(id) ON DELETE CASCADE,
                title TEXT NOT NULL,
                description TEXT,
                status TEXT DEFAULT 'to_plan',
                due_date TEXT,
                completion_pct INTEGER DEFAULT 0,
                ado_item_id INTEGER,
                "order" INTEGER DEFAULT 0,
                created_at TEXT DEFAULT (datetime('now')),
                updated_at TEXT DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                deliverable_id INTEGER NOT NULL REFERENCES deliverables(id) ON DELETE CASCADE,
                title TEXT NOT NULL,
                description TEXT,
                status TEXT DEFAULT 'to_plan',
                start_date TEXT,
                end_date TEXT,
                completion_pct INTEGER DEFAULT 0,
                assignee TEXT,
                ado_item_id INTEGER,
                "order" INTEGER DEFAULT 0,
                created_at TEXT DEFAULT (datetime('now')),
                updated_at TEXT DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS weekly_reports (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
                report_date TEXT NOT NULL,
                summary TEXT,
                last_period_achievements TEXT,
                planned_activities TEXT,
                watch_items TEXT,
                risks_issues TEXT,
                kpi_cost TEXT DEFAULT 'G',
                kpi_scope TEXT DEFAULT 'G',
                kpi_schedule TEXT DEFAULT 'G',
                kpi_resources TEXT DEFAULT 'G',
                kpi_risk TEXT DEFAULT 'G',
                kpi_transition TEXT DEFAULT 'G',
                created_at TEXT DEFAULT (datetime('now'))
            );
        """)
        await db.commit()
