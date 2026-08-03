import express from "express";
import { orderRouter } from "./routes/orders.js";

const config = require("./config");

export const app = express();
app.use(config.basePath, orderRouter);

export function createApp() {
  return app;
}

export async function start(): Promise<void> {
  app.listen(config.port);
}

if (require.main === module) {
  void start();
}
