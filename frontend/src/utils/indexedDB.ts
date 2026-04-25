/**
 * IndexedDB 降级存储模块
 * 当 OPFS 不可用时作为降级方案
 * 适合存储较小的文件（< 50MB）
 */

const DB_NAME = 'MixCutFallbackDB';
const DB_VERSION = 1;

// 存储对象名
const STORES = {
  MATERIALS: 'materials',
  RENDERS: 'renders',
  METADATA: 'metadata',
} as const;

// 最大单个文件大小（50MB）
const MAX_FILE_SIZE = 50 * 1024 * 1024;
// 最大总存储大小（200MB）
const MAX_TOTAL_SIZE = 200 * 1024 * 1024;

let db: IDBDatabase | null = null;

/**
 * 初始化 IndexedDB
 */
export async function initIndexedDB(): Promise<IDBDatabase> {
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

      // 素材存储
      if (!database.objectStoreNames.contains(STORES.MATERIALS)) {
        const materialStore = database.createObjectStore(STORES.MATERIALS, { keyPath: 'id' });
        materialStore.createIndex('timestamp', 'timestamp', { unique: false });
      }

      // 渲染结果存储
      if (!database.objectStoreNames.contains(STORES.RENDERS)) {
        const renderStore = database.createObjectStore(STORES.RENDERS, { keyPath: 'id' });
        renderStore.createIndex('timestamp', 'timestamp', { unique: false });
      }

      // 元数据存储
      if (!database.objectStoreNames.contains(STORES.METADATA)) {
        const metaStore = database.createObjectStore(STORES.METADATA, { keyPath: 'id' });
        metaStore.createIndex('lastAccessed', 'lastAccessed', { unique: false });
        metaStore.createIndex('type', 'type', { unique: false });
      }
    };
  });
}

/**
 * 存储素材
 */
export async function saveMaterialToIndexedDB(
  materialId: string,
  videoBlob: Blob,
  thumbnailBlob?: Blob
): Promise<boolean> {
  // 检查文件大小
  if (videoBlob.size > MAX_FILE_SIZE) {
    console.warn(`[IndexedDB] File too large: ${(videoBlob.size / 1024 / 1024).toFixed(2)}MB, max: ${MAX_FILE_SIZE / 1024 / 1024}MB`);
    return false;
  }

  try {
    const database = await initIndexedDB();

    // 检查存储空间
    const hasSpace = await ensureSpace(database, videoBlob.size + (thumbnailBlob?.size || 0));
    if (!hasSpace) {
      console.warn('[IndexedDB] Not enough space');
      return false;
    }

    const transaction = database.transaction(
      [STORES.MATERIALS, STORES.METADATA],
      'readwrite'
    );

    // 保存视频
    const videoData = {
      id: materialId,
      type: 'video',
      data: videoBlob,
      timestamp: Date.now(),
    };

    await new Promise<void>((resolve, reject) => {
      const request = transaction.objectStore(STORES.MATERIALS).put(videoData);
      request.onsuccess = () => resolve();
      request.onerror = () => reject(request.error);
    });

    // 保存缩略图（如果提供）
    if (thumbnailBlob) {
      const thumbData = {
        id: `${materialId}_thumb`,
        type: 'thumbnail',
        data: thumbnailBlob,
        timestamp: Date.now(),
      };

      await new Promise<void>((resolve, reject) => {
        const request = transaction.objectStore(STORES.MATERIALS).put(thumbData);
        request.onsuccess = () => resolve();
        request.onerror = () => reject(request.error);
      });
    }

    // 保存元数据
    const metadata = {
      id: materialId,
      type: 'material',
      size: videoBlob.size + (thumbnailBlob?.size || 0),
      hasThumbnail: !!thumbnailBlob,
      timestamp: Date.now(),
      lastAccessed: Date.now(),
      accessCount: 0,
    };

    await new Promise<void>((resolve, reject) => {
      const request = transaction.objectStore(STORES.METADATA).put(metadata);
      request.onsuccess = () => resolve();
      request.onerror = () => reject(request.error);
    });

    console.log(`[IndexedDB] Material saved: ${materialId}`);
    return true;
  } catch (error) {
    console.error('[IndexedDB] Failed to save material:', error);
    return false;
  }
}

/**
 * 从 IndexedDB 读取素材
 */
