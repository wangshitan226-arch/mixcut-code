"""
Pexels API 客户端
用于搜索和下载视频素材
"""
import os
import requests
import logging
from typing import List, Dict, Optional
from utils.oss import oss_client

logger = logging.getLogger(__name__)

# Pexels API 配置
PEXELS_API_KEY = os.environ.get('PEXELS_API_KEY', 'J9ccbksVBkWZUfz4WZB2Xav3xh2Hb6Tk6JRVxdWvKTkfX3DZtXTyXitE')
PEXELS_API_URL = 'https://api.pexels.com/videos/search'


def search_videos(query: str, per_page: int = 1) -> List[Dict]:
    """
    搜索 Pexels 视频素材
    
    Args:
        query: 搜索关键词
        per_page: 返回结果数量
    
    Returns:
        视频列表，每个视频包含 url, width, height, duration 等信息
    """
    if not PEXELS_API_KEY:
        logger.error("Pexels API Key 未配置")
        return []
    
    headers = {
        'Authorization': PEXELS_API_KEY
    }
    
    params = {
        'query': query,
        'per_page': per_page,
        'orientation': 'portrait'  # 竖屏视频
    }
    
    try:
        response = requests.get(PEXELS_API_URL, headers=headers, params=params, timeout=30)
        response.raise_for_status()
        data = response.json()
        
        videos = []
        for video in data.get('videos', []):
            # 获取最高质量的视频文件
            video_files = sorted(video.get('video_files', []), 
                               key=lambda x: x.get('width', 0) * x.get('height', 0), 
                               reverse=True)
            
            if video_files:
                best_file = video_files[0]
                videos.append({
                    'id': video.get('id'),
                    'url': best_file.get('link'),
                    'width': best_file.get('width'),
                    'height': best_file.get('height'),
                    'duration': video.get('duration'),
                    'user': video.get('user', {}).get('name')
                })
        
        logger.info(f"Pexels 搜索 '{query}' 找到 {len(videos)} 个视频")
        return videos
        
    except Exception as e:
        logger.error(f"Pexels 搜索失败: {e}")
        return []


def download_and_upload_to_oss(video_url: str, keyword: str, user_id: str) -> Optional[str]:
    """
    下载 Pexels 视频并上传到 OSS
    
    Args:
        video_url: Pexels 视频 URL
        keyword: 关键词（用于生成文件名）
        user_id: 用户ID
    
    Returns:
        OSS URL，失败返回 None
    """
    try:
        # 下载视频
        logger.info(f"下载 Pexels 视频: {video_url[:80]}...")
        response = requests.get(video_url, timeout=120, stream=True)
        response.raise_for_status()
        
        # 读取内容
        video_content = response.content
        logger.info(f"下载完成: {len(video_content)} bytes")
        
        # 生成 OSS 路径
        import time
        timestamp = int(time.time())
        oss_path = f'pexels/{user_id}/{keyword}_{timestamp}.mp4'
        
        # 上传到 OSS
        oss_client.bucket.put_object(oss_path, video_content)
        
        # 生成 URL
        if oss_client.cdn_domain:
            oss_url = f"https://{oss_client.cdn_domain}/{oss_path}"
        else:
            oss_url = f"https://{oss_client.bucket_name}.{oss_client.endpoint}/{oss_path}"
        
        logger.info(f"上传 OSS 成功: {oss_url[:80]}...")
        return oss_url
        
    except Exception as e:
        logger.error(f"下载或上传失败: {e}")
        return None


def get_videos_for_keywords(keywords: List[Dict], user_id: str) -> List[Dict]:
    """
    为多个关键词获取视频素材
    
    Args:
        keywords: 关键词列表，每个包含 keyword, sentence_id, beginTime, endTime
        user_id: 用户ID
    
    Returns:
        视频配置列表，每个包含 url, beginTime, endTime
    """
    videos = []
    
    for kw in keywords:
        keyword = kw.get('keyword')
        begin_time = kw.get('beginTime', 0)
        end_time = kw.get('endTime', 0)
        
        if not keyword:
            continue
        
        # 搜索视频
        search_results = search_videos(keyword, per_page=1)
        
        if search_results:
            video = search_results[0]
            
            # 下载并上传
            oss_url = download_and_upload_to_oss(video['url'], keyword, user_id)
            
            if oss_url:
                videos.append({
                    'url': oss_url,
                    'beginTime': begin_time,
                    'endTime': end_time,
                    'keyword': keyword
                })
    
    logger.info(f"成功获取 {len(videos)} 个 Pexels 视频")
    return videos
