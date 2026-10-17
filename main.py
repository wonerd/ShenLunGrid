# -*- coding: utf-8 -*-
"""
申论方格纸 · 离线本地练习器
"""
import os
import sys
import json
import time
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse

APP_TITLE = "申论方格纸"
SAVE_DIR_NAME = "申论存档"
DRAFT_NAME = "当前草稿.txt"
INDEX_NAME = "索引.json"


# ============ 路径与存档（全部放在程序同目录的「申论存档」文件夹内） ============
def base_dir():
    """exe 运行时取 exe 所在目录；脚本运行时取脚本所在目录。"""
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))


SAVE_DIR = os.path.join(base_dir(), SAVE_DIR_NAME)
DRAFT_PATH = os.path.join(SAVE_DIR, DRAFT_NAME)
INDEX_PATH = os.path.join(SAVE_DIR, INDEX_NAME)


def ensure_dir():
    os.makedirs(SAVE_DIR, exist_ok=True)


def _safe_name(s):
    for ch in '\\/:*?"<>|':
        s = s.replace(ch, "")
    s = s.strip()[:20]
    return s or "无题"


def read_draft():
    try:
        with open(DRAFT_PATH, "r", encoding="utf-8") as f:
            return f.read()
    except (FileNotFoundError, UnicodeDecodeError):
        return ""


def write_draft(text):
    ensure_dir()
    tmp = DRAFT_PATH + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(text)
    os.replace(tmp, DRAFT_PATH)


def read_index():
    try:
        with open(INDEX_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, list):
            return data
    except (FileNotFoundError, json.JSONDecodeError, UnicodeDecodeError):
        pass
    return []


def write_index(items):
    ensure_dir()
    tmp = INDEX_PATH + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(items, f, ensure_ascii=False, indent=2)
    os.replace(tmp, INDEX_PATH)


# 标点集合（与前端一致：连续标点合占一格）
_PUNCT = set("，。、；：！？）】」』”’…—·》〉（【「『“‘《〈,.!?;:)][(\"'<")


def _is_digit(ch):
    return ch.isdigit() or ("\uff10" <= ch <= "\uff19")


def count_cells(text):
    """按稿纸格数统计：数字两位一格，连续标点一格，其余一字一格，换行不计。"""
    total = 0
    for para in text.split("\n"):
        i, n = 0, len(para)
        while i < n:
            ch = para[i]
            if _is_digit(ch):
                j = i
                while j < n and _is_digit(para[j]):
                    j += 1
                total += (j - i + 1) // 2  # 每两位一格，落单一位也算一格
                i = j
            elif ch in ("…", "—"):
                # 叠用符号 …… / —— 连续出现合占一格
                j = i
                while j < n and para[j] == ch:
                    j += 1
                total += 1
                i = j
            elif ch in _PUNCT:
                total += 1  # 普通标点各自一格
                i += 1
            else:
                total += 1
                i += 1
    return total


def get_data():
    """组装给前端：草稿 + 历史列表（正文从各自 txt 读回）。"""
    items = read_index()
    history = []
    for it in items:
        fp = os.path.join(SAVE_DIR, it.get("file", ""))
        try:
            with open(fp, "r", encoding="utf-8") as f:
                it = dict(it)
                it["text"] = f.read()
        except (FileNotFoundError, UnicodeDecodeError):
            continue
        history.append(it)
    return {"draft": read_draft(), "history": history}


def add_history(text, label):
    ensure_dir()
    count = count_cells(text)
    ts = time.strftime("%Y%m%d_%H%M%S")
    hms = f"{ts}_{int(time.time()*1000)%1000:03d}"
    fname = f"{hms}_{_safe_name(label)}_{count}字.txt"
    fp = os.path.join(SAVE_DIR, fname)
    with open(fp, "w", encoding="utf-8") as f:
        f.write(text)
    entry = {
        "id": int(time.time() * 1000),
        "time": time.strftime("%Y-%m-%d %H:%M"),
        "count": count,
        "label": _safe_name(label),
        "file": fname,
    }
    items = read_index()
    items.insert(0, entry)
    write_index(items)
    return entry


