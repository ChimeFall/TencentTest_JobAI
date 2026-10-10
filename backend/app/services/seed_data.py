import json
import os
import uuid
from app.database import save_job
from app.services.matching_engine import compute_job_radar

SEED_DATA_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "seed_data", "jobs.json")


def load_seed_jobs() -> list[dict]:
    """Load seed jobs from JSON file."""
    if os.path.exists(SEED_DATA_PATH):
        with open(SEED_DATA_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    return []


def generate_seed_jobs() -> list[dict]:
    """Generate default seed job data if no file exists."""
    jobs = [
        {
            "job_id": str(uuid.uuid4()),
            "platform": "boss",
            "title": "Python后端开发工程师",
            "company": "字节跳动",
            "salary_min": 20000,
            "salary_max": 40000,
            "city": "北京",
            "city_tier": 1,
            "industry": "互联网",
            "company_size": "10000人以上",
            "level": "初级",
            "skills_required": ["Python", "Go", "MySQL", "Redis", "Docker", "Kafka", "微服务"],
            "jd_text": """岗位职责：
1. 负责公司核心业务系统的后端开发与维护
2. 参与系统架构设计，保证系统高可用、高并发
3. 编写高质量代码，进行代码评审
4. 与产品、前端团队紧密协作

任职要求：
1. 计算机相关专业本科及以上学历
2. 熟练掌握Python/Go，熟悉常用数据结构和算法
3. 熟悉MySQL、Redis等数据库
4. 了解分布式系统、消息队列等中间件
5. 有良好的编码习惯和团队协作能力
6. 对技术有热情，喜欢钻研新技术""",
        },
        {
            "job_id": str(uuid.uuid4()),
            "platform": "boss",
            "title": "AI算法工程师（应届生）",
            "company": "腾讯",
            "salary_min": 25000,
            "salary_max": 45000,
            "city": "深圳",
            "city_tier": 1,
            "industry": "AI",
            "company_size": "10000人以上",
            "level": "初级",
            "skills_required": ["Python", "PyTorch", "TensorFlow", "NLP", "机器学习", "深度学习"],
            "jd_text": """岗位职责：
1. 参与AI产品的算法研发与优化
2. 负责自然语言处理相关模型训练与部署
3. 跟踪前沿技术，推动技术创新
4. 撰写技术文档，参与技术分享

任职要求：
1. 计算机/AI相关专业硕士及以上学历
2. 扎实的机器学习、深度学习基础
3. 熟练使用Python，熟悉PyTorch/TensorFlow
4. 有NLP/CV相关项目经验优先
5. 良好的英文论文阅读能力""",
        },
        {
            "job_id": str(uuid.uuid4()),
            "platform": "智联",
            "title": "Java开发工程师",
            "company": "美团",
            "salary_min": 18000,
            "salary_max": 30000,
            "city": "北京",
            "city_tier": 1,
            "industry": "互联网",
            "company_size": "10000人以上",
            "level": "初级",
            "skills_required": ["Java", "Spring Boot", "MySQL", "Redis", "消息队列", "微服务"],
            "jd_text": """岗位职责：
1. 参与美团到家业务后端系统开发
2. 负责核心功能模块的设计与实现
3. 持续优化系统性能和稳定性
4. 参与技术方案评审

任职要求：
1. 计算机相关专业本科及以上
2. 扎实的Java基础，熟悉Spring框架
3. 熟悉MySQL、Redis等常用中间件
4. 了解分布式系统设计原则
5. 良好的沟通协作能力""",
        },
        {
            "job_id": str(uuid.uuid4()),
            "platform": "boss",
            "title": "前端开发工程师（React）",
            "company": "快手",
            "salary_min": 18000,
            "salary_max": 35000,
            "city": "北京",
            "city_tier": 1,
            "industry": "互联网",
            "company_size": "10000人以上",
            "level": "初级",
            "skills_required": ["JavaScript", "React", "TypeScript", "CSS", "Webpack", "Node.js"],
            "jd_text": """岗位职责：
1. 负责快手主站前端功能开发
2. 参与前端基础设施建设
3. 优化页面性能和用户体验
4. 与设计、后端团队协作

任职要求：
1. 计算机相关专业本科及以上
2. 熟练掌握JavaScript/TypeScript
3. 熟悉React框架及其生态
4. 了解前端工程化，有Webpack/Vite使用经验
5. 对用户体验有追求""",
        },
        {
            "job_id": str(uuid.uuid4()),
            "platform": "猎聘",
            "title": "数据开发工程师",
            "company": "阿里巴巴",
            "salary_min": 20000,
            "salary_max": 35000,
            "city": "杭州",
            "city_tier": 2,
            "industry": "互联网",
            "company_size": "10000人以上",
            "level": "初级",
            "skills_required": ["SQL", "Python", "Spark", "Hadoop", "数据仓库", "ETL"],
            "jd_text": """岗位职责：
1. 负责数据仓库建设与维护
2. 开发ETL流程，保障数据质量
3. 参与数据产品研发
4. 数据分析和可视化

任职要求：
1. 计算机/统计相关专业本科及以上
2. 熟练掌握SQL，有Python编程能力
3. 了解大数据技术栈（Spark/Hadoop）
4. 有数据仓库建模经验优先
5. 逻辑清晰，善于沟通""",
        },
        {
            "job_id": str(uuid.uuid4()),
            "platform": "boss",
            "title": "运维开发工程师",
            "company": "网易",
            "salary_min": 15000,
            "salary_max": 25000,
            "city": "广州",
            "city_tier": 1,
            "industry": "互联网",
            "company_size": "1000-9999人",
            "level": "初级",
            "skills_required": ["Linux", "Python", "Docker", "Kubernetes", "CI/CD", "监控"],
            "jd_text": """岗位职责：
1. 负责线上服务的运维保障
2. 开发自动化运维工具
3. 参与容器化平台建设
4. 故障排查与性能优化

任职要求：
1. 计算机相关专业本科及以上
2. 熟悉Linux系统管理
3. 掌握Python/Shell脚本编程
4. 了解Docker/K8s容器技术
5. 有责任心，抗压能力强""",
        },
        {
            "job_id": str(uuid.uuid4()),
            "platform": "boss",
            "title": "Golang后端开发",
            "company": "小红书",
            "salary_min": 22000,
            "salary_max": 40000,
            "city": "上海",
            "city_tier": 1,
            "industry": "互联网",
            "company_size": "1000-9999人",
            "level": "初级",
            "skills_required": ["Go", "Python", "MySQL", "Redis", "微服务", "Kafka", "Docker"],
            "jd_text": """岗位职责：
1. 负责小红书社区后端服务开发
2. 参与微服务架构设计与实现
3. 保障系统高可用和高性能
4. Code Review和技术分享

任职要求：
1. 计算机相关专业本科及以上
2. 熟练掌握Go语言，了解Python
3. 熟悉MySQL、Redis等数据库
4. 有微服务开发经验
5. 热爱技术，喜欢挑战""",
        },
        {
            "job_id": str(uuid.uuid4()),
            "platform": "智联",
            "title": "测试开发工程师",
            "company": "百度",
            "salary_min": 18000,
            "salary_max": 30000,
            "city": "北京",
            "city_tier": 1,
            "industry": "互联网",
            "company_size": "10000人以上",
            "level": "初级",
            "skills_required": ["Python", "Java", "Selenium", "自动化测试", "CI/CD", "Linux"],
            "jd_text": """岗位职责：
1. 负责产品质量保障，制定测试方案
2. 开发自动化测试框架和工具
3. 参与CI/CD流水线建设
4. 性能测试和压力测试

任职要求：
1. 计算机相关专业本科及以上
2. 熟悉Python/Java编程
3. 了解自动化测试框架
4. 有良好的逻辑思维能力
5. 细心负责，善于发现bug""",
        },
        {
            "job_id": str(uuid.uuid4()),
            "platform": "boss",
            "title": "产品经理（技术方向）",
            "company": "京东",
            "salary_min": 18000,
            "salary_max": 28000,
            "city": "北京",
            "city_tier": 1,
            "industry": "互联网",
            "company_size": "10000人以上",
            "level": "初级",
            "skills_required": ["产品设计", "数据分析", "SQL", "Axure", "需求分析", "项目管理"],
            "jd_text": """岗位职责：
1. 负责电商平台产品功能规划
2. 进行用户需求调研和分析
3. 撰写PRD文档，跟进开发进度
4. 数据驱动的产品迭代优化

任职要求：
1. 本科及以上学历，计算机相关专业优先
2. 有技术背景，了解基本开发流程
3. 逻辑清晰，善于沟通表达
4. 对电商行业有兴趣
5. 有产品实习经验优先""",
        },
        {
            "job_id": str(uuid.uuid4()),
            "platform": "猎聘",
            "title": "全栈开发工程师",
            "company": "Shopee",
            "salary_min": 20000,
            "salary_max": 35000,
            "city": "深圳",
            "city_tier": 1,
            "industry": "互联网",
            "company_size": "5000-9999人",
            "level": "初级",
            "skills_required": ["Python", "JavaScript", "React", "MySQL", "Redis", "Docker", "AWS"],
            "jd_text": """岗位职责：
1. 负责跨境电商平台前后端开发
2. 参与系统架构设计
3. 编写单元测试和集成测试
4. 与海外团队协作

任职要求：
1. 计算机相关专业本科及以上
2. 熟悉Python/JavaScript
3. 了解React或Vue前端框架
4. 英语读写能力良好
5. 有全栈项目经验优先""",
        },
    ]

    # 每个岗位预计算雷达分，免得匹配时重复算
    for job in jobs:
        radar = compute_job_radar(job)
        job["radar_json"] = radar
        job["salary_score"] = radar.get("薪资", 0.7)

    # 顺带把种子数据写一份 json，方便查看和手工导入
    os.makedirs(os.path.dirname(SEED_DATA_PATH), exist_ok=True)
    with open(SEED_DATA_PATH, "w", encoding="utf-8") as f:
        json.dump(jobs, f, ensure_ascii=False, indent=2)

    return jobs


def init_seed_data():
    """Initialize seed data into database."""
    jobs = load_seed_jobs()
    if not jobs:
        jobs = generate_seed_jobs()

    for job in jobs:
        save_job(job)

    print(f"Initialized {len(jobs)} seed jobs.")
    return len(jobs)
