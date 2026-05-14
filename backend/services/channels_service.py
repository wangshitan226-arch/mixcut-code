"""
视频号运营服务
- 登录管理：使用 subprocess 启动独立进程运行 Playwright
- 发布功能：使用 Playwright 自动填充表单并点击发表
- 评论监控：优先使用 API，API 失败时使用 Playwright 网络拦截
"""
import os
import json
import time
import subprocess
import traceback
import tempfile
import requests
from datetime import datetime
from typing import Optional, Dict, List, Callable, Tuple

CHANNELS_PLATFORM_URL = "https://channels.weixin.qq.com/platform"
CHANNELS_LOGIN_URL = "https://channels.weixin.qq.com/login.html"
CHANNELS_API_BASE = "https://channels.weixin.qq.com/cgi-bin/mmfinderassistant-bin"

COOKIE_BASE_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "channels_cookies")
os.makedirs(COOKIE_BASE_DIR, exist_ok=True)

USER_DATA_BASE_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "channels_user_data")
os.makedirs(USER_DATA_BASE_DIR, exist_ok=True)

CDP_PORT_BASE = 9300

VIDEO_STORAGE_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "channels_videos")
os.makedirs(VIDEO_STORAGE_DIR, exist_ok=True)

USER_DATA_BASE_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "channels_user_data")
os.makedirs(USER_DATA_BASE_DIR, exist_ok=True)

WORKER_SCRIPT = os.path.join(os.path.dirname(__file__), "channels_login_worker.py")


def get_cookie_path(account_id: str) -> str:
    return os.path.join(COOKIE_BASE_DIR, f"account_{account_id}.json")


def get_user_data_dir(account_id: str) -> str:
    path = os.path.join(USER_DATA_BASE_DIR, f"account_{account_id}")
    os.makedirs(path, exist_ok=True)
    return path


def get_cdp_port(account_id: str) -> int:
    try:
        aid = int(account_id)
    except:
        aid = hash(account_id) % 1000
    return CDP_PORT_BASE + aid


def _try_connect_cdp(account_id: str):
    import socket
    cdp_port = get_cdp_port(account_id)
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    result = sock.connect_ex(('127.0.0.1', cdp_port))
    sock.close()
    if result == 0:
        return cdp_port
    return None


def _kill_browser_for_account(account_id: str):
    import subprocess
    user_data_dir = get_user_data_dir(account_id)
    try:
        result = subprocess.run(
            ['wmic', 'process', 'where',
             f"CommandLine like '%{user_data_dir}%'",
             'get', 'ProcessId'],
            capture_output=True, text=True, timeout=10
        )
        for line in result.stdout.strip().split('\n'):
            line = line.strip()
            if line.isdigit():
                print(f"[Browser] 终止占用用户数据目录的进程: PID {line}")
                subprocess.run(['taskkill', '/F', '/PID', line],
                               capture_output=True, timeout=5)
                time.sleep(1)
    except Exception as e:
        print(f"[Browser] 检查/终止浏览器进程失败: {e}")


def get_status_path(task_id: str) -> str:
    return os.path.join(COOKIE_BASE_DIR, f"status_{task_id}.json")


def _get_chromium_executable_path() -> Optional[str]:
    home = os.path.expanduser("~")
    base = os.path.join(home, "AppData", "Local", "ms-playwright")

    candidates = [
        os.path.join(base, "chromium-1194", "chrome-win", "chrome.exe"),
        os.path.join(base, "chromium-1097", "chrome-win", "chrome.exe"),
        os.path.join(base, "chromium-1084", "chrome-win", "chrome.exe"),
    ]

    for path in candidates:
        if os.path.exists(path):
            print(f"[Playwright] 使用 Chromium: {path}")
            return path

    for item in os.listdir(base) if os.path.exists(base) else []:
        item_path = os.path.join(base, item)
        if os.path.isdir(item_path) and item.startswith("chromium-"):
            exe = os.path.join(item_path, "chrome-win", "chrome.exe")
            if os.path.exists(exe):
                print(f"[Playwright] 自动发现 Chromium: {exe}")
                return exe

    print(f"[Playwright] 未找到本地 Chromium，将使用默认配置")
    return None


def _launch_browser(playwright_instance, headless=False):
    exe_path = _get_chromium_executable_path()
    kwargs = {
        'headless': headless,
        'args': [
            '--disable-blink-features=AutomationControlled',
            '--no-sandbox',
        ]
    }
    if exe_path:
        kwargs['executable_path'] = exe_path
    return playwright_instance.chromium.launch(**kwargs)


# ==================== Login Manager ====================

