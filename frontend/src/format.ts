export const money = (n: number) =>
  new Intl.NumberFormat("vi-VN", { maximumFractionDigits: 2 }).format(n / 1e6);
export const count = (n: number) => new Intl.NumberFormat("vi-VN").format(n);
export const fullDate = (value: string) =>
  new Date(value).toLocaleDateString("vi-VN");
