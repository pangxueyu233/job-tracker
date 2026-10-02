"""各招聘来源的抓取器。每个函数返回 list[dict]，字段统一为：
    title, org, location, url, description, posted, deadline, source, kind
kind ∈ {"faculty", "industry"}（industry 来源直接标 industry；学术来源在 filters 里再判断）
"""
from __future__ import annotations

import csv
import html
import io
import logging
import re
import time
import xml.etree.ElementTree as ET
from datetime import datetime, timezone

import requests

log = logging.getLogger("tracker")

NS = {
    "rss1": "http://purl.org/rss/1.0/",
    "dc": "http://purl.org/dc/elements/1.1/",
    "content": "http://purl.org/rss/1.0/modules/content/",
    "rdf": "http://www.w3.org/1999/02/22-rdf-syntax-ns#",
}

_TAG_RE = re.compile(r"<[^>]+>")
_WS_RE = re.compile(r"\s+")


def strip_html(s: str | None) -> str:
    if not s:
        return ""
    s = html.unescape(s)
    s = _TAG_RE.sub(" ", s)
    return _WS_RE.sub(" ", s).strip()


class Http:
    def __init__(self, user_agent: str, timeout: int = 30, pause: float = 0.6):
        self.s = requests.Session()
        self.s.headers.update({
            "User-Agent": user_agent, "Accept": "*/*",
            "Accept-Language": "en-US,en;q=0.9", "Accept-Encoding": "gzip, deflate, br",
        })
        self.timeout = timeout
        self.pause = pause

    def get(self, url, retries: int = 2, **kw):
        last = None
        for i in range(retries + 1):
            time.sleep(self.pause * (1 + 3 * i))
            try:
                r = self.s.get(url, timeout=self.timeout, **kw)
                if r.status_code in (429, 500, 502, 503, 504) and i < retries:
                    last = requests.HTTPError(f"{r.status_code} for {url}")
                    continue
                r.raise_for_status()
                return r
            except requests.RequestException as e:
                last = e
        raise last

    def post_json(self, url, payload, **kw):
        time.sleep(self.pause)
        r = self.s.post(url, json=payload, timeout=self.timeout,
                        headers={"Accept": "application/json", "Content-Type": "application/json"}, **kw)
        r.raise_for_status()
        return r.json()


def _parse_date(s: str | None) -> str:
    """尽量把各种日期字符串转成 YYYY-MM-DD；失败返回空串。"""
    if not s:
        return ""
    s = s.strip()
    fmts = [
        "%a, %d %b %Y %H:%M:%S %z", "%a, %d %b %Y %H:%M:%S %Z",
        "%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%dT%H:%M:%S.%f%z", "%Y-%m-%dT%H:%M:%SZ",
        "%Y-%m-%d", "%d %b %Y", "%B %d, %Y", "%b %d, %Y",
    ]
    s2 = re.sub(r"([+-]\d\d):(\d\d)$", r"\1\2", s)  # 2026-10-01T15:31:18-04:00 -> -0400
    s3 = re.sub(r"\s+[A-Z]{2,4}$", "", s)             # "... 01:32:04 EDT" -> 去掉时区缩写
    fmts.append("%a, %d %b %Y %H:%M:%S")
    for f in fmts:
        for cand in (s, s2, s3):
            try:
                return datetime.strptime(cand, f).date().isoformat()
            except ValueError:
                pass
    m = re.search(r"(\d{4}-\d{2}-\d{2})", s)
    return m.group(1) if m else ""


def _today() -> str:
    return datetime.now(timezone.utc).date().isoformat()


# ---------------------------------------------------------------- RSS helpers

_BAD_XML_CHARS = re.compile("[\x00-\x08\x0b\x0c\x0e-\x1f]")
_BARE_AMP = re.compile(r"&(?!(?:[a-zA-Z]+|#\d+|#x[0-9a-fA-F]+);)")


def _xml_root(text: str):
    """容错解析：去掉非法控制字符、修复裸 &；不是 XML 时抛出带内容片段的错误。"""
    if isinstance(text, bytes):
        text = text.decode("utf-8", "replace")
    head = text.lstrip()[:200].lower()
    if not head.startswith("<?xml") and not head.startswith("<rss") and not head.startswith("<rdf"):
        raise ValueError(f"not XML (got: {text.strip()[:120]!r})")
    text = _BARE_AMP.sub("&amp;", _BAD_XML_CHARS.sub("", text))
    return ET.fromstring(text.encode("utf-8"))


