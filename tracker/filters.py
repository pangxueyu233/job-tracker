"""关键词打分与分类。"""
from __future__ import annotations

import re

US_HINTS = re.compile(
    r"\b(USA?|United States|U\.S\.)\b|\((?:US|USA)\)|"
    r"\b(AL|AK|AZ|AR|CA|CO|CT|DE|FL|GA|HI|ID|IL|IN|IA|KS|KY|LA|ME|MD|MA|MI|MN|MS|MO|MT|NE|NV|NH|NJ|NM|NY|NC|ND|OH|OK|OR|PA|RI|SC|SD|TN|TX|UT|VT|VA|WA|WV|WI|WY|DC)\b|"
    r"\b(Alabama|Alaska|Arizona|Arkansas|California|Colorado|Connecticut|Delaware|Florida|Georgia|Hawaii|Idaho|Illinois|Indiana|Iowa|Kansas|Kentucky|Louisiana|Maine|Maryland|Massachusetts|Michigan|Minnesota|Mississippi|Missouri|Montana|Nebraska|Nevada|New Hampshire|New Jersey|New Mexico|New York|North Carolina|North Dakota|Ohio|Oklahoma|Oregon|Pennsylvania|Rhode Island|South Carolina|South Dakota|Tennessee|Texas|Utah|Vermont|Virginia|Washington|West Virginia|Wisconsin|Wyoming)\b"
)
NON_US_HINTS = re.compile(
    r"\b(United Kingdom|UK|England|Scotland|Germany|France|Switzerland|Netherlands|Sweden|Denmark|Norway|Finland|"
    r"Spain|Italy|Austria|Belgium|Ireland|Canada|Australia|New Zealand|Japan|China|Singapore|Korea|India|Israel|"
    r"Saudi|Qatar|UAE|Hong Kong|Taiwan|Brazil|Mexico|Portugal|Poland|Czech|Hungary|Turkey|Bangalore|Bangladesh|"
    r"Basel|Zurich|Z\u00fcrich|Geneva|London|Oxford|Paris|Berlin|Munich|Heidelberg|Toronto|Vancouver|Montreal|Tokyo|Shanghai|Beijing|"
    r"Shenzhen|Sydney|Melbourne|Copenhagen|Stockholm|Amsterdam|Dublin|Tel Aviv|Hyderabad|Mumbai|Great Abington|Woodlands|Seoul)\b"
)


# 薪资：$150,000 - $200,000 / $150K–$200K / 150,000 - 200,000 USD / £60,000 / CHF 120'000
_SAL_RE = re.compile(
    r"(?:(?:USD|US\$|\$|£|€|CHF|SGD)\s?\d{2,3}(?:[,.']\d{3})?(?:\s?[kK])?(?:\s?(?:-|–|—|to)\s?(?:USD|US\$|\$|£|€|CHF|SGD)?\s?\d{2,3}(?:[,.']\d{3})?(?:\s?[kK])?)?"
    r"|\d{2,3}(?:,\d{3})(?:\s?(?:-|–|—|to)\s?\d{2,3}(?:,\d{3}))?\s?(?:USD|dollars|per year|/year|annually))"
    r"(?:\s?(?:per year|/year|/yr|annually|per annum|p\.a\.|a year))?", re.I)
_SAL_HINT = re.compile(r"salary|pay range|base pay|compensation|annual|per year|remuneration|stipend|rate", re.I)


def extract_salary(text: str) -> str:
    """从正文里抓薪资区间；优先取附近有 salary/pay 字样的匹配。"""
    if not text:
        return ""
    cands = []
    for m in _SAL_RE.finditer(text):
        s = m.group(0).strip()
        digits = re.findall(r"\d+", s.replace(",", "").replace("'", ""))
        try:
            nums = [int(d) for d in digits]
        except ValueError:
            continue
        big = max(nums) if nums else 0
        if "k" in s.lower() or "K" in s:
            big *= 1000 if big < 1000 else 1
        if big < 30000:  # 过滤掉 $500 bonus / 年份 等
            continue
        ctx = text[max(0, m.start() - 80): m.end() + 40]
        cands.append((bool(_SAL_HINT.search(ctx)), "-" in s or "–" in s or "to" in s.lower(), s))
    if not cands:
        return ""
    cands.sort(key=lambda c: (c[0], c[1]), reverse=True)
    return cands[0][2][:40]


