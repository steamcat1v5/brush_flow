import { useEffect, useRef } from 'react';

/**
 * 定时轮询 Hook
 * @param callback 轮询回调函数
 * @param intervalMs 轮询间隔（毫秒）
 * @param deps 依赖数组，变化时重新启动轮询
 */
export function usePolling(callback: () => void, intervalMs: number, deps: unknown[] = []) {
  const callbackRef = useRef(callback);
  callbackRef.current = callback;

  useEffect(() => {
    // 立即执行一次
    callbackRef.current();
    const timer = setInterval(() => callbackRef.current(), intervalMs);
    return () => clearInterval(timer);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps);
}
