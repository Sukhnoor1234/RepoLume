import type { Order } from "../models/order.js";

export function createOrder(total: number): Order {
  return { id: crypto.randomUUID(), total };
}
