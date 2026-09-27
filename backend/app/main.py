import os
import secrets
from datetime import datetime, timedelta
from fastapi import FastAPI, Request, Response, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from app.database import init_db, get_profile, save_profile, get_profile_by_token
from app.routers import resume, chat, jobs
from app.services.seed_data import init_seed_data
from app.config import DATABASE_URL

app = FastAPI(title="Offer捕手 - AI求职匹配系统", version="2.0.0")

# CORS 要允许携带 Cookie，不能用 "*" 通配
app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=r"https?://.*",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# CloudRun 网关返回的 405/401 不经过 CORSMiddleware，浏览器会因为缺 CORS 头直接报错，
# 所以在这里统一兜底，保证任何响应都带上 CORS 头
@app.middleware("http")
async def cors_headers_middleware(request: Request, call_next):
    try:
        response = await call_next(request)
    except Exception as e:
        import traceback
        traceback.print_exc()
        response = JSONResponse(
            status_code=500,
            content={"detail": str(e), "type": type(e).__name__},
        )
    origin = request.headers.get("origin")
    if origin:
        response.headers["Access-Control-Allow-Origin"] = origin
        response.headers["Access-Control-Allow-Credentials"] = "true"
        if request.method == "OPTIONS":
            response.headers["Access-Control-Allow-Methods"] = "GET, POST, PUT, DELETE, OPTIONS, PATCH"
            response.headers["Access-Control-Allow-Headers"] = "Content-Type, Authorization, X-Requested-With, Accept, Origin"
            response.headers["Access-Control-Max-Age"] = "86400"
    return response

# OPTIONS 预检请求必须显式接住，否则 CloudRun 网关会直接 405
@app.options("/{path:path}")
async def options_handler(path: str, request: Request):
    """Handle CORS preflight for all routes."""
    from fastapi.responses import Response
    resp = Response(status_code=204)
    origin = request.headers.get("origin", "*")
    resp.headers["Access-Control-Allow-Origin"] = origin
    resp.headers["Access-Control-Allow-Methods"] = "GET, POST, PUT, DELETE, OPTIONS, PATCH"
    resp.headers["Access-Control-Allow-Headers"] = "Content-Type, Authorization, X-Requested-With, Accept, Origin"
    resp.headers["Access-Control-Allow-Credentials"] = "true"
    resp.headers["Access-Control-Max-Age"] = "86400"
    return resp

app.include_router(resume.router)
app.include_router(chat.router)
app.include_router(jobs.router)

# 会话 Token 有效期 24 小时
SESSION_EXPIRY_HOURS = 24


@app.on_event("startup")
async def startup():
    from app.database import _use_mysql, _use_postgres
    init_db()
    count = init_seed_data()
    db_type = "MySQL" if _use_mysql else ("PostgreSQL" if _use_postgres else "SQLite")
    print(f"Database initialized with {count} seed jobs. Using {db_type}.")


@app.get("/api/health")
async def health_check():
    from app.database import _use_mysql, _use_postgres
    db_type = "MySQL" if _use_mysql else ("PostgreSQL" if _use_postgres else "SQLite")
    return {"status": "ok", "service": "Offer捕手 API v2.0", "db": db_type}


@app.post("/api/session/create")
async def create_session(request: Request, response: Response):
    """Create a new session and set httpOnly cookie."""
    body = await request.json()
    resume_id = body.get("resume_id", "")
    session_id = body.get("session_id", "")
    profile_data = body.get("profile", {})
    stage = body.get("stage", "S2")

    if not session_id:
        raise HTTPException(400, "session_id is required")

    session_token = secrets.token_urlsafe(48)
    expires_at = datetime.now() + timedelta(hours=SESSION_EXPIRY_HOURS)

    save_profile(session_id, resume_id, profile_data, stage, session_token, expires_at)

    # httpOnly + secure，跨站靠 samesite=none
    response.set_cookie(
        key="offer_session",
        value=session_token,
        httponly=True,
        secure=True,
        samesite="none",  # Allow cross-site requests with credentials
        max_age=SESSION_EXPIRY_HOURS * 3600,
        path="/",
    )

    return {
        "code": 0,
        "data": {
            "session_id": session_id,
        },
    }


