/**
 * OPFS (Origin Private File System) 存储封装模块
 * 提供浏览器端的持久化大文件存储能力
 */

// 素材存储目录名
const MATERIALS_DIR = 'materials';
const THUMBNAILS_DIR = 'thumbnails';
const RENDERS_DIR = 'renders';

// 最大存储配额警告阈值 (80%)
const QUOTA_WARNING_THRESHOLD = 0.8;

/**
 * 获取 OPFS 根目录
 */
async function getRootDirectory(): Promise<FileSystemDirectoryHandle> {
  return await navigator.storage.getDirectory();
}

/**
 * 获取或创建子目录
 */
async function getDirectory(
  parent: FileSystemDirectoryHandle,
  name: string
): Promise<FileSystemDirectoryHandle> {
  return await parent.getDirectoryHandle(name, { create: true });
}

/**
 * 检查 OPFS 是否可用
 */
export function isOPFSSupported(): boolean {
  return 'storage' in navigator && 'getDirectory' in navigator.storage;
}

/**
 * 存储素材到 OPFS
 * @param materialId 素材唯一ID
 * @param videoBlob 视频文件 Blob
 * @param thumbnailBlob 缩略图 Blob（可选）
 */
export async function saveMaterial(
  materialId: string,
  videoBlob: Blob,
  thumbnailBlob?: Blob
): Promise<void> {
  const root = await getRootDirectory();
  const materialsDir = await getDirectory(root, MATERIALS_DIR);

  // 创建素材目录
  const materialDir = await materialsDir.getDirectoryHandle(materialId, { create: true });

  // 保存视频文件
  const videoFile = await materialDir.getFileHandle('video.mp4', { create: true });
  const videoWriter = await videoFile.createWritable();
  await videoWriter.write(videoBlob);
  await videoWriter.close();

  // 保存缩略图（如果提供）
  if (thumbnailBlob) {
    const thumbFile = await materialDir.getFileHandle('thumbnail.jpg', { create: true });
    const thumbWriter = await thumbFile.createWritable();
    await thumbWriter.write(thumbnailBlob);
    await thumbWriter.close();
  }

  console.log(`[OPFS] Material saved: ${materialId}`);
}

/**
 * 从 OPFS 读取素材
 */
export async function loadMaterial(materialId: string): Promise<{
  video: File | null;
  thumbnail: File | null;
}> {
  const root = await getRootDirectory();

  try {
    const materialsDir = await root.getDirectoryHandle(MATERIALS_DIR);
    const materialDir = await materialsDir.getDirectoryHandle(materialId);

    let video: File | null = null;
    let thumbnail: File | null = null;

    // 读取视频
    try {
      const videoFile = await materialDir.getFileHandle('video.mp4');
      video = await videoFile.getFile();
    } catch {
      // 视频文件不存在
    }

    // 读取缩略图
    try {
      const thumbFile = await materialDir.getFileHandle('thumbnail.jpg');
      thumbnail = await thumbFile.getFile();
    } catch {
      // 缩略图不存在
    }

    return { video, thumbnail };
  } catch {
    return { video: null, thumbnail: null };
  }
}

/**
 * 检查素材是否存在于 OPFS
 */
export async function hasMaterial(materialId: string): Promise<boolean> {
  const root = await getRootDirectory();

  try {
    const materialsDir = await root.getDirectoryHandle(MATERIALS_DIR);
    await materialsDir.getDirectoryHandle(materialId);
    return true;
  } catch {
    return false;
  }
}

/**
 * 删除素材
 */
export async function deleteMaterial(materialId: string): Promise<boolean> {
  const root = await getRootDirectory();

  try {
    const materialsDir = await root.getDirectoryHandle(MATERIALS_DIR);
    await materialsDir.removeEntry(materialId, { recursive: true });
    console.log(`[OPFS] Material deleted: ${materialId}`);
    return true;
  } catch (error) {
    console.error(`[OPFS] Failed to delete material ${materialId}:`, error);
    return false;
  }
}

/**
 * 保存渲染结果到 OPFS
 */
export async function saveRender(
  renderId: string,
  videoBlob: Blob
): Promise<void> {
  const root = await getRootDirectory();
  const rendersDir = await getDirectory(root, RENDERS_DIR);

  const renderFile = await rendersDir.getFileHandle(`${renderId}.mp4`, { create: true });
  const writer = await renderFile.createWritable();
  await writer.write(videoBlob);
  await writer.close();

  console.log(`[OPFS] Render saved: ${renderId}`);
}

/**
 * 从 OPFS 读取渲染结果
 */
export async function loadRender(renderId: string): Promise<File | null> {
  const root = await getRootDirectory();

  try {
    const rendersDir = await root.getDirectoryHandle(RENDERS_DIR);
    const renderFile = await rendersDir.getFileHandle(`${renderId}.mp4`);
    return await renderFile.getFile();
  } catch {
    return null;
  }
}

/**
 * 删除渲染结果
 */
export async function deleteRender(renderId: string): Promise<boolean> {
  const root = await getRootDirectory();

  try {
    const rendersDir = await root.getDirectoryHandle(RENDERS_DIR);
    await rendersDir.removeEntry(`${renderId}.mp4`);
    console.log(`[OPFS] Render deleted: ${renderId}`);
    return true;
  } catch (error) {
    console.error(`[OPFS] Failed to delete render ${renderId}:`, error);
    return false;
  }
}

