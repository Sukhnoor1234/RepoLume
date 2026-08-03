export interface Order {
  id: OrderId;
  total: number;
}

export type OrderId = string;

export enum OrderStatus {
  Open,
  Complete,
}
