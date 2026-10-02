"""把 jobs.json 渲染成单文件 index.html（数据内嵌，离线可开，GitHub Pages 可直接托管）。"""
from __future__ import annotations

import json
import os
from datetime import date, datetime

TEMPLATE = r"""<!doctype html>
<html lang="zh-CN" data-theme="auto">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Job Tracker · __NAME__</title>
<style>
:root{--bg:#f7f7f5;--card:#fff;--ink:#1c1c1c;--mut:#6b6b6b;--line:#e4e2dd;--acc:#2a6f97;--acc2:#e8f1f6;--new:#b8552b;--newbg:#fbeee6;--ok:#2d7a4f;--okbg:#e6f3ea;--warn:#8a6d00;--warnbg:#fff6d6;--bad:#9b3131;--badbg:#f8e5e5}
@media (prefers-color-scheme:dark){:root:not([data-theme=light]){--bg:#15161a;--card:#1e2027;--ink:#ececec;--mut:#9a9aa3;--line:#2e313a;--acc:#7cb6d8;--acc2:#1f2f3a;--new:#f0a07a;--newbg:#3b2419;--ok:#7fcf9c;--okbg:#1b3324;--warn:#e8c75a;--warnbg:#3a3114;--bad:#f09a9a;--badbg:#3c1f1f}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font:14px/1.45 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,"PingFang SC","Microsoft YaHei",sans-serif}
header{padding:18px 20px 10px;border-bottom:1px solid var(--line);background:var(--card);position:sticky;top:0;z-index:5}
h1{margin:0 0 6px;font-size:18px;font-weight:650}h1 span{color:var(--mut);font-weight:400;font-size:13px;margin-left:10px}
.stats{display:flex;gap:18px;flex-wrap:wrap;color:var(--mut);font-size:13px;margin-bottom:10px}.stats b{color:var(--ink);font-size:16px;margin-right:4px}
.bar{display:flex;gap:8px;flex-wrap:wrap;align-items:center}
input[type=search],select{padding:6px 9px;border:1px solid var(--line);border-radius:7px;background:var(--bg);color:var(--ink);font-size:13px}
input[type=search]{min-width:240px;flex:1}
.tabs{display:inline-flex;border:1px solid var(--line);border-radius:7px;overflow:hidden}.tabs button{border:0;background:var(--bg);color:var(--ink);padding:6px 12px;cursor:pointer;font-size:13px}.tabs button.on{background:var(--acc);color:#fff}
label.chk{display:inline-flex;align-items:center;gap:4px;color:var(--mut);font-size:13px;cursor:pointer}
button.sm{border:1px solid var(--line);background:var(--bg);color:var(--ink);border-radius:6px;padding:4px 8px;font-size:12px;cursor:pointer}button.sm:hover{border-color:var(--acc)}
main{padding:12px 20px 60px;max-width:1400px;margin:0 auto}
table{width:100%;border-collapse:collapse;background:var(--card);border:1px solid var(--line);border-radius:10px;overflow:hidden}
th{background:var(--card);text-align:left;font-size:12px;color:var(--mut);font-weight:600;padding:8px 10px;border-bottom:1px solid var(--line);cursor:pointer;white-space:nowrap;z-index:2}
td{padding:9px 10px;border-bottom:1px solid var(--line);vertical-align:top}td.d{white-space:nowrap;font-variant-numeric:tabular-nums}
tr.closed td{opacity:.45}tr.hidden{display:none}
a{color:var(--acc);text-decoration:none}a:hover{text-decoration:underline}
.t{font-weight:600;font-size:14px}.o{color:var(--mut);font-size:12.5px;margin-top:2px}
.tag{display:inline-block;font-size:11px;padding:1px 7px;border-radius:999px;background:var(--acc2);color:var(--acc);margin:2px 3px 0 0;white-space:nowrap}
.tag.new{background:var(--newbg);color:var(--new);font-weight:600}.tag.role{background:var(--line);color:var(--ink)}.tag.cat{background:var(--okbg);color:var(--ok);margin-top:4px}.tag.reg{background:var(--warnbg);color:var(--warn)}td.sal{font-size:12.5px;white-space:nowrap}
.sc{font-variant-numeric:tabular-nums;font-weight:600}
.st select{padding:3px 6px;font-size:12px;border-radius:6px;border:1px solid var(--line);background:var(--bg);color:var(--ink)}
.st.s-interested select{background:var(--warnbg);color:var(--warn)}.st.s-applied select,.st.s-interview select{background:var(--okbg);color:var(--ok)}.st.s-rejected select,.st.s-ignore select{background:var(--badbg);color:var(--bad)}
.note{width:100%;margin-top:4px;padding:3px 6px;font-size:12px;border:1px solid var(--line);border-radius:6px;background:var(--bg);color:var(--ink)}
.desc{display:none;color:var(--mut);font-size:12.5px;margin-top:6px;max-width:720px}tr.open .desc{display:block}
.more{font-size:12px;color:var(--mut);cursor:pointer}
footer{color:var(--mut);font-size:12px;padding:14px 20px;text-align:center}
@media (max-width:760px){td.hide-m,th.hide-m{display:none}input[type=search]{min-width:160px}}
</style>
</head>
<body>
<header>
  <h1>Job Tracker <span>__NAME__ · 更新于 __UPDATED__ · 共 __TOTAL__ 条 · 新增 __NEW__ 条（近 __NEWDAYS__ 天）</span></h1>
  <div class="stats" id="stats"></div>
  <div class="bar">
    <div class="tabs" id="roleTabs"><button data-r="" class="on">全部</button><button data-r="faculty">学术 Faculty</button><button data-r="industry">公司 Industry</button></div>
    <input type="search" id="q" placeholder="搜索标题 / 机构 / 地点 / 关键词…">
    <select id="src"><option value="">所有来源</option></select>
    <select id="stf"><option value="">所有状态</option><option value="_none">未标记</option><option value="interested">感兴趣</option><option value="applied">已申请</option><option value="interview">面试中</option><option value="rejected">已拒绝</option><option value="ignore">忽略</option></select>
    <select id="cat"><option value="">所有职能</option></select>
    <label class="chk"><input type="checkbox" id="usOnly"> 只看美国</label>
    <label class="chk"><input type="checkbox" id="onlyNew"> 只看新增</label>
    <label class="chk"><input type="checkbox" id="hideClosed" checked> 隐藏已关闭</label>
    <label class="chk"><input type="checkbox" id="hideIgnored" checked> 隐藏已忽略</label>
    <button class="sm" id="exp">导出标记 status.json</button>
    <button class="sm" id="imp">导入标记</button><input type="file" id="impf" accept=".json" style="display:none">
  </div>
</header>
<main>
<table id="tb">
<thead><tr>
<th data-k="title">职位 / 机构</th>
<th data-k="level" class="hide-m">类型</th>
<th data-k="location" class="hide-m">地点</th>
<th data-k="salary" class="hide-m">薪资</th>
<th data-k="score" title="领域关键词得分">匹配</th>
<th data-k="posted" class="hide-m">发布</th>
<th data-k="first_seen">首次抓到</th>
<th data-k="deadline" class="hide-m">截止</th>
<th data-k="source" class="hide-m">来源</th>
<th>状态 / 备注</th>
</tr></thead>
<tbody id="rows"></tbody>
</table>
</main>
<footer>数据每日自动抓取；标记保存在本浏览器（localStorage），用「导出标记」把 status.json 放回仓库 data/ 目录可跨设备同步。</footer>
<script>
const JOBS = __JOBS__;
const NEW_DAYS = __NEWDAYS__;
const STATUS_LABEL = {"":"—","interested":"感兴趣","applied":"已申请","interview":"面试中","rejected":"已拒绝","ignore":"忽略"};
let st = {}; try { st = JSON.parse(localStorage.getItem('jobstatus')||'{}'); } catch(e){ st = {}; }
// 仓库里 status.json 带来的标记作为底，本地标记覆盖
for (const j of JOBS) { if (j.status && !st[j.id]) st[j.id] = {status:j.status, note:j.note||''}; }
function saveSt(){ try{ localStorage.setItem('jobstatus', JSON.stringify(st)); }catch(e){} }
const today = new Date(); const cut = new Date(today.getTime()-NEW_DAYS*864e5).toISOString().slice(0,10);
for (const j of JOBS) j.isNew = (j.first_seen||'') >= cut;
let role = '', sortK = 'score', sortD = -1;
const $ = s => document.querySelector(s);
const esc = s => String(s??'').replace(/[&<>"]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
// 来源下拉
const srcs = [...new Set(JOBS.map(j=>j.source))].sort();
for (const s of srcs){ const o=document.createElement('option'); o.value=s; o.textContent=s; $('#src').appendChild(o); }
const cats = [...new Set(JOBS.map(j=>j.category).filter(Boolean))].sort();
for (const c of cats){ const o=document.createElement('option'); o.value=c; o.textContent=c; $('#cat').appendChild(o); }
function render(){
  const q = $('#q').value.trim().toLowerCase(), src=$('#src').value, stf=$('#stf').value, cat=$('#cat').value, usOnly=$('#usOnly').checked;
  const onlyNew=$('#onlyNew').checked, hideClosed=$('#hideClosed').checked, hideIgn=$('#hideIgnored').checked;
  let list = JOBS.filter(j=>{
    const s = (st[j.id]||{}).status||'';
    if (role && j.role!==role) return false;
    if (src && j.source!==src) return false;
    if (cat && j.category!==cat) return false;
    if (usOnly && j.region && j.region!=='US') return false;
    if (stf==='_none' ? s : (stf && s!==stf)) return false;
    if (onlyNew && !j.isNew) return false;
    if (hideClosed && j.closed) return false;
    if (hideIgn && s==='ignore' && stf!=='ignore') return false;
    if (q){ const hay=`${j.title} ${j.org} ${j.location} ${j.category||''} ${j.salary||''} ${(j.hits||[]).join(' ')} ${j.description||''}`.toLowerCase(); if(!hay.includes(q)) return false; }
    return true;
  });
  list.sort((a,b)=>{ let x=a[sortK]??'', y=b[sortK]??''; if(typeof x==='number'||typeof y==='number'){ return ((x||0)-(y||0))*sortD; } x=String(x); y=String(y); if(x===y) return (b.score||0)-(a.score||0); if(x==='') return 1; if(y==='') return -1; return x.localeCompare(y)*sortD; });
  const rows=$('#rows'); rows.innerHTML='';
  for (const j of list){
    const s = st[j.id]||{status:'',note:''};
    const tr=document.createElement('tr'); tr.className=(j.closed?'closed ':'');
    tr.innerHTML = `
      <td><div class="t"><a href="${esc(j.url)}" target="_blank" rel="noopener">${esc(j.title)}</a> ${j.isNew?'<span class="tag new">NEW</span>':''}${j.closed?'<span class="tag">可能已关闭</span>':''}</div>
          <div class="o">${esc(j.org)}</div>
          <div>${(j.hits||[]).slice(0,6).map(h=>`<span class="tag">${esc(h)}</span>`).join('')} <span class="more">详情 ▾</span></div>
          <div class="desc">${esc(j.description||'')}</div></td>
      <td class="hide-m"><span class="tag role">${esc(j.level||'')}</span>${j.category?`<br><span class="tag cat">${esc(j.category)}</span>`:''}</td>
      <td class="hide-m">${esc(j.location||'')}${j.region&&j.region!=='US'?` <span class="tag reg">${esc(j.region)}</span>`:''}</td>
      <td class="hide-m sal">${esc(j.salary||'')}</td>
      <td class="sc">${j.score??''}</td>
      <td class="hide-m d">${esc(j.posted||'')}</td>
      <td class="d">${esc(j.first_seen||'')}</td>
      <td class="hide-m d">${esc(j.deadline||'')}</td>
      <td class="hide-m">${esc(j.source||'')}</td>
      <td class="st s-${esc(s.status)}"><select data-id="${j.id}">${Object.entries(STATUS_LABEL).map(([k,v])=>`<option value="${k}" ${k===s.status?'selected':''}>${v}</option>`).join('')}</select>
          <input class="note" data-id="${j.id}" placeholder="备注…" value="${esc(s.note||'')}"></td>`;
    tr.querySelector('.more').onclick=()=>tr.classList.toggle('open');
    rows.appendChild(tr);
  }
  const nFac=JOBS.filter(j=>j.role==='faculty'&&!j.closed).length, nInd=JOBS.filter(j=>j.role==='industry'&&!j.closed).length;
  const nApp=Object.values(st).filter(v=>['applied','interview'].includes(v.status)).length, nInt=Object.values(st).filter(v=>v.status==='interested').length;
  $('#stats').innerHTML=`<div><b>${list.length}</b>当前显示</div><div><b>${nFac}</b>学术在招</div><div><b>${nInd}</b>公司在招</div><div><b>${nInt}</b>感兴趣</div><div><b>${nApp}</b>已申请/面试</div>`;
}
document.addEventListener('change', e=>{
  if (e.target.matches('.st select')){ const id=e.target.dataset.id; st[id]=st[id]||{}; st[id].status=e.target.value; saveSt(); e.target.parentElement.className='st s-'+e.target.value; render(); }
  if (e.target.matches('.note')){ const id=e.target.dataset.id; st[id]=st[id]||{status:''}; st[id].note=e.target.value; saveSt(); }
});
['#q','#src','#stf','#cat','#usOnly','#onlyNew','#hideClosed','#hideIgnored'].forEach(s=>$(s).addEventListener('input',render));
$('#roleTabs').onclick=e=>{ if(e.target.tagName!=='BUTTON') return; role=e.target.dataset.r; [...e.currentTarget.children].forEach(b=>b.classList.toggle('on',b===e.target)); render(); };
document.querySelectorAll('th[data-k]').forEach(th=>th.onclick=()=>{ const k=th.dataset.k; if(sortK===k) sortD*=-1; else { sortK=k; sortD = (k==='score'||k==='first_seen'||k==='posted')?-1:1; } render(); });
$('#exp').onclick=()=>{ const out={}; for(const [k,v] of Object.entries(st)){ if(v.status||v.note) out[k]=v; } const b=new Blob([JSON.stringify(out,null,1)],{type:'application/json'}); const a=document.createElement('a'); a.href=URL.createObjectURL(b); a.download='status.json'; a.click(); };
$('#imp').onclick=()=>$('#impf').click();
$('#impf').onchange=e=>{ const f=e.target.files[0]; if(!f) return; f.text().then(t=>{ try{ Object.assign(st, JSON.parse(t)); saveSt(); render(); }catch(err){ alert('无法解析 JSON'); } }); };
render();
</script>
</body>
</html>
"""


def render(data: dict, out_path: str, name: str, new_days: int = 7) -> dict:
    jobs = list(data.get("jobs", {}).values())
    keep = ["id", "title", "org", "location", "url", "description", "posted", "deadline", "source", "role",
            "score", "hits", "level", "first_seen", "last_seen", "closed", "status", "note", "salary", "category", "region", "department"]
    slim = [{k: j.get(k) for k in keep if j.get(k) not in (None, "", False, [])} for j in jobs]
    today = date.today()
    n_new = sum(1 for j in jobs if (today - date.fromisoformat(j["first_seen"])).days < new_days)
    html = (TEMPLATE.replace("__JOBS__", json.dumps(slim, ensure_ascii=False).replace("</", "<\\/"))
            .replace("__NAME__", name).replace("__UPDATED__", datetime.now().strftime("%Y-%m-%d %H:%M"))
            .replace("__TOTAL__", str(len([j for j in jobs if not j.get("closed")])))
            .replace("__NEW__", str(n_new)).replace("__NEWDAYS__", str(new_days)))
    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(html)
    return {"total": len(jobs), "new": n_new}
