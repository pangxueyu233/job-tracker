# Job Tracker — 学术 TT 教职 + 公司岗位 自动追踪

每天自动从十几个来源抓取职位，按你的研究方向打分、去重、记录首次出现时间，生成一个可筛选、可标记申请状态的网页。

- 零服务器：GitHub Actions 定时跑 + GitHub Pages 托管（推荐），也可以本地 `python run.py` 后双击 `docs/index.html`
- 来源与接口 **全部在 2026-10-01 实测可用**（见下表）
- 所有可调参数都在 `config.yaml`

---

## 1. 研究画像与关键词（已按你的 35 篇发表预设）

| 维度 | 内容 |
|---|---|
| 当前主线 | 肠道**真菌组 / 微生物组**与宿主免疫、IBD（Nat Med 2026 一作；Nature 2024；Nat Microbiol 2025 综述 multi-kingdom cancer microbiome） |
| 第二条线 | **克隆性造血 / 血液肿瘤**计算基因组（Nat Genet 2026；Cancer Discov 2025；JCI 2025，与 MSK Abdel-Wahab / Bolton 合作） |
| 博士阶段 | 肿瘤小鼠模型 + 表观遗传 + 单细胞（SCLC 转移 Nat Cancer 2022；ESCC 细胞身份 STTT 2022 一作；Cancer Cell 2022 膀胱癌） |
| 技术标签 | metagenomics / WGS、single-cell & spatial、tumor evolution、clonal hematopoiesis、epigenetics、mouse models、host–microbe |

对应的 `config.yaml → profile.topics` 权重：microbiome / metagenomics / mycobiome / clonal hematopoiesis / cancer genomics 最高，computational biology / bioinformatics / single-cell 次之，immunology / oncology / machine learning 做加分项。

**适合投的系 / 方向**（faculty 搜索时注意这些关键词）：Microbiology & Immunology、Computational Biology / Biomedical Informatics、Cancer Biology / Oncological Sciences、Genetics & Genomics、Systems Biology、Pathology（computational）、以及各大癌症中心（MSK、MD Anderson、Dana-Farber、Fred Hutch、Moffitt、City of Hope、Huntsman）的 computational / microbiome program。

**美国 TT 招聘时间线**：岗位集中在 8–11 月放出，截止多在 10–12 月，面试 1–3 月。如果 2027 年秋季投，建议 2027 年 6 月前把网页跑顺，7–8 月开始准备 research statement。

---

## 2. 数据来源（已验证）

### 学术岗位
| 来源 | 方式 | 备注 |
|---|---|---|
| Science Careers | RSS，`keywords` + `countrycode=US` | 6 组关键词，可在 config 里改 |
| Nature Careers | 同上（同一 Madgex 系统） | |
| HigherEdJobs | 10 个学科分类 RSS（Biology、Biochem、Medical Research、Biostat、Data Science…） | 站点有 Incapsula 反爬：分类之间停 5 秒可正常拿 RSS；详情页有 JS 验证抓不到，所以只按标题 + 分类名打分 |
| AcademicJobsOnline | 全站 RSS 1.0，本地按关键词过滤 | |
| 社区共享表 | Google Sheet "发布到网络 → CSV" 链接 | 留空则跳过；每年秋季的 comp bio / microbiome faculty jobs 共享表可以直接挂上 |

### 公司岗位（招聘系统公开接口）
| 系统 | 已验证公司 |
|---|---|
| Greenhouse | Altos Labs、Arc Institute、Chan Zuckerberg Initiative、Isomorphic Labs、Recursion、Calico、Generate Biomedicines、Lila Sciences、Ginkgo Bioworks、Vedanta Biosciences |
| Ashby | insitro |
| Workday | Illumina、NVIDIA、Pfizer、Novartis |
| 待确认（`enabled: false`） | Tempus、GRAIL、Guardant、10x Genomics、Xaira、Flagship、DeepMind、Genentech、Regeneron、AbbVie —— 用 `discover.py` 找到正确 slug 后打开 |

> LinkedIn / Indeed 禁止抓取且反爬严格，故意不做。想盯的公司优先走它自己的招聘系统接口。

---

## 3. 本地运行（Windows / Linux / Mac 都一样）

```bash
pip install -r requirements.txt
python run.py                 # 抓取 + 生成 docs/index.html
python run.py --no-fetch --reclassify   # 不联网，用已存数据重新算薪资/职能/地区并重新生成网页
python tests/test_offline.py  # 不联网的自检
```

然后双击打开 `docs/index.html`。数据在 `data/jobs.json`，每次运行只追加/更新，不会丢历史。