@app.post("/api/session/verify")
async def verify_session(request: Request):
    """Verify session token from cookie and return session_id."""
    token = request.cookies.get("offer_session")
    if not token:
        raise HTTPException(401, "未登录或会话已过期")

    profile = get_profile_by_token(token)
    if not profile:
        raise HTTPException(401, "会话无效或已过期")

    return {
        "code": 0,
        "data": {
            "session_id": profile["session_id"],
            "resume_id": profile["resume_id"],
            "stage": profile["current_stage"],
        },
    }


@app.get("/api/session/state")
async def get_session_state(request: Request):
    """Get full session state via cookie (no session_id in URL)."""
    token = request.cookies.get("offer_session")
    if not token:
        raise HTTPException(401, "未登录或会话已过期")

    profile = get_profile_by_token(token)
    if not profile:
        raise HTTPException(401, "会话无效或已过期")

    from app.routers.chat import _get_components_for_stage
    from app.database import get_chat_history

    sid = profile["session_id"]
    stage = profile["current_stage"]
    p = profile["profile"]

    raw_history = get_chat_history(sid)
    messages = []
    for h in raw_history:
        msg = {"role": h["role"], "content": h["content"]}
        messages.append(msg)

    components = _get_components_for_stage(stage)

    return {
        "code": 0,
        "data": {
            "session_id": sid,
            "resume_id": profile["resume_id"],
            "stage": stage,
            "messages": messages,
            "components": components,
            "profile": p,
        },
    }


@app.get("/api/session/preview")
async def get_session_preview(request: Request):
    """Get resume preview via cookie."""
    token = request.cookies.get("offer_session")
    if not token:
        raise HTTPException(401, "未登录或会话已过期")

    profile = get_profile_by_token(token)
    if not profile:
        raise HTTPException(401, "会话无效或已过期")

    from app.database import get_resume
    from app.routers.resume import _build_preview_html
    from app.services.ai_service import mask_name, mask_phone, mask_email

    resume = get_resume(profile["resume_id"])
    if not resume:
        raise HTTPException(404, "简历不存在")

    parsed = resume["parsed"]
    basic = parsed.get("basic", {})
    masked_basic = {
        "name": mask_name(basic.get("name", "")),
        "phone": mask_phone(basic.get("phone", "")),
        "email": mask_email(basic.get("email", "")),
        "school": basic.get("school", ""),
        "major": basic.get("major", ""),
        "degree": basic.get("degree", ""),
        "graduation_year": basic.get("graduation_year", ""),
    }
    masked_parsed = {**parsed, "basic": masked_basic}
    preview_html = _build_preview_html(masked_parsed)

    return {
        "code": 0,
        "data": {
            "resume_id": resume["resume_id"],
            "parsed": masked_parsed,
            "preview_html": preview_html,
        },
    }


# 生产模式下前端构建产物直接由后端托管（CloudRun 单容器部署）
FRONTEND_DIST = os.path.join(os.path.dirname(__file__), "..", "..", "frontend", "dist")
if os.path.exists(FRONTEND_DIST):
    from fastapi.staticfiles import StaticFiles

    app.mount("/assets", StaticFiles(directory=os.path.join(FRONTEND_DIST, "assets")), name="assets")


    @app.middleware("http")
    async def spa_fallback_middleware(request: Request, call_next):
        """Middleware to serve index.html for SPA routes that don't match API or static files."""
        response = await call_next(request)

        # 前端路由（如 /chat）在服务端不存在，404 时回退到 index.html 交给前端路由处理
        if response.status_code == 404 and not request.url.path.startswith("/api"):
            import aiofiles
            from fastapi.responses import HTMLResponse
            index_path = os.path.join(FRONTEND_DIST, "index.html")
            if os.path.exists(index_path):
                async with aiofiles.open(index_path, encoding="utf-8") as f:
                    content = await f.read()
                return HTMLResponse(content=content)

        return response


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