class ChannelsLoginManager:
    def __init__(self):
        self._processes: Dict[str, subprocess.Popen] = {}
        self._status: Dict[str, dict] = {}

    def start_login(self, task_id: str) -> dict:
        print(f"[LoginManager] 开始登录任务: {task_id}")

        if task_id in self._processes and self._processes[task_id].poll() is None:
            return {'error': '登录任务已存在'}

        self._status[task_id] = {
            'task_id': task_id,
            'status': 'opening',
        }

        try:
            process = subprocess.Popen(
                ['python', WORKER_SCRIPT, '--task-id', task_id],
                stdout=None,
                stderr=None,
                creationflags=subprocess.CREATE_NEW_PROCESS_GROUP
            )
            self._processes[task_id] = process
            print(f"[LoginManager] 子进程已启动: PID={process.pid}")
            return {'task_id': task_id, 'status': 'opening'}
        except Exception as e:
            print(f"[LoginManager] 启动子进程失败: {e}")
            self._status[task_id]['status'] = 'failed'
            self._status[task_id]['error'] = str(e)
            return {'error': str(e)}

    def get_login_status(self, task_id: str) -> dict:
        print(f"[LoginManager] 查询任务状态: {task_id}")

        status_path = get_status_path(task_id)
        if os.path.exists(status_path):
            try:
                with open(status_path, 'r', encoding='utf-8') as f:
                    file_status = json.load(f)
                    if task_id in self._status:
                        self._status[task_id].update(file_status)
                    else:
                        self._status[task_id] = file_status
                    self._status[task_id]['task_id'] = task_id
            except Exception as e:
                print(f"[LoginManager] 读取状态文件失败: {e}")

        return self._status.get(task_id, {'status': 'not_found'})

    def cleanup_task(self, task_id: str):
        print(f"[LoginManager] 清理任务: {task_id}")

        if task_id in self._processes:
            process = self._processes[task_id]
            if process.poll() is None:
                try:
                    subprocess.run(['taskkill', '/F', '/T', '/PID', str(process.pid)],
                                  capture_output=True, check=False)
                except:
                    try:
                        process.terminate()
                        process.wait(timeout=5)
                    except:
                        try:
                            process.kill()
                        except:
                            pass
            del self._processes[task_id]

        status_path = get_status_path(task_id)
        if os.path.exists(status_path):
            os.remove(status_path)

        if task_id in self._status:
            del self._status[task_id]


login_manager = ChannelsLoginManager()


# ==================== API Client ====================

