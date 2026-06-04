"""
Sakura Backend — 访问分析 + 轻量CMS + 文件托管
FastAPI + SQLite, 专为单服务器部署优化
"""

import sqlite3, os, time, hashlib
from datetime import datetime
from pathlib import Path
from fastapi import FastAPI, Request, UploadFile, File, HTTPException
from fastapi.responses import JSONResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
import uvicorn

app = FastAPI(title="Sakura Backend")

BASE = Path(__file__).parent
DB = BASE / "data.db"
UPLOADS = BASE / "uploads"
UPLOADS.mkdir(exist_ok=True)

ADMIN_PASSWORD = os.getenv("ADMIN_PASS", "sakura2026")

# ==== Database ====

def get_db():
    db = sqlite3.connect(str(DB))
    db.row_factory = sqlite3.Row
    return db

def init_db():
    db = get_db()
    db.executescript("""
        CREATE TABLE IF NOT EXISTS visits (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            path TEXT, ip TEXT, ua TEXT, referer TEXT,
            country TEXT, created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS articles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT, slug TEXT UNIQUE, content TEXT, excerpt TEXT,
            published INTEGER DEFAULT 1,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS files (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            filename TEXT, original_name TEXT, size INTEGER,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS contacts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT, email TEXT, message TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        );
        CREATE INDEX IF NOT EXISTS idx_visits_created ON visits(created_at);
        CREATE INDEX IF NOT EXISTS idx_visits_path ON visits(path);
    """)
    db.commit()
    db.close()

init_db()

# ==== Auth ====

def check_auth(request: Request):
    token = request.cookies.get("admin_token", "")
    return hashlib.sha256(ADMIN_PASSWORD.encode()).hexdigest() == token

# ==== Analytics Middleware ====

@app.middleware("http")
async def track_visit(request: Request, call_next):
    if not request.url.path.startswith("/api/") and not request.url.path.startswith("/admin/"):
        try:
            db = get_db()
            db.execute("INSERT INTO visits (path, ip, ua, referer) VALUES (?,?,?,?)",
                       (request.url.path,
                        request.client.host if request.client else "unknown",
                        request.headers.get("user-agent", "")[:500],
                        request.headers.get("referer", "")[:500]))
            db.commit()
            db.close()
        except:
            pass
    response = await call_next(request)
    return response

# ==== Static Files ====
app.mount("/uploads", StaticFiles(directory=str(UPLOADS)), name="uploads")

# ==== Analytics API ====

@app.post("/api/analytics/hit")
async def record_hit(request: Request):
    """记录页面访问（前端 JS 主动上报）"""
    try:
        data = await request.json()
        db = get_db()
        db.execute("INSERT INTO visits (path, ip, ua, referer) VALUES (?,?,?,?)",
                   (data.get("path", "/"),
                    request.client.host if request.client else "unknown",
                    request.headers.get("user-agent", "")[:500],
                    data.get("ref", "")[:500]))
        db.commit()
        db.close()
    except:
        pass
    return {"ok": True}

@app.get("/api/analytics/summary")
def analytics_summary():
    db = get_db()
    today = datetime.now().strftime("%Y-%m-%d")
    
    total_pv = db.execute("SELECT COUNT(*) as c FROM visits").fetchone()["c"]
    today_pv = db.execute("SELECT COUNT(*) as c FROM visits WHERE date(created_at)=?", (today,)).fetchone()["c"]
    
    total_uv = db.execute("SELECT COUNT(DISTINCT ip) as c FROM visits").fetchone()["c"]
    today_uv = db.execute("SELECT COUNT(DISTINCT ip) as c FROM visits WHERE date(created_at)=?", (today,)).fetchone()["c"]
    
    top_pages = [dict(r) for r in db.execute(
        "SELECT path, COUNT(*) as views FROM visits GROUP BY path ORDER BY views DESC LIMIT 10"
    ).fetchall()]
    
    hourly = [dict(r) for r in db.execute("""
        SELECT strftime('%H', created_at) as hour, COUNT(*) as views
        FROM visits WHERE date(created_at)=?
        GROUP BY hour ORDER BY hour
    """, (today,)).fetchall()]
    
    db.close()
    return {"total_pv": total_pv, "today_pv": today_pv, "total_uv": total_uv, "today_uv": today_uv, "top_pages": top_pages, "hourly": hourly}

