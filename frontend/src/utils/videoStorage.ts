/**
 * 视频本地存储模块
 * 使用 IndexedDB 和 OPFS 实现浏览器本地视频缓存
 * 
 * 功能：
 * 1. 保存视频到浏览器本地存储
 * 2. 从本地存储读取视频
 * 3. LRU 清理策略
 * 4. 存储配额管理
 */

const DB_NAME = 'MixCutVideos';
const DB_VERSION = 1;
const STORE_NAME = 'videos';
const DEFAULT_MAX_SIZE = 500 * 1024 * 1024; // 默认 500MB

// 视频元数据接口
interface VideoMetadata {
  id: string;
  file: File;
  timestamp: number;
  size: number;
  mimeType: string;
}

// 存储统计信息
interface StorageStats {
  totalSize: number;
  videoCount: number;
  maxSize: number;
}

/**
 * 打开 IndexedDB 数据库
 */
function openDB(): Promise<IDBDatabase> {
  return new Promise((resolve, reject) => {
    const request = indexedDB.open(DB_NAME, DB_VERSION);

    request.onerror = () => reject(request.error);
    request.onsuccess = () => resolve(request.result);

    request.onupgradeneeded = (event) => {
      const db = (event.target as IDBOpenDBRequest).result;
      if (!db.objectStoreNames.contains(STORE_NAME)) {
        const store = db.createObjectStore(STORE_NAME, { keyPath: 'id' });
        store.createIndex('timestamp', 'timestamp', { unique: false });
        store.createIndex('size', 'size', { unique: false });
      }
    };
  });
}

/**
 * 保存视频到本地存储（IndexedDB）
 * @param id 视频唯一标识
 * @param file 视频文件
 */
export async function saveVideoToLocal(id: string, file: File): Promise<void> {
  try {
    // 检查存储空间
    await cleanupIfNeeded(file.size);

    const db = await openDB();
    const transaction = db.transaction([STORE_NAME], 'readwrite');
    const store = transaction.objectStore(STORE_NAME);

    const metadata: VideoMetadata = {
      id,
      file,
      timestamp: Date.now(),
      size: file.size,
      mimeType: file.type,
    };

    return new Promise((resolve, reject) => {
      const request = store.put(metadata);
      request.onsuccess = () => resolve();
      request.onerror = () => reject(request.error);

      transaction.oncomplete = () => db.close();
    });
  } catch (error) {
    console.error('[VideoStorage] 保存视频失败:', error);
    throw error;
  }
}

/**
 * 从本地存储获取视频
 * @param id 视频唯一标识
 * @returns 视频文件，如果不存在返回 null
 */
export async function getVideoFromLocal(id: string): Promise<File | null> {
  try {
    const db = await openDB();
    const transaction = db.transaction([STORE_NAME], 'readonly');
    const store = transaction.objectStore(STORE_NAME);

    return new Promise((resolve, reject) => {
      const request = store.get(id);

      request.onsuccess = () => {
        const result = request.result as VideoMetadata | undefined;
        if (result) {
          // 更新访问时间（LRU策略）
          updateAccessTime(id);
          resolve(result.file);
        } else {
          resolve(null);
        }
      };

      request.onerror = () => reject(request.error);
      transaction.oncomplete = () => db.close();
    });
  } catch (error) {
    console.error('[VideoStorage] 获取视频失败:', error);
    return null;
  }
}

/**
 * 更新视频访问时间（用于LRU策略）
 */
async function updateAccessTime(id: string): Promise<void> {
  try {
    const db = await openDB();
    const transaction = db.transaction([STORE_NAME], 'readwrite');
    const store = transaction.objectStore(STORE_NAME);

    const request = store.get(id);
    request.onsuccess = () => {
      const data = request.result as VideoMetadata | undefined;
      if (data) {
        data.timestamp = Date.now();
        store.put(data);
      }
    };

    transaction.oncomplete = () => db.close();
  } catch (error) {
    console.warn('[VideoStorage] 更新访问时间失败:', error);
  }
}

/**
 * 从本地存储删除视频
 * @param id 视频唯一标识
 */
export async function removeVideoFromLocal(id: string): Promise<void> {
  try {
    const db = await openDB();
    const transaction = db.transaction([STORE_NAME], 'readwrite');
    const store = transaction.objectStore(STORE_NAME);

    return new Promise((resolve, reject) => {
      const request = store.delete(id);
      request.onsuccess = () => resolve();
      request.onerror = () => reject(request.error);
      transaction.oncomplete = () => db.close();
    });
  } catch (error) {
    console.error('[VideoStorage] 删除视频失败:', error);
    throw error;
  }
}

/**
 * 检查视频是否存在于本地存储
 * @param id 视频唯一标识
 */
export async function hasVideoInLocal(id: string): Promise<boolean> {
  const file = await getVideoFromLocal(id);
  return file !== null;
}

/**
 * 获取存储统计信息
 */
export async function getStorageStats(): Promise<StorageStats> {
  try {
    const db = await openDB();
    const transaction = db.transaction([STORE_NAME], 'readonly');
    const store = transaction.objectStore(STORE_NAME);

    return new Promise((resolve, reject) => {
      const request = store.getAll();

      request.onsuccess = () => {
        const videos = request.result as VideoMetadata[];
        const totalSize = videos.reduce((sum, v) => sum + v.size, 0);

        resolve({
          totalSize,
          videoCount: videos.length,
          maxSize: DEFAULT_MAX_SIZE,
        });
      };

      request.onerror = () => reject(request.error);
      transaction.oncomplete = () => db.close();
    });
  } catch (error) {
    console.error('[VideoStorage] 获取统计信息失败:', error);
    return {
      totalSize: 0,
      videoCount: 0,
      maxSize: DEFAULT_MAX_SIZE,
    };
  }
}

