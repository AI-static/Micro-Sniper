# -*- coding: utf-8 -*-
"""任务模型 - AI Native 设计，记录任务执行过程和结果"""

from enum import Enum
from tortoise.models import Model
from tortoise.fields import (
    CharField, IntField, BooleanField, DatetimeField, 
    TextField, UUIDField, JSONField
)
import uuid
from datetime import datetime


class TaskStatus(str, Enum):
    """任务状态枚举"""
    PENDING = "pending"
    RUNNING = "running"
    WAITING_LOGIN = "waiting_login"  # 等待用户登录平台
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class Task(Model):
    """
    任务模型 - AI Native 设计
    
    设计理念：
    1. 记录任务执行过程中的每一步上下文
    2. Agent 可以查看上下文，决定下一步操作
    3. Service 负责实际执行，Task 负责记录
    4. 结果存储为自然语言文本，AI 可直接阅读
    """

    # 基础信息
    id = UUIDField(pk=True, default=uuid.uuid4, description="任务唯一标识")
    source = CharField(50, description="请求来源：system, api, user等")
    source_id = CharField(100, description="请求来源ID：用户ID、服务名等")
    task_type = CharField(50, description="任务类型：trend_analysis, creator_monitor等")

    # 状态管理
    status = CharField(20, default=TaskStatus.PENDING.value, description="任务状态")
    progress = IntField(default=0, description="任务进度 0-100")
    
    # 结果和错误（AI Native：存储自然语言文本）
    result = JSONField(null=True, description="任务最终结果（AI可读的自然语言格式）")
    error = TextField(null=True, description="错误信息（自然语言描述）")

    # 执行日志 - 记录每一步的输入输出（本身就是上下文）
    logs = JSONField(default=lambda : [], description="执行日志，记录每一步的详细信息")

    # 时间戳
    created_at = DatetimeField(auto_now_add=True, description="创建时间")
    started_at = DatetimeField(null=True, description="开始时间")
    completed_at = DatetimeField(null=True, description="完成时间")

    class Meta:
        table = "tasks"
        indexes = [
            ("source_id", "status"),
            ("task_type", "status"),
            ("created_at",),
        ]

    # ===== 任务状态管理方法 =====

    async def start(self):
        """开始执行任务"""
        self.status = TaskStatus.RUNNING
        self.started_at = datetime.now()
        await self.save()

    async def waiting_login(self, login_info: dict = None):
        """标记任务等待登录"""
        self.status = TaskStatus.WAITING_LOGIN
        if login_info:
            self.result = {"login_required": True, **login_info}
        await self.save()

    async def complete(self, result_data: dict = None):
        """完成任务"""
        self.status = TaskStatus.COMPLETED
        self.completed_at = datetime.now()
        self.progress = 100
        if result_data:
            self.result = result_data
        await self.save()

    async def fail(self, error_msg: str, current_progress: int = None):
        """标记任务失败"""
        self.status = TaskStatus.FAILED
        self.completed_at = datetime.now()
        self.error = error_msg
        if current_progress is not None:
            self.progress = current_progress
        await self.save()

    async def cancel(self):
        """取消任务"""
        self.status = TaskStatus.CANCELLED
        self.completed_at = datetime.now()
        await self.save()

    # ===== 日志管理方法 =====

    async def log_step(self, step: int, name: str, input_data: dict, output_data: dict, status: str = "completed"):
        """
        记录一步执行

        Args:
            step: 步骤编号
            name: 步骤名称
            input_data: 输入数据
            output_data: 输出数据
            status: 步骤状态
        """
        log_entry = {
            "step": step,
            "name": name,
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "input": input_data,
            "output": output_data,
            "status": status
        }
        self.logs.append(log_entry)
        await self.save()

    # ===== AI 可读格式转换 =====

    def to_agent_readable(self) -> dict:
        """
        转换为 Agent 可读的格式 - AI Native 核心方法
        
        Returns:
            包含任务完整信息的字典，适合 LLM 理解
        """
        # 构建自然语言摘要
        summary_parts = []
        summary_parts.append(f"任务类型: {self.task_type}")
        summary_parts.append(f"当前状态: {self.status}")
        summary_parts.append(f"执行进度: {self.progress}%")
        
        if self.error:
            summary_parts.append(f"错误信息: {self.error}")
        
        # 构建日志摘要
        if self.logs:
            log_summary = f"已执行 {len(self.logs)} 个步骤："
            for log in self.logs:
                log_summary += f"\n  - 步骤{log['step']}: {log['name']} ({log['status']})"
            summary_parts.append(log_summary)
        
        # 构建结果摘要
        if self.result:
            if isinstance(self.result, dict):
                if 'analysis' in self.result:
                    summary_parts.append(f"分析结果: {self.result['analysis'][:100]}...")
                elif 'report' in self.result:
                    summary_parts.append(f"报告: {self.result['report'][:100]}...")
                else:
                    summary_parts.append(f"结果: {str(self.result)[:100]}...")
        
        return {
            "task_id": str(self.id),
            "task_type": self.task_type,
            "status": self.status,
            "progress": self.progress,
            "summary": "\n".join(summary_parts),
            "logs": self.logs,
            "result": self.result,
            "error": self.error,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "next_step_hint": self._get_next_step_hint()
        }

    def _get_next_step_hint(self) -> str:
        """生成下一步操作提示（自然语言）"""
        if self.status == TaskStatus.PENDING:
            return "任务等待开始，请检查前置条件"
        elif self.status == TaskStatus.RUNNING:
            completed_steps = len([l for l in self.logs if l.get('status') == 'completed'])
            return f"任务执行中，已完成 {completed_steps} 个步骤，当前进度 {self.progress}%"
        elif self.status == TaskStatus.WAITING_LOGIN:
            return "任务等待登录，请在平台完成登录后继续"
        elif self.status == TaskStatus.COMPLETED:
            return "任务已完成，可查看执行结果和报告"
        elif self.status == TaskStatus.FAILED:
            return f"任务失败: {self.error or '未知错误'}，请查看日志了解详情"
        elif self.status == TaskStatus.CANCELLED:
            return "任务已被取消"
        return "未知状态"

    def get_result_text(self) -> str:
        """
        获取结果的纯文本格式 - AI Native
        
        Returns:
            适合 AI 阅读的纯文本结果
        """
        if not self.result:
            return "暂无结果"
        
        if isinstance(self.result, dict):
            # 提取分析或报告
            if 'analysis' in self.result:
                return self.result['analysis']
            elif 'report' in self.result:
                return self.result['report']
            else:
                # 转换为自然语言描述
                lines = []
                for key, value in self.result.items():
                    lines.append(f"{key}: {value}")
                return "\n".join(lines)
        
        return str(self.result)

    def get_logs_summary(self) -> str:
        """
        获取日志摘要 - AI Native
        
        Returns:
            适合 AI 阅读的日志摘要
        """
        if not self.logs:
            return "暂无执行日志"
        
        lines = [f"任务执行日志（共 {len(self.logs)} 步）:"]
        
        for log in self.logs:
            status_icon = "✓" if log.get('status') == 'completed' else "✗"
            lines.append(f"\n{status_icon} 步骤 {log['step']}: {log['name']}")
            lines.append(f"  时间: {log['timestamp']}")
            
            if log.get('input'):
                lines.append(f"  输入: {self._format_dict(log['input'])}")
            if log.get('output'):
                lines.append(f"  输出: {self._format_dict(log['output'])}")
        
        return "\n".join(lines)

    def _format_dict(self, data: dict, max_len: int = 100) -> str:
        """格式化字典为简短的字符串"""
        if not data:
            return ""
        
        items = []
        for key, value in list(data.items())[:3]:  # 只取前3个
            value_str = str(value)
            if len(value_str) > max_len:
                value_str = value_str[:max_len] + "..."
            items.append(f"{key}={value_str}")
        
        return ", ".join(items)