def delete_history(entry_id):
    items = read_index()
    kept = []
    for it in items:
        if it.get("id") == entry_id:
            fp = os.path.join(SAVE_DIR, it.get("file", ""))
            try:
                os.remove(fp)
            except OSError:
                pass
        else:
            kept.append(it)
    write_index(kept)


# ============ 页面 ============
HTML_PAGE = r"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>申论方格纸 · 离线练习</title>
<link rel="icon" href="data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 32 32'%3E%3Crect x='3' y='3' width='26' height='26' fill='%23fffdf9' stroke='%23c0504d' stroke-width='2'/%3E%3Cpath d='M3 12h26M3 21h26M12 3v26M21 3v26' stroke='%23d8b9b7' stroke-width='1.5'/%3E%3C/svg%3E">
<style>
:root{
  --side-bg:#f6f6f7; --line:#e3e3e6; --ink:#1f2329; --ink-2:#646a73;
  --red:#c0504d; --red-soft:#f3e3e2; --paper:#fffdf9; --paper-edge:#d9d2c4;
  --btn:#2b6cb0; --btn-hover:#245a96; --danger:#c0392b;
}
*{box-sizing:border-box;margin:0;padding:0}
html,body{height:100%}
body{font-family:"PingFang SC","Microsoft YaHei","Noto Sans SC",sans-serif;
  color:var(--ink);background:#ececee;display:flex;overflow:hidden}
button{font-family:inherit;cursor:pointer}

/* ===== 左侧栏 ===== */
#sidebar{width:272px;min-width:272px;background:var(--side-bg);
  border-right:1px solid var(--line);display:flex;flex-direction:column;height:100vh}
.brand{padding:18px 18px 10px}
.brand h1{font-size:18px;font-weight:700;letter-spacing:.5px}
.brand p{font-size:12px;color:var(--ink-2);margin-top:4px}
.side-actions{padding:10px 14px;display:flex;flex-direction:column;gap:8px}
.btn{border:1px solid var(--line);background:#fff;color:var(--ink);
  border-radius:8px;padding:9px 12px;font-size:14px;text-align:left;transition:.15s}
