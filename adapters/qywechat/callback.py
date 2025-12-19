"""
企业微信回调验证服务

处理企业微信第三方应用的回调事件验证、消息解密等功能
参考文档：https://developer.work.weixin.qq.com/document/path/90930
"""
import base64
import hashlib
import hmac
import json
import time
from typing import Dict, Any, Optional, Tuple, Union
from xml.etree import ElementTree as ET
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives import padding
from cryptography.hazmat.backends import default_backend
from utils.logger import logger


class WeChatCallback:
    """企业微信回调服务"""
    
    def __init__(self, token: str, encoding_aes_key: str):
        """
        初始化回调服务
        
        Args:
            token: 企业微信应用的回调验证Token
            encoding_aes_key: 企业微信应用的回调消息加密密钥
        """
        self.token = token
        # EncodingAESKey是Base64编码的，需要解码
        self.aes_key = base64.b64decode(encoding_aes_key + "=")
        # 企业微信的AES密钥长度固定为32字节
        assert len(self.aes_key) == 32, "EncodingAESKey长度错误"
    
    def verify_url(self, msg_signature: str, timestamp: str, nonce: str, echostr: str) -> Optional[str]:
        """
        验证回调URL的合法性
        
        Args:
            msg_signature: 企业微信生成的签名
            timestamp: 时间戳
            nonce: 随机字符串
            echostr: 加密的验证字符串
            
        Returns:
            解密后的echostr，验证失败返回None
        """
        try:
            # 1. 参数验证
            if not all([msg_signature, timestamp, nonce, echostr]):
                logger.error("Missing required parameters")
                return None
            
            # 验证时间戳格式
            try:
                int(timestamp)
            except ValueError:
                logger.error("Invalid timestamp format")
                return None
            
            # 2. 签名验证
            if not self._verify_signature(msg_signature, timestamp, nonce, echostr):
                logger.error("Signature verification failed")
                return None
            
            # 3. 解密消息
            decrypted_echostr = self._decrypt_message(echostr)
            if not decrypted_echostr:
                logger.error("Decryption failed")
                return None
            
            # 4. 时间戳有效性检查（5分钟内）
            current_time = int(time.time())
            try:
                msg_time = int(timestamp)
                if abs(current_time - msg_time) > 300:
                    logger.warning("Timestamp expired")
            except ValueError:
                logger.warning("Invalid timestamp")
            
            logger.debug("URL verification successful")
            return decrypted_echostr
            
        except Exception as e:
            logger.error(f"Verification error: {e}")
            return None
    
    def decrypt_callback_message(self, encrypted_msg: str, msg_signature: str, 
                               timestamp: str, nonce: str) -> Optional[Dict[str, Any]]:
        """
        解密回调消息
        
        Args:
            encrypted_msg: 加密的消息内容
            msg_signature: 消息签名
            timestamp: 时间戳
            nonce: 随机字符串
            
        Returns:
            解密后的消息字典，失败返回None
        """
        logger.debug("Decrypting callback message")
        
        try:
            # 1. 验证签名
            if not self._verify_signature(msg_signature, timestamp, nonce, encrypted_msg):
                logger.error("Message signature verification failed")
                return None
            
            # 2. 解密消息
            decrypted_msg = self._decrypt_message(encrypted_msg)
            if decrypted_msg is None:
                logger.error("Message decryption failed")
                return None
            
            # 3. 解析XML
            msg_data = self._parse_xml_message(decrypted_msg)
            if msg_data is None:
                logger.error("XML parsing failed")
                return None
            
            logger.debug(f"Message decrypted: {msg_data.get('MsgType', 'unknown')}")
            return msg_data
            
        except Exception as e:
            logger.error(f"Message decryption error: {e}")
            return None
    
    def _verify_signature(self, msg_signature: str, timestamp: str, nonce: str, encrypt_str: str) -> bool:
        """
        验证消息签名
        
        Args:
            msg_signature: 企业微信生成的签名
            timestamp: 时间戳
            nonce: 随机字符串
            encrypt_str: 加密的字符串（echostr或加密的消息）
            
        Returns:
            签名是否正确
        """
        # 按照企业微信文档：将token、timestamp、nonce、encrypt_str按字典序排序后拼接
        tmp_list = [self.token, timestamp, nonce, encrypt_str]
        tmp_list.sort()
        tmp_str = "".join(tmp_list)
        
        # 计算SHA1签名
        tmp_str = tmp_str.encode('utf-8')
        sha1 = hashlib.sha1()
        sha1.update(tmp_str)
        hash_code = sha1.hexdigest()
        
        # 比较签名（不区分大小写）
        is_valid = hash_code.lower() == msg_signature.lower()
        
        if not is_valid:
            logger.debug(f"Signature mismatch - expected: {msg_signature}, calculated: {hash_code}")
        else:
            logger.debug("Signature verified")
        
        return is_valid
    
    def _decrypt_message(self, encrypted_msg: str) -> Optional[str]:
        """
        解密消息
        
        Args:
            encrypted_msg: Base64编码的加密消息
            
        Returns:
            解密后的明文，失败返回None
        """
        try:
            # Base64解码
            encrypted_data = base64.b64decode(encrypted_msg)
            
            # 企业微信消息格式：msg_len(4字节) + msg + corp_id(随机字符串)
            # AES-256-CBC模式，IV=密钥前16字节
            iv = self.aes_key[:16]
            cipher = Cipher(
                algorithms.AES(self.aes_key),
                modes.CBC(iv),
                backend=default_backend()
            )
            decryptor = cipher.decryptor()
            
            # 解密
            decrypted_data = decryptor.update(encrypted_data) + decryptor.finalize()
            
            # 去除PKCS7填充
            unpadder = padding.PKCS7(128).unpadder()
            unpadded_data = unpadder.update(decrypted_data) + unpadder.finalize()
            
            # 提取消息内容（前4字节是消息长度）
            msg_len = int.from_bytes(unpadded_data[:4], byteorder='big')
            message = unpadded_data[4:4 + msg_len].decode('utf-8')
            
            # 后面的是corp_id，可以验证但不必须
            # corp_id_len = len(unpadded_data) - 4 - msg_len
            # corp_id = unpadded_data[4 + msg_len:].decode('utf-8')
            
            return message
            
        except Exception as e:
            logger.debug(f"Decryption failed: {e}")
            return None
    
    def _parse_xml_message(self, xml_content: str) -> Optional[Dict[str, Any]]:
        """
        解析XML消息
        
        Args:
            xml_content: XML格式的消息内容
            
        Returns:
            解析后的消息字典
        """
        try:
            root = ET.fromstring(xml_content)
            
            # 解析基本的XML标签
            msg_data = {}
            for child in root:
                if child.tag == 'AgentID':
                    msg_data[child.tag] = int(child.text)
                elif child.tag in ['CreateTime', 'AuthLevel', ' Approver', 'Assistant', 'TemplateId']:
                    msg_data[child.tag] = int(child.text) if child.text.isdigit() else child.text
                else:
                    msg_data[child.tag] = child.text
            
            # 特殊处理某些消息类型
            if 'MsgType' in msg_data:
                msg_type = msg_data['MsgType']
                logger.debug(f"Msg type: {msg_type}")
                
                # 根据消息类型进行特殊处理
                if msg_type == 'text':
                    # 文本消息
                    pass
                elif msg_type == 'image':
                    # 图片消息，包含PicUrl和MediaId
                    pass
                elif msg_type == 'event':
                    # 事件消息，包含Event类型
                    event = msg_data.get('Event', '')
                    logger.debug(f"Event: {event}")
                    
                    # 特殊事件处理
                    if event == 'subscribe':
                        # 关注事件
                        logger.debug("User subscribe")
                    elif event == 'unsubscribe':
                        # 取消关注事件
                        logger.debug("User unsubscribe")
                    elif event == 'click':
                        # 菜单点击事件
                        logger.debug(f"Menu click: {msg_data.get('EventKey', '')}")
                    elif event == 'view':
                        # 链接跳转事件
                        logger.debug(f"Link view: {msg_data.get('EventKey', '')}")
            
            return msg_data
            
        except ET.ParseError as e:
            logger.error(f"XML parse error: {e}")
            return None
        except Exception as e:
            logger.error(f"Message parse error: {e}")
            return None
    
    def encrypt_message(self, message: str, nonce: str) -> Optional[Tuple[str, str, str]]:
        """
        加密回复消息（如果需要主动回复）
        
        Args:
            message: 要加密的消息明文
            nonce: 随机字符串
            
        Returns:
            (encrypted_msg, signature, timestamp) or None if failed
        """
        try:
            timestamp = str(int(time.time()))
            
            # 生成随机字符串
            import random
            import string
            rnd_str = ''.join(random.choices(string.ascii_letters + string.digits, k=16))
            
            # 按照企业微信格式构造明文：msg_len(4字节) + msg + rnd_str
            msg_bytes = message.encode('utf-8')
            msg_len = len(msg_bytes).to_bytes(4, byteorder='big')
            rnd_bytes = rnd_str.encode('utf-8')
            
            plain_text = msg_len + msg_bytes + rnd_bytes
            
            # 使用AES-256-CBC加密
            iv = self.aes_key[:16]
            cipher = Cipher(
                algorithms.AES(self.aes_key),
                modes.CBC(iv),
                backend=default_backend()
            )
            encryptor = cipher.encryptor()
            
            # PKCS7填充
            padder = padding.PKCS7(128).padder()
            padded_data = padder.update(plain_text) + padder.finalize()
            
            # 加密
            encrypted_data = encryptor.update(padded_data) + encryptor.finalize()
            
            # Base64编码
            encrypted_msg = base64.b64encode(encrypted_data).decode('utf-8')
            
            # 生成签名
            tmp_list = [self.token, timestamp, nonce, encrypted_msg]
            tmp_list.sort()
            tmp_str = "".join(tmp_list)
            
            sha1 = hashlib.sha1()
            sha1.update(tmp_str.encode('utf-8'))
            signature = sha1.hexdigest()
            
            return encrypted_msg, signature, timestamp
            
        except Exception as e:
            logger.error(f"Message encryption failed: {e}")
            return None