# 公司岗位的职能分类：按顺序匹配，先标题后正文
INDUSTRY_CATEGORIES = [
    ("产品/市场/商务", r"marketing|business development|\bsales\b|commercial|product manager|product management|customer|account manager|market access"),
    ("项目/运营/管理", r"program manager|project manager|operations|portfolio lead|scientific program|chief of staff|alliance management"),
    ("临床/转化/医学", r"clinical|translational|biomarker|medical affairs|patient|pharmacovigilance|regulatory|diagnostic|companion dx|real[- ]world"),
    ("药物设计/化学/蛋白", r"medicinal chem|drug design|cheminformatic|protein design|antibody|small molecule|structural biol|molecular design|nucleic acid design|developability|synthesis"),
    ("研发·计算/生信/ML", r"computational|bioinformatic|machine learning|\bml\b|\bai\b|data scien|statistical genetic|genomic|multiomic|multi-omic|algorithm|foundation model|biostatist"),
    ("研发·生物/湿实验", r"in vivo|in vitro|pharmacolog|assay|disease biology|cell biology|immunolog|screening|wet lab|molecular biology|microbiolog|animal|histolog|imaging|technology development|platform"),
    ("软件/数据工程", r"software|engineer|infrastructure|devops|data engineer|pipeline|platform engineer|full stack|backend|cloud"),
]


def categorize_industry(title: str, desc: str, dept: str = "") -> str:
    for name, pat in INDUSTRY_CATEGORIES:
        if re.search(pat, f"{title} {dept}", re.I):
            return name
    for name, pat in INDUSTRY_CATEGORIES:
        if re.search(pat, desc[:1200], re.I):
            return name
    return "其他"


def region_of(location: str, desc: str = "") -> str:
    """US / 非美国 / 未知。先看地点字段，再看正文开头。"""
    loc = location or ""
    if NON_US_HINTS.search(loc) and not US_HINTS.search(loc):
        return "非美国"
    if US_HINTS.search(loc) or re.search(r"\bUS\b|USA|United States", loc):
        return "US"
    if not loc.strip() or "locations" in loc.lower():
        head = desc[:400]
        if US_HINTS.search(head) and not NON_US_HINTS.search(head):
            return "US"
        if NON_US_HINTS.search(head) and not US_HINTS.search(head):
            return "非美国"
        return "未知"
    # 常见美国城市但没写州
    if re.search(r"San Francisco|South San Francisco|Palo Alto|San Diego|Boston|Cambridge, MA|New York|Seattle|Houston|Chicago|Salt Lake|Redwood City|Santa Clara|Bay Area", loc, re.I):
        return "US"
    return "未知"


def _contains_any(text: str, words: list[str]) -> list[str]:
    t = text.lower()
    return [w for w in words if w.lower() in t]


def topic_score(text: str, topics: list[dict]) -> tuple[int, list[str]]:
    t = text.lower()
    score, hits = 0, []
    for item in topics:
        kw = item["kw"].lower()
        if kw in t:
            score += int(item.get("w", 1))
            hits.append(item["kw"])
    return score, hits


def classify(job: dict, prof: dict) -> dict | None:
    """返回补充了 score/hits/kind/role 的 job，或 None（被过滤掉）。"""
    title = job.get("title", "") or ""
    text = f"{title} {job.get('description', '')} {job.get('org', '')}"
    tl = title.lower()

    if _contains_any(tl, prof.get("exclude_title_words", [])):
        return None

    fac_hits = _contains_any(tl, prof.get("faculty_title_words", []))
    ind_hits = _contains_any(tl, prof.get("industry_title_words", []))

    if job.get("kind") == "industry":
        if not ind_hits:
            return None
        role = "industry"
    else:
        # 学术来源：有 faculty 词 → faculty；否则丢弃（postdoc 等已被排除词挡掉）
        if not fac_hits:
            return None
        role = "faculty"

    score, hits = topic_score(text, prof.get("topics", []))
    # 标题里命中的领域词额外加权
    tscore, thits = topic_score(title, prof.get("topics", []))
    score += tscore
    threshold = prof.get("min_score_faculty", 2) if role == "faculty" else prof.get("min_score_industry", 3)
    if score < threshold:
        return None

    if role == "faculty" and prof.get("faculty_us_only", True):
        loc_text = f"{job.get('location', '')} {job.get('description', '')[:400]} {job.get('org', '')}"
        if NON_US_HINTS.search(loc_text) and not US_HINTS.search(loc_text):
            return None

    tt = tl
    if "tenure" in tt or "assistant professor" in tt:
        level = "Tenure-track / Asst Prof"
    elif role == "faculty":
        level = "Faculty / PI"
    elif any(w in tt for w in ("principal", "director", "lead", "staff", "head")):
        level = "Senior / Lead"
    elif "senior" in tt or " ii" in tt or " iii" in tt:
        level = "Senior"
    else:
        level = "Scientist"

    out = dict(job)
    full_desc = out.get("description") or ""
    out.update({"role": role, "score": score, "hits": sorted(set(hits + thits)), "level": level})
    out["salary"] = out.get("salary") or extract_salary(full_desc)
    out["region"] = region_of(out.get("location", ""), full_desc)
    if role == "industry":
        out["category"] = categorize_industry(title, full_desc, out.get("department", ""))
    out["description"] = full_desc[:1500]
    return out
