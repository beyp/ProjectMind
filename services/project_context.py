"""Project context builder for ProjectMindAgent."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from core.models import (
    get_project,
    get_tasks,
    get_categories,
    get_resources,
    get_project_assignments,
    get_milestones,
    get_risks,
    get_kpis,
    get_weekly_note,
    get_capacity_matrix,
)


@dataclass
class ProjectContext:
    project_id: int
    project: dict[str, Any] | None = None
    tasks: list[dict[str, Any]] = field(default_factory=list)
    categories: list[dict[str, Any]] = field(default_factory=list)
    resources: list[dict[str, Any]] = field(default_factory=list)
    assignments: list[dict[str, Any]] = field(default_factory=list)
    milestones: list[dict[str, Any]] = field(default_factory=list)
    risks: list[dict[str, Any]] = field(default_factory=list)
    kpis: list[dict[str, Any]] = field(default_factory=list)
    weekly_note: dict[str, Any] | None = None
    capacity: dict[str, Any] | None = None
    summary: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "project": self.project,
            "tasks": self.tasks,
            "categories": self.categories,
            "resources": self.resources,
            "assignments": self.assignments,
            "milestones": self.milestones,
            "risks": self.risks,
            "kpis": self.kpis,
            "weekly_note": self.weekly_note,
            "capacity": self.capacity,
            "summary": self.summary,
        }

    def to_prompt(self) -> str:
        project = self.project or {}

        lines = []
        lines.append("PROJECT")
        lines.append(f"- id: {self.project_id}")
        lines.append(f"- name: {project.get('name', '')}")
        lines.append(f"- language: {project.get('language', 'fr')}")
        lines.append(f"- go_live_date: {project.get('go_live_date', '')}")
        lines.append("")

        lines.append("SUMMARY")
        for key, value in self.summary.items():
            lines.append(f"- {key}: {value}")
        lines.append("")

        lines.append("CATEGORIES")
        for c in self.categories:
            lines.append(
                f"- #{c.get('id')} {c.get('name', '')} "
                f"/ {c.get('name_en', '')} color:{c.get('color', '')}"
            )
        lines.append("")

        lines.append("TASKS")
        for t in self.tasks[:80]:
            lines.append(
                f"- #{t.get('id')} {t.get('title', '')} "
                f"status:{t.get('status', '')} "
                f"cat:{t.get('category_id', '')} "
                f"start:{t.get('start_date', '')} "
                f"end:{t.get('end_date', '')} "
                f"progress:{t.get('progress', '')}"
            )
        lines.append("")

        lines.append("RESOURCES")
        for r in self.resources:
            lines.append(
                f"- #{r.get('id')} {r.get('acronym', '')} "
                f"name:{r.get('full_name', '')} "
                f"role:{r.get('role', '')} "
                f"max:{r.get('max_fraction', '')}"
            )
        lines.append("")

        lines.append("ASSIGNMENTS")
        for a in self.assignments[:80]:
            lines.append(
                f"- task:{a.get('task_id')} resource:{a.get('resource_id')} "
                f"hours:{a.get('hours', '')} fraction:{a.get('fraction', '')}"
            )
        lines.append("")

        lines.append("MILESTONES")
        for m in self.milestones:
            lines.append(
                f"- #{m.get('id')} {m.get('title', '')} "
                f"baseline:{m.get('baseline_date', '')} "
                f"current:{m.get('current_date', '')} "
                f"status:{m.get('status', '')}"
            )
        lines.append("")

        lines.append("RISKS_ISSUES_DECISIONS")
        for r in self.risks:
            lines.append(
                f"- #{r.get('id')} [{r.get('risk_type', '')}] "
                f"{r.get('description', '')} owner:{r.get('owner', '')}"
            )
        lines.append("")

        lines.append("KPIS")
        for k in self.kpis:
            lines.append(
                f"- {k.get('kpi_name', '')}: "
                f"prev:{k.get('prev_value', '')} curr:{k.get('curr_value', '')}"
            )
        lines.append("")

        return "\n".join(lines)


class ProjectContextBuilder:
    def build(
        self,
        project_id: int,
        *,
        year: int | None = None,
        include_capacity: bool = False,
    ) -> ProjectContext:
        project = get_project(project_id)

        ctx = ProjectContext(
            project_id=project_id,
            project=project,
            tasks=get_tasks(project_id),
            categories=get_categories(project_id),
            resources=get_resources(project_id),
            assignments=get_project_assignments(project_id),
            milestones=get_milestones(project_id),
            risks=get_risks(project_id),
            kpis=get_kpis(project_id),
            weekly_note=get_weekly_note(project_id),
        )

        if include_capacity and year:
            ctx.capacity = get_capacity_matrix(project_id, year)

        ctx.summary = self._build_summary(ctx)
        return ctx

    def _build_summary(self, ctx: ProjectContext) -> dict[str, Any]:
        open_risks = [
            r for r in ctx.risks
            if (r.get("risk_type") or "").upper() in ("R", "I")
        ]

        completed_tasks = [
            t for t in ctx.tasks
            if "termin" in (t.get("status") or "").lower()
            or "complete" in (t.get("status") or "").lower()
        ]

        return {
            "task_count": len(ctx.tasks),
            "category_count": len(ctx.categories),
            "resource_count": len(ctx.resources),
            "assignment_count": len(ctx.assignments),
            "milestone_count": len(ctx.milestones),
            "risk_issue_count": len(open_risks),
            "completed_task_count": len(completed_tasks),
        }