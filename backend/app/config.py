import os
from dotenv import load_dotenv

load_dotenv()

DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "")
DEEPSEEK_BASE_URL = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./offer_catcher.db")

# CloudBase 的 MySQL 是单独的环境变量，没有走 DATABASE_URL
MYSQL_HOST = os.getenv("MYSQL_HOST", "")
MYSQL_PORT = os.getenv("MYSQL_PORT", "3306")
MYSQL_USER = os.getenv("MYSQL_USER", "")
MYSQL_PASSWORD = os.getenv("MYSQL_PASSWORD", "")
MYSQL_DATABASE = os.getenv("MYSQL_DATABASE", "")

# 用户排序第 1~6 名对应的权重，拍脑袋定的递减序列
RANK_WEIGHTS = {
    0: 0.30,
    1: 0.25,
    2: 0.20,
    3: 0.15,
    4: 0.07,
    5: 0.03,
}

SIX_DIMENSIONS = ["技能", "行业", "薪资", "地域", "成长", "兴趣"]

SALARY_SCORE_MAP = {
    5000: 0.2,
    10000: 0.4,
    15000: 0.6,
    20000: 0.8,
    25000: 1.0,
}

DEGREE_SCORE = {"专科": 0.4, "本科": 0.6, "硕士": 0.8, "博士": 1.0}

CITY_TIER = {
    "北京": 1, "上海": 1, "深圳": 1, "广州": 1,
    "杭州": 2, "成都": 2, "武汉": 2, "南京": 2,
    "西安": 2, "重庆": 2, "苏州": 2, "天津": 2,
}
CITY_TIER_SCORE = {1: 1.0, 2: 0.8, 3: 0.6}

# 用来判断"大厂经历"的关键词，成长维加分用
BIG_COMPANY_KEYWORDS = ["字节", "腾讯", "阿里", "百度", "美团", "京东", "快手", "网易", "华为", "微软", "谷歌"]
