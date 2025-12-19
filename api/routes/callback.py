"""
回调API路由

处理第三方应用（企业微信、飞书等）的回调验证
"""
from sanic import Blueprint, Request
from sanic.response import json, text
from utils.logger import logger
from adapters.qywechat.callback import WeChatCallback
from config.settings import global_settings

callback_bp = Blueprint('callback', url_prefix='/callback')


@callback_bp.get('/wechat_verify')
async def wechat_verify_url(request: Request):
    """
    企业微信URL验证
    
    验证回调URL的合法性，响应企业微信的验证请求
    
    Args:
        request: Sanic请求对象
        service_name: 服务名称，用于区分不同的企业微信应用
        
    Query Params:
        msg_signature: 企业微信生成的签名
        timestamp: 时间戳
        nonce: 随机字符串
        echostr: 加密的验证字符串
        
    Returns:
        解密后的echostr字符串
    """

    try:
        logger.info(f"wechat_verify_url {request.args}")
        # 获取验证参数
        msg_signature = request.args.get('msg_signature', '')
        timestamp = request.args.get('timestamp', '')
        nonce = request.args.get('nonce', '')
        echostr = request.args.get('echostr', '')
        
        # 获取服务配置
        if not global_settings.im.wechat_token or not global_settings.im.wechat_encoding_aes_key:
            return json({
                "success": False,
                "error": "Service configuration not found",
                "code": 404
            }, status=404)
        
        # 获取回调服务实例
        callback_service = WeChatCallback(
            token=global_settings.im.wechat_token,
            encoding_aes_key=global_settings.im.wechat_encoding_aes_key
        )
        
        # 调用 verify_url 函数处理所有业务逻辑
        result = callback_service.verify_url(
            msg_signature=msg_signature,
            timestamp=timestamp,
            nonce=nonce,
            echostr=echostr
        )
        
        if result is None:
            logger.error("URL verification failed")
            return json({
                "success": False,
                "error": "URL verification failed",
                "code": 403
            }, status=403)
        
        return text(result)
        
    except Exception as e:
        logger.error(f"URL verification error: {e}")
        return json({
            "success": False,
            "error": "Internal server error",
            "code": 500
        }, status=500)

