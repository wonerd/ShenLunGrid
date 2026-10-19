# -*- coding: utf-8 -*-
"""
申论方格纸 · 离线本地练习器
"""
import os
import sys
import json
import time
import threading
import subprocess
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


# 标点集合（与前端一致：……、—— 合占一格，其余标点各占一格）
_PUNCT = set("，。、；：！？）】」』”’…—·》〉（【「『“‘《〈,.!?;:)][(\"'<")


def _is_digit(ch):
    return ch.isdigit() or ("\uff10" <= ch <= "\uff19")


def count_cells(text):
    """按稿纸格数统计，与前端一致：数字两位一格、数字后接 . 合并、
    ：后接前引号合并、……/—— 合占一格，其余一字一格，换行不计。"""
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
                if j < n and para[j] == ".":  # 1. 数字与下脚点同格
                    j += 1
                i = j
            elif ch in ("：", ":") and i + 1 < n and para[i + 1] in ("“", "‘", '"', "'"):
                total += 1  # ：“ 合占一格
                i += 2
            elif ch in ("…", "—"):
                j = i
                while j < n and para[j] == ch:
                    j += 1
                total += 1  # …… / —— 合占一格
                i = j
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


def open_save_folder():
    """在系统文件管理器中打开存档文件夹。"""
    ensure_dir()
    if os.name == "nt":
        try:
            os.startfile(SAVE_DIR)
            return True
        except OSError:
            pass
        # 兜底：explorer 直接拉起
        try:
            subprocess.Popen(["explorer", SAVE_DIR])
            return True
        except OSError:
            return False
    try:
        if sys.platform == "darwin":
            subprocess.Popen(["open", SAVE_DIR])
        else:
            subprocess.Popen(["xdg-open", SAVE_DIR])
        return True
    except OSError:
        return False


def _decode_bytes(raw):
    """按常见编码尝试解码 txt（UTF-8 / 带 BOM / UTF-16 / GB 系列）。"""
    try:
        return raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        pass
    if raw[:2] in (b"\xff\xfe", b"\xfe\xff"):
        try:
            return raw.decode("utf-16")
        except UnicodeDecodeError:
            pass
    for enc in ("gb18030", "big5"):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", "replace")


_GUI_Q = None
_GUI_LOCK = threading.Lock()

def _gui_worker(q):
    """常驻 GUI 线程：tkinter 只在这一条线程里创建和销毁，避免线程亲和性问题。"""
    while True:
        item = q.get()
        if item is None:
            break
        fn, box = item
        try:
            box["res"] = fn()
        except BaseException as e:
            box["err"] = e
        finally:
            box["done"].set()

def _run_on_gui_thread(fn, timeout=600):
    """把 fn 交给专用 GUI 线程执行并等待结果；失败/超时都返回显式 JSON。"""
    global _GUI_Q
    import queue
    with _GUI_LOCK:
        if _GUI_Q is None:
            _GUI_Q = queue.Queue()
            threading.Thread(target=_gui_worker, args=(_GUI_Q,),
                             daemon=True, name="shenlun-gui").start()
    box = {"done": threading.Event()}
    _GUI_Q.put((fn, box))
    if not box["done"].wait(timeout):
        return {"ok": False, "canceled": True, "note": "选择窗口长时间未响应"}
    if "err" in box:
        return {"ok": False, "error": f"无法打开选择窗口：{box['err']}"}
    return box["res"]

