import math
import re
from app.config import (
    RANK_WEIGHTS, SIX_DIMENSIONS, SALARY_SCORE_MAP,
    DEGREE_SCORE, CITY_TIER_SCORE, BIG_COMPANY_KEYWORDS,
)


# ═══════════════════════════════════════════════════════════
#  成长维：非对称"托举"公式
# ═══════════════════════════════════════════════════════════

def growth_fit(user_potential: float, job_space: float) -> float:
    """
    成长维度非对称匹配：岗位空间对用户潜力的托举适配度。

    - 当 job_space >= user_potential: 岗位能托住用户，理想是略大，过大略有惩罚
    - 当 job_space < user_potential: 岗位空间不足，用户会触顶，按比例下降，保底0.2

    Returns 0.2 ~ 1.0
    """
    if job_space >= user_potential:
        gap = job_space - user_potential
        penalty = min(gap * 0.4, 0.25)  # max penalty 0.25
        return round(1.0 - penalty, 2)
    else:
        return round(max(0.2, job_space / user_potential), 2)


def growth_fit_reason(fit_score: float) -> str:
    """Generate human-readable reason for growth fit score."""
    if fit_score >= 0.9:
        return "该岗位成长空间充足，能充分托举你的发展潜力"
    elif fit_score >= 0.6:
        return "岗位成长空间与你的潜力基本匹配"
    else:
        return "岗位成长空间有限，你的潜力可能无法充分释放"


# ═══════════════════════════════════════════════════════════
#  用户雷达
# ═══════════════════════════════════════════════════════════

def compute_user_radar(resume: dict, industry_score: float, interest_score: float,
                       preferences: dict) -> dict:
    """Compute user's six-dimension radar scores.

    NOTE: The '行业' value here is the legacy "user-industry-fit" score.
    It will be overridden per-job in match_jobs using industry similarity.
    The radar displayed to the user should show this as a general indicator.
    """
    skills = resume.get("skills", [])
    basic = resume.get("basic", {})
    experiences = resume.get("experiences", [])
    degree = basic.get("degree", "本科")

    skill_score = min(len(skills) / 10, 1.0)

    # 行业分先用 DeepSeek 给的笼统分顶着，匹配时会按岗位行业重算
    industry_dim = industry_score

    # 期望薪资只是个粗略映射，用户填的范围本身不代表"薪资能力"
    salary_range = preferences.get("salary_range", "")
    salary_score = 0.6
    if "5k" in salary_range or "10k" in salary_range:
        salary_score = SALARY_SCORE_MAP.get(10000, 0.4)
    elif "15k" in salary_range or "20k" in salary_range:
        salary_score = SALARY_SCORE_MAP.get(15000, 0.6)
    elif "25k" in salary_range:
        salary_score = 1.0

    # 选的城市越多视为地域上越灵活
    cities = preferences.get("cities", [])
    region_score = min(len(cities) / 5, 1.0) if cities else 0.5

    # 成长潜力：学历打底，有大厂经历加 20%
    degree_score = DEGREE_SCORE.get(degree, 0.6)
    has_big_company = any(
        any(kw in exp.get("company", "") for kw in BIG_COMPANY_KEYWORDS)
        for exp in experiences
    )
    growth_score = degree_score * (1.2 if has_big_company else 1.0)
    growth_score = min(growth_score, 1.0)

    interest_dim = interest_score

    return {
        "技能": round(skill_score, 2),
        "行业": round(industry_dim, 2),
        "薪资": round(salary_score, 2),
        "地域": round(region_score, 2),
        "成长": round(growth_score, 2),
        "兴趣": round(interest_dim, 2),
    }


# ═══════════════════════════════════════════════════════════
#  岗位雷达：成长维存原始分，匹配时才过 growth_fit
# ═══════════════════════════════════════════════════════════

