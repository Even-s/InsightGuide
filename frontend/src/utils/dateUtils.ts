/**
 * Date and time utilities with proper timezone handling.
 *
 * The backend stores all dates in UTC. These utilities ensure:
 * 1. UTC dates from API are correctly parsed
 * 2. Dates are displayed in the user's local timezone
 */

/**
 * Format a UTC date string to local time.
 *
 * @param dateString - ISO 8601 date string from API (may or may not have 'Z' suffix)
 * @param options - Intl.DateTimeFormat options
 * @returns Formatted date string in local timezone
 *
 * @example
 * formatDateUTC('2026-05-26T04:51:43')  // Taiwan: 2026/05/26 12:51:43
 * formatDateUTC('2026-05-26T04:51:43Z') // Taiwan: 2026/05/26 12:51:43
 */
export function formatDateUTC(
  dateString: string,
  options?: Intl.DateTimeFormatOptions
): string {
  // Ensure the date string is treated as UTC by appending 'Z' if not present
  const dateStr = dateString.endsWith('Z') ? dateString : dateString + 'Z';

  const defaultOptions: Intl.DateTimeFormatOptions = {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    hour12: false,
  };

  return new Date(dateStr).toLocaleString('zh-TW', {
    ...defaultOptions,
    ...options,
  });
}

/**
 * Format a UTC date string to a short date format.
 *
 * @example
 * formatDateShort('2026-05-26T04:51:43Z') // 2026/05/26
 */
export function formatDateShort(dateString: string): string {
  const dateStr = dateString.endsWith('Z') ? dateString : dateString + 'Z';
  return new Date(dateStr).toLocaleDateString('zh-TW', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
  });
}

/**
 * Format a UTC date string to a time-only format.
 *
 * @example
 * formatTimeOnly('2026-05-26T04:51:43Z') // 12:51:43
 */
export function formatTimeOnly(dateString: string): string {
  const dateStr = dateString.endsWith('Z') ? dateString : dateString + 'Z';
  return new Date(dateStr).toLocaleTimeString('zh-TW', {
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    hour12: false,
  });
}

/**
 * Format a UTC date string to a relative time format.
 *
 * @example
 * formatRelativeTime('2026-05-26T04:51:43Z') // "2 hours ago", "3 days ago", etc.
 */
export function formatRelativeTime(dateString: string): string {
  const dateStr = dateString.endsWith('Z') ? dateString : dateString + 'Z';
  const date = new Date(dateStr);
  const now = new Date();
  const diffMs = now.getTime() - date.getTime();
  const diffSecs = Math.floor(diffMs / 1000);
  const diffMins = Math.floor(diffSecs / 60);
  const diffHours = Math.floor(diffMins / 60);
  const diffDays = Math.floor(diffHours / 24);

  if (diffSecs < 60) {
    return `${diffSecs} 秒前`;
  } else if (diffMins < 60) {
    return `${diffMins} 分鐘前`;
  } else if (diffHours < 24) {
    return `${diffHours} 小時前`;
  } else if (diffDays < 7) {
    return `${diffDays} 天前`;
  } else {
    return formatDateShort(dateString);
  }
}
