/**
 * 前端组合生成模块
 * 纯 JavaScript 计算排列组合，无需服务器参与
 */

// 素材信息
export interface Material {
  id: string;
  shotId: string;
  duration: number;
  name: string;
}

// 镜头信息
export interface Shot {
  id: string;
  name: string;
  order: number;
}

// 组合信息
export interface Combination {
  id: string;
  materials: Material[];
  duration: number;
  tag: string;
  uniqueness: number; // 唯一性评分 (0-100)
}

// 生成选项
export interface GenerateOptions {
  limit?: number;
  minUniqueness?: number;
  maxDuration?: number;
  minDuration?: number;
}

/**
 * 生成排列组合
 * @param shots 镜头列表（按顺序）
 * @param materialsMap 每个镜头对应的素材映射
 * @param options 生成选项
 */
export function generateCombinations(
  shots: Shot[],
  materialsMap: Map<string, Material[]>,
  options: GenerateOptions = {}
): Combination[] {
  const {
    limit = 1000,
    minUniqueness = 0,
    maxDuration = Infinity,
    minDuration = 0,
  } = options;

  // 按 order 排序镜头
  const sortedShots = [...shots].sort((a, b) => a.order - b.order);

  const combinations: Combination[] = [];

  // 使用回溯算法生成组合
  function backtrack(
    shotIndex: number,
    currentMaterials: Material[],
    currentDuration: number
  ) {
    // 如果已达到限制，停止
    if (combinations.length >= limit) return;

    // 如果已选择所有镜头，保存组合
    if (shotIndex === sortedShots.length) {
      // 检查时长限制
      if (currentDuration < minDuration || currentDuration > maxDuration) {
        return;
      }

      const uniqueness = calculateUniqueness(currentMaterials);

      // 检查唯一性限制
      if (uniqueness < minUniqueness) {
        return;
      }

      combinations.push({
        id: generateComboId(currentMaterials),
        materials: [...currentMaterials],
        duration: currentDuration,
        tag: generateTag(uniqueness),
        uniqueness,
      });

      return;
    }

    const shot = sortedShots[shotIndex];
    const shotMaterials = materialsMap.get(shot.id) || [];

    // 如果该镜头没有素材，跳过
    if (shotMaterials.length === 0) {
      backtrack(shotIndex + 1, currentMaterials, currentDuration);
      return;
    }

    // 尝试每个素材
    for (const material of shotMaterials) {
      // 检查是否已使用该素材（避免同一素材在同一组合中重复）
      if (currentMaterials.some(m => m.id === material.id)) {
        continue;
      }

      // 检查时长是否会超出限制
      const newDuration = currentDuration + material.duration;
      if (newDuration > maxDuration) {
        continue;
      }

      currentMaterials.push(material);
      backtrack(shotIndex + 1, currentMaterials, newDuration);
      currentMaterials.pop();
    }
  }

  backtrack(0, [], 0);

  // 按唯一性排序（高唯一性在前）
  combinations.sort((a, b) => b.uniqueness - a.uniqueness);

  return combinations;
}

/**
 * 智能生成组合（带策略优化）
 * 优先生成高唯一性的组合
 */
export function generateSmartCombinations(
  shots: Shot[],
  materialsMap: Map<string, Material[]>,
  options: GenerateOptions = {}
): Combination[] {
  const {
    limit = 1000,
    maxDuration = Infinity,
    minDuration = 0,
  } = options;

  // 按 order 排序镜头
  const sortedShots = [...shots].sort((a, b) => a.order - b.order);

  const combinations: Combination[] = [];
  const seenSignatures = new Set<string>();

  // 策略1：每个镜头选择不同素材（最大唯一性）
  function generateHighUniqueness() {
    const materials: Material[] = [];
    let duration = 0;

    for (const shot of sortedShots) {
      const shotMaterials = materialsMap.get(shot.id) || [];
      if (shotMaterials.length === 0) continue;

      // 选择使用次数最少的素材
      const selected = shotMaterials[0]; // 简化：选择第一个
      materials.push(selected);
      duration += selected.duration;
    }

    if (duration >= minDuration && duration <= maxDuration) {
      const signature = materials.map(m => m.id).join(',');
      if (!seenSignatures.has(signature)) {
        seenSignatures.add(signature);
        combinations.push({
          id: generateComboId(materials),
          materials: [...materials],
          duration,
          tag: '完全不重复',
          uniqueness: 100,
        });
      }
    }
  }

  // 策略2：随机组合
  function generateRandomCombinations(count: number) {
    for (let i = 0; i < count && combinations.length < limit; i++) {
      const materials: Material[] = [];
      let duration = 0;

      for (const shot of sortedShots) {
        const shotMaterials = materialsMap.get(shot.id) || [];
        if (shotMaterials.length === 0) continue;

        // 随机选择素材
        const randomIndex = Math.floor(Math.random() * shotMaterials.length);
        const selected = shotMaterials[randomIndex];
        materials.push(selected);
        duration += selected.duration;
      }

      if (duration >= minDuration && duration <= maxDuration) {
        const signature = materials.map(m => m.id).join(',');
        if (!seenSignatures.has(signature)) {
          seenSignatures.add(signature);
          const uniqueness = calculateUniqueness(materials);
          combinations.push({
            id: generateComboId(materials),
            materials: [...materials],
            duration,
            tag: generateTag(uniqueness),
            uniqueness,
          });
        }
      }
    }
  }

  // 策略3：系统遍历（如果组合数不多）
  function generateSystematic() {
    const totalCombinations = sortedShots.reduce(
      (acc, shot) => acc * (materialsMap.get(shot.id)?.length || 1),
      1
    );

    // 如果总组合数不多，系统生成
    if (totalCombinations <= limit * 2) {
      generateCombinations(shots, materialsMap, {
        limit,
        maxDuration,
        minDuration,
      });
    }
  }

  // 执行生成策略
  generateHighUniqueness();
  generateRandomCombinations(Math.min(limit - combinations.length, 500));

  // 如果还有空间，尝试系统生成
  if (combinations.length < limit / 2) {
    generateSystematic();
  }

  // 去重并排序
  const uniqueCombinations = Array.from(
    new Map(combinations.map(c => [c.id, c])).values()
  );

  uniqueCombinations.sort((a, b) => b.uniqueness - a.uniqueness);

  return uniqueCombinations.slice(0, limit);
}