# ==== Articles API ====

@app.get("/api/articles")
def list_articles():
    db = get_db()
    rows = [dict(r) for r in db.execute(
        "SELECT id, title, slug, excerpt, created_at FROM articles WHERE published=1 ORDER BY created_at DESC"
    ).fetchall()]
    db.close()
    return rows

@app.get("/api/articles/{slug}")
def get_article(slug: str):
    db = get_db()
    row = db.execute("SELECT * FROM articles WHERE slug=? AND published=1", (slug,)).fetchone()
    db.close()
    if not row:
        raise HTTPException(404, "Not found")
    return dict(row)

# ==== Admin API ====

def verify_admin(request: Request):
    if not check_auth(request):
        raise HTTPException(401, "Unauthorized")

@app.post("/api/admin/login")
async def admin_login(request: Request):
    data = await request.json()
    if data.get("password") == ADMIN_PASSWORD:
        token = hashlib.sha256(ADMIN_PASSWORD.encode()).hexdigest()
        resp = JSONResponse({"ok": True})
        resp.set_cookie("admin_token", token, httponly=True, max_age=86400*30)
        return resp
    raise HTTPException(401, "Wrong password")

@app.get("/api/admin/articles")
def admin_articles(request: Request):
    verify_admin(request)
    db = get_db()
    rows = [dict(r) for r in db.execute("SELECT * FROM articles ORDER BY id DESC").fetchall()]
    db.close()
    return rows

@app.post("/api/admin/articles")
async def create_article(request: Request):
    verify_admin(request)
    data = await request.json()
    db = get_db()
    try:
        db.execute("INSERT INTO articles (title, slug, excerpt, content) VALUES (?,?,?,?)",
                   (data["title"], data["slug"], data.get("excerpt", ""), data["content"]))
        db.commit()
        return {"ok": True}
    except sqlite3.IntegrityError:
        raise HTTPException(400, "Slug already exists")
    finally:
        db.close()

@app.put("/api/admin/articles/{id}")
async def update_article(id: int, request: Request):
    verify_admin(request)
    data = await request.json()
    db = get_db()
    db.execute("UPDATE articles SET title=?, slug=?, excerpt=?, content=?, updated_at=CURRENT_TIMESTAMP WHERE id=?",
               (data["title"], data["slug"], data.get("excerpt", ""), data["content"], id))
    db.commit()
    db.close()
    return {"ok": True}

@app.delete("/api/admin/articles/{id}")
def delete_article(id: int, request: Request):
    verify_admin(request)
    db = get_db()
    db.execute("DELETE FROM articles WHERE id=?", (id,))
    db.commit()
    db.close()
    return {"ok": True}

@app.post("/api/admin/upload")
async def upload_file(request: Request, file: UploadFile = File(...)):
    verify_admin(request)
    safe_name = f"{int(time.time())}_{file.filename}"
    path = UPLOADS / safe_name
    content = await file.read()
    path.write_bytes(content)
    
    db = get_db()
    db.execute("INSERT INTO files (filename, original_name, size) VALUES (?,?,?)",
               (safe_name, file.filename, len(content)))
    db.commit()
    db.close()
    return {"url": f"/uploads/{safe_name}"}

@app.get("/api/admin/files")
def list_files(request: Request):
    verify_admin(request)
    db = get_db()
    rows = [dict(r) for r in db.execute("SELECT * FROM files ORDER BY id DESC").fetchall()]
    db.close()
    return rows

# ==== Contact API ====

@app.post("/api/contact")
async def submit_contact(request: Request):
    """提交联系表单留言"""
    try:
        data = await request.json()
        db = get_db()
        db.execute("INSERT INTO contacts (name, email, message) VALUES (?,?,?)",
                   (data.get("name", "")[:100],
                    data.get("email", "")[:200],
                    data.get("message", "")[:2000]))
        db.commit()
        db.close()
        return {"ok": True}
    except Exception as e:
        raise HTTPException(400, "提交失败，请稍后再试")

