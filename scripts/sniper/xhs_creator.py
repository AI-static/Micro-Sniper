# -*- coding: utf-8 -*-
"""创作者狙击手 - 定时监控多个创作者的新内容

功能：
1. 监控指定创作者列表
2. 获取其笔记列表
3. 检查每篇笔记的发布时间
4. 筛选出今天发布的内容
5. 输出配置时间内新发布笔记详情
"""

import asyncio
from datetime import datetime, timedelta
from typing import List, Dict, Any
from playwright.async_api import async_playwright

from services.connector_service import ConnectorService
from models.connectors import PlatformType
from utils.logger import logger


class CreatorSniper:
    """创作者狙击手 - 监控新内容"""

    def __init__(self, source_id: str = "system", playwright: Any = None):
        self.connector_service = ConnectorService(
            source="system",
            source_id=source_id,
            playwright=playwright
        )
        self.today = datetime.now().date()
        self.lantcy = 7

    async def monitor_creators(
        self,
        creator_ids: List[str]
    ) -> Dict[str, Any]:
        """
        监控多个创作者，找出今天发布的内容

        Args:
            creator_ids: 创作者ID列表

        Returns:
            监控结果 {
                "total_creators": int,
                "monitored_creators": int,
                "today_notes_count": int,
                "results": {
                    creator_id: {
                        "success": bool,
                        "total_notes": int,
                        "today_notes_count": int,
                        "today_notes": [...]
                    }
                }
            }
        """
        logger.info(f"开始监控 {len(creator_ids)} 个创作者")

        # 1. 获取所有创作者的笔记列表
        harvest_results = await self.connector_service.harvest_user_content(
            platform=PlatformType.XIAOHONGSHU,
            creator_ids=creator_ids,
            limit=None  # 获取所有笔记
        )

        # 2. 整理结果
        results = {}
        total_today_notes = 0
        monitored_creators = 0

        for result in harvest_results:
            creator_id = result.get("creator_id")
            notes = result.get("data", []) if result.get("success") else []

            if result.get("success"):
                # 筛选今天的笔记和上次发布
                filter_result = await self._filter_today_notes(notes)
                today_notes = filter_result.get("today_notes", [])
                last_note = filter_result.get("last_note")

                monitored_creators += 1
                total_today_notes += len(today_notes)

                results[creator_id] = {
                    "success": True,
                    "total_notes": len(notes),
                    "today_notes_count": len(today_notes),
                    "today_notes": today_notes,
                    "last_note": last_note
                }

                logger.info(f"创作者 {creator_id}: 共 {len(notes)} 篇，今天 {len(today_notes)} 篇")
            else:
                results[creator_id] = {
                    "success": False,
                    "error": result.get("error"),
                    "total_notes": 0,
                    "today_notes_count": 0,
                    "today_notes": []
                }
                logger.error(f"创作者 {creator_id} 监控失败: {result.get('error')}")

        return {
            "total_creators": len(creator_ids),
            "monitored_creators": monitored_creators,
            "today_notes_count": total_today_notes,
            "results": results,
            "date": self.today.isoformat()
        }

    async def _filter_today_notes(self, notes: List[Dict]) -> Dict[str, Any]:
        """
        筛选今天发布的笔记

        Args:
            notes: 笔记列表（只有基础信息）

        Returns:
            {
                "today_notes": [...],  # 今天的笔记列表（包含详情）
                "last_note": {...}     # 上一次发布的笔记（如果有）
            }
        """
        today_notes = []
        last_note = None
        all_full_urls = [note.get("full_url") for note in notes if note.get("full_url")]

        if not all_full_urls:
            return {"today_notes": [], "last_note": None}

        batch_size = 2
        checked_count = 0

        # 每次2个2个获取详情，直到发现非今天的笔记
        while checked_count < len(all_full_urls):
            batch_urls = all_full_urls[checked_count:checked_count + batch_size]

            try:
                batch_details = await self.connector_service.get_note_details(
                    urls=batch_urls,
                    platform=PlatformType.XIAOHONGSHU,
                    concurrency=2
                )

                for detail_result in batch_details:
                    if not detail_result.get("success"):
                        checked_count += 1
                        continue

                    detail = detail_result.get("data", {})
                    publish_time = detail.get("time")

                    if not publish_time:
                        checked_count += 1
                        continue

                    publish_date = datetime.fromtimestamp(publish_time / 1000).date()

                    # 合并基础信息和详情
                    full_note = {**notes[checked_count], **detail}
                    logger.info(f"publish_date--->: {publish_date}")

                    # 检查是否在最近7天内发布
                    if publish_date >= self.today - timedelta(days=self.lantcy):
                        today_notes.append(full_note)
                        logger.info(f"发现{self.lantcy}天内新笔记: {detail.get('title')[:30]}")
                    elif last_note is None:
                        # 第一篇超过7天的笔记就是上次发布的
                        last_note = full_note
                        # 找到超过7天的笔记，停止获取
                        return {"today_notes": today_notes, "last_note": last_note}

                    checked_count += 1

            except Exception as e:
                logger.error(f"批量获取详情失败: {e}")
                break

        return {
            "today_notes": today_notes,
            "last_note": last_note
        }

    def format_report(self, monitor_result: Dict[str, Any]) -> str:
        """
        格式化监控报告

        Args:
            monitor_result: monitor_creators 返回的结果

        Returns:
            格式化的报告文本
        """
        lines = [
            "=" * 80,
            f"创作者狙击手监控报告 - {monitor_result.get('date')}",
            "=" * 80,
            f"监控创作者: {monitor_result.get('monitored_creators')}/{monitor_result.get('total_creators')}",
            f"{self.lantcy}日新增笔记: {monitor_result.get('today_notes_count')} 篇",
            "",
        ]

        results = monitor_result.get("results", {})

        for creator_id, result in results.items():
            if not result.get("success"):
                lines.append(f"❌ {creator_id}: 监控失败 - {result.get('error')}")
                continue

            today_count = result.get("today_notes_count", 0)
            total_count = result.get("total_notes", 0)
            last_note = result.get("last_note")
            user = result.get("user")
            user_nickname = user.get("name") if user else ""


            lines.append(f"👤 创作者: {creator_id}")
            lines.append(f"🌾 创作者昵称: {user_nickname}")
            lines.append(f"   总笔记数: {total_count}")

            # 上次发布内容
            if last_note:
                last_time = last_note.get("update_time", "")
                last_title = last_note.get("title", "无标题")
                lines.append(f"   上次发布: {last_time}")
                lines.append(f"     📝 {last_title}")
                lines.append(f"     👍 {last_note.get('liked_count', 0)} | ⭐ {last_note.get('collected_count', 0)} | 💬 {last_note.get('comment_count', 0)}")
                lines.append(f"     🔗 {last_note.get('note_id', '')}")
                last_desc = last_note.get('desc', '')
                if last_desc:
                    lines.append(f"     📖 {last_desc[:100]}...")
            else:
                lines.append(f"   上次发布: 无记录")

            lines.append("-"*80)

            # 新增内容
            if today_count > 0:
                lines.append(f"   ✨ {self.lantcy}日内新增 ({today_count} 篇):")
                lines.append("")

                for note in result.get("today_notes", []):
                    publish_time = note.get("update_time", "")
                    lines.append(f"     📅 发布时间: {publish_time}")
                    lines.append(f"     📝 标题: {note.get('title', '无标题')}")
                    lines.append(f"     👍 点赞: {note.get('liked_count', 0)} | ⭐ 收藏: {note.get('collected_count', 0)} | 💬 评论: {note.get('comment_count', 0)}")
                    lines.append(f"     🔗 笔记ID: {note.get('note_id', '')}")

                    desc = note.get('desc', '')
                    if desc:
                        lines.append(f"     📖 摘要: {desc[:150]}...")

                    images = note.get('images', [])
                    if images:
                        lines.append(f"     🖼️  图片: {len(images)} 张")

                    tags = note.get('tags', [])
                    if tags:
                        lines.append(f"     🏷️  标签: {', '.join(tags[:5])}")

                    lines.append("-"*80)

            else:
                lines.append(f"   ℹ️  {self.lantcy}日内无新内容")
                lines.append("-"*80)

        lines.append("=" * 80)

        return "\n".join(lines)


# ========== 主程序 ==========
async def main():
    """主程序入口"""
    start_time = datetime.now()
    print("=== 创作者狙击手启动 ===", flush=True)
    print(f"⏰ 任务开始时间: {start_time.strftime('%Y-%m-%d %H:%M:%S')}", flush=True)

    async with async_playwright() as p:
        # 初始化狙击手
        sniper = CreatorSniper(source_id="system", playwright=p)

        # 监控的创作者列表（示例）
        creator_ids = [
            "657f31eb000000003d036737", "5c4c5848000000001200de55" # 苹狗大王，奶油mi
        ]

        print(f"监控创作者: {creator_ids}")
        print("-" * 80)

        # 执行监控
        result = await sniper.monitor_creators(creator_ids)

        # 输出报告
        report = sniper.format_report(result)
        print(report, flush=True)

        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()
        print(f"⏰ 任务结束时间: {end_time.strftime('%Y-%m-%d %H:%M:%S')}", flush=True)
        print(f"⏱️  任务耗时: {duration:.2f} 秒", flush=True)


if __name__ == "__main__":
    asyncio.run(main())