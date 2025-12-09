"""图片相关的API模型"""
from pydantic import BaseModel, Field
from typing import Optional, List


class CreateImageRequest(BaseModel):
    """创建图片请求"""
    prompt: str = Field(..., description="图片描述", min_length=1, max_length=1000)
    model: str = Field("gemini-2.5-flash-image-preview", description="模型名称")
    n: int = Field(1, ge=1, le=10, description="生成图片数量")
    size: str = Field("1024x1024", description="图片尺寸")


class EditImageRequest(BaseModel):
    """编辑图片请求"""
    prompt: str = Field(..., description="编辑描述", min_length=1, max_length=1000)
    model: str = Field("gemini-2.5-flash-image-preview", description="模型名称")
    n: Optional[int] = Field(1, ge=1, le=10, description="生成图片数量")
    size: Optional[str] = Field(default="1024x1024", description="图片尺寸")


class BatchCreateRequest(BaseModel):
    """批量创建图片请求"""
    prompts: List[str] = Field(..., description="图片描述列表")
    model: str = Field("gemini-2.5-flash-image-preview", description="模型名称")
    n: int = Field(1, ge=1, le=10, description="每张图片生成数量")
    size: str = Field("1024x1024", description="图片尺寸")


class ImageInfo(BaseModel):
    """图片信息"""
    index: int
    filename: str
    url: str
    path: Optional[str] = None


class ImageResponse(BaseModel):
    """图片生成响应"""
    success: bool
    created: Optional[int] = None
    images: List[ImageInfo] = []
    usage: Optional[dict] = {}
    prompt: Optional[str] = None
    model: Optional[str] = None
    size: Optional[str] = None
    original_image_size: Optional[int] = None
    saved_files: Optional[List[str]] = None
    error: Optional[str] = None
    batch_index: Optional[int] = None