#!/usr/bin/env python3
"""抓取 → 过滤 → 合并 → 生成网页。用法：
    python run.py                 # 正常运行
    python run.py --no-fetch      # 不抓取，只用已有 data/jobs.json 重新生成网页
    python run.py --no-fetch --reclassify   # 不抓取，重新计算薪资/职能/地区后生成网页
    python run.py --only "Science Careers,Altos Labs"   # 只跑部分来源（调试用）
"""
import argparse
import logging
import os
import sys

import yaml

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from tracker import filters, render, sources, store  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s", datefmt="%H:%M:%S")
log = logging.getLogger("tracker")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="config.yaml")
    ap.add_argument("--no-fetch", action="store_true")
    ap.add_argument("--only", default="")
    ap.add_argument("--reclassify", action="store_true", help="不抓取，用已存的描述重新计算薪资/职能/地区")
    args = ap.parse_args()

    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    with open(args.config, encoding="utf-8") as f:
        cfg = yaml.safe_load(f)
    prof, out = cfg["profile"], cfg["output"]

    data = store.load(out["data_file"])

    if not args.no_fetch:
        if args.only:
            names = {n.strip() for n in args.only.split(",")}
            for key in ("academic_sources", "industry_sources"):
                cfg[key] = [s for s in cfg.get(key, []) if s.get("name") in names]
        # 已经补抓过详情（有地点且有正文）的岗位不再重复抓详情页
        known = {j.get("url", "") for j in data.get("jobs", {}).values()
                 if j.get("location") and len(j.get("description", "")) > 200}
        raw = sources.fetch_all(cfg, known)
        log.info("fetched %d raw postings", len(raw))
        kept = [k for k in (filters.classify(j, prof) for j in raw) if k]
        sources.enrich_kept(cfg, kept, known)
        for k in kept:  # 补抓到地点后重新判断地区
            k["region"] = filters.region_of(k.get("location", ""), k.get("description", ""))
        log.info("kept %d after filtering (faculty=%d, industry=%d)", len(kept),
                 sum(1 for k in kept if k["role"] == "faculty"), sum(1 for k in kept if k["role"] == "industry"))
        data = store.merge(data, kept, out.get("stale_days", 14))
        store.apply_status_file(data, os.path.join(os.path.dirname(out["data_file"]), "status.json"))
        store.save(out["data_file"], data)

    if args.reclassify:
        for j in data.get("jobs", {}).values():
            j["salary"] = j.get("salary") or filters.extract_salary(j.get("description", ""))
            j["region"] = filters.region_of(j.get("location", ""), j.get("description", ""))
            if j.get("role") == "industry":
                j["category"] = filters.categorize_industry(j.get("title", ""), j.get("description", ""), j.get("department", ""))
        store.save(out["data_file"], data)
        log.info("reclassified %d jobs", len(data.get("jobs", {})))

    info = render.render(data, out["html_file"], prof.get("name", ""), out.get("new_days", 7))
    log.info("wrote %s (%d jobs, %d new)", out["html_file"], info["total"], info["new"])


if __name__ == "__main__":
    main()
