const VN = 'Asia/Ho_Chi_Minh';

/** "14:35:07" */
export const toVNTime = (iso: string) =>
  new Date(iso).toLocaleTimeString('vi-VN', { timeZone: VN, hour12: false });

/** "27/06/2026 14:35:07" */
export const toVNDateTime = (iso: string) =>
  new Date(iso).toLocaleString('vi-VN', { timeZone: VN, hour12: false });

/** Đồng hồ realtime — dùng cho TopBar */
export const nowVN = () =>
  new Date().toLocaleTimeString('vi-VN', { timeZone: VN, hour12: false });
