"""监控服务 - 基于source_id的监控任务调度"""
import asyncio
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
from utils.logger import logger
from services.config_service import ConfigService
from services.connectors.connector_service import ConnectorService
from models.config import MonitorConfig
from models.connectors import PlatformType
import aiohttp
import json


class MonitorService:
    """监控服务 - 管理所有监控任务"""
    
    def __init__(self):
        """初始化监控服务"""
        self.config_service = ConfigService()
        self.connector_service = ConnectorService()
        self.running_tasks: Dict[str, asyncio.Task] = {}
        self.is_running = False
        
    async def start(self):
        """启动监控服务"""
        if self.is_running:
            logger.warning("监控服务已在运行")
            return
            
        self.is_running = True
        logger.info("监控服务启动")
        
        # 加载所有活跃的监控配置
        await self._load_and_schedule_monitors()
        
    async def stop(self):
        """停止监控服务"""
        self.is_running = False
        
        # 取消所有运行中的任务
        for task_id, task in self.running_tasks.items():
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
                
        self.running_tasks.clear()
        logger.info("监控服务停止")
        
    async def _load_and_schedule_monitors(self):
        """加载并调度所有监控任务"""
        configs = await self.config_service.get_active_configs_for_monitor()
        
        for config in configs:
            task_id = f"{config.source_id}_{config.id}"
            if task_id not in self.running_tasks:
                task = asyncio.create_task(
                    self._monitor_loop(config)
                )
                self.running_tasks[task_id] = task
                logger.info(f"启动监控任务: {task_id}")
    
    async def _monitor_loop(self, config: MonitorConfig):
        """监控循环"""
        logger.info(f"开始监控: {config.name} (source_id: {config.source_id})")
        
        while self.is_running and config.is_active:
            try:
                # 获取用户会话（如果有）
                session = await self.config_service.get_session(
                    source_id=config.source_id,
                    platform=config.platform
                )
                
                # 执行监控
                triggered = await self._execute_monitor(
                    config=config,
                    context_id=session.context_id if session else None
                )
                
                # 更新统计
                await config.update_stats(triggered=triggered)
                
                # 等待下次检查
                await asyncio.sleep(config.check_interval)
                
            except asyncio.CancelledError:
                logger.info(f"监控任务被取消: {config.name}")
                break
            except Exception as e:
                logger.error(f"监控任务异常: {config.name}, error: {e}")
                await asyncio.sleep(min(60, config.check_interval))  # 出错时最多等待1分钟
    
    async def _execute_monitor(
        self,
        config: MonitorConfig,
        context_id: Optional[str] = None
    ) -> bool:
        """执行单次监控检查"""
        triggered = False
        platform = PlatformType(config.platform)
        connector = self.connector_service._get_connector(platform)
        
        # 监控不同的目标
        targets = config.targets
        
        # 监控用户
        if "users" in targets:
            for user_id in targets["users"]:
                try:
                    # 获取用户最新内容
                    result = await connector.get_user_latest_posts(
                        user_id=user_id,
                        context_id=context_id,
                        limit=1
                    )
                    
                    if result and result.get("posts"):
                        latest_post = result["posts"][0]
                        
                        # 检查触发条件
                        if await self._check_triggers(
                            config.triggers,
                            latest_post
                        ):
                            triggered = True
                            await self._send_alert(
                                config=config,
                                trigger_data=latest_post,
                                trigger_type="user_post",
                                target_id=user_id
                            )
                            
                except Exception as e:
                    logger.error(f"监控用户 {user_id} 失败: {e}")
        
        # 监控URL
        if "urls" in targets:
            for url in targets["urls"]:
                try:
                    # 提取URL内容
                    async for result in self.connector_service.extract_summary_stream(
                        urls=[url],
                        platform=platform,
                        context_id=context_id,
                        concurrency=1
                    ):
                        if result.get("success") and result.get("data"):
                            # 检查价格变动等触发条件
                            if await self._check_triggers(
                                config.triggers,
                                result["data"],
                                check_type="url"
                            ):
                                triggered = True
                                await self._send_alert(
                                    config=config,
                                    trigger_data=result["data"],
                                    trigger_type="url_change",
                                    target_id=url
                                )
                                
                except Exception as e:
                    logger.error(f"监控URL {url} 失败: {e}")
        
        # 监控关键词
        if "keywords" in targets:
            for keyword in targets["keywords"]:
                try:
                    # 搜索关键词
                    results = await connector.search_content(
                        keyword=keyword,
                        context_id=context_id,
                        limit=10
                    )
                    
                    if results and results.get("items"):
                        # 检查新内容
                        for item in results["items"]:
                            if await self._check_triggers(
                                config.triggers,
                                item,
                                check_type="keyword"
                            ):
                                triggered = True
                                await self._send_alert(
                                    config=config,
                                    trigger_data=item,
                                    trigger_type="keyword_match",
                                    target_id=keyword
                                )
                                
                except Exception as e:
                    logger.error(f"监控关键词 {keyword} 失败: {e}")
        
        return triggered
    
    async def _check_triggers(
        self,
        triggers: List[Dict[str, Any]],
        data: Dict[str, Any],
        check_type: str = "default"
    ) -> bool:
        """检查触发条件"""
        for trigger in triggers:
            trigger_type = trigger.get("type")
            
            if trigger_type == "like_threshold":
                # 点赞数阈值触发
                likes = data.get("likes", 0)
                threshold = trigger.get("value", 1000)
                time_window = trigger.get("time_window", 3600)
                
                # 检查时间窗口内的点赞数
                if likes >= threshold:
                    # TODO: 需要计算时间窗口内的增长率
                    return True
            
            elif trigger_type == "price_change":
                # 价格变动触发
                if check_type == "url":
                    old_price = data.get("old_price", 0)
                    new_price = data.get("price", 0)
                    drop_threshold = trigger.get("drop_threshold", 0.1)
                    
                    if old_price > 0 and (old_price - new_price) / old_price >= drop_threshold:
                        return True
            
            elif trigger_type == "new_post":
                # 新发布触发
                publish_time = data.get("publish_time")
                if publish_time:
                    # 检查是否是最近发布的内容
                    post_time = datetime.fromisoformat(publish_time) if isinstance(publish_time, str) else publish_time
                    if datetime.now() - post_time < timedelta(minutes=5):
                        return True
        
        return False
    
    async def _send_alert(
        self,
        config: MonitorConfig,
        trigger_data: Dict[str, Any],
        trigger_type: str,
        target_id: str
    ):
        """发送报警通知"""
        try:
            # 构建报警消息
            alert_message = {
                "source_id": config.source_id,
                "config_name": config.name,
                "platform": config.platform,
                "trigger_type": trigger_type,
                "target_id": target_id,
                "data": trigger_data,
                "timestamp": datetime.now().isoformat()
            }
            
            # 发送到webhook
            if config.webhook_url:
                async with aiohttp.ClientSession() as session:
                    async with session.post(
                        config.webhook_url,
                        json=alert_message,
                        timeout=10
                    ) as response:
                        if response.status == 200:
                            logger.info(f"报警发送成功: {config.name}")
                        else:
                            logger.error(f"报警发送失败: {config.name}, status: {response.status}")
            
            # TODO: 支持其他通知方式（邮件、微信、钉钉等）
            
        except Exception as e:
            logger.error(f"发送报警失败: {e}")
    
    async def add_monitor(self, source_id: str, config_id: str):
        """添加新的监控任务"""
        config = await self.config_service.get_monitor_config(config_id, source_id)
        if not config:
            logger.error(f"监控配置不存在: {config_id}")
            return
        
        task_id = f"{source_id}_{config_id}"
        if task_id in self.running_tasks:
            logger.warning(f"监控任务已存在: {task_id}")
            return
        
        # 创建并启动任务
        task = asyncio.create_task(self._monitor_loop(config))
        self.running_tasks[task_id] = task
        logger.info(f"添加监控任务: {task_id}")
    
    async def remove_monitor(self, source_id: str, config_id: str):
        """移除监控任务"""
        task_id = f"{source_id}_{config_id}"
        if task_id in self.running_tasks:
            task = self.running_tasks[task_id]
            task.cancel()
            del self.running_tasks[task_id]
            logger.info(f"移除监控任务: {task_id}")
    
    async def reload_monitor(self, source_id: str, config_id: str):
        """重新加载监控任务"""
        await self.remove_monitor(source_id, config_id)
        await self.add_monitor(source_id, config_id)


# 全局监控服务实例
monitor_service = MonitorService()