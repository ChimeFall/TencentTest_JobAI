from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from app.database import get_all_jobs, get_profile, get_resume, get_job
from app.services.matching_engine import (
    compute_match_percentage, compute_job_radar,
    compute_extra_interest_bonus, growth_fit,
)
from app.services.ai_service import ats_analyze
from app.services.industry_matcher import get_industry_similarity

router = APIRouter(prefix="/api", tags=["jobs"])


class MatchRequest(BaseModel):
    session_id: str
    keywords: list[str] = []
    limit: int = 10
    page: int = 1


class ATSRequest(BaseModel):
    resume_id: str
    job_id: str


@router.post("/jobs/match")
async def match_jobs(req: MatchRequest):
    """Match jobs based on user profile and return top matches."""
    profile_data = get_profile(req.session_id)
    if not profile_data:
        raise HTTPException(404, "会话不存在")

    profile = profile_data["profile"]
    user_radar_base = profile.get("radar_user", {})
    weight_order = profile.get("weight_order", ["成长", "兴趣", "技能", "薪资", "行业", "地域"])
    extra_keywords = profile.get("preferences", {}).get("extra_keywords", [])

    if not user_radar_base:
        raise HTTPException(400, "用户画像尚未生成，请先完成对话采集")

    # 行业分不在这里定死，下面逐个岗位算用户 Top3 行业和该岗位的相似度
    user_industries = profile.get("user_industries", [])

    jobs = get_all_jobs()

    # 关键词过滤：标题或 JD 命中即保留；一个都没命中就当作没过滤，避免空列表
    if req.keywords:
        filtered_jobs = []
        for job in jobs:
            jd_lower = job["jd_text"].lower()
            title_lower = job["title"].lower()
            for kw in req.keywords:
                if kw.lower() in jd_lower or kw.lower() in title_lower:
                    filtered_jobs.append(job)
                    break
        jobs = filtered_jobs if filtered_jobs else jobs

    matches = []
    for job in jobs:
        user_radar = dict(user_radar_base)
        if user_industries:
            job_industry = job.get("industry", "")
            industry_sim = get_industry_similarity(user_industries, job_industry)
            user_radar["行业"] = industry_sim

        # 用户填了补充兴趣时岗位雷达要重算（兴趣维依赖关键词），否则直接用预计算的
        if extra_keywords:
            job_radar = compute_job_radar(job, extra_keywords)
        else:
            job_radar = job.get("radar_json", {})
            if not job_radar:
                job_radar = compute_job_radar(job)

        # 成长维用非对称 fit 分参与匹配
        match_pct, dim_match, reason, gf_score = compute_match_percentage(
            user_radar, job_radar, weight_order
        )

        # 命中补充兴趣关键词的话，在理由开头交代一下，不然加成显得莫名其妙
        if extra_keywords:
            bonus, matched_kw = compute_extra_interest_bonus(extra_keywords, job)
            if matched_kw:
                kw_str = "、".join(matched_kw)
                reason = f"该岗位与你的补充兴趣「{kw_str}」匹配，" + reason

        matches.append({
            "job_id": job["job_id"],
            "title": job["title"],
            "company": job["company"],
            "salary_min": job["salary_min"],
            "salary_max": job["salary_max"],
            "city": job["city"],
            "industry": job["industry"],
            "company_size": job.get("company_size", ""),
            "level": job.get("level", ""),
            "platform": job.get("platform", ""),
            "skills_required": job.get("skills_required", []),
            "jd_text": job.get("jd_text", ""),
            "match_percentage": match_pct,
            "radar_user": user_radar,
            "radar_job": job_radar,
            "dimension_match": dim_match,
            "growth_fit": gf_score,
            "reason": reason,
        })

    # 只保留 50 分以上的，低于这个数的基本是凑数
    matches = [m for m in matches if m["match_percentage"] > 50]

    matches.sort(key=lambda x: x["match_percentage"], reverse=True)

    page = getattr(req, "page", 1)
    page_size = req.limit
    total = len(matches)
    total_pages = max(1, (total + page_size - 1) // page_size)
    start = (page - 1) * page_size
    paged = matches[start:start + page_size]

    return {
        "code": 0,
        "data": {
            "matches": paged,
            "total": total,
            "page": page,
            "page_size": page_size,
            "total_pages": total_pages,
        },
    }


@router.post("/ats/analyze")
async def analyze_ats(req: ATSRequest):
    """Analyze resume against a specific job for ATS optimization."""
    resume = get_resume(req.resume_id)
    if not resume:
        raise HTTPException(404, "简历不存在")

    job = get_job(req.job_id)
    if not job:
        raise HTTPException(404, "岗位不存在")

    result = await ats_analyze(resume["raw_text"], job["jd_text"])

    return {
        "code": 0,
        "data": result,
    }