export async function loadMaterialFromIndexedDB(materialId: string): Promise<{
  video: Blob | null;
  thumbnail: Blob | null;
}> {
  try {
    const database = await initIndexedDB();
    const transaction = database.transaction(
      [STORES.MATERIALS, STORES.METADATA],
      'readwrite'
    );

    // 读取视频
    const videoData = await new Promise<any>((resolve, reject) => {
      const request = transaction.objectStore(STORES.MATERIALS).get(materialId);
      request.onsuccess = () => resolve(request.result);
      request.onerror = () => reject(request.error);
    });

    // 读取缩略图
    const thumbData = await new Promise<any>((resolve, reject) => {
      const request = transaction.objectStore(STORES.MATERIALS).get(`${materialId}_thumb`);
      request.onsuccess = () => resolve(request.result);
      request.onerror = () => reject(request.error);
    });

    // 更新访问统计
    const metadata = await new Promise<any>((resolve, reject) => {
      const request = transaction.objectStore(STORES.METADATA).get(materialId);
      request.onsuccess = () => resolve(request.result);
      request.onerror = () => reject(request.error);
    });

    if (metadata) {
      metadata.lastAccessed = Date.now();
      metadata.accessCount = (metadata.accessCount || 0) + 1;
      transaction.objectStore(STORES.METADATA).put(metadata);
    }

    return {
      video: videoData?.data || null,
      thumbnail: thumbData?.data || null,
    };
  } catch (error) {
    console.error('[IndexedDB] Failed to load material:', error);
    return { video: null, thumbnail: null };
  }
}

/**
 * 检查素材是否存在于 IndexedDB
 */
export async function hasMaterialInIndexedDB(materialId: string): Promise<boolean> {
  try {
    const database = await initIndexedDB();
    const transaction = database.transaction(STORES.METADATA, 'readonly');

    const metadata = await new Promise<any>((resolve, reject) => {
      const request = transaction.objectStore(STORES.METADATA).get(materialId);
      request.onsuccess = () => resolve(request.result);
      request.onerror = () => reject(request.error);
    });

    return !!metadata;
  } catch {
    return false;
  }
}

/**
 * 删除素材
 */
export async function deleteMaterialFromIndexedDB(materialId: string): Promise<boolean> {
  try {
    const database = await initIndexedDB();
    const transaction = database.transaction(
      [STORES.MATERIALS, STORES.METADATA],
      'readwrite'
    );

    transaction.objectStore(STORES.MATERIALS).delete(materialId);
    transaction.objectStore(STORES.MATERIALS).delete(`${materialId}_thumb`);
    transaction.objectStore(STORES.METADATA).delete(materialId);

    console.log(`[IndexedDB] Material deleted: ${materialId}`);
    return true;
  } catch (error) {
    console.error('[IndexedDB] Failed to delete material:', error);
    return false;
  }
}

/**
 * 保存渲染结果
 */
export async function saveRenderToIndexedDB(renderId: string, videoBlob: Blob): Promise<boolean> {
  if (videoBlob.size > MAX_FILE_SIZE) {
    console.warn(`[IndexedDB] Render too large: ${(videoBlob.size / 1024 / 1024).toFixed(2)}MB`);
    return false;
  }

  try {
    const database = await initIndexedDB();

    const hasSpace = await ensureSpace(database, videoBlob.size);
    if (!hasSpace) return false;

    const transaction = database.transaction(
      [STORES.RENDERS, STORES.METADATA],
      'readwrite'
    );

    // 保存渲染结果
    const renderData = {
      id: renderId,
      type: 'render',
      data: videoBlob,
      timestamp: Date.now(),
    };

    await new Promise<void>((resolve, reject) => {
      const request = transaction.objectStore(STORES.RENDERS).put(renderData);
      request.onsuccess = () => resolve();
      request.onerror = () => reject(request.error);
    });

    // 保存元数据
    const metadata = {
      id: renderId,
      type: 'render',
      size: videoBlob.size,
      timestamp: Date.now(),
      lastAccessed: Date.now(),
      accessCount: 0,
    };

    await new Promise<void>((resolve, reject) => {
      const request = transaction.objectStore(STORES.METADATA).put(metadata);
      request.onsuccess = () => resolve();
      request.onerror = () => reject(request.error);
    });

    console.log(`[IndexedDB] Render saved: ${renderId}`);
    return true;
  } catch (error) {
    console.error('[IndexedDB] Failed to save render:', error);
    return false;
  }
}

/**
 * 从 IndexedDB 读取渲染结果
 */
