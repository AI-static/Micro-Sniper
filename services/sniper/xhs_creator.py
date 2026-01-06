# -*- coding: utf-8 -*-
"""创作者狙击手 - 定时监控多个创作者的新内容

功能：
1. 监控指定创作者列表
2. 获取其笔记列表
3. 检查每篇笔记的发布时间
4. 筛选出近期发布的内容
5. 输出配置时间内新发布笔记详情
"""

import asyncio
from datetime import datetime, timedelta
from typing import List, Dict, Any
from playwright.async_api import async_playwright

from services.sniper.connectors import ConnectorService
from models.connectors import PlatformType
from models.task import Task
from utils.logger import logger


class CreatorSniper:
    """创作者狙击手 - 监控新内容"""

    def __init__(self, source_id: str = "system", source: str = "system", playwright: Any = None, task: Task = None):
        self._playwright = playwright
        self._task = task
        self._source = source
        self._source_id = source_id
        self.today = datetime.now().date()
        self.latency = 10

    async def monitor_creators(
        self,
        creator_ids: List[str]
    ) -> Dict[str, Any]:
        """
        监控多个创作者，找出近期发布的内容

        Args:
            creator_ids: 创作者ID列表

        Returns:
            监控结果报告
        """
        if not self._task:
            raise ValueError("task is required for monitor_creators")

        logger.info(f"开始监控 {len(creator_ids)} 个创作者")

        try:
            # 记录初始参数
            await self._task.log_step(0, "任务初始化",
                              {
                                "purpose": f"监控 {len(creator_ids)} 个创作者的近期内容",
                                "creators_to_monitor": creator_ids,
                                "monitoring_period_days": self.latency
                              },
                              {
                                "task_initialized": f"任务已创建，ID: {self._task.id}",
                                "next_step": "将调用小红书连接器获取每个创作者的笔记列表"
                              })
            self._task.progress = 10
            await self._task.save()

            # 使用 async with ConnectorService
            async with ConnectorService(self._playwright, self._source, self._source_id, self._task) as connector_service:
                # 1. 获取所有创作者的笔记列表
                harvest_results = await connector_service.harvest_user_content(
                    platform=PlatformType.XIAOHONGSHU,
                    creator_ids=creator_ids,
                    limit=None
                )

                # 生成详细的自然语言日志
                log_lines = []
                log_lines.append(f"步骤目标: 获取 {len(creator_ids)} 个创作者在小红书平台发布的笔记列表")
                log_lines.append(f"执行结果: 成功获取 {len(harvest_results)} 个创作者的数据")
                log_lines.append("")

                success_count = 0
                total_notes = 0

                for result in harvest_results:
                    if result.get("success"):
                        data = result.get("data", [])
                        creator_id = result.get("creator_id")
                        # 获取创作者昵称（从第一篇笔记）
                        nickname = creator_id
                        if data and len(data) > 0:
                            nickname = data[0].get("user", {}).get("name", creator_id)

                        success_count += 1
                        total_notes += len(data)

                        log_lines.append(f"✓ 成功 - 创作者: {nickname}")
                        log_lines.append(f"  - 笔记数量: {len(data)} 篇")
                        log_lines.append(f"  - 创作者ID: {creator_id}")

                        # 记录前3篇笔记标题作为示例
                        if data:
                            log_lines.append(f"  - 最新笔记示例:")
                            for i, note in enumerate(data[:3], 1):
                                title = note.get("title", "无标题")
                                likes = note.get("liked_count", "0")
                                log_lines.append(f"    {i}. {title} (👍{likes} 赞)")
                    else:
                        error = result.get("error", "未知错误")
                        creator_id = result.get("creator_id", "未知")
                        log_lines.append(f"✗ 失败 - 创作者ID: {creator_id}")
                        log_lines.append(f"  - 错误原因: {error}")
                    log_lines.append("")

                log_lines.append(f"数据统计: 成功 {success_count}/{len(creator_ids)} 个创作者，共获取 {total_notes} 篇笔记")
                log_lines.append(f"下一步: 将筛选出近{self.latency}天内发布的笔记，并获取详细信息")

                log_text = "\n".join(log_lines)

                await self._task.log_step(1, "获取创作者笔记列表",
                                  {
                                    "action": "harvest_user_content",
                                    "platform": "xiaohongshu",
                                    "creators_count": len(creator_ids)
                                  },
                                  {
                                    "result_summary": log_text,
                                    "status": f"成功获取 {success_count}/{len(creator_ids)} 个创作者数据",
                                    "total_notes_collected": total_notes
                                  })
                self._task.progress = 50
                await self._task.save()

                # 2. 整理结果
                results = {}
                total_today_notes = 0
                monitored_creators = 0

                logger.info(f"[DEBUG] 开始处理 {len(harvest_results)} 个创作者的采集结果")

                for creator_idx, result in enumerate(harvest_results, 1):
                    creator_id = result.get("creator_id")
                    notes = result.get("data", []) if result.get("success") else []

                    logger.info(f"[DEBUG] 处理创作者 {creator_id}: success={result.get('success')}, 笔记数={len(notes)}")

                    if result.get("success"):
                        # 记录开始筛选
                        await self._task.log_step(
                            1 + creator_idx,
                            f"筛选创作者 {creator_id} 的笔记",
                            {
                                "creator_id": creator_id,
                                "total_notes": len(notes),
                                "monitoring_period_days": self.latency
                            },
                            {
                                "status": f"开始筛选 {len(notes)} 篇笔记"
                            }
                        )

                        filter_result = await self._filter_today_notes(notes, connector_service)
                        today_notes = filter_result.get("today_notes", [])
                        last_note = filter_result.get("last_note")
                        pinned_notes = filter_result.get("pinned_notes", [])

                        monitored_creators += 1
                        total_today_notes += len(today_notes)

                        results[creator_id] = {
                            "success": True,
                            "total_notes": len(notes),
                            "today_notes_count": len(today_notes),
                            "today_notes": today_notes,
                            "last_note": last_note,
                            "pinned_notes": pinned_notes
                        }

                        logger.info(f"创作者 {creator_id}: 共 {len(notes)} 篇，近{self.latency}天 {len(today_notes)} 篇")
                        logger.info(f"[DEBUG] 结果字典更新: creator_id={creator_id}, today_notes_count={len(today_notes)}")

                        # 记录筛选完成
                        await self._task.log_step(
                            1 + creator_idx,
                            f"筛选创作者 {creator_id} 的笔记",
                            {
                                "creator_id": creator_id,
                                "total_notes": len(notes)
                            },
                            {
                                "status": f"筛选完成，发现 {len(today_notes)} 篇近期笔记，{len(pinned_notes)} 篇置顶笔记",
                                "today_notes_count": len(today_notes),
                                "pinned_notes_count": len(pinned_notes)
                            }
                        )
                    else:
                        results[creator_id] = {
                            "success": False,
                            "error": result.get("error"),
                            "total_notes": 0,
                            "today_notes_count": 0,
                            "today_notes": []
                        }
                        logger.error(f"创作者 {creator_id} 监控失败: {result.get('error')}")

                logger.info(f"[DEBUG] 所有创作者处理完成: total_today_notes={total_today_notes}, results_keys={list(results.keys())}")

                # AI Native: 生成自然语言报告作为结果
                report = self.format_report({
                    "total_creators": len(creator_ids),
                    "monitored_creators": monitored_creators,
                    "today_notes_count": total_today_notes,
                    "results": results,
                    "date": self.today.isoformat()
                })

                # 简要日志摘要
                await self._task.log_step(3, "生成监控报告",
                                  {
                                    "action": "complete_monitoring_task",
                                    "creators_monitored": monitored_creators,
                                    "new_notes_found": total_today_notes
                                  },
                                  {
                                    "summary": f"监控完成，成功监控 {monitored_creators} 个创作者，发现 {total_today_notes} 篇新笔记"
                                  })

                # 存储 AI 可读的自然语言报告
                await self._task.complete({"report": report})
                return report

        except Exception as e:
            logger.error(f"监控失败: {e}")
            await self._task.fail(str(e), self._task.progress)
            raise

    async def _filter_today_notes(self, notes: List[Dict], connector_service) -> Dict[str, Any]:
        """
        筛选近期发布的笔记

        Args:
            notes: 笔记列表（只有基础信息）
            connector_service: ConnectorService 实例

        Returns:
            {
                "today_notes": [...],  # 近期的笔记列表（包含详情）
                "last_note": {...},    # 上一次发布的笔记（如果有）
                "pinned_notes": [...]   # 所有置顶笔记
            }
        """
        today_notes = []
        last_note = None
        pinned_notes = []

        all_full_urls = [note.get("full_url") for note in notes if note.get("full_url")]

        logger.info(f"[DEBUG] _filter_today_notes 输入: {len(notes)} 篇笔记")
        logger.info(f"[DEBUG] 提取到 {len(all_full_urls)} 个有效URL")
        logger.info(f"[DEBUG] 当前日期: {self.today}, 监控周期: {self.latency}天")
        logger.info(f"[DEBUG] 筛选条件: publish_date >= {self.today - timedelta(days=self.latency)}")

        if not all_full_urls:
            logger.warning("[DEBUG] 没有有效的URL，返回空结果")
            return {"today_notes": [], "last_note": None, "pinned_notes": []}

        batch_size = 3
        should_stop = False

        # 分批获取笔记详情
        for i in range(0, len(all_full_urls), batch_size):
            if should_stop:
                logger.info(f"[DEBUG] 遇到非置顶超期笔记，停止后续批次检查")
                break

            batch_urls = all_full_urls[i:i + batch_size]
            logger.info(f"[DEBUG] 处理批次 {i}-{i + batch_size}, URLs: {batch_urls}")

            try:
                batch_details = await connector_service.get_note_details(
                    urls=batch_urls,
                    platform=PlatformType.XIAOHONGSHU
                )

                logger.info(f"[DEBUG] 批次返回 {len(batch_details)} 个结果")

                for idx, detail_result in enumerate(batch_details):
                    current_note_index = i + idx

                    if not detail_result.get("success"):
                        logger.warning(f"[DEBUG] 索引 {current_note_index}: 获取详情失败 - {detail_result.get('error', '未知错误')}")
                        continue

                    detail = detail_result.get("data", {})
                    publish_time = detail.get("time")

                    if not publish_time:
                        logger.warning(f"[DEBUG] 索引 {current_note_index}: 没有publish_time, detail keys: {list(detail.keys())}")
                        continue

                    publish_date = datetime.fromtimestamp(publish_time / 1000).date()
                    cutoff_date = self.today - timedelta(days=self.latency)

                    # 合并基础信息和详情
                    original_note = notes[current_note_index]
                    full_note = {**original_note, **detail}
                    title = detail.get('title', '无标题')
                    is_pinned = original_note.get('is_pinned', False)

                    # 记录所有置顶笔记
                    if is_pinned:
                        pinned_notes.append(full_note)

                    logger.info(f"[DEBUG] 索引 {current_note_index}: {title}, 发布日期: {publish_date}, 置顶: {is_pinned}, 符合条件: {publish_date >= cutoff_date}")

                    # 检查是否在最近规定天数内发布
                    if publish_date >= cutoff_date:
                        # 近期内的笔记（包括置顶），加入列表
                        today_notes.append(full_note)
                        logger.info(f"[DEBUG] ✅ 发现{self.latency}天内新笔记: {title[:30]} (置顶: {is_pinned}, 当前共{len(today_notes)}篇)")
                    elif not is_pinned:
                        # 非置顶且超出周期的笔记，触发停止
                        last_note = full_note
                        should_stop = True
                        logger.info(f"[DEBUG] 🛑 发现超出周期的非置顶笔记，停止检查: {title[:30]}")
                    elif is_pinned:
                        # 置顶但超出周期，跳过（不触发停止）
                        logger.info(f"[DEBUG] ⏭️  跳过超出周期的置顶笔记: {title[:30]}")

            except Exception as e:
                logger.error(f"批量获取详情失败: {e}")
                import traceback
                traceback.print_exc()
                break

        logger.info(f"[DEBUG] 筛选完成: 共{len(today_notes)}篇符合条件的新笔记, {len(pinned_notes)}篇置顶笔记")
        return {
            "today_notes": today_notes,
            "last_note": last_note,
            "pinned_notes": pinned_notes
        }

    def format_report(self, monitor_result: Dict[str, Any]) -> str:
        """
        格式化监控报告（优化版，包含创作者昵称）

        Args:
            monitor_result: monitor_creators 返回的结果

        Returns:
            格式化的报告文本
        """
        from datetime import datetime

        # Debug logging
        logger.info(f"[DEBUG] format_report 输入参数:")
        logger.info(f"[DEBUG]   - total_creators: {monitor_result.get('total_creators')}")
        logger.info(f"[DEBUG]   - monitored_creators: {monitor_result.get('monitored_creators')}")
        logger.info(f"[DEBUG]   - today_notes_count: {monitor_result.get('today_notes_count')}")
        logger.info(f"[DEBUG]   - results keys: {list(monitor_result.get('results', {}).keys())}")

        results = monitor_result.get("results", {})
        for creator_id, result in results.items():
            logger.info(f"[DEBUG]   - creator {creator_id}: success={result.get('success')}, today_notes_count={result.get('today_notes_count')}, total_notes={result.get('total_notes')}")

        lines = []
        lines.append("=" * 30)
        lines.append(f"📊 创作者监控报告".center(30))
        lines.append(f"生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}".center(30))
        lines.append("=" * 30)
        lines.append(f"📈 监控概览:")
        lines.append(f"   • 监控创作者: {monitor_result.get('monitored_creators')}/{monitor_result.get('total_creators')}")
        lines.append(f"   • 监控周期: 近{self.latency}天")
        lines.append(f"   • 新增笔记: {monitor_result.get('today_notes_count')} 篇")
        lines.append("")
        lines.append("-" * 30)

        results = monitor_result.get("results", {})

        for idx, (creator_id, result) in enumerate(results.items(), 1):
            if not result.get("success"):
                lines.append(f"\n❌ 创作者 #{idx}: {creator_id}")
                lines.append(f"   监控失败: {result.get('error')}")
                lines.append("-" * 30)
                continue

            today_count = result.get("today_notes_count", 0)
            total_count = result.get("total_notes", 0)
            last_note = result.get("last_note")
            
            # 从第一篇笔记中获取创作者信息
            creator_nickname = "未知"
            if result.get("today_notes"):
                creator_nickname = result["today_notes"][0].get("user_nickname", creator_id)
            elif last_note:
                creator_nickname = last_note.get("user_nickname", creator_id)

            lines.append(f"\n👤 创作者 #{idx}: {creator_nickname}")
            lines.append(f"   🆔 ID: {creator_id}")
            lines.append(f"   📚 总笔记数: {total_count} 篇")
            lines.append(f"   ✨ 近{self.latency}日新增: {today_count} 篇")

            # 上次发布内容
            lines.append(f"\n   📅 前{self.latency}发布的最后一篇:")
            if last_note:
                last_note_url = last_note.get("full_url", "")
                last_time = last_note.get("update_time", "未知时间")
                last_title = last_note.get("title", "无标题")
                lines.append(f"      ⏰ 时间: {last_time}")
                lines.append(f"      📝 标题: {last_title}")
                lines.append(f"      💬 互动: 👍{last_note.get('liked_count', 0)} ⭐{last_note.get('collected_count', 0)} 💬{last_note.get('comment_count', 0)}")
                lines.append(f"      🔗 链接: {last_note_url}")

                last_desc = last_note.get('desc', '')
                if last_desc:
                    lines.append(f"      📖 简介: {last_desc[:80]}{'...' if len(last_desc) > 80 else ''}")
            else:
                lines.append(f"      暂无记录")

            lines.append("-" * 30)

            # 新增内容
            if today_count > 0:
                lines.append(f"\n   🎉 近{self.latency}日新增内容 ({today_count} 篇):")
                lines.append("")

                # 按时间倒序排列（最新的在前）
                today_notes_sorted = sorted(
                    result.get("today_notes", []),
                    key=lambda x: x.get("update_time", ""),
                    reverse=True
                )

                for note_idx, note in enumerate(today_notes_sorted, 1):
                    publish_time = note.get("update_time", "")
                    title = note.get("title", "无标题")
                    full_url = note.get("full_url", "")
                    is_pinned = note.get("is_pinned", False)

                    # 如果是置顶笔记，添加标记
                    pinned_mark = " 📌 [置顶]" if is_pinned else ""

                    lines.append(f"      [{note_idx}] 📅 {publish_time}{pinned_mark}")
                    lines.append(f"          📝 {title}")
                    lines.append(f"          🔗 {full_url}")
                    lines.append(f"          💭 👍{note.get('liked_count', 0)} ⭐{note.get('collected_count', 0)} 💬{note.get('comment_count', 0)}")

                    lines.append("")
            else:
                lines.append(f"\n   ℹ️  近{self.latency}日无新内容")
                lines.append("")

            # 置顶笔记
            pinned_notes = result.get("pinned_notes", [])
            if pinned_notes:
                lines.append(f"\n   📌 置顶笔记 ({len(pinned_notes)} 篇):")
                lines.append("")

                for note_idx, note in enumerate(pinned_notes, 1):
                    publish_time = note.get("update_time", "")
                    title = note.get("title", "无标题")
                    full_url = note.get("full_url", "")

                    lines.append(f"      [{note_idx}] 📅 {publish_time}")
                    lines.append(f"          📝 {title}")
                    lines.append(f"          🔗 {full_url}")
                    lines.append(f"          💭 👍{note.get('liked_count', 0)} ⭐{note.get('collected_count', 0)} 💬{note.get('comment_count', 0)}")

                    lines.append("")

            lines.append("-" * 30)

        lines.append("=" * 30)
        lines.append(f"报告结束".center(30))
        lines.append("=" * 30)

        return "\n".join(lines)