class ChannelsAPIClient:
    BASE_URL = "https://channels.weixin.qq.com/cgi-bin/mmfinderassistant-bin"

    HIGH_INTENT_KEYWORDS = [
        '怎么买', '哪里买', '求链接', '多少钱', '价格', '怎么卖',
        '怎么联系', '微信', '私信', '想要', '想买', '怎么下单',
        '在哪买', '购买', '链接', '怎么加', '联系方式', '感兴趣',
        '咨询', '了解', '详情', '订购', '下单', '买', '卖'
    ]

    def __init__(self, account_id: str):
        self.account_id = account_id
        self.cookie_path = get_cookie_path(account_id)
        self.session = requests.Session()
        self.finder_username = None
        self.wxuin = None
        self._load_auth_data()

    def _load_auth_data(self):
        if not os.path.exists(self.cookie_path):
            raise FileNotFoundError(f"Cookie文件不存在: {self.cookie_path}")

        with open(self.cookie_path, 'r', encoding='utf-8') as f:
            state = json.load(f)

        for cookie in state.get('cookies', []):
            self.session.cookies.set(
                cookie['name'],
                cookie['value'],
                domain=cookie.get('domain', '').lstrip('.'),
                path=cookie.get('path', '/')
            )
            if cookie['name'] == 'wxuin':
                self.wxuin = cookie['value']

        for origin in state.get('origins', []):
            if 'channels.weixin.qq.com' in origin.get('origin', ''):
                for item in origin.get('localStorage', []):
                    if item['name'] == 'finder_username':
                        self.finder_username = item['value']

        self.session.headers.update({
            'Referer': 'https://channels.weixin.qq.com/platform',
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Content-Type': 'application/json',
            'Origin': 'https://channels.weixin.qq.com',
        })

        print(f"[APIClient] 加载认证数据: finder_username={self.finder_username}, wxuin={self.wxuin}")

    def _build_common_payload(self) -> dict:
        payload = {}
        if self.wxuin:
            payload['wxuin'] = int(self.wxuin)
        if self.finder_username:
            payload['finderUsername'] = self.finder_username
        return payload

    def check_auth(self) -> bool:
        try:
            url = f"{self.BASE_URL}/auth/auth_data"
            response = self.session.post(url, json={}, timeout=10)
            result = response.json()
            is_valid = result.get('errCode') == 0
            print(f"[APIClient] 认证检查: errCode={result.get('errCode')}, valid={is_valid}")
            return is_valid
        except Exception as e:
            print(f"[APIClient] 检查认证失败: {e}")
            return False

    def get_post_list(self, page_size: int = 20) -> List[dict]:
        try:
            url = f"{self.BASE_URL}/post/post_list"
            data = {**self._build_common_payload(), "pageSize": page_size}
            response = self.session.post(url, json=data, timeout=10)
            result = response.json()

            if result.get('errCode') == 0:
                post_list = result.get('data', {}).get('list', [])
                print(f"[APIClient] 获取视频列表成功: {len(post_list)} 条")
                return post_list
            else:
                print(f"[APIClient] 获取视频列表失败: errCode={result.get('errCode')}, errMsg={result.get('errMsg')}")
                return []
        except Exception as e:
            print(f"[APIClient] 获取视频列表异常: {e}")
            return []

    def find_video_id_by_title(self, title: str, max_retries: int = 6, retry_interval: int = 5) -> Optional[str]:
        for i in range(max_retries):
            post_list = self.get_post_list()
            for post in post_list:
                desc = post.get('desc', {})
                post_title = ''
                if isinstance(desc, dict):
                    post_title = desc.get('description', '') or ''
                    if not post_title:
                        for m in desc.get('media', []):
                            post_title = m.get('title', '') or ''
                            if post_title:
                                break
                else:
                    post_title = str(desc)

                if title and (title in post_title or post_title in title):
                    object_id = post.get('objectId', '')
                    if object_id:
                        print(f"[APIClient] 找到匹配视频: objectId={object_id}, title={post_title}")
                        return object_id

            if i < max_retries - 1:
                print(f"[APIClient] 未找到匹配视频，{retry_interval}秒后重试 ({i+1}/{max_retries})")
                time.sleep(retry_interval)

        print(f"[APIClient] 未找到匹配视频: {title}")
        return None

    def get_comment_list(self, feed_id: str, page_size: int = 20) -> List[dict]:
        payloads = [
            {"feedId": feed_id, "pageSize": page_size},
            {"exportId": feed_id, "pageSize": page_size},
            {"feedId": feed_id, "pageSize": page_size, "commentType": 0},
            {"exportId": feed_id, "pageSize": page_size, "commentType": 0},
        ]
        endpoints = [
            f"{self.BASE_URL}/comment/comment_list",
            f"{self.BASE_URL}/comment/comment_list_v2",
            f"{self.BASE_URL}/findercomment/comment_list",
            f"{self.BASE_URL}/findercomment/get_comment_list",
        ]

        for endpoint in endpoints:
            for payload_base in payloads:
                try:
                    data = {**self._build_common_payload(), **payload_base}
                    print(f"[APIClient] 尝试 {endpoint.split('/')[-1]} payload={list(payload_base.keys())}")
                    response = self.session.post(endpoint, json=data, timeout=10)
                    result = response.json()
                    if result.get('errCode') == 0:
                        comment_list = result.get('data', {}).get('commentList', [])
                        if comment_list:
                            print(f"[APIClient] 获取评论成功: {len(comment_list)} 条 from {endpoint.split('/')[-1]}")
                            return comment_list
                    else:
                        err_code = result.get('errCode')
                        if err_code != 300800:
                            print(f"[APIClient] errCode={err_code}, payload={payload_base}")
                except Exception as e:
                    pass

        print(f"[APIClient] 所有API方式均未获取到评论")
        return []

    def reply_comment(self, feed_id: str, comment_id: str, content: str) -> dict:
        endpoints = [
            f"{self.BASE_URL}/comment/reply",
            f"{self.BASE_URL}/findercomment/reply",
            f"{self.BASE_URL}/findercomment/add_reply",
        ]
        payloads = [
            {"feedId": feed_id, "commentId": comment_id, "content": content},
            {"exportId": feed_id, "commentId": comment_id, "content": content},
        ]

        for endpoint in endpoints:
            for payload_base in payloads:
                try:
                    data = {**self._build_common_payload(), **payload_base}
                    response = self.session.post(endpoint, json=data, timeout=10)
                    result = response.json()
                    if result.get('errCode') == 0:
                        print(f"[APIClient] 回复评论成功")
                        return {'success': True}
                    else:
                        err_code = result.get('errCode')
                        if err_code != 300800:
                            print(f"[APIClient] 回复失败: errCode={err_code}, msg={result.get('errMsg')}")
                except Exception as e:
                    pass

        print(f"[APIClient] 所有API回复方式均失败")
        return {'success': False, 'error': 'API回复失败'}

    @staticmethod
    def check_high_intent(text: str) -> Tuple[bool, List[str]]:
        found_keywords = []
        for keyword in ChannelsAPIClient.HIGH_INTENT_KEYWORDS:
            if keyword in text:
                found_keywords.append(keyword)
        return len(found_keywords) > 0, found_keywords


# ==================== Login Status Check ====================

def check_login_status(account_id: str) -> bool:
    try:
        client = ChannelsAPIClient(account_id)
        return client.check_auth()
    except FileNotFoundError:
        print(f"[CheckLogin] Cookie文件不存在: {account_id}")
        return False
    except Exception as e:
        print(f"[CheckLogin] 检查登录状态失败: {e}")
        return False


# ==================== Publisher ====================

