import { format, isToday, isThisYear, parseISO } from 'date-fns';

export function formatEmailDate(dateStr: string | null): string {
  if (!dateStr) return '';
  try {
    const date = parseISO(dateStr);
    if (isToday(date)) return format(date, 'h:mm a');
    if (isThisYear(date)) return format(date, 'MMM d');
    return format(date, 'MMM d, yyyy');
  } catch {
    return dateStr;
  }
}

export function formatFullDate(dateStr: string | null): string {
  if (!dateStr) return '';
  try {
    const date = parseISO(dateStr);
    return format(date, "EEE, MMM d, yyyy 'at' h:mm a");
  } catch {
    return dateStr;
  }
}

export function formatFileSize(bytes: number): string {
  if (bytes === 0) return '0 B';
  const units = ['B', 'KB', 'MB', 'GB'];
  const i = Math.floor(Math.log(bytes) / Math.log(1024));
  return `${(bytes / Math.pow(1024, i)).toFixed(i > 0 ? 1 : 0)} ${units[i]}`;
}

export function formatSender(name: string | null, address: string | null): string {
  if (name && name.trim()) return name.trim();
  if (address) return address;
  return '(unknown)';
}

export function formatAddressList(
  addrs: { name: string; address: string }[]
): string {
  return addrs
    .map((a) => (a.name ? `${a.name} <${a.address}>` : a.address))
    .join(', ');
}