/**
 * 清理旧视频（LRU策略）
 * @param maxSize 最大存储空间（字节）
 */
export async function cleanupVideos(maxSize: number = DEFAULT_MAX_SIZE): Promise<void> {
  try {
    const db = await openDB();
    const transaction = db.transaction([STORE_NAME], 'readonly');
    const store = transaction.objectStore(STORE_NAME);

    const videos = await new Promise<VideoMetadata[]>((resolve, reject) => {
      const request = store.getAll();
      request.onsuccess = () => resolve(request.result);
      request.onerror = () => reject(request.error);
    });

    const totalSize = videos.reduce((sum, v) => sum + v.size, 0);

    if (totalSize > maxSize) {
      // 按时间排序，删除最旧的
      videos.sort((a, b) => a.timestamp - b.timestamp);

      let currentSize = totalSize;
      const targetSize = maxSize * 0.8; // 清理到80%

      const deleteTransaction = db.transaction([STORE_NAME], 'readwrite');
      const deleteStore = deleteTransaction.objectStore(STORE_NAME);

      for (const video of videos) {
        if (currentSize <= targetSize) break;

        deleteStore.delete(video.id);
        currentSize -= video.size;

        console.log(`[VideoStorage] 清理旧视频: ${video.id}, 释放 ${(video.size / 1024 / 1024).toFixed(2)}MB`);
      }

      await new Promise<void>((resolve) => {
        deleteTransaction.oncomplete = () => resolve();
      });
    }

    db.close();
  } catch (error) {
    console.error('[VideoStorage] 清理视频失败:', error);
  }
}

/**
 * 如果需要，清理存储空间
 * @param requiredSpace 需要的空间（字节）
 */
async function cleanupIfNeeded(requiredSpace: number): Promise<void> {
  const stats = await getStorageStats();

  if (stats.totalSize + requiredSpace > stats.maxSize) {
    console.log(`[VideoStorage] 存储空间不足，开始清理...`);
    await cleanupVideos(stats.maxSize);
  }
}

/**
 * 清空所有本地存储的视频
 */
export async function clearAllVideos(): Promise<void> {
  try {
    const db = await openDB();
    const transaction = db.transaction([STORE_NAME], 'readwrite');
    const store = transaction.objectStore(STORE_NAME);

    return new Promise((resolve, reject) => {
      const request = store.clear();
      request.onsuccess = () => {
        console.log('[VideoStorage] 已清空所有视频');
        resolve();
      };
      request.onerror = () => reject(request.error);
      transaction.oncomplete = () => db.close();
    });
  } catch (error) {
    console.error('[VideoStorage] 清空视频失败:', error);
    throw error;
  }
}

/**
 * 获取所有本地存储的视频ID列表
 */
export async function getAllVideoIds(): Promise<string[]> {
  try {
    const db = await openDB();
    const transaction = db.transaction([STORE_NAME], 'readonly');
    const store = transaction.objectStore(STORE_NAME);

    return new Promise((resolve, reject) => {
      const request = store.getAllKeys();
      request.onsuccess = () => resolve(request.result as string[]);
      request.onerror = () => reject(request.error);
      transaction.oncomplete = () => db.close();
    });
  } catch (error) {
    console.error('[VideoStorage] 获取视频列表失败:', error);
    return [];
  }
}

// ==================== OPFS 支持（可选增强）====================

/**
 * 检测 OPFS 支持
 */
export function isOPFSSupported(): boolean {
  return typeof navigator.storage?.getDirectory === 'function';
}

/**
 * 使用 OPFS 保存视频（性能更好，Chrome/Edge）
 * @param id 视频唯一标识
 * @param file 视频文件
 */
export async function saveVideoToOPFS(id: string, file: File): Promise<void> {
  if (!isOPFSSupported()) {
    throw new Error('OPFS 不支持');
  }

  try {
    const root = await navigator.storage.getDirectory();
    const fileHandle = await root.getFileHandle(`video_${id}.mp4`, { create: true });

    const writable = await fileHandle.createWritable();
    await writable.write(file);
    await writable.close();

    console.log(`[VideoStorage] OPFS 保存成功: ${id}`);
  } catch (error) {
    console.error('[VideoStorage] OPFS 保存失败:', error);
    throw error;
  }
}

/**
 * 从 OPFS 读取视频
 * @param id 视频唯一标识
 */
export async function getVideoFromOPFS(id: string): Promise<File | null> {
  if (!isOPFSSupported()) {
    return null;
  }

  try {
    const root = await navigator.storage.getDirectory();
    const fileHandle = await root.getFileHandle(`video_${id}.mp4`);
    return await fileHandle.getFile();
  } catch {
    return null;
  }
}

/**
 * 智能保存视频（优先 OPFS，回退 IndexedDB）
 */
export async function saveVideo(id: string, file: File): Promise<void> {
  // 优先尝试 OPFS
  if (isOPFSSupported()) {
    try {
      await saveVideoToOPFS(id, file);
      return;
    } catch (error) {
      console.warn('[VideoStorage] OPFS 失败，回退到 IndexedDB:', error);
    }
  }

  // 回退到 IndexedDB
  await saveVideoToLocal(id, file);
}

/**
 * 智能读取视频（优先 OPFS，回退 IndexedDB）
 */
export async function getVideo(id: string): Promise<File | null> {
  // 优先尝试 OPFS
  if (isOPFSSupported()) {
    const opfsFile = await getVideoFromOPFS(id);
    if (opfsFile) return opfsFile;
  }

  // 回退到 IndexedDB
  return await getVideoFromLocal(id);
}
