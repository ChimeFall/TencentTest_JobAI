"""
Industry semantic similarity matching module.

Replaces the old "user-industry-score vs job-industry-prestige" approach
with a proper semantic distance calculation:
  user_industry_score = max_similarity(user_top3_industries, job_industry)
  job_industry_score  = 1.0 (job always fully represents its own industry)
"""

from app.services.ai_service import call_deepseek

# ── Industry grouping table ──
INDUSTRY_GROUPS: dict[str, list[str]] = {
    "互联网": ["互联网", "IT", "计算机软件", "电子商务", "游戏", "人工智能", "大数据", "云计算"],
    "教育": ["教育", "培训", "在线教育", "K12", "职业教育", "教育科技", "知识付费"],
    "金融": ["金融", "银行", "保险", "证券", "投资", "金融科技", "互联网金融", "财富管理"],
    "文化": ["文化", "传媒", "广告", "出版", "影视", "动漫", "体育", "娱乐"],
    "医疗": ["医疗", "制药", "生物科技", "医疗器械", "健康", "医美"],
    "制造": ["制造", "汽车", "机械", "电子硬件", "自动化", "航空航天", "半导体"],
    "房地产": ["房地产", "建筑", "物业", "建材", "室内设计"],
    "零售": ["零售", "贸易", "物流", "电商", "消费品", "供应链"],
    "能源": ["能源", "化工", "环保", "电力", "石油", "新能源"],
    "农业": ["农业", "林业", "牧业", "渔业", "食品"],
    "政府": ["政府", "非营利组织", "公共事业", "社会组织"],
    "服务": ["服务", "餐饮", "旅游", "酒店", "生活服务"],
}

# ── Cross-group related pairs (e.g. 互联网+教育 = 教育科技) ──
RELATED_PAIRS: dict[tuple[str, str], float] = {
    ("互联网", "教育"): 0.60,
    ("互联网", "金融"): 0.55,
    ("互联网", "零售"): 0.65,
    ("互联网", "文化"): 0.50,
    ("互联网", "医疗"): 0.50,
    ("互联网", "制造"): 0.40,
    ("教育", "文化"): 0.45,
    ("金融", "零售"): 0.40,
    ("金融", "房地产"): 0.35,
    ("医疗", "制造"): 0.30,
    ("零售", "农业"): 0.30,
    ("能源", "制造"): 0.35,
}

# ── In-memory cache for DeepSeek results ──
_deepseek_cache: dict[str, float] = {}


def _find_group(industry_name: str) -> str | None:
    """Find which major group an industry belongs to."""
    name_lower = industry_name.lower()
    for group_name, members in INDUSTRY_GROUPS.items():
        for m in members:
            if m.lower() == name_lower or m.lower() in name_lower or name_lower in m.lower():
                return group_name
    return None


def _calc_pair_similarity(a: str, b: str) -> float:
    """Calculate similarity between two industry names using rules + DeepSeek fallback."""
    # 1. Exact match or substring containment
    a_lower = a.lower()
    b_lower = b.lower()
    if a_lower == b_lower or a_lower in b_lower or b_lower in a_lower:
        return 1.0

    # 2. Same major group
    ga = _find_group(a)
    gb = _find_group(b)
    if ga and gb:
        if ga == gb:
            return 0.85
        # 3. Cross-group related pairs
        key = tuple(sorted([ga, gb]))
        if key in RELATED_PAIRS:
            return RELATED_PAIRS[key]

    # 4. Completely unrelated
    return 0.15


async def _deepseek_similarity(a: str, b: str) -> float:
    """Call DeepSeek to judge industry similarity, with caching."""
    cache_key = f"{a}|{b}"
    if cache_key in _deepseek_cache:
        return _deepseek_cache[cache_key]

    prompt = f"""判断'{a}'与'{b}'两个行业的相关程度。
考虑：业务场景重叠度、技能可迁移性、人才流动方向。
只返回0到1之间的一个数字，不要解释。
1=完全相关（如"在线教育"与"教育"），0=完全无关（如"教育"与"军工"）。"""

    try:
        result = await call_deepseek(
            prompt,
            system_prompt="你是一个行业分类专家，只返回一个0到1之间的数字。"
        )
        # 响应里把数字抠出来，模型偶尔会多说话
        score = float(result) if isinstance(result, (int, float)) else 0.3
        score = max(0.0, min(1.0, score))
        _deepseek_cache[cache_key] = score
        return score
    except Exception:
        return 0.15


def get_industry_similarity(user_industries: list[dict], job_industry: str) -> float:
    """
    Calculate industry similarity between user's top industries and job's industry.

    Args:
        user_industries: [{"name":"教育","score":0.9}, {"name":"互联网","score":0.65}, ...]
        job_industry: Job's industry label (e.g. "互联网", "教育科技")

    Returns:
        0.0 ~ 1.0 similarity score (synchronous, no DeepSeek)
    """
    if not user_industries or not job_industry:
        return 0.5

    best_score = 0.0
    for ui in user_industries:
        sim = _calc_pair_similarity(ui["name"], job_industry)
        # 按用户在该行业的契合度加权
        weighted = sim * ui.get("score", 0.5)
        best_score = max(best_score, weighted)

    return round(best_score, 2)


async def get_industry_similarity_async(user_industries: list[dict], job_industry: str) -> float:
    """
    Async version with DeepSeek fallback for unknown industry pairs.

    Args:
        user_industries: [{"name":"教育","score":0.9}, ...]
        job_industry: Job's industry label

    Returns:
        0.0 ~ 1.0 similarity score
    """
    if not user_industries or not job_industry:
        return 0.5

    best_score = 0.0
    for ui in user_industries:
        a = ui["name"]
        b = job_industry
        a_lower = a.lower()
        b_lower = b.lower()

        # 先走本地规则表，判不出来再麻烦 DeepSeek
        if a_lower == b_lower or a_lower in b_lower or b_lower in a_lower:
            sim = 1.0
        else:
            ga = _find_group(a)
            gb = _find_group(b)
            if ga and gb:
                if ga == gb:
                    sim = 0.85
                else:
                    key = tuple(sorted([ga, gb]))
                    sim = RELATED_PAIRS.get(key, -1)
                    if sim < 0:
                        # 规则表判不出来再问模型
                        sim = await _deepseek_similarity(a, b)
            else:
                sim = await _deepseek_similarity(a, b)

        weighted = sim * ui.get("score", 0.5)
        best_score = max(best_score, weighted)

    return round(best_score, 2)
