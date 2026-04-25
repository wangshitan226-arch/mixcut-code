/**
 * OSS直传上传模块
 * 支持客户端直接上传文件到阿里云OSS（使用STS临时签名）
 */

const API_BASE_URL = (import.meta as any).env?.VITE_API_URL || 'http://localhost:3002';

export interface STSToken {
  accessid: string;
  policy: string;
  signature: string;
  dir: string;
  host: string;
  expire: number;
}

export interface UploadResult {
  url: string;
  success: boolean;
}

/**
 * 获取OSS STS临时签名
 */
export async function getSTSToken(userId: string): Promise<STSToken> {
  const response = await fetch(`${API_BASE_URL}/api/oss/sts-token`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      user_id: userId,
      dir: `users/${userId}/client-renders/`,
      expire_seconds: 300,
    }),
  });

  if (!response.ok) {
    throw new Error('获取STS签名失败');
  }

  return await response.json();
}

/**
 * 直传文件到OSS（使用STS签名）
 *
 * @param blob 文件Blob
 * @param filename 文件名
 * @param userId 用户ID
 * @param onProgress 进度回调
 */
export async function uploadToOSSDirect(
  blob: Blob,
  filename: string,
  userId: string,
  onProgress?: (progress: number) => void
): Promise<UploadResult> {
  console.log('[OSS] 开始直传:', filename, `(${(blob.size / 1024 / 1024).toFixed(2)}MB)`);

  // 1. 获取STS签名
  const stsToken = await getSTSToken(userId);
  console.log('[OSS] STS签名获取成功');

  // 2. 构建OSS路径
  const ossKey = `${stsToken.dir}${filename}`;

  // 3. 构建FormData
  const formData = new FormData();
  formData.append('key', ossKey);
  formData.append('policy', stsToken.policy);
  formData.append('OSSAccessKeyId', stsToken.accessid);
  formData.append('success_action_status', '200');
  formData.append('signature', stsToken.signature);
  formData.append('file', blob, filename);

  // 4. 上传到OSS
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();

    xhr.upload.addEventListener('progress', (e) => {
      if (e.lengthComputable) {
        const progress = Math.round((e.loaded / e.total) * 100);
        onProgress?.(progress);
      }
    });

    xhr.addEventListener('load', () => {
      if (xhr.status === 200) {
        const url = `${stsToken.host}/${ossKey}`;
        console.log('[OSS] 上传成功:', url);
        resolve({ url, success: true });
      } else {
        reject(new Error(`OSS上传失败: ${xhr.status}`));
      }
    });

    xhr.addEventListener('error', () => {
      reject(new Error('OSS上传网络错误'));
    });

    xhr.addEventListener('abort', () => {
      reject(new Error('OSS上传被取消'));
    });

    xhr.open('POST', stsToken.host);
    xhr.send(formData);
  });
}

/**
 * 通知后端客户端渲染结果已上传到OSS
 *
 * @param editId 剪辑任务ID
 * @param ossUrl OSS文件URL
 * @param duration 视频时长（秒）
 * @param fileSize 文件大小（字节）
 */
export async function notifyClientRenderUploaded(
  editId: string,
  ossUrl: string,
  duration: number,
  fileSize: number
): Promise<any> {
  const response = await fetch(`${API_BASE_URL}/api/kaipai/${editId}/client-render`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      oss_url: ossUrl,
      duration,
      file_size: fileSize,
    }),
  });

  if (!response.ok) {
    throw new Error('通知后端上传完成失败');
  }

  return await response.json();
}

/**
 * 完整的客户端渲染上传流程
 *
 * 1. 上传Blob到OSS
 * 2. 通知后端
 * 3. 后端自动触发ICE模板渲染（如果选择了模板）
 *
 * @param blob 视频Blob
 * @param editId 剪辑任务ID
 * @param userId 用户ID
 * @param duration 视频时长
 * @param onProgress 进度回调
 */
export async function uploadClientRender(
  blob: Blob,
  editId: string,
  userId: string,
  duration: number,
  onProgress?: (stage: string, progress: number) => void
): Promise<{ url: string; taskId?: string; status: string }> {
  const filename = `client_render_${editId}_${Date.now()}.mp4`;

  // 阶段1：上传到OSS
  onProgress?.('uploading', 0);
  const uploadResult = await uploadToOSSDirect(blob, filename, userId, (progress) => {
    onProgress?.('uploading', progress);
  });

  if (!uploadResult.success) {
    throw new Error('上传到OSS失败');
  }

  // 阶段2：通知后端
  onProgress?.('notifying', 0);
  const result = await notifyClientRenderUploaded(
    editId,
    uploadResult.url,
    duration,
    blob.size
  );

  onProgress?.('completed', 100);

  return {
    url: uploadResult.url,
    taskId: result.task_id,
    status: result.status,
  };
}
