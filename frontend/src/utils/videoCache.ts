/**
 * 视频缓存管理工具 - 优化版
 * 支持智能预加载、分片缓存和播放优化
 */

const DB_NAME = 'MixCutVideoCache';
const DB_VERSION = 2;
const STORE_NAME = 'videos';
const METADATA_STORE = 'metadata';

// 最大缓存大小 (200MB)
const MAX_CACHE_SIZE = 200 * 1024 * 1024;
// 单个视频最大大小 (50MB)
const MAX_VIDEO_SIZE = 50 * 1024 * 1024;

interface VideoMetadata {
  id: string;
  size: number;
  timestamp: number;
  accessCount: number;
  lastAccessed: number;
  url: string;
}

let db: IDBDatabase | null = null;

/**
 * 初始化IndexedDB
 */
export async function initVideoDB(): Promise<IDBDatabase> {
  if (db) return db;

  return new Promise((resolve, reject) => {
    const request = indexedDB.open(DB_NAME, DB_VERSION);

    request.onerror = () => reject(request.error);
    request.onsuccess = () => {
      db = request.result;
      resolve(db);
    };

    request.onupgradeneeded = (event) => {
      const database = (event.target as IDBOpenDBRequest).result;
      
      // 视频存储
      if (!database.objectStoreNames.contains(STORE_NAME)) {
        const videoStore = database.createObjectStore(STORE_NAME, { keyPath: 'id' });
        videoStore.createIndex('timestamp', 'timestamp', { unique: false });
      }
      
      // 元数据存储
      if (!database.objectStoreNames.contains(METADATA_STORE)) {
        const metaStore = database.createObjectStore(METADATA_STORE, { keyPath: 'id' });
        metaStore.createIndex('lastAccessed', 'lastAccessed', { unique: false });
        metaStore.createIndex('accessCount', 'accessCount', { unique: false });
      }
    };
  });
}

/**
 * 保存视频到本地缓存（带大小检查和LRU清理）
 */
export async function saveVideo(id: string, file: File, url: string): Promise<boolean> {
  try {
    // 检查文件大小
    if (file.size > MAX_VIDEO_SIZE) {
      console.log(`[VideoCache] 视频过大，跳过缓存: ${(file.size / 1024 / 1024).toFixed(2)}MB`);
      return false;
    }

    const database = await initVideoDB();
    
    // 检查是否需要清理空间
    await ensureSpace(database, file.size);
    
    // 保存视频数据
    const videoData = {
      id,
      data: file,
      timestamp: Date.now()
    };

    const transaction = database.transaction([STORE_NAME, METADATA_STORE], 'readwrite');
    const videoStore = transaction.objectStore(STORE_NAME);
    const metaStore = transaction.objectStore(METADATA_STORE);

    await Promise.all([
      new Promise<void>((resolve, reject) => {
        const request = videoStore.put(videoData);
        request.onsuccess = () => resolve();
        request.onerror = () => reject(request.error);
      }),
      new Promise<void>((resolve, reject) => {
        const metadata: VideoMetadata = {
          id,
          size: file.size,
          timestamp: Date.now(),
          accessCount: 0,
          lastAccessed: Date.now(),
          url
        };
        const request = metaStore.put(metadata);
        request.onsuccess = () => resolve();
        request.onerror = () => reject(request.error);
      })
    ]);

    console.log(`[VideoCache] 视频已缓存: ${id}, 大小: ${(file.size / 1024 / 1024).toFixed(2)}MB`);
    return true;
  } catch (err) {
    console.error('[VideoCache] 保存视频失败:', err);
    return false;
  }
}

/**
 * 从本地缓存获取视频
 */