.btn:hover{background:#fff;border-color:#c9c9cf}
.btn.primary{background:var(--btn);color:#fff;border-color:var(--btn)}
.btn.primary:hover{background:var(--btn-hover)}
.btn.danger{color:var(--danger);border-color:#e6b8b1}
.btn.danger:hover{background:#fbeae7}
.stat-card{margin:10px 14px;background:#fff;border:1px solid var(--line);
  border-radius:10px;padding:12px 14px;display:flex;justify-content:space-between;align-items:center}
.stat-card b{font-size:24px;color:var(--red);font-variant-numeric:tabular-nums}
.stat-card span{font-size:12px;color:var(--ink-2)}
.side-section{padding:8px 14px 4px;font-size:13px;color:var(--ink-2);
  display:flex;justify-content:space-between;align-items:center}
#historyList{flex:1;overflow-y:auto;padding:4px 14px 18px;display:flex;flex-direction:column;gap:8px}
.empty-tip{font-size:13px;color:#9aa0a8;padding:18px 6px;text-align:center;line-height:1.7}
.h-item{background:#fff;border:1px solid var(--line);border-radius:10px;padding:10px 12px}
.h-item .h-meta{display:flex;justify-content:space-between;font-size:12px;color:var(--ink-2)}
.h-item .h-count{color:var(--red);font-weight:600}
.h-item .h-preview{font-size:13px;margin-top:6px;line-height:1.5;color:#3a3f45;
  overflow:hidden;display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical}
.h-item .h-btns{display:flex;gap:6px;margin-top:8px}
.h-item .h-btns button{font-size:12px;padding:4px 10px;border-radius:6px;
  border:1px solid var(--line);background:#fafafa}
.h-item .h-btns button:hover{background:#eee}
.h-item .h-btns .del{color:var(--danger)}
.side-foot{padding:10px 14px;font-size:11px;color:#9aa0a8;border-top:1px solid var(--line);line-height:1.6}

/* ===== 格子区 ===== */
#main{flex:1;display:flex;flex-direction:column;min-width:0;height:100vh}
.toolbar{height:56px;flex:none;background:#fff;border-bottom:1px solid var(--line);
  display:flex;align-items:center;gap:14px;padding:0 22px}
.toolbar .t-title{font-size:15px;font-weight:600}
.toolbar .spacer{flex:1}
.toolbar .t-count{font-size:13px;color:var(--ink-2)}
.toolbar .t-count b{color:var(--red);font-size:16px}
.tbtn{border:1px solid var(--line);background:#fff;border-radius:8px;
  padding:7px 14px;font-size:13px}
.tbtn:hover{background:#f2f3f5}
#paperWrap{flex:1;overflow-y:auto;padding:28px 24px 60px;background:#e9eaed}

/* 纸张页 */
.page{background:var(--paper);width:min(880px,100%);margin:0 auto 34px;
  box-shadow:0 2px 14px rgba(0,0,0,.12);padding:26px 30px 20px;position:relative}
.page-head{display:flex;justify-content:space-between;align-items:baseline;margin-bottom:10px}
.page-head .ph-title{font-size:14px;color:#8a8175;letter-spacing:2px}
.page-head .ph-no{font-size:13px;color:#8a8175}
.sheet{position:relative}
.g-row{display:grid;grid-template-columns:repeat(25,1fr)}
.cell{aspect-ratio:1/1;border-right:1px solid #d8b9b7;border-bottom:1px solid #d8b9b7;
  display:flex;align-items:center;justify-content:center;
  font-family:"Kaiti SC","KaiTi","STKaiti","FangSong",serif;
  font-size:clamp(14px,2.1vw,22px);color:#232323;position:relative;user-select:none}
.g-row .cell:nth-child(25n){border-right:none}
.g-row .cell.caret{outline:2px solid var(--red);outline-offset:-2px;background:var(--red-soft)}
/* 两位数字合占一格：字号略小、等宽 */
.cell.num{font-family:Consolas,"Courier New",monospace;font-size:0.74em;letter-spacing:1px}
/* 并入同一格的连续标点紧凑显示 */
.cell.punct{font-size:0.92em;letter-spacing:0}
/* 每行格子下方的空白间隔带，累计字数标在带内右侧 */
.g-gap{position:relative;height:1.15em;min-height:16px}
.g-gap .scale{position:absolute;right:2px;top:50%;transform:translateY(-50%);
  font-size:11px;color:#b08a87;font-style:italic}
.page-foot{text-align:right;font-size:11px;color:#a89e8d;margin-top:10px;letter-spacing:1px}
/* 历史弹窗里的小方格 */
.mini .g-row{margin-bottom:2px}
.mini .cell{font-size:13px;border-color:#ddd}
.mini .g-gap{height:.7em;min-height:8px}

/* 跟随输入框（承接中文输入法） */
#ghost{position:fixed;opacity:0;border:none;outline:none;background:transparent;
  font-size:18px;caret-color:transparent;z-index:99;width:24px;height:24px;padding:0}

/* 历史预览弹窗 */
#modalMask{position:fixed;inset:0;background:rgba(0,0,0,.35);display:none;
  align-items:center;justify-content:center;z-index:200}
#modalMask.show{display:flex}
.modal{width:min(920px,94vw);max-height:84vh;background:#fff;border-radius:14px;
  display:flex;flex-direction:column;overflow:hidden}
.modal h3{padding:16px 20px;border-bottom:1px solid var(--line);font-size:16px}
.modal .body{padding:20px 24px;overflow-y:auto;flex:1;background:#faf7f1}
.modal .foot{padding:14px 20px;border-top:1px solid var(--line);display:flex;gap:10px;justify-content:flex-end}

#toast{position:fixed;left:50%;bottom:34px;transform:translateX(-50%);
  background:rgba(30,30,32,.9);color:#fff;padding:10px 18px;border-radius:8px;
  font-size:14px;opacity:0;transition:.25s;z-index:300;pointer-events:none}
#toast.show{opacity:1}

/* 窄屏：左栏变顶部 */
@media (max-width:760px){
  body{flex-direction:column;overflow:auto}
  #sidebar{width:100%;min-width:0;height:auto;max-height:46vh;border-right:none;border-bottom:1px solid var(--line)}
  #historyList{max-height:180px}
  #main{height:auto;flex:none}
  .cell{font-size:14px}
}
@media print{
  #sidebar,.toolbar,#ghost,#toast,#modalMask{display:none!important}
  body{background:#fff;overflow:visible}
  #main,#paperWrap{overflow:visible;height:auto}
  .page{box-shadow:none;page-break-after:always;width:100%}
}
</style>
</head>
<body>
<!-- ===== 左侧栏 ===== -->
<aside id="sidebar">
  <div class="brand">
    <h1>申论方格纸</h1>
    <p>离线练习 · 数据保存在程序同目录</p>
  </div>
  <div class="side-actions">
    <button class="btn primary" id="btnSaveHistory">保存为历史记录</button>
    <button class="btn" id="btnCopy">复制全文</button>
    <button class="btn" id="btnPrint">打印 / 另存 PDF</button>
    <button class="btn danger" id="btnClear">一键清空</button>
  </div>
  <div class="stat-card">
    <span>已写字数</span><b id="statCount">0</b>
  </div>
  <div class="side-section"><span>历史记录</span><span id="histMeta"></span></div>
  <div id="historyList"></div>
  <div class="side-foot">存档保存在程序同目录的「申论存档」文件夹：当前草稿自动存为「当前草稿.txt」。</div>
</aside>

<!-- ===== 右侧主区 ===== -->
<main id="main">
  <div class="toolbar">
    <span class="t-title">作答区（25 格 × 20 行 = 每页 500 字）</span>
    <span class="spacer"></span>
    <span class="t-count">当前 <b id="tbCount">0</b> 字</span>
    <button class="tbtn" id="btnAddPage">加一页</button>
  </div>
  <div id="paperWrap"></div>
</main>

<textarea id="ghost" autocomplete="off" autocorrect="off" autocapitalize="off" spellcheck="false"></textarea>

<div id="modalMask">
  <div class="modal">
    <h3 id="modalTitle">历史预览</h3>
    <div class="body" id="modalBody"></div>
    <div class="foot">
      <button class="tbtn" id="modalClose">关闭</button>
      <button class="btn primary" id="modalRestore" style="padding:7px 14px">恢复到作答区</button>
    </div>
  </div>
</div>
<div id="toast"></div>

<script>
"use strict";
const COLS = 25, ROWS = 20, PER_PAGE = COLS * ROWS;
let text = "";
let reservedPages = 2;
let historyCache = [];
let modalRestoreText = "";
let saveTimer = null;

const ghost = document.getElementById("ghost");
const paperWrap = document.getElementById("paperWrap");
const historyList = document.getElementById("historyList");

// ---------- 工具 ----------
function esc(s){ return s.replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;"); }
function countChars(t){ return [...t].filter(c=>c!=="\n").length; }
function toast(msg){
  const el=document.getElementById("toast");
  el.textContent=msg; el.classList.add("show");
  clearTimeout(el._t); el._t=setTimeout(()=>el.classList.remove("show"),1800);
}
async function api(url, data){
  const r = await fetch(url,{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(data||{})});
  return r.json();
}

// ---------- 稿纸排版：数字两位一格，标点不上行首（避头点） ----------
const DIGIT_RE=/[0-9０-９]/;
// 避头标点：不得出现在一行第一个格子
const BAN_HEAD=new Set(['，','。','、','；','：','！','？','）','】','」','』','”','’','…','—','·','》','〉',',','.',';',':','!','?',')',']']);
// 全部标点（用于把连续标点如 …… —— “” 合到一格，不散开）
const PUNCT_ALL=new Set([...BAN_HEAD,'（','【','「','『','“','‘','《','〈','(', '[']);
function normDigit(ch){const c=ch.codePointAt(0);return (c>=0xFF10&&c<=0xFF19)?String.fromCharCode(c-0xFEE0):ch;}

// 把一整段切成「格单元」：连续数字每 2 个合占一格；连续标点（…… —— “”）合占一格；其余一字一格
function tokenizePara(para, base){
  const toks=[]; let i=0;
  while(i<para.length){
    const ch=para[i];
    if(DIGIT_RE.test(ch)){
      let j=i,raw="";
      while(j<para.length&&DIGIT_RE.test(para[j])){raw+=normDigit(para[j]);j++;}
      for(let k=0;k<raw.length;k+=2){toks.push({text:raw.slice(k,k+2),start:base+i+k,kind:'num'});}
      i=j;
    }else if(ch==='…'||ch==='—'){
      // 叠用符号：省略号 …… 、破折号 —— 连续出现合占一格
      let j=i; while(j<para.length&&para[j]===ch) j++;
      toks.push({text:para.slice(i,j),start:base+i,kind:'punct'});
      i=j;
    }else if(PUNCT_ALL.has(ch)){
      // 普通标点（，。、；：！？等）各自占一格
      toks.push({text:ch,start:base+i,kind:'punct'});
      i++;
    }else{
      toks.push({text:ch,start:base+i,kind:ch===' '?'space':'ch'});
      i++;
    }
  }
  return toks;
}

// 每行 25 格；避头点：行满时标点并入上一格
function buildLinesFrom(src){
  const lines=[]; let base=0;
  const paras=src.split('\n');
  for(const para of paras){
    const toks=tokenizePara(para,base);
    base+=para.length+1;
    let cur=[];
    for(const tk of toks){
      if(cur.length>=COLS){
        // 避头点：行满时标点并入上一格
        if(cur.length && BAN_HEAD.has(tk.text[0])){
          cur[cur.length-1].text+=tk.text;
          cur[cur.length-1].merged=true;
        }
        else{lines.push(cur);cur=[];cur.push(tk);}
      }else cur.push(tk);
    }
    lines.push(cur);
  }
  return lines;
}
function buildLines(){ return buildLinesFrom(text); }

// 所占格数
function countCells(src){
  let n=0,base=0;
  for(const para of src.split('\n')){n+=tokenizePara(para,base).length;base+=para.length+1;}
  return n;
}

// 生成一行 25 格
function rowHtml(line, caret, rowInPage, mini){
  let cells="";
  for(let c=0;c<COLS;c++){
    const tk=line?line[c]:null;
    let cls="cell";
    if(tk&&tk.kind==='num') cls+=" num";
    if(tk&&(tk.kind==='punct'||tk.merged)) cls+=" punct";
    let attr="";
    if(tk){
      if(caret!=null&&caret>=tk.start&&caret<tk.start+tk.text.length) cls+=" caret";
      attr=`data-offset="${tk.start}"`;
    }else{
      const eol=line&&line.length?line[line.length-1]:null;
      if(caret!=null&&eol&&caret>=eol.start+eol.text.length&&c===line.length) cls+=" caret";
      attr=`data-endofline="${eol?eol.start+eol.text.length:-1}"`;
    }
    cells+=`<div class="${cls}" data-row="${rowInPage}" data-col="${c}" ${attr}>${tk?esc(tk.text):""}</div>`;
  }
  let gap=[3,7,11,15].includes(rowInPage)
    ?`<div class="g-gap"><span class="scale">${(rowInPage+1)*25}</span></div>`
    :`<div class="g-gap"></div>`;
  return `<div class="g-row">${cells}</div>${gap}`;
}

// 文本铺成只读方格，历史预览
function previewSheet(srcText){
  const lines=buildLinesFrom(srcText);
  let html="";
  for(let r=0;r<Math.max(ROWS,lines.length);r++) html+=rowHtml(lines[r],null,r,true);
  return html;
}

function render(){
  const caret = ghost.selectionStart != null ? ghost.selectionStart : text.length;
  const lines = buildLines();
  const contentPages = Math.max(1, Math.ceil(lines.length/ROWS));
  const totalPages = Math.max(reservedPages, contentPages);
  let html="";
  for(let p=0;p<totalPages;p++){
    const pageLines = lines.slice(p*ROWS, p*ROWS+ROWS);
    let sheetHtml="";
    for(let r=0;r<ROWS;r++) sheetHtml+=rowHtml(pageLines[r], caret, r, false);
    html+=`<section class="page">
      <div class="page-head"><span class="ph-title">试 卷</span><span class="ph-no">第 ${p+1} 页</span></div>
      <div class="sheet">${sheetHtml}</div>
      <div class="page-foot">25 × 20 = 500 字（数字两位一格，标点不上行首）</div>
    </section>`;
  }
  paperWrap.innerHTML=html;
  const n=countCells(text);
  document.getElementById("statCount").textContent=n;
  document.getElementById("tbCount").textContent=n;
}

// 点击格子定位光标
paperWrap.addEventListener("click", e=>{
  const cell=e.target.closest(".cell"); if(!cell) return;
  let pos;
  if(cell.dataset.offset!==undefined) pos=parseInt(cell.dataset.offset,10);
  else pos=parseInt(cell.dataset.endofline,10);
  if(isNaN(pos)) pos=text.length;
  ghost.focus();
  ghost.setSelectionRange(pos,pos);
  render();
});

// ---------- 输入与自动保存 ----------
ghost.addEventListener("input", ()=>{
  text=ghost.value;
  render();
  clearTimeout(saveTimer);
  saveTimer=setTimeout(()=>api("/api/draft",{text}).catch(()=>{}),800);
});
ghost.addEventListener("keydown", e=>{
  // 让原生退格/方向键正常工作，渲染在 input 后刷新即可
  clearTimeout(saveTimer);
  saveTimer=setTimeout(()=>{text=ghost.value;render();api("/api/draft",{text}).catch(()=>{});},300);
});

// ---------- 历史记录 ----------
async function loadHistory(){
  const d=await (await fetch("/api/data")).json();
  text=d.draft||""; ghost.value=text;
  historyCache=d.history||[];
  renderHistory(); render();
}
function renderHistory(){
  document.getElementById("histMeta").textContent=historyCache.length?`${historyCache.length} 条`:"";
  if(!historyCache.length){
    historyList.innerHTML=`<div class="empty-tip">暂无历史记录<br>写完点「保存为历史记录」即可存档</div>`;
    return;
  }
  historyList.innerHTML=historyCache.map(h=>`
    <div class="h-item">
      <div class="h-meta"><span>${esc(h.time)}${h.label?" · "+esc(h.label):""}</span><span class="h-count">${h.count} 字</span></div>
      <div class="h-preview">${esc(h.text.slice(0,60))}${h.text.length>60?"…":""}</div>
      <div class="h-btns">
        <button data-act="view" data-id="${h.id}">查看</button>
        <button data-act="restore" data-id="${h.id}">恢复</button>
        <button class="del" data-act="del" data-id="${h.id}">删除</button>
      </div>
    </div>`).join("");
}
historyList.addEventListener("click", async e=>{
  const btn=e.target.closest("button[data-act]"); if(!btn) return;
  const id=parseInt(btn.dataset.id,10);
  const item=historyCache.find(h=>h.id===id); if(!item) return;
  const act=btn.dataset.act;
  if(act==="view"){
    modalRestoreText=item.text;
    document.getElementById("modalTitle").innerHTML=`${esc(item.time)}${item.label?" · "+esc(item.label):""} · 共 <b style="color:var(--red)">${item.count}</b> 字`;
    const body=document.getElementById("modalBody");
    body.className="body mini";
    body.innerHTML=`<div class="sheet">${previewSheet(item.text)}</div>`;
    document.getElementById("modalRestore").style.display="inline-block";
    document.getElementById("modalMask").classList.add("show");
  }else if(act==="restore"){
    if(!confirm("用这条历史覆盖当前作答区？当前未存档内容会被替换。")) return;
    ghost.value=item.text; text=item.text;
    await api("/api/draft",{text});
    render(); toast("已恢复到作答区");
  }else if(act==="del"){
    if(!confirm("确定删除这条历史记录？")) return;
    await api("/api/history/delete",{id});
    await loadHistory(); toast("已删除");
  }
});

// ---------- 工具栏按钮 ----------
document.getElementById("btnSaveHistory").addEventListener("click", async ()=>{
  if(!text.trim()){ toast("作答区还是空的"); return; }
  const label=prompt("给这条记录起个名字（可留空）：","");
  const r=await api("/api/history",{text,label:(label||"").trim()});
  if(r.ok){ await loadHistory(); toast("已保存为历史记录"); }
  else toast("保存失败：内容为空");
});
document.getElementById("btnCopy").addEventListener("click", async ()=>{
  if(!text){ toast("没有可复制的内容"); return; }
  try{ await navigator.clipboard.writeText(text); toast("已复制全文"); }
  catch(_){ ghost.value=text; ghost.select(); document.execCommand("copy"); toast("已复制全文"); }
});
document.getElementById("btnPrint").addEventListener("click", ()=>window.print());
document.getElementById("btnClear").addEventListener("click", async ()=>{
  if(!text){ toast("已经是空的"); return; }
  if(!confirm("一键清空：将删除当前作答区全部内容（历史记录不受影响），确定？")) return;
  ghost.value=""; text="";
  await api("/api/clear",{});
  render(); toast("已清空");
});
document.getElementById("btnAddPage").addEventListener("click", ()=>{ reservedPages++; render(); toast("已加一页"); });

// 弹窗
document.getElementById("modalClose").addEventListener("click",()=>document.getElementById("modalMask").classList.remove("show"));
document.getElementById("modalRestore").addEventListener("click", async ()=>{
  if(!confirm("用这条历史覆盖当前作答区？")) return;
  ghost.value=modalRestoreText; text=modalRestoreText;
  await api("/api/draft",{text});
  document.getElementById("modalMask").classList.remove("show");
  render(); toast("已恢复到作答区");
});
document.getElementById("modalMask").addEventListener("click",e=>{
  if(e.target.id==="modalMask") document.getElementById("modalMask").classList.remove("show");
});

// 启动：把焦点交给 ghost，便于直接打字
loadHistory().then(()=>{ ghost.focus(); });
</script>
</body>
</html>
"""

# ============ HTTP 处理 ============
class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def _send(self, code, payload, ctype="application/json; charset=utf-8"):
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8") if ctype.startswith("application/json") else payload
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        path = urlparse(self.path).path
        if path == "/" or path == "/index.html":
            self._send(200, HTML_PAGE.encode("utf-8"), "text/html; charset=utf-8")
        elif path == "/api/data":
            self._send(200, get_data())
        elif path == "/favicon.ico":
            self.send_response(204); self.end_headers()
        else:
            self._send(404, {"error": "not found"})

    def do_POST(self):
        path = urlparse(self.path).path
        try:
            length = int(self.headers.get("Content-Length", 0))
            raw = self.rfile.read(length) if length else b"{}"
            body = json.loads(raw.decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError):
            self._send(400, {"ok": False, "error": "bad json"})
            return

        if path == "/api/draft":
            write_draft(str(body.get("text", "")))
            self._send(200, {"ok": True})
        elif path == "/api/history":
            text = str(body.get("text", ""))
            if text.strip():
                entry = add_history(text, str(body.get("label", "")))
                self._send(200, {"ok": True, "id": entry["id"]})
            else:
                self._send(200, {"ok": False, "error": "empty"})
        elif path == "/api/history/delete":
            delete_history(body.get("id"))
            self._send(200, {"ok": True})
        elif path == "/api/clear":
            write_draft("")
            self._send(200, {"ok": True})
        else:
            self._send(404, {"ok": False})


def find_port(start=8765):
    import socket
    for port in range(start, start + 30):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            if s.connect_ex(("127.0.0.1", port)) != 0:
                return port
    return start


def main():
    ensure_dir()
    port = find_port()
    server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    url = f"http://127.0.0.1:{port}/"
    threading.Timer(0.6, lambda: webbrowser.open(url)).start()
    print(f"{APP_TITLE} 已启动：{url}")
    print("存档文件夹：" + SAVE_DIR)
    print("关闭本窗口即退出程序。")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
