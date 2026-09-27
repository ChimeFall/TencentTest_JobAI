import uuid
import json
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from app.database import get_resume, get_profile, save_profile, save_chat, get_chat_history
from app.services.ai_service import assess_industry, assess_interest, extract_interest_keywords
from app.services.matching_engine import compute_user_radar
from app.config import SIX_DIMENSIONS, RANK_WEIGHTS

router = APIRouter(prefix="/api/chat", tags=["chat"])


class InitRequest(BaseModel):
    resume_id: str


class MessageRequest(BaseModel):
    session_id: str
    current_stage: str
    payload: dict | None = None


@router.post("/init")
async def init_chat(req: InitRequest):
    """Initialize chat session after resume upload."""
    resume = get_resume(req.resume_id)
    if not resume:
        raise HTTPException(404, "简历不存在")

    session_id = str(uuid.uuid4())
    parsed = resume["parsed"]
    skills = parsed.get("skills", [])
    top_skills = skills[:3] if len(skills) >= 3 else skills
    skill_str = "、".join(top_skills)

    message = f"已解析你的简历，发现你擅长 {skill_str}。为了精准匹配，请先排序你最看重的因素："

    # 画像先建个空壳，后面每个阶段往里填
    profile = {
        "resume_id": req.resume_id,
        "radar_user": {},
        "weight_order": [],
        "weights": {},
        "preferences": {
            "cities": [],
            "salary_range": "",
            "salary_score": 0,
            "industries": [],
            "extra_interests": "",
        },
    }
    save_profile(session_id, req.resume_id, profile, "S2")
    save_chat(session_id, "S1", "system", message)

    return {
        "code": 0,
        "data": {
            "session_id": session_id,
            "message": message,
            "stage": "S2",
            "components": [
                {
                    "type": "drag_sort",
                    "options": SIX_DIMENSIONS,
                }
            ],
        },
    }


@router.get("/state/{session_id}")
async def get_chat_state(session_id: str):
    """Restore chat session state — used when user refreshes page."""
    profile_data = get_profile(session_id)
    if not profile_data:
        raise HTTPException(404, "会话不存在")

    profile = profile_data["profile"]
    stage = profile_data["current_stage"]

    # 刷新页面时靠这个接口把消息记录拼回来
    raw_history = get_chat_history(session_id)
    messages = []
    for h in raw_history:
        msg = {"role": h["role"], "content": h["content"]}
        if h.get("stage"):
            msg["stage"] = h["stage"]
        messages.append(msg)

    # 恢复到哪个阶段就给哪个阶段的交互组件
    components = _get_components_for_stage(stage)

    return {
        "code": 0,
        "data": {
            "session_id": session_id,
            "resume_id": profile_data["resume_id"],
            "stage": stage,
            "messages": messages,
            "components": components,
            "profile": profile,
        },
    }


def _get_components_for_stage(stage: str) -> list[dict]:
    """Return the components needed for a given stage."""
    stage_components = {
        "S2": [{"type": "drag_sort", "options": SIX_DIMENSIONS}],
        "S3": [
            {
                "type": "multi_select",
                "key": "cities",
                "label": "期望城市（可多选）",
                "options": ["北京", "上海", "深圳", "杭州", "广州", "成都", "武汉", "其他"],
            },
            {
                "type": "slider",
                "key": "salary_range",
                "label": "期望薪资范围",
                "min": 5000,
                "max": 25000,
                "step": 5000,
                "marks": {5000: "5k", 10000: "10k", 15000: "15k", 20000: "20k", 25000: "25k+"},
            },
            {
                "type": "multi_select",
                "key": "industries",
                "label": "目标行业（可多选）",
                "options": ["互联网", "教育", "金融", "文化", "医疗", "制造", "房地产", "零售", "能源", "农业", "政府", "服务", "不限"],
            },
        ],
        "S4": [{
            "type": "text_input",
            "key": "extra_interests",
            "label": "补充信息",
            "placeholder": "例如：想做AI Infra方向，偏好中厂，希望团队氛围好...",
        }],
        "S5": [],
    }
    return stage_components.get(stage, [])


