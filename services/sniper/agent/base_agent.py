# -*- coding: utf-8 -*-
"""Agent 基类 - 提供资源管理"""

from abc import ABC, abstractmethod
from typing import List, Any, Dict
from utils.logger import logger


class BaseAgent(ABC):
    """Agent 基类 - 所有 Agent 的父类

    提供功能：
    - Connector 管理（自动追踪和清理）
    - 统一的 cleanup 接口
    """

    def __init__(self, source_id: str, source: str, playwright: Any, task: Any):
        """初始化 Agent

        Args:
            source_id: 用户标识
            source: 系统标识
            playwright: Playwright 实例
            task: 任务对象
        """
        self._source_id = source_id
        self._source = source
        self._playwright = playwright
        self._task = task

        # Connector 追踪列表
        self._connectors: List[Any] = []

    def add_connector(self, connector: Any):
        """添加一个 connector 到追踪列表

        Args:
            connector: ConnectorService 实例
        """
        self._connectors.append(connector)
        logger.debug(f"[Agent] Added connector, total: {len(self._connectors)}")

    async def cleanup(self):
        """清理所有 Connector 资源

        在任务取消、完成或失败时自动调用
        """
        logger.info(f"[Agent] Cleaning up {len(self._connectors)} connectors")

        # 遍历清理所有 connector
        for connector in self._connectors:
            try:
                # 调用每个 connector 的 cleanup 方法
                if hasattr(connector, 'cleanup'):
                    await connector.cleanup()
                    logger.debug(f"[Agent] Cleaned connector")
            except Exception as e:
                logger.error(f"[Agent] Error cleaning connector: {e}")

        # 清空列表
        self._connectors.clear()

        logger.info(f"[Agent] Cleanup completed for task {self._task.id if self._task else 'unknown'}")

    @abstractmethod
    async def execute(self, **kwargs) -> Dict[str, Any]:
        """执行 Agent 任务（子类必须实现）

        Args:
            **kwargs: Agent 参数

        Returns:
            执行结果字典
        """
        pass