/** "2025-05-13" → "2025.05.13". 형식이 다르면 원문 그대로. */
export function formatDateDots(value: string): string {
  const match = /^(\d{4})-(\d{2})-(\d{2})/.exec(value);
  return match ? `${match[1]}.${match[2]}.${match[3]}` : value;
}
