# -*- coding: utf-8 -*-
"""微信公众号文章采集 Agent"""

from typing import List, Dict, Any, Optional
from config.settings import global_settings
from datetime import datetime
import asyncio
import json

# Agno imports
from agno.agent import Agent
from agno.models.dashscope import DashScope
from agno.db.postgres import AsyncPostgresDb
from playwright.async_api import async_playwright

# 导入外部 Service
from services.sniper.connectors import ConnectorService
from services.sniper.agent.base_agent import BaseAgent
from models.task import Task
from models.connectors import PlatformType
from utils.logger import logger

# 1. 数据库连接
db = AsyncPostgresDb(
    db_url=f"postgresql+asyncpg://{global_settings.database.user}:{global_settings.database.password}@{global_settings.database.host}:{global_settings.database.port}/{global_settings.database.name}"
)

# 2. 模型配置
chat_model = DashScope(
    base_url=global_settings.external_service.aliyun_base_url,
    api_key=global_settings.external_service.aliyun_api_key,
    id="qwen-plus",
)


class WechatHarvestAgent(BaseAgent):
    """微信公众号文章采集专家 - 根据链接列表采集文章结构化数据"""

    def __init__(
            self,
            source_id: str = "system_user",
            source: str = "system",
            playwright: Any = None,
            task: Task = None
    ):
        super().__init__(source_id, source, playwright, task)

        # Agent 只负责分析，不负责采集
        self.agent = Agent(
            name="微信采集助手",
            model=chat_model,
            instructions=[
                "你是一个微信公众号文章采集助手。",
                "你负责整理和验证采集到的公众号文章数据。",
                "确保数据完整性，包括标题、作者、发布时间、内容等字段。",
                "对采集失败的文章进行标记和错误记录。"
            ],
            db=db,
            markdown=True,
            add_history_to_context=True,
            user_id=source_id,
        )

    async def execute(
        self,
        urls: List[str],
        concurrency: int = 2,
        **kwargs
    ) -> Dict[str, Any]:
        """执行采集任务

        Args:
            urls: 公众号文章URL列表
            concurrency: 并发数
            **kwargs: 其他参数

        Returns:
            采集结果字典
        """
        if not urls:
            return {
                "success": False,
                "error": "未提供文章URL列表",
                "data": []
            }

        logger.info(f"[WechatHarvestAgent] 开始采集 {len(urls)} 篇公众号文章，并发数: {concurrency}")

        # 记录开始采集
        await self._task.log_step(
            1,
            "开始采集",
            {
                "urls_count": len(urls),
                "concurrency": concurrency
            },
            {
                "status": f"准备采集 {len(urls)} 篇文章"
            }
        )
        self._task.progress = 10
        await self._task.save()

        try:
            # 使用 async with ConnectorService（自动清理资源）
            async with ConnectorService(self._playwright, self._source, self._source_id, self._task) as connector_service:
                # 调用 connector 的 get_note_detail 方法采集文章
                results = await connector_service.get_note_details(
                    urls=urls,
                    platform=PlatformType.WECHAT,
                    concurrency=concurrency
                )

                # 统计结果
                success_count = sum(1 for r in results if r.get("success"))
                failed_count = len(results) - success_count

                logger.info(f"[WechatHarvestAgent] 采集完成: 成功 {success_count} 篇，失败 {failed_count} 篇")

                # 记录完成采集
                await self._task.log_step(
                    2,
                    "采集完成",
                    {
                        "success_count": success_count,
                        "failed_count": failed_count,
                        "total_count": len(results)
                    },
                    {
                        "status": f"采集完成: {success_count}/{len(results)} 篇成功"
                    }
                )
                self._task.progress = 40
                await self._task.save()

                # 生成简单的文本报告
                report_lines = [
                    f"# 微信公众号文章采集报告",
                    f"",
                    f"## 采集统计",
                    f"- 总计: {len(results)} 篇",
                    f"- 成功: {success_count} 篇",
                    f"- 失败: {failed_count} 篇",
                    f"",
                    f"## 采集成功文章列表",
                ]

                # 列出成功采集的文章
                for idx, result in enumerate(results, 1):
                    if result.get("success"):
                        data = result.get("data", {})
                        report_lines.append(f"\n{idx}. **{data.get('title', 'N/A')}**")
                        report_lines.append(f"   - 作者: {data.get('author', 'N/A')}")
                        report_lines.append(f"   - 发布时间: {data.get('publish_time', 'N/A')}")
                        report_lines.append(f"   - 阅读量: {data.get('read_count', 0)}")
                        report_lines.append(f"   - 内容长度: {data.get('content_length', 0)} 字符")
                        report_lines.append(f"   - 图片数量: {data.get('image_count', 0)}")
                        report_lines.append(f"   - 详细图片: {data.get('images', 0)}")
                        report_lines.append(f"   - 全文内容: {data.get('content', 'N/A')}")

                self._task.progress = 60
                await self._task.save()

                # 列出失败的文章
                if failed_count > 0:
                    report_lines.append(f"\n## 采集失败列表")
                    for idx, result in enumerate(results, 1):
                        if not result.get("success"):
                            report_lines.append(f"\n{idx}. {result.get('url', 'N/A')}")
                            report_lines.append(f"   - 错误: {result.get('error', 'Unknown')}")

                report = "\n".join(report_lines)

                result = {
                    "success": True,
                    "data": results,
                    "stats": {
                        "total": len(results),
                        "success": success_count,
                        "failed": failed_count
                    }
                }

                # 保存结果到 task（output 字段用于前端显示）
                await self._task.complete({"output": report})
                logger.info(f"[WechatHarvestAgent] 任务完成，结果已保存")

                return result

        except Exception as e:
            logger.error(f"[WechatHarvestAgent] 采集失败: {e}")
            import traceback
            logger.error(traceback.format_exc())

            return {
                "success": False,
                "error": str(e),
                "data": []
            }
