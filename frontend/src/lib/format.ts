/** 将 ISO 时间字符串格式化为 "YYYY-MM-DD HH:mm"（解析失败时原样返回） */
export function formatSavedAt(savedAt: string): string {
  try {
    const d = new Date(savedAt);
    if (Number.isNaN(d.getTime())) return savedAt;
    const pad = (n: number) => String(n).padStart(2, "0");
    return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(
      d.getHours()
    )}:${pad(d.getMinutes())}`;
  } catch {
    return savedAt;
  }
}
