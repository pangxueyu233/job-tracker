"""离线测试：用与真实接口同构的样例数据跑完整流程（不需要网络）。
    python tests/test_offline.py
"""
import json
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import yaml  # noqa: E402

from tracker import filters, render, sources, store  # noqa: E402

SCIENCE_RSS = """<?xml version="1.0"?><rss version="2.0"><channel>
<item><title>Lee Kong Chian School of Medicine : Associate/Assistant Professor of Microbiome</title>
<description>
Commensurate with skills and experience:

Lee Kong Chian School of Medicine :
A full-time position is open for a tenure-track Associate/Assistant Professor of Microbiome.
Singapore (SG)
</description><link>https://jobs.sciencecareers.org/job/680240/associate-assistant-professor-of-microbiome/?TrackID=9&amp;utm_source=rss</link>
<pubDate>Fri, 18 Sep 2026 05:48:00 -0500</pubDate></item>
<item><title>MD Anderson Cancer Center: Assistant Professor, Tenure Track - Computational Cancer Genomics</title>
<description>
Commensurate:

MD Anderson Cancer Center:
Seeking a tenure-track faculty member in computational biology, single-cell and cancer genomics, tumor evolution.
Houston, Texas (US)
</description><link>https://jobs.sciencecareers.org/job/680300/asst-prof/?TrackID=9</link>
<pubDate>Thu, 01 Oct 2026 01:32:04 EDT</pubDate></item>
<item><title>UCSF: Postdoctoral Scholar - Microbiome</title><description>UCSF:\nmicrobiome metagenomics\nSan Francisco</description>
<link>https://jobs.sciencecareers.org/job/679946/postdoc/</link><pubDate>Wed, 02 Sep 2026 04:30:04 -0500</pubDate></item>
</channel></rss>"""

HEJ_RSS = """<rss version="2.0"><channel>
<item><title>Asst Professor</title><description>University of Michigan (Ann Arbor, MI)</description><link>https://www.higheredjobs.com/details.cfm?JobCode=179574664</link><pubDate>Thu, 01 Oct 2026 01:30:37 EDT</pubDate></item>
<item><title>Instructor</title><description>Midwestern State University (Wichita Falls, TX)</description><link>https://www.higheredjobs.com/details.cfm?JobCode=179546985</link><pubDate>Thu, 03 Sep 2026 15:08:35 EDT</pubDate></item>
</channel></rss>"""
HEJ_DETAIL = '<html><body><div id="jobDesc">The Department of Microbiology seeks a tenure-track Assistant Professor studying the human microbiome using metagenomics and computational biology approaches. ' + 'x' * 200 + '</div><div class="x">o</div></body></html>'

AJO_RDF = """<?xml version="1.0"?><rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#" xmlns="http://purl.org/rss/1.0/" xmlns:dc="http://purl.org/dc/elements/1.1/">
<channel rdf:about="https://academicjobsonline.org/ajo"><title>AJO</title></channel>
<item rdf:about="https://academicjobsonline.org/ajo/Duke/Biology/32900?rss"><title>Assistant Professor in Computational Biology</title>
<link>https://academicjobsonline.org/ajo/Duke/Biology/32900?rss</link>
<description>Duke University Biology invites applications for a tenure-track assistant professor in computational biology, genomics, microbiome science. Deadline: December 1, 2026. Durham, NC</description>
<dc:date>2026-09-30T10:00:00-04:00</dc:date></item>
<item rdf:about="https://academicjobsonline.org/ajo/Yale/Soc/32903?rss"><title>Postdoctoral Associate Position in Biosocial Science</title><link>https://academicjobsonline.org/ajo/Yale/Soc/32903?rss</link><description>microbiome postdoc</description><dc:date>2026-09-30T10:00:00-04:00</dc:date></item>
</rdf:RDF>"""

GH_JSON = {"jobs": [
    {"absolute_url": "https://job-boards.greenhouse.io/altoslabs/jobs/6106430004", "title": "Senior Scientist, Computational Biology",
     "location": {"name": "Redwood City, CA"}, "content": "&lt;p&gt;single-cell genomics, machine learning, epigenetics&lt;/p&gt;",
     "first_published": "2026-09-20T12:00:00-04:00"},
    {"absolute_url": "https://job-boards.greenhouse.io/altoslabs/jobs/1", "title": "Accounting Manager", "location": {"name": "x"}, "content": "finance", "first_published": "2026-09-20T12:00:00-04:00"},
]}
ASHBY_JSON = {"jobs": [{"id": "0bff", "title": "Machine Learning Scientist, Genomics", "location": "South San Francisco", "jobUrl": "https://jobs.ashbyhq.com/insitro/0bff",
                        "descriptionPlain": "multi-omic single cell data, computational biology", "publishedAt": "2026-09-25T00:00:00.000Z"}]}
