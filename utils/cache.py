# -*- coding: utf-8 -*-
"""Redis 缓存和分布式锁管理"""
import redis.asyncio as aioredis
from typing import Any, Optional, Dict
from contextlib import asynccontextmanager
import asyncio
import logging

logger = logging.getLogger(__name__)


class RedisInstanceManager:
    _instances: Dict[int, aioredis.Redis] = {}

    @classmethod
    def get_redis_instance(cls) -> aioredis.Redis:
        from config.settings import settings
        
        db = settings.redis.db
        
        if db not in cls._instances:
            pool = aioredis.ConnectionPool(
                username=settings.redis.user,
                host=settings.redis.host,
                port=settings.redis.port,
                password=settings.redis.password,
                db=db,
                decode_responses=False,
                max_connections=settings.redis.max_connections,
            )
            redis_client = aioredis.Redis(connection_pool=pool)
            cls._instances[db] = redis_client
            logger.info(f"Created Redis connection for db={db}")
        
        return cls._instances[db]

    @classmethod
    async def close_all(cls):
        for redis_instance in cls._instances.values():
            await redis_instance.close()
        cls._instances.clear()
        logger.info("All Redis connections closed")


def get_redis() -> aioredis.Redis:
    """获取默认 Redis 实例"""
    return RedisInstanceManager.get_redis_instance()


class DistributedLock:
    """分布式锁实现 - 防止死锁设计
    
    安全特性：
    1. 使用唯一值标识锁持有者，防止误删
    2. Redis 自动过期 (ex) 防止死锁
    3. Lua 脚本保证原子性
    4. 异常安全：release 失败也会重置状态
    """
    
    def __init__(
        self,
        redis_client: aioredis.Redis,
        key: str,
        timeout: float = 30.0
    ):
        self.redis = redis_client
        self.key = f"lock:{key}"
        self.timeout = timeout
        self._lock_value: Optional[str] = None
        self._acquired = False
    
    async def __aenter__(self):
        await self.acquire()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.release()
        return False
    
    async def acquire(self) -> bool:
        """获取锁"""
        if self._acquired:
            return True
        
        import uuid
        self._lock_value = str(uuid.uuid4())
        
        try:
            acquired = await self.redis.set(
                self.key,
                self._lock_value.encode(),
                nx=True,
                ex=int(self.timeout)
            )
            
            if acquired:
                self._acquired = True
                logger.debug(f"Lock acquired: {self.key}")
                return True
            
            return False
        except Exception as e:
            logger.error(f"Failed to acquire lock {self.key}: {e}")
            return False
    
    async def release(self):
        """释放锁 - 异常安全，确保状态重置"""
        if not self._acquired:
            return
        
        lock_key = self.key
        lock_value = self._lock_value
        
        try:
            lua_script = """
            if redis.call("get", KEYS[1]) == ARGV[1] then
                return redis.call("del", KEYS[1])
            else
                return 0
            end
            """
            await self.redis.eval(
                lua_script, 
                1, 
                lock_key, 
                lock_value.encode() if lock_value else b''
            )
            logger.debug(f"Lock released: {lock_key}")
        except Exception as e:
            logger.error(f"Failed to release lock {lock_key} (will auto-expire): {e}")
        finally:
            self._acquired = False
            self._lock_value = None


class RateLimiter:
    """频率限制器"""
    
    def __init__(
        self,
        redis_client: aioredis.Redis,
        key: str,
        max_requests: int,
        window: int
    ):
        self.redis = redis_client
        self.key = f"rate_limit:{key}"
        self.max_requests = max_requests
        self.window = window
    
    async def is_allowed(self) -> bool:
        """检查是否允许请求"""
        try:
            # 使用 Lua 脚本保证原子性
            lua_script = """
            local current = redis.call('incr', KEYS[1])
            if current == 1 then
                redis.call('expire', KEYS[1], ARGV[1])
            end
            return current
            """
            current = await self.redis.eval(lua_script, 1, self.key, self.window)

            logger.info(f"[RateLimiter] {self.key}: {current}/{self.max_requests}, TTL={self.window}s")

            return current <= self.max_requests
        except Exception as e:
            logger.error(f"Rate limiter error: {e}")
            return True
    
    async def get_remaining(self) -> int:
        """获取剩余可用次数"""
        try:
            current = int(await self.redis.get(self.key) or 0)
            return max(0, self.max_requests - current)
        except Exception:
            return self.max_requests


@asynccontextmanager
async def distributed_lock(
    key: str,
    timeout: float = 30.0,
    redis_client: Optional[aioredis.Redis] = None
):
    """分布式锁上下文管理器 - 异常安全
    
    保证锁一定会被释放，即使发生异常：
    1. 使用 finally 块确保释放
    2. release() 内部有异常处理
    3. Redis 自动过期防止死锁
    """
    if redis_client is None:
        redis_client = get_redis()
    
    lock = None
    acquired = False
    
    try:
        lock = DistributedLock(redis_client, key, timeout=timeout)
        acquired = await lock.acquire()
        
        if not acquired:
            raise Exception(f"Failed to acquire lock: {key}")
        
        yield lock
    except Exception as e:
        logger.error(f"Exception in lock context {key}: {e}")
        raise
    finally:
        if lock and acquired:
            try:
                await lock.release()
            except Exception as e:
                logger.error(f"Error releasing lock {key}: {e}")


async def check_rate_limit(
    key: str,
    max_requests: int,
    window: int,
    redis_client: Optional[aioredis.Redis] = None
) -> bool:
    """检查频率限制"""
    if redis_client is None:
        redis_client = get_redis()
    
    limiter = RateLimiter(redis_client, key, max_requests, window)
    return await limiter.is_allowed()



def with_lock_and_rate_limit(
    max_requests: int,
    window: int,
    lock_timeout: float = 30.0,
    operation: Optional[str] = None
):
    """分布式锁和频率限制装饰器
    
    Args:
        max_requests: 时间窗口内最大请求数
        window: 时间窗口（秒）
        lock_timeout: 锁超时时间（秒）
        operation: 操作名称，如果为 None 则使用函数名
    """
    def decorator(func):
        async def wrapper(self, *args, **kwargs):
            # 提取 source 和 source_id
            source = kwargs.get('source', 'default')
            source_id = kwargs.get('source_id', 'default')
            platform = getattr(self, 'platform_name', 'unknown')
            op_name = operation or func.__name__
            
            # 构建锁和频率限制的键
            key = f"{source}:{source_id}:{platform}:{op_name}"
            
            redis_client = get_redis()
            
            # 检查频率限制
            if not await check_rate_limit(key, max_requests, window, redis_client):
                logger.warning(f"Rate limit exceeded for {key}")
                raise Exception(f"Rate limit exceeded for {op_name}")
            
            # 获取分布式锁
            try:
                async with distributed_lock(key, lock_timeout, redis_client):
                    return await func(self, *args, **kwargs)
            except Exception as e:
                if "Failed to acquire lock" in str(e):
                    logger.warning(f"Lock acquisition failed for {key}")
                    raise Exception(f"Operation {op_name} is already in progress")
                raise
        
        return wrapper
    return decorator