export async function getVideo(id: string): Promise<File | null> {
  try {
    const database = await initVideoDB();
    const transaction = database.transaction([STORE_NAME, METADATA_STORE], 'readwrite');
    const videoStore = transaction.objectStore(STORE_NAME);
    const metaStore = transaction.objectStore(METADATA_STORE);

    // 获取视频数据
    const videoData = await new Promise<any>((resolve, reject) => {
      const request = videoStore.get(id);
      request.onsuccess = () => resolve(request.result);
      request.onerror = () => reject(request.error);
    });

    if (!videoData) return null;

    // 更新访问统计
    const metadata = await new Promise<VideoMetadata>((resolve, reject) => {
      const request = metaStore.get(id);
      request.onsuccess = () => resolve(request.result);
      request.onerror = () => reject(request.error);
    });

    if (metadata) {
      metadata.accessCount++;
      metadata.lastAccessed = Date.now();
      metaStore.put(metadata);
    }

    return videoData.data;
  } catch (err) {
    console.error('[VideoCache] 获取视频失败:', err);
    return null;
  }
}

/**
 * 检查视频是否在本地缓存
 */
export async function hasVideoInLocal(id: string): Promise<boolean> {
  try {
    const database = await initVideoDB();
    const transaction = database.transaction(METADATA_STORE, 'readonly');
    const store = transaction.objectStore(METADATA_STORE);

    const metadata = await new Promise<VideoMetadata>((resolve, reject) => {
      const request = store.get(id);
      request.onsuccess = () => resolve(request.result);
      request.onerror = () => reject(request.error);
    });

    return !!metadata;
  } catch (err) {
    console.error('[VideoCache] 检查缓存失败:', err);
    return false;
  }
}

/**
 * 删除指定视频缓存
 */
export async function removeVideo(id: string): Promise<void> {
  try {
    const database = await initVideoDB();
    const transaction = database.transaction([STORE_NAME, METADATA_STORE], 'readwrite');
    
    transaction.objectStore(STORE_NAME).delete(id);
    transaction.objectStore(METADATA_STORE).delete(id);
    
    console.log(`[VideoCache] 已删除缓存: ${id}`);
  } catch (err) {
    console.error('[VideoCache] 删除视频失败:', err);
  }
}

/**
 * 获取缓存统计信息
 */
export async function getCacheStats(): Promise<{ totalSize: number; count: number }> {
  try {
    const database = await initVideoDB();
    const transaction = database.transaction(METADATA_STORE, 'readonly');
    const store = transaction.objectStore(METADATA_STORE);

    const allMetadata = await new Promise<VideoMetadata[]>((resolve, reject) => {
      const request = store.getAll();
      request.onsuccess = () => resolve(request.result);
      request.onerror = () => reject(request.error);
    });

    const totalSize = allMetadata.reduce((sum, meta) => sum + meta.size, 0);
    return { totalSize, count: allMetadata.length };
  } catch (err) {
    console.error('[VideoCache] 获取统计失败:', err);
    return { totalSize: 0, count: 0 };
  }
}

/**
 * 清理所有缓存
 */
export async function clearAllCache(): Promise<void> {
  try {
    const database = await initVideoDB();
    const transaction = database.transaction([STORE_NAME, METADATA_STORE], 'readwrite');
    
    transaction.objectStore(STORE_NAME).clear();
    transaction.objectStore(METADATA_STORE).clear();
    
    console.log('[VideoCache] 已清空所有缓存');
  } catch (err) {
    console.error('[VideoCache] 清空缓存失败:', err);
  }
}

/**
 * 确保有足够空间（LRU清理策略）
 */
async function ensureSpace(database: IDBDatabase, requiredSpace: number): Promise<void> {
  const stats = await getCacheStats();
  
  if (stats.totalSize + requiredSpace <= MAX_CACHE_SIZE) {
    return; // 空间足够
  }

  // 需要清理空间
  const spaceToFree = stats.totalSize + requiredSpace - MAX_CACHE_SIZE;
  let freedSpace = 0;

  const transaction = database.transaction([STORE_NAME, METADATA_STORE], 'readwrite');
  const metaStore = transaction.objectStore(METADATA_STORE);
  const videoStore = transaction.objectStore(STORE_NAME);

  // 按最后访问时间排序（LRU）
  const allMetadata = await new Promise<VideoMetadata[]>((resolve, reject) => {
    const request = metaStore.index('lastAccessed').getAll();
    request.onsuccess = () => resolve(request.result);
    request.onerror = () => reject(request.error);
  });

  // 删除最久未访问的视频
  for (const meta of allMetadata.sort((a, b) => a.lastAccessed - b.lastAccessed)) {
    if (freedSpace >= spaceToFree) break;
    
    videoStore.delete(meta.id);
    metaStore.delete(meta.id);
    freedSpace += meta.size;
    
    console.log(`[VideoCache] LRU清理: ${meta.id}, 释放 ${(meta.size / 1024 / 1024).toFixed(2)}MB`);
  }

  console.log(`[VideoCache] 总共释放: ${(freedSpace / 1024 / 1024).toFixed(2)}MB`);
}

