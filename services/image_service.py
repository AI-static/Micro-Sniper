"""图片生成服务"""
from typing import List, Dict, Any
from adapters.ezlink.image import ImageAdapter
from utils.logger import logger
from utils.exceptions import BusinessException
from api.schema.response import ErrorCode
from config.settings import settings
import base64
import os
from datetime import datetime
import hashlib


class ImageService:
    """图片生成业务服务"""
    
    def __init__(self):
        self.ezlink = ImageAdapter()
        # 图片存储目录
        self.image_dir = settings.image_dir
        # 图片URL路径（固定路径）
        self.image_url_path = "/images"
    
    async def create_image(self, prompt: str, model: str = "gemini-2.5-flash-image-preview", 
                          n: int = 1, size: str = "1024x1024") -> Dict[str, Any]:
        """
        创建图片
        :param prompt: 图片描述
        :param model: 模型名称
        :param n: 生成图片数量
        :param size: 图片尺寸
        :return: 包含图片链接和使用情况的结果
        """
        logger.info(f"开始创建图片: {prompt[:100]}")
        
        # 调用Ezlink API
        result = await self.ezlink.generate_image(prompt, model, n, size)
        
        if not result:
            raise BusinessException("Ezlink API 返回空结果", ErrorCode.IMAGE_GENERATE_FAILED)
        
        # 保存图片并生成URL
        images = await self._save_images_with_urls(result)
        
        # 构造返回结果
        response = {
            "success": True,
            "created": result.get("created"),
            "images": images,
            "usage": result.get("usage", {}),
            "prompt": prompt,
            "model": model,
            "size": size
        }
        
        logger.info(f"图片生成成功，数量: {len(images)}")
        return response
    
    async def edit_image(self, prompt: str, files,
                        model: str = "gemini-2.5-flash-image-preview", 
                        n: int = 1) -> Dict[str, Any]:
        """
        编辑图片
        :param prompt: 编辑描述
        :param files: 图片文件（可能是单个文件或文件列表）
        :param model: 模型名称
        :param n: 生成图片数量
        :return: 编辑后的图片信息
        """
        logger.info(f"开始编辑图片: {prompt[:100]}")
        logger.info(f"files type: {type(files)}")
        
        # 调用Ezlink编辑API，一次性传入所有图片
        result = await self.ezlink.edit_image(prompt, files, model, n)
        
        if not result:
            raise BusinessException("Ezlink API 返回空结果", ErrorCode.IMAGE_EDIT_FAILED)
        
        # 保存图片并生成URL
        images = await self._save_images_with_urls(result, prefix="edited")
        
        # 构造返回结果
        response = {
            "success": True,
            "created": result.get("created"),
            "images": images,
            "usage": result.get("usage", {}),
            "prompt": prompt,
            "model": model
        }
        
        logger.info(f"图片编辑成功，数量: {len(images)}")
        return response

    async def _save_images_with_urls(self, result: Dict, prefix: str = "generated") -> List[Dict[str, Any]]:
        """
        保存图片并返回访问URL
        :param result: API返回结果
        :param prefix: 文件名前缀
        :return: 包含URL的图片信息列表
        """
        if not result or 'data' not in result:
            return []
            
        # 创建输出目录
        os.makedirs(self.image_dir, exist_ok=True)
        
        images = []
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        for i, item in enumerate(result.get("data", [])):
            if "b64_json" in item:
                # 生成唯一的文件名
                content_hash = hashlib.md5(item["b64_json"].encode()).hexdigest()[:8]
                filename = f"{prefix}_{timestamp}_{content_hash}_{i+1}.png"
                filepath = os.path.join(self.image_dir, filename)
                
                # 解码并保存图片
                image_data = base64.b64decode(item["b64_json"])
                with open(filepath, 'wb') as f:
                    f.write(image_data)
                
                # 构造访问URL（相对路径）
                image_url = f"{self.image_url_path}/{filename}"
                
                image_info = {
                    "index": i + 1,
                    "filename": filename,
                    "url": image_url,
                    "path": filepath
                }
                images.append(image_info)
                
                logger.info(f"保存图片: {filename}")
        
        return images
    
    async def batch_create_images(self, prompts: List[str], **kwargs) -> List[Dict[str, Any]]:
        """
        批量创建图片
        :param prompts: 图片描述列表
        :param kwargs: 其他参数（model, n, size等）
        :return: 所有图片的生成结果
        """
        results = []
        
        for i, prompt in enumerate(prompts):
            logger.info(f"批量生成图片进度: {i+1}/{len(prompts)}")
            result = await self.create_image(prompt, **kwargs)
            result["batch_index"] = i
            results.append(result)
            
        return results
    
    async def upload_image(self, image_data: bytes, filename: str = None) -> Dict[str, Any]:
        """
        上传图片（图床功能）
        :param image_data: 图片二进制数据
        :param filename: 文件名（可选）
        :return: 上传结果
        """
        logger.info(f"开始上传图片: {filename or '未命名'}")
        
        # 生成文件名
        if not filename:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            content_hash = hashlib.md5(image_data).hexdigest()[:8]
            filename = f"upload_{timestamp}_{content_hash}.png"
        
        # 确保文件有扩展名
        if not filename.lower().endswith(('.png', '.jpg', '.jpeg', '.gif', '.webp')):
            filename += '.png'
        
        # 保存图片
        filepath = os.path.join(self.image_dir, filename)
        os.makedirs(self.image_dir, exist_ok=True)
        
        try:
            with open(filepath, 'wb') as f:
                f.write(image_data)
            
            # 生成访问URL
            image_url = f"{self.image_url_path}/{filename}"
            
            response = {
                "success": True,
                "filename": filename,
                "url": image_url,
                "path": filepath,
                "size": len(image_data)
            }
            
            logger.info(f"图片上传成功: {filename}")
            return response
            
        except Exception as e:
            logger.error(f"图片上传失败: {e}")
            raise BusinessException(f"上传失败: {str(e)}", ErrorCode.IMAGE_UPLOAD_FAILED)
    
    async def upload_from_url(self, image_url: str) -> Dict[str, Any]:
        """
        从URL上传图片到图床
        :param image_url: 图片URL
        :return: 上传结果
        """
        logger.info(f"从URL上传图片: {image_url}")
        
        # 下载图片
        image_data = await self.ezlink.get_image_from_url(image_url)
        if not image_data:
            raise BusinessException("无法下载图片", ErrorCode.IMAGE_UPLOAD_FAILED)
        
        # 从URL提取文件名
        filename = image_url.split('/')[-1]
        if '.' not in filename:
            filename += '.png'
        
        return await self.upload_image(image_data, filename)