"""全局配置管理：自动初始化数据目录与持久化随机 JWT 密钥"""
from __future__ import annotations

import os
import secrets
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent

WEAK_SECRETS = {
    "",
    "your-secret-key-change-this-in-production",
    "secret",
    "changeme",
    "default",
}


def load_dotenv_file(env_path: Path | None = None) -> None:
    """加载根目录 .env 文件（不覆盖已存在的环境变量）"""
    target = env_path or (PROJECT_ROOT / ".env")
    if not target.exists():
        return
    try:
        for raw_line in target.read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, val = line.split("=", 1)
            key = key.strip()
            val = val.strip().strip('"').strip("'")
            if key and key not in os.environ:
                os.environ[key] = val
    except OSError:
        pass


load_dotenv_file()


def get_data_dir() -> Path:
    """获取并自动创建数据存储目录"""
    raw = os.getenv("QVS_DATA_DIR", "").strip()
    data_dir = Path(raw).expanduser() if raw else (PROJECT_ROOT / "data")
    if not data_dir.is_absolute():
        data_dir = (PROJECT_ROOT / data_dir).resolve()
    data_dir.mkdir(parents=True, exist_ok=True)
    return data_dir


def get_or_create_jwt_secret() -> str:
    """获取 JWT 密钥；若未配置或为弱默认密钥则自动生成并持久化随机密钥"""
    env_secret = os.getenv("JWT_SECRET_KEY", "").strip()
    if env_secret and env_secret not in WEAK_SECRETS and len(env_secret) >= 24:
        return env_secret

    secret_file = get_data_dir() / ".secret_key"
    if secret_file.exists():
        try:
            saved = secret_file.read_text(encoding="utf-8").strip()
            if len(saved) >= 24:
                return saved
        except OSError:
            pass

    new_secret = secrets.token_urlsafe(48)
    try:
        secret_file.write_text(new_secret, encoding="utf-8")
        try:
            os.chmod(secret_file, 0o600)
        except OSError:
            pass
    except OSError:
        pass
    return new_secret


DATA_DIR = get_data_dir()
DATA_DB_PATH = DATA_DIR / "data.db"
LOGS_DB_PATH = DATA_DIR / "logs.db"
JWT_SECRET_KEY = get_or_create_jwt_secret()
JWT_EXPIRE_HOURS = int(os.getenv("JWT_EXPIRE_HOURS", "168"))  # 默认 7 天
DEFAULT_HOST = os.getenv("HOST", "0.0.0.0")
DEFAULT_PORT = int(os.getenv("PORT", "8000"))
