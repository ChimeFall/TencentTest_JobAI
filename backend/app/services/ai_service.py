import json
import re
import httpx
from app.config import DEEPSEEK_API_KEY, DEEPSEEK_BASE_URL


async def call_deepseek(prompt: str, system_prompt: str = "你是一个专业的助手，请严格返回JSON格式。") -> dict:
    """Call DeepSeek V4 Flash API and return parsed JSON."""
    async with httpx.AsyncClient(timeout=60.0) as client:
        resp = await client.post(
            f"{DEEPSEEK_BASE_URL}/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
                "Content-Type": "application/json",
            },
            json={
                "model": "deepseek-chat",
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": prompt},
                ],
                "temperature": 0.1,
                "max_tokens": 4096,
            },
        )
        data = resp.json()
        content = data["choices"][0]["message"]["content"]

        # DeepSeek 返回的 JSON 外面经常裹着 markdown 代码块，先剥掉
        content = content.strip()
        if content.startswith("```json"):
            content = content[7:]
        if content.startswith("```"):
            content = content[3:]
        if content.endswith("```"):
            content = content[:-3]
        content = content.strip()

        return json.loads(content)


def mask_phone(phone: str) -> str:
    if not phone or len(phone) < 7:
        return phone
    return phone[:3] + "****" + phone[-4:]


def mask_email(email: str) -> str:
    if not email or "@" not in email:
        return email
    local, domain = email.split("@", 1)
    if len(local) <= 1:
        return email
    return local[0] + "**" + local[-1] + "@" + domain


def mask_name(name: str) -> str:
    if not name:
        return name
    if len(name) == 2:
        return name[0] + "*"
    if len(name) >= 3:
        return name[0] + "*" * (len(name) - 1)
    return name


async def parse_resume_text(raw_text: str) -> dict:
    """Parse resume text using DeepSeek API."""
    prompt = f"""你是一名简历解析专家。请从以下简历文本中提取结构化信息，严格返回JSON格式，不要有任何其他文字。

要求字段：
- basic: {{name, phone, email, school, major, degree, graduation_year}}
- skills: 技能列表（数组）
- experiences: 数组，每个元素含 {{type, company, role, description, tech_stack}}
- projects: 数组，每个元素含 {{name, description}}
- self_eval: 自我评价原文

简历文本：
{raw_text}"""

    try:
        result = await call_deepseek(prompt)
        return result
    except Exception as e:
        # AI 挂了就用正则粗提取兜底，至少把技能和学校捞出来
        return _fallback_parse(raw_text)


def _fallback_parse(raw_text: str) -> dict:
    """Fallback parser when DeepSeek is unavailable."""
    lines = raw_text.split("\n")
    skills = []
    for line in lines:
        if "技能" in line or "skill" in line.lower():
            parts = re.split(r"[：:，,、\s]+", line)
            for p in parts[1:]:
                if len(p) > 1 and not any(k in p for k in ["技能", "skill", "：", ":"]):
                    skills.append(p.strip())

    return {
        "basic": {
            "name": "",
            "phone": "",
            "email": "",
            "school": "",
            "major": "",
            "degree": "本科",
            "graduation_year": "2026",
        },
        "skills": skills if skills else ["未识别"],
        "experiences": [],
        "projects": [],
        "self_eval": raw_text[:200],
    }


async def assess_industry(experiences_text: str) -> dict:
    """Assess user industry fit — returns Top3 industries with scores."""
    prompt = f"""根据以下用户经历（教育+实习+项目），评估其与【互联网、金融、AI、制造业、教育】五个行业的契合度。
返回JSON格式，包含Top3最匹配行业及其契合度分数(0-1)：
{{"industry_match": 0.85, "industry_name": "教育", "industries": [{{"name":"教育","score":0.85}}, {{"name":"互联网","score":0.62}}, {{"name":"金融","score":0.40}}]}}

经历文本：
{experiences_text}"""

    try:
        result = await call_deepseek(prompt)
        # 老数据可能没有 industries 字段，补个空的
        if "industries" not in result:
            result["industries"] = [
                {"name": result.get("industry_name", "互联网"), "score": result.get("industry_match", 0.7)}
            ]
        return result
    except Exception:
        return {
            "industry_match": 0.7,
            "industry_name": "互联网",
            "industries": [{"name": "互联网", "score": 0.7}],
        }


