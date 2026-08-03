import React from "react";

import { Client } from "./service.js";

export function main() {
  return React.createElement("main", null, new Client().name);
}
