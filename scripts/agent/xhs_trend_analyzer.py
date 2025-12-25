"""
Agent服务 - 脚本任务执行方式 (多轮关键词搜索 + 纯LLM推理版)
核心逻辑：
1. 关键词裂变：Agent 自主将核心词扩展为 3 个不同维度的搜索词。
2. 多轮搜索：针对每个扩展词执行搜索，获取更丰富的数据样本。
3. 深度综合：由 LLM 直接阅读笔记详情，不再依赖统计工具。
"""
from typing import List, Dict, Any, Optional
from config.settings import global_settings
from datetime import datetime
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

# 2. 模型配置 (建议使用 qwen-max-latest 以保证多轮调用的逻辑稳定性)
resoning_model = DashScope(
    base_url=global_settings.external_service.aliyun_base_url,
    api_key=global_settings.external_service.aliyun_api_key,
    id="qwen-max-latest",
)

class XiaohongshuDeepAgent:
    """小红书深度爆款分析专家 - 多视角搜索版"""

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
            tool_call_limit=30,
            tools=[
                self.search_xiaohongshu,
                self.get_note_details
            ],
            instructions=[
                f"当前日期: {self.current_date}。你是一个擅长通过多维搜索挖掘爆款逻辑的专家。",
                "你的作业流程如下（必须严格遵守）：",
                f"1. **关键词裂变策略**：不要只搜「{self.keywords}」。请基于用户思维，将其拆解为 3 个具体的搜索方向。例如：",
                "   - 核心词（如：海豹文创）",
                "   - 场景词（如：海豹文创 礼物/办公好物）",
                "   - 痛点/情绪词（如：海豹 治愈系/可爱到犯规）",
                "2. **广域数据采集**：必须 **分别串行调用** `search_xiaohongshu` 工具去搜索这 3 个方向的关键词。严禁只搜一次就交差，如果有并发限制就一个一个调用工具。",
                "3. **精准筛选**：在多轮搜索返回的数十条数据中，综合考量 `liked_count` (点赞) ，挑选出 10-15 篇最具代表性的笔记。",
                "4. **深度解码**：分别串行多次调用（如果有并发限制就一个一个调用工具。） `get_note_details` 读取这些精选笔记的全文，结合 `publish_time` (时效)，挑选出 5-8 篇最具代表性的笔记。重点分析：",
                "   - 标题是如何制造焦虑或期待的？",
                "   - 首图是用什么视觉元素留住用户的？",
                "   - 评论区大家都在问什么？",
                "5. **输出行动指南**：基于以上分析，生成 3 个具体的爆款选题方案。"
            ],
            db=db,
            markdown=True,
            add_history_to_context=True,
            user_id=source_id,
        )

    async def search_xiaohongshu(self, keyword: str, limit: int = 15) -> Dict[str, Any]:
        """
        在小红书搜索指定关键词。
        返回包含：title, note_id, liked_count, publish_time, full_url
        """
        try:
            from models.connectors import PlatformType
            logger.info(f"Agent 正在执行第 N 轮搜索: {keyword}")

            # 调用底层爬虫服务
            raw_result = await self.connector_service.search_and_extract(
                platform=PlatformType.XIAOHONGSHU,
                keyword=keyword,
                limit=limit
            )

            # 数据清洗：只返回 LLM 需要的核心字段，防止 Context 溢出
            cleaned_data = [{
                "note_id": item.get("note_id"),
                "title": item.get("title"),
                "liked_count": item.get("liked_count", 0),
                "publish_time": item.get("publish_time", "未知"),
                "full_url": item.get("full_url")
            } for item in raw_result]

            return {
                "success": True,
                "keyword_used": keyword,
                "count": len(cleaned_data),
                "data": cleaned_data
            }
        except Exception as e:
            # 如果搜索失败，返回错误但不中断整个流程
            return {"success": False, "error": str(e)}

    async def get_note_details(self, full_url: str) -> Dict[str, Any]:
        """
        获取笔记详情（正文、图片描述、评论）
        """
        try:
            from models.connectors import PlatformType
            logger.info(f"Agent 正在深入分析 {len(urls)} 篇精选笔记...")

            result = await self.connector_service.get_note_details(
                urls=[full_url],
                platform=PlatformType.XIAOHONGSHU,
                concurrency=3
            )
            return {"success": True, "data": result}
        except Exception as e:
            return {"success": False, "error": str(e)}

    async def analyze_trends_stream(self):
        """流式任务入口"""
        # Prompt 越简单直接越好，具体的执行逻辑已经写在 instructions 里了
        prompt = f"""
        任务：请对「{self.keywords}」进行多维度的爆款拆解。
        
        请立即开始你的第一步：思考如何裂变关键词，并发起第一轮搜索。
        """

        async for chunk in self.agent.arun(prompt, stream=True):
            if chunk and chunk.content:
                yield chunk.content

# --- 主程序 ---
async def main():
    print("=== 小红书多维爆款分析任务启动 ===", flush=True)

    async with async_playwright() as p:

        try:
            analyzer = XiaohongshuDeepAgent(
                source_id="system",
                playwright=p,
                keywords="海豹文创"  # 核心种子词
            )

            print(f"[核心词]: {analyzer.keywords}")
            print("-" * 80)

            # 流式输出 Agent 的思考与执行过程
            async for content in analyzer.analyze_trends_stream():
                print(content, end="", flush=True)

            print("\n" + "-" * 80)
            print("[任务结束]")

        except Exception as e:
            print(f"\n运行时异常: {e}")
            import traceback
            traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main())