def compute_job_radar(job: dict, extra_keywords: list[str] = None) -> dict:
    """Compute job's six-dimension radar scores.

    Args:
        job: Job document from database.
        extra_keywords: User's extra interest keywords for interest dimension matching.

    Key design decisions:
    - 行业 (industry): Fixed to 1.0 — the job always fully represents its own industry.
      User-side industry is computed per-job using industry similarity matching.
    - 成长 (growth): Raw value for radar display; actual matching uses growth_fit().
    """
    skills_required = job.get("skills_required", [])
    salary_min = job.get("salary_min", 0)
    salary_max = job.get("salary_max", 0)
    city_tier = job.get("city_tier", 2)
    company_size = job.get("company_size", "")
    level = job.get("level", "初级")

    skill_score = min(len(skills_required) / 10, 1.0)

    # 岗位对自己所属行业永远是满分，用户侧的分在匹配时按相似度算
    industry_score = 1.0

    avg_salary = (salary_min + salary_max) / 2 if salary_max > 0 else salary_min
    salary_score = min(avg_salary / 25000, 1.0)

    region_score = CITY_TIER_SCORE.get(city_tier, 0.8)

    # 成长空间：公司规模 × 岗位级别。这里存原始分给雷达图用
    size_score = 0.8
    if any(kw in company_size for kw in ["1000", "10000", "上市", "大型"]):
        size_score = 1.0
    elif any(kw in company_size for kw in ["100", "500", "中型"]):
        size_score = 0.8
    elif any(kw in company_size for kw in ["50", "小型", "初创"]):
        size_score = 0.6

    level_map = {"高级": 1.0, "中级": 0.8, "初级": 0.7, "实习": 0.5}
    level_score = level_map.get(level, 0.7)

    growth_score = size_score * level_score

    # 没有补充关键词时兴趣维只能给个中间值
    if extra_keywords:
        interest_score = _compute_keyword_interest_score(extra_keywords, job)
    else:
        interest_score = 0.5

    return {
        "技能": round(skill_score, 2),
        "行业": round(industry_score, 2),
        "薪资": round(salary_score, 2),
        "地域": round(region_score, 2),
        "成长": round(growth_score, 2),
        "兴趣": round(interest_score, 2),
    }


def _compute_keyword_interest_score(keywords: list[str], job: dict) -> float:
    """Compute interest dimension score based on how well job matches user's interest keywords.

    Returns 0.0~1.0 where:
    - 0.9~1.0: Title directly matches keywords (e.g. "数据分析师" vs ["数据分析"])
    - 0.6~0.8: JD/skills contain keywords
    - 0.3~0.5: Weak or no match
    """
    if not keywords:
        return 0.5

    title = job.get("title", "")
    jd_text = job.get("jd_text", "")
    skills = job.get("skills_required", [])
    industry = job.get("industry", "")

    title_lower = title.lower()
    jd_lower = jd_text.lower()
    skills_lower = ' '.join(skills).lower()
    industry_lower = industry.lower()

    max_score = 0.3  # base score for no match
    for kw in keywords:
        kw_lower = kw.lower()

        # 标题完整命中关键词，权重最高
        if kw_lower in title_lower:
            max_score = max(max_score, 0.95)
            continue
        # 标题命中 2 字子串也算
        if len(kw) >= 2:
            for i in range(len(kw_lower) - 1):
                sub = kw_lower[i:i+2]
                if sub in title_lower:
                    max_score = max(max_score, 0.85)
                    break

        # JD 里命中
        if kw_lower in jd_lower:
            max_score = max(max_score, 0.75)
            continue
        if len(kw) >= 2:
            for i in range(len(kw_lower) - 1):
                sub = kw_lower[i:i+2]
                if sub in jd_lower:
                    max_score = max(max_score, 0.65)
                    break

        # 技能列表里命中
        if kw_lower in skills_lower:
            max_score = max(max_score, 0.70)
            continue

        # 行业名里命中
        if len(kw) >= 2 and kw_lower in industry_lower:
            max_score = max(max_score, 0.55)

    return min(max_score, 1.0)


# ═══════════════════════════════════════════════════════════
#  匹配度计算（成长维走非对称 fit，其余对称重叠）
# ═══════════════════════════════════════════════════════════