def pick_and_load():
    """弹出系统「打开文件」对话框选 txt，读取并返回文本。取消时返回 canceled。"""
    def _do_pick():
        import tkinter as tk
        from tkinter import filedialog
        root = tk.Tk()
        root.withdraw()
        root.attributes("-topmost", True)  # 防止对话框被浏览器窗口压在下面
        try:
            return filedialog.askopenfilename(
                parent=root,
                title="选择要打开的文本文件",
                filetypes=[("文本文件", "*.txt"), ("所有文件", "*.*")],
            )
        finally:
            root.destroy()

    path = _run_on_gui_thread(_do_pick)
    if isinstance(path, dict):  # GUI 线程返回的错误/超时 JSON
        return path
    if not path:
        return {"ok": False, "canceled": True}
    try:
        with open(path, "rb") as f:
            raw = f.read()
    except OSError as e:
        return {"ok": False, "error": f"读取失败：{e}"}
    txt = _decode_bytes(raw).replace("\r\n", "\n").replace("\r", "\n")
    truncated = False
    if len(txt) > 100000:
        txt = txt[:100000]
        truncated = True
    return {"ok": True, "text": txt, "name": os.path.basename(path), "truncated": truncated}


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
/* 并入同一格的连续标点紧凑显示；三字以上再缩小 */
.cell.punct{font-size:0.92em;letter-spacing:0}
.cell.tiny{font-size:11px;letter-spacing:0;line-height:1.2}
/* 每行格子下方的空白间隔带，累计字数标在带内右侧 */
.g-gap{position:relative;height:1.15em;min-height:16px}
.g-gap .scale{position:absolute;right:2px;top:50%;transform:translateY(-50%);
  font-size:11px;color:#b08a87;font-style:italic}
.page-foot{text-align:right;font-size:11px;color:#a89e8d;margin-top:10px;letter-spacing:1px}
/* 历史弹窗里的小方格 */
.mini .g-row{margin-bottom:2px}
.mini .cell{font-size:13px;border-color:#ddd}
.mini .g-gap{height:.7em;min-height:8px}

/* 隐藏输入框（承接中文输入法）：平时藏在屏幕左上角；聚焦后移动到正在写的
   格子旁边，输入法候选窗就会跟着书写位置走，不会跑到屏幕左上角 */
#ghost{position:fixed;left:0;top:0;width:24px;height:24px;opacity:0;border:none;
  outline:none;background:transparent;font-size:18px;caret-color:transparent;
  z-index:99;padding:0;pointer-events:none}
#ghost.live{opacity:.01}

/* 历史预览/确认/文件预览 弹窗 */
#modalMask{position:fixed;inset:0;background:rgba(0,0,0,.35);display:none;
  align-items:center;justify-content:center;z-index:200}
#modalMask.show{display:flex}
.modal{width:min(920px,94vw);max-height:84vh;background:#fff;border-radius:14px;
  display:flex;flex-direction:column;overflow:hidden}
.modal.small{width:min(560px,92vw)}
.modal h3{padding:16px 20px;border-bottom:1px solid var(--line);font-size:16px}
.modal .body{padding:20px 24px;overflow-y:auto;flex:1;background:#faf7f1}
.modal .foot{padding:14px 20px;border-top:1px solid var(--line);display:flex;gap:10px;justify-content:flex-end}
/* 页内确认弹窗（替代被浏览器拦截的原生 confirm/prompt） */
#askMask{position:fixed;inset:0;background:rgba(0,0,0,.4);display:none;
  align-items:center;justify-content:center;z-index:400}
#askMask.show{display:flex}
.ask{width:min(420px,90vw);background:#fff;border-radius:12px;padding:20px 22px;
  box-shadow:0 8px 30px rgba(0,0,0,.25)}
.ask p{font-size:14px;line-height:1.7;white-space:pre-wrap}
.ask input{width:100%;margin-top:10px;border:1px solid var(--line);border-radius:8px;
  padding:8px 10px;font-size:14px;font-family:inherit}
.ask .ask-btns{display:flex;gap:10px;justify-content:flex-end;margin-top:16px}
#reviewTip{display:none;margin:10px 14px 0;padding:10px 12px;background:#fff7ed;
  border:1px solid #fed7aa;border-radius:8px;font-size:13px;color:#9a3412}
body.review-mode #reviewTip{display:block}
body.review-mode #paperWrap{pointer-events:auto}

#toast{position:fixed;left:50%;bottom:34px;transform:translateX(-50%);
  background:rgba(30,30,32,.9);color:#fff;padding:10px 18px;border-radius:8px;
  font-size:14px;opacity:0;transition:.25s;z-index:300;pointer-events:none}
#toast.show{opacity:1}
#fatal{display:none;margin:0;padding:14px 18px;background:#c0392b;color:#fff;
  font:14px/1.6 "Consolas","Microsoft YaHei",sans-serif;white-space:pre-wrap;z-index:400}