class ChannelsPublisher:
    def __init__(self, account_id: str):
        self.account_id = account_id
        self.cookie_path = get_cookie_path(account_id)

    def publish_video(self, video_path: str, title: str, tags: str = "",
                      description: str = "", cover_path: str = None,
                      progress_callback: Callable = None) -> dict:
        from playwright.sync_api import sync_playwright

        if not os.path.exists(video_path):
            return {'success': False, 'error': f'视频文件不存在: {video_path}'}

        user_data_dir = get_user_data_dir(self.account_id)

        _kill_browser_for_account(self.account_id)

        p = None
        context = None

        try:
            if progress_callback:
                progress_callback('launching_browser', 5)

            print(f"[Publisher] 启动浏览器（持久化用户数据目录）...")
            p = sync_playwright().start()
            context = p.chromium.launch_persistent_context(
                user_data_dir=user_data_dir,
                headless=False,
                args=[
                    '--disable-blink-features=AutomationControlled',
                    '--no-sandbox',
                ],
                viewport={'width': 1280, 'height': 800},
                user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
            )

            context.add_init_script("""
                Object.defineProperty(navigator, 'webdriver', {
                    get: () => undefined
                });
            """)

            page = context.pages[0] if context.pages else context.new_page()

            print(f"[Publisher] 打开发布页面...")
            page.goto("https://channels.weixin.qq.com/platform/post/create",
                      wait_until='networkidle', timeout=60000)

            if "/login" in page.url:
                return {'success': False, 'error': '登录已过期，请重新登录'}

            if progress_callback:
                progress_callback('uploading', 20)

            print(f"[Publisher] 上传视频: {video_path}")
            file_input = page.wait_for_selector('input[type="file"]', timeout=15000)
            if file_input:
                file_input.set_input_files(video_path)
            else:
                return {'success': False, 'error': '无法找到上传按钮'}

            print(f"[Publisher] 等待视频上传完成...")
            max_wait = 300
            for i in range(max_wait):
                time.sleep(1)
                if progress_callback:
                    progress_callback('uploading', min(20 + int(i / max_wait * 30), 50))
                try:
                    title_input = page.query_selector('input[placeholder*="标题"], textarea[placeholder*="标题"]')
                    if title_input:
                        break
                except:
                    pass

            if progress_callback:
                progress_callback('filling_info', 60)

            try:
                title_input = page.wait_for_selector('input[placeholder*="标题"], textarea[placeholder*="标题"]', timeout=5000)
                if title_input:
                    title_input.fill(title)
                    print(f"[Publisher] 已填写标题: {title}")
            except Exception as e:
                print(f"[Publisher] 填写标题失败: {e}")

            if tags:
                tag_list = tags.split()
                for tag in tag_list:
                    try:
                        topic_input = page.wait_for_selector('input[placeholder*="话题"]', timeout=3000)
                        if topic_input:
                            topic_input.fill(f"#{tag}")
                            time.sleep(1)
                            try:
                                suggestion = page.wait_for_selector('[class*="suggestion"], [class*="dropdown"] li', timeout=3000)
                                if suggestion:
                                    suggestion.click()
                            except:
                                topic_input.press('Enter')
                    except:
                        pass

            if description:
                try:
                    desc_input = page.wait_for_selector('textarea[placeholder*="描述"], textarea[placeholder*="内容"]', timeout=3000)
                    if desc_input:
                        desc_input.fill(description)
                except:
                    pass

            if cover_path and os.path.exists(cover_path):
                try:
                    cover_input = page.wait_for_selector('input[type="file"][accept*="image"]', timeout=3000)
                    if cover_input:
                        cover_input.set_input_files(cover_path)
                        time.sleep(2)
                except:
                    pass

            if progress_callback:
                progress_callback('publishing', 80)

            print(f"[Publisher] 尝试点击发表按钮...")
            publish_clicked = False

            publish_selectors = [
                'button:has-text("发表")',
                'button:has-text("发布")',
                'button.publish-btn',
                '[class*="publish"] button',
                '[class*="submit"] button',
                'button[type="submit"]',
            ]

            for selector in publish_selectors:
                try:
                    btn = page.query_selector(selector)
                    if btn and btn.is_visible():
                        btn.click()
                        publish_clicked = True
                        print(f"[Publisher] 使用选择器 '{selector}' 点击了发表按钮")
                        break
                except:
                    continue

            if not publish_clicked:
                print(f"[Publisher] 未能自动点击发表按钮，请手动点击")
                try:
                    context.close()
                except:
                    pass
                p.stop()
                return {
                    'success': True,
                    'platform_link': page.url,
                    'message': '信息已填充，但未能自动点击发表，请手动点击发表按钮',
                    'auto_publish': False
                }

            print(f"[Publisher] 等待发表完成...")
            time.sleep(3)

            success_detected = False
            for i in range(30):
                time.sleep(1)
                current_url = page.url
                if '/platform/post/create' not in current_url:
                    success_detected = True
                    print(f"[Publisher] 检测到页面跳转: {current_url}")
                    break
                try:
                    success_msg = page.query_selector('[class*="success"], [class*="toast"]')
                    if success_msg:
                        success_detected = True
                        print(f"[Publisher] 检测到成功提示")
                        break
                except:
                    pass

            if progress_callback:
                progress_callback('completed', 90)

            if success_detected:
                print(f"[Publisher] 发表成功")
                return {
                    'success': True,
                    'message': '视频已成功发布',
                    'auto_publish': True
                }
            else:
                print(f"[Publisher] 发表状态不确定，可能仍在处理中")
                return {
                    'success': True,
                    'message': '已点击发表按钮，但未能确认发布结果，请检查视频号助手',
                    'auto_publish': True
                }

        except Exception as e:
            print(f"[Publisher] 发布失败: {e}")
            traceback.print_exc()
            return {'success': False, 'error': str(e)}
        finally:
            try:
                if context:
                    context.close()
            except:
                pass
            try:
                if p:
                    p.stop()
            except:
                pass


