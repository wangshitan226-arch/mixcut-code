"""
阿里云OpenAPI签名工具
用于生成阿里云API请求的签名
"""
import hashlib
import hmac
import base64
import urllib.parse
from datetime import datetime
from typing import Dict


def sign_request(
    access_key_id: str,
    access_key_secret: str,
    params: Dict,
    http_method: str = 'POST',
    endpoint: str = 'ice.cn-shanghai.aliyuncs.com',
    api_version: str = '2020-11-09',
    action: str = ''
) -> Dict:
    """
    生成阿里云OpenAPI签名
    
    Args:
        access_key_id: AccessKey ID
        access_key_secret: AccessKey Secret
        params: API请求参数
        http_method: HTTP方法 (GET/POST)
        endpoint: API端点
        api_version: API版本
        action: API动作名称
    
    Returns:
        包含签名的完整参数字典
    """
    # 添加公共参数
    signed_params = params.copy()
    signed_params['Format'] = 'JSON'
    signed_params['Version'] = api_version
    signed_params['AccessKeyId'] = access_key_id
    signed_params['SignatureMethod'] = 'HMAC-SHA1'
    signed_params['Timestamp'] = datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%SZ')
    signed_params['SignatureVersion'] = '1.0'
    signed_params['SignatureNonce'] = str(int(datetime.now().timestamp() * 1000))
    if action:
        signed_params['Action'] = action
    
    # 按参数名排序
    sorted_params = sorted(signed_params.items())
    
    # 构造待签名字符串
    canonicalized_query_string = '&'.join(
        f'{urllib.parse.quote(k, safe="")}={urllib.parse.quote(str(v), safe="")}'
        for k, v in sorted_params
    )
    
    # 构造StringToSign
    string_to_sign = f'{http_method}&%2F&{urllib.parse.quote(canonicalized_query_string, safe="")}'
    
    # 计算签名
    key = f'{access_key_secret}&'
    signature = base64.b64encode(
        hmac.new(key.encode('utf-8'), string_to_sign.encode('utf-8'), hashlib.sha1).digest()
    ).decode('utf-8')
    
    # 添加签名到参数
    signed_params['Signature'] = signature
    
    return signed_params