**Windows 每天自动跑**：任务计划程序 → 创建基本任务 → 每天 → 操作"启动程序"：
程序 `python`，参数 `run.py`，起始于 本目录路径。（或把 `run.bat` 拖进任务计划程序。）

---

## 4. 部署到 GitHub（推荐，免费、手机也能看）

1. 在 GitHub 新建一个仓库（可以是 **Private**），把本目录全部推上去：
   ```bash
   git init && git add . && git commit -m "init"
   git branch -M main && git remote add origin git@github.com:<你>/job-tracker.git && git push -u origin main
   ```
2. 仓库 **Settings → Actions → General → Workflow permissions** 选 *Read and write permissions*（让机器人能提交结果）。
3. 仓库 **Settings → Pages → Build and deployment**：Source 选 *Deploy from a branch*，Branch 选 `main` / `/docs`。
   - Private 仓库的 Pages 需要 GitHub Pro / 学校的 GitHub Education（Cornell 有）；或者仓库设 Public 也没关系，页面上只有职位信息，你的申请标记只存在你浏览器里。
4. **Actions** 标签页 → *Update job tracker* → *Run workflow* 跑第一次。之后每天 UTC 11:17（美东早 7 点）自动跑，网址是 `https://<你>.github.io/job-tracker/`。

想改时间：编辑 `.github/workflows/update.yml` 里的 `cron`。

---

## 5. 网页怎么用

- 顶部切换 **全部 / 学术 / 公司**，搜索框匹配标题、机构、地点、关键词、正文
- **NEW** = 近 7 天首次抓到（`output.new_days`）；"可能已关闭" = 连续 14 天没再抓到（`output.stale_days`），默认隐藏
- 点列头排序；"匹配"列是领域关键词得分，默认按它倒序
- **薪资**列：从岗位正文里自动抓取的区间（美国不少州强制公示，Greenhouse/Ashby 岗位多数有；学校岗位视情况），抓不到就留空
- **职能**（公司岗位）：按标题/部门/正文自动归类为 研发·计算/生信/ML、研发·生物/湿实验、药物设计/化学/蛋白、临床/转化/医学、软件/数据工程、项目/运营/管理、产品/市场/商务；规则在 `tracker/filters.py → INDUSTRY_CATEGORIES`，可自己加词
- **地点**：公司岗取招聘系统的地点字段（Workday 会补抓详情页拿完整地点列表）；AJO 岗位补抓详情页拿地点和截止日期；明确在美国以外的会打"非美国"标签，勾"只看美国"即可隐藏
- 每行可标 **感兴趣 / 已申请 / 面试中 / 已拒绝 / 忽略** + 备注，保存在浏览器 localStorage
- 换电脑想同步：点 **导出标记 status.json** → 放到仓库 `data/status.json` 并 push，下次运行会合并进页面；或在另一台机器上 **导入标记**

---

## 6. 调整与扩展

- **调阈值**：`profile.min_score_faculty / min_score_industry`。觉得漏了就调低，噪音多就调高或加 `exclude_title_words`
- **想看 postdoc**：把 `exclude_title_words` 里的 postdoc 三行删掉
- **只看美国教职**：`profile.faculty_us_only: true`（公司岗不过滤地区）
- **加公司**：
  ```bash
  python discover.py https://www.tempus.com/careers/     # 从 careers 页面检测招聘系统
  python discover.py tempus grail guardant                # 或直接猜 slug
  ```
  把输出的条目贴进 `config.yaml → industry_sources`
- **加学校自己的招聘页**：多数学校用 Interfolio / PeopleAdmin / Workday。Workday 的可直接按 Workday 格式加；其余建议靠 Science/Nature/HigherEdJobs/AJO 覆盖（大部分 TT 岗位至少会在其中之一出现）

## 7. 文件说明

```
config.yaml            所有配置（关键词、来源、阈值）
run.py                 主程序：抓取 → 过滤 → 合并 → 渲染
discover.py            判断一个公司用的招聘系统
tracker/sources.py     各来源抓取器
tracker/filters.py     打分、分类、US 过滤
tracker/store.py       data/jobs.json 读写、first_seen/last_seen、status 合并
tracker/render.py      生成 docs/index.html（单文件，数据内嵌）
tests/test_offline.py  离线自检
.github/workflows/update.yml   每日定时任务
data/jobs.json         抓取结果（自动生成）
data/status.json       你的申请标记（可选，从网页导出）
docs/index.html        网页（自动生成，GitHub Pages 从这里托管）
```