/**
 * 智能预加载管理器
 */
class PreloadManager {
  private preloadQueue: Array<{ id: string; url: string; priority: number }> = [];
  private isPreloading = false;
  private maxConcurrent = 2; // 最大并发预加载数
  private activeLoads = 0;
  private API_BASE_URL: string;

  constructor(apiBaseUrl: string) {
    this.API_BASE_URL = apiBaseUrl;
  }

  /**
   * 添加视频到预加载队列
   */
  addToQueue(id: string, url: string, priority: number = 0) {
    // 检查是否已在队列中
    const existingIndex = this.preloadQueue.findIndex(item => item.id === id);
    if (existingIndex >= 0) {
      // 更新优先级
      this.preloadQueue[existingIndex].priority = Math.max(
        this.preloadQueue[existingIndex].priority,
        priority
      );
    } else {
      this.preloadQueue.push({ id, url, priority });
    }
    
    // 按优先级排序
    this.preloadQueue.sort((a, b) => b.priority - a.priority);
    
    // 开始预加载
    this.processQueue();
  }

  /**
   * 处理预加载队列
   */
  private async processQueue() {
    if (this.isPreloading || this.activeLoads >= this.maxConcurrent) return;
    if (this.preloadQueue.length === 0) return;

    this.isPreloading = true;

    while (this.preloadQueue.length > 0 && this.activeLoads < this.maxConcurrent) {
      const item = this.preloadQueue.shift();
      if (!item) continue;

      // 检查是否已缓存
      const isCached = await hasVideoInLocal(item.id);
      if (isCached) continue;

      this.activeLoads++;
      this.preloadVideo(item.id, item.url).finally(() => {
        this.activeLoads--;
        // 继续处理队列
        setTimeout(() => this.processQueue(), 100);
      });
    }

    this.isPreloading = false;
  }

  /**
   * 预加载单个视频
   */
  private async preloadVideo(id: string, url: string): Promise<void> {
    try {
      console.log(`[Preload] 开始预加载: ${id}`);
      
      const fullVideoUrl = url.startsWith('http') ? url : `${this.API_BASE_URL}${url}`;
      const videoDownloadUrl = `${this.API_BASE_URL}/api/proxy/video?url=${encodeURIComponent(fullVideoUrl)}`;

      // 使用AbortController实现超时控制
      const controller = new AbortController();
      const timeoutId = setTimeout(() => controller.abort(), 30000); // 30秒超时

      const response = await fetch(videoDownloadUrl, {
        signal: controller.signal,
        priority: 'low' // 低优先级，不阻塞其他请求
      });
      
      clearTimeout(timeoutId);

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`);
      }

      const blob = await response.blob();
      if (blob.size === 0) {
        throw new Error('Empty blob');
      }

      const file = new File([blob], `${id}.mp4`, { type: 'video/mp4' });
      await saveVideo(id, file, url);
      
      console.log(`[Preload] 完成: ${id}, 大小: ${(file.size / 1024 / 1024).toFixed(2)}MB`);
    } catch (err) {
      console.log(`[Preload] 失败: ${id}`, err);
    }
  }

  /**
   * 清空预加载队列
   */
  clearQueue() {
    this.preloadQueue = [];
    console.log('[Preload] 队列已清空');
  }
}

// 导出预加载管理器实例
export let preloadManager: PreloadManager | null = null;

export function initPreloadManager(apiBaseUrl: string) {
  preloadManager = new PreloadManager(apiBaseUrl);
  return preloadManager;
}
