"""
视频流媒体处理工具 - 支持HLS分片播放
用于优化服务器部署后的视频播放性能
"""
import os
import subprocess
import uuid
import shutil
from config import RENDERS_FOLDER


def create_hls_stream(input_path, output_dir, segment_duration=6, quality='medium'):
    """
    将视频转换为HLS流媒体格式（m3u8 + ts分片）
    
    Args:
        input_path: 输入视频路径
        output_dir: 输出目录
        segment_duration: 每个分片的时长（秒）
        quality: 质量等级
        
    Returns:
        m3u8文件的相对路径，失败返回None
    """
    if not os.path.exists(input_path):
        print(f"[HLS] 输入文件不存在: {input_path}")
        return None
    
    # 确保输出目录存在
    os.makedirs(output_dir, exist_ok=True)
    
    # 生成唯一的流名称
    stream_id = uuid.uuid4().hex[:12]
    m3u8_name = f"stream_{stream_id}.m3u8"
    m3u8_path = os.path.join(output_dir, m3u8_name)
    
    # 码率设置
    bitrate_settings = {
        'low': {'video': '800k', 'audio': '96k', 'scale': '720:1280'},
        'medium': {'video': '2000k', 'audio': '128k', 'scale': '1080:1920'},
        'high': {'video': '4000k', 'audio': '192k', 'scale': '1440:2560'},
    }
    settings = bitrate_settings.get(quality, bitrate_settings['medium'])
    
    try:
        # 使用ffmpeg生成HLS流
        cmd = [
            'ffmpeg', '-y',
            '-i', input_path,
            '-c:v', 'libx264',
            '-preset', 'veryfast',
            '-crf', '23',
            '-maxrate', settings['video'],
            '-bufsize', '2M',
            '-vf', f"scale={settings['scale']}:force_original_aspect_ratio=decrease,pad={settings['scale']}:(ow-iw)/2:(oh-ih)/2",
            '-c:a', 'aac',
            '-b:a', settings['audio'],
            '-ar', '44100',
            '-ac', '2',
            '-f', 'hls',
            '-hls_time', str(segment_duration),
            '-hls_list_size', '0',  # 保留所有分片
            '-hls_segment_filename', os.path.join(output_dir, f'stream_{stream_id}_%03d.ts'),
            '-hls_playlist_type', 'vod',  # VOD模式（非直播）
            m3u8_path
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        if result.returncode == 0 and os.path.exists(m3u8_path):
            print(f"[HLS] 生成成功: {m3u8_path}")
            return m3u8_name
        else:
            print(f"[HLS] 生成失败: {result.stderr}")
            return None
            
    except Exception as e:
        print(f"[HLS] 异常: {e}")
        return None


def get_video_stream_info(video_path):
    """获取视频流信息"""
    try:
        cmd = [
            'ffprobe', '-v', 'error',
            '-select_streams', 'v:0',
            '-show_entries', 'stream=bit_rate,duration,width,height',
            '-of', 'json',
            video_path
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode == 0:
            import json
            return json.loads(result.stdout)
        return None
    except Exception as e:
        print(f"[Stream] 获取视频信息失败: {e}")
        return None


def cleanup_old_streams(streams_dir, max_age_hours=24):
    """清理旧的HLS流文件"""
    if not os.path.exists(streams_dir):
        return
        
    import time
    current_time = time.time()
    max_age_seconds = max_age_hours * 3600
    
    for item in os.listdir(streams_dir):
        item_path = os.path.join(streams_dir, item)
        if os.path.isdir(item_path):
            # 检查目录修改时间
            mtime = os.path.getmtime(item_path)
            if current_time - mtime > max_age_seconds:
                shutil.rmtree(item_path)
                print(f"[HLS] 清理旧流: {item}")
