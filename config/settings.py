from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    """应用配置"""
    
    # 应用配置
    app_name: str = "Aether"
    app_description: str = "业务适配层服务"  # 应用描述
    app_port: int = 8000
    app_debug: bool = False
    app_auto_reload: bool = False
    
    # Redis配置
    redis_host: str = "localhost"
    redis_port: int = 6379
    redis_db: int = 0
    redis_password: Optional[str] = None

    pg_host: str = "localhost"
    pg_port: int = 5432
    pg_user: str = None
    pg_password: str = None
    pg_database: str = 'aether'
    
    # 其他服务配置
    ezlink_api_key: Optional[str] = None
    ezlink_base_url: Optional[str] = None
    
    # 图片配置
    image_dir: str = "generated_images"  # 图片存储目录

    # 日志配置
    log_level: str = "INFO"  # 日志级别: DEBUG, INFO, WARNING, ERROR, CRITICAL
    log_to_file: bool = True  # 是否写入文件
    log_to_console: bool = True  # 是否输出到控制台
    log_file_path: str = "logs/app.log"  # 日志文件路径
    log_file_rotation: str = "1 day"  # 日志轮转: 1 day, 1 week, 1 month
    log_file_retention: str = "30 days"  # 日志保留时间
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


# 创建全局配置实例
settings = Settings()

# 兼容旧代码的引用
global_settings = settings

# 导出常用配置
REDIS_HOST = settings.redis_host
REDIS_PORT = settings.redis_port
REDIS_DB = settings.redis_db
REDIS_PASSWORD = settings.redis_password


def create_db_config() -> dict:
    return {
        "connections": {
            "default": {
                "engine": "tortoise.backends.asyncpg",
                "credentials": {
                    "host": global_settings.postgres.host,
                    "port": global_settings.postgres.port,
                    "user": global_settings.postgres.user,
                    "password": global_settings.postgres.password,
                    "database": global_settings.postgres.database,
                    "schema": "public",
                    "maxsize": 100,
                    "minsize": 500,
                    "command_timeout": 30,  # 增加超时时间
                    "server_settings": {
                        # PostgreSQL服务器设置
                        "application_name": global_settings.app.name,
                        "tcp_keepalives_idle": "300",
                        "tcp_keepalives_interval": "30",
                        "tcp_keepalives_count": "3",
                    },
                    # SSL设置（可能影响性能）
                    "ssl": "prefer",  # 或 False, True, "require"
                }
            }
        },
        "apps": {
            "models": {
                "models": [
                    "app.models.identity.policy",
                    "app.models.identity.application",
                    "app.models.document.file",
                    "app.models.document.item",
                    "app.models.kb.kb"
                ],
                "default_connection": "default"
            }
        },
        "use_tz": False,
        "timezone": "Asia/Shanghai",
    }