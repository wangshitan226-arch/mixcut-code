#!/usr/bin/env python3
"""
查询阿里云ICE转码模板列表
运行: python list_transcode_templates.py
"""
import json
import sys
sys.path.insert(0, 'd:\\project\\mixcut\\backend')

from config import ICE_CONFIG

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


def list_templates():
    client = create_client()
    
    # 查询系统预置模板
    print("=" * 60)
    print("系统预置模板 (Preset Templates):")
    print("=" * 60)
    
    try:
        request = ice_models.ListTranscodeTemplatesRequest(
            type='Preset',
            page_size=100
        )
        response = client.list_transcode_templates(request)
        
        for template in response.body.transcode_template_list:
            print(f"  ID: {template.template_id}")
            print(f"  名称: {template.name}")
            print(f"  格式: {template.container}")
            print(f"  视频: {template.video.codec if template.video else 'N/A'}")
            print(f"  分辨率: {template.video.resolution if template.video else 'N/A'}")
            print("-" * 40)
    except Exception as e:
        print(f"查询系统预置模板失败: {e}")
    
    # 查询自定义模板
    print("\n" + "=" * 60)
    print("自定义模板 (Custom Templates):")
    print("=" * 60)
    
    try:
        request = ice_models.ListTranscodeTemplatesRequest(
            type='Custom',
            page_size=100
        )
        response = client.list_transcode_templates(request)
        
        for template in response.body.transcode_template_list:
            print(f"  ID: {template.template_id}")
            print(f"  名称: {template.name}")
            print(f"  格式: {template.container}")
            print(f"  视频: {template.video.codec if template.video else 'N/A'}")
            print(f"  分辨率: {template.video.resolution if template.video else 'N/A'}")
            print("-" * 40)
    except Exception as e:
        print(f"查询自定义模板失败: {e}")


if __name__ == '__main__':
    list_templates()
