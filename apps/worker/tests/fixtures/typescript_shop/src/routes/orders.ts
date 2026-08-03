import { Router } from "express";

import { createOrder } from "../services/orders.js";

export const orderRouter = Router();

@Controller("/orders")
export class OrderController {
  create(total: number) {
    return createOrder(total);
  }
}
