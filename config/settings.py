from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional
from enum import Enum


# ==================================
# 环境枚举
# ==================================
class LogLevel(str, Enum):
    """日志级别枚举"""
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


# ==================================
# 配置模型
# ==================================
class AppConfig(BaseModel):
    """应用配置"""
    name: str = Field(default="Aether", description="服务名称")
    description: str = Field(default="浏览器自动化服务", description="应用描述")
    port: int = Field(default=1111, description="服务端口")
    debug: bool = Field(default=False, description="调试模式")
    env: str = Field(default="dev", description="环境")


class AgentBayConfig(BaseModel):
    """AgentBay配置"""
    api_key: Optional[str] = Field(default=None, description="AgentBay API密钥")
    base_url: Optional[str] = Field(default=None, description="AgentBay API地址")


class DatabaseConfig(BaseModel):
    """数据库配置"""
    host: str = Field(default="localhost", description="数据库主机")
    port: int = Field(default=5432, description="数据库端口")
    user: Optional[str] = Field(default=None, description="数据库用户名")
    password: Optional[str] = Field(default="", description="数据库密码")
    name: str = Field(default="browser_automation", description="数据库名")
    schema_name: str = Field(default="public", description="模式名")
    max_connections: int = Field(default=100, description="最大连接数")
    min_connections: int = Field(default=10, description="最小连接数")

class LoggerConfig(BaseModel):
    """日志配置"""
    level: LogLevel = Field(default=LogLevel.INFO, description="日志级别")
    to_console: bool = Field(default=True, description="是否输出到控制台")
    to_file: bool = Field(default=True, description="是否写入文件")
    file_path: str = Field(default="logs/app.log", description="日志文件路径")
    file_rotation: str = Field(default="1 day", description="文件存储天数")
    file_retention: str = Field(default="30 days", description="")


class ExternalServiceConfig(BaseModel):
    """外部服务配置"""
    ezlink_base_url: Optional[str] = Field(default=None, description="EzLink API基础URL")
    ezlink_api_key: Optional[str] = Field(default=None, description="EzLink API密钥")
    vectorai_base_url: Optional[str] = Field(default=None, description="VectorAI API基础URL")
    vectorai_api_key: Optional[str] = Field(default=None, description="VectorAI API密钥")
    aliyun_base_url: Optional[str] = Field(default=None, description="阿里云基础URL")
    aliyun_api_key: Optional[str] = Field(default=None, description="阿里云API密钥")


class SecurityConfig(BaseModel):
    """安全配置"""
    encryption_key: Optional[str] = Field(default=None, description="apikey的加密密钥")


class OSSConfig(BaseModel):
    """OSS对象存储配置"""
    access_key_id: Optional[str] = Field(default=None, description="OSS访问密钥ID")
    access_key_secret: Optional[str] = Field(default=None, description="OSS访问密钥Secret")
    endpoint: str = Field(default="https://oss-cn-beijing.aliyuncs.com", description="OSS端点")
    bucket_name: Optional[str] = Field(default=None, description="OSS存储桶名称")


class WechatConfig(BaseModel):
    """微信连接器配置"""
    rss_url: Optional[str] = Field(default=None, description="微信公众号订阅源URL")
    rss_timeout: int = Field(default=30, description="订阅源请求超时时间(秒)")
    rss_buffer_size: int = Field(default=8192, description="流式读取缓冲区大小")


class RedisConfig(BaseModel):
    """Redis配置"""
    host: str = Field(default="localhost", description="Redis主机")
    port: int = Field(default=6379, description="Redis端口")
    db: int = Field(default=0, description="Redis数据库")
    user: Optional[str] = Field(default=None, description="Redis用户名")
    password: Optional[str] = Field(default=None, description="Redis密码")
    max_connections: int = Field(default=5000, description="最大连接数")


class IMConfig(BaseModel):
    """微信连接器配置"""
    wechat_corpid: str = Field(default=None, description="企业微信的企业id")
    wechat_secret: str = Field(default=None, description="企业微信的应用密钥")
    wechat_agent_id: int = Field(default=8192, description="企业微信的应用id")
    wechat_token: str = Field(default=None, description="解密token")
    wechat_encoding_aes_key: str = Field(default=None, description="解密字符串")
# ==================================
# 全局设置
# ==================================
class GlobalSettings(BaseSettings):
    """全局配置设置"""
    app: AppConfig = Field(default_factory=AppConfig)
    logger: LoggerConfig = Field(default_factory=LoggerConfig)
    database: DatabaseConfig = Field(default_factory=DatabaseConfig)
    redis: RedisConfig = Field(default_factory=RedisConfig)
    agentbay: AgentBayConfig = Field(default_factory=AgentBayConfig)
    external_service: ExternalServiceConfig = Field(default_factory=ExternalServiceConfig)
    security: SecurityConfig = Field(default_factory=SecurityConfig)
    oss: OSSConfig = Field(default_factory=OSSConfig)
    wechat: WechatConfig = Field(default_factory=WechatConfig)
    im: IMConfig = Field(default_factory=IMConfig)

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="allow",
        env_nested_delimiter="__",
    )


# ==================================
# 全局实例
# ==================================
settings = GlobalSettings()
global_settings = settings


# ==================================
# 数据库配置创建函数
# ==================================
def create_db_config():
    """创建Tortoise ORM数据库配置"""
    return {
        "connections": {
            "default": {
                "engine": "tortoise.backends.asyncpg",
                "credentials": {
                    "host": settings.database.host,
                    "port": settings.database.port,
                    "user": settings.database.user,
                    "password": settings.database.password,
                    "database": settings.database.name,
                    "schema": settings.database.schema_name,
                    "maxsize": settings.database.max_connections,
                    "minsize": settings.database.min_connections,
                    "command_timeout": 30,
                    "server_settings": {
                        "application_name": settings.app.name,
                    },
                    "ssl": "prefer",
                }
            }
        },
        "apps": {
            "models": {
                "models": [
                    "models.identity",
                ],
                "default_connection": "default"
            }
        },
        "use_tz": False,
        "timezone": "Asia/Shanghai",
    }