/**
 * 获取所有素材ID列表
 */
export async function listMaterials(): Promise<string[]> {
  const root = await getRootDirectory();
  const materials: string[] = [];

  try {
    const materialsDir = await root.getDirectoryHandle(MATERIALS_DIR);

    // @ts-ignore - entries() 是 OPFS 标准 API，但 TypeScript 定义可能不完整
    for await (const [name, handle] of materialsDir.entries()) {
      if (handle.kind === 'directory') {
        materials.push(name);
      }
    }
  } catch {
    // 目录不存在，返回空数组
  }

  return materials;
}

/**
 * 获取所有渲染结果ID列表
 */
export async function listRenders(): Promise<string[]> {
  const root = await getRootDirectory();
  const renders: string[] = [];

  try {
    const rendersDir = await root.getDirectoryHandle(RENDERS_DIR);

    // @ts-ignore - entries() 是 OPFS 标准 API，但 TypeScript 定义可能不完整
    for await (const [name, handle] of rendersDir.entries()) {
      if (handle.kind === 'file' && name.endsWith('.mp4')) {
        renders.push(name.replace('.mp4', ''));
      }
    }
  } catch {
    // 目录不存在，返回空数组
  }

  return renders;
}

/**
 * 获取存储配额信息
 */
export async function getStorageQuota(): Promise<{
  usage: number;
  quota: number;
  usageDetails?: Record<string, number>;
}> {
  if ('storage' in navigator && 'estimate' in navigator.storage) {
    const estimate = await navigator.storage.estimate();
    return {
      usage: estimate.usage || 0,
      quota: estimate.quota || 0,
      // @ts-ignore - usageDetails 是 Storage API 的非标准属性
      usageDetails: estimate.usageDetails,
    };
  }

  throw new Error('Storage quota API not supported');
}

/**
 * 检查存储空间是否充足
 */
export async function checkStorageSpace(requiredBytes: number): Promise<{
  sufficient: boolean;
  available: number;
  warning?: string;
}> {
  try {
    const { usage, quota } = await getStorageQuota();
    const available = quota - usage;
    const sufficient = available >= requiredBytes;
    const usageRatio = usage / quota;

    let warning: string | undefined;
    if (usageRatio > QUOTA_WARNING_THRESHOLD) {
      warning = `Storage usage is at ${(usageRatio * 100).toFixed(1)}%`;
    }

    return { sufficient, available, warning };
  } catch (error) {
    // 无法获取配额信息，假设空间充足
    return { sufficient: true, available: Infinity };
  }
}

/**
 * 清理所有存储（危险操作）
 */
export async function clearAllStorage(): Promise<void> {
  const root = await getRootDirectory();

  // 删除素材目录
  try {
    await root.removeEntry(MATERIALS_DIR, { recursive: true });
  } catch {
    // 目录可能不存在
  }

  // 删除渲染目录
  try {
    await root.removeEntry(RENDERS_DIR, { recursive: true });
  } catch {
    // 目录可能不存在
  }

  console.log('[OPFS] All storage cleared');
}

/**
 * 获取素材大小
 */
export async function getMaterialSize(materialId: string): Promise<number> {
  const { video, thumbnail } = await loadMaterial(materialId);
  let size = 0;
  if (video) size += video.size;
  if (thumbnail) size += thumbnail.size;
  return size;
}

/**
 * 获取总存储大小
 */
export async function getTotalStorageSize(): Promise<{
  materials: number;
  renders: number;
  total: number;
}> {
  const materialIds = await listMaterials();
  const renderIds = await listRenders();

  let materialsSize = 0;
  for (const id of materialIds) {
    materialsSize += await getMaterialSize(id);
  }

  let rendersSize = 0;
  for (const id of renderIds) {
    const file = await loadRender(id);
    if (file) rendersSize += file.size;
  }

  return {
    materials: materialsSize,
    renders: rendersSize,
    total: materialsSize + rendersSize,
  };
}

/**
 * LRU 清理策略：删除最久未访问的素材
 * @param targetBytes 需要释放的目标字节数
 */
export async function cleanupLRU(targetBytes: number): Promise<number> {
  const materialIds = await listMaterials();

  // 获取所有素材的最后访问时间
  const materialsWithTime: Array<{ id: string; size: number; lastAccessed: number }> = [];

  for (const id of materialIds) {
    const size = await getMaterialSize(id);
    // 这里简化处理，使用素材目录的修改时间作为最后访问时间
    // 实际项目中可以维护一个访问时间记录
    const { video } = await loadMaterial(id);
    const lastAccessed = video?.lastModified || Date.now();
    materialsWithTime.push({ id, size, lastAccessed });
  }

  // 按最后访问时间排序（最久的在前）
  materialsWithTime.sort((a, b) => a.lastAccessed - b.lastAccessed);

  let freedBytes = 0;

  for (const material of materialsWithTime) {
    if (freedBytes >= targetBytes) break;

    await deleteMaterial(material.id);
    freedBytes += material.size;

    console.log(`[OPFS] LRU cleanup: ${material.id}, freed ${(material.size / 1024 / 1024).toFixed(2)}MB`);
  }

  console.log(`[OPFS] Total freed: ${(freedBytes / 1024 / 1024).toFixed(2)}MB`);
  return freedBytes;
}
