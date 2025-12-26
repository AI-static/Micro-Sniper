"""OSS异步客户端封装"""
from typing import Union, BinaryIO
from utils.logger import logger
from config.settings import settings
from alibabacloud_oss_v2 import models, Credentials, Config
from alibabacloud_oss_v2.aio import AsyncClient
from alibabacloud_oss_v2.types import CredentialsProvider


class OSSAsyncClient:
    """OSS异步客户端"""
    
    def __init__(self,
                 access_key_id: str,
                 access_key_secret: str,
                 endpoint: str,
                 bucket_name: str,
                 region: str = "cn-shenzhen"):
        """
        初始化OSS异步客户端
        
        Args:
            access_key_id: 访问密钥ID（必传）
            access_key_secret: 访问密钥（必传）
            endpoint: OSS端点（必传）
            bucket_name: 存储桶名称（必传）
            region: 区域（默认oss-cn-shenzhen）
        """
        self.access_key_id = access_key_id
        self.access_key_secret = access_key_secret
        self.endpoint = endpoint
        self.bucket_name = bucket_name
        self.region = region
        
        if not all([self.access_key_id, self.access_key_secret, self.endpoint, self.bucket_name]):
            raise ValueError("Missing required OSS configuration parameters: access_key_id, access_key_secret, endpoint, bucket_name are all required")

        # 创建凭证提供器
        class StaticCredentialsProvider(CredentialsProvider):
            def __init__(self, credentials: Credentials):
                self._credentials = credentials

            def get_credentials(self) -> Credentials:
                return self._credentials
        
        # 创建认证凭证
        credentials = Credentials(
            access_key_id=self.access_key_id,
            access_key_secret=self.access_key_secret
        )
        
        credentials_provider = StaticCredentialsProvider(credentials)

        config = Config(
            region=self.region,
            endpoint=self.endpoint,
            credentials_provider=credentials_provider
        )
        
        # 创建异步客户端
        self.client = AsyncClient(config)
    
    async def upload_file(self, object_name: str, file_data: Union[bytes, BinaryIO, str]) -> bool:
        """
        异步上传文件
        
        Args:
            object_name: 对象名称（文件路径）
            file_data: 文件数据，可以是bytes、文件对象或文件路径
            
        Returns:
            上传是否成功
        """
        try:
            # 处理不同类型的输入
            if isinstance(file_data, str):
                # 如果是文件路径，读取文件
                with open(file_data, 'rb') as f:
                    content = f.read()
                body = content
            elif isinstance(file_data, bytes):
                body = file_data
            else:
                # 文件对象
                body = file_data.read()
                if isinstance(body, str):
                    body = body.encode('utf-8')
            
            # 创建上传请求
            request = models.PutObjectRequest(
                bucket=self.bucket_name,
                key=object_name,
                body=body
            )
            
            # 执行上传
            result = await self.client.put_object(request)
            
            logger.info(f"文件上传成功: {object_name}")
            return True
            
        except Exception as e:
            logger.error(f"文件上传失败: {str(e)}")
            raise
    
    async def download_file(self, object_name: str) -> bytes:
        """
        异步下载文件
        
        Args:
            object_name: 对象名称（文件路径）
            
        Returns:
            文件内容（bytes）
        """
        try:
            request = models.GetObjectRequest(
                bucket=self.bucket_name,
                key=object_name
            )
            
            result = await self.client.get_object(request)
            content = await result.body.read()
            
            logger.info(f"文件下载成功: {object_name}")
            return content
            
        except Exception as e:
            logger.error(f"文件下载失败: {str(e)}")
            raise
    
    async def delete_file(self, object_name: str) -> bool:
        """
        异步删除文件
        
        Args:
            object_name: 对象名称（文件路径）
            
        Returns:
            删除是否成功
        """
        try:
            request = models.DeleteObjectRequest(
                bucket=self.bucket_name,
                key=object_name
            )
            
            result = await self.client.delete_object(request)
            
            logger.info(f"文件删除成功: {object_name}")
            return True
            
        except Exception as e:
            logger.error(f"文件删除失败: {str(e)}")
            return False
    
    async def create_folder(self, folder_name: str) -> bool:
        """
        异步创建文件夹（如果不存在）
        
        Args:
            folder_name: 文件夹名称，必须以 '/' 结尾
            
        Returns:
            创建是否成功
        """
        try:
            # 确保文件夹名以 '/' 结尾
            if not folder_name.endswith('/'):
                folder_name += '/'
            
            # 检查文件夹是否存在
            if await self.object_exists(folder_name):
                logger.info(f"文件夹已存在: {folder_name}")
                return True
            
            # 创建空对象表示文件夹
            request = models.PutObjectRequest(
                bucket=self.bucket_name,
                key=folder_name,
                body=b''
            )
            
            result = await self.client.put_object(request)
            
            logger.info(f"文件夹创建成功: {folder_name}")
            return True
            
        except Exception as e:
            logger.error(f"文件夹创建失败: {str(e)}")
            return False
    
    async def list_objects(self, prefix: str = '', max_keys: int = 100) -> list:
        """
        异步列出对象
        
        Args:
            prefix: 对象名前缀
            max_keys: 返回的最大对象数量
            
        Returns:
            对象列表
        """
        try:
            request = models.ListObjectsRequest(
                bucket=self.bucket_name,
                prefix=prefix,
                max_keys=max_keys
            )
            
            result = await self.client.list_objects(request)
            
            objects = []
            if result.contents:
                for obj in result.contents:
                    objects.append({
                        'key': obj.key,
                        'size': obj.size,
                        'last_modified': obj.last_modified,
                        'etag': obj.etag
                    })
            
            logger.info(f"对象列表获取成功，前缀: {prefix}, 数量: {len(objects)}")
            return objects
            
        except Exception as e:
            logger.error(f"对象列表获取失败: {str(e)}")
            return []
    
    async def object_exists(self, object_name: str) -> bool:
        """
        异步检查对象是否存在
        
        Args:
            object_name: 对象名称
            
        Returns:
            对象是否存在
        """
        try:
            request = models.HeadObjectRequest(
                bucket=self.bucket_name,
                key=object_name
            )
            
            # 尝试获取对象元数据
            result = await self.client.head_object(request)
            return True
            
        except Exception as e:
            # 如果是404错误，表示对象不存在
            if "NotFound" in str(e) or "NoSuchKey" in str(e):
                return False
            logger.error(f"检查对象存在性失败: {str(e)}")
            return False

    
    def get_public_url(self, object_name: str) -> str:
        """
        生成公共访问URL（非预签名）
        
        Args:
            object_name: 对象名称
            
        Returns:
            公共访问URL
        """


        return f'https://{self.bucket_name}.{self.endpoint}/{object_name}'
    
    async def upload_and_get_url(self, object_name: str, file_data: Union[bytes, BinaryIO, str]) -> str:
        """
        上传文件并返回URL
        
        Args:
            object_name: 对象名称（文件路径）
            file_data: 文件数据，可以是bytes、文件对象或文件路径

        Returns:
            文件访问URL
        """
        await self.upload_file(object_name, file_data)
        
        return self.get_public_url(object_name)

    async def close(self):
        """关闭客户端"""
        if hasattr(self, 'client'):
            await self.client.close()
    
    async def __aenter__(self):
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()

# 创建全局OSS客户端实例
oss_client = OSSAsyncClient(
    access_key_id=settings.oss.access_key_id,
    access_key_secret=settings.oss.access_key_secret,
    endpoint=settings.oss.endpoint,
    bucket_name=settings.oss.bucket_name
)