# ========== 脚本主程序 ==========
async def main():
    """主程序入口"""
    source = "service"
    source_id = "default"

    from tortoise import Tortoise
    from config.settings import create_db_config

    await Tortoise.init(config=create_db_config())

    start_time = datetime.now()

    print("=== 创作者sniper启动 ===", flush=True)
    print(f"⏰ 任务开始时间: {start_time.strftime('%Y-%m-%d %H:%M:%S')}", flush=True)

    async with async_playwright() as p:
        # 监控的创作者列表（示例）
        creator_ids = [
            "5b7fc43c39b013000158458e" # 苹狗大王，海豹王
        ]

        print(f"监控创作者: {creator_ids}")
        print("-" * 80)

        # 创建任务
        task = await Task.create(
            source=source,
            source_id=source_id,
            task_type="creator_monitor"
        )
        await task.start()

        # 初始化狙击手（传入 task）
        sniper = CreatorSniper(source=source, source_id=source_id, playwright=p, task=task)

        # 执行监控
        report = await sniper.monitor_creators(creator_ids)

        print(report, flush=True)

        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()
        print(f"⏰ 任务结束时间: {end_time.strftime('%Y-%m-%d %H:%M:%S')}", flush=True)
        print(f"⏱️  任务耗时: {duration:.2f} 秒", flush=True)


if __name__ == "__main__":
    asyncio.run(main())