def _rss2_items(xml_text: str):
    root = _xml_root(xml_text)
    for item in root.iter("item"):
        yield {
            "title": html.unescape((item.findtext("title") or "").strip()),
            "link": (item.findtext("link") or "").strip(),
            "description": item.findtext("description") or "",
            "pubDate": item.findtext("pubDate") or item.findtext(f"{{{NS['dc']}}}date") or "",
        }


# ---------------------------------------------------------------- academic

def fetch_madgex_rss(http: Http, src: dict) -> list[dict]:
    """Science Careers / Nature Careers（Madgex 平台）RSS。"""
    out, seen = [], set()
    for q in src.get("queries", []):
        params = {"keywords": q}
        if src.get("country"):
            params["countrycode"] = src["country"]
        try:
            r = http.get(src["base"], params=params)
            for it in _rss2_items(r.text):
                if not it["link"] or it["link"] in seen:
                    continue
                seen.add(it["link"])
                # Madgex：title = "Org: Position"；description = "Salary:\n\nOrg:\n\n摘要\n地点\n"
                title, org = it["title"], ""
                if ": " in title:
                    org, title = title.split(": ", 1)
                lines = [l.strip() for l in html.unescape(it["description"]).splitlines() if l.strip()]
                loc = lines[-1] if lines and len(lines[-1]) < 60 else ""
                desc = strip_html(it["description"])
                out.append({
                    "title": title.strip(), "org": org.strip(), "location": loc, "url": it["link"].split("?TrackID")[0],
                    "description": desc, "posted": _parse_date(it["pubDate"]), "deadline": "",
                    "source": src["name"], "kind": "faculty",
                })
        except Exception as e:  # noqa: BLE001
            log.warning("%s [%s] failed: %s", src["name"], q, e)
    log.info("%s: %d items", src["name"], len(out))
    return out


BLOCK_MARKERS = ("Incapsula", "Pardon Our Interruption", "_Incapsula_Resource", "Access Denied", "captcha")


def _looks_blocked(text: str) -> bool:
    head = text[:1500]
    return any(m.lower() in head.lower() for m in BLOCK_MARKERS)


def fetch_higheredjobs_rss(http: Http, src: dict) -> list[dict]:
    """HigherEdJobs 分类 RSS：title = 职位；description = "机构 (城市, 州)"，没有正文。
    站点有 Incapsula 反爬，请求间隔必须够长：分类 RSS 之间停 feed_pause 秒，分类顺序每天轮换，
    一旦检测到拦截页就停止本次对该站点的所有请求。随后对"标题像 faculty、本地没见过"的最新条目
    补抓详情页拿正文（每次 detail_budget 条，间隔 detail_pause 秒）。"""
    out, seen = [], set()
    known = src.get("_known_urls", set())
    fac_words = [w.lower() for w in src.get("_faculty_words", ["professor", "faculty", "tenure"])]
    feed_pause = float(src.get("feed_pause", 5))
    detail_pause = float(src.get("detail_pause", 6))
    detail_budget = int(src.get("detail_budget", 12))
    cats = list(src.get("categories", {}).items())
    if cats:  # 按日期轮换起点，几天内把所有分类都覆盖到
        k = datetime.now().timetuple().tm_yday % len(cats)
        cats = cats[k:] + cats[:k]
    blocked = False
    for i, (cat_id, cat_name) in enumerate(cats):
        if i:
            time.sleep(feed_pause)
        url = f"https://www.higheredjobs.com/rss/categoryFeed.cfm?catID={cat_id}"
        try:
            r = http.get(url, headers={"Accept": "application/rss+xml, application/xml, text/xml, */*"})
            if _looks_blocked(r.text):
                log.warning("HigherEdJobs: 被反爬拦截（cat %s），本次停止访问该站点；其余分类明天轮到", cat_id)
                blocked = True
                break
            for it in _rss2_items(r.text):
                link = it["link"].split("&utm")[0]
                if not link or link in seen:
                    continue
                seen.add(link)
                meta = strip_html(it["description"])
                org, loc = meta, ""
                m = re.match(r"(.*?)\s*\(([^()]*)\)\s*$", meta)
                if m:
                    org, loc = m.group(1).strip(), m.group(2).strip()
                out.append({
                    "title": it["title"].strip(), "org": org, "location": loc, "url": link,
                    "description": f"[{cat_name}] {meta}", "posted": _parse_date(it["pubDate"]),
                    "deadline": "", "source": src["name"], "kind": "faculty",
                })
        except Exception as e:  # noqa: BLE001
            log.warning("HigherEdJobs cat %s failed: %s", cat_id, e)
    # 详情页：新出现、标题像 faculty 的条目，最新的优先
    cands = [j for j in out if j["url"] not in known and any(w in j["title"].lower() for w in fac_words)]
    cands.sort(key=lambda j: j.get("posted", ""), reverse=True)
    n_detail = 0
    for j in cands:
        if blocked or n_detail >= detail_budget:
            break
        time.sleep(detail_pause)
        try:
            page = http.get(j["url"]).text
            if _looks_blocked(page):
                log.warning("HigherEdJobs: 详情页被拦截，停止补抓")
                blocked = True
                break
            i = page.find('id="jobDesc"')
            body = strip_html(page[i: i + 12000]) if i >= 0 else ""
            if len(body) > 200:
                j["description"] += " — " + body[:2500]
                n_detail += 1
        except Exception as e:  # noqa: BLE001
            log.debug("HigherEdJobs detail failed %s: %s", j["url"], e)
    log.info("%s: %d items (%d 条补抓了正文)", src["name"], len(out), n_detail)
    return out


