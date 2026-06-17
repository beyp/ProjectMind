"""Modeles de donnees ProjectMind."""
from datetime import datetime
from enum import Enum
from typing import Optional
from pydantic import BaseModel


class Language(str, Enum):
    FR = "fr"
    EN = "en"


class Status(str, Enum):
    IN_PROGRESS = "in_progress"
    DONE        = "done"
    TO_PLAN     = "to_plan"
    BLOCKED     = "blocked"
    LATE        = "late"
    CANCELLED   = "cancelled"


STATUS_LABELS = {
    "fr": {
        Status.IN_PROGRESS: "En cours",
        Status.DONE:        "Realise",
        Status.TO_PLAN:     "A planifier",
        Status.BLOCKED:     "Bloque",
        Status.LATE:        "En retard",
        Status.CANCELLED:   "Annule",
    },
    "en": {
        Status.IN_PROGRESS: "In Progress",
        Status.DONE:        "Done",
        Status.TO_PLAN:     "To Plan",
        Status.BLOCKED:     "Blocked",
        Status.LATE:        "Late",
        Status.CANCELLED:   "Cancelled",
    },
}

STATUS_COLORS = {
    Status.IN_PROGRESS: "#FFA500",
    Status.DONE:        "#4CAF50",
    Status.TO_PLAN:     "#2196F3",
    Status.BLOCKED:     "#F44336",
    Status.LATE:        "#E91E63",
    Status.CANCELLED:   "#9E9E9E",
}

STATUS_BG_COLORS = {
    Status.IN_PROGRESS: "#FFF3E0",
    Status.DONE:        "#E8F5E9",
    Status.TO_PLAN:     "#E3F2FD",
    Status.BLOCKED:     "#FFEBEE",
    Status.LATE:        "#FCE4EC",
    Status.CANCELLED:   "#F5F5F5",
}


class KPIStatus(str, Enum):
    GREEN  = "G"
    YELLOW = "Y"
    RED    = "R"


class ProjectCreate(BaseModel):
    name:                    str
    language:                Language = Language.FR
    go_live_date:            Optional[str] = None
    ado_project:             Optional[str] = None
    ado_area_path:           Optional[str] = None
    description:             Optional[str] = None
    fiscal_year_start_month: int = 3


class CategoryCreate(BaseModel):
    project_id: int
    name:       str
    order:      int = 0
    color:      Optional[str] = None


class DeliverableCreate(BaseModel):
    project_id:     int
    category_id:    int
    title:          str
    description:    Optional[str] = None
    status:         Status = Status.TO_PLAN
    due_date:       Optional[str] = None
    completion_pct: int = 0
    ado_item_id:    Optional[int] = None
    order:          int = 0


class TaskCreate(BaseModel):
    deliverable_id: int
    title:          str
    description:    Optional[str] = None
    status:         Status = Status.TO_PLAN
    start_date:     Optional[str] = None
    end_date:       Optional[str] = None
    completion_pct: int = 0
    assignee:       Optional[str] = None
    ado_item_id:    Optional[int] = None
    order:          int = 0


class WeeklyReportCreate(BaseModel):
    project_id:               int
    report_date:              str
    summary:                  Optional[str] = None
    last_period_achievements: Optional[str] = None
    planned_activities:       Optional[str] = None
    watch_items:              Optional[str] = None
    risks_issues:             Optional[str] = None
    kpi_cost:       KPIStatus = KPIStatus.GREEN
    kpi_scope:      KPIStatus = KPIStatus.GREEN
    kpi_schedule:   KPIStatus = KPIStatus.GREEN
    kpi_resources:  KPIStatus = KPIStatus.GREEN
    kpi_risk:       KPIStatus = KPIStatus.GREEN
    kpi_transition: KPIStatus = KPIStatus.GREEN