@router.post("/message")
async def chat_message(req: MessageRequest):
    """Handle chat state machine transitions."""
    profile_data = get_profile(req.session_id)
    if not profile_data:
        raise HTTPException(404, "会话不存在")

    profile = dict(profile_data["profile"])  # copy to avoid mutating
    current_stage = req.current_stage
    payload = req.payload or {}

    # 老数据里 profile JSON 可能缺 resume_id，以表字段为准
    resume_id = profile.get("resume_id") or profile_data["resume_id"]

    # 缺啥补啥，老会话的画像结构不一定是全的
    profile.setdefault("resume_id", resume_id)
    profile.setdefault("radar_user", {})
    profile.setdefault("weight_order", [])
    profile.setdefault("weights", {})
    profile.setdefault("preferences", {
        "cities": [],
        "salary_range": "",
        "salary_score": 0,
        "industries": [],
        "extra_interests": "",
    })

    if current_stage == "S2":
        # S2：收下用户的六维排序，按名次映射权重
        weight_order = payload.get("weight_order", SIX_DIMENSIONS)
        profile["weight_order"] = weight_order
        weights = {}
        for i, dim in enumerate(weight_order):
            if i < len(RANK_WEIGHTS):
                weights[dim] = RANK_WEIGHTS[i]
        profile["weights"] = weights

        save_profile(req.session_id, resume_id, profile, "S3")
        save_chat(req.session_id, "S2", "user", "我的排序：" + " > ".join(weight_order))

        reply = "收到！接下来请选择你的偏好：期望城市、薪资范围和目标行业。"
        return {
            "code": 0,
            "data": {
                "reply": reply,
                "next_stage": "S3",
                "components": [
                    {
                        "type": "multi_select",
                        "key": "cities",
                        "label": "期望城市（可多选）",
                        "options": ["北京", "上海", "深圳", "杭州", "广州", "成都", "武汉", "其他"],
                    },
                    {
                        "type": "slider",
                        "key": "salary_range",
                        "label": "期望薪资范围",
                        "min": 5000,
                        "max": 25000,
                        "step": 5000,
                        "marks": {5000: "5k", 10000: "10k", 15000: "15k", 20000: "20k", 25000: "25k+"},
                    },
                    {
                        "type": "multi_select",
                        "key": "industries",
                        "label": "目标行业（可多选）",
                        "options": ["互联网", "教育", "金融", "文化", "医疗", "制造", "房地产", "零售", "能源", "农业", "政府", "服务", "不限"],
                    },
                ],
                "updated_profile": profile,
            },
        }

    elif current_stage == "S3":
        # S3：城市 / 薪资 / 行业偏好
        cities = payload.get("cities", [])
        salary_range = payload.get("salary_range", "4k-8k")
        industries = payload.get("industries", [])
        salary_min = payload.get("salary_min", 4)
        salary_max = payload.get("salary_max", 8)

        profile["preferences"]["cities"] = cities
        profile["preferences"]["salary_range"] = salary_range
        profile["preferences"]["salary_min"] = salary_min
        profile["preferences"]["salary_max"] = salary_max
        profile["preferences"]["industries"] = industries

        save_profile(req.session_id, resume_id, profile, "S4")
        cities_str = "、".join(cities) if cities else "不限"
        industries_str = "、".join(industries) if industries else "不限"
        save_chat(req.session_id, "S3", "user", f"期望城市: {cities_str}, 薪资: {salary_range}, 行业: {industries_str}")

        reply = "收到你的偏好！除了已识别的技能，你还有哪些感兴趣的方向？偏好大厂/中厂/外企/国企？可以自由补充一下。"
        return {
            "code": 0,
            "data": {
                "reply": reply,
                "next_stage": "S4",
                "components": [
                    {
                        "type": "text_input",
                        "key": "extra_interests",
                        "label": "补充信息",
                        "placeholder": "例如：想做AI Infra方向，偏好中厂，希望团队氛围好...",
                    }
                ],
                "updated_profile": profile,
            },
        }

    elif current_stage == "S4":
        # S4：自由文本补充，提完关键词顺手把用户雷达算出来
        extra = payload.get("extra_interests", "")
        profile["preferences"]["extra_interests"] = extra

        extra_keywords = await extract_interest_keywords(extra)
        profile["preferences"]["extra_keywords"] = extra_keywords

        resume = get_resume(resume_id)
        if resume:
            parsed = resume["parsed"]

            exp_text = json.dumps(parsed.get("experiences", []), ensure_ascii=False)
            industry_result = await assess_industry(exp_text)
            industry_score = industry_result.get("industry_match", 0.7)
            # 存下 Top3 行业，匹配时逐个岗位算相似度用
            user_industries = industry_result.get("industries", [
                {"name": industry_result.get("industry_name", "互联网"), "score": industry_score}
            ])
            profile["user_industries"] = user_industries

            interest_text = parsed.get("self_eval", "") + " " + extra
            interest_result = await assess_interest(interest_text)
            interest_score = interest_result.get("interest_score", 0.75)

            radar = compute_user_radar(parsed, industry_score, interest_score, profile["preferences"])
            profile["radar_user"] = radar

        save_profile(req.session_id, resume_id, profile, "S5")
        save_chat(req.session_id, "S4", "user", extra)

        reply = "已生成你的求职画像！请点击右侧面板的「查看匹配结果」按钮。"
        return {
            "code": 0,
            "data": {
                "reply": reply,
                "next_stage": "S5",
                "components": [],
                "updated_profile": profile,
            },
        }

    else:
        raise HTTPException(400, f"未知阶段: {current_stage}")