#fatal.show{display:block}

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
<div id="fatal"></div>
<script>
// 兜底：任何脚本错误都直接显示在页面顶部，避免"白屏且按钮没反应"却查不到原因
(function(){
  function show(msg){
    var el=document.getElementById("fatal");
    if(!el) return;
    el.textContent="脚本出错，功能可能不可用：\n"+msg;
    el.classList.add("show");
  }
  window.addEventListener("error",function(e){
    var m=e.message||"";
    if(e.filename) m+="  ("+e.filename.split("/").pop()+":"+e.lineno+":"+e.colno+")";
    show(m);
  });
  window.addEventListener("unhandledrejection",function(e){
    show("Promise: "+((e.reason&&(e.reason.message||e.reason))||"unknown"));
  });
})();
</script>
<!-- ===== 左侧栏 ===== -->
<aside id="sidebar">
  <div class="brand">
    <h1>申论方格纸</h1>
    <p>离线练习 · 数据保存在程序同目录</p>
  </div>
  <div id="reviewTip">阅读校对模式：内容只读，点右上角按钮切回打字模式。</div>
  <div class="side-actions">
    <button class="btn primary" id="btnSaveHistory">保存为历史记录</button>
    <button class="btn" id="btnOpenFile">打开文件…（并入作答区）</button>
    <button class="btn" id="btnOpenFolder">打开存档文件夹</button>
    <button class="btn" id="btnCopy">复制全文</button>
    <button class="btn" id="btnPrint">打印 / 另存 PDF</button>
    <button class="btn danger" id="btnClear">一键清空</button>
  </div>
  <div class="stat-card">
    <span>已写字数</span><b id="statCount">0</b>
  </div>
  <div class="side-section"><span>历史记录</span><span id="histMeta"></span></div>
  <div id="historyList"></div>
  <div class="side-foot">存档保存在程序同目录的「申论存档」文件夹：当前草稿自动存为「当前草稿.txt」。也可把 .txt 文件直接拖进方格纸打开。</div>
</aside>

<!-- ===== 右侧主区 ===== -->
<main id="main">
  <div class="toolbar">
    <span class="t-title">作答区（25 格 × 20 行 = 每页 500 字）</span>
    <span class="spacer"></span>
    <span class="t-count">当前 <b id="tbCount">0</b> 字</span>
    <button class="tbtn" id="btnMode">切到阅读校对</button>
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

<!-- 页内确认/输入弹窗 -->
<div id="askMask">
  <div class="ask">
    <p id="askText"></p>
    <input id="askInput" style="display:none">
    <div class="ask-btns">
      <button class="tbtn" id="askCancel">取消</button>
      <button class="btn primary" id="askOk" style="padding:7px 16px">确定</button>
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

// 输入法候选窗跟随：把隐藏输入框定位到当前光标所在格子旁
function positionGhost(){
  try{
    const cell = paperWrap.querySelector(".cell.caret") || paperWrap.querySelector(".cell");
    if(!cell) return;
    const cr = cell.getBoundingClientRect();
    const wr = paperWrap.getBoundingClientRect();
    let left = cr.left, top = cr.bottom - 2;
    if(left > wr.right - 34) left = wr.right - 34;
    if(left < wr.left) left = wr.left;
    if(top  > wr.bottom - 34) top = wr.bottom - 34;
    if(top  < wr.top) top = wr.top;
    ghost.style.left = left + "px";
    ghost.style.top = top + "px";
  }catch(_){}
}

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
// 全部标点
const PUNCT_ALL=new Set([...BAN_HEAD,'（','【','「','『','“','‘','《','〈','(', '[']);
// 与冒号连用合占一格的前引号（：“ 合一格）
const OPEN_Q=new Set(['“','‘','"',"'"]);
function normDigit(ch){const c=ch.codePointAt(0);return (c>=0xFF10&&c<=0xFF19)?String.fromCharCode(c-0xFEE0):ch;}