export async function loadRenderFromIndexedDB(renderId: string): Promise<Blob | null> {
  try {
    const database = await initIndexedDB();
    const transaction = database.transaction(
      [STORES.RENDERS, STORES.METADATA],
      'readwrite'
    );

    const renderData = await new Promise<any>((resolve, reject) => {
      const request = transaction.objectStore(STORES.RENDERS).get(renderId);
      request.onsuccess = () => resolve(request.result);
      request.onerror = () => reject(request.error);
    });

    // 更新访问统计
    const metadata = await new Promise<any>((resolve, reject) => {
      const request = transaction.objectStore(STORES.METADATA).get(renderId);
      request.onsuccess = () => resolve(request.result);
      request.onerror = () => reject(request.error);
    });

    if (metadata) {
      metadata.lastAccessed = Date.now();
      metadata.accessCount = (metadata.accessCount || 0) + 1;
      transaction.objectStore(STORES.METADATA).put(metadata);
    }

    return renderData?.data || null;
  } catch (error) {
    console.error('[IndexedDB] Failed to load render:', error);
    return null;
  }
}

/**
 * 获取存储统计
 */
export async function getIndexedDBStats(): Promise<{
  totalSize: number;
  materialCount: number;
  renderCount: number;
}> {
  try {
    const database = await initIndexedDB();
    const transaction = database.transaction(STORES.METADATA, 'readonly');
    const store = transaction.objectStore(STORES.METADATA);

    const allMetadata = await new Promise<any[]>((resolve, reject) => {
      const request = store.getAll();
      request.onsuccess = () => resolve(request.result);
      request.onerror = () => reject(request.error);
    });

    let totalSize = 0;
    let materialCount = 0;
    let renderCount = 0;

    for (const meta of allMetadata) {
      totalSize += meta.size || 0;
      if (meta.type === 'material') materialCount++;
      if (meta.type === 'render') renderCount++;
    }

    return { totalSize, materialCount, renderCount };
  } catch (error) {
    console.error('[IndexedDB] Failed to get stats:', error);
    return { totalSize: 0, materialCount: 0, renderCount: 0 };
  }
}

/**
 * 清理所有存储
 */
export async function clearAllIndexedDB(): Promise<void> {
  try {
    const database = await initIndexedDB();
    const transaction = database.transaction(
      [STORES.MATERIALS, STORES.RENDERS, STORES.METADATA],
      'readwrite'
    );

    transaction.objectStore(STORES.MATERIALS).clear();
    transaction.objectStore(STORES.RENDERS).clear();
    transaction.objectStore(STORES.METADATA).clear();

    console.log('[IndexedDB] All storage cleared');
  } catch (error) {
    console.error('[IndexedDB] Failed to clear storage:', error);
  }
}

/**
 * 确保有足够空间（LRU清理）
 */
async function ensureSpace(database: IDBDatabase, requiredBytes: number): Promise<boolean> {
  const stats = await getIndexedDBStats();

  if (stats.totalSize + requiredBytes <= MAX_TOTAL_SIZE) {
    return true;
  }

  // 需要清理空间
  const spaceToFree = stats.totalSize + requiredBytes - MAX_TOTAL_SIZE + 10 * 1024 * 1024; // 额外清理10MB

  const transaction = database.transaction(STORES.METADATA, 'readonly');
  const store = transaction.objectStore(STORES.METADATA);

  const allMetadata = await new Promise<any[]>((resolve, reject) => {
    const request = store.getAll();
    request.onsuccess = () => resolve(request.result);
    request.onerror = () => reject(request.error);
  });

  // 按最后访问时间排序
  allMetadata.sort((a, b) => (a.lastAccessed || 0) - (b.lastAccessed || 0));

  let freedSpace = 0;

  for (const meta of allMetadata) {
    if (freedSpace >= spaceToFree) break;

    if (meta.type === 'material') {
      await deleteMaterialFromIndexedDB(meta.id);
    }
    // 注意：渲染结果不自动清理，因为它们是用户确认的成品

    freedSpace += meta.size || 0;
  }

  console.log(`[IndexedDB] LRU cleanup freed: ${(freedSpace / 1024 / 1024).toFixed(2)}MB`);

  // 重新检查空间
  const newStats = await getIndexedDBStats();
  return newStats.totalSize + requiredBytes <= MAX_TOTAL_SIZE;
}

/**
 * 检查 IndexedDB 是否可用
 */
export function isIndexedDBSupported(): boolean {
  return 'indexedDB' in window;
}