def compute_match_percentage(user_radar: dict, job_radar: dict,
                             weight_order: list[str],
                             growth_fit_override: float = None) -> tuple[float, dict, str, float]:
    """Compute match percentage using six-dimension overlap algorithm.

    Growth dimension uses the asymmetric growth_fit() formula instead of
    symmetric min/max overlap. All other dimensions use symmetric overlap.

    Args:
        user_radar: User's six-dimension scores.
        job_radar: Job's six-dimension scores.
        weight_order: User's dimension priority order.
        growth_fit_override: If provided, use this as the growth fit score
            instead of computing from radar values.

    Returns:
        (match_pct, dimension_match, reason, growth_fit_value)
    """
    # 按名次展开成 维度→权重 的映射
    weight_map = {}
    for i, dim in enumerate(weight_order):
        if i < len(RANK_WEIGHTS):
            weight_map[dim] = RANK_WEIGHTS[i]

    # 用户没排的维度给个默认权重，别让分子分母对不上
    default_weights = {"技能": 0.20, "行业": 0.15, "薪资": 0.15, "地域": 0.15, "成长": 0.20, "兴趣": 0.15}
    for dim in SIX_DIMENSIONS:
        if dim not in weight_map:
            weight_map[dim] = default_weights.get(dim, 0.1)

    # 成长维先算出 fit 分，下面循环里直接用
    u_growth = user_radar.get("成长", 0.5)
    j_growth = job_radar.get("成长", 0.5)
    if growth_fit_override is not None:
        gf_score = growth_fit_override
    else:
        gf_score = growth_fit(u_growth, j_growth)

    numerator = 0.0
    denominator = 0.0
    dimension_match = {}

    for dim in SIX_DIMENSIONS:
        u_i = user_radar.get(dim, 0.5)
        j_i = job_radar.get(dim, 0.5)
        w_i = weight_map.get(dim, 0.1)

        if dim == "成长":
            # 成长维走非对称 fit 分，分母按满分 1.0 算
            numerator += gf_score * w_i
            denominator += 1.0 * w_i
            dimension_match[dim] = round(gf_score, 2)
        else:
            numerator += min(u_i, j_i) * w_i
            denominator += max(u_i, j_i) * w_i

            # 单维匹配度，前端六维对比格子用
            if max(u_i, j_i) > 0:
                dim_match = min(u_i, j_i) / max(u_i, j_i)
            else:
                dim_match = 0
            dimension_match[dim] = round(dim_match, 2)

    if denominator == 0:
        match_pct = 0.0
    else:
        match_pct = (numerator / denominator) * 100

    # 匹配理由：挑最高的三个维度说事，成长维有单独的文案
    display_dims = {d: v for d, v in dimension_match.items() if d != "成长"}
    top_dims = sorted(display_dims.items(), key=lambda x: x[1], reverse=True)[:3]
    top_dim_names = [d[0] for d in top_dims]
    reason = f"该岗位在{'、'.join(top_dim_names)}方面与你的需求高度匹配。"

    growth_reason = growth_fit_reason(gf_score)
    reason = growth_reason + "。" + reason

    return round(match_pct, 1), dimension_match, reason, gf_score


# ═══════════════════════════════════════════════════════════
#  补充兴趣关键词加成（用于匹配加权 + 生成命中理由）
# ═══════════════════════════════════════════════════════════

def compute_extra_interest_bonus(extra_keywords: list[str], job: dict) -> tuple[float, list[str]]:
    """Compute bonus score based on how well the job matches user's extra interest keywords.

    Returns (bonus_multiplier, matched_keywords).
    bonus_multiplier: 1.0 ~ 1.15, applied to final match percentage.
    matched_keywords: which keywords matched (for reason generation).
    """
    if not extra_keywords:
        return 1.0, []

    title = job.get("title", "")
    company = job.get("company", "")
    jd_text = job.get("jd_text", "")
    skills = job.get("skills_required", [])
    industry = job.get("industry", "")
    company_size = job.get("company_size", "")

    # 把岗位的所有文本拼一起查关键词，简单粗暴但够用
    combined = f"{title} {company} {jd_text} {' '.join(skills)} {industry} {company_size}".lower()

    matched = []
    for kw in extra_keywords:
        kw_lower = kw.lower()
        if kw_lower in combined:
            matched.append(kw)
            continue
        # 完整命中失败再试模糊：2 字词直接在标题/技能里找，3 字以上查 2 字子串
        if len(kw) >= 2:
            title_lower = title.lower()
            skills_lower = ' '.join(skills).lower()
            if len(kw) == 2 and (kw_lower in title_lower or kw_lower in skills_lower):
                matched.append(kw)
                continue
            if len(kw) >= 3:
                for i in range(len(kw_lower) - 1):
                    sub = kw_lower[i:i+2]
                    if sub in title_lower or sub in skills_lower:
                        matched.append(kw)
                        break

    bonus = min(len(matched) * 0.025, 0.15)
    return 1.0 + bonus, matched
