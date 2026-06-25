/**
 * 将字节数格式化为人类可读的字符串
 */
export function formatBytes(bytes: number): string {
  if (bytes < 1024) return bytes + ' B';
  if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB';
  if (bytes < 1024 * 1024 * 1024) return (bytes / (1024 * 1024)).toFixed(1) + ' MB';
  return (bytes / (1024 * 1024 * 1024)).toFixed(2) + ' GB';
}

/**
 * 将每秒字节数格式化为速度字符串
 */
export function formatSpeed(bytesPerSec: number): string {
  return formatBytes(bytesPerSec) + '/s';
}