// 把一整段切成「格单元」：数字每 2 个合占一格；1. 2. 与 ：“ 合占一格；
// …… —— 连续出现合占一格；其余（。，、等）一字一格
function tokenizePara(para, base){
  const toks=[]; let i=0;
  while(i<para.length){
    const ch=para[i];
    if(DIGIT_RE.test(ch)){
      let j=i,raw="";
      while(j<para.length&&DIGIT_RE.test(para[j])){raw+=normDigit(para[j]);j++;}
      for(let k=0;k<raw.length;k+=2){toks.push({text:raw.slice(k,k+2),start:base+i+k,kind:'num'});}
      if(j<para.length&&para[j]==='.'){ // 1. 2. 数字与下脚点合占一格
        if(toks.length) toks[toks.length-1].text+='.';
        j++;
      }
      i=j;
    }else if((ch==='：'||ch===':')&&i+1<para.length&&OPEN_Q.has(para[i+1])){
      toks.push({text:ch+para[i+1],start:base+i,kind:'punct'}); // ：“ 合占一格
      i+=2;
    }else if(ch==='…'||ch==='—'){
      // 叠用符号：省略号 …… 、破折号 —— 连续出现合占一格
      let j=i; while(j<para.length&&para[j]===ch) j++;
      toks.push({text:para.slice(i,j),start:base+i,kind:'punct'});
      i=j;
    }else if(PUNCT_ALL.has(ch)){
      // 普通标点各自占一格
      toks.push({text:ch,start:base+i,kind:'punct'});
      i++;
    }else{
      toks.push({text:ch,start:base+i,kind:ch===' '?'space':'ch'});
      i++;
    }
  }
  return toks;
}

// 每行 25 格；避头点：行满时收尾标点并入上一格；开口引号/括号不悬在行尾
const OPEN_HEAD=new Set([...PUNCT_ALL].filter(c=>!BAN_HEAD.has(c)));
function buildLinesFrom(src){
  const lines=[]; let base=0;
  const paras=src.split('\n');
  for(const para of paras){
    const toks=tokenizePara(para,base);
    base+=para.length+1;
    let cur=[];
    for(const tk of toks){
      if(cur.length>=COLS){
        // 避头点：行满时收尾标点并入上一格
        if(cur.length && BAN_HEAD.has(tk.text[0])){
          cur[cur.length-1].text+=tk.text;
          cur[cur.length-1].merged=true;
        }
        else{lines.push(cur);cur=[];cur.push(tk);}
      }else{
        cur.push(tk);
        // 行尾禁则：开口引号/括号不得悬在行尾，移到下一行行首
        if(cur.length===COLS && OPEN_HEAD.has(tk.text[0])){
          cur.pop(); lines.push(cur); cur=[tk];
        }
      }
    }
    lines.push(cur);
  }
  return lines;
}
function buildLines(){ return buildLinesFrom(text); }

