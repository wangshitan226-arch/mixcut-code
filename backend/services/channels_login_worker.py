#!/usr/bin/env python3
import sys
import os
import json
import time
import argparse
import traceback

CHANNELS_PLATFORM_URL = "https://channels.weixin.qq.com/platform"
COOKIE_BASE_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "channels_cookies")
os.makedirs(COOKIE_BASE_DIR, exist_ok=True)

USER_DATA_BASE_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "channels_user_data")
os.makedirs(USER_DATA_BASE_DIR, exist_ok=True)

CDP_PORT_BASE = 9300


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


def get_status_path(task_id: str) -> str:
    return os.path.join(COOKIE_BASE_DIR, f"status_{task_id}.json")


def get_log_path(task_id: str) -> str:
    return os.path.join(COOKIE_BASE_DIR, f"log_{task_id}.txt")


def log(task_id: str, message: str):
    timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{timestamp}][Worker][{task_id}] {message}"
    print(line, flush=True)
    try:
        with open(get_log_path(task_id), 'a', encoding='utf-8') as f:
            f.write(line + '\n')
    except:
        pass


def write_status(task_id: str, data: dict):
    status_path = get_status_path(task_id)
    temp_path = status_path + '.tmp'
    try:
        with open(temp_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False)
        if os.path.exists(status_path):
            os.remove(status_path)
        os.rename(temp_path, status_path)
        log(task_id, f"状态已写入: {data}")
    except Exception as e:
        log(task_id, f"写入状态文件失败: {e}")


def run_login(task_id: str):
    from playwright.sync_api import sync_playwright

    log(task_id, "========== 子进程启动 ==========")

    old_status = get_status_path(task_id)
    if os.path.exists(old_status):
        os.remove(old_status)
        log(task_id, "清理旧状态文件")

    user_data_dir = get_user_data_dir(task_id)
    cdp_port = get_cdp_port(task_id)
    log(task_id, f"使用持久化用户数据目录: {user_data_dir}")
    log(task_id, f"CDP调试端口: {cdp_port}")

    try:
        p = sync_playwright().start()
        log(task_id, "启动 Chromium（持久化用户数据目录 + CDP端口）...")
        context = p.chromium.launch_persistent_context(
            user_data_dir=user_data_dir,
            headless=False,
            args=[
                '--disable-blink-features=AutomationControlled',
                '--disable-web-security',
                f'--remote-debugging-port={cdp_port}',
            ],
            viewport={'width': 1280, 'height': 800},
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        )

        context.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', {
                get: () => undefined
            });
            Object.defineProperty(navigator, 'plugins', {
                get: () => [1, 2, 3, 4, 5]
            });
            window.chrome = { runtime: {} };
        """)

        page = context.pages[0] if context.pages else context.new_page()
        log(task_id, "打开视频号助手登录页...")

        write_status(task_id, {'status': 'opening'})

        page.goto("https://channels.weixin.qq.com/login.html", wait_until='networkidle', timeout=30000)

        time.sleep(2)
        initial_url = page.url
        log(task_id, f"当前URL: {initial_url}")

        if '/platform' in initial_url and '/login' not in initial_url:
            log(task_id, "检测到已登录状态（用户数据目录中有有效session）")
            cookie_path = get_cookie_path(task_id)
            storage = context.storage_state()
            with open(cookie_path, 'w', encoding='utf-8') as f:
                json.dump(storage, f, ensure_ascii=False, indent=2)
            write_status(task_id, {
                'status': 'success',
                'account_info': {
                    'nickname': '视频号账号',
                    'login_time': time.time()
                }
            })
            log(task_id, "========== 已登录，浏览器保持打开 ==========")
            while True:
                time.sleep(1)
            return

        log(task_id, "等待用户扫码（最多180秒）...")
        write_status(task_id, {'status': 'waiting_login'})

        max_wait = 180
        login_success = False
        start_time = time.time()

        for i in range(max_wait):
            try:
                current_url = page.evaluate("window.location.href")
            except:
                current_url = page.url

            elapsed = int(time.time() - start_time)

            if (i + 1) % 10 == 0 or i < 3:
                log(task_id, f"等待中... {elapsed}秒, URL: {current_url}")

            if current_url != initial_url:
                log(task_id, f"检测到URL变化: {initial_url} -> {current_url}")
                time.sleep(2)
                try:
                    final_url = page.evaluate("window.location.href")
                except:
                    final_url = page.url
                if final_url != initial_url:
                    log(task_id, f"确认URL已变化: {final_url}")
                    login_success = True
                    break

            time.sleep(1)

        final_url = page.url
        log(task_id, f"等待结束，最终URL: {final_url}")

        if not login_success:
            log(task_id, "登录超时或失败")
            write_status(task_id, {'status': 'failed', 'error': '登录超时，请重新尝试'})
            log(task_id, "浏览器保持打开（登录超时）")
            while True:
                time.sleep(1)
        else:
            log(task_id, "确认登录成功")

        log(task_id, "保存登录状态...")
        cookie_path = get_cookie_path(task_id)
        storage = context.storage_state()
        with open(cookie_path, 'w', encoding='utf-8') as f:
            json.dump(storage, f, ensure_ascii=False, indent=2)

        log(task_id, f"Cookie 已保存到: {cookie_path}")

        write_status(task_id, {
            'status': 'success',
            'account_info': {
                'nickname': '视频号账号',
                'login_time': time.time()
            }
        })

        log(task_id, "========== 登录成功，浏览器保持打开 ==========")
        while True:
            time.sleep(1)

    except Exception as e:
        error_msg = f"异常: {str(e)}\n{traceback.format_exc()}"
        log(task_id, error_msg)
        write_status(task_id, {'status': 'failed', 'error': str(e)})
        log(task_id, "发生异常，进程保持运行以便查看")
        while True:
            time.sleep(1)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--task-id', required=True)
    args = parser.parse_args()

    run_login(args.task_id)
