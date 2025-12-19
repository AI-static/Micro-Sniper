"""企业微信消息发送模块"""
from typing import Dict, Any, List, Optional, Union
import aiohttp
import json
from utils.logger import logger
from .token import get_access_token
from config.settings import global_settings


class QyWechatMessageClient:
    """企业微信消息客户端"""
    
    def __init__(self, corpid: str, corpsecret: str, agent_id: int):
        """
        初始化消息客户端
        
        Args:
            corpid: 企业ID
            corpsecret: 应用的凭证密钥
            agent_id: 应用ID
        """
        self.corpid = corpid
        self.corpsecret = corpsecret
        self.agent_id = agent_id
        self.base_url = "https://qyapi.weixin.qq.com/cgi-bin"
    
    async def send_text(
        self,
        touser: Optional[str] = None,
        toparty: Optional[str] = None,
        totag: Optional[str] = None,
        content: str = "",
        safe: int = 0
    ) -> Dict[str, Any]:
        """
        发送文本消息
        
        Args:
            touser: 指定接收消息的成员，@all表示全部（多个用|分隔）
            toparty: 指定接收消息的部门（多个用|分隔）
            totag: 指定接收消息的标签（多个用|分隔）
            content: 消息内容
            safe: 表示是否是保密消息，0表示可对外分享，1表示不能分享且内容显示水印
            
        Returns:
            发送结果
        """
        data = {
            "touser": touser or "",
            "toparty": toparty or "",
            "totag": totag or "",
            "msgtype": "text",
            "agentid": self.agent_id,
            "text": {
                "content": content
            },
            "safe": safe
        }
        
        # 移除空的接收者
        if not data["touser"]:
            del data["touser"]
        if not data["toparty"]:
            del data["toparty"]
        if not data["totag"]:
            del data["totag"]
        
        return await self._send_message(data)
    
    async def send_markdown(
        self,
        touser: Optional[str] = None,
        toparty: Optional[str] = None,
        totag: Optional[str] = None,
        content: str = ""
    ) -> Dict[str, Any]:
        """
        发送markdown消息
        
        Args:
            touser: 指定接收消息的成员
            toparty: 指定接收消息的部门
            totag: 指定接收消息的标签
            content: markdown内容，支持html标签
            
        Returns:
            发送结果
        """
        data = {
            "touser": touser or "",
            "toparty": toparty or "",
            "totag": totag or "",
            "msgtype": "markdown",
            "agentid": self.agent_id,
            "markdown": {
                "content": content
            }
        }
        
        # 移除空的接收者
        if not data["touser"]:
            del data["touser"]
        if not data["toparty"]:
            del data["toparty"]
        if not data["totag"]:
            del data["totag"]
        
        return await self._send_message(data)
    
    async def send_news(
        self,
        touser: Optional[str] = None,
        toparty: Optional[str] = None,
        totag: Optional[str] = None,
        articles: List[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        发送图文消息
        
        Args:
            touser: 指定接收消息的成员
            toparty: 指定接收消息的部门
            totag: 指定接收消息的标签
            articles: 图文消息列表，每个article包含:
                - title: 标题
                - description: 描述
                - url: 点击后跳转的链接
                - picurl: 图片链接
                
        Returns:
            发送结果
        """
        data = {
            "touser": touser or "",
            "toparty": toparty or "",
            "totag": totag or "",
            "msgtype": "news",
            "agentid": self.agent_id,
            "news": {
                "articles": articles or []
            }
        }
        
        # 移除空的接收者
        if not data["touser"]:
            del data["touser"]
        if not data["toparty"]:
            del data["toparty"]
        if not data["totag"]:
            del data["totag"]
        
        return await self._send_message(data)
    
    async def send_template_card(
        self,
        touser: Optional[str] = None,
        toparty: Optional[str] = None,
        totag: Optional[str] = None,
        title: str = "",
        description: str = "",
        url: str = "",
        btn_list: List[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        发送模板卡片消息
        
        Args:
            touser: 指定接收消息的成员
            toparty: 指定接收消息的部门
            totag: 指定接收消息的标签
            title: 标题
            description: 描述
            url: 点击跳转的链接
            btn_list: 按钮列表，每个btn包含:
                - type: 按钮类型（1：跳转url，2：打开小程序）
                - text: 按钮文字
                - url: 按钮链接（type=1时）
                - appid: 小程序appid（type=2时）
                - pagepath: 小程序页面路径（type=2时）
                
        Returns:
            发送结果
        """
        card_data = {
            "title": title,
            "description": description,
            "url": url
        }
        
        if btn_list:
            card_data["btn"] = btn_list
        
        data = {
            "touser": touser or "",
            "toparty": toparty or "",
            "totag": totag or "",
            "msgtype": "template_card",
            "agentid": self.agent_id,
            "template_card": card_data
        }
        
        # 移除空的接收者
        if not data["touser"]:
            del data["touser"]
        if not data["toparty"]:
            del data["toparty"]
        if not data["totag"]:
            del data["totag"]
        
        return await self._send_message(data)
    
    async def _send_message(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        发送消息的通用方法
        
        Args:
            data: 请求数据
            
        Returns:
            发送结果
        """
        try:
            # 获取access_token
            access_token = await get_access_token(self.corpid, self.corpsecret)
            url = f"{self.base_url}/message/send?access_token={access_token}"
            
            async with aiohttp.ClientSession() as session:
                async with session.post(url, json=data) as response:
                    result = await response.json()
                    
                    if result.get("errcode") == 0:
                        logger.info(f"企业微信消息发送成功: {result.get('errmsg')}")
                    else:
                        error_msg = result.get("errmsg", "未知错误")
                        error_code = result.get("errcode")
                        logger.error(f"企业微信消息发送失败: {error_msg} (errcode: {error_code})")
                    
                    return result
                    
        except aiohttp.ClientError as e:
            logger.error(f"请求企业微信API失败: {e}")
            return {"errcode": -1, "errmsg": f"网络请求失败: {e}"}
        except Exception as e:
            logger.error(f"发送消息异常: {e}")
            return {"errcode": -1, "errmsg": f"发送异常: {e}"}
    
    async def send_alert(
        self,
        message: str,
        title: str = "监控报警",
        touser: Optional[str] = None,
        level: str = "warning"
    ) -> Dict[str, Any]:
        """
        发送报警消息（快捷方法）
        
        Args:
            message: 报警消息内容
            title: 报警标题
            touser: 接收人
            level: 报警级别（info/warning/error）
            
        Returns:
            发送结果
        """
        # 根据级别设置emoji
        level_emoji = {
            "info": "ℹ️",
            "warning": "⚠️",
            "error": "❌"
        }
        
        emoji = level_emoji.get(level, "⚠️")
        
        # 使用markdown格式发送
        markdown_content = f"""
## {emoji} {title}

{message}

---
*来自 Micro-Sniper 监控系统*
        """.strip()
        
        return await self.send_markdown(
            touser=touser,
            content=markdown_content
        )
    
    async def send_monitor_alert(
        self,
        alert_type: str,
        data: Dict[str, Any],
        touser: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        发送监控报警（专用方法）
        
        Args:
            alert_type: 报警类型（viral/price/gig）
            data: 报警数据
            touser: 接收人
            
        Returns:
            发送结果
        """
        if alert_type == "viral":
            # 爆款内容报警
            title = "🔥 爆款内容报警"
            content = f"""
**平台**: {data.get('platform', '未知')}

**标题**: {data.get('title', '无标题')}

**数据**:
- 点赞: {data.get('likes', 0):,}
- 浏览: {data.get('views', 0):,}
- 链接: [查看原文]({data.get('url', '')})

**检测时间**: {data.get('timestamp', '')}
            """
            
        elif alert_type == "price":
            # 价格变动报警
            title = "💰 价格变动报警"
            content = f"""
**商品**: {data.get('name', '未知商品')}

**价格变动**:
- 原价: ¥{data.get('old_price', 0)}
- 现价: ¥{data.get('new_price', 0)}
- 降幅: {data.get('discount', 0):.1f}%

**链接**: [查看商品]({data.get('url', '')})

**检测时间**: {data.get('timestamp', '')}
            """
            
        elif alert_type == "gig":
            # 外包订单报警
            title = "💼 优质订单提醒"
            content = f"""
**订单标题**: {data.get('title', '无标题')}

**订单信息**:
- 预算: ${data.get('budget', 0):,}
- 平台: {data.get('platform', '未知')}
- 发布时间: {data.get('posted_time', '')}

**描述**: {data.get('description', '')[:200]}...

**链接**: [查看订单]({data.get('url', '')})

**检测时间**: {data.get('timestamp', '')}
            """
            
        else:
            title = "📢 监控通知"
            content = json.dumps(data, ensure_ascii=False, indent=2)
        
        return await self.send_markdown(
            touser=touser,
            content=f"## {title}\n\n{content}"
        )

qy_wechat_message_client = QyWechatMessageClient(global_settings.im.wechat_corpid,
                                          global_settings.im.wechat_secret,
                                          global_settings.im.wechat_agent_id)