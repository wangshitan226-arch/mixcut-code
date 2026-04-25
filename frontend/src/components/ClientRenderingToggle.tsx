/**
 * 客户端渲染开关组件
 * 显示设备能力检测结果，允许用户启用/禁用客户端渲染
 */

import React from 'react';
import { Cpu, Smartphone, AlertTriangle, CheckCircle, XCircle, Zap } from 'lucide-react';
import { DeviceCapability } from '../utils/deviceCapability';

interface ClientRenderingToggleProps {
  capability: DeviceCapability | null;
  isEnabled: boolean;
  isForced: boolean;
  onEnable: () => void;
  onDisable: () => void;
  onForceEnable: () => void;
}

export default function ClientRenderingToggle({
  capability,
  isEnabled,
  isForced,
  onEnable,
  onDisable,
  onForceEnable,
}: ClientRenderingToggleProps) {
  if (!capability) {
    return (
      <div className="bg-gray-50 rounded-lg p-4 animate-pulse">
        <div className="h-4 bg-gray-200 rounded w-3/4 mb-2"></div>
        <div className="h-4 bg-gray-200 rounded w-1/2"></div>
      </div>
    );
  }

  const canUse = capability.canUseClientRendering;
  const isMobile = capability.isMobile;

  return (
    <div className={`rounded-lg p-4 ${isEnabled ? 'bg-green-50 border border-green-200' : 'bg-gray-50 border border-gray-200'}`}>
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2">
          <Cpu size={20} className={isEnabled ? 'text-green-600' : 'text-gray-500'} />
          <h3 className="font-semibold text-gray-900">客户端渲染</h3>
          {isEnabled && (
            <span className="px-2 py-0.5 bg-green-100 text-green-700 text-xs rounded-full">
              已启用
            </span>
          )}
          {isForced && (
            <span className="px-2 py-0.5 bg-orange-100 text-orange-700 text-xs rounded-full">
              强制启用
            </span>
          )}
        </div>
        
        {/* 开关按钮 */}
        {canUse && !isForced && (
          <button
            onClick={isEnabled ? onDisable : onEnable}
            className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors ${
              isEnabled ? 'bg-green-600' : 'bg-gray-300'
            }`}
          >
            <span
              className={`inline-block h-4 w-4 transform rounded-full bg-white transition-transform ${
                isEnabled ? 'translate-x-6' : 'translate-x-1'
              }`}
            />
          </button>
        )}
      </div>

      {/* 设备信息 */}
      <div className="grid grid-cols-2 gap-2 text-sm mb-3">
        <div className="flex items-center gap-1 text-gray-600">
          <Smartphone size={14} />
          <span>性能等级: {capability.performanceLevel}</span>
        </div>
        <div className="text-gray-600">
          内存: {capability.memoryGB}GB
        </div>
        <div className="text-gray-600">
          CPU: {capability.cpuCores}核
        </div>
        <div className="text-gray-600">
          最大文件: {(capability.maxFileSize / 1024 / 1024).toFixed(0)}MB
        </div>
      </div>

      {/* 不支持原因 */}
      {!canUse && capability.unsupportedReasons.length > 0 && (
        <div className="bg-red-50 rounded p-2 mb-3">
          <div className="flex items-center gap-1 text-red-700 text-sm mb-1">
            <AlertTriangle size={14} />
            <span>不支持的原因:</span>
          </div>
          <ul className="text-xs text-red-600 space-y-1">
            {capability.unsupportedReasons.map((reason, i) => (
              <li key={i}>• {reason}</li>
            ))}
          </ul>
        </div>
      )}

      {/* 移动端强制启用 */}
      {isMobile && !canUse && (
        <div className="bg-orange-50 rounded p-2 mb-3">
          <div className="flex items-center gap-1 text-orange-700 text-sm mb-1">
            <Zap size={14} />
            <span>移动端提示</span>
          </div>
          <p className="text-xs text-orange-600 mb-2">
            当前设备性能可能不足，强制启用可能导致卡顿、发热。
          </p>
          <button
            onClick={onForceEnable}
            className="px-3 py-1 bg-orange-600 text-white text-xs rounded hover:bg-orange-700"
          >
            强制启用
          </button>
        </div>
      )}

      {/* 功能支持状态 */}
      <div className="grid grid-cols-3 gap-2 text-xs">
        <div className={`flex items-center gap-1 ${capability.supportsFFmpeg ? 'text-green-600' : 'text-red-500'}`}>
          {capability.supportsFFmpeg ? <CheckCircle size={12} /> : <XCircle size={12} />}
          <span>FFmpeg</span>
        </div>
        <div className={`flex items-center gap-1 ${capability.supportsOPFS ? 'text-green-600' : 'text-red-500'}`}>
          {capability.supportsOPFS ? <CheckCircle size={12} /> : <XCircle size={12} />}
          <span>OPFS</span>
        </div>
        <div className={`flex items-center gap-1 ${capability.supportsWebCodecs ? 'text-green-600' : 'text-red-500'}`}>
          {capability.supportsWebCodecs ? <CheckCircle size={12} /> : <XCircle size={12} />}
          <span>WebCodecs</span>
        </div>
      </div>
    </div>
  );
}
