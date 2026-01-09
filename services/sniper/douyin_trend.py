# -*- coding: utf-8 -*-
"""抖音趋势分析模块"""

from typing import List, Dict, Any, Optional
from config.settings import global_settings
from datetime import datetime
import asyncio
import json

# Agno imports
from agno.agent import Agent
from agno.models.dashscope import DashScope
from agno.db.postgres import AsyncPostgresDb

from .connectors.connector_service import ConnectorService
from models.task import Task
from utils.logger import logger
from models.connectors import PlatformType

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


class DouyinDeepAgent:
    """抖音深度爆款分析专家"""

    def __init__(
        self,
        source_id: str = "system_user",
        source: str = "system",
        playwright: Any = None,
        task: Task = None
    ):
        self._playwright = playwright
        self._task = task
        self._source = source
        self._source_id = source_id
        self.current_date = datetime.now().strftime("%Y-%m-%d")

        # Agent 配置
        self.agent = Agent(
            name="抖音爆款探针",
            model=chat_model,
            instructions=[
                f"当前日期: {self.current_date}",
                "你是抖音平台的爆款内容分析专家。",
                "用户已为你准备好【搜索结果】和【视频详情】数据。",
                "请你完成以下分析：",
                "1. **深度解码**：分析视频标题、封面、文案策略、评论区痛点",
                "2. **输出爆款分析**：基于数据给出详细分析",
                "3. **输出行动指南**：生成3个具体的爆款选题方案",
                "4. **证据链条**：引用具体视频的完整URL作为证据"
            ],
            db=db,
            markdown=True,
            add_history_to_context=True,
            user_id=source_id,
        )

        # 关键词裂变助手
        self.planner = Agent(model=reasoning_model, description="抖音关键词裂变助手")

    async def _generate_keywords(self, keywords) -> List[str]:
        """关键词裂变"""
        logger.info("[douyin] 正在裂变关键词...")
        prompt = f"请基于核心词「{keywords}」融合抖音平台特点，裂变出3个不同维度的搜索词（核心词、场景词、痛点词）。只返回逗号分隔的关键词字符串。"
        resp = await self.planner.arun(prompt)
        keywords = [k.strip() for k in resp.content.replace("，", ",").split(",") if k.strip()]
        return keywords

    async def execute(self, keywords) -> str:
        """
        执行抖音趋势分析任务 - 统一入口方法

        Args:
            keywords: 关键词列表

        Returns:
            分析结果
        """
        try:
            # 记录初始参数
            await self._task.log_step(0, "任务初始化",
                              {"keywords": keywords},
                              {"task_id": str(self._task.id), "source": self._source})
            self._task.progress = 10
            await self._task.save()

            # Step 1: 关键词裂变
            search_keywords = await self._generate_keywords(keywords)
            await self._task.log_step(1, "关键词裂变",
                              {"core_keyword": keywords},
                              {"keywords": search_keywords})
            self._task.progress = 25
            await self._task.save()

            # 使用 ConnectorService 搜索和分析
            async with ConnectorService(self._playwright, self._source, self._source_id, self._task) as connector_service:
                # Step 2: 搜索抖音视频
                from models.connectors import PlatformType

                logger.info(f"[douyin] 开始搜索关键词: {search_keywords}")
                search_results = await connector_service.search_and_extract(
                    platform=PlatformType.DOUYIN,
                    keywords=search_keywords,
                    limit=10
                )

                # 提取视频URL
                all_videos = []
                for result in search_results:
                    if result.get("success"):
                        all_videos.extend(result.get("data", []))

                if not all_videos:
                    await self._task.fail("未搜索到有效数据", self._task.progress)
                    return ""

                await self._task.log_step(2, "搜索完成",
                                  {"keywords": search_keywords},
                                  {"video_count": len(all_videos)})
                self._task.progress = 50
                await self._task.save()

                # Step 3: 获取视频详情
                video_urls = [v.get("url") for v in all_videos if v.get("url")]
                detail_results = await connector_service.get_note_details(
                    urls=video_urls[:10],
                    platform=PlatformType.DOUYIN,
                    concurrency=2
                )

                # 拼接上下文
                context_parts = []
                for i, result in enumerate(detail_results):
                    if result.get("success"):
                        data = result.get("data", {})
                        context_parts.append(f"""
【视频 {i + 1}】
标题: {data.get('title', 'N/A')}
作者: {data.get('author', 'N/A')}
点赞: {data.get('liked_count', 0)}
评论: {data.get('comment_count', 0)}
描述: {data.get('desc', 'N/A')[:200]}
链接: {result.get('url', 'N/A')}
{'='*60}
                        """)

                context_data = "\n\n".join(context_parts)

                await self._task.log_step(3, "详情获取完成",
                                  {"video_count": len(context_parts)},
                                  {"context_length": len(context_data)})
                self._task.progress = 70
                await self._task.save()

                # Step 4: Agent 分析
                prompt = f"""
抖音核心词：{keywords}

以下是为你采集到的最新数据：
{context_data}

请根据 instructions 开始分析。

**重要提醒**：必须为每个观点提供证据，引用具体视频的完整URL。
                """

                analysis_result = await self.agent.arun(prompt)
                analysis = analysis_result.content

                await self._task.log_step(4, "Agent分析完成",
                                  {"data_size": len(context_data)},
                                  {"analysis_length": len(analysis)})
                self._task.progress = 95
                await self._task.save()

                await self._task.complete({"output": analysis})
                return analysis

        except Exception as e:
            logger.error(f"[douyin] 趋势分析失败: {e}")
            await self._task.fail(str(e), self._task.progress)
            raise


# ========== 脚本主程序 ==========
async def main():
    """独立运行脚本"""
    source = "service"
    source_id = "default"
    from tortoise import Tortoise
    from config.settings import create_db_config

    await Tortoise.init(config=create_db_config())

    start_time = datetime.now()
    print("=== 抖音趋势分析启动 ===")
    print(f"⏰ 开始时间: {start_time.strftime('%Y-%m-%d %H:%M:%S')}")

    try:


        # 创建任务
        task = await Task.create(
            source=source,
            source_id=source_id,
            task_type="trend_analysis"
        )
        await task.start()

        analyzer = DouyinDeepAgent(
            source=source,
            source_id=source_id,
            task=task
        )

        # 执行分析
        analysis = await analyzer.execute(keywords=["美食探店"])
        print(analysis)

        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()
        print(f"\n⏱️  耗时: {duration:.2f} 秒")

    except Exception as e:
        print(f"错误: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())