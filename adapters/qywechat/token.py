"""企业微信Token管理模块"""
import aiohttp
from utils.logger import logger


async def get_access_token(corpid: str, corpsecret: str) -> str:
    """
    获取企业微信access_token（每次都获取最新的）
    
    Args:
        corpid: 企业ID
        corpsecret: 应用的凭证密钥
        
    Returns:
        access_token字符串
        
    Raises:
        ValueError: 获取token失败
    """
    url = "https://qyapi.weixin.qq.com/cgi-bin/gettoken"
    params = {
        "corpid": corpid,
        "corpsecret": corpsecret
    }
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, params=params) as response:
                data = await response.json()
                
                if data.get("errcode") == 0:
                    access_token = data["access_token"]
                    expires_in = data["expires_in"]
                    logger.info(f"获取企业微信access_token成功，有效期: {expires_in}秒")
                    return access_token
                else:
                    error_msg = data.get("errmsg", "未知错误")
                    logger.error(f"获取企业微信access_token失败: {error_msg}")
                    raise ValueError(f"获取access_token失败: {error_msg}")
                    
    except aiohttp.ClientError as e:
        logger.error(f"请求企业微信API失败: {e}")
        raise ValueError(f"请求企业微信API失败: {e}")
    except Exception as e:
        logger.error(f"获取token异常: {e}")
        raise