// 所占格数
function countCells(src){
  let n=0,base=0;
  for(const para of src.split('\n')){
    const toks=tokenizePara(para,base);
    // 与 buildLinesFrom 相同的合占规则：行满并入上一格的标点不再另占格
    base+=para.length+1;
    let cur=[];
    for(const tk of toks){
      if(cur.length>=COLS){
        if(cur.length && BAN_HEAD.has(tk.text[0])){ /* 并入上一格，不加格数 */ }
        else{ n+=cur.length; cur=[tk]; continue; }
      }else cur.push(tk);
      if(cur.length===COLS && OPEN_HEAD.has(tk.text[0])){
        cur.pop(); n+=cur.length; cur=[tk];
      }
    }
    n+=cur.length;
  }
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
    if(tk&&tk.text.length>2) cls+=" tiny";
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
      <div class="page-foot">25 × 20 = 500 字（1. 2. 与 ：“ 合占一格，数字两位一格，标点不上行首）</div>
    </section>`;
  }
  paperWrap.innerHTML=html;
  const n=countCells(text);
  document.getElementById("statCount").textContent=n;
  document.getElementById("tbCount").textContent=n;
  positionGhost();
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

// ---------- 拖拽 txt 文件到页面直接打开 ----------
function mergeLoaded(d, mode){
  if(d.error){ toast(d.error); return; }
  if(d.canceled) return;
  const t=d.text||"";
  if(mode==="replace" || !text.trim()){
    ghost.value=t; text=t;
  }else{
    const sep=text.endsWith("\n")||!text?"":"\n";
    ghost.value=text+sep+t; text=ghost.value;
  }
  ghost.setSelectionRange(text.length,text.length);
  api("/api/draft",{text}).catch(()=>{});
  render();
  toast(`已打开「${d.name||"文件"}」${d.truncated?"（超长部分已截断）":""}`);
}
// ---------- 打开文件：先弹预览窗（像新页面一样），再选「并入/替换/取消」 ----------
function openPreview(d){
  return new Promise(res=>{
    const mask=document.getElementById("modalMask");
    document.getElementById("modalTitle").innerHTML=
      `文件预览 · ${esc(d.name||"文件")} · ${d.text.length} 字`;
    const body=document.getElementById("modalBody");
    body.className="body";
    body.innerHTML=`<div style="white-space:pre-wrap;font-size:14px;line-height:1.9;
      max-height:52vh;overflow:auto;background:#fff;border:1px solid var(--line);
      border-radius:8px;padding:14px 16px">${esc(d.text.slice(0,2000))}${d.text.length>2000?"\n…（仅预览前 2000 字）":""}</div>`;
    const foot=mask.querySelector(".foot");
    foot.innerHTML=`<button class="tbtn" id="pvCancel">取消</button>
      <button class="tbtn" id="pvReplace">替换当前内容</button>
      <button class="btn primary" id="pvMerge" style="padding:7px 14px">并入作答区末尾</button>`;
    mask.classList.add("show");
    const close=()=>{ mask.classList.remove("show");
      foot.innerHTML=`<button class="tbtn" id="modalClose">关闭</button>
        <button class="btn primary" id="modalRestore" style="padding:7px 14px">恢复到作答区</button>`;
      bindModalButtons(); };
    document.getElementById("pvCancel").onclick=()=>{ close(); res(null); };
    document.getElementById("pvReplace").onclick=()=>{ close(); res("replace"); };
    document.getElementById("pvMerge").onclick=()=>{ close(); res("merge"); };
  });
}
document.getElementById("btnOpenFile").addEventListener("click", async ()=>{
  toast("在弹出的窗口中选择文件…");
  const d=await api("/api/open-file",{});
  if(d.error){ toast(d.error); return; }
  if(d.canceled) return;
  const mode=await openPreview(d);
  if(mode) mergeLoaded(d, mode);
});
document.getElementById("btnOpenFolder").addEventListener("click", async ()=>{
  const r=await api("/api/open-folder",{});
  if(!r.ok) toast("无法打开文件夹（已尝试打开「申论存档」）");
});
["dragover","drop"].forEach(ev=>paperWrap.addEventListener(ev, e=>{
  e.preventDefault();
  if(ev==="drop"){
    const f=e.dataTransfer.files&&e.dataTransfer.files[0];
    if(!f) return;
    const name=f.name||"拖入文件";
    (async ()=>{
      let t;
      try{
        if(/\.txt$/i.test(name)){
          t=await f.text();
        }else{
          const raw=new Uint8Array(await f.arrayBuffer()), head=raw.slice(0,4);
          const utf8 = head[0]===0xEF&&head[1]===0xBB&&head[2]===0xBF;
          try{
            t=new TextDecoder("utf-8",{fatal:true}).decode(utf8?raw.slice(3):raw);
          }catch(_){
            t=new TextDecoder("gb18030").decode(raw);
          }
        }
      }catch(__){ toast("无法读取拖入的文件"); return; }
      const d={ok:true,text:t.replace(/\r\n/g,"\n"),name};
      const mode=await openPreview(d);   // 拖入也先预览，再选并入/替换
      if(mode) mergeLoaded(d, mode);
    })();
  }
}));

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

ghost.addEventListener("focus", ()=>{ ghost.classList.add("live"); positionGhost(); });
ghost.addEventListener("blur",  ()=>ghost.classList.remove("live"));
ghost.addEventListener("keyup", positionGhost);
ghost.addEventListener("mouseup", positionGhost);

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
    if(!await askConfirm("用这条历史覆盖当前作答区？当前未存档内容会被替换。")) return;
    ghost.value=item.text; text=item.text;
    await api("/api/draft",{text});
    render(); toast("已恢复到作答区");
  }else if(act==="del"){
    if(!await askConfirm("确定删除这条历史记录？")) return;
    await api("/api/history/delete",{id});
    await loadHistory(); toast("已删除");
  }
});

