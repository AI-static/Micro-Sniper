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
from utils.logger import logger

# 1. 数据库连接
db = AsyncPostgresDb(
    db_url=f"postgresql+asyncpg://{global_settings.database.user}:{global_settings.database.password}@{global_settings.database.host}:{global_settings.database.port}/{global_settings.database.name}")

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

class XiaohongshuTrendAgent(BaseAgent):
    """小红书深度爆款分析专家"""

    def __init__(
            self,
            source_id: str = "system_user",
            source: str = "system",
            playwright: Any = None,
            task: Task = None
    ):
        super().__init__(source_id, source, playwright, task)
        self.current_date = datetime.now().strftime("%Y-%m-%d")

        # === 核心变化 1：Agent 不再挂载 tools ===
        # 它现在只是一个纯粹的分析大脑
        self.agent = Agent(
            name="爆款探针",
            model=chat_model,
            instructions=[
                f"当前日期: {self.current_date}。",
                "你是一个擅长挖掘爆款逻辑的专家。",
                "用户已经为你准备好了【搜索结果】和【笔记详情】的数据。",
                "请你直接阅读这些数据，完成以下分析：",
                "1. **深度解码**：分析笔记标题如何制造焦虑/期待？首图有何视觉吸睛点？评论区痛点是什么？",
                "2. **输出爆款的详细信息**：基于数据，给出原文数据与爆款分析。",
                "3. **输出行动指南**：基于数据，生成 3 个具体的爆款选题方案和建议。",
                "4. **证据链条**：重要！在分析每个观点时，必须引用具体笔记的完整URL（字段full_url）作为证据，让分析可追溯。"
            ],
            db=db,
            markdown=True,
            add_history_to_context=True,
            user_id=source_id,
        )

        # 用于生成关键词的小号 Agent (轻量级)
        self.planner = Agent(model=reasoning_model, description="关键词裂变助手")

    # === 核心变化 2：工具变成了普通的 Python 异步方法 ===
    # 这些方法不再被 Agent 自动调用，而是被 Python 逻辑显式调用

    async def _generate_keywords(self, core_keyword: str) -> List[str]:
        """前置工作 Step 1: 裂变关键词"""
        logger.info("正在裂变关键词...")
        prompt = f"请基于核心词「{core_keyword}」融合这三个点，裂变出 3 个不同维度的搜索词（核心词、场景词、痛点词）。只返回逗号分隔的关键词字符串，不要其他内容。"
        resp = await self.planner.arun(prompt)
        # 简单的清洗逻辑
        keywords = [k.strip() for k in resp.content.replace("，", ",").split(",") if k.strip()]
        return keywords  # 确保只取前3个

    async def _run_search(self, keywords: List[str], connector_service, limit: int = 10) -> List[Dict]:
        """前置工作 Step 2: 执行搜索"""
        from models.connectors import PlatformType
        logger.info(f"正在执行搜索: {keywords}")

        # 记录开始搜索
        await self._task.log_step(
            2,
            "执行搜索",
            {
                "keywords": keywords,
                "limit": limit
            },
            {
                "status": f"开始搜索 {len(keywords)} 个关键词"
            }
        )

        raw_results = await connector_service.search_and_extract(
            platform=PlatformType.XIAOHONGSHU,
            keywords=keywords,
            limit=limit
        )

        all_notes = []
        for res in raw_results:
            if res.get("success"):
                all_notes.extend(res.get("data", []))

        # === 去重逻辑：基于帖子唯一标识 ===
        # 使用 note_id 或 full_url 作为唯一标识
        seen_note_ids = set()
        unique_notes = []

        for note in all_notes:
            # 优先使用 note_id，如果没有则使用 full_url
            note_id = note.get("note_id") or note.get("full_url")

            if note_id and note_id not in seen_note_ids:
                seen_note_ids.add(note_id)
                unique_notes.append(note)

        logger.info(f"搜索结果去重: {len(all_notes)} 条 -> {len(unique_notes)} 条唯一帖子")

        # 按点赞数倒序，取前 10 个最有价值的
        sorted_notes = sorted(unique_notes, key=lambda x: x.get("liked_count", 0), reverse=True)
        top_notes = sorted_notes[:10]

        # 记录搜索完成
        await self._task.log_step(
            2,
            "执行搜索",
            {
                "keywords": keywords
            },
            {
                "status": f"搜索完成，获得 {len(all_notes)} 条结果，去重后 {len(unique_notes)} 条",
                "raw_count": len(all_notes),
                "unique_count": len(unique_notes),
                "top_count": len(top_notes)
            }
        )

        return top_notes

    async def _fetch_details(self, notes: List[Dict], connector_service) -> str:
        """前置工作 Step 3: 抓取详情并拼接成文本"""
        from models.connectors import PlatformType

        # 提取 URL
        urls = [n.get("full_url") for n in notes if n.get("full_url")]
        logger.info(f"正在抓取详情，共 {len(urls)} 篇")

        # 记录开始获取详情
        await self._task.log_step(
            3,
            "获取笔记详情",
            {
                "note_count": len(notes),
                "urls": urls[:3]  # 只记录前3个URL作为示例
            },
            {
                "status": f"开始获取 {len(urls)} 篇笔记的详情"
            }
        )

        # 分批获取笔记详情，避免浏览器拨打过快
        batch_size = 3
        all_details_results = []

        for i in range(0, len(urls), batch_size):
            batch_urls = urls[i:i + batch_size]
            logger.info(f"正在处理批次 {i//batch_size + 1}, URLs: {batch_urls}")

            batch_results = await connector_service.get_note_details(
                urls=batch_urls,
                platform=PlatformType.XIAOHONGSHU,
                concurrency=2  # 每批内部并发2个
            )

            all_details_results.extend(batch_results)
            logger.info(f"批次 {i//batch_size + 1} 完成，获取 {len(batch_results)} 个结果")

        details_results = all_details_results

        # 构建 url -> detail 映射
        details_map = {}
        success_count = 0
        for result in details_results:
            if result.get("success") and result.get("data"):
                details_map[result.get("url")] = result.get("data", {})
                success_count += 1

        logger.info(f"详情获取完成: {success_count}/{len(urls)} 成功")

        # 记录每篇笔记的详情
        for i, note in enumerate(notes):
            url = note.get("full_url")
            detail = details_map.get(url, {})

            title = detail.get("title") or note.get("title", "未知标题")
            liked_count = detail.get("liked_count", note.get("liked_count", 0))

            if detail and title:
                # 成功获取详情
                await self._task.log_step(
                    3,
                    f"解析笔记 [{i+1}/{len(notes)}]",
                    {
                        "note_index": i + 1,
                        "title": title,
                        "url": url
                    },
                    {
                        "status": f"解析成功: {title[:30]}",
                        "liked_count": liked_count,
                        "has_detail": True
                    }
                )
            else:
                # 获取详情失败
                await self._task.log_step(
                    3,
                    f"解析笔记 [{i+1}/{len(notes)}]",
                    {
                        "note_index": i + 1,
                        "url": url
                    },
                    {
                        "status": "解析失败",
                        "has_detail": False
                    }
                )

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

    async def execute(self, keywords) -> str:
        """
        执行趋势分析任务 - 统一入口方法

        Args:
            keywords

        Returns:
            分析结果
        """

        try:
            if not keywords:
                # 记录错误参数
                await self._task.fail("无输入，请输入有效关键字重试", 0)
                await self._task.save()
                return "无输入，请输入有效关键字重试"

            # 记录初始参数
            await self._task.log_step(0, "任务初始化",
                              {"keywords": keywords},
                              {"task_id": str(self._task.id), "source": self._source})
            self._task.progress = 10
            await self._task.save()

            # === AI Native 登录检查 ===
            # 在执行任务前，先检查平台登录状态
            from services.sniper.connectors.xiaohongshu import XiaohongshuConnector

            connector = XiaohongshuConnector(playwright=self._playwright)

            # 调用公共方法检查登录状态
            # 方法内部会自动处理 session、browser、context 的创建和清理
            login_res = await connector.login_with_qrcode(
                source=self._source,
                source_id=self._source_id
            )
            logger.info(f"login_res --> {login_res}")
            if not login_res.get("is_logged_in"):
                # 未登录，暂停任务并保存登录信息
                await self._task.waiting_login(login_res)
                logger.info(f"[xhs_trend] 任务 {task.id} 等待登录")
                return "等待登录"

            # Step 1: 关键词裂变
            search_keywords = await self._generate_keywords(keywords[0] if isinstance(keywords, list) else keywords)
            await self._task.log_step(1, "关键词裂变",
                              {"core_keyword": keywords},
                              {"keywords": search_keywords})
            self._task.progress = 25
            await self._task.save()

            # 使用 async with ConnectorService
            async with ConnectorService(self._playwright, self._source, self._source_id, self._task) as connector_service:
                # Step 2: 搜索并去重
                top_notes = await self._run_search(search_keywords, connector_service)
                if not top_notes:
                    await self._task.fail("未搜索到有效数据", self._task.progress)
                    return ""

                self._task.progress = 50
                await self._task.save()

                # Step 3: 获取详情
                context_data = await self._fetch_details(top_notes, connector_service)

                # 记录获取详情完成
                await self._task.log_step(3, "获取笔记详情",
                                  {"note_count": len(top_notes)},
                                  {
                                    "status": f"详情获取完成，共 {len(context_data)} 字符",
                                    "context_length": len(context_data)
                                  })
                self._task.progress = 70
                await self._task.save()

                # Step 4: Agent 分析
                prompt = f"""
                任务核心词：{keywords}

                以下是我为你采集到的最新数据：
                {context_data}

                请根据 instructions 开始分析。

                **重要提醒**：在输出分析和建议时，必须为每个观点提供证据链条，引用具体笔记的完整URL（full_url）。
                """

                analysis_result = await self.agent.arun(prompt)
                analysis = analysis_result.content

                await self._task.log_step(4, "Agent分析",
                                  {"data_size": len(context_data)},
                                  {"analysis_length": len(analysis)})
                self._task.progress = 95
                await self._task.save()

                # AI Native: Agent 的分析结果本身就是自然语言，直接存储
                # 无需额外格式化，LLM 生成的分析结果就是最适合 AI 阅读的格式
                await self._task.complete({"output": analysis})
                return analysis

        except Exception as e:
            import traceback
            logger.error(f"趋势分析失败: {traceback.format_exc()}")
            await self._task.fail(str(e), self._task.progress)
            raise

    async def _run_search_no_task(self, keywords: List[str], connector_service, limit: int = 10) -> List[Dict]:
        """前置工作 Step 2: 执行搜索 (不带 task，用于 stream 版本)"""
        from models.connectors import PlatformType
        logger.info(f"正在执行搜索: {keywords}")

        raw_results = await connector_service.search_and_extract(
            platform=PlatformType.XIAOHONGSHU,
            keywords=keywords,
            limit=limit,
            concurrency=2
        )

        all_notes = []
        for res in raw_results:
            if res.get("success"):
                all_notes.extend(res.get("data", []))

        # === 去重逻辑：基于帖子唯一标识 ===
        seen_note_ids = set()
        unique_notes = []

        for note in all_notes:
            note_id = note.get("note_id") or note.get("full_url")
            if note_id and note_id not in seen_note_ids:
                seen_note_ids.add(note_id)
                unique_notes.append(note)

        logger.info(f"搜索结果去重: {len(all_notes)} 条 -> {len(unique_notes)} 条唯一帖子")

        sorted_notes = sorted(unique_notes, key=lambda x: x.get("liked_count", 0), reverse=True)
        return sorted_notes[:10]

    async def _fetch_details_no_task(self, notes: List[Dict], connector_service) -> str:
        """前置工作 Step 3: 抓取详情并拼接成文本 (不带 task，用于 stream 版本)"""
        from models.connectors import PlatformType

        urls = [n.get("full_url") for n in notes if n.get("full_url")]
        logger.info(f"正在抓取详情，共 {len(urls)} 篇")

        # 分批获取笔记详情，避免浏览器拨打过快
        batch_size = 3
        all_details_results = []

        for i in range(0, len(urls), batch_size):
            batch_urls = urls[i:i + batch_size]
            logger.info(f"正在处理批次 {i//batch_size + 1}, URLs: {batch_urls}")

            batch_results = await connector_service.get_note_details(
                urls=batch_urls,
                platform=PlatformType.XIAOHONGSHU,
                concurrency=2  # 每批内部并发2个
            )

            all_details_results.extend(batch_results)
            logger.info(f"批次 {i//batch_size + 1} 完成，获取 {len(batch_results)} 个结果")

        details_results = all_details_results

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

            title = detail.get("title") or note.get("title", "未知标题")
            desc = detail.get("desc", "")

            liked_count = detail.get("liked_count", note.get("liked_count", 0))
            collected_count = detail.get("collected_count", 0)
            comment_count = detail.get("comment_count", 0)

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


# ========== 脚本主程序 ==========
async def main():
    source = "service"
    source_id = "default"
    from tortoise import Tortoise
    from config.settings import create_db_config

    await Tortoise.init(config=create_db_config())

    start_time = datetime.now()
    print("=== 小红书trend分析启动 ===", flush=True)
    print(f"⏰ 任务开始时间: {start_time.strftime('%Y-%m-%d %H:%M:%S')}", flush=True)

    async with async_playwright() as p:
        try:
            # 创建任务
            task = await Task.create(
                source=source,
                source_id=source_id,
                task_type="trend_analysis"
            )
            await self._task.start()

            keywords = ["SKG", "健康穿戴", "按摩仪"]
            keywords = ["后端开发", "Agent"]
            # 重新创建 analyzer，传入 task
            analyzer = XiaohongshuTrendAgent(
                source_id=source_id,
                source=source,
                playwright=p,
                task=task
            )

            print(f"[核心词]: {analyzer.keywords}")
            print("-" * 30)
            print(f"[Task ID]: {task.id}")

            # 执行分析
            analysis = await analyzer.execute(keywords=keywords)
            print(analysis, flush=True)

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