# ==================== Comment Monitor ====================

class ChannelsCommentMonitor:
    HIGH_INTENT_KEYWORDS = ChannelsAPIClient.HIGH_INTENT_KEYWORDS

    def __init__(self, account_id: str):
        self.account_id = account_id
        self.cookie_path = get_cookie_path(account_id)
        self.api_client = ChannelsAPIClient(account_id)

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass

    def fetch_comments(self, video_id: str) -> List[dict]:
        print(f"[CommentMonitor] 开始抓取评论, video_id={video_id}")

        api_comments = self.api_client.get_comment_list(video_id)
        if api_comments:
            return self._parse_raw_comments(api_comments)

        print(f"[CommentMonitor] API获取评论失败，使用Playwright方式")
        return self._fetch_comments_via_playwright(video_id)

    def _fetch_comments_via_playwright(self, video_id: str) -> List[dict]:
        from playwright.sync_api import sync_playwright

        captured_responses = []
        p = None
        browser = None
        context = None
        own_browser = False

        try:
            p = sync_playwright().start()

            cdp_port = _try_connect_cdp(self.account_id)
            if cdp_port:
                print(f"[CommentMonitor] 通过CDP连接已运行的浏览器 (端口 {cdp_port})...")
                try:
                    browser = p.chromium.connect_over_cdp(f"http://127.0.0.1:{cdp_port}")
                    contexts = browser.contexts
                    if contexts:
                        context = contexts[0]
                        print(f"[CommentMonitor] 复用已有浏览器上下文")
                    else:
                        context = browser.new_context()
                    own_browser = False
                except Exception as e:
                    print(f"[CommentMonitor] CDP连接失败: {e}，启动新浏览器")
                    browser = None
                    context = None

            if not context:
                print(f"[CommentMonitor] 启动新的持久化浏览器...")
                _kill_browser_for_account(self.account_id)
                user_data_dir = get_user_data_dir(self.account_id)
                context = p.chromium.launch_persistent_context(
                    user_data_dir=user_data_dir,
                    headless=False,
                    args=[
                        '--disable-blink-features=AutomationControlled',
                        '--disable-web-security',
                        f'--remote-debugging-port={get_cdp_port(self.account_id)}',
                    ],
                    viewport={'width': 1280, 'height': 800},
                    user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
                )
                context.add_init_script("""
                    Object.defineProperty(navigator, 'webdriver', {
                        get: () => undefined
                    });
                """)
                own_browser = True

            page = context.pages[0] if context.pages else context.new_page()

            def handle_response(response):
                url = response.url
                if 'cgi-bin' in url and response.status == 200:
                    try:
                        data = response.json()
                        captured_responses.append({
                            'url': url,
                            'data': data
                        })
                    except:
                        pass

            page.on('response', handle_response)

            print(f"[CommentMonitor] 导航到评论管理页面...")
            page.goto("https://channels.weixin.qq.com/platform/interaction/comment",
                      wait_until='networkidle', timeout=60000)

            current_url = page.evaluate("window.location.href")
            if "/login" in current_url:
                print(f"[CommentMonitor] 登录已过期")
                return []

            time.sleep(3)

            try:
                cancel_btn = page.locator('text=取消切换').first
                if cancel_btn.is_visible(timeout=1000):
                    cancel_btn.click()
                    time.sleep(1)
                    print(f"[CommentMonitor] 关闭了切换弹窗")
            except:
                pass

            print(f"[CommentMonitor] 等待视频列表加载...")
            time.sleep(5)

            print(f"[CommentMonitor] 用JS查找并点击第一个视频卡片...")
            clicked = page.evaluate("""
                () => {
                    const allElements = document.querySelectorAll('*');
                    for (const el of allElements) {
                        const cls = el.className || '';
                        if (typeof cls === 'string' && (
                            cls.includes('feed-comment') ||
                            cls.includes('MicroInteraction')
                        )) {
                            const parent = el.closest('[class*="item"]') || el.parentElement;
                            if (parent) {
                                parent.click();
                                return 'clicked_by_class: ' + cls;
                            }
                        }
                    }
                    const imgs = document.querySelectorAll('img[src*="finder"], img[src*="wxfile"]');
                    for (const img of imgs) {
                        const rect = img.getBoundingClientRect();
                        if (rect.width > 50 && rect.height > 50 && rect.x > 100 && rect.x < 600) {
                            img.click();
                            return 'clicked_by_img: ' + img.src.substring(0, 50);
                        }
                    }
                    const clickables = document.querySelectorAll('[class*="feed"], [class*="card"], [class*="post"]');
                    for (const el of clickables) {
                        const rect = el.getBoundingClientRect();
                        if (rect.width > 100 && rect.height > 80 && rect.x < 600 && rect.y > 100) {
                            el.click();
                            return 'clicked_by_generic: ' + el.className.substring(0, 50);
                        }
                    }
                    return 'not_found';
                }
            """)
            print(f"[CommentMonitor] JS点击结果: {clicked}")

            if clicked == 'not_found':
                print(f"[CommentMonitor] JS未找到视频卡片，尝试鼠标点击...")
                page.mouse.click(350, 280)
                time.sleep(1)

            print(f"[CommentMonitor] 等待评论数据加载...")
            time.sleep(8)

            page.screenshot(path=os.path.join(COOKIE_BASE_DIR, "comment_fetch_result.png"))

            network_comments = self._extract_comments_from_network(captured_responses, video_id)
            if network_comments:
                print(f"[CommentMonitor] 从网络拦截获取到 {len(network_comments)} 条评论")
                if own_browser:
                    try:
                        context.close()
                    except:
                        pass
                p.stop()
                return network_comments

            print(f"[CommentMonitor] 网络拦截未获取到评论，尝试DOM提取...")
            dom_comments = self._extract_comments_from_page_robust(page)
            if dom_comments:
                print(f"[CommentMonitor] 从DOM提取到 {len(dom_comments)} 条评论")
                if own_browser:
                    try:
                        context.close()
                    except:
                        pass
                p.stop()
                return dom_comments

            print(f"[CommentMonitor] 尝试在iframe中查找评论...")
            for frame in page.frames:
                if frame == page.main_frame:
                    continue
                frame_url = frame.url
                if 'interaction' in frame_url or 'comment' in frame_url or 'micro' in frame_url:
                    print(f"[CommentMonitor] 检查iframe: {frame_url[:80]}")
                    frame_comments = self._extract_comments_from_page_robust(frame)
                    if frame_comments:
                        print(f"[CommentMonitor] 从iframe提取到 {len(frame_comments)} 条评论")
                        if own_browser:
                            try:
                                context.close()
                            except:
                                pass
                        p.stop()
                        return frame_comments

            if own_browser:
                try:
                    context.close()
                except:
                    pass
            p.stop()

        except Exception as e:
            print(f"[CommentMonitor] Playwright抓取评论异常: {e}")
            traceback.print_exc()
        finally:
            if own_browser:
                try:
                    if context:
                        context.close()
                except:
                    pass
            try:
                if p:
                    p.stop()
            except:
                pass

        network_comments = self._extract_comments_from_network(captured_responses, video_id)
        if network_comments:
            return network_comments

        return []

    def _save_cookie(self, context):
        try:
            storage = context.storage_state()
            with open(self.cookie_path, 'w', encoding='utf-8') as f:
                json.dump(storage, f, ensure_ascii=False, indent=2)
        except:
            pass

    def _extract_comments_from_network(self, captured_responses: list, video_id: str = '') -> List[dict]:
        all_comments = []

        for resp in captured_responses:
            url = resp.get('url', '')
            resp_data = resp.get('data', {})

            if 'comment' in url.lower() and resp_data.get('errCode') == 0:
                comment_list = resp_data.get('data', {}).get('commentList', [])
                if comment_list:
                    all_comments.extend(comment_list)
                    print(f"[CommentMonitor] 网络: 从 {url.split('/')[-1]} 拦截到 {len(comment_list)} 条评论")

        if not all_comments:
            for resp in captured_responses:
                resp_data = resp.get('data', {})
                if resp_data.get('errCode') == 0:
                    data = resp_data.get('data', {})
                    if isinstance(data, dict):
                        for key, val in data.items():
                            if isinstance(val, list) and len(val) > 0 and isinstance(val[0], dict):
                                if any(k in str(val[0]).lower() for k in ['content', 'comment', 'nickname', 'text']):
                                    all_comments.extend(val)
                                    print(f"[CommentMonitor] 网络: 从 {resp['url'].split('/')[-1]}.{key} 发现 {len(val)} 条评论数据")

        if video_id and all_comments:
            filtered = []
            for c in all_comments:
                feed_id = c.get('feedId', '') or c.get('exportId', '') or c.get('objectId', '')
                if feed_id == video_id or not feed_id:
                    filtered.append(c)
            if filtered:
                all_comments = filtered

        print(f"[CommentMonitor] 网络拦截共获取 {len(all_comments)} 条评论")
        return self._parse_raw_comments(all_comments)

    def _extract_comments_from_page_robust(self, page_or_frame) -> List[dict]:
        comments = []
        try:
            print(f"[CommentMonitor] 用JS从页面DOM提取评论...")

            result = page_or_frame.evaluate("""
                () => {
                    const comments = [];
                    const chineseRegex = /[\\u4e00-\\u9fa5]{2,}/;
                    const allElements = document.querySelectorAll('*');
                    const processedTexts = new Set();

                    for (const el of allElements) {
                        if (el.children.length > 5) continue;

                        const text = el.textContent.trim();
                        if (!chineseRegex.test(text)) continue;
                        if (text.length < 2 || text.length > 500) continue;
                        if (processedTexts.has(text)) continue;

                        const cls = (el.className || '').toLowerCase();
                        const tag = el.tagName.toLowerCase();

                        const isCommentLike =
                            cls.includes('comment') ||
                            cls.includes('reply') ||
                            cls.includes('msg') ||
                            cls.includes('feed-comment') ||
                            cls.includes('interaction') ||
                            (cls.includes('item') && text.length < 200) ||
                            (cls.includes('content') && text.length < 200 && el.children.length <= 3);

                        const isNotComment =
                            cls.includes('menu') ||
                            cls.includes('nav') ||
                            cls.includes('header') ||
                            cls.includes('sidebar') ||
                            cls.includes('brand') ||
                            tag === 'title' ||
                            tag === 'script' ||
                            tag === 'style' ||
                            text.includes('视频号') ||
                            text.includes('扫码') ||
                            text.includes('登录') ||
                            text.includes('内容管理') ||
                            text.includes('互动管理') ||
                            text.includes('数据中心');

                        if (isCommentLike && !isNotComment) {
                            processedTexts.add(text);
                            let name = '';
                            let content = text;

                            const nameEl = el.querySelector('[class*="name"], [class*="nick"], [class*="user"]');
                            if (nameEl) {
                                name = nameEl.textContent.trim();
                            }

                            const contentEl = el.querySelector('[class*="content"], [class*="text"], [class*="body"]');
                            if (contentEl) {
                                content = contentEl.textContent.trim();
                            }

                            comments.push({
                                name: name,
                                content: content,
                                className: el.className || '',
                                tag: tag
                            });
                        }
                    }

                    return comments;
                }
            """)

            for item in result:
                content = item.get('content', '').strip()
                name = item.get('name', '').strip()
                if content and len(content) > 1:
                    is_high_intent, keywords = ChannelsAPIClient.check_high_intent(content)
                    comments.append({
                        'commenter_name': name or '未知用户',
                        'content': content,
                        'platform_comment_id': '',
                        'is_high_intent': is_high_intent,
                        'intent_keywords': ','.join(keywords) if keywords else None,
                    })

            print(f"[CommentMonitor] DOM提取到 {len(comments)} 条评论")
            for c in comments:
                print(f"  [{c['commenter_name']}] {c['content'][:60]}")

        except Exception as e:
            print(f"[CommentMonitor] DOM提取评论异常: {e}")
            traceback.print_exc()

        return comments

    def _parse_raw_comments(self, raw_comments: List[dict]) -> List[dict]:
        comments = []
        for item in raw_comments:
            try:
                content = (item.get('content', '') or item.get('text', '')
                           or item.get('commentContent', '') or '')
                commenter_name = (item.get('commenterNickname', '') or item.get('nickname', '')
                                  or item.get('userName', '') or '未知用户')
                comment_id = str(item.get('commentId', '') or item.get('id', '') or '')

                if not content:
                    continue

                is_high_intent, keywords = ChannelsAPIClient.check_high_intent(content)

                comments.append({
                    'commenter_name': commenter_name,
                    'content': content,
                    'platform_comment_id': comment_id,
                    'is_high_intent': is_high_intent,
                    'intent_keywords': ','.join(keywords) if keywords else None,
                })
            except Exception as e:
                print(f"[CommentMonitor] 解析评论失败: {e}")
                continue

        print(f"[CommentMonitor] 共解析 {len(comments)} 条评论")
        return comments

    def reply_comment(self, comment_id: str, reply_text: str, feed_id: str = '') -> bool:
        if not feed_id:
            print(f"[CommentMonitor] 回复评论缺少 feed_id")
            return False

        api_result = self.api_client.reply_comment(feed_id, comment_id, reply_text)
        if api_result.get('success'):
            return True

        print(f"[CommentMonitor] API回复失败，尝试Playwright方式")
        return self._reply_comment_via_playwright(comment_id, reply_text, feed_id)

    def _reply_comment_via_playwright(self, comment_id: str, reply_text: str, feed_id: str) -> bool:
        from playwright.sync_api import sync_playwright

        p = None
        browser = None
        context = None
        own_browser = False

        try:
            p = sync_playwright().start()

            cdp_port = _try_connect_cdp(self.account_id)
            if cdp_port:
                print(f"[CommentMonitor] 回复: 通过CDP连接已运行的浏览器 (端口 {cdp_port})...")
                try:
                    browser = p.chromium.connect_over_cdp(f"http://127.0.0.1:{cdp_port}")
                    contexts = browser.contexts
                    if contexts:
                        context = contexts[0]
                    else:
                        context = browser.new_context()
                    own_browser = False
                except Exception as e:
                    print(f"[CommentMonitor] CDP连接失败: {e}，启动新浏览器")
                    browser = None
                    context = None

            if not context:
                _kill_browser_for_account(self.account_id)
                user_data_dir = get_user_data_dir(self.account_id)
                context = p.chromium.launch_persistent_context(
                    user_data_dir=user_data_dir,
                    headless=False,
                    args=[
                        '--disable-blink-features=AutomationControlled',
                        '--disable-web-security',
                        f'--remote-debugging-port={get_cdp_port(self.account_id)}',
                    ],
                    viewport={'width': 1280, 'height': 800},
                    user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
                )
                context.add_init_script("""
                    Object.defineProperty(navigator, 'webdriver', {
                        get: () => undefined
                    });
                """)
                own_browser = True

            page = context.pages[0] if context.pages else context.new_page()

            page.goto("https://channels.weixin.qq.com/platform/interaction/comment",
                      wait_until='networkidle', timeout=60000)

            current_url = page.evaluate("window.location.href")
            if "/login" in current_url:
                print(f"[CommentMonitor] 登录已过期，无法回复")
                return False

            time.sleep(3)

            try:
                cancel_btn = page.locator('text=取消切换').first
                if cancel_btn.is_visible(timeout=1000):
                    cancel_btn.click()
                    time.sleep(1)
            except:
                pass

            time.sleep(5)

            print(f"[CommentMonitor] 点击视频卡片以显示评论...")
            page.evaluate("""
                () => {
                    const allElements = document.querySelectorAll('*');
                    for (const el of allElements) {
                        const cls = el.className || '';
                        if (typeof cls === 'string' && (
                            cls.includes('feed-comment') ||
                            cls.includes('MicroInteraction')
                        )) {
                            const parent = el.closest('[class*="item"]') || el.parentElement;
                            if (parent) {
                                parent.click();
                                return true;
                            }
                        }
                    }
                    const clickables = document.querySelectorAll('[class*="feed"], [class*="card"], [class*="post"]');
                    for (const el of clickables) {
                        const rect = el.getBoundingClientRect();
                        if (rect.width > 100 && rect.height > 80 && rect.x < 600 && rect.y > 100) {
                            el.click();
                            return true;
                        }
                    }
                    return false;
                }
            """)
            time.sleep(5)

            print(f"[CommentMonitor] 查找回复按钮...")
            reply_btn = page.evaluate("""
                () => {
                    const allElements = document.querySelectorAll('*');
                    for (const el of allElements) {
                        const text = el.textContent.trim();
                        const cls = (el.className || '').toLowerCase();
                        if (text === '回复' && el.offsetWidth > 0) {
                            el.click();
                            return 'clicked_reply_btn';
                        }
                    }
                    return 'not_found';
                }
            """)
            print(f"[CommentMonitor] 回复按钮: {reply_btn}")

            if reply_btn == 'not_found':
                print(f"[CommentMonitor] 未找到回复按钮")
                return False

            time.sleep(1)

            print(f"[CommentMonitor] 查找回复输入框...")
            input_found = page.evaluate("""
                (replyText) => {
                    const selectors = [
                        'textarea[placeholder*="回复"]',
                        'input[placeholder*="回复"]',
                        'textarea',
                        '[contenteditable="true"]',
                    ];
                    for (const sel of selectors) {
                        const el = document.querySelector(sel);
                        if (el && el.offsetWidth > 0) {
                            el.focus();
                            el.textContent = replyText;
                            el.value = replyText;
                            el.dispatchEvent(new Event('input', { bubbles: true }));
                            return 'filled: ' + sel;
                        }
                    }
                    return 'not_found';
                }
            """, reply_text)
            print(f"[CommentMonitor] 输入框: {input_found}")

            if input_found == 'not_found':
                try:
                    textarea = page.locator('textarea, [contenteditable="true"]').first
                    textarea.fill(reply_text)
                    print(f"[CommentMonitor] 通过Playwright fill填写回复")
                except:
                    print(f"[CommentMonitor] 未找到回复输入框")
                    return False

            time.sleep(0.5)

            print(f"[CommentMonitor] 查找发送按钮...")
            send_clicked = page.evaluate("""
                () => {
                    const allElements = document.querySelectorAll('*');
                    for (const el of allElements) {
                        const text = el.textContent.trim();
                        if ((text === '发送' || text === '提交' || text === '确定') && el.offsetWidth > 0) {
                            const tag = el.tagName.toLowerCase();
                            if (tag === 'button' || tag === 'a' || el.onclick || el.getAttribute('role') === 'button') {
                                el.click();
                                return 'clicked: ' + text;
                            }
                        }
                    }
                    return 'not_found';
                }
            """)

            if send_clicked == 'not_found':
                try:
                    page.locator('textarea, [contenteditable="true"]').first.press('Enter')
                    print(f"[CommentMonitor] 通过Enter键发送回复")
                except:
                    pass
            else:
                print(f"[CommentMonitor] 发送按钮: {send_clicked}")

            time.sleep(2)
            print(f"[CommentMonitor] Playwright回复完成")
            if own_browser:
                try:
                    context.close()
                except:
                    pass
            p.stop()
            return True

        except Exception as e:
            print(f"[CommentMonitor] Playwright回复异常: {e}")
            traceback.print_exc()
            return False
        finally:
            if own_browser:
                try:
                    if context:
                        context.close()
                except:
                    pass
            try:
                if p:
                    p.stop()
            except:
                pass

    def _check_high_intent(self, text: str) -> Tuple[bool, List[str]]:
        return ChannelsAPIClient.check_high_intent(text)
