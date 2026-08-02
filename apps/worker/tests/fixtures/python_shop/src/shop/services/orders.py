from decimal import Decimal

from ..models.order import Order


class OrderService:
    def create(self, total: Decimal) -> Order:
        return Order(total=total)


def create_order(total: str) -> dict[str, str]:
    order = OrderService().create(Decimal(total))
    return {"total": str(order.total)}
