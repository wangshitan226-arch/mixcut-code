#!/usr/bin/env python3
"""
精确截取视频号助手登录二维码
"""
import os
from playwright.sync_api import sync_playwright

CHANNELS_LOGIN_URL = "https://channels.weixin.qq.com/login.html"
COOKIE_DIR = os.path.join(os.path.dirname(__file__), "channels_cookies")
os.makedirs(COOKIE_DIR, exist_ok=True)


def test_precise_qrcode():
    """测试精确截取二维码"""
    print("=" * 60)
    print("精确截取视频号助手二维码")
    print("=" * 60)
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        context = browser.new_context(viewport={'width': 1280, 'height': 800})
        page = context.new_page()
        
        try:
            print("\n[1] 打开登录页面...")
            page.goto(CHANNELS_LOGIN_URL, wait_until='networkidle', timeout=30000)
            print(f"    页面标题: {page.title()}")
            
            # 等待二维码加载
            page.wait_for_timeout(3000)
            
            # 方法 1: 通过 JavaScript 找到二维码元素并获取位置
            print("\n[2] 通过 JavaScript 定位二维码...")
            
            # 先获取页面中所有 canvas 和 img 的位置信息
            elements_info = page.evaluate("""
                () => {
                    const results = [];
                    
                    // 查找所有 canvas
                    document.querySelectorAll('canvas').forEach((canvas, i) => {
                        const rect = canvas.getBoundingClientRect();
                        results.push({
                            type: 'canvas',
                            index: i,
                            x: rect.x,
                            y: rect.y,
                            width: rect.width,
                            height: rect.height,
                            visible: rect.width > 0 && rect.height > 0
                        });
                    });
                    
                    // 查找所有图片
                    document.querySelectorAll('img').forEach((img, i) => {
                        const rect = img.getBoundingClientRect();
                        results.push({
                            type: 'img',
                            index: i,
                            x: rect.x,
                            y: rect.y,
                            width: rect.width,
                            height: rect.height,
                            src: img.src.substring(0, 100),
                            visible: rect.width > 50 && rect.height > 50
                        });
                    });
                    
                    return results;
                }
            """)
            
            print(f"    找到 {len(elements_info)} 个元素")
            for info in elements_info:
                print(f"    {info['type']} {info['index']}: "
                      f"位置({info['x']:.0f}, {info['y']:.0f}) "
                      f"大小({info['width']:.0f}x{info['height']:.0f}) "
                      f"可见={info['visible']}")
            
            # 方法 2: 直接截取包含二维码的区域
            print("\n[3] 尝试截取二维码区域...")
            
            # 从截图分析，二维码大约在页面右侧中间位置
            # 尝试截取页面右侧 1/3 区域
            page_width = page.evaluate("() => window.innerWidth")
            page_height = page.evaluate("() => window.innerHeight")
            print(f"    页面大小: {page_width}x{page_height}")
            
            # 截取右侧区域（二维码大概位置）
            right_area = {
                'x': page_width * 0.55,
                'y': page_height * 0.15,
                'width': page_width * 0.4,
                'height': page_height * 0.7
            }
            
            right_path = os.path.join(COOKIE_DIR, "qrcode_right_area.png")
            page.screenshot(path=right_path, clip=right_area)
            print(f"    右侧区域已截取: {right_path}")
            
            # 方法 3: 尝试找到二维码的父容器
            print("\n[4] 查找二维码容器...")
            
            # 通过文本内容找到二维码附近的元素
            qr_container = page.evaluate("""
                () => {
                    // 查找包含"微信扫码登录"或"视频号助手"文本的元素
                    const texts = ['微信扫码登录', '视频号助手', '扫码登录'];
                    for (const text of texts) {
                        const elements = document.querySelectorAll('*');
                        for (const el of elements) {
                            if (el.textContent && el.textContent.includes(text)) {
                                const rect = el.getBoundingClientRect();
                                if (rect.width > 0 && rect.height > 0) {
                                    return {
                                        text: text,
                                        tag: el.tagName,
                                        x: rect.x,
                                        y: rect.y,
                                        width: rect.width,
                                        height: rect.height,
                                        parentHTML: el.parentElement ? el.parentElement.outerHTML.substring(0, 200) : ''
                                    };
                                }
                            }
                        }
                    }
                    return null;
                }
            """)
            
            if qr_container:
                print(f"    找到包含'{qr_container['text']}'的元素:")
                print(f"    位置: ({qr_container['x']:.0f}, {qr_container['y']:.0f})")
                print(f"    大小: {qr_container['width']:.0f}x{qr_container['height']:.0f}")
                
                # 截取该元素
                container_area = {
                    'x': qr_container['x'] - 50,
                    'y': qr_container['y'] - 200,
                    'width': qr_container['width'] + 100,
                    'height': qr_container['height'] + 250
                }
                
                container_path = os.path.join(COOKIE_DIR, "qrcode_container.png")
                page.screenshot(path=container_path, clip=container_area)
                print(f"    容器区域已截取: {container_path}")
            
            # 方法 4: 通过选择器查找
            print("\n[5] 尝试 CSS 选择器...")
            selectors = [
                'canvas',
                'img[src*="qr"]',
                'img[src*="code"]',
                '[class*="qr"]',
                '[class*="code"]',
                '[class*="login"] canvas',
                '[class*="scan"]',
            ]
            
            for selector in selectors:
                try:
                    element = page.query_selector(selector)
                    if element:
                        box = element.bounding_box()
                        if box and box['width'] > 50 and box['height'] > 50:
                            print(f"    选择器 '{selector}' 找到元素: "
                                  f"({box['x']:.0f}, {box['y']:.0f}) "
                                  f"{box['width']:.0f}x{box['height']:.0f}")
                            
                            # 截图这个元素
                            safe_selector = selector.replace('[', '').replace(']', '').replace('*', '').replace('=', '').replace('"', '').replace("'", '')
                            elem_path = os.path.join(COOKIE_DIR, f"qrcode_selector_{safe_selector}.png")
                            element.screenshot(path=elem_path)
                            print(f"      已保存: {elem_path}")
                except Exception as e:
                    pass
            
            print("\n" + "=" * 60)
            print("测试完成！请检查以下文件：")
            print("  - qrcode_right_area.png (右侧区域)")
            print("  - qrcode_container.png (二维码容器)")
            print("  - qrcode_selector_*.png (选择器匹配)")
            print("=" * 60)
            
            # 保持页面打开
            print("\n页面将保持打开 30 秒，供查看...")
            page.wait_for_timeout(30000)
            
        except Exception as e:
            print(f"\n[错误] {e}")
            import traceback
            traceback.print_exc()
        finally:
            context.close()
            browser.close()


if __name__ == '__main__':
    test_precise_qrcode()