def fetch_ajo_rss(http: Http, src: dict) -> list[dict]:
    """AcademicJobsOnline 全站 RSS 1.0（RDF）。"""
    out = []
    try:
        r = http.get(src["url"])
        root = _xml_root(r.text)
        for item in root.iter(f"{{{NS['rss1']}}}item"):
            title = html.unescape((item.findtext(f"{{{NS['rss1']}}}title") or "").strip())
            link = (item.findtext(f"{{{NS['rss1']}}}link") or item.get(f"{{{NS['rdf']}}}about") or "").strip()
            link = link.replace("?rss", "")
            desc = strip_html(item.findtext(f"{{{NS['rss1']}}}description") or
                              item.findtext(f"{{{NS['content']}}}encoded") or "")
            date = item.findtext(f"{{{NS['dc']}}}date") or ""
            # 链接形如 https://academicjobsonline.org/ajo/Duke/Biology/32900
            org, dept = "", ""
            m = re.search(r"academicjobsonline\.org/ajo/([^/]+)/([^/]+)/\d+", link)
            if m:
                org = requests.utils.unquote(m.group(1))
                dept = requests.utils.unquote(m.group(2))
            # AJO 标题常是 "[Org] Position Title" 或 "Position Title"
            t = re.sub(r"^\[[^\]]*\]\s*", "", title)
            loc = ""
            m = re.search(r"\(([A-Za-z .]+,\s*[A-Z]{2}(?:,\s*US)?)\)", desc)
            if m:
                loc = m.group(1)
            out.append({
                "title": t, "org": org + (f" — {dept}" if dept else ""), "location": loc, "url": link,
                "description": desc, "posted": _parse_date(date), "deadline": _find_deadline(desc),
                "source": src["name"], "kind": "faculty",
            })
    except Exception as e:  # noqa: BLE001
        log.warning("AJO failed: %s", e)
    log.info("%s: %d items", src["name"], len(out))
    return out


def enrich_ajo(http: Http, job: dict) -> bool:
    """AJO 的 RSS 没有地点/截止日期：对保留下来的岗位补抓详情页。返回是否成功。"""
    try:
        page = http.get(job["url"]).text
    except Exception as e:  # noqa: BLE001
        log.debug("AJO detail failed %s: %s", job["url"], e)
        return False
    ok = False
    m = re.search(r"Position Location:</b></div>\s*<div[^>]*>(.*?)</div>", page, re.S)
    if m:
        job["location"] = re.sub(r"\s*\[.*$", "", strip_html(m.group(1))).strip()
        ok = True
    m = re.search(r"Appl Deadline:</b></div>\s*<div[^>]*>(.*?)</div>", page, re.S)
    if m:
        txt = strip_html(m.group(1)).strip()
        dates = re.findall(r"(\d{4}/\d{2}/\d{2})", txt)
        if dates:
            if txt.startswith("("):
                job["deadline"] = dates[-1].replace("/", "-") + " (listed until)"
            else:
                job["deadline"] = dates[0].replace("/", "-")
    m = re.search(r"Position Type:</b></div>\s*<div[^>]*>(.*?)</div>", page, re.S)
    if m and not job.get("description", "").startswith("["):
        job["description"] = f"[{strip_html(m.group(1))}] " + job.get("description", "")
    return ok


