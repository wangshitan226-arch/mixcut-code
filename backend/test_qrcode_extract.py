#!/usr/bin/env python3
"""
测试从视频号助手登录页提取二维码
"""
import os
from playwright.sync_api import sync_playwright

CHANNELS_LOGIN_URL = "https://channels.weixin.qq.com/login.html"
COOKIE_DIR = os.path.join(os.path.dirname(__file__), "channels_cookies")
os.makedirs(COOKIE_DIR, exist_ok=True)


def test_qrcode_extraction():
    """测试提取二维码"""
    print("=" * 60)
    print("测试提取视频号助手登录二维码")
    print("=" * 60)
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        context = browser.new_context(
            viewport={'width': 1280, 'height': 800}
        )
        page = context.new_page()
        
        try:
            # 打开登录页面
            print("\n[1] 打开视频号助手登录页...")
            page.goto(CHANNELS_LOGIN_URL, wait_until='networkidle', timeout=30000)
            print(f"    页面标题: {page.title()}")
            
            # 等待页面加载
            page.wait_for_timeout(3000)
            
            # 方法 1: 查找 canvas 元素并截图
            print("\n[2] 尝试查找 canvas 元素...")
            canvas_elements = page.query_selector_all('canvas')
            print(f"    找到 {len(canvas_elements)} 个 canvas 元素")
            
            for i, canvas in enumerate(canvas_elements):
                try:
                    # 截图 canvas
                    canvas_path = os.path.join(COOKIE_DIR, f"canvas_{i}.png")
                    canvas.screenshot(path=canvas_path)
                    print(f"    Canvas {i} 已截图: {canvas_path}")
                except Exception as e:
                    print(f"    Canvas {i} 截图失败: {e}")
            
            # 方法 2: 查找 img 元素
            print("\n[3] 尝试查找 img 元素...")
            img_elements = page.query_selector_all('img')
            print(f"    找到 {len(img_elements)} 个 img 元素")
            
            for i, img in enumerate(img_elements):
                try:
                    src = img.get_attribute('src')
                    if src and ('qr' in src.lower() or 'code' in src.lower()):
                        img_path = os.path.join(COOKIE_DIR, f"img_qr_{i}.png")
                        img.screenshot(path=img_path)
                        print(f"    Img {i} (src={src[:50]}) 已截图")
                except:
                    pass
            
            # 方法 3: 查找包含二维码的 div 区域
            print("\n[4] 尝试查找二维码容器...")
            qr_selectors = [
                '[class*="qr"]',
                '[class*="qrcode"]',
                '[class*="login-code"]',
                '[class*="scan"]',
            ]
            
            for selector in qr_selectors:
                try:
                    elements = page.query_selector_all(selector)
                    if elements:
                        print(f"    选择器 '{selector}' 找到 {len(elements)} 个元素")
                        for i, elem in enumerate(elements[:3]):  # 最多截图前3个
                            selector_name = selector.replace('[class*="', '').replace('"]', '')
                            elem_path = os.path.join(COOKIE_DIR, f"elem_{selector_name}_{i}.png")
                            elem.screenshot(path=elem_path)
                            print(f"      元素 {i} 已截图")
                except Exception as e:
                    print(f"    选择器 '{selector}' 失败: {e}")
            
            # 方法 4: 获取页面 HTML 结构
            print("\n[5] 分析页面结构...")
            html_content = page.content()
            
            # 查找包含 qr、qrcode、canvas 的部分
            import re
            qr_patterns = [
                r'<canvas[^>]*>',
                r'class="[^"]*qr[^"]*"',
                r'class="[^"]*qrcode[^"]*"',
            ]
            
            for pattern in qr_patterns:
                matches = re.findall(pattern, html_content, re.IGNORECASE)
                if matches:
                    print(f"    找到匹配 '{pattern}': {len(matches)} 个")
                    for match in matches[:3]:
                        print(f"      {match[:100]}")
            
            # 方法 5: 执行 JavaScript 获取 canvas 数据
            print("\n[6] 尝试通过 JavaScript 获取 canvas 数据...")
            try:
                canvas_data = page.evaluate("""
                    () => {
                        const canvases = document.querySelectorAll('canvas');
                        return canvases.length;
                    }
                """)
                print(f"    JavaScript 找到 {canvas_data} 个 canvas")
                
                # 尝试将第一个 canvas 转为 base64
                if canvas_data > 0:
                    base64_data = page.evaluate("""
                        () => {
                            const canvas = document.querySelector('canvas');
                            if (canvas) {
                                return canvas.toDataURL('image/png');
                            }
                            return null;
                        }
                    """)
                    
                    if base64_data:
                        # 保存 base64 图片
                        import base64
                        img_data = base64_data.split(',')[1]
                        img_bytes = base64.b64decode(img_data)
                        base64_path = os.path.join(COOKIE_DIR, "canvas_from_js.png")
                        with open(base64_path, 'wb') as f:
                            f.write(img_bytes)
                        print(f"    Canvas base64 已保存: {base64_path}")
            except Exception as e:
                print(f"    JavaScript 获取失败: {e}")
            
            # 最后截图整个页面供参考
            full_page_path = os.path.join(COOKIE_DIR, "login_page_full.png")
            page.screenshot(path=full_page_path, full_page=True)
            print(f"\n[7] 完整页面截图已保存: {full_page_path}")
            
            print("\n" + "=" * 60)
            print("测试完成，请检查 channels_cookies 目录下的截图文件")
            print("=" * 60)
            
            # 保持页面打开，方便查看
            print("\n页面将保持打开 30 秒...")
            page.wait_for_timeout(30000)
            
        except Exception as e:
            print(f"\n[错误] {e}")
        finally:
            context.close()
            browser.close()


if __name__ == '__main__':
    test_qrcode_extraction()
