"""
数字人视频生成 API - 使用阿里云 VideoRetalk
"""

from fastapi import APIRouter, HTTPException, Query, Form
from pydantic import BaseModel
from typing import Optional
import os
import re

from app.tools.videoretalk import VideoRetalkTool
from app.tools.oss_simple import OSSSimpleTool

router = APIRouter()

# 初始化工具
videoretalk_tool = VideoRetalkTool()
oss_tool = OSSSimpleTool()


class AvatarGenerateRequest(BaseModel):
    video_object_key: str
    audio_object_key: str
    ref_image_object_key: Optional[str] = None
    video_extension: bool = False


@router.post("/generate")
async def generate_avatar_video(
    video_object_key: str = Form(..., description="模板视频的OSS对象键"),
    audio_object_key: str = Form(..., description="驱动音频的OSS对象键"),
    ref_image_object_key: Optional[str] = Form(None, description="参考图片的OSS对象键（可选）"),
    video_extension: bool = Form(False, description="是否扩展视频时长"),
    user_id: Optional[int] = Query(1)
):
    """
    提交数字人视频生成任务
    """
    print(f"[Avatar] 提交数字人视频生成任务: user_id={user_id}")
    print(f"[Avatar] 视频: {video_object_key}")
    print(f"[Avatar] 音频: {audio_object_key}")
    
    try:
        # 使用公共访问URL（不带签名）
        # 如果Bucket设置了公共读取权限，可以直接访问
        video_url = f"{oss_tool.base_url}/{video_object_key}"
        audio_url = f"{oss_tool.base_url}/{audio_object_key}"
        
        ref_image_url = None
        if ref_image_object_key:
            ref_image_url = f"{oss_tool.base_url}/{ref_image_object_key}"
        
        print(f"[Avatar] 视频URL: {video_url[:80]}...")
        print(f"[Avatar] 音频URL: {audio_url[:80]}...")
        
        # 提交任务到VideoRetalk
        result = videoretalk_tool.submit_task(
            video_url=video_url,
            audio_url=audio_url,
            ref_image_url=ref_image_url,
            video_extension=video_extension
        )
        
        print(f"[Avatar] 任务提交结果: {result}")
        
        if not result.get("success"):
            error_msg = result.get("error", "提交任务失败")
            print(f"[Avatar] 提交失败: {error_msg}")
            raise HTTPException(status_code=500, detail=error_msg)
        
        return {
            "success": True,
            "task_id": result.get("task_id"),
            "task_status": result.get("task_status"),
            "request_id": result.get("request_id"),
            "message": "任务已提交，正在生成数字人视频"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"[Avatar] 提交任务异常: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"提交任务失败: {str(e)}")


@router.get("/tasks/{task_id}")
async def query_avatar_task(
    task_id: str,
    user_id: Optional[int] = Query(1),
    audio_name: Optional[str] = Query(None, description="音频名称，用于生成视频文件名")
):
    """
    查询数字人视频生成任务状态
    """
    print(f"[Avatar] 查询任务状态: task_id={task_id}, user_id={user_id}, audio_name={audio_name}")
    
    try:
        result = videoretalk_tool.query_task(task_id)
        
        print(f"[Avatar] 任务状态: {result.get('status')}")
        
        if not result.get("success"):
            error_msg = result.get("error", "查询任务失败")
            raise HTTPException(status_code=500, detail=error_msg)
        
        # 如果任务成功完成，将视频上传到OSS
        if result.get("status") == "SUCCEEDED" and result.get("video_url"):
            video_url = result.get("video_url")
            video_duration = result.get("video_duration", 0)
            cost = result.get("cost", 0)
            
            print(f"[Avatar] 任务完成，开始下载视频: {video_url}")
            
            # 下载视频到本地临时文件
            try:
                import requests
                response = requests.get(video_url, timeout=300)
                response.raise_for_status()
                video_content = response.content
                
                # 使用音频名称作为视频文件名，如果没有音频名称则使用task_id
                if audio_name:
                    # 清理文件名，只保留安全字符
                    safe_filename = re.sub(r'[^\w\u4e00-\u9fff.-]', '_', audio_name)
                    safe_filename = safe_filename[:50]  # 限制长度
                    output_filename = f"{safe_filename}.mp4"
                else:
                    output_filename = f"avatar_{task_id}.mp4"
                
                # 保存到本地临时文件
                local_temp_path = os.path.join(os.path.dirname(__file__), '..', '..', '..', 'tmp', output_filename)
                os.makedirs(os.path.dirname(local_temp_path), exist_ok=True)
                
                with open(local_temp_path, 'wb') as f:
                    f.write(video_content)
                
                print(f"[Avatar] 视频下载完成，大小: {len(video_content)} bytes")
                
                # 上传到OSS: users/{user_id}/generated/video/
                upload_result = oss_tool.upload_file(
                    user_id=str(user_id),
                    local_file_path=local_temp_path,
                    file_type="video",
                    category="generated"
                )
                
                if upload_result.get("success"):
                    object_key = upload_result.get("object_key")
                    # 使用公共访问URL（不带签名）
                    public_url = f"{oss_tool.base_url}/{object_key}"
                    print(f"[Avatar] 视频上传成功: {object_key}")
                    print(f"[Avatar] 公共访问URL: {public_url}")
                    
                    # 删除本地临时文件
                    try:
                        os.remove(local_temp_path)
                        print(f"[Avatar] 删除本地临时文件: {local_temp_path}")
                    except Exception as e:
                        print(f"[Avatar] 删除本地文件失败: {e}")
                    
                    # 更新结果
                    result["object_key"] = object_key
                    result["signed_url"] = public_url
                else:
                    print(f"[Avatar] 上传到OSS失败: {upload_result.get('message')}")
                    # 仍然返回原始URL
                    result["signed_url"] = video_url
            except Exception as e:
                print(f"[Avatar] 下载并上传视频失败: {e}")
                import traceback
                traceback.print_exc()
        
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"[Avatar] 查询任务异常: {e}")
        raise HTTPException(status_code=500, detail=f"查询任务失败: {str(e)}")