def enrich_kept(cfg: dict, kept: list[dict], known_urls: set) -> None:
    """分类之后、入库之前，对保留下来的岗位补抓详情（目前：AJO 地点/截止日期）。"""
    o = cfg["output"]
    http = Http(o.get("user_agent", "Mozilla/5.0"), o.get("request_timeout", 30), pause=1.0)
    budget = int(o.get("ajo_detail_budget", 40))
    n = 0
    for j in kept:
        if budget <= 0:
            break
        if j.get("source") == "AcademicJobsOnline" and not j.get("location") and j["url"] not in known_urls:
            budget -= 1
            n += enrich_ajo(http, j)
    if n:
        log.info("AJO: %d 条补抓到地点/截止日期", n)


def _find_deadline(desc: str) -> str:
    m = re.search(r"[Dd]eadline\s*:?\s*([A-Za-z]{3,9}\.? \d{1,2},? \d{4}|\d{4}-\d{2}-\d{2})", desc)
    return _parse_date(m.group(1).replace(".", "")) if m else ""


def fetch_gsheet_csv(http: Http, src: dict) -> list[dict]:
    if not src.get("url"):
        return []
    out = []
    try:
        r = http.get(src["url"])
        cols = src.get("columns", {})
        reader = csv.DictReader(io.StringIO(r.text))
        for row in reader:
            title = row.get(cols.get("title", "Position"), "") or ""
            if not title.strip():
                continue
            out.append({
                "title": title.strip(), "org": row.get(cols.get("org", "Institution"), "") or "",
                "location": row.get(cols.get("location", "Location"), "") or "",
                "url": row.get(cols.get("url", "Link"), "") or "",
                "description": " | ".join(f"{k}: {v}" for k, v in row.items() if v),
                "posted": "", "deadline": _parse_date(row.get(cols.get("deadline", "Deadline"), "")),
                "source": src["name"], "kind": "faculty",
            })
    except Exception as e:  # noqa: BLE001
        log.warning("gsheet failed: %s", e)
    log.info("%s: %d items", src["name"], len(out))
    return out


# ---------------------------------------------------------------- industry

def fetch_greenhouse(http: Http, src: dict) -> list[dict]:
    url = f"https://boards-api.greenhouse.io/v1/boards/{src['slug']}/jobs?content=true"
    out = []
    try:
        data = http.get(url).json()
        for j in data.get("jobs", []):
            depts = ", ".join(d.get("name", "") for d in (j.get("departments") or []) if d)
            out.append({
                "title": j.get("title", ""), "org": src["name"],
                "location": (j.get("location") or {}).get("name", ""),
                "url": j.get("absolute_url", ""), "description": strip_html(j.get("content", "")),
                "posted": _parse_date(j.get("first_published") or j.get("updated_at")),
                "deadline": "", "source": "Greenhouse", "kind": "industry", "department": depts,
            })
    except Exception as e:  # noqa: BLE001
        log.warning("Greenhouse %s failed: %s", src["name"], e)
    log.info("%s: %d items", src["name"], len(out))
    return out


def fetch_lever(http: Http, src: dict) -> list[dict]:
    url = f"https://api.lever.co/v0/postings/{src['slug']}?mode=json"
    out = []
    try:
        for j in http.get(url).json():
            cats = j.get("categories") or {}
            ts = j.get("createdAt")
            posted = datetime.fromtimestamp(ts / 1000, tz=timezone.utc).date().isoformat() if ts else ""
            sr = j.get("salaryRange") or {}
            sal = f"{sr.get('currency','')} {sr.get('min','')}-{sr.get('max','')} {sr.get('interval','')}".strip() if sr.get("max") else ""
            out.append({
                "salary": sal, "department": cats.get("team", "") or cats.get("department", ""),
                "title": j.get("text", ""), "org": src["name"], "location": cats.get("location", ""),
                "url": j.get("hostedUrl", ""), "description": j.get("descriptionPlain", "") or strip_html(j.get("description", "")),
                "posted": posted, "deadline": "", "source": "Lever", "kind": "industry",
            })
    except Exception as e:  # noqa: BLE001
        log.warning("Lever %s failed: %s", src["name"], e)
    log.info("%s: %d items", src["name"], len(out))
    return out


