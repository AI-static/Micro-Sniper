"""图片生成服务"""
from typing import List, Dict, Any, Optional
from adapters import ezlink_client, vectorai_client
from utils.logger import logger
from utils.exceptions import BusinessException
from api.schema.base import ErrorCode
from models.images import get_model_info, ProviderEnum
from utils.oss import oss_client
from datetime import datetime
import hashlib
import base64


class ImageService:
    """图片生成业务服务"""
    
    def __init__(self):
        # OSS文件夹路径
        self.oss_folder = "Aether"

    async def create_image(self,
                           prompt: str,
                           model: str = "gemini-2.5-flash-image-preview",
                           n: int = 1,
                           size: str = "1024x1024",
                           aspect_ratio: str = '1:1',
                           resolution: str="1K") -> Dict[str, Any]:
        """
        创建图片
        :param prompt: 图片描述
        :param model: 模型名称
        :param n: 生成图片数量
        :param size: 图片尺寸
        :param aspect_ratio: 长宽比
        :param resolution: 分辨率
        :return: 包含图片链接和使用情况的结果
        """
        # 获取模型信息
        model_info = get_model_info(model)

        if not model_info:
            raise ValueError(f"不支持的模型: {model}")

        if size and model_info.supported_sizes and size not in model_info.supported_sizes:
            raise ValueError(f"不支持的尺寸: {size} 已经支持的为 {model_info.supported_sizes}")

        if aspect_ratio and model_info.supported_aspect_ratio and aspect_ratio not in model_info.supported_aspect_ratio:
            raise ValueError(f"不支持的长宽比: {aspect_ratio} 已经支持的为 {model_info.supported_aspect_ratio}")

        if resolution and model_info.supported_resolution and resolution not in model_info.supported_resolution:
            raise ValueError(f"不支持的长宽比: {resolution} 已经支持的为 {model_info.supported_resolution}")

        logger.info(f"开始创建图片: {prompt[:100]} model_info {model_info}")

        # 根据提供商调用不同的API - 统一使用OpenAI格式
        if model_info.provider == ProviderEnum.VECTORAI:
            # 调用VectorAI (OpenAI兼容) API，使用url格式
            response = await vectorai_client.images.generate(
                prompt=prompt,
                model=model,
                n=n,
                size=size,
                extra_body={
                    "watermark": True
                },
            )
        else:
            extra_body = {}
            if aspect_ratio:
                extra_body.update({"aspectRatio": aspect_ratio})

            if resolution:
                extra_body.update({"imageSize": resolution})

            logger.info(f"生成图片请求 prompt {prompt} {model} {extra_body}")
            response = await ezlink_client.images.generate(
                prompt=prompt,
                model=model,
                n=n,
                extra_body=extra_body,
            )
        if not response:
            provider_name = model_info.provider.value
            raise BusinessException(f"{provider_name} API 返回空结果", ErrorCode.IMAGE_GENERATE_FAILED)

        # 保存图片并生成URL
        images = await self._save_images_with_urls(response, model=model)

        # 兼容对象和字典格式
        if isinstance(response, dict):
            created = response.get("created", int(datetime.now().timestamp()))
            usage = response.get("usage", {})
        else:
            created = response.created
            usage = {
                "input_tokens": response.usage.input_tokens if hasattr(response, 'usage') else 0,
                "output_tokens": response.usage.output_tokens if hasattr(response, 'usage') else 0,
                "total_tokens": response.usage.total_tokens if hasattr(response, 'usage') else 0
            }

        # 构造返回结果
        result = {
            "success": True,
            "created": created,
            "images": images,
            "usage": usage,
            "prompt": prompt,
            "model": model,
            "size": size,
            "provider": model_info.provider.value
        }
        
        logger.info(f"图片生成成功，数量: {len(images)}，提供商: {model_info.provider.value}")
        return result
    
    async def edit_image(self, prompt: str, files,
                        model: str = "gemini-2.5-flash-image-preview",
                        n: int = 1,
                        size: Optional[str] = None,
                        aspect_ratio: Optional[str] = None,
                        resolution: Optional[str] = None) -> Dict[str, Any]:
        """
        编辑图片
        :param prompt: 编辑描述
        :param files: 图片文件（可能是单个文件或文件列表）
        :param model: 模型名称
        :param n: 生成图片数量
        :param size: 图片尺寸
        :param aspect_ratio: 长宽比
        :param resolution: 分辨率
        :return: 编辑后的图片信息
        """
        # 获取模型信息
        model_info = get_model_info(model)

        if model_info.provider != ProviderEnum.EZLINK:
            raise ValueError(f"不支持的模型: {model}")

        logger.info(f"开始编辑图片: {prompt[:100]}")
        logger.info(f"files type: {type(files)}")

        # 处理 Sanic 文件对象，转换为 OpenAI SDK 可接受的格式
        # 确保 files 是列表格式
        files_list = files if isinstance(files, list) else [files]
        logger.info(f"待处理图片数量: {len(files_list)}")

        # 处理所有文件
        processed_images = []
        for idx, file_obj in enumerate(files_list):
            # 确定 MIME 类型
            filename = file_obj.name if hasattr(file_obj, 'name') else f'image_{idx}.png'
            file_content = file_obj.body if hasattr(file_obj, 'body') else file_obj

            # 从文件名推断 MIME 类型
            mime_type = None
            if filename:
                lower_filename = filename.lower()
                if lower_filename.endswith('.jpg') or lower_filename.endswith('.jpeg'):
                    mime_type = 'image/jpeg'
                elif lower_filename.endswith('.png'):
                    mime_type = 'image/png'
                elif lower_filename.endswith('.webp'):
                    mime_type = 'image/webp'
                elif lower_filename.endswith('.gif'):
                    mime_type = 'image/gif'

            # 如果文件对象有 type 属性，优先使用（但要验证是否有效）
            if hasattr(file_obj, 'type') and file_obj.type and file_obj.type.startswith('image/'):
                mime_type = file_obj.type

            # 如果仍然无法确定 MIME 类型，使用默认值并记录警告
            if not mime_type:
                logger.warning(f"无法确定文件 [{idx+1}/{len(files_list)}] 的 MIME 类型，文件名: {filename}，使用默认值 image/png")
                mime_type = 'image/png'

            # 验证文件内容大小（至少 100 字节）
            if len(file_content) < 100:
                raise ValueError(f"文件 [{filename}] 内容过小，可能不是有效的图片文件（大小: {len(file_content)} bytes）")

            logger.info(f"处理文件 [{idx+1}/{len(files_list)}]: {filename}, MIME类型: {mime_type}, 文件大小: {len(file_content)} bytes")

            # 使用元组格式: (filename, file_content, mime_type)
            processed_images.append((filename, file_content, mime_type))

        # 准备 extra_body 参数
        extra_body = {}
        if aspect_ratio:
            extra_body["aspect_ratio"] = aspect_ratio
        if resolution:
            extra_body["resolution"] = resolution

        # 调用 OpenAI 兼容的 images.edit API
        # 如果只有一张图片，直接传递；如果有多张，传递列表
        image_param = processed_images[0] if len(processed_images) == 1 else processed_images

        result = await ezlink_client.images.edit(
            image=image_param,
            prompt=prompt,
            model=model,
            n=n,
            size=size,
            extra_body=extra_body if extra_body else None
        )
        
        if not result:
            raise BusinessException("Ezlink API 返回空结果", ErrorCode.IMAGE_EDIT_FAILED)

        # 保存图片并生成URL
        images = await self._save_images_with_urls(result, prefix="edited", model=model)

        # 兼容对象和字典格式处理返回结果
        if isinstance(result, dict):
            created = result.get("created", int(datetime.now().timestamp()))
            usage = result.get("usage", {})
        else:
            # Pydantic 对象格式
            created = result.created if hasattr(result, 'created') else int(datetime.now().timestamp())
            usage = {
                "input_tokens": result.usage.input_tokens if hasattr(result, 'usage') and hasattr(result.usage, 'input_tokens') else 0,
                "output_tokens": result.usage.output_tokens if hasattr(result, 'usage') and hasattr(result.usage, 'output_tokens') else 0,
                "total_tokens": result.usage.total_tokens if hasattr(result, 'usage') and hasattr(result.usage, 'total_tokens') else 0
            }

        # 构造返回结果
        response = {
            "success": True,
            "created": created,
            "images": images,
            "usage": usage,
            "prompt": prompt,
            "model": model,
            "size": size,
            "aspect_ratio": aspect_ratio,
            "resolution": resolution
        }

        logger.info(f"图片编辑成功，数量: {len(images)}")
        return response

    async def _save_images_with_urls(self, response, prefix: str = "generated", model: str = "unknown") -> List[Dict[str, Any]]:
        """
        保存图片并返回访问URL
        :param response: API返回结果（OpenAI格式对象或字典）
        :param prefix: 文件名前缀
        :return: 包含URL的图片信息列表
        """
        # 兼容对象和字典格式
        if isinstance(response, dict):
            data = response.get("data", [])
        else:
            data = response.data if hasattr(response, 'data') else []

        if not data:
            return []

        images = []

        for i, item in enumerate(data):
            # 兼容字典和对象格式
            if isinstance(item, dict):
                url = item.get("url")
                b64_json = item.get("b64_json")
            else:
                url = item.url if hasattr(item, 'url') else None
                b64_json = item.b64_json if hasattr(item, 'b64_json') else None

            # 直接使用adapter返回的URL（可能是外部URL或已上传到OSS的URL）
            if url:
                image_info = {
                    "index": i + 1,
                    "filename": f"{url.split('/')[-1]}" if url else f"{prefix}_{i+1}",
                    "url": url,
                    "path": None  # 不再需要path，因为文件都在OSS上
                }
                images.append(image_info)
                logger.info(f"图片URL: {url}")

            # 处理base64格式：解码并上传到OSS
            elif b64_json:
                try:
                    # 解码 base64 (修复padding)
                    missing_padding = len(b64_json) % 4
                    if missing_padding:
                        b64_json += '=' * (4 - missing_padding)
                    image_bytes = base64.b64decode(b64_json)

                    # 生成文件名
                    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                    content_hash = hashlib.md5(image_bytes).hexdigest()[:8]
                    filename = f"{prefix}_{model}_{timestamp}_{content_hash}.png"
                    object_name = f"{self.oss_folder}/{filename}"

                    # 上传到 OSS
                    oss_url = await oss_client.upload_and_get_url(object_name, image_bytes)

                    image_info = {
                        "index": i + 1,
                        "filename": filename,
                        "url": oss_url,
                        "path": None
                    }
                    images.append(image_info)
                    logger.info(f"图片已上传 OSS: {oss_url}")

                except Exception as e:
                    logger.error(f"上传图片到 OSS 失败: {e}")
                    # 失败时仍然返回，但标记失败
                    image_info = {
                        "index": i + 1,
                        "filename": f"{prefix}_{i+1}_failed",
                        "url": None,
                        "error": str(e)
                    }
                    images.append(image_info)

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
        上传图片到OSS（图床功能）
        :param image_data: 图片二进制数据
        :param filename: 文件名（可选）
        :return: 上传结果
        """
        logger.info(f"开始上传图片到OSS: {filename or '未命名'}")
        
        # 生成文件名
        if not filename:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            content_hash = hashlib.md5(image_data).hexdigest()[:8]
            filename = f"upload_{timestamp}_{content_hash}.png"
        
        # 确保文件有扩展名
        if not filename.lower().endswith(('.png', '.jpg', '.jpeg', '.gif', '.webp')):
            filename += '.png'
        
        try:
            # 上传到OSS
            object_name = f"{self.oss_folder}/{filename}"
            oss_url = await oss_client.upload_and_get_url(
                object_name, 
                image_data,
            )
            
            response = {
                "success": True,
                "filename": filename,
                "url": oss_url,
                "path": object_name,
                "size": len(image_data)
            }
            
            logger.info(f"图片上传到OSS成功: {filename}")
            return response
            
        except Exception as e:
            logger.error(f"图片上传到OSS失败: {e}")
            raise BusinessException(f"上传失败: {str(e)}", ErrorCode.IMAGE_UPLOAD_FAILED)
    
    
    async def get_models(self) -> List[Dict[str, Any]]:
        """获取所有支持的图片模型"""
        from models.images import get_all_models
        
        models = get_all_models()
        return [model.model_dump() for model in models]