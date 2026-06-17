"""Synchronisation Azure DevOps pour ProjectMind."""
import base64
import os
import requests

ADO_ORG  = os.getenv("ADO_ORG", "Premiertech")
BASE_URL = f"https://dev.azure.com/{ADO_ORG}"


def _headers() -> dict:
    pat   = os.getenv("ADO_PAT", "")
    token = base64.b64encode(f":{pat}".encode()).decode()
    return {"Authorization": f"Basic {token}", "Accept": "application/json"}


def get_work_item(item_id: int) -> dict | None:
    """Recupere un work item ADO par son ID."""
    try:
        r = requests.get(
            f"{BASE_URL}/_apis/wit/workitems/{item_id}?api-version=7.1",
            headers=_headers(), timeout=10,
        )
        if r.status_code != 200:
            return None
        fields   = r.json().get("fields", {})
        assigned = fields.get("System.AssignedTo", {})
        return {
            "id":          item_id,
            "title":       fields.get("System.Title", ""),
            "state":       fields.get("System.State", ""),
            "type":        fields.get("System.WorkItemType", ""),
            "project":     fields.get("System.TeamProject", ""),
            "area_path":   fields.get("System.AreaPath", ""),
            "assigned_to": assigned.get("displayName", "") if isinstance(assigned, dict) else "",
        }
    except Exception:
        return None


def search_work_items(
    project:   str,
    area_path: str = "",
    state:     str = "",
    limit:     int = 50,
) -> list[dict]:
    """Recherche des work items ADO."""
    conditions = [f"[System.TeamProject] = '{project}'"]
    if area_path:
        conditions.append(f"[System.AreaPath] UNDER '{area_path}'")
    if state:
        conditions.append(f"[System.State] = '{state}'")

    wiql = {"query": (
        "SELECT [System.Id],[System.Title],[System.State],"
        "[System.WorkItemType],[System.AssignedTo] "
        f"FROM WorkItems WHERE {' AND '.join(conditions)} "
        "ORDER BY [System.ChangedDate] DESC"
    )}

    try:
        proj_enc = requests.utils.quote(project)
        r = requests.post(
            f"{BASE_URL}/{proj_enc}/_apis/wit/wiql?$top={limit}&api-version=7.1",
            headers={**_headers(), "Content-Type": "application/json"},
            json=wiql, timeout=10,
        )
        if r.status_code != 200:
            return []
        items = r.json().get("workItems", [])
        if not items:
            return []
        ids = ",".join(str(i["id"]) for i in items[:limit])
        r2 = requests.get(
            f"{BASE_URL}/_apis/wit/workitems?ids={ids}"
            "&fields=System.Id,System.Title,System.State,"
            "System.WorkItemType,System.AssignedTo,System.AreaPath"
            "&api-version=7.1",
            headers=_headers(), timeout=10,
        )
        if r2.status_code != 200:
            return []
        result = []
        for item in r2.json().get("value", []):
            f        = item.get("fields", {})
            assigned = f.get("System.AssignedTo", {})
            result.append({
                "id":          item["id"],
                "title":       f.get("System.Title", ""),
                "state":       f.get("System.State", ""),
                "type":        f.get("System.WorkItemType", ""),
                "area_path":   f.get("System.AreaPath", ""),
                "assigned_to": assigned.get("displayName", "") if isinstance(assigned, dict) else "",
            })
        return result
    except Exception:
        return []
