"""jobs.json 的读写与合并：记录 first_seen / last_seen，保留用户标记。"""
from __future__ import annotations

import hashlib
import json
import os
import re
from datetime import date, datetime, timedelta


def job_id(job: dict) -> str:
    url = (job.get("url") or "").split("?utm")[0].rstrip("/").lower()
    key = url or f"{job.get('org','')}|{job.get('title','')}".lower()
    key = re.sub(r"\s+", " ", key)
    return hashlib.sha1(key.encode()).hexdigest()[:12]


def load(path: str) -> dict:
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    return {"jobs": {}, "runs": []}


def save(path: str, data: dict) -> None:
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=1)


def merge(data: dict, fresh: list[dict], stale_days: int = 14) -> dict:
    today = date.today().isoformat()
    jobs = data.setdefault("jobs", {})
    seen_ids = set()
    n_new = 0
    for j in fresh:
        jid = job_id(j)
        seen_ids.add(jid)
        if jid in jobs:
            old = jobs[jid]
            old.update({k: v for k, v in j.items() if v})  # 用新抓到的非空字段覆盖
            old["last_seen"] = today
        else:
            j = dict(j)
            j.update({"id": jid, "first_seen": today, "last_seen": today, "status": ""})
            jobs[jid] = j
            n_new += 1
    # 没再抓到的岗位：超过 stale_days 标记为 closed（不删，保留申请记录）
    cutoff = (date.today() - timedelta(days=stale_days)).isoformat()
    for jid, j in jobs.items():
        if jid not in seen_ids and j.get("last_seen", today) < cutoff:
            j["closed"] = True
        elif jid in seen_ids:
            j.pop("closed", None)
    data.setdefault("runs", []).append({"at": datetime.now().isoformat(timespec="minutes"),
                                        "fetched": len(fresh), "new": n_new, "total": len(jobs)})
    data["runs"] = data["runs"][-60:]
    return data


def apply_status_file(data: dict, path: str) -> None:
    """status.json：{job_id: {"status": "applied", "note": "..."}}，由网页导出后放回仓库即可同步。"""
    if not os.path.exists(path):
        return
    with open(path, encoding="utf-8") as f:
        st = json.load(f)
    for jid, v in st.items():
        if jid in data["jobs"]:
            data["jobs"][jid]["status"] = v.get("status", "")
            data["jobs"][jid]["note"] = v.get("note", "")
