"""
阿里云OSS工具类
用于视频合成后上传到OSS，获取公网URL
"""
import oss2
import os
from datetime import datetime, timedelta
from typing import Optional
import logging

logger = logging.getLogger(__name__)


class OSSClient:
    """阿里云OSS客户端"""
    
    def __init__(self):
        # 从环境变量读取配置（生产环境推荐）
        # 或从config.py读取（开发环境）
        try:
            from config import OSS_CONFIG
            
            self.access_key_id = OSS_CONFIG.get('access_key_id', '')
            self.access_key_secret = OSS_CONFIG.get('access_key_secret', '')
            self.endpoint = OSS_CONFIG.get('endpoint', '')
            self.bucket_name = OSS_CONFIG.get('bucket_name', '')
            self.cdn_domain = OSS_CONFIG.get('cdn_domain', '')  # 可选CDN加速域名
            
            if not all([self.access_key_id, self.access_key_secret, self.endpoint, self.bucket_name]):
                logger.warning("OSS配置不完整，将使用本地存储模式")
                self.enabled = False
            else:
                self.enabled = True
                self.auth = oss2.Auth(self.access_key_id, self.access_key_secret)
                self.bucket = oss2.Bucket(self.auth, self.endpoint, self.bucket_name)
                logger.info(f"OSS客户端初始化成功: {self.bucket_name}")
        except Exception as e:
            logger.error(f"OSS客户端初始化失败: {e}")
            self.enabled = False
    
    def upload_render(self, local_path: str, render_id: str, user_id: str = None, user_obj=None) -> Optional[str]:
        """
        上传混剪结果到OSS（同步上传）
        
        Args:
            local_path: 本地文件路径
            render_id: 渲染ID（用于生成OSS路径）
            user_id: 用户ID（用于划分用户目录）
            user_obj: User模型对象（用于判断匿名用户）
        
        Returns:
            OSS URL 或 None（上传失败时）
        """
        if not self.enabled:
            print("[OSS] OSS未启用，跳过上传")
            return None
        
        if not os.path.exists(local_path):
            print(f"[OSS] 本地文件不存在: {local_path}")
            return None
        
        try:
            # 从render_id解析user_id（如果未传入）
            # render_id格式: combo_{user_id}_{index}
            if not user_id and render_id.startswith('combo_'):
                parts = render_id.split('_')
                if len(parts) >= 2:
                    user_id = parts[1]
            
            # 生成OSS路径
            # 注册用户: users/{user_id}/renders/2024/01/15/render_xxx.mp4
            # 匿名用户: users/anonymous/{user_id}/renders/2024/01/15/render_xxx.mp4
            date_str = datetime.now().strftime('%Y/%m/%d')
            filename = os.path.basename(local_path)
            
            if user_id:
                # 判断是否为匿名用户
                if self._is_anonymous_user(user_id, user_obj):
                    oss_key = f"users/anonymous/{user_id}/renders/{date_str}/{filename}"
                else:
                    oss_key = f"users/{user_id}/renders/{date_str}/{filename}"
            else:
                # 回退到旧路径（兼容）
                oss_key = f"renders/{date_str}/{filename}"
            
            # 上传文件
            print(f"[OSS] 开始上传 {local_path} 到 OSS/{oss_key}")
            self.bucket.put_object_from_file(oss_key, local_path)
            
            # 获取URL（使用CDN域名如果配置了）
            if self.cdn_domain:
                url = f"https://{self.cdn_domain}/{oss_key}"
            else:
                url = f"https://{self.bucket_name}.{self.endpoint}/{oss_key}"
            
            print(f"[OSS] 上传成功: {url}")
            return url
            
        except Exception as e:
            print(f"[OSS] 上传到OSS失败: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    def upload_render_async(self, local_path: str, render_id: str, user_id: str = None, user_obj=None, callback=None):
        """
        异步上传混剪结果到OSS（后台线程，不阻塞主流程）
        
        Args:
            local_path: 本地文件路径
            render_id: 渲染ID
            user_id: 用户ID
            user_obj: User模型对象
            callback: 上传完成后的回调函数，参数为(oss_url, success)
        
        Returns:
            thread: 上传线程对象
        """
        import threading
        
        def _upload_task():
            try:
                print(f"[ASYNC] 开始异步上传: {local_path}")
                oss_url = self.upload_render(local_path, render_id, user_id, user_obj)
                
                if oss_url:
                    print(f"[ASYNC] 异步上传成功: {oss_url}")
                    if callback:
                        callback(oss_url, True)
                else:
                    print(f"[ASYNC] 异步上传失败: {local_path}")
                    if callback:
                        callback(None, False)
                        
            except Exception as e:
                print(f"[ASYNC] 异步上传异常: {e}")
                import traceback
                traceback.print_exc()
                if callback:
                    callback(None, False)
        
        # 启动后台线程
        thread = threading.Thread(target=_upload_task, daemon=True)
        thread.start()
        print(f"[ASYNC] 已启动异步上传线程: {render_id}")
        
        return thread
    
    def _is_anonymous_user(self, user_id: str, user_obj=None) -> bool:
        """
        判断是否为匿名用户
        
        匿名用户特征（按优先级）：
        1. user_obj.anonymous == True（数据库字段，最准确）
        2. 包含'anon'前缀
        
        Args:
            user_id: 用户ID
            user_obj: User模型对象（可选，用于获取anonymous字段）
            
        Returns:
            bool: 是否为匿名用户
        """
        if not user_id:
            return False
        
        # 优先使用数据库字段判断（最准确）
        if user_obj is not None:
            return getattr(user_obj, 'anonymous', False) or False
        
        # 包含anon前缀（备用判断）
        if 'anon' in user_id.lower():
            return True
        
        return False
    
    def delete_render(self, oss_url: str) -> bool:
        """
        根据URL删除OSS文件
        
        Args:
            oss_url: 完整的OSS URL
            
        Returns:
            bool: 是否删除成功
        """
        if not self.enabled:
            logger.info("OSS未启用，跳过删除")
            return False
        
        try:
            # 解析URL获取OSS key
            oss_key = self._extract_key_from_url(oss_url)
            if not oss_key:
                logger.error(f"无法从URL解析OSS key: {oss_url}")
                return False
            
            # 删除文件
            self.bucket.delete_object(oss_key)
            logger.info(f"已删除OSS文件: {oss_key}")
            return True
            
        except Exception as e:
            logger.error(f"删除OSS文件失败: {e}")
            return False
    
    def _extract_key_from_url(self, oss_url: str) -> Optional[str]:
        """从OSS URL中提取key"""
        try:
            from urllib.parse import urlparse
            
            parsed = urlparse(oss_url)
            path = parsed.path
            
            # 移除开头的/
            if path.startswith('/'):
                path = path[1:]
            
            return path
            
        except Exception as e:
            logger.error(f"解析OSS URL失败: {e}")
            return None
    
    def get_signed_url(self, oss_key: str, expiration: int = 3600) -> Optional[str]:
        """
        获取签名URL（用于私有bucket）
        
        Args:
            oss_key: OSS文件路径
            expiration: 过期时间（秒）
        
        Returns:
            签名URL
        """
        if not self.enabled:
            return None
        
        try:
            url = self.bucket.sign_url('GET', oss_key, expiration)
            return url
        except Exception as e:
            logger.error(f"生成签名URL失败: {e}")
            return None
    
    def check_object_exists(self, oss_key: str) -> bool:
        """检查OSS文件是否存在"""
        if not self.enabled:
            return False
        
        try:
            exists = self.bucket.object_exists(oss_key)
            return exists
        except Exception as e:
            logger.error(f"检查OSS文件存在性失败: {e}")
            return False
    
    def refresh_cdn_cache(self, oss_url: str) -> bool:
        """
        刷新CDN缓存（如果配置了CDN）
        
        Args:
            oss_url: 需要刷新的URL
            
        Returns:
            bool: 是否成功提交刷新任务
        """
        if not self.enabled or not self.cdn_domain:
            return False
        
        try:
            # 这里可以集成阿里云CDN刷新API
            # 需要额外的CDN AccessKey
            logger.info(f"[CDN] 刷新缓存: {oss_url}")
            return True
        except Exception as e:
            logger.error(f"[CDN] 刷新缓存失败: {e}")
            return False
    
    def get_optimized_url(self, oss_url: str, width: int = None, height: int = None) -> str:
        """
        获取优化后的URL（支持图片/视频处理参数）
        
        Args:
            oss_url: 原始OSS URL
            width: 目标宽度（可选）
            height: 目标高度（可选）
            
        Returns:
            优化后的URL
        """
        if not oss_url:
            return oss_url
        
        # 如果是图片，可以添加OSS图片处理参数
        if any(oss_url.endswith(ext) for ext in ['.jpg', '.jpeg', '.png', '.webp']):
            params = []
            if width:
                params.append(f"w_{width}")
            if height:
                params.append(f"h_{height}")
            
            if params:
                separator = '&' if '?' in oss_url else '?'
                return f"{oss_url}{separator}x-oss-process=image/resize,{','.join(params)}"
        
        return oss_url


# 全局OSS客户端实例
oss_client = OSSClient()
