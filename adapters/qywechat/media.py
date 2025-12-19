"""企业微信素材管理模块"""
from typing import Optional, Dict, Any
import aiohttp
import aiofiles
import os
from utils.logger import logger
from .token import get_access_token


class QyWechatMediaClient:
    """企业微信素材管理客户端"""
    
    def __init__(self, corpid: str, corpsecret: str):
        """
        初始化素材管理客户端
        
        Args:
            corpid: 企业ID
            corpsecret: 应用的凭证密钥
        """
        self.corpid = corpid
        self.corpsecret = corpsecret
        self.base_url = "https://qyapi.weixin.qq.com/cgi-bin"
    
    async def upload_temp_media(
        self,
        file_path: str,
        media_type: str = "file"
    ) -> Optional[Dict[str, Any]]:
        """
        上传临时素材（获取media_id）
        
        Args:
            file_path: 文件路径
            media_type: 媒体类型（image/voice/video/file）
            
        Returns:
            上传成功返回包含media_id的字典，失败返回None
        """
        url = f"{self.base_url}/media/upload"
        
        try:
            # 检查文件是否存在
            if not os.path.exists(file_path):
                logger.error(f"文件不存在: {file_path}")
                return None
            
            # 获取文件信息
            filename = os.path.basename(file_path)
            file_size = os.path.getsize(file_path)
            
            # 检查文件大小限制
            size_limits = {
                "image": 10 * 1024 * 1024,  # 10MB
                "voice": 2 * 1024 * 1024,   # 2MB
                "video": 10 * 1024 * 1024,  # 10MB
                "file": 20 * 1024 * 1024    # 20MB
            }
            
            if file_size > size_limits.get(media_type, size_limits["file"]):
                logger.error(f"文件大小超出限制: {file_size} bytes")
                return None
            
            # 检查文件最小大小
            if file_size <= 5:
                logger.error(f"文件太小: {file_size} bytes，必须大于5个字节")
                return None
            
            # 根据文件类型确定Content-Type
            ext = os.path.splitext(filename)[1].lower()
            content_type_map = {
                # 图片格式
                '.jpg': 'image/jpeg',
                '.jpeg': 'image/jpeg',
                '.png': 'image/png',
                '.gif': 'image/gif',
                '.bmp': 'image/bmp',
                '.webp': 'image/webp',
                # 语音格式
                '.amr': 'audio/amr',
                '.mp3': 'audio/mp3',
                # 视频格式
                '.mp4': 'video/mp4',
                '.avi': 'video/avi',
                '.mov': 'video/quicktime',
                # 通用文件格式
                '.txt': 'text/plain',
                '.pdf': 'application/pdf',
                '.doc': 'application/msword',
                '.docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
                '.xls': 'application/vnd.ms-excel',
                '.xlsx': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                '.ppt': 'application/vnd.ms-powerpoint',
                '.pptx': 'application/vnd.openxmlformats-officedocument.presentationml.presentation',
                '.zip': 'application/zip',
                '.rar': 'application/x-rar-compressed'
            }
            
            content_type = content_type_map.get(ext, 'application/octet-stream')
            
            # 获取access_token
            access_token = await get_access_token(self.corpid, self.corpsecret)
            url = f"{self.base_url}/media/upload?access_token={access_token}&type={media_type}"
            
            # 使用aiohttp上传文件
            async with aiohttp.ClientSession() as session:
                # 读取文件内容
                async with aiofiles.open(file_path, 'rb') as f:
                    file_data = await f.read()
                
                # 创建multipart/form-data
                data = aiohttp.FormData()
                data.add_field(
                    'media',
                    file_data,
                    filename=filename,
                    content_type=content_type
                )
                
                # 发送请求
                async with session.post(url, data=data) as response:
                    result = await response.json()
                    
                    if result.get("errcode") == 0:
                        media_id = result.get("media_id")
                        created_at = result.get("created_at")
                        logger.info(f"临时素材上传成功: media_id={media_id}, type={result.get('type')}")
                        return {
                            "media_id": media_id,
                            "type": result.get("type"),
                            "created_at": created_at
                        }
                    else:
                        error_msg = result.get("errmsg", "未知错误")
                        error_code = result.get("errcode")
                        logger.error(f"临时素材上传失败: {error_msg} (errcode: {error_code})")
                        return None
                        
        except aiohttp.ClientError as e:
            logger.error(f"上传临时素材请求失败: {e}")
            return None
        except Exception as e:
            logger.error(f"上传临时素材异常: {e}")
            return None
    
    async def upload_image_for_avatar(
        self,
        image_path: str
    ) -> Optional[Dict[str, Any]]:
        """
        上传头像图片
        
        Args:
            image_path: 图片路径
            
        Returns:
            上传结果
        """
        # 头像使用临时素材接口
        return await self.upload_temp_media(image_path, "image")
    
    async def upload_image_for_attachment(
        self,
        image_path: str
    ) -> Optional[str]:
        """
        上传图片作为附件使用
        
        Args:
            image_path: 图片路径
            
        Returns:
            media_id
        """
        result = await self.upload_temp_media(image_path, "image")
        return result["media_id"] if result else None
    
    async def upload_video_for_attachment(
        self,
        video_path: str
    ) -> Optional[str]:
        """
        上传视频作为附件使用
        
        Args:
            video_path: 视频路径
            
        Returns:
            media_id
        """
        # 检查视频格式
        ext = os.path.splitext(video_path)[1].lower()
        if ext not in ['.mp4', '.avi', '.mov']:
            logger.error(f"不支持的视频格式: {ext}")
            return None
        
        result = await self.upload_temp_media(video_path, "video")
        return result["media_id"] if result else None
    
    async def upload_file_for_attachment(
        self,
        file_path: str
    ) -> Optional[str]:
        """
        上传文件作为附件使用
        
        Args:
            file_path: 文件路径
            
        Returns:
            media_id
        """
        result = await self.upload_temp_media(file_path, "file")
        return result["media_id"] if result else None
    
  