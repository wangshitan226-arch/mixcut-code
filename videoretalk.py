"""
阿里云 VideoRetalk 对口型视频工具

官方文档: https://help.aliyun.com/zh/model-studio/developer-reference/videoretalk-api
价格: 0.08元/秒（约4.8元/分钟），免费额度1800秒（30分钟）
"""

import json
import time
import requests
from typing import Optional, Dict, Any
from config.settings import settings


class VideoRetalkTool:
    """
    阿里云 VideoRetalk 视频口型替换服务
    """

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or settings.ALIYUN_API_KEY
        self.base_url = settings.ALIYUN_BASE_URL
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "X-DashScope-Async": "enable"  # 启用异步模式
        }

    def submit_task(
        self,
        video_url: str,
        audio_url: str,
        ref_image_url: Optional[str] = None,
        video_extension: bool = False
    ) -> Dict[str, Any]:
        """
        提交视频口型替换任务

        Args:
            video_url: 模板视频URL（人物口播视频）
            audio_url: 驱动音频URL
            ref_image_url: 人脸参考图URL（可选）
            video_extension: 是否扩展视频时长

        Returns:
            {
                "success": True/False,
                "task_id": "task_xxx",
                "task_status": "PENDING",
                "request_id": "req_xxx"
            }
        """
        url = f"{self.base_url}/services/aigc/image2video/video-synthesis/"

        payload = {
            "model": "videoretalk",
            "input": {
                "video_url": video_url,
                "audio_url": audio_url,
                "ref_image_url": ref_image_url or ""
            },
            "parameters": {
                "video_extension": video_extension
            }
        }

        print(f"[VideoRetalk] 提交任务 - video_url: {video_url[:50]}...")
        print(f"[VideoRetalk] 提交任务 - audio_url: {audio_url[:50]}...")

        try:
            response = requests.post(
                url,
                headers=self.headers,
                json=payload,
                timeout=60
            )
            
            print(f"[VideoRetalk] 提交任务响应状态码: {response.status_code}")
            
            # 即使状态码不是200，也尝试读取响应内容
            try:
                result = response.json()
            except:
                result = {"text": response.text}
            
            print(f"[VideoRetalk] 提交任务响应: {json.dumps(result, ensure_ascii=False)[:500]}")
            
            response.raise_for_status()

            task_id = result.get("output", {}).get("task_id")
            task_status = result.get("output", {}).get("task_status")
            request_id = result.get("request_id")

            if not task_id:
                return {
                    "success": False,
                    "error": f"API未返回task_id，响应: {json.dumps(result, ensure_ascii=False)[:500]}"
                }

            return {
                "success": True,
                "task_id": task_id,
                "task_status": task_status,
                "request_id": request_id
            }

        except requests.exceptions.HTTPError as e:
            error_msg = f"HTTP错误 {e.response.status_code}: {e.response.text[:500]}"
            print(f"[VideoRetalk] 提交任务失败: {error_msg}")
            return {
                "success": False,
                "error": error_msg,
                "status_code": e.response.status_code
            }
        except requests.exceptions.RequestException as e:
            error_msg = f"请求异常: {str(e)}"
            print(f"[VideoRetalk] 提交任务失败: {error_msg}")
            return {
                "success": False,
                "error": error_msg
            }
        except Exception as e:
            error_msg = f"未知异常: {str(e)}"
            print(f"[VideoRetalk] 提交任务失败: {error_msg}")
            return {
                "success": False,
                "error": error_msg
            }

    def query_task(self, task_id: str) -> Dict[str, Any]:
        """
        查询任务状态和结果

        任务状态说明:
        - PENDING: 排队中
        - PRE-PROCESSING: 前置处理中
        - RUNNING: 处理中
        - POST-PROCESSING: 后置处理中
        - SUCCEEDED: 成功
        - FAILED: 失败

        Args:
            task_id: 任务ID

        Returns:
            {
                "success": True/False,
                "status": "SUCCEEDED",
                "video_url": "https://...",
                "video_duration": 10,
                "cost": 0.8
            }
        """
        url = f"{self.base_url}/tasks/{task_id}"

        headers = {
            "Authorization": f"Bearer {self.api_key}"
        }

        try:
            response = requests.get(
                url,
                headers=headers,
                timeout=30
            )
            
            # 先读取响应内容
            try:
                result = response.json()
            except:
                result = {"text": response.text}
            
            response.raise_for_status()

            output = result.get("output", {})
            task_status = output.get("task_status")
            
            print(f"[VideoRetalk] 查询任务 {task_id[:20]}... 状态: {task_status}")

            if task_status == "SUCCEEDED":
                video_url = output.get("video_url")
                usage = result.get("usage", {})

                video_duration = usage.get("video_duration", 0)
                cost = video_duration * 0.08  # 0.08元/秒

                return {
                    "success": True,
                    "status": task_status,
                    "video_url": video_url,
                    "video_duration": video_duration,
                    "cost": cost,
                    "usage": usage
                }

            elif task_status == "FAILED":
                error_code = output.get("code", "unknown")
                error_message = output.get("message", "未知错误")
                
                print(f"[VideoRetalk] 任务失败 - code: {error_code}, message: {error_message}")

                return {
                    "success": False,
                    "status": task_status,
                    "error_code": error_code,
                    "error_message": error_message,
                    "full_response": result
                }

            else:
                # 任务还在处理中
                return {
                    "success": True,
                    "status": task_status,
                    "pending": True
                }

        except requests.exceptions.HTTPError as e:
            error_msg = f"HTTP错误 {e.response.status_code}: {e.response.text[:500]}"
            print(f"[VideoRetalk] 查询任务失败: {error_msg}")
            return {
                "success": False,
                "error": error_msg,
                "status_code": e.response.status_code
            }
        except requests.exceptions.RequestException as e:
            error_msg = f"请求异常: {str(e)}"
            print(f"[VideoRetalk] 查询任务失败: {error_msg}")
            return {
                "success": False,
                "error": error_msg
            }
        except Exception as e:
            error_msg = f"未知异常: {str(e)}"
            print(f"[VideoRetalk] 查询任务失败: {error_msg}")
            return {
                "success": False,
                "error": error_msg
            }

    def wait_for_completion(
        self,
        task_id: str,
        poll_interval: int = 10,
        max_wait: int = 600
    ) -> Dict[str, Any]:
        """
        轮询等待任务完成

        Args:
            task_id: 任务ID
            poll_interval: 轮询间隔（秒），默认10秒
            max_wait: 最大等待时间（秒），默认600秒（10分钟）

        Returns:
            任务结果字典
        """
        elapsed = 0
        while elapsed < max_wait:
            result = self.query_task(task_id)

            if not result.get("success"):
                return result

            status = result.get("status")

            if status == "SUCCEEDED":
                return result
            elif status == "FAILED":
                return result

            # 还在处理中，等待后继续轮询
            time.sleep(poll_interval)
            elapsed += poll_interval

        return {
            "success": False,
            "status": "TIMEOUT",
            "error": f"等待超时，已等待 {max_wait} 秒"
        }

    def generate_avatar_video(
        self,
        video_url: str,
        audio_url: str,
        ref_image_url: Optional[str] = None,
        video_extension: bool = False,
        wait: bool = True
    ) -> Dict[str, Any]:
        """
        一站式生成数字人视频（提交任务+等待完成）

        Args:
            video_url: 模板视频URL
            audio_url: 驱动音频URL
            ref_image_url: 人脸参考图URL
            video_extension: 是否扩展视频
            wait: 是否等待任务完成

        Returns:
            {
                "success": True/False,
                "video_url": "https://...",
                "task_id": "task_xxx",
                "duration": 10,
                "cost": 0.8
            }
        """
        # 提交任务
        submit_result = self.submit_task(
            video_url=video_url,
            audio_url=audio_url,
            ref_image_url=ref_image_url,
            video_extension=video_extension
        )

        if not submit_result.get("success"):
            return submit_result

        task_id = submit_result.get("task_id")

        if not wait:
            return {
                "success": True,
                "task_id": task_id,
                "message": "任务已提交，请稍后查询结果"
            }

        # 等待任务完成
        final_result = self.wait_for_completion(task_id)

        if final_result.get("success") and final_result.get("status") == "SUCCEEDED":
            return {
                "success": True,
                "video_url": final_result.get("video_url"),
                "task_id": task_id,
                "duration": final_result.get("video_duration"),
                "cost": final_result.get("cost")
            }
        else:
            return final_result