@app.get("/api/admin/contacts")
def list_contacts(request: Request):
    verify_admin(request)
    db = get_db()
    rows = [dict(r) for r in db.execute("SELECT * FROM contacts ORDER BY id DESC").fetchall()]
    db.close()
    return rows

# ==== Admin HTML ====

@app.get("/admin", response_class=HTMLResponse)
def admin_page():
    return HTMLResponse("""
<!DOCTYPE html><html lang="zh"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Sakura Admin</title>
<style>
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:system-ui,sans-serif;background:#0a0a1a;color:#ddd;padding:2rem}
h1{color:#8b5cf6;margin-bottom:1rem}
.tabs{display:flex;gap:.5rem;margin-bottom:2rem}
.tab{padding:.5rem 1.5rem;border:1px solid #333;border-radius:8px;cursor:pointer;background:none;color:#aaa}
.tab.active{background:#8b5cf6;color:#fff;border-color:#8b5cf6}
.login{max-width:300px;margin:5rem auto;text-align:center}
.login input{width:100%;padding:.75rem;margin-bottom:1rem;background:#111;border:1px solid #333;border-radius:8px;color:#fff}
.login button{padding:.75rem 2rem;background:#8b5cf6;border:none;border-radius:8px;color:#fff;cursor:pointer}
.panel{display:none}
.panel.active{display:block}
.card{background:#111;border:1px solid #222;border-radius:12px;padding:1.5rem;margin-bottom:1rem}
.stats-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:1rem;margin-bottom:2rem}
.stat{background:#111;border:1px solid #222;border-radius:12px;padding:1rem;text-align:center}
.stat .num{font-size:2rem;color:#8b5cf6;font-weight:bold}
.stat .label{font-size:.75rem;color:#666;margin-top:.25rem}
table{width:100%;border-collapse:collapse}
th,td{padding:.75rem;text-align:left;border-bottom:1px solid #222;font-size:.875rem}
th{color:#666}
.btn{padding:.25rem .75rem;border:1px solid #333;border-radius:6px;background:none;color:#aaa;cursor:pointer;margin-right:.25rem}
.btn:hover{border-color:#8b5cf6;color:#8b5cf6}
.btn.danger:hover{border-color:#e74c3c;color:#e74c3c}
form label{display:block;margin:.75rem 0 .25rem;color:#888;font-size:.875rem}
form input,form textarea{width:100%;padding:.5rem;background:#0a0a0a;border:1px solid #222;border-radius:6px;color:#ddd;font-size:.875rem}
form textarea{min-height:200px;resize:vertical}
form button{padding:.75rem 2rem;background:#8b5cf6;border:none;border-radius:8px;color:#fff;cursor:pointer;margin-top:1rem}
</style></head><body>
<div class="login" id="login">
<h1 style="color:#8b5cf6">Sakura Admin</h1>
<input type="password" id="pass" placeholder="密码"><br>
<button onclick="login()">登录</button>
</div>
<div id="app" style="display:none">
<h1>Sakura Admin</h1>
<div class="tabs">
<button class="tab active" onclick="switchTab('analytics')">数据分析</button>
<button class="tab" onclick="switchTab('articles')">文章管理</button>
<button class="tab" onclick="switchTab('new')">新建文章</button>
<button class="tab" onclick="switchTab('files')">文件管理</button>
</div>
<div class="panel active" id="analytics">
<div class="stats-grid" id="stats"></div>
<h3>热门页面</h3><table id="toppages"><tbody></tbody></table>
</div>
<div class="panel" id="articles"><table id="articleTable"><thead><tr><th>编号</th><th>标题</th><th>日期</th><th>操作</th></tr></thead><tbody></tbody></table></div>
<div class="panel" id="new"><h3 id="editTitle">新建文章</h3>
<form id="articleForm"><input type="hidden" id="editId"><label>标题</label><input id="title" required><label>别名</label><input id="slug" required><label>摘要</label><input id="excerpt"><label>内容 (HTML)</label><textarea id="content" required></textarea><button type="submit">保存</button></form></div>
<div class="panel" id="files"><h3>上传文件</h3><input type="file" id="fileInput"><button onclick="uploadFile()">上传</button><table id="fileTable" style="margin-top:1rem"><thead><tr><th>文件名</th><th>大小</th><th>链接</th></tr></thead><tbody></tbody></table></div>
</div>
<script>
let TOKEN="";
function api(path,opt={}){return fetch(path,{...opt,credentials:'same-origin'}).then(r=>r.ok?r.json():r.json().then(e=>{throw e})).catch(e=>{if(e.error===alert(e.error),401===e.statusCode||'Unauthorized'===e.detail)document.getElementById('login').style.display='block',document.getElementById('app').style.display='none'})}
async function login(){let r=await fetch('/api/admin/login',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({password:document.getElementById('pass').value}),credentials:'same-origin'});if(r.ok){document.getElementById('login').style.display='none';document.getElementById('app').style.display='block';loadAll()}else alert('密码错误')}
function loadAll(){loadAnalytics();loadArticles();loadFiles()}
async function loadAnalytics(){let d=await api('/api/analytics/summary');document.getElementById('stats').innerHTML=`<div class="stat"><div class="num">${d.total_pv}</div><div class="label">总浏览量</div></div><div class="stat"><div class="num">${d.total_uv}</div><div class="label">总访客</div></div><div class="stat"><div class="num">${d.today_pv}</div><div class="label">今日浏览</div></div><div class="stat"><div class="num">${d.today_uv}</div><div class="label">今日访客</div></div>`;document.getElementById('toppages').innerHTML=d.top_pages.map(p=>`<tr><td>${p.path}</td><td>${p.views}</td></tr>`).join('')}
async function loadArticles(){let rows=await api('/api/admin/articles');document.querySelector('#articleTable tbody').innerHTML=rows.map(r=>`<tr><td>${r.id}</td><td>${r.title}</td><td>${r.created_at?.slice(0,10)}</td><td><button class="btn" onclick="editArticle(${r.id})">编辑</button><button class="btn danger" onclick="delArticle(${r.id})">删除</button></td></tr>`).join('')}
async function editArticle(id){let rows=await api('/api/admin/articles');let r=rows.find(x=>x.id===id);if(!r)return;switchTab('new');document.getElementById('editTitle').textContent='编辑文章';document.getElementById('editId').value=r.id;document.getElementById('title').value=r.title;document.getElementById('slug').value=r.slug;document.getElementById('excerpt').value=r.excerpt||'';document.getElementById('content').value=r.content}
async function delArticle(id){if(!confirm('确认删除？'))return;await api('/api/admin/articles/'+id,{method:'DELETE'});loadArticles()}
document.getElementById('articleForm').onsubmit=async function(e){e.preventDefault();let id=document.getElementById('editId').value;let body={title:document.getElementById('title').value,slug:document.getElementById('slug').value,excerpt:document.getElementById('excerpt').value,content:document.getElementById('content').value};if(id)await api('/api/admin/articles/'+id,{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});else await api('/api/admin/articles',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});this.reset();document.getElementById('editId').value='';document.getElementById('editTitle').textContent='新建文章';switchTab('articles');loadArticles()}
async function uploadFile(){let f=document.getElementById('fileInput').files[0];if(!f)return;let fd=new FormData();fd.append('file',f);let r=await api('/api/admin/upload',{method:'POST',body:fd});loadFiles();alert('链接: '+r.url)}
async function loadFiles(){let rows=await api('/api/admin/files');document.querySelector('#fileTable tbody').innerHTML=rows.map(r=>`<tr><td>${r.original_name}</td><td>${(r.size/1024).toFixed(1)}KB</td><td><a href="${'/uploads/'+r.filename}" target="_blank">${'/uploads/'+r.filename}</a></td></tr>`).join('')}
function switchTab(name){document.querySelectorAll('.tab').forEach(b=>b.classList.remove('active'));event.target.classList.add('active');document.querySelectorAll('.panel').forEach(p=>p.classList.remove('active'));document.getElementById(name).classList.add('active');if(name==='articles')loadArticles();if(name==='files')loadFiles();if(name==='analytics')loadAnalytics()}
</script></body></html>""")

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