/**
 * 计算组合的唯一性
 * 基于素材重复程度计算
 */
function calculateUniqueness(materials: Material[]): number {
  if (materials.length <= 1) return 100;

  // 统计每个 shotId 出现的次数
  const shotCounts = new Map<string, number>();
  for (const material of materials) {
    shotCounts.set(material.shotId, (shotCounts.get(material.shotId) || 0) + 1);
  }

  // 计算重复率
  let duplicateCount = 0;
  for (const count of shotCounts.values()) {
    if (count > 1) {
      duplicateCount += count - 1;
    }
  }

  // 唯一性 = 100 - (重复数 / 总数) * 100
  const uniqueness = Math.max(0, 100 - (duplicateCount / materials.length) * 100);

  return Math.round(uniqueness);
}

/**
 * 生成组合标签
 */
function generateTag(uniqueness: number): string {
  if (uniqueness >= 90) return '完全不重复';
  if (uniqueness >= 70) return '极低重复率';
  if (uniqueness >= 50) return '低重复率';
  if (uniqueness >= 30) return '普通';
  return '高重复率';
}

/**
 * 生成组合唯一ID
 */
function generateComboId(materials: Material[]): string {
  const materialIds = materials.map(m => m.id).join('_');
  const hash = simpleHash(materialIds);
  return `combo_${hash}`;
}

/**
 * 简单哈希函数
 */
function simpleHash(str: string): string {
  let hash = 0;
  for (let i = 0; i < str.length; i++) {
    const char = str.charCodeAt(i);
    hash = ((hash << 5) - hash + char) | 0;
  }
  return Math.abs(hash).toString(36).substring(0, 8);
}

/**
 * 从服务器数据转换素材
 */
export function convertServerMaterials(
  serverMaterials: Array<{
    id: string;
    shot_id: string;
    duration_seconds?: number;
    duration?: string;
    original_name?: string;
  }>
): Material[] {
  return serverMaterials.map(m => ({
    id: m.id,
    shotId: m.shot_id,
    duration: m.duration_seconds || parseDuration(m.duration) || 3,
    name: m.original_name || m.id,
  }));
}

/**
 * 解析时长字符串（如 "0:05" -> 5）
 */
function parseDuration(durationStr?: string): number {
  if (!durationStr) return 0;

  const parts = durationStr.split(':').map(Number);
  if (parts.length === 2) {
    return parts[0] * 60 + parts[1];
  }
  if (parts.length === 3) {
    return parts[0] * 3600 + parts[1] * 60 + parts[2];
  }

  return Number(durationStr) || 0;
}

/**
 * 按镜头分组素材
 */
export function groupMaterialsByShot(
  materials: Material[]
): Map<string, Material[]> {
  const map = new Map<string, Material[]>();

  for (const material of materials) {
    const list = map.get(material.shotId) || [];
    list.push(material);
    map.set(material.shotId, list);
  }

  return map;
}

/**
 * 估算组合总数
 */
export function estimateCombinationCount(
  shots: Shot[],
  materialsMap: Map<string, Material[]>
): number {
  let total = 1;

  for (const shot of shots) {
    const materials = materialsMap.get(shot.id) || [];
    total *= Math.max(1, materials.length);
  }

  return total;
}

/**
 * 筛选组合
 */
export function filterCombinations(
  combinations: Combination[],
  filter: string
): Combination[] {
  if (filter === '全部' || !filter) {
    return combinations;
  }

  return combinations.filter(c => c.tag === filter);
}

/**
 * 排序组合
 */
export function sortCombinations(
  combinations: Combination[],
  sortBy: 'uniqueness' | 'duration' | 'default' = 'default'
): Combination[] {
  const sorted = [...combinations];

  switch (sortBy) {
    case 'uniqueness':
      sorted.sort((a, b) => b.uniqueness - a.uniqueness);
      break;
    case 'duration':
      sorted.sort((a, b) => a.duration - b.duration);
      break;
    default:
      // 默认排序：唯一性优先，其次时长
      sorted.sort((a, b) => {
        if (b.uniqueness !== a.uniqueness) {
          return b.uniqueness - a.uniqueness;
        }
        return a.duration - b.duration;
      });
  }

  return sorted;
}
