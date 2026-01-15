# -*- coding: utf-8 -*-
"""微信公众号文章分析 Agent"""

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
reasoning_model = DashScope(
    base_url=global_settings.external_service.aliyun_base_url,
    api_key=global_settings.external_service.aliyun_api_key,
    id="qwen-max-latest",
)

chat_model = DashScope(
    base_url=global_settings.external_service.aliyun_base_url,
    api_key=global_settings.external_service.aliyun_api_key,
    id="qwen-plus",
)


class WechatAnalyzeAgent(BaseAgent):
    """微信公众号文章分析专家 - 使用 LLM 深度分析公众号内容"""

    def __init__(
            self,
            source_id: str = "system_user",
            source: str = "system",
            playwright: Any = None,
            task: Task = None
    ):
        super().__init__(source_id, source, playwright, task)
        self.current_date = datetime.now().strftime("%Y-%m-%d")

        # 主分析 Agent
        self.agent = Agent(
            name="微信内容分析师",
            model=reasoning_model,
            instructions=[
                f"当前日期: {self.current_date}。",
                "你是一个擅长分析微信公众号内容的专家。",
                "你将对用户提供的公众号文章数据进行深度分析，挖掘内容价值。",
                "请从以下维度进行分析：",
                "1. **核心观点提炼**：提取文章的核心论点和观点，总结文章主旨。",
                "2. **目标受众分析**：分析文章的目标读者群体特征、需求痛点。",
                "3. **内容结构分析**：分析文章的逻辑结构、论证方式、修辞手法。",
                "4. **价值评估**：评估文章的信息价值、实用价值、传播价值。",
                "5. **写作特点**：总结作者的写作风格、语言特色、标题技巧。",
                "6. **改进建议**：给出优化内容的具体建议。",
                "",
                "**重要提醒**：",
                "- 保持客观中立，基于事实数据进行分析",
                "- 引用文章具体内容作为证据支撑你的观点",
                "- 输出结构化、层次分明的分析报告"
            ],
            db=db,
            markdown=True,
            add_history_to_context=True,
            user_id=source_id,
        )

        # 用于生成分析维度的轻量级 Agent
        self.planner = Agent(
            model=chat_model,
            description="分析规划助手"
        )

    async def execute(
        self,
        articles: str,
        analysis_type: str = "comprehensive",
        **kwargs
    ) -> Dict[str, Any]:
        """执行分析任务

        Args:
            articles: 文章内容字符串（URLs、JSON 或直接的文章内容）
            analysis_type: 分析类型
                - "comprehensive": 全面分析（默认）
                - "quick": 快速分析
                - "comparison": 对比分析（多篇文章）
                - "trend": 趋势分析
            **kwargs: 其他参数

        Returns:
            分析结果字典
        """
        if not articles or not articles.strip():
            return {
                "success": False,
                "error": "未提供文章数据",
                "analysis": ""
            }

        logger.info(f"[WechatAnalyzeAgent] 开始分析公众号文章，分析类型: {analysis_type}")

        # 记录开始分析
        await self._task.log_step(
            1,
            "开始分析",
            {
                "analysis_type": analysis_type,
                "content_length": len(articles)
            },
            {
                "status": "准备分析文章内容"
            }
        )
        self._task.progress = 10
        await self._task.save()
        try:
            # 根据分析类型选择不同的分析方法
            if analysis_type == "comprehensive":
                analysis = await self._comprehensive_analysis(articles)
            elif analysis_type == "quick":
                analysis = await self._quick_analysis(articles)
            elif analysis_type == "comparison":
                analysis = await self._comparison_analysis(articles)
            elif analysis_type == "trend":
                analysis = await self._trend_analysis(articles)
            else:
                analysis = await self._comprehensive_analysis(articles)

            logger.info(f"[WechatAnalyzeAgent] 分析完成")

            # 记录完成分析
            await self._task.log_step(
                2,
                "分析完成",
                {
                    "analysis_type": analysis_type
                },
                {
                    "status": "分析完成"
                }
            )
            self._task.progress = 60
            await self._task.save()
            # 保存结果到 task（output 字段用于前端显示）
            await self._task.complete({"output": analysis})
            logger.info(f"[WechatAnalyzeAgent] 任务完成，结果已保存")

            return {
                "success": True,
                "analysis": analysis,
                "analysis_type": analysis_type,
                "articles_count": len(articles)
            }

        except Exception as e:
            logger.error(f"[WechatAnalyzeAgent] 分析失败: {e}")
            import traceback
            logger.error(traceback.format_exc())

            return {
                "success": False,
                "error": str(e),
                "analysis": ""
            }

    async def _comprehensive_analysis(self, articles: str) -> str:
        """全面分析

        Args:
            articles: 文章内容字符串

        Returns:
            分析报告
        """
        logger.info("[WechatAnalyzeAgent] 执行全面分析")

        prompt = f"""请对以下公众号文章内容进行全面深度分析：

## 文章内容

{articles}

## 分析要求

请按照以下结构生成分析报告：

### 一、整体概览
- 内容主题分析
- 文章结构分析

### 二、核心观点提炼
- 提取文章的核心论点和观点
- 总结文章主旨

### 三、内容深度分析
1. 目标受众分析
2. 内容结构与逻辑
3. 写作风格与技巧
4. 价值评估（信息价值、实用价值、传播价值）

### 四、改进建议
基于分析结果，给出3-5条具体的改进建议

请开始你的分析：
"""

        response = await self.agent.arun(prompt)
        return response.content if response else "分析生成失败"

    async def _quick_analysis(self, articles: str) -> str:
        """快速分析

        Args:
            articles: 文章内容字符串

        Returns:
            简要分析报告
        """
        logger.info("[WechatAnalyzeAgent] 执行快速分析")

        prompt = f"""请对以下公众号文章内容进行快速简要分析：

## 文章内容

{articles}

要求：
1. 用3-5句话概括整体内容
2. 指出1-2个亮点
3. 给出1条改进建议

请开始：
"""

        response = await self.agent.arun(prompt)
        return response.content if response else "快速分析生成失败"

    async def _comparison_analysis(self, articles: str) -> str:
        """对比分析

        Args:
            articles: 文章内容字符串（多篇）

        Returns:
            对比分析报告
        """
        logger.info("[WechatAnalyzeAgent] 执行对比分析")

        prompt = f"""请对以下公众号文章内容进行对比分析：

## 文章内容

{articles}

请从以下维度进行对比：
1. 内容主题对比
2. 写作风格对比
3. 内容结构对比
4. 优劣势对比
5. 适用场景对比

请生成详细的对比分析报告：
"""

        response = await self.agent.arun(prompt)
        return response.content if response else "对比分析生成失败"

    async def _trend_analysis(self, articles: str) -> str:
        """趋势分析

        Args:
            articles: 文章内容字符串

        Returns:
            趋势分析报告
        """
        logger.info("[WechatAnalyzeAgent] 执行趋势分析")

        prompt = f"""请基于以下公众号文章内容，分析内容趋势：

## 文章内容

{articles}

请分析：
1. 主题演化趋势
2. 内容风格变化
3. 价值观点趋势
4. 未来发展趋势预测

请生成趋势分析报告：
"""

        response = await self.agent.arun(prompt)
        return response.content if response else "趋势分析生成失败"