async def assess_interest(text: str) -> dict:
    """Assess user interest clarity."""
    prompt = f"""根据用户自我评价与补充兴趣，评估其求职兴趣的明确度与热门方向（AI/云原生/大数据/前端/后端）契合度。
返回0-1之间的数值，JSON格式：{{"interest_score": 0.85}}

文本：
{text}"""

    try:
        return await call_deepseek(prompt)
    except Exception:
        return {"interest_score": 0.75}


async def assess_job_interest(jd_text: str) -> float:
    """Assess job interest score from JD text."""
    prompt = f"""分析以下岗位JD文本，评估该岗位在"创新、挑战、技术深度、业务理解、用户增长"等方面的表现，
返回0-1之间的数值，JSON格式：{{"interest_score": 0.85}}

JD文本：
{jd_text}"""

    try:
        result = await call_deepseek(prompt)
        return float(result.get("interest_score", 0.7))
    except Exception:
        return 0.7


async def extract_interest_keywords(extra_text: str) -> list[str]:
    """Extract specific career direction keywords from user's extra interests text.
    
    Returns a list of direction keywords like ['数据分析', 'AI', '后端开发'].
    These will be used to boost matching weight for relevant jobs.
    """
    if not extra_text or not extra_text.strip():
        return []

    prompt = f"""从用户补充的求职意向中提取具体的职业方向关键词，返回JSON格式。
要求：
- 提取技术方向（如：数据分析、AI、后端、前端、算法、云原生等）
- 提取业务方向（如：电商、金融科技、教育、游戏等）
- 提取公司偏好（如：大厂、中厂、外企、国企、创业等）
- 每个关键词尽量简短精确，不超过6个字
- 返回数组，最多5个关键词
- 如果用户没有明确补充，返回空数组

用户补充信息：
{extra_text}

严格返回JSON格式，不要有其他文字：
{{"keywords": ["数据分析", "AI", "中厂"]}}"""

    try:
        result = await call_deepseek(prompt)
        keywords = result.get("keywords", [])
        return [k for k in keywords if k and len(k) <= 10][:5]
    except Exception:
        return _fallback_extract_keywords(extra_text)


def _fallback_extract_keywords(text: str) -> list[str]:
    """Fallback keyword extraction when DeepSeek is unavailable."""
    if not text:
        return []
    
    KNOWN_KEYWORDS = [
        "数据分析", "AI", "人工智能", "机器学习", "深度学习",
        "后端", "前端", "全栈", "算法", "大数据", "云原生",
        "DevOps", "测试", "运维", "安全", "区块链", "物联网",
        "大厂", "中厂", "外企", "国企", "创业",
        "电商", "金融", "教育", "游戏", "医疗", "自动驾驶",
    ]
    found = []
    text_lower = text.lower()
    for kw in KNOWN_KEYWORDS:
        if kw.lower() in text_lower:
            found.append(kw)
    return found[:5]


async def ats_analyze(resume_text: str, jd_text: str) -> dict:
    """ATS analysis and optimization suggestions."""
    prompt = f"""你是一名ATS（简历筛选系统）专家和资深HR。

岗位JD：
{jd_text}

用户简历：
{resume_text}

请完成以下分析，严格返回JSON：
{{
  "ats_score": 0-100,
  "keyword_hit": ["命中关键词"],
  "keyword_miss": ["缺失关键词"],
  "format_issues": ["格式问题1", "格式问题2"],
  "suggestions": [
    {{
      "id": 1,
      "location": "问题所在段落",
      "issue": "具体问题",
      "advice": "为什么需要改",
      "original": "原文",
      "optimized": "优化后的文本"
    }}
  ]
}}

注意：
1. ats_score 基于关键词覆盖率（60%）、格式规范性（20%）、经历相关性（20%）
2. 必须给出具体改写示例，不要泛泛而谈
3. 优化后的文本必须包含量化成果
4. **极其重要**：optimized 字段必须是修改后的实际内容，不能与 original 完全相同！如果问题是"时间顺序颠倒"，optimized 中必须按正确顺序重新排列；如果是"描述不够量化"，optimized 中必须补充具体数字和成果。每条建议的 optimized 都必须体现实际的修改动作。"""

    try:
        return await call_deepseek(prompt)
    except Exception:
        return {
            "ats_score": 65,
            "keyword_hit": ["Python"],
            "keyword_miss": ["暂未分析"],
            "format_issues": ["API暂不可用，请稍后重试"],
            "suggestions": [],
        }
