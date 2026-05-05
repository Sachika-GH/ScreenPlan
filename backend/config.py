"""Configuration for ScreenPlan backend."""
import os
from pathlib import Path

SERVER_HOST = os.environ.get("SCREENPLAN_HOST", "0.0.0.0")
SERVER_PORT = int(os.environ.get("SCREENPLAN_PORT", "5051"))
DEBUG = os.environ.get("SCREENPLAN_DEBUG", "0") == "1"

JWT_SECRET = os.environ.get("SCREENPLAN_JWT_SECRET", "change-me-in-production")
JWT_ALGORITHM = "HS256"
JWT_EXPIRY_HOURS = int(os.environ.get("SCREENPLAN_JWT_EXPIRY_HOURS", "720"))  # 30 days

DATA_DIR = Path(os.environ.get("SCREENPLAN_DATA_DIR", str(Path(__file__).parent / "data")))
DATA_DIR.mkdir(parents=True, exist_ok=True)
DATABASE_PATH = DATA_DIR / "screenplan.db"

# LLM config
LLM_API_KEY = os.environ.get("DEEPSEEK_API_KEY") or os.environ.get("OPENAI_API_KEY", "")
# 注意：推荐每个用户在 Web UI 中配置自己的 API Key，而非使用服务端全局 Key
# 全局 Key 仅作为兜底，留空则强制用户自行配置
LLM_API_BASE = os.environ.get("SCREENPLAN_LLM_API_BASE", "https://api.deepseek.com/v1")
LLM_MODEL = os.environ.get("SCREENPLAN_LLM_MODEL", "deepseek-chat")
LLM_MAX_TOKENS = int(os.environ.get("SCREENPLAN_LLM_MAX_TOKENS", "4096"))
LLM_TEMPERATURE = float(os.environ.get("SCREENPLAN_LLM_TEMPERATURE", "0.7"))
LLM_TIMEOUT = int(os.environ.get("SCREENPLAN_LLM_TIMEOUT", "120"))

# Admin — for bot / automation access
ADMIN_TOKEN = os.environ.get("SCREENPLAN_ADMIN_TOKEN", "")

VERSION = "0.1.0"
