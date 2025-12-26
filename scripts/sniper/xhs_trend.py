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
from services.connector_service import ConnectorService
from utils.logger import logger

# 1. 数据库连接
db = AsyncPostgresDb(
    db_url=f"postgresql+asyncpg://{global_settings.database.user}:{global_settings.database.password}@{global_settings.database.host}:{global_settings.database.port}/{global_settings.database.name}")

# 2. 模型配置
resoning_model = DashScope(
    base_url=global_settings.external_service.aliyun_base_url,
    api_key=global_settings.external_service.aliyun_api_key,
    id="qwen-max-latest",
)

chat_model = DashScope(
    base_url=global_settings.external_service.aliyun_base_url,
    api_key=global_settings.external_service.aliyun_api_key,
    id="qwen-plus",
)

class XiaohongshuDeepAgent:
    """小红书深度爆款分析专家"""

    def __init__(
            self,
            source_id: str = "system_user",
            playwright: Any = None,
            keywords: str = None
    ):
        self.connector_service = ConnectorService(source="system", source_id=source_id, playwright=playwright)
        self.keywords = keywords
        self.current_date = datetime.now().strftime("%Y-%m-%d")

        # === 核心变化 1：Agent 不再挂载 tools ===
        # 它现在只是一个纯粹的分析大脑
        self.agent = Agent(
            name="小红书爆款探针",
            model=chat_model,
            instructions=[
                f"当前日期: {self.current_date}。",
                "你是一个擅长挖掘爆款逻辑的专家。",
                "用户已经为你准备好了【搜索结果】和【笔记详情】的数据。",
                "请你直接阅读这些数据，完成以下分析：",
                "1. **深度解码**：分析笔记标题如何制造焦虑/期待？首图有何视觉吸睛点？评论区痛点是什么？",
                "2. **输出爆款的详细信息**：基于数据，给出原文数据与爆款分析。"
                "3. **输出行动指南**：基于数据，生成 3 个具体的爆款选题方案和建议。"
            ],
            db=db,
            markdown=True,
            add_history_to_context=True,
            user_id=source_id,
        )

        # 用于生成关键词的小号 Agent (轻量级)
        self.planner = Agent(model=resoning_model, description="关键词裂变助手")

    # === 核心变化 2：工具变成了普通的 Python 异步方法 ===
    # 这些方法不再被 Agent 自动调用，而是被 Python 逻辑显式调用

    async def _generate_keywords(self) -> List[str]:
        """前置工作 Step 1: 裂变关键词"""
        logger.info("正在裂变关键词...")
        prompt = f"请基于核心词「{self.keywords}」，裂变出 3 个不同维度的搜索词（核心词、场景词、痛点词）。只返回逗号分隔的关键词字符串，不要其他内容。"
        resp = await self.planner.arun(prompt)
        # 简单的清洗逻辑
        keywords = [k.strip() for k in resp.content.replace("，", ",").split(",") if k.strip()]
        return keywords[:3]  # 确保只取前3个

    async def _run_search(self, keywords: List[str], limit: int = 10) -> List[Dict]:
        """前置工作 Step 2: 执行搜索"""
        from models.connectors import PlatformType
        logger.info(f"正在执行搜索: {keywords}")

        raw_results = await self.connector_service.search_and_extract(
            platform=PlatformType.XIAOHONGSHU,
            keywords=keywords,
            limit=limit
        )

        all_notes = []
        for res in raw_results:
            if res.get("success"):
                all_notes.extend(res.get("data", []))

        # 按点赞数倒序，取前 10 个最有价值的
        sorted_notes = sorted(all_notes, key=lambda x: x.get("liked_count", 0), reverse=True)
        return sorted_notes[:10]

    async def _fetch_details(self, notes: List[Dict]) -> str:
        """前置工作 Step 3: 抓取详情并拼接成文本"""
        from models.connectors import PlatformType

        # 提取 URL
        urls = [n.get("full_url") for n in notes if n.get("full_url")]
        logger.info(f"正在抓取详情，共 {len(urls)} 篇")

        # get_note_details 返回: [{url, success, data, method}, ...]
        details_results = await self.connector_service.get_note_details(
            urls=urls,
            platform=PlatformType.XIAOHONGSHU
        )

        # 构建 url -> detail 映射
        details_map = {}
        for result in details_results:
            if result.get("success") and result.get("data"):
                details_map[result.get("url")] = result.get("data", {})

        # 拼接 context 文本
        context_parts = []
        for i, note in enumerate(notes):
            url = note.get("full_url")
            detail = details_map.get(url, {})
            
            # 提取详情数据（使用新的扁平化字段）
            title = detail.get("title") or note.get("title", "未知标题")
            desc = detail.get("desc", "")
            
            # 互动数据已经是扁平化的整数
            liked_count = detail.get("liked_count", note.get("liked_count", 0))
            collected_count = detail.get("collected_count", 0)
            comment_count = detail.get("comment_count", 0)
            
            # 图片和评论
            images = detail.get("images", [])
            cover_url = images[0].get("url") if images else None
            comments = detail.get("comments", [])

            # 格式化评论（前3条）
            comment_str = ""
            if comments:
                top_comments = comments[:3]
                comment_texts = [
                    f"- {c.get('content', '')[:50]}..."
                    for c in top_comments if c.get("content")
                ]
                comment_str = "\n".join(comment_texts)
            else:
                comment_str = "暂无评论"

            note_str = (
                f"【笔记 {i + 1}】\n"
                f"标题: {title}\n"
                f"封面: {cover_url}\n"
                f"链接: {url}\n"
                f"互动数据: 点赞{liked_count} | 收藏{collected_count} | 评论{comment_count}\n"
                f"正文内容:\n{desc}\n\n"
                f"精选评论:\n{comment_str}\n"
                f"{'='*60}"
            )
            context_parts.append(note_str)

        return "\n\n".join(context_parts)

    async def analyze_trends_stream(self):
        """
        流式任务入口 - 编排逻辑
        """
        yield "🚀 [Step 1] 正在进行关键词裂变...\n"
        search_keywords = await self._generate_keywords()
        yield f" -> 裂变结果: {search_keywords}\n"

        yield "🔍 [Step 2] 正在多线程并发搜索...\n"
        top_notes = await self._run_search(search_keywords)
        yield f" -> 筛选出 {len(top_notes)} 篇头部笔记\n"

        if not top_notes:
            yield "❌ 未搜索到有效数据，任务终止。"
            return

        yield "📖 [Step 3] 正在阅读笔记详情...\n"
        context_data = await self._fetch_details(top_notes)

        yield "🧠 [Step 4] 数据准备完毕，Agent 开始深度分析...\n\n"

        # === 核心：把准备好的数据喂给 Agent ===
        prompt = f"""
        任务核心词：{self.keywords}

        以下是我为你采集到的最新数据：
        {context_data}

        请根据 instructions 开始分析。
        """

        async for chunk in self.agent.arun(prompt, stream=True):
            if chunk and chunk.content:
                yield chunk.content


# --- 主程序 ---
async def main():
    start_time = datetime.now()
    print("=== 小红书多维爆款分析任务启动 ===", flush=True)
    print(f"⏰ 任务开始时间: {start_time.strftime('%Y-%m-%d %H:%M:%S')}", flush=True)

    async with async_playwright() as p:
        try:
            analyzer = XiaohongshuDeepAgent(
                source_id="system",
                playwright=p,
                keywords="agent面试"
            )

            print(f"[核心词]: {analyzer.keywords}")
            print("-" * 80)

            async for content in analyzer.analyze_trends_stream():
                print(content, end="", flush=True)

            end_time = datetime.now()
            duration = (end_time - start_time).total_seconds()

            print("\n" + "-" * 80)
            print("[任务结束]")
            print(f"⏰ 任务结束时间: {end_time.strftime('%Y-%m-%d %H:%M:%S')}", flush=True)
            print(f"⏱️  任务耗时: {duration:.2f} 秒", flush=True)

        except Exception as e:
            print(f"\n运行时异常: {e}")
            import traceback
            traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())