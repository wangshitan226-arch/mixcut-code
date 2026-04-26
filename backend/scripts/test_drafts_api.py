#!/usr/bin/env python3
"""
测试获取草稿API
"""
import requests

def test_drafts():
    try:
        url = 'http://localhost:3002/api/users/cb13b04d-dcc0-40e0-ab0c-f7502c4f0b34/kaipai/drafts'
        print(f"测试: {url}")
        response = requests.get(url, timeout=10)
        print(f"状态码: {response.status_code}")
        print(f"响应: {response.text}")
    except Exception as e:
        print(f"错误: {e}")

if __name__ == '__main__':
    test_drafts()
