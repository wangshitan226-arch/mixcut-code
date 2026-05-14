#!/usr/bin/env python3
"""
视频号助手登录流程验证脚本
用于测试 Playwright 能否正常操作视频号助手
"""

import os
import json
import time
from playwright.sync_api import sync_playwright

# 配置
CHANNELS_LOGIN_URL = "https://channels.weixin.qq.com/login.html"
CHANNELS_PLATFORM_URL = "https://channels.weixin.qq.com/platform"
COOKIE_DIR = os.path.join(os.path.dirname(__file__), "channels_cookies")

# 确保目录存在
os.makedirs(COOKIE_DIR, exist_ok=True)


def test_login_flow():
    """测试视频号助手登录流程"""
    print("=" * 60)
    print("视频号助手登录流程验证")
    print("=" * 60)
    
    with sync_playwright() as p:
        # 启动浏览器（显示窗口，方便观察）
        print("\n[1] 启动 Chromium 浏览器...")
        browser = p.chromium.launch(
            headless=False,  # 显示窗口，方便扫码
            args=['--disable-blink-features=AutomationControlled']
        )
        
        # 创建新的浏览器上下文
        context = browser.new_context(
            viewport={'width': 1280, 'height': 800},
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        )
        
        # 注入脚本隐藏自动化特征
        context.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', {
                get: () => undefined
            });
            Object.defineProperty(navigator, 'plugins', {
                get: () => [1, 2, 3, 4, 5]
            });
        """)
        
        page = context.new_page()
        
        try:
            # 步骤 1: 打开登录页面
            print(f"[2] 打开视频号助手登录页...")
            page.goto(CHANNELS_LOGIN_URL, wait_until='networkidle', timeout=30000)
            print(f"    页面标题: {page.title()}")
            
            # 步骤 2: 等待页面加载完成，查找二维码
            print(f"[3] 等待二维码加载...")
            
            # 先截图看看页面内容
            screenshot_path = os.path.join(COOKIE_DIR, "login_page.png")
            page.screenshot(path=screenshot_path, full_page=True)
            print(f"    已截图保存到: {screenshot_path}")
            
            # 尝试查找二维码元素（可能有多种形式）
            qrcode_selectors = [
                'canvas',  # 二维码通常是 canvas
                'img[src*="qrcode"]',
                '.qrcode',
                '[class*="qr"]',
                '[class*="login"] img',
            ]
            
            qrcode_found = False
            for selector in qrcode_selectors:
                try:
                    element = page.wait_for_selector(selector, timeout=5000)
                    if element:
                        print(f"    找到二维码元素: {selector}")
                        # 截取二维码区域
                        qrcode_path = os.path.join(COOKIE_DIR, "qrcode.png")
                        element.screenshot(path=qrcode_path)
                        print(f"    二维码截图保存到: {qrcode_path}")
                        qrcode_found = True
                        break
                except Exception as e:
                    continue
            
            if not qrcode_found:
                print("    未找到标准二维码元素，请查看截图")
            
            # 步骤 3: 等待用户扫码登录
            print(f"[4] 请使用微信扫描二维码登录...")
            print(f"    等待登录完成（最多 120 秒）...")
            
            # 等待 URL 变化到平台页面
            try:
                page.wait_for_url(
                    lambda url: CHANNELS_PLATFORM_URL in url or "/platform" in url,
                    timeout=120000
                )
                print(f"    登录成功！当前 URL: {page.url}")
            except Exception as e:
                print(f"    等待登录超时: {e}")
                print(f"    当前 URL: {page.url}")
                return False
            
            # 步骤 4: 保存 Cookie
            print(f"[5] 保存登录状态...")
            cookies = context.cookies()
            storage_state = context.storage_state()
            
            cookie_file = os.path.join(COOKIE_DIR, "account_default.json")
            with open(cookie_file, 'w', encoding='utf-8') as f:
                json.dump({
                    'cookies': cookies,
                    'storage': storage_state,
                    'login_time': time.time()
                }, f, ensure_ascii=False, indent=2)
            
            print(f"    Cookie 已保存到: {cookie_file}")
            print(f"    Cookie 数量: {len(cookies)}")
            
            # 步骤 5: 尝试访问发布页面
            print(f"[6] 尝试访问发布页面...")
            page.goto("https://channels.weixin.qq.com/platform/post/create", 
                     wait_until='networkidle', timeout=30000)
            
            # 截图保存
            post_page_path = os.path.join(COOKIE_DIR, "post_create_page.png")
            page.screenshot(path=post_page_path, full_page=True)
            print(f"    发布页面截图保存到: {post_page_path}")
            print(f"    当前页面标题: {page.title()}")
            
            # 检查是否成功加载发布页面
            if "发表" in page.title() or "post" in page.url:
                print(f"    成功进入发布页面！")
            else:
                print(f"    可能未进入发布页面，请查看截图")
            
            print(f"\n{'=' * 60}")
            print("验证完成！")
            print(f"{'=' * 60}")
            return True
            
        except Exception as e:
            print(f"\n[错误] {e}")
            # 错误时截图
            error_path = os.path.join(COOKIE_DIR, "error.png")
            page.screenshot(path=error_path)
            print(f"错误截图保存到: {error_path}")
            return False
            
        finally:
            context.close()
            browser.close()
            print("\n浏览器已关闭")


def test_cookie_restore():
    """测试 Cookie 恢复登录"""
    print("\n" + "=" * 60)
    print("测试 Cookie 恢复登录")
    print("=" * 60)
    
    cookie_file = os.path.join(COOKIE_DIR, "account_default.json")
    if not os.path.exists(cookie_file):
        print("未找到 Cookie 文件，请先运行登录测试")
        return False
    
    with open(cookie_file, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    print(f"Cookie 文件大小: {os.path.getsize(cookie_file)} bytes")
    print(f"Cookie 数量: {len(data.get('cookies', []))}")
    print(f"登录时间: {data.get('login_time', 'unknown')}")
    
    with sync_playwright() as p:
        print("\n[1] 启动浏览器...")
        browser = p.chromium.launch(
            headless=False,
            args=['--disable-blink-features=AutomationControlled']
        )
        
        # 使用保存的 storage state 创建上下文
        context = browser.new_context(
            viewport={'width': 1280, 'height': 800},
            storage_state=data.get('storage')
        )
        
        page = context.new_page()
        
        try:
            print("[2] 尝试直接访问平台页面...")
            page.goto(CHANNELS_PLATFORM_URL, wait_until='networkidle', timeout=30000)
            
            # 截图
            restore_path = os.path.join(COOKIE_DIR, "restore_test.png")
            page.screenshot(path=restore_path, full_page=True)
            print(f"    截图保存到: {restore_path}")
            print(f"    当前 URL: {page.url}")
            print(f"    页面标题: {page.title()}")
            
            # 判断是否登录成功
            if "/login" in page.url:
                print("    Cookie 已过期，需要重新登录")
                return False
            else:
                print("    Cookie 恢复成功！")
                return True
                
        except Exception as e:
            print(f"[错误] {e}")
            return False
            
        finally:
            context.close()
            browser.close()


if __name__ == '__main__':
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == 'restore':
        test_cookie_restore()
    else:
        success = test_login_flow()
        if success:
            print("\n登录流程验证成功！")
            print("可以运行 `python test_channels_login.py restore` 测试 Cookie 恢复")
        else:
            print("\n登录流程验证失败，请检查截图和错误信息")