WD_LIST = {"total": 1, "jobPostings": [{"title": "Staff Bioinformatics Scientist", "externalPath": "/job/US---California---San-Diego/Staff-Bioinformatics-Scientist_43098-JOB-1",
                                        "locationsText": "2 Locations", "postedOn": "Posted 30+ Days Ago"}]}
WD_DETAIL = {"jobPostingInfo": {"jobDescription": "<p>metagenomics pipelines, microbiome, whole-genome sequencing</p>", "startDate": "2026-08-15"}}


class FakeResp:
    def __init__(self, text="", data=None):
        self.text, self._data = text, data
        self.content = text.encode()
    def json(self):
        return self._data


class FakeHttp:
    def get(self, url, params=None, **kw):
        if "sciencecareers" in url or "naturecareers" in url:
            return FakeResp(SCIENCE_RSS)
        if "categoryFeed" in url:
            return FakeResp(HEJ_RSS)
        if "higheredjobs.com/details" in url:
            return FakeResp(HEJ_DETAIL)
        if "academicjobsonline" in url:
            return FakeResp(AJO_RDF)
        if "greenhouse" in url:
            return FakeResp(data=GH_JSON)
        if "ashbyhq" in url:
            return FakeResp(data=ASHBY_JSON)
        if "/wday/cxs/" in url:
            return FakeResp(data=WD_DETAIL)
        return FakeResp("<html></html>")
    def post_json(self, url, payload, **kw):
        return WD_LIST


def main():
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    with open(os.path.join(root, "config.yaml"), encoding="utf-8") as f:
        cfg = yaml.safe_load(f)
    http = FakeHttp()
    raw = []
    for src in cfg["academic_sources"] + cfg["industry_sources"]:
        if not src.get("enabled", True):
            continue
        src["_faculty_words"] = cfg["profile"]["faculty_title_words"]
        src.update({"feed_pause": 0, "detail_pause": 0, "detail_budget": 5})  # 离线测试不等待，并测试详情页逻辑
        raw += sources.FETCHERS[src["type"]](http, src)
    print(f"raw: {len(raw)}")
    kept = [k for k in (filters.classify(j, cfg["profile"]) for j in raw) if k]
    for k in kept:
        print(f"  [{k['role']:8}] {k['score']:>2}  {k['title'][:60]:60} | {k['org'][:30]:30} | {k['location']} | posted={k['posted']} dl={k['deadline']}")
    titles = {k["title"] for k in kept}
    assert "Assistant Professor, Tenure Track - Computational Cancer Genomics" in titles
    assert "Assistant Professor in Computational Biology" in titles
    assert "Asst Professor" in titles, "HigherEdJobs 详情页正文应被用于打分"
    assert "Senior Scientist, Computational Biology" in titles
    assert "Machine Learning Scientist, Genomics" in titles
    assert "Staff Bioinformatics Scientist" in titles
    assert not any("Postdoc" in t for t in titles), "postdoc 应被排除"
    assert not any("Microbiome" in t and "Lee Kong" in k["org"] for t in titles for k in kept), "新加坡岗位应被 US-only 过滤"
    assert "Accounting Manager" not in titles
    with tempfile.TemporaryDirectory() as d:
        data = store.merge(store.load(os.path.join(d, "jobs.json")), kept, 14)
        store.save(os.path.join(d, "jobs.json"), data)
        data2 = store.merge(store.load(os.path.join(d, "jobs.json")), kept, 14)
        assert data2["runs"][-1]["new"] == 0, "第二次合并不应有新增"
        info = render.render(data2, os.path.join(d, "index.html"), "test", 7)
        html = open(os.path.join(d, "index.html"), encoding="utf-8").read()
        assert "const JOBS = [" in html and info["total"] == len({store.job_id(k) for k in kept})
        print(f"rendered {len(html)} bytes, {info}")
        print(json.dumps(data2["runs"], ensure_ascii=False))
    print("ALL OK")


if __name__ == "__main__":
    main()
