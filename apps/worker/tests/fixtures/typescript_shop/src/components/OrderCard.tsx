import React from "react";

interface Props {
  total: number;
}

export function OrderCard({ total }: Props) {
  return <article>Order total: {total}</article>;
}
