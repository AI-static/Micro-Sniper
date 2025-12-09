"""日志工具"""
import sys
import os
from pathlib import Path
from typing import Optional
from contextvars import ContextVar
from loguru import logger as loguru_logger
from config.settings import settings


# 请求ID上下文变量
request_id_ctx: ContextVar[Optional[str]] = ContextVar('request_id', default=None)


class LoggerWrapper:
    """带请求ID的Logger包装器"""
    
    def __init__(self, base_logger):
        self.base_logger = base_logger
    
    def _format(self, message):
        """格式化消息，添加请求ID"""
        rid = request_id_ctx.get()
        return f"[{rid}] {message}"

    def debug(self, message, **kwargs):
        self.base_logger.debug(self._format(message), **kwargs)
    
    def info(self, message, **kwargs):
        self.base_logger.info(self._format(message), **kwargs)
    
    def warning(self, message, **kwargs):
        self.base_logger.warning(self._format(message), **kwargs)
    
    def error(self, message, **kwargs):
        self.base_logger.error(self._format(message), **kwargs)
    
    def critical(self, message, **kwargs):
        self.base_logger.critical(self._format(message), **kwargs)
    
    def exception(self, message, **kwargs):
        self.base_logger.exception(self._format(message), **kwargs)
    
    # 保持原有接口
    def bind(self, **kwargs):
        """绑定额外参数"""
        wrapped = LoggerWrapper(self.base_logger.bind(**kwargs))
        return wrapped
    
    def opt(self, **kwargs):
        """选项"""
        wrapped = LoggerWrapper(self.base_logger.opt(**kwargs))
        return wrapped


class LoggingManager:
    """日志管理器"""
    
    def __init__(self):
        # 移除默认的处理器
        loguru_logger.remove()
        # 根据配置设置日志
        self._setup_logging()
    
    def _setup_logging(self):
        """设置日志配置"""
        # 创建日志目录
        if settings.log_file_path and settings.log_to_file:
            log_file_path = Path(settings.log_file_path)
            log_file_path.parent.mkdir(parents=True, exist_ok=True)

            loguru_logger.add(
                settings.log_file_path,
                level=settings.log_level,
                rotation=settings.log_file_rotation,
                retention=settings.log_file_retention,
                compression="zip",
                encoding="utf-8"
            )
        
        # 控制台输出配置
        if settings.log_to_console:
            loguru_logger.add(
                sys.stdout,
                level=settings.log_level,
                colorize=True
            )
    
    def get_logger(self, name):
        """获取logger实例"""
        return LoggerWrapper(loguru_logger.bind(name=name)).opt(depth=2)


# 创建全局日志管理器实例
logging_manager = LoggingManager()

# 导出logger实例（支持请求ID）
logger = logging_manager.get_logger("api")

# 提供便捷函数
def set_request_id(request_id: str):
    """设置当前请求的ID"""
    request_id_ctx.set(request_id)


def get_request_id() -> Optional[str]:
    """获取当前请求的ID"""
    return request_id_ctx.get()
