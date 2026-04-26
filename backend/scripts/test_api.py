#!/usr/bin/env python3
"""
测试模板API
运行: python scripts/test_api.py
"""
import requests
import sys
sys.path.insert(0, 'd:\\project\\mixcut\\backend')

def test_templates_api():
    """测试模板API"""
    try:
        # 测试本地API
        url = 'http://localhost:3002/api/kaipai/templates'
        print(f"测试API: {url}")
        
        response = requests.get(url, timeout=10)
        print(f"状态码: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            templates = data.get('templates', [])
            print(f"返回模板数量: {len(templates)}")
            
            if templates:
                print("\n模板列表:")
                for t in templates:
                    print(f"  - {t.get('name')} (ID: {t.get('id')}, 分类: {t.get('category')})")
            else:
                print("警告: 返回的模板列表为空")
        else:
            print(f"错误: {response.text}")
            
    except requests.exceptions.ConnectionError:
        print("错误: 无法连接到后端服务，请确保服务已启动")
    except Exception as e:
        print(f"错误: {e}")

if __name__ == '__main__':
    test_templates_api()
