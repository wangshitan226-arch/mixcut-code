#!/usr/bin/env python3
"""
注册OSS Bucket到阿里云IMS存储系统
运行: python register_oss_storage.py
"""
import sys
sys.path.insert(0, 'd:\\project\\mixcut\\backend')

from config import ICE_CONFIG, OSS_CONFIG

try:
    from alibabacloud_ice20201109.client import Client as ICEClient
    from alibabacloud_tea_openapi import models as open_api_models
    from alibabacloud_ice20201109 import models as ice_models
except ImportError:
    print("请先安装阿里云SDK: pip install alibabacloud_ice20201109")
    sys.exit(1)


def create_client():
    config = open_api_models.Config(
        access_key_id=ICE_CONFIG['access_key_id'],
        access_key_secret=ICE_CONFIG['access_key_secret']
    )
    config.endpoint = f"ice.{ICE_CONFIG['region']}.aliyuncs.com"
    return ICEClient(config)


def register_storage():
    """注册OSS存储到IMS"""
    client = create_client()
    
    bucket_name = OSS_CONFIG['bucket_name']
    
    # 构建存储配置
    storage_config = {
        "Bucket": bucket_name,
        "Region": OSS_CONFIG['region'],
        "Endpoint": f"oss-{OSS_CONFIG['region']}.aliyuncs.com"
    }
    
    try:
        # 尝试注册存储
        request = ice_models.AddStorageRequest(
            storage_type='OSS',
            storage_location=json.dumps(storage_config)
        )
        
        response = client.add_storage(request)
        print(f"存储注册成功: {response.body}")
        
    except Exception as e:
        print(f"存储注册失败: {e}")
        print("\n请手动在控制台注册:")
        print("1. 登录 https://ims.console.aliyun.com")
        print("2. 配置管理 → 存储管理")
        print(f"3. 添加存储，选择 bucket: {bucket_name}")


def list_storages():
    """列出已注册的存储"""
    client = create_client()
    
    try:
        request = ice_models.ListStoragesRequest()
        response = client.list_storages(request)
        
        print("已注册的存储列表:")
        for storage in response.body.storage_list:
            print(f"  - {storage.storage_type}: {storage.storage_location}")
            
    except Exception as e:
        print(f"查询存储列表失败: {e}")


if __name__ == '__main__':
    print("=" * 60)
    print("阿里云IMS存储注册工具")
    print("=" * 60)
    
    print("\n当前已注册的存储:")
    list_storages()
    
    print(f"\n尝试注册 bucket: {OSS_CONFIG['bucket_name']}")
    register_storage()
