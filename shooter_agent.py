"""
拍 Agent - 数字人视频生成

功能:
1. 语音合成 (CosyVoice) - 上传到OSS
2. 数字人对口型 (VideoRetalk) - 上传到OSS
3. 支持混剪模式：分段语音合成（每组4段：开头+钩子+内容+结尾）
"""

import requests
import asyncio
from typing import List, Dict, Any
from langgraph.graph import StateGraph
from app.agents.state import WorkflowState, VoiceInfo, AvatarVideoInfo, VoiceSegmentInfo
from app.tools.cosyvoice import CosyVoiceTool
from app.tools.videoretalk import VideoRetalkTool
from app.tools.oss_simple import OSSSimpleTool


class ShooterAgent:
    """数字人视频生成智能体"""

    def __init__(self, voice_id: str = "default_voice", avatar_video_url: str = None, user_id: int = 1, progress_callback=None):
        self.cosyvoice = CosyVoiceTool()
        self.videoretalk = VideoRetalkTool()
        self.oss = OSSSimpleTool()
        self.voice_id = voice_id
        self.avatar_video_url = avatar_video_url  # 模板视频URL
        self.user_id = user_id  # 用户ID，用于OSS上传路径
        self.progress_callback = progress_callback  # 进度回调函数

    async def synthesize_voices(self, state: WorkflowState) -> WorkflowState:
        """
        语音合成 - 根据 task_mode 决定合成方式
        - normal: 为完整文案合成语音
        - mixcut: 为结构化文案分段合成语音（3组×4段=12段）
        """
        task_mode = state.get("task_mode", "normal")
        
        if task_mode == "mixcut":
            return await self._synthesize_segmented_voices(state)
        else:
            return await self._synthesize_normal_voices(state)

    async def _synthesize_normal_voices(self, state: WorkflowState) -> WorkflowState:
        """
        普通模式：为完整文案合成语音
        """
        scripts = state["scripts"]
        voices: List[VoiceInfo] = []

        for script in scripts:
            try:
                # 检查文本长度，如果太长则分段合成
                text = script["content"]
                max_length = 500  # CosyVoice 单次最大字符数
                
                if len(text) > max_length:
                    print(f"[ShooterAgent] 文本长度 {len(text)} 超过限制，分段合成")
                    text = text[:max_length] + "..."
                
                result = self.cosyvoice.synthesize(
                    text=text,
                    voice_id=self.voice_id
                )

                if result.get("success"):
                    # 下载音频并上传到OSS
                    temp_audio_url = result["audio_url"]
                    oss_result = await self._upload_audio_to_oss(temp_audio_url, f"voice_{script['index']}.mp3")
                    
                    if oss_result.get("success"):
                        voices.append({
                            "voice_id": self.voice_id,
                            "audio_url": oss_result["url"],
                            "duration": result.get("duration", 0),
                        })
                        print(f"[ShooterAgent] 语音合成并上传成功: {oss_result['url']}")
                    else:
                        error_msg = f"上传OSS失败: {oss_result.get('message')}"
                        print(f"[ShooterAgent] {error_msg}")
                        voices.append({
                            "voice_id": self.voice_id,
                            "audio_url": f"placeholder_audio_{script['index']}.mp3",
                            "duration": 10,
                        })
                else:
                    error_msg = result.get("error", "未知错误")
                    print(f"[ShooterAgent] 语音合成失败: {error_msg}")
                    voices.append({
                        "voice_id": self.voice_id,
                        "audio_url": f"placeholder_audio_{script['index']}.mp3",
                        "duration": 10,
                    })
            except Exception as e:
                print(f"[ShooterAgent] 语音合成异常: {e}")
                voices.append({
                    "voice_id": self.voice_id,
                    "audio_url": f"placeholder_audio_{script['index']}.mp3",
                    "duration": 10,
                })

        state["voices"] = voices
        
        # 检查有效语音数量，如果全部失败则抛出异常
        valid_voices = [v for v in voices if "placeholder" not in v.get("audio_url", "")]
        if len(valid_voices) == 0 and len(voices) > 0:
            raise Exception("语音合成全部失败，无法继续后续步骤")
        
        state["current_step"] = "voice_synthesis_completed"
        print(f"[ShooterAgent] 普通模式语音合成完成：{len(voices)}个语音，有效: {len(valid_voices)}个")
        return state

    async def _synthesize_segmented_voices(self, state: WorkflowState) -> WorkflowState:
        """
        混剪模式：为结构化文案分段合成语音
        3组文案 × 4个部分（开头+钩子+内容+结尾）= 12段语音
        """
        import time
        structured_scripts = state.get("structured_scripts", [])
        voice_segments: List[VoiceSegmentInfo] = []
        errors = []

        print(f"[ShooterAgent] 混剪模式：分段语音合成，共{len(structured_scripts)}组文案")
        print(f"[ShooterAgent] 开始时间: {time.strftime('%Y-%m-%d %H:%M:%S')}")

        for script in structured_scripts:
            group_index = script["index"]
            
            # 为每个部分合成语音
            parts = [
                ("opening", script["opening"]),
                ("hook", script["hook"]),
                ("content", script["content"]),
                ("ending", script["ending"])
            ]
            
            for part_name, text in parts:
                try:
                    result = self.cosyvoice.synthesize(
                        text=text,
                        voice_id=self.voice_id,
                        custom_filename=f"voice_{group_index}_{part_name}"
                    )

                    if result.get("success"):
                        # 下载音频并上传到OSS
                        temp_audio_url = result["audio_url"]
                        oss_result = await self._upload_audio_to_oss(temp_audio_url, f"voice_{group_index}_{part_name}.mp3")
                        
                        if oss_result.get("success"):
                            # 验证文件是否真的上传成功
                            uploaded_url = oss_result["url"]
                            print(f"[ShooterAgent] 验证上传结果: {uploaded_url}")
                            verify_result = await self._verify_oss_file(uploaded_url)
                            
                            if verify_result.get("success"):
                                voice_segments.append({
                                    "part": part_name,
                                    "audio_url": uploaded_url,
                                    "duration": result.get("duration", 5),
                                    "group_index": group_index,
                                    "text": text  # 保存文案，用于字幕显示
                                })
                                print(f"[ShooterAgent] ✓ 语音片段合成并上传成功: 组{group_index}-{part_name}")
                            else:
                                error_msg = f"上传验证失败: {verify_result.get('message')}"
                                print(f"[ShooterAgent] ✗ {error_msg}")
                                errors.append(f"组{group_index}-{part_name}: {error_msg}")
                                voice_segments.append({
                                    "part": part_name,
                                    "audio_url": f"placeholder_audio_{group_index}_{part_name}.mp3",
                                    "duration": 5,
                                    "group_index": group_index,
                                    "text": text  # 保存文案，用于字幕显示
                                })
                        else:
                            error_msg = f"上传OSS失败: {oss_result.get('message')}"
                            print(f"[ShooterAgent] ✗ {error_msg}")
                            errors.append(f"组{group_index}-{part_name}: {error_msg}")
                            voice_segments.append({
                                "part": part_name,
                                "audio_url": f"placeholder_audio_{group_index}_{part_name}.mp3",
                                "duration": 5,
                                "group_index": group_index,
                                "text": text  # 保存文案，用于字幕显示
                            })
                    else:
                        error_msg = result.get("error", "未知错误")
                        print(f"[ShooterAgent] 语音片段合成失败: 组{group_index}-{part_name}, {error_msg}")
                        errors.append(f"组{group_index}-{part_name}: {error_msg}")
                        voice_segments.append({
                            "part": part_name,
                            "audio_url": f"placeholder_audio_{group_index}_{part_name}.mp3",
                            "duration": 5,
                            "group_index": group_index,
                            "text": text  # 保存文案，用于字幕显示
                        })
                except Exception as e:
                    print(f"[ShooterAgent] 语音片段合成异常: 组{group_index}-{part_name}, {e}")
                    errors.append(f"组{group_index}-{part_name}: {str(e)}")
                    voice_segments.append({
                        "part": part_name,
                        "audio_url": f"placeholder_audio_{group_index}_{part_name}.mp3",
                        "duration": 5,
                        "group_index": group_index,
                        "text": text  # 保存文案，用于字幕显示
                    })

        state["voice_segments"] = voice_segments
        if errors:
            state["voice_errors"] = errors
        
        # 检查有效语音数量，如果全部失败则抛出异常
        valid_voices = [v for v in voice_segments if "placeholder" not in v.get("audio_url", "")]
        if len(valid_voices) == 0:
            raise Exception(f"语音合成全部失败，无法继续混剪。错误: {errors}")
        
        state["current_step"] = "voice_synthesis_completed"
        print(f"[ShooterAgent] 混剪模式语音合成完成：{len(voice_segments)}段语音，有效: {len(valid_voices)}段")
        print(f"[ShooterAgent] 结束时间: {time.strftime('%Y-%m-%d %H:%M:%S')}")
        return state

    async def _upload_audio_to_oss(self, audio_url: str, filename: str) -> Dict[str, Any]:
        """
        下载音频并上传到OSS
        
        Args:
            audio_url: 临时音频URL
            filename: 目标文件名
            
        Returns:
            {"success": True/False, "url": "...", "message": "..."}
        """
        try:
            print(f"[ShooterAgent] 下载音频: {audio_url[:60]}...")
            response = requests.get(audio_url, timeout=60)
            response.raise_for_status()
            
            print(f"[ShooterAgent] 上传音频到OSS: {filename}")
            oss_result = self.oss.upload_content(
                user_id=str(self.user_id),
                content=response.content,
                file_type="audio",
                filename=filename,
                category="generated"
            )
            
            return oss_result
            
        except Exception as e:
            print(f"[ShooterAgent] 音频上传OSS异常: {e}")
            import traceback
            traceback.print_exc()
            return {
                "success": False,
                "message": f"上传失败: {str(e)}"
            }

    async def _verify_oss_file(self, file_url: str, max_retries: int = 3) -> Dict[str, Any]:
        """
        验证OSS文件是否可访问
        
        Args:
            file_url: 文件URL
            max_retries: 最大重试次数
            
        Returns:
            {"success": True/False, "message": "..."}
        """
        import time
        
        for attempt in range(max_retries):
            try:
                print(f"[ShooterAgent] 验证文件可访问性 (尝试{attempt+1}/{max_retries}): {file_url[:80]}...")
                response = requests.head(file_url, timeout=10)
                
                if response.status_code == 200:
                    content_length = response.headers.get('Content-Length', 'unknown')
                    print(f"[ShooterAgent] ✓ 文件验证成功，大小: {content_length} bytes")
                    return {
                        "success": True,
                        "message": f"文件可访问，大小: {content_length} bytes"
                    }
                else:
                    print(f"[ShooterAgent] ✗ 文件验证失败，状态码: {response.status_code}")
                    if attempt < max_retries - 1:
                        wait_time = 2 ** attempt  # 指数退避
                        print(f"[ShooterAgent] 等待{wait_time}秒后重试...")
                        time.sleep(wait_time)
                    else:
                        return {
                            "success": False,
                            "message": f"文件不可访问，状态码: {response.status_code}"
                        }
            except Exception as e:
                print(f"[ShooterAgent] ✗ 文件验证异常: {e}")
                if attempt < max_retries - 1:
                    wait_time = 2 ** attempt
                    print(f"[ShooterAgent] 等待{wait_time}秒后重试...")
                    time.sleep(wait_time)
                else:
                    return {
                        "success": False,
                        "message": f"验证异常: {str(e)}"
                    }
        
        return {
            "success": False,
            "message": "验证失败，已耗尽重试次数"
        }

    async def _upload_video_to_oss(self, video_url: str, filename: str) -> Dict[str, Any]:
        """
        下载视频并上传到OSS
        
        Args:
            video_url: 临时视频URL
            filename: 目标文件名
            
        Returns:
            {"success": True/False, "url": "...", "message": "..."}
        """
        try:
            print(f"[ShooterAgent] 下载视频: {video_url[:60]}...")
            response = requests.get(video_url, timeout=120)
            response.raise_for_status()
            
            print(f"[ShooterAgent] 上传视频到OSS: {filename}, 大小: {len(response.content)} bytes")
            oss_result = self.oss.upload_content(
                user_id=str(self.user_id),
                content=response.content,
                file_type="video",
                filename=filename,
                category="generated"
            )
            
            return oss_result
            
        except Exception as e:
            print(f"[ShooterAgent] 视频上传OSS异常: {e}")
            import traceback
            traceback.print_exc()
            return {
                "success": False,
                "message": f"上传失败: {str(e)}"
            }

    async def generate_avatar_videos(self, state: WorkflowState) -> WorkflowState:
        """
        生成数字人视频（对口型）
        支持普通模式和混剪模式
        """
        task_mode = state.get("task_mode", "normal")
        
        if task_mode == "mixcut":
            return await self._generate_segmented_avatars(state)
        else:
            return await self._generate_normal_avatars(state)
    
    async def _generate_normal_avatars(self, state: WorkflowState) -> WorkflowState:
        """普通模式：为完整语音生成数字人视频"""
        voices = state["voices"]
        avatar_videos: List[AvatarVideoInfo] = []

        # 如果没有设置模板视频，使用占位符
        if not self.avatar_video_url:
            for i, voice in enumerate(voices):
                avatar_videos.append({
                    "video_url": f"placeholder_avatar_{i}.mp4",
                    "duration": voice.get("duration", 10),
                })
            state["avatar_videos"] = avatar_videos
            state["current_step"] = "avatar_generation_completed"
            return state

        # 使用 VideoRetalk 生成对口型视频
        for i, voice in enumerate(voices):
            try:
                result = self.videoretalk.generate_avatar_video(
                    video_url=self.avatar_video_url,
                    audio_url=voice["audio_url"],
                    wait=True
                )

                if result.get("success"):
                    # 下载视频并上传到OSS
                    temp_video_url = result["video_url"]
                    oss_result = await self._upload_video_to_oss(temp_video_url, f"avatar_{i}.mp4")
                    
                    if oss_result.get("success"):
                        avatar_videos.append({
                            "video_url": oss_result["url"],
                            "duration": result.get("duration", voice.get("duration", 10)),
                        })
                        print(f"[ShooterAgent] 数字人视频生成并上传成功: {oss_result['url']}")
                    else:
                        error_msg = f"上传OSS失败: {oss_result.get('message')}"
                        print(f"[ShooterAgent] {error_msg}")
                        avatar_videos.append({
                            "video_url": f"placeholder_avatar_{i}.mp4",
                            "duration": voice.get("duration", 10),
                        })
                else:
                    print(f"[ShooterAgent] 数字人视频生成失败: {result.get('error')}")
                    avatar_videos.append({
                        "video_url": f"placeholder_avatar_{i}.mp4",
                        "duration": voice.get("duration", 10),
                    })
            except Exception as e:
                print(f"[ShooterAgent] 数字人视频生成异常: {e}")
                avatar_videos.append({
                    "video_url": f"placeholder_avatar_{i}.mp4",
                    "duration": voice.get("duration", 10),
                })

        state["avatar_videos"] = avatar_videos
        state["current_step"] = "avatar_generation_completed"
        return state
    
    async def _generate_segmented_avatars(self, state: WorkflowState) -> WorkflowState:
        """
        混剪模式：为分段语音生成数字人视频
        只需要生成开头和结尾的数字人（钩子/内容使用图片）
        使用并发提交+并发轮询，提高效率
        所有视频生成完成后再返回
        """
        import time
        from concurrent.futures import ThreadPoolExecutor, as_completed
        
        voice_segments = state.get("voice_segments", [])
        avatar_segments: List[Dict[str, Any]] = []
        
        # 统计信息
        stats = {
            "total": 0,
            "skipped_placeholder": 0,
            "submit_success": 0,
            "submit_failed": 0,
            "completed": 0,
            "failed": 0,
            "timeout": 0,
            "upload_failed": 0
        }
        
        print(f"\n{'='*80}")
        print(f"[ShooterAgent] 数字人视频生成开始")
        print(f"[ShooterAgent] 开始时间: {time.strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"{'='*80}\n")
        
        # 如果没有设置模板视频，使用占位符
        if not self.avatar_video_url:
            print(f"[ShooterAgent] [FAIL] 错误: 未设置数字人模板")
            for seg in voice_segments:
                part = seg.get("part")
                if part in ["opening", "ending"]:
                    avatar_segments.append({
                        "part": part,
                        "video_url": f"placeholder_avatar_{seg['group_index']}_{part}.mp4",
                        "duration": seg.get("duration", 5),
                        "group_index": seg.get("group_index", 0),
                        "status": "failed",
                        "error": "未设置数字人模板"
                    })
                    stats["failed"] += 1
            state["avatar_segments"] = avatar_segments
            state["avatar_generation_stats"] = stats
            state["current_step"] = "avatar_generation_completed"
            return state
        
        # 按组和部位生成数字人视频
        segments_to_process = []
        for seg in voice_segments:
            part = seg.get("part")
            if part in ["opening", "ending"]:
                segments_to_process.append(seg)
        
        stats["total"] = len(segments_to_process)
        print(f"[ShooterAgent] 需要生成 {stats['total']} 个数字人视频")
        print(f"[ShooterAgent] 数字人模板: {self.avatar_video_url[:80]}...")
        print()
        
        # 检查每个语音片段的状态
        print(f"[ShooterAgent] 语音片段检查:")
        for seg in segments_to_process:
            group_index = seg.get("group_index", 0)
            part = seg.get("part", "unknown")
            audio_url = seg.get("audio_url", "")
            is_placeholder = "placeholder" in audio_url
            print(f"  组{group_index}-{part}: {'[FAIL] placeholder' if is_placeholder else '[OK] 有效URL'} ({audio_url[:50]}...)")
        print()
        
        # 第一步：提交所有任务（限制并发数为2，避免429限流）
        print(f"[ShooterAgent] 第一步：提交任务到VideoRetalk...")
        tasks = []
        
        def submit_single_task(seg, retry_count=0, max_retries=3):
            """提交单个任务（带重试机制）"""
            part = seg.get("part")
            group_index = seg.get("group_index", 0)
            audio_url = seg.get("audio_url", "")
            
            # 检查是否是占位符
            if "placeholder" in audio_url:
                print(f"[ShooterAgent]   组{group_index}-{part}: [SKIP] 跳过（placeholder音频）")
                return {
                    "task_id": None,
                    "part": part,
                    "group_index": group_index,
                    "is_placeholder": True,
                    "error": "placeholder音频"
                }
            
            try:
                result = self.videoretalk.submit_task(
                    video_url=self.avatar_video_url,
                    audio_url=audio_url
                )
                
                if result.get("success"):
                    task_id = result.get("task_id")
                    print(f"[ShooterAgent]   组{group_index}-{part}: [OK] 提交成功 (task_id={task_id[:20]}...)")
                    return {
                        "task_id": task_id,
                        "part": part,
                        "group_index": group_index,
                        "is_placeholder": False
                    }
                else:
                    error_msg = result.get("error", "未知错误")
                    
                    # 如果是429限流错误，尝试重试
                    if "429" in error_msg and retry_count < max_retries:
                        wait_time = (retry_count + 1) * 2  # 递增等待时间
                        print(f"[ShooterAgent]   组{group_index}-{part}: [WARN] 限流(429)，{wait_time}秒后重试 ({retry_count+1}/{max_retries})")
                        import time
                        time.sleep(wait_time)
                        return submit_single_task(seg, retry_count + 1, max_retries)
                    
                    print(f"[ShooterAgent]   组{group_index}-{part}: [FAIL] 提交失败 ({error_msg})")
                    return {
                        "task_id": None,
                        "part": part,
                        "group_index": group_index,
                        "is_placeholder": True,
                        "error": f"提交失败: {error_msg}"
                    }
            except Exception as e:
                error_str = str(e)
                
                # 如果是429限流错误，尝试重试
                if "429" in error_str and retry_count < max_retries:
                    wait_time = (retry_count + 1) * 2
                    print(f"[ShooterAgent]   组{group_index}-{part}: [WARN] 限流(429)异常，{wait_time}秒后重试 ({retry_count+1}/{max_retries})")
                    import time
                    time.sleep(wait_time)
                    return submit_single_task(seg, retry_count + 1, max_retries)
                
                print(f"[ShooterAgent]   组{group_index}-{part}: [FAIL] 提交异常 ({error_str})")
                return {
                    "task_id": None,
                    "part": part,
                    "group_index": group_index,
                    "is_placeholder": True,
                    "error": f"提交异常: {error_str}"
                }
        
        # 串行提交任务（避免并发问题）
        print(f"[ShooterAgent] 串行提交任务（非并发模式）")
        
        for seg in segments_to_process:
            result = submit_single_task(seg)
            tasks.append(result)
            if result.get("is_placeholder"):
                if "placeholder" in result.get("error", ""):
                    stats["skipped_placeholder"] += 1
                else:
                    stats["submit_failed"] += 1
            else:
                stats["submit_success"] += 1
            # 任务间添加小延迟，避免触发限流
            import time
            time.sleep(1.0)
        
        print(f"\n[ShooterAgent] 任务提交统计:")
        print(f"  总任务数: {stats['total']}")
        print(f"  跳过(placeholder): {stats['skipped_placeholder']}")
        print(f"  提交成功: {stats['submit_success']}")
        print(f"  提交失败: {stats['submit_failed']}")
        print()
        
        # 第二步：并发轮询等待所有任务完成
        pending_task_count = len([t for t in tasks if not t.get("is_placeholder") and t.get("task_id")])
        print(f"[ShooterAgent] 第二步：等待 {pending_task_count} 个任务完成...")
        
        max_wait = 300
        poll_interval = 3
        elapsed = 0
        completed_tasks = {}
        failed_tasks = {}
        
        def query_single_task(task):
            """查询单个任务状态"""
            task_id = task.get("task_id")
            if not task_id:
                return None
            
            try:
                result = self.videoretalk.query_task(task_id)
                if result.get("success"):
                    status = result.get("status")
                    if status in ["SUCCEEDED", "FAILED"]:
                        return {
                            "task_id": task_id,
                            "task": task,
                            "result": result,
                            "status": status
                        }
                return None
            except Exception as e:
                print(f"[ShooterAgent]   查询任务异常: {task_id[:20]}... ({str(e)})")
                return None
        
        while elapsed < max_wait:
            # 获取待处理的任务
            pending_tasks = [t for t in tasks if t.get("task_id") 
                           and t["task_id"] not in completed_tasks 
                           and t["task_id"] not in failed_tasks]
            
            if not pending_tasks:
                print(f"[ShooterAgent] 所有任务已完成")
                break
            
            print(f"[ShooterAgent]   轮询中... 已完成: {len(completed_tasks)}, 失败: {len(failed_tasks)}, 待处理: {len(pending_tasks)}, 已等待: {elapsed}秒")
            
            # 串行查询所有待处理任务（非并发模式）
            for task in pending_tasks:
                query_result = query_single_task(task)
                if query_result:
                    task_id = query_result["task_id"]
                    task_info = query_result["task"]
                    result = query_result["result"]
                    status = query_result["status"]
                    
                    part = task_info["part"]
                    group_index = task_info["group_index"]
                    
                    if status == "SUCCEEDED":
                        video_url = result.get("video_url", "")
                        print(f"[ShooterAgent]   组{group_index}-{part}: [OK] VideoRetalk生成成功")
                        
                        # 下载并上传到OSS
                        oss_result = await self._upload_video_to_oss(video_url, f"avatar_{group_index}_{part}.mp4")
                        
                        if oss_result.get("success"):
                            completed_tasks[task_id] = {
                                "part": part,
                                "group_index": group_index,
                                "video_url": oss_result["url"],
                                "duration": result.get("video_duration", 5)
                            }
                            print(f"[ShooterAgent]   组{group_index}-{part}: [OK] OSS上传成功")
                        else:
                            print(f"[ShooterAgent]   组{group_index}-{part}: [FAIL] OSS上传失败 ({oss_result.get('message')})")
                            failed_tasks[task_id] = {
                                "part": part,
                                "group_index": group_index,
                                "error": f"OSS上传失败: {oss_result.get('message')}"
                            }
                            stats["upload_failed"] += 1
                            
                    elif status == "FAILED":
                        error_msg = result.get("error", "任务失败")
                        print(f"[ShooterAgent]   组{group_index}-{part}: [FAIL] VideoRetalk失败 ({error_msg})")
                        failed_tasks[task_id] = {
                            "part": part,
                            "group_index": group_index,
                            "error": error_msg
                        }
            
            # 如果还有未完成的任务，等待后继续轮询
            pending_tasks = [t for t in tasks if t.get("task_id") 
                           and t["task_id"] not in completed_tasks 
                           and t["task_id"] not in failed_tasks]
            if pending_tasks:
                await asyncio.sleep(poll_interval)
                elapsed += poll_interval
        
        # 处理超时任务
        for task in tasks:
            if task.get("task_id") and task["task_id"] not in completed_tasks and task["task_id"] not in failed_tasks:
                stats["timeout"] += 1
        
        # 第三步：整理结果
        print(f"\n[ShooterAgent] 第三步：整理结果...")
        for task in tasks:
            part = task["part"]
            group_index = task["group_index"]
            
            if task.get("is_placeholder"):
                avatar_segments.append({
                    "part": part,
                    "video_url": f"placeholder_avatar_{group_index}_{part}.mp4",
                    "duration": 5,
                    "group_index": group_index,
                    "status": "placeholder",
                    "error": task.get("error", "placeholder")
                })
            elif task["task_id"] in completed_tasks:
                completed = completed_tasks[task["task_id"]]
                avatar_segments.append({
                    "part": part,
                    "video_url": completed["video_url"],
                    "duration": completed["duration"],
                    "group_index": group_index,
                    "status": "completed"
                })
                stats["completed"] += 1
            else:
                error_msg = "超时"
                if task["task_id"] in failed_tasks:
                    error_msg = failed_tasks[task["task_id"]].get("error", "失败")
                avatar_segments.append({
                    "part": part,
                    "video_url": f"placeholder_avatar_{group_index}_{part}.mp4",
                    "duration": 5,
                    "group_index": group_index,
                    "status": "failed",
                    "error": error_msg
                })
                stats["failed"] += 1
        
        avatar_segments.sort(key=lambda x: (x["group_index"], x["part"]))
        
        state["avatar_segments"] = avatar_segments
        state["avatar_generation_stats"] = stats
        state["current_step"] = "avatar_generation_completed"
        
        # 打印最终统计
        print(f"\n{'='*80}")
        print(f"[ShooterAgent] 数字人视频生成完成")
        print(f"[ShooterAgent] 结束时间: {time.strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"{'='*80}")
        print(f"统计信息:")
        print(f"  总任务数: {stats['total']}")
        print(f"  [OK] 成功: {stats['completed']}")
        print(f"  [FAIL] 失败: {stats['failed']}")
        print(f"  [TIMEOUT] 超时: {stats['timeout']}")
        print(f"  [SKIP] 跳过(placeholder): {stats['skipped_placeholder']}")
        print(f"  [FAIL] 上传失败: {stats['upload_failed']}")
        print(f"  [FAIL] 提交失败: {stats['submit_failed']}")
        print(f"{'='*80}\n")
        
        # 打印每个片段的详情
        print(f"[ShooterAgent] 生成详情:")
        for seg in avatar_segments:
            status_icon = "[OK]" if seg["status"] == "completed" else "[FAIL]" if seg["status"] == "failed" else "[SKIP]"
            print(f"  {status_icon} 组{seg['group_index']}-{seg['part']}: {seg['status']}")
            if seg.get("error"):
                print(f"      错误: {seg['error']}")
        print()
        
        return state

    def build_graph(self) -> StateGraph:
        """构建拍 Agent 的子图"""
        workflow = StateGraph(WorkflowState)

        workflow.add_node("synthesize_voices", self.synthesize_voices)
        workflow.add_node("generate_avatar_videos", self.generate_avatar_videos)

        workflow.edge("synthesize_voices", "generate_avatar_videos")

        workflow.set_entry_point("synthesize_voices")
        workflow.set_finish_point("generate_avatar_videos")

        return workflow.compile()
