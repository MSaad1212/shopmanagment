import os
import sys
from decimal import Decimal
from fastapi.templating import Jinja2Templates

class MockItem:
    def __init__(self, brand, pattern, size):
        self.brand = brand
        self.pattern = pattern
        self.size = size

class MockLineItem:
    def __init__(self, brand, pattern, size, quantity, unit_price, subtotal):
        self.item = MockItem(brand, pattern, size)
        self.quantity = quantity
        self.unit_price = unit_price
        self.subtotal = subtotal

class MockCustomer:
    def __init__(self, name, phone, is_walk_in):
        self.name = name
        self.phone = phone
        self.is_walk_in = is_walk_in

class MockSale:
    def __init__(self):
        self.invoice_no = "SINV-1002"
        self.date = "2026-08-23"
        self.created_at = None
        self.customer = MockCustomer("Test Customer", "0333-1234567", False)
        self.total_amount = Decimal("1500.00")
        self.discount = Decimal("100.00")
        self.amount_received = Decimal("1400.00")
        self.balance = Decimal("0.00")
        self.items = [
            MockLineItem("Yokohama", "Bluearth", "175/65 R14", 2, Decimal("700.00"), Decimal("1400.00")),
            MockLineItem("Local Part", None, "Standard", 1, Decimal("100.00"), Decimal("100.00"))
        ]

def test_render():
    try:
        sale = MockSale()
        previous_balance = Decimal("200.00")
        final_balance = Decimal("200.00")
        
        templates = Jinja2Templates(directory="app/templates")
        html_content = templates.get_template("print/sale_pos.html").render({
            "sale": sale,
            "shop_name": "New Metro Traders",
            "shop_tagline": "Test Tagline",
            "previous_balance": previous_balance,
            "final_balance": final_balance,
            "today": "23-aug-2026",
            "request": None
        })
        
        with open("scratch/output.html", "w", encoding="utf-8") as f:
            f.write(html_content)
        print("HTML written to scratch/output.html")
    except Exception as e:
        print("Failed:", e)

if __name__ == "__main__":
    test_render()
