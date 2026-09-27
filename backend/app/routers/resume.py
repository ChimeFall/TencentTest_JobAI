import uuid
import os
from io import BytesIO
from fastapi import APIRouter, UploadFile, File, HTTPException
from app.database import save_resume, get_resume, get_profile
from app.services.ai_service import parse_resume_text, mask_name, mask_phone, mask_email

router = APIRouter(prefix="/api/resume", tags=["resume"])

# uploads 目录是早期版本的遗留，现在 PDF 解析完就删了
UPLOAD_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)


@router.post("/upload")
async def upload_resume(file: UploadFile = File(...)):
    """Upload and parse a PDF resume."""
    if not file.filename.endswith(".pdf"):
        raise HTTPException(400, "仅支持PDF格式文件")

    resume_id = str(uuid.uuid4())

    content = await file.read()

    # 落盘一份临时文件（pdfplumber 直接从内存读，这里留文件只是方便排查问题）
    file_path = os.path.join(UPLOAD_DIR, f"{resume_id}.pdf")
    with open(file_path, "wb") as f:
        f.write(content)

    try:
        import pdfplumber
        raw_text = ""
        with pdfplumber.open(BytesIO(content)) as pdf:
            for page in pdf.pages:
                text = page.extract_text()
                if text:
                    raw_text += text + "\n"
    except Exception as e:
        raw_text = f"[PDF文本提取失败: {str(e)}]"

    if not raw_text.strip():
        raise HTTPException(400, "无法从PDF中提取文本，请确保PDF包含可选择的文字")

    parsed = await parse_resume_text(raw_text)

    # 展示前先脱敏，库里留原文（后续 ATS 分析要用完整信息）
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

    # 只存提取后的文本和解析结果，PDF 二进制不落库
    save_resume(resume_id, raw_text, parsed)

    masked_parsed = {
        **parsed,
        "basic": masked_basic,
    }

    preview_html = _build_preview_html(masked_parsed)

    # 临时文件用完即删
    try:
        os.remove(file_path)
    except Exception:
        pass

    return {
        "code": 0,
        "data": {
            "resume_id": resume_id,
            "parsed": masked_parsed,
            "preview_html": preview_html,
        },
    }


@router.get("/preview/{session_id}")
async def get_resume_preview(session_id: str):
    """Get resume preview by session_id (for recovering state after navigation)."""
    profile = get_profile(session_id)
    if not profile:
        raise HTTPException(404, "会话不存在")

    resume = get_resume(profile["resume_id"])
    if not resume:
        raise HTTPException(404, "简历不存在")

    parsed = resume["parsed"]
    # 预览页也要脱敏后再渲染
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


def _build_preview_html(parsed: dict) -> str:
    """Build HTML preview string for frontend rendering."""
    basic = parsed.get("basic", {})
    skills = parsed.get("skills", [])
    experiences = parsed.get("experiences", [])
    projects = parsed.get("projects", [])
    self_eval = parsed.get("self_eval", "")

    skills_tags = " ".join([f'<span class="skill-tag">{s}</span>' for s in skills])

    exp_html = ""
    for exp in experiences:
        tech_tags = " ".join([f'<span class="skill-tag">{t}</span>' for t in exp.get("tech_stack", [])])
        exp_html += f"""
        <div class="timeline-item">
            <div class="timeline-dot"></div>
            <div class="timeline-content">
                <div class="exp-header">
                    <span class="exp-type">{exp.get('type', '')}</span>
                    <span class="exp-company">{exp.get('company', '')}</span>
                    <span class="exp-role">{exp.get('role', '')}</span>
                </div>
                <p>{exp.get('description', '')}</p>
                <div class="tech-tags">{tech_tags}</div>
            </div>
        </div>"""

    proj_html = ""
    for proj in projects:
        proj_html += f"""
        <div class="project-item">
            <div class="project-name">{proj.get('name', '')}</div>
            <p>{proj.get('description', '')}</p>
        </div>"""

    return f"""<div class="resume-preview">
    <div class="preview-section">
        <h3>基本信息</h3>
        <div class="basic-grid">
            <div class="basic-item"><span>姓名</span><span>{basic.get('name', '-')}</span></div>
            <div class="basic-item"><span>手机</span><span>{basic.get('phone', '-')}</span></div>
            <div class="basic-item"><span>邮箱</span><span>{basic.get('email', '-')}</span></div>
            <div class="basic-item"><span>学校</span><span>{basic.get('school', '-')}</span></div>
            <div class="basic-item"><span>专业</span><span>{basic.get('major', '-')}</span></div>
            <div class="basic-item"><span>学历</span><span>{basic.get('degree', '-')}</span></div>
            <div class="basic-item"><span>毕业年份</span><span>{basic.get('graduation_year', '-')}</span></div>
        </div>
    </div>
    <div class="preview-section">
        <h3>技能</h3>
        <div class="skill-list">{skills_tags}</div>
    </div>
    <div class="preview-section">
        <h3>经历</h3>
        <div class="timeline">{exp_html}</div>
    </div>
    <div class="preview-section">
        <h3>项目</h3>
        {proj_html}
    </div>
    <div class="preview-section">
        <h3>自我评价</h3>
        <p class="self-eval">{self_eval}</p>
    </div>
</div>"""
