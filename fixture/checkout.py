from receipt import render_receipt


def checkout(prices_in_cents: list[int]) -> str:
    return render_receipt(len(prices_in_cents), sum(prices_in_cents))