def fetch_ashby(http: Http, src: dict) -> list[dict]:
    url = f"https://api.ashbyhq.com/posting-api/job-board/{src['slug']}?includeCompensation=true"
    out = []
    try:
        r = http.get(url, headers={"Accept": "application/json"})
        try:
            jobs = r.json().get("jobs", [])
        except ValueError:
            raise ValueError(f"非 JSON 响应（HTTP {r.status_code}）: {r.text[:120]!r}")
        for j in jobs:
            comp = (j.get("compensation") or {}).get("compensationTierSummary") or ""
            out.append({
                "title": j.get("title", ""), "org": src["name"], "location": j.get("location", ""),
                "url": j.get("jobUrl", ""), "description": j.get("descriptionPlain", "") or strip_html(j.get("descriptionHtml", "")),
                "posted": _parse_date(j.get("publishedAt")), "deadline": "", "source": "Ashby", "kind": "industry",
                "salary": comp, "department": j.get("department", "") or j.get("team", ""),
            })
    except Exception as e:  # noqa: BLE001
        log.warning("Ashby %s failed: %s", src["name"], e)
    log.info("%s: %d items", src["name"], len(out))
    return out


def fetch_workday(http: Http, src: dict, max_detail: int = 40) -> list[dict]:
    """Workday：列表接口不含描述，先按 searchText 搜，再对每个岗位拉详情（限量）。"""
    host, tenant, site = src["host"].rstrip("/"), src["tenant"], src["site"]
    list_url = f"{host}/wday/cxs/{tenant}/{site}/jobs"
    # Workday 的 cxs 接口要求先有会话 cookie，先 GET 一次站点首页
    try:
        http.get(f"{host}/{site}")
    except Exception as e:  # noqa: BLE001
        log.warning("Workday %s: warm-up failed (%s), continuing", src["name"], e)
    found: dict[str, dict] = {}
    for q in src.get("queries", ["computational biology"]):
        offset = 0
        while True:
            try:
                data = http.post_json(list_url, {"appliedFacets": {}, "limit": 20, "offset": offset, "searchText": q})
            except Exception as e:  # noqa: BLE001
                log.warning("Workday %s [%s] failed: %s", src["name"], q, e)
                break
            posts = data.get("jobPostings", [])
            for p in posts:
                path = p.get("externalPath", "")
                if path and path not in found:
                    found[path] = p
            offset += 20
            if not posts or offset >= min(data.get("total", 0), 100):
                break
    out = []
    for i, (path, p) in enumerate(found.items()):
        desc = ""
        if i < max_detail:
            try:
                d = http.get(f"{host}/wday/cxs/{tenant}/{site}{path}").json()
                jp = d.get("jobPostingInfo", {})
                desc = strip_html(jp.get("jobDescription", ""))
                posted = _parse_date(jp.get("startDate") or jp.get("postedOn"))
                locs = [jp.get("location", "")] + list(jp.get("additionalLocations") or [])
                loc = "; ".join(l for l in locs if l) or p.get("locationsText", "")
            except Exception:  # noqa: BLE001
                posted, loc = "", p.get("locationsText", "")
        else:
            posted, loc = "", p.get("locationsText", "")
        out.append({
            "title": p.get("title", ""), "org": src["name"], "location": loc,
            "url": f"{host}/{site}{path}", "description": desc, "posted": posted, "deadline": "",
            "source": "Workday", "kind": "industry",
        })
    log.info("%s: %d items", src["name"], len(out))
    return out


FETCHERS = {
    "madgex_rss": fetch_madgex_rss,
    "higheredjobs_rss": fetch_higheredjobs_rss,
    "ajo_rss": fetch_ajo_rss,
    "gsheet_csv": fetch_gsheet_csv,
    "greenhouse": fetch_greenhouse,
    "lever": fetch_lever,
    "ashby": fetch_ashby,
    "workday": fetch_workday,
}


def fetch_all(cfg: dict, known_urls: set | None = None) -> list[dict]:
    o = cfg["output"]
    http = Http(o.get("user_agent", "Mozilla/5.0"), o.get("request_timeout", 30))
    jobs: list[dict] = []
    for src in cfg.get("academic_sources", []) + cfg.get("industry_sources", []):
        if not src.get("enabled", True):
            continue
        src["_known_urls"] = known_urls or set()
        src["_faculty_words"] = cfg.get("profile", {}).get("faculty_title_words", [])
        fn = FETCHERS.get(src["type"])
        if not fn:
            log.warning("unknown source type %s", src["type"])
            continue
        try:
            jobs.extend(fn(http, src))
        except Exception as e:  # noqa: BLE001
            log.error("source %s crashed: %s", src.get("name"), e)
    return jobs
