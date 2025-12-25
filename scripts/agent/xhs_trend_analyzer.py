"""
Agent服务 - 强制顺序执行版
核心目标：禁止并发，强制 Agent "想一步 -> 走一步 -> 看一步"。
"""
from typing import List, Dict, Any, Optional
from config.settings import global_settings
from datetime import datetime, timedelta
import asyncio

# Agno imports
from agno.agent import Agent
from agno.models.dashscope import DashScope
from agno.db.postgres import AsyncPostgresDb
from playwright.async_api import async_playwright

# 导入外部 Service
from services.connector_service import ConnectorService
from utils.logger import logger

# 1. 数据库连接
db = AsyncPostgresDb(db_url=f"postgresql+asyncpg://{global_settings.database.user}:{global_settings.database.password}@{global_settings.database.host}:{global_settings.database.port}/{global_settings.database.name}")

# 2. 模型配置
resoning_model = DashScope(
    base_url=global_settings.external_service.aliyun_base_url,
    api_key=global_settings.external_service.aliyun_api_key,
    id="qwen-max-latest", # 使用最新模型以更好地遵循复杂指令
)

class XiaohongshuDeepAgent:
    """小红书深度分析 Agent - 顺序执行版"""

    def __init__(
            self,
            source_id: str = "system_user",
            playwright: Any = None,
            keywords: str = None
    ):
        self.connector_service = ConnectorService(source="system", source_id=source_id, playwright=playwright)
        self.keywords = keywords
        self.current_date = datetime.now().strftime("%Y-%m-%d")

        self.agent = Agent(
            name="小红书爆款探针",
            model=resoning_model,
            tool_call_limit=30, # 必须足够大，因为顺序执行意味着交互轮数变多
            tools=[
                self.search_xiaohongshu,
                self.get_note_details
            ],
            instructions=[
                f"当前日期: {self.current_date}。",
                "你的任务是针对关键词进行多维度、实效性的爆款拆解。",
                "",
                "## ⚠️ 严格执行协议 (必须遵守)",
                "1. **单线程工作模式**：为了防止触发反爬虫机制，**你每次回复只能调用【唯一】的一个工具**。严禁在一次回复中同时申请调用多个工具（如同时搜3个词）。",
                "2. **顺序执行逻辑**：",
                "   - 动作 A：规划第 1 个关键词 -> 调用搜索 -> 等待结果返回。",
                "   - 动作 B：分析第 1 次结果 -> 规划第 2 个关键词 -> 调用搜索 -> 等待结果返回。",
                "   - 动作 C：...以此类推。",
                "",
                "## 任务流程",
                f"1. **关键词规划**：围绕「{self.keywords}」构思 3 个不同维度的搜索词（核心词、场景词、痛点词）。",
                "2. **轮询搜索**：请**逐一**对这 3 个词发起 `search_xiaohongshu`。",
                "3. **实效性筛选**：",
                "   - 重点关注 `publish_time` 在近 7-15 天内的笔记。",
                "   - 忽略 30 天以前的内容。",
                "4. **详情深挖**：搜集完所有搜索结果后，挑选 3-5 篇最值得分析的笔记，**逐一**或一次性（仅此处允许批量）调用 `get_note_details`。",
                "5. **最终报告**：输出 3 个具备实效性的爆款选题。"
            ],
            db=db,
            markdown=True,
            add_history_to_context=True,
            user_id=source_id,
        )

    async def search_xiaohongshu(self, keyword: str, limit: int = 15) -> Dict[str, Any]:
        """
        搜索小红书。
        """
        try:
            from models.connectors import PlatformType
            logger.info(f"⚡️ Agent 正在顺序执行搜索: {keyword}")

            # 可以在这里人为加一个短暂 sleep，确保顺序感更强，且对平台更友好
            # await asyncio.sleep(2)

            raw_result = await self.connector_service.search_and_extract(
                platform=PlatformType.XIAOHONGSHU,
                keyword=keyword,
                limit=limit
            )

            # 清洗数据
            cleaned_data = []
            for item in raw_result:
                cleaned_data.append({
                    "note_id": item.get("note_id"),
                    "title": item.get("title"),
                    "liked_count": item.get("liked_count", 0),
                    "publish_time": item.get("publish_time", "未知"),
                    "full_url": item.get("full_url")
                })

            return {
                "success": True,
                "keyword_current": keyword,
                "status": "本轮搜索完成，请分析数据后决定是否需要搜索下一个词。",
                "data": cleaned_data
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def get_note_details(self, urls: List[str]) -> Dict[str, Any]:
        """获取笔记详情"""
        try:
            from models.connectors import PlatformType
            logger.info(f"📖 Agent 正在阅读 {len(urls)} 篇笔记详情...")

            result = await self.connector_service.get_note_details(
                urls=urls,
                platform=PlatformType.XIAOHONGSHU,
                concurrency=3
            )
            return {"success": True, "data": result}
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def analyze_trends_stream(self):
        """流式分析"""
        prompt = f"""
        任务启动：请对「{self.keywords}」进行多维度爆款拆解。
        
        请记住：**不要着急，一个一个搜**。
        请立即开始规划第 1 个关键词并执行搜索。
        """

        async for chunk in self.agent.arun(prompt, stream=True):
            if chunk and chunk.content:
                yield chunk.content

async def main():
    print("=== 小红书顺序执行 Agent 启动 ===", flush=True)

    async with async_playwright() as p:
        try:
            analyzer = XiaohongshuDeepAgent(
                source_id="system",
                playwright=p,
                keywords="海豹文创"
            )

            print(f"[目标]: {analyzer.keywords} (强制顺序模式)")
            print("-" * 60)

            async for content in analyzer.analyze_trends_stream():
                print(content, end="", flush=True)

            print("\n" + "-" * 60)
            print("[任务结束]")

        except Exception as e:
            print(f"\n执行异常: {e}")


if __name__ == "__main__":
    asyncio.run(main())