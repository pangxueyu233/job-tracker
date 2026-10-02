#!/usr/bin/env python3
"""给一个公司 careers 页面 URL，自动判断它用的招聘系统并给出 config.yaml 里要填的条目。
    python discover.py https://www.tempus.com/careers/
    python discover.py tempus grail guardant   # 也可以直接猜 slug
"""
import re
import sys

import requests

UA = {"User-Agent": "Mozilla/5.0"}


def probe(slug: str):
    hits = []
    r = requests.get(f"https://boards-api.greenhouse.io/v1/boards/{slug}/jobs", headers=UA, timeout=20)
    if r.ok and "jobs" in r.json():
        hits.append(f'  - {{type: greenhouse, name: "{slug}", slug: "{slug}"}}   # {r.json().get("meta", {}).get("total", "?")} jobs')
    r = requests.get(f"https://api.lever.co/v0/postings/{slug}?mode=json", headers=UA, timeout=20)
    if r.ok and isinstance(r.json(), list):
        hits.append(f'  - {{type: lever, name: "{slug}", slug: "{slug}"}}   # {len(r.json())} jobs')
    r = requests.get(f"https://api.ashbyhq.com/posting-api/job-board/{slug}", headers=UA, timeout=20)
    if r.ok and "jobs" in r.json():
        hits.append(f'  - {{type: ashby, name: "{slug}", slug: "{slug}"}}   # {len(r.json()["jobs"])} jobs')
    return hits


def from_url(url: str):
    try:
        html = requests.get(url, headers=UA, timeout=25).text
    except Exception as e:  # noqa: BLE001
        print(f"无法打开 {url}: {e}")
        return
    found = set()
    for m in re.finditer(r"boards\.greenhouse\.io/([a-z0-9_-]+)|job-boards\.greenhouse\.io/([a-z0-9_-]+)|greenhouse\.io/embed/job_board\?for=([a-z0-9_-]+)", html):
        found.add(("greenhouse", next(g for g in m.groups() if g)))
    for m in re.finditer(r"jobs\.lever\.co/([a-z0-9_-]+)", html):
        found.add(("lever", m.group(1)))
    for m in re.finditer(r"jobs\.ashbyhq\.com/([a-z0-9_-]+)", html):
        found.add(("ashby", m.group(1)))
    for m in re.finditer(r"https?://([a-z0-9-]+)\.(wd\d+)\.myworkdayjobs\.com/(?:[a-z]{2}-[A-Z]{2}/)?([A-Za-z0-9_-]+)", html):
        found.add(("workday", m.group(1), m.group(2), m.group(3)))
    if not found:
        print("页面里没找到 Greenhouse / Lever / Ashby / Workday 的痕迹（可能是 iframe 或自建系统）。")
        print("可以试试：python discover.py <公司名的小写 slug>")
        return
    print("在页面里找到：")
    for f in sorted(found):
        if f[0] == "workday":
            tenant, wd, site = f[1:]
            print(f'  - type: workday\n    name: "{tenant}"\n    host: "https://{tenant}.{wd}.myworkdayjobs.com"\n    tenant: "{tenant}"\n    site: "{site}"\n    queries: ["computational biology", "bioinformatics"]')
        else:
            print(f'  - {{type: {f[0]}, name: "{f[1]}", slug: "{f[1]}"}}')


if __name__ == "__main__":
    for arg in sys.argv[1:]:
        print(f"== {arg}")
        if arg.startswith("http"):
            from_url(arg)
        else:
            hits = probe(arg)
            print("\n".join(hits) if hits else "  没有命中（试试别的 slug 拼法，或用 careers 页面 URL）")
