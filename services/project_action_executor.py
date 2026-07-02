"""Execute ProjectMind AI actions."""

from core.models import (
    get_db,
    create_task,
    update_task,
    create_category,
    update_resource,
    delete_resource,
    create_resource,
    get_resources,
    upsert_capacity,
    upsert_task_assignment,
    delete_task_assignment,
    color_for_role,
)


class ProjectActionExecutor:
    def execute(self, project_id: int, actions: list[dict]) -> list[dict]:
        executed = []

        for action in actions:
            atype = action.get("type", "")

            try:
                if atype == "message":
                    executed.append(action)

                elif atype == "create_task":
                    task_id = create_task(
                        project_id=project_id,
                        title=action.get("title", ""),
                        category_id=action.get("category_id"),
                        status=action.get("status", "A planifier"),
                        date_label=action.get("date_label", ""),
                        start_date=action.get("start_date", ""),
                        end_date=action.get("end_date", ""),
                        description=action.get("description", ""),
                        ado_item_id=action.get("ado_item_id"),
                    )
                    action["executed"] = True
                    action["id"] = task_id
                    executed.append(action)

                elif atype == "update_task":
                    update_task(int(action["id"]), **{
                        k: v for k, v in action.items()
                        if k not in ("type", "id")
                    })
                    action["executed"] = True
                    executed.append(action)

                elif atype == "delete_task":
                    action["executed"] = self._delete_task(action)
                    executed.append(action)

                elif atype == "create_category":
                    cat_id = create_category(
                        project_id=project_id,
                        name=action.get("name", ""),
                        name_en=action.get("name_en", ""),
                        color=action.get("color", "#041E42"),
                    )
                    action["executed"] = True
                    action["id"] = cat_id
                    executed.append(action)

                elif atype == "update_category":
                    self._update_category(action)
                    action["executed"] = True
                    executed.append(action)

                elif atype == "delete_category":
                    action["executed"] = self._delete_category(action)
                    executed.append(action)

                elif atype == "create_milestone":
                    mid = self._create_milestone(project_id, action)
                    action["executed"] = True
                    action["id"] = mid
                    executed.append(action)

                elif atype == "update_milestone":
                    self._update_milestone(action)
                    action["executed"] = True
                    executed.append(action)

                elif atype == "delete_milestone":
                    action["executed"] = self._delete_milestone(action)
                    executed.append(action)

                elif atype == "create_risk":
                    rid = self._create_risk(project_id, action)
                    action["executed"] = True
                    action["id"] = rid
                    executed.append(action)

                elif atype == "update_risk":
                    self._update_risk(action)
                    action["executed"] = True
                    executed.append(action)

                elif atype == "delete_risk":
                    action["executed"] = self._delete_risk(action)
                    executed.append(action)

                else:
                    action["executed"] = False
                    action["note"] = f"Unknown action type: {atype}"
                    executed.append(action)

            except Exception as exc:
                action["executed"] = False
                action["error"] = str(exc)
                executed.append(action)

        return executed

    def _create_milestone(self, project_id: int, action: dict) -> int:
        conn = get_db()
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO milestones (project_id, title, baseline_date, current_date, status)
            VALUES (?, ?, ?, ?, ?)
        """, (
            project_id,
            action.get("title", ""),
            action.get("baseline_date", ""),
            action.get("current_date", ""),
            action.get("status", "In progress"),
        ))
        mid = cur.lastrowid
        conn.commit()
        conn.close()
        return mid

    def _update_milestone(self, action: dict) -> None:
        conn = get_db()
        conn.execute("""
            UPDATE milestones
            SET title=?, baseline_date=?, current_date=?, status=?
            WHERE id=?
        """, (
            action.get("title", ""),
            action.get("baseline_date", ""),
            action.get("current_date", ""),
            action.get("status", "In progress"),
            int(action.get("id")),
        ))
        conn.commit()
        conn.close()

    def _delete_milestone(self, action: dict) -> bool:
        conn = get_db()
        cur = conn.cursor()
        cur.execute("DELETE FROM milestones WHERE id=?", (int(action.get("id")),))
        deleted = cur.rowcount > 0
        conn.commit()
        conn.close()
        return deleted

    def _create_risk(self, project_id: int, action: dict) -> int:
        conn = get_db()
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO risks (project_id, risk_type, description, owner)
            VALUES (?, ?, ?, ?)
        """, (
            project_id,
            action.get("risk_type", "R"),
            action.get("description", ""),
            action.get("owner", ""),
        ))
        rid = cur.lastrowid
        conn.commit()
        conn.close()
        return rid

    def _update_risk(self, action: dict) -> None:
        conn = get_db()
        conn.execute("""
            UPDATE risks
            SET risk_type=?, description=?, owner=?
            WHERE id=?
        """, (
            action.get("risk_type", "R"),
            action.get("description", ""),
            action.get("owner", ""),
            int(action.get("id")),
        ))
        conn.commit()
        conn.close()

    def _delete_risk(self, action: dict) -> bool:
        conn = get_db()
        cur = conn.cursor()
        cur.execute("DELETE FROM risks WHERE id=?", (int(action.get("id")),))
        deleted = cur.rowcount > 0
        conn.commit()
        conn.close()
        return deleted

    def _delete_task(self, action: dict) -> bool:
        conn = get_db()
        cur = conn.cursor()
        cur.execute("DELETE FROM tasks WHERE id=?", (int(action.get("id")),))
        deleted = cur.rowcount > 0
        conn.commit()
        conn.close()
        return deleted


    def _update_category(self, action: dict) -> None:
        conn = get_db()
        conn.execute("""
            UPDATE categories
            SET name=?, name_en=?, color=?
            WHERE id=?
        """, (
            action.get("name", ""),
            action.get("name_en", ""),
            action.get("color", "#041E42"),
            int(action.get("id")),
        ))
        conn.commit()
        conn.close()


    def _delete_category(self, action: dict) -> bool:
        conn = get_db()
        cur = conn.cursor()
        cur.execute("UPDATE tasks SET category_id=NULL WHERE category_id=?", (int(action.get("id")),))
        cur.execute("DELETE FROM categories WHERE id=?", (int(action.get("id")),))
        deleted = cur.rowcount > 0
        conn.commit()
        conn.close()
        return deleted