// ---------- 页内确认/输入弹窗（替代被浏览器拦截的原生 confirm/prompt） ----------
function askConfirm(msg){
  return new Promise(res=>{
    const mask=document.getElementById("askMask");
    document.getElementById("askText").textContent=msg;
    const inp=document.getElementById("askInput");
    inp.style.display="none";
    document.getElementById("askOk").textContent="确定";
    mask.classList.add("show");
    const done=v=>{ mask.classList.remove("show");
      document.getElementById("askOk").onclick=null;
      document.getElementById("askCancel").onclick=null; res(v); };
    document.getElementById("askOk").onclick=()=>done(true);
    document.getElementById("askCancel").onclick=()=>done(false);
  });
}
function askText(msg, def){
  return new Promise(res=>{
    const mask=document.getElementById("askMask");
    document.getElementById("askText").textContent=msg;
    const inp=document.getElementById("askInput");
    inp.value=def||""; inp.style.display="block";
    document.getElementById("askOk").textContent="确定";
    mask.classList.add("show");
    setTimeout(()=>{ inp.focus(); inp.select(); },50);
    const done=v=>{ mask.classList.remove("show");
      document.getElementById("askOk").onclick=null;
      document.getElementById("askCancel").onclick=null; res(v); };
    document.getElementById("askOk").onclick=()=>done(inp.value);
    document.getElementById("askCancel").onclick=()=>done(null);
    inp.onkeydown=e=>{ if(e.key==="Enter") done(inp.value); };
  });
}

// ---------- 工具栏按钮 ----------
document.getElementById("btnSaveHistory").addEventListener("click", async ()=>{
  if(!text.trim()){ toast("作答区还是空的"); return; }
  const label=await askText("给这条记录起个名字（可留空）：","");
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
  if(!await askConfirm("一键清空：将删除当前作答区全部内容（历史记录不受影响），确定？")) return;
  ghost.value=""; text="";
  await api("/api/clear",{});
  render(); toast("已清空");
});
document.getElementById("btnAddPage").addEventListener("click", ()=>{ reservedPages++; render(); toast("已加一页"); });

// 弹窗（历史预览的关闭/恢复按钮在预览窗重建后需重新绑定）
function bindModalButtons(){
  document.getElementById("modalClose").onclick=()=>document.getElementById("modalMask").classList.remove("show");
  document.getElementById("modalRestore").onclick=async ()=>{
    if(!await askConfirm("用这条历史覆盖当前作答区？")) return;
    ghost.value=modalRestoreText; text=modalRestoreText;
    await api("/api/draft",{text});
    document.getElementById("modalMask").classList.remove("show");
    render(); toast("已恢复到作答区");
  };
}
bindModalButtons();
document.getElementById("modalMask").addEventListener("click",e=>{
  if(e.target.id==="modalMask") document.getElementById("modalMask").classList.remove("show");
});

// 心跳保活：页面开着就定期报平安（后台标签页被浏览器限流也没关系，
// 后端给了足够宽限）。页面关闭一段时间后程序自动退出。
function ping(){ try{ fetch("/api/ping",{method:"POST",body:"{}",keepalive:true}).catch(()=>{}); }catch(_){} }
ping();
setInterval(ping, 2000);
document.addEventListener("visibilitychange", ()=>{ if(!document.hidden) ping(); });
window.addEventListener("pageshow", ping);

// ---------- 模式选择：打字模式 / 阅读校对模式 ----------
let readOnlyMode = false;
function restoreModalFoot(){
  const foot = document.querySelector("#modalMask .foot");
  if(!foot) return;
  foot.innerHTML = `<button class="tbtn" id="modalClose">关闭</button>
    <button class="btn primary" id="modalRestore" style="padding:7px 14px">恢复到作答区</button>`;
  bindModalButtons();
}
function toggleMode(){
  readOnlyMode = !readOnlyMode;
  document.body.classList.toggle("review-mode", readOnlyMode);
  localStorage.setItem("sl_mode", readOnlyMode ? "review" : "typing");
  if(readOnlyMode){ ghost.blur(); }
  toast(readOnlyMode ? "已切换到阅读校对模式" : "已切换到打字模式");
}
document.getElementById("btnMode").addEventListener("click", toggleMode);
function chooseMode(){
  return new Promise(res=>{
    const saved = localStorage.getItem("sl_mode");
    if(saved === "typing" || saved === "review"){
      readOnlyMode = (saved === "review");
      document.body.classList.toggle("review-mode", readOnlyMode);
      res(); return;
    }
    const mask = document.getElementById("modalMask");
    const title = document.getElementById("modalTitle");
    const body  = document.getElementById("modalBody");
    const foot  = mask.querySelector(".foot");
    title.textContent = "请选择模式";
    body.innerHTML = `
      <p style="margin:0 0 12px;font-size:14px;color:var(--ink-2)">每次打开都会先弹这个窗口（记住选择后就不再打扰）：</p>
      <div style="display:flex;gap:14px;flex-wrap:wrap">
        <button class="btn primary" id="modeTyping" style="flex:1;min-width:180px;padding:14px">打字模式<br>
          <span style="font-size:12px;font-weight:400;color:var(--ink-2)">直接在方格纸上作答</span></button>
        <button class="btn" id="modeReview" style="flex:1;min-width:180px;padding:14px">阅读校对模式<br>
          <span style="font-size:12px;font-weight:400;color:var(--ink-2)">只看格子与统计，不能改字</span></button>
      </div>
      <label style="display:flex;gap:6px;align-items:center;margin-top:14px;font-size:13px;color:var(--ink-2)">
        <input type="checkbox" id="modeRemember" checked> 记住我的选择，下次不再询问</label>`;
    foot.innerHTML = "";
    mask.classList.add("show");
    const enter = (m)=>{
      readOnlyMode = (m === "review");
      if(document.getElementById("modeRemember").checked){
        localStorage.setItem("sl_mode", m);
      }else{
        localStorage.removeItem("sl_mode");
      }
      document.body.classList.toggle("review-mode", readOnlyMode);
      restoreModalFoot();
      mask.classList.remove("show");
      toast(readOnlyMode ? "已进入阅读校对模式（页面底部可切回打字模式）" : "已进入打字模式");
      res();
    };
    document.getElementById("modeTyping").onclick  = ()=>enter("typing");
    document.getElementById("modeReview").onclick  = ()=>enter("review");
  });
}
// 阅读校对模式下禁写：拦截输入与粘贴
["input","keydown","paste"].forEach(ev=>ghost.addEventListener(ev, e=>{
  if(readOnlyMode){ e.preventDefault(); e.stopPropagation(); }
}, true));

// 启动：先选模式，选完再把焦点交给 ghost
loadHistory().then(()=>{ chooseMode().then(()=>ghost.focus()); });
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
        elif path == "/api/open-file":
            self._send(200, pick_and_load())
        elif path == "/api/open-folder":
            self._send(200, {"ok": open_save_folder()})
        elif path == "/api/ping":
            HEARTBEAT["t"] = time.time()
            HEARTBEAT["seen"] = True
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


# 心跳：页面关闭后自动退出。宽限期足够长，刷新/最小化/后台标签页都不会误退出。
HEARTBEAT = {"t": 0.0, "seen": False}
START_AT = time.time()
GRACE = 120   # 启动后 120 秒内浏览器一直没连上 -> 认为没打开成功，退出
IDLE = 600    # 页面连上后，超过 600 秒没有任何心跳 -> 认为页面已关闭，退出


def _watchdog(url):
    retried = False
    while True:
        time.sleep(1)
        if not HEARTBEAT["seen"]:
            age = time.time() - START_AT
            if not retried and age > 12:
                retried = True
                try:
                    webbrowser.open(url)
                except Exception:
                    pass
            elif age > GRACE:
                os._exit(0)
        elif time.time() - HEARTBEAT["t"] > IDLE:
            os._exit(0)


def main():
    # --noconsole 打包后没有标准输出，print 会崩溃，这里统一丢弃
    if getattr(sys, "frozen", False) or sys.stdout is None or sys.stderr is None:
        try:
            devnull = open(os.devnull, "w", encoding="utf-8")
            if sys.stdout is None:
                sys.stdout = devnull
            if sys.stderr is None:
                sys.stderr = devnull
        except OSError:
            pass
    ensure_dir()
    port = find_port()
    url = f"http://127.0.0.1:{port}/"
    threading.Thread(target=_watchdog, args=(url,), daemon=True).start()
    server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    if os.environ.get("SHENLUN_NO_BROWSER") != "1":
        threading.Timer(0.25, lambda: webbrowser.open(url)).start()
    print(f"{APP_TITLE} 已启动：{url}")
    print("存档文件夹：" + SAVE_DIR)
    print("关闭本窗口即退出程序。")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
