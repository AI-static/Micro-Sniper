"""
Agent服务 - 脚本任务执行方式
"""
from typing import List, Dict, Any, Optional
from config.settings import global_settings
from datetime import datetime
import asyncio
import sys

# Agno imports
from agno.agent import Agent
from agno.models.dashscope import DashScope
from agno.db.postgres import AsyncPostgresDb
from playwright.async_api import async_playwright

# 导入 ConnectorService
from services.connector_service import ConnectorService
from utils.logger import logger

# 1. 数据库连接
db = AsyncPostgresDb(db_url=f"postgresql+asyncpg://{global_settings.database.user}:{global_settings.database.password}@{global_settings.database.host}:{global_settings.database.port}/{global_settings.database.name}")

# 2. 模型配置
resoning_model = DashScope(
    base_url=global_settings.external_service.aliyun_base_url,
    api_key=global_settings.external_service.aliyun_api_key,
    id="qwen-max-latest",
)

class XiaohongshuTrendAnalyzer:
    """小红书爆款分析Agent - 支持流式响应"""

    def __init__(
            self,
            source: str = "system",
            source_id: str = "system",
            playwright: Any = None,
            keywords: str = None
    ):
        self.connector_service = ConnectorService(source=source, source_id=source_id, playwright=playwright)
        self.keywords = keywords
        self.current_date = datetime.now().strftime("%Y-%m-%d")

        self.agent = Agent(
            name="小红书爆款分析师",
            model=resoning_model,
            # debug_mode=True, # 流式模式下开启debug可以看到详细的Tool调用过程
            tool_call_limit=15,
            tools=[
                self.search_xiaohongshu,
                self.get_note_details
            ],
            instructions=[
                f"当前日期: {self.current_date}。重点关注 2025 年的最新趋势。",
                "链路：1.扩展关键词 -> 2.搜索并根据点赞和发布时间筛选 -> 3.获取详情 -> 4.定量分析 -> 5.输出爆款报告。",
                "注意：在流式输出中，请清晰地展示你的思考过程，让用户知道你正在调用哪个工具。"
            ],
            db=db,
            markdown=True,
            add_history_to_context=True,
            user_id=source_id,
        )

    async def search_xiaohongshu(self, keyword: str, limit: int = 20) -> Dict[str, Any]:
        """搜索小红书热门内容"""
        try:
            from models.connectors import PlatformType
            # 这里打印是为了在后台日志中确认动作
            logger.info(f"正在搜索关键词: {keyword}")
            raw_result = await self.connector_service.search_and_extract(
                platform=PlatformType.XIAOHONGSHU,
                keyword=keyword,
                limit=limit
            )
            cleaned_data = [{
                "note_id": item.get("note_id"),
                "title": item.get("title"),
                "liked_count": item.get("liked_count", 0),
                "publish_time": item.get("publish_time", "未知"),
                "full_url": item.get("full_url")
            } for item in raw_result]

            return {"success": True, "data": cleaned_data}
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def get_note_details(self, urls: List[str]) -> Dict[str, Any]:
        """获取笔记详情"""
        try:
            from models.connectors import PlatformType
            result = await self.connector_service.get_note_details(
                urls=urls, platform=PlatformType.XIAOHONGSHU, concurrency=2
            )
            return {"success": True, "data": result}
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def analyze_trends_stream(self):
        """
        核心方法：生成流式响应
        """
        prompt = f"""
        请对关键词「{self.keywords}」进行深度调研。
        要求：
        1. 必须先通过 search_xiaohongshu 搜索。
        2. 挑选出高点赞的笔记，通过 get_note_details 获取正文。
        3. 最后总结出 3 个爆款选题。
        """

        # 使用 arun 开启流模式
        async for chunk in self.agent.arun(prompt, stream=True):
            # Agno 的流式输出 chunk 包含 content 属性
            if chunk and chunk.content:
                yield chunk.content

async def main():
    print("=== 开始执行 Agent 流式任务 ===", flush=True)

    async with async_playwright() as p:

        try:
            analyzer = XiaohongshuTrendAnalyzer(
                source="system",
                source_id="system",
                playwright=p,
                keywords="海豹文创" # 目标词
            )

            print(f"\n[任务目标]: 拆解「{analyzer.keywords}」爆款逻辑\n")
            print("-" * 30 + " Agent 思考与响应 " + "-" * 30)

            # --- 流式接收数据 ---
            async for content in analyzer.analyze_trends_stream():
                # 实时打印到终端，不换行，flush 确保立即显示
                print(content, end="", flush=True)
            # ------------------

            print("\n" + "-" * 78)
            print("\n[任务完成]")

        except Exception as e:
            print(f"\n运行时出错: {e}")

if __name__ == "__main__":
    asyncio.run(main())