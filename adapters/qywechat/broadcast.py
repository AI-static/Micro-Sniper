"""企业微信企业群发模块"""
from typing import Dict, Any, List, Optional, Union
import aiohttp
from utils.logger import logger
from .token import get_access_token
from config.settings import global_settings


class QyWechatBroadcastClient:
    """企业微信企业群发客户端"""
    
    def __init__(self, corpid: str, corpsecret: str):
        """
        初始化群发客户端
        
        Args:
            corpid: 企业ID
            corpsecret: 应用的凭证密钥
        """
        self.corpid = corpid
        self.corpsecret = corpsecret
        self.base_url = "https://qyapi.weixin.qq.com/cgi-bin"
    
    async def create_single_customer_broadcast(
        self,
        external_user_ids: List[str],
        content: str,
        attachments: Optional[List[Dict[str, Any]]] = None,
        sender: Optional[str] = None,
        allow_select: bool = False,
        tag_filter: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        创建发送给客户的群发任务
        
        Args:
            external_user_ids: 客户的external_userid列表，最多1万个
            content: 消息文本内容，最多4000字节
            attachments: 附件列表，最多9个附件
            sender: 发送消息的成员userid，可选
            allow_select: 是否允许成员重新选择客户
            tag_filter: 标签过滤条件
            
        Returns:
            创建结果，包含失败列表
        """
        return await self._create_broadcast(
            chat_type="single",
            external_userid=external_user_ids,
            text={"content": content},
            attachments=attachments,
            sender=sender,
            allow_select=allow_select,
            tag_filter=tag_filter
        )
    
    async def create_group_broadcast(
        self,
        chat_id_list: List[str],
        content: str,
        sender: str,
        attachments: Optional[List[Dict[str, Any]]] = None,
        allow_select: bool = False,
        tag_filter: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        创建发送给客户群的群发任务
        
        Args:
            chat_id_list: 客户群ID列表，最多2000个
            content: 消息文本内容
            sender: 发送消息的成员userid（必填）
            attachments: 附件列表
            allow_select: 是否允许成员重新选择客户群
            tag_filter: 标签过滤条件
            
        Returns:
            创建结果
        """
        return await self._create_broadcast(
            chat_type="group",
            chat_id_list=chat_id_list,
            text={"content": content},
            attachments=attachments,
            sender=sender,
            allow_select=allow_select,
            tag_filter=tag_filter
        )
    
    async def _create_broadcast(self, **kwargs) -> Dict[str, Any]:
        """
        创建群发任务的通用方法
        
        Returns:
            创建结果
        """
        url = f"{self.base_url}/externalcontact/add_msg_template"
        
        # 构建请求数据
        data = {}
        
        # 必填参数
        if "chat_type" in kwargs:
            data["chat_type"] = kwargs["chat_type"]
        
        # 接收者参数
        if "external_userid" in kwargs:
            data["external_userid"] = kwargs["external_userid"]
        if "chat_id_list" in kwargs:
            data["chat_id_list"] = kwargs["chat_id_list"]
        
        # 可选参数
        if "sender" in kwargs and kwargs["sender"]:
            data["sender"] = kwargs["sender"]
        if "allow_select" in kwargs:
            data["allow_select"] = kwargs["allow_select"]
        
        # 文本内容
        if "text" in kwargs:
            data["text"] = kwargs["text"]
        
        # 附件
        if "attachments" in kwargs and kwargs["attachments"]:
            data["attachments"] = kwargs["attachments"]
        
        # 标签过滤
        if "tag_filter" in kwargs and kwargs["tag_filter"]:
            data["tag_filter"] = kwargs["tag_filter"]
        
        try:
            # 获取access_token
            access_token = await get_access_token(self.corpid, self.corpsecret)
            url = f"{self.base_url}/externalcontact/add_msg_template?access_token={access_token}"
            
            async with aiohttp.ClientSession() as session:
                async with session.post(url, json=data) as response:
                    result = await response.json()
                    
                    if result.get("errcode") == 0:
                        logger.info(f"企业群发任务创建成功")
                        if "fail_list" in result and result["fail_list"]:
                            logger.warning(f"部分客户创建失败: {result['fail_list']}")
                    else:
                        error_msg = result.get("errmsg", "未知错误")
                        error_code = result.get("errcode")
                        logger.error(f"企业群发任务创建失败: {error_msg} (errcode: {error_code})")
                    
                    return result
                    
        except aiohttp.ClientError as e:
            logger.error(f"请求企业微信API失败: {e}")
            return {"errcode": -1, "errmsg": f"网络请求失败: {e}"}
        except Exception as e:
            logger.error(f"创建群发任务异常: {e}")
            return {"errcode": -1, "errmsg": f"创建异常: {e}"}
    
    async def create_text_attachment(self, content: str) -> Dict[str, Any]:
        """创建文本附件（实际上text是直接放在text字段中的）"""
        return {"content": content}
    
    async def create_image_attachment(
        self,
        media_id: Optional[str] = None,
        pic_url: Optional[str] = None,
        image_path: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        创建图片附件
        
        Args:
            media_id: 图片的media_id（已有）
            pic_url: 图片的链接（已有）
            image_path: 本地图片路径（需要上传）
            
        Returns:
            图片附件字典，包含media_id或pic_url
        """
        attachment = {"msgtype": "image", "image": {}}
        
        # 如果提供了本地图片路径，先上传获取pic_url
        if image_path:
            uploaded_url = await self.upload_image(image_path)
            if uploaded_url:
                attachment["image"]["pic_url"] = uploaded_url
                logger.info(f"图片上传成功: {uploaded_url}")
            else:
                # 上传失败，尝试使用其他参数
                logger.error("图片上传失败")
        
        # 使用提供的media_id
        if media_id:
            attachment["image"]["media_id"] = media_id
        
        # 使用提供的pic_url
        if pic_url:
            attachment["image"]["pic_url"] = pic_url
        
        return attachment
    
    async def upload_image(self, image_path: str) -> Optional[str]:
        """
        上传图片到企业微信
        
        Args:
            image_path: 图片文件路径
            
        Returns:
            上传成功返回图片URL，失败返回None
        """
        url = f"{self.base_url}/media/uploadimg"
        
        try:
            # 获取access_token
            access_token = await get_access_token(self.corpid, self.corpsecret)
            url = f"{self.base_url}/media/uploadimg?access_token={access_token}"
            
            # 读取图片文件
            import aiofiles
            import os
            
            if not os.path.exists(image_path):
                logger.error(f"图片文件不存在: {image_path}")
                return None
            
            # 获取文件名和扩展名
            filename = os.path.basename(image_path)
            
            # 根据文件扩展名确定Content-Type
            ext = os.path.splitext(filename)[1].lower()
            content_type_map = {
                '.jpg': 'image/jpeg',
                '.jpeg': 'image/jpeg',
                '.png': 'image/png',
                '.gif': 'image/gif',
                '.bmp': 'image/bmp',
                '.webp': 'image/webp'
            }
            content_type = content_type_map.get(ext, 'application/octet-stream')
            
            # 使用aiohttp上传文件
            async with aiohttp.ClientSession() as session:
                # 先读取文件内容
                async with aiofiles.open(image_path, 'rb') as f:
                    image_data = await f.read()
                
                # 创建multipart/form-data
                data = aiohttp.FormData()
                data.add_field(
                    'media',
                    image_data,
                    filename=filename,
                    content_type=content_type
                )
                
                # 发送请求
                async with session.post(url, data=data) as response:
                    result = await response.json()
                    
                    if result.get("errcode") == 0:
                        pic_url = result.get("url")
                        logger.info(f"图片上传成功: {pic_url}")
                        return pic_url
                    else:
                        error_msg = result.get("errmsg", "未知错误")
                        logger.error(f"图片上传失败: {error_msg} (errcode: {result.get('errcode')})")
                        return None
                        
        except aiohttp.ClientError as e:
            logger.error(f"上传图片请求失败: {e}")
            return None
        except Exception as e:
            logger.error(f"上传图片异常: {e}")
            return None
    
    async def create_link_attachment(
        self,
        title: str,
        url: str,
        picurl: Optional[str] = None,
        desc: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        创建图文链接附件
        
        Args:
            title: 标题，最长128字节
            url: 链接，最长2048字节
            picurl: 封面图片链接，最长2048字节
            desc: 描述，最多512字节
            
        Returns:
            链接附件字典
        """
        attachment = {
            "msgtype": "link",
            "link": {
                "title": title,
                "url": url
            }
        }
        
        if picurl:
            attachment["link"]["picurl"] = picurl
        if desc:
            attachment["link"]["desc"] = desc
            
        return attachment
    
    async def create_miniprogram_attachment(
        self,
        title: str,
        appid: str,
        page: str,
        pic_media_id: str
    ) -> Dict[str, Any]:
        """
        创建小程序附件
        
        Args:
            title: 标题，最多64字节
            appid: 小程序appid
            page: 小程序页面路径
            pic_media_id: 小程序封面图的media_id
            
        Returns:
            小程序附件字典
        """
        return {
            "msgtype": "miniprogram",
            "miniprogram": {
                "title": title,
                "appid": appid,
                "page": page,
                "pic_media_id": pic_media_id
            }
        }
    
    async def create_video_attachment(self, media_id: str) -> Dict[str, Any]:
        """
        创建视频附件
        
        Args:
            media_id: 视频的media_id
            
        Returns:
            视频附件字典
        """
        return {
            "msgtype": "video",
            "video": {
                "media_id": media_id
            }
        }
    
    async def create_file_attachment(self, media_id: str) -> Dict[str, Any]:
        """
        创建文件附件
        
        Args:
            media_id: 文件的media_id
            
        Returns:
            文件附件字典
        """
        return {
            "msgtype": "file",
            "file": {
                "media_id": media_id
            }
        }
    
    async def send_promotion_broadcast(
        self,
        external_userids: List[str],
        product_name: str,
        product_url: str,
        product_desc: str,
        product_image: Optional[str] = None,
        discount: Optional[str] = None,
        sender: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        发送产品推广群发（快捷方法）
        
        Args:
            external_userids: 客户列表
            product_name: 产品名称
            product_url: 产品链接
            product_desc: 产品描述
            product_image: 产品图片链接
            discount: 优惠信息
            sender: 发送者
            
        Returns:
            发送结果
        """
        content = f"""
🎉 好消息推荐

产品：{product_name}
{product_desc}
        """.strip()
        
        if discount:
            content += f"\n\n💰 限时优惠：{discount}"
        
        attachments = [
            await self.create_link_attachment(
                title=product_name,
                url=product_url,
                desc=product_desc[:100] + "..." if len(product_desc) > 100 else product_desc,
                picurl=product_image
            )
        ]
        
        return await self.create_single_customer_broadcast(
            external_userids=external_userids,
            content=content,
            attachments=attachments,
            sender=sender
        )
    
    async def send_activity_broadcast(
        self,
        chat_id_list: List[str],
        sender: str,
        activity_title: str,
        activity_desc: str,
        activity_time: str,
        activity_url: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        发送活动通知群发（快捷方法）
        
        Args:
            chat_id_list: 客户群列表
            sender: 发送者
            activity_title: 活动标题
            activity_desc: 活动描述
            activity_time: 活动时间
            activity_url: 活动链接
            
        Returns:
            发送结果
        """
        content = f"""
📢 活动通知

活动主题：{activity_title}

活动详情：
{activity_desc}

活动时间：{activity_time}
        """.strip()
        
        if activity_url:
            content += f"\n\n👉 了解更多：{activity_url}"
        
        return await self.create_group_broadcast(
            chat_id_list=chat_id_list,
            sender=sender,
            content=content
        )
    
    async def get_broadcast_result(self, msgid: str) -> Dict[str, Any]:
        """
        获取群发发送结果
        
        Args:
            msgid: 群发消息的ID
            
        Returns:
            群发结果详情
        """
        url = f"{self.base_url}/externalcontact/get_groupmsg_result"
        
        data = {"msgid": msgid}
        
        try:
            access_token = await get_access_token(self.corpid, self.corpsecret)
            url = f"{self.base_url}/externalcontact/get_groupmsg_result?access_token={access_token}"
            
            async with aiohttp.ClientSession() as session:
                async with session.post(url, json=data) as response:
                    result = await response.json()
                    
                    if result.get("errcode") == 0:
                        logger.info(f"获取群发结果成功")
                    else:
                        error_msg = result.get("errmsg", "未知错误")
                        logger.error(f"获取群发结果失败: {error_msg}")
                    
                    return result
                    
        except Exception as e:
            logger.error(f"获取群发结果异常: {e}")
            return {"errcode": -1, "errmsg": f"获取异常: {e}"}

qy_wechat_broadcast_client = QyWechatBroadcastClient(global_settings.im.wechat_corpid,
                                                     global_settings.im.wechat_secret)