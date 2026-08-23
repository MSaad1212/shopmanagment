import os
import sys
from decimal import Decimal
from fastapi.templating import Jinja2Templates

# Create a mock Sale class
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
        self.created_at = None  # test None
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
        print(f"Testing mock render for Invoice: {sale.invoice_no}")
        
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
        print("SUCCESS: Template rendered successfully!")
        print("HTML Output Length:", len(html_content))
    except Exception as e:
        print("FAILED: Rendering failed with error:")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_render()
