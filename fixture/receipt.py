def render_receipt(item_count: int, subtotal_cents: int) -> str:
    total_cents = subtotal_cents + (175 if item_count else 0)
    dollars, cents = divmod(total_cents, 100)
    return f"{item_count} items: ${dollars}.{cents:02d}"
