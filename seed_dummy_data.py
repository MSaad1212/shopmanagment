import os
from datetime import date
from dotenv import load_dotenv

from app.database import engine, Base, SessionLocal
from app.models import Supplier, Customer, Item
from app.services import next_code

load_dotenv()

db = SessionLocal()
try:
    if db.query(Item).count() > 0:
        print("Data already exists. Please clear the database if you want fresh dummy data.")
    else:
        print("Seeding dummy data...")
        
        # Add Suppliers
        s1 = Supplier(supplier_code=next_code(db, Supplier, "supplier_code", "SUPP"), name="Michelin Distributors", contact_person="John Doe", phone="1234567890", address="123 Industrial Park", opening_balance=0, current_balance=0)
        db.add(s1)
        db.flush()
        
        s2 = Supplier(supplier_code=next_code(db, Supplier, "supplier_code", "SUPP"), name="Bridgestone Direct", contact_person="Jane Smith", phone="0987654321", address="456 Warehouse Ave", opening_balance=5000, current_balance=5000)
        db.add(s2)
        db.flush()

        # Add Customers
        c1 = Customer(customer_code=next_code(db, Customer, "customer_code", "CUST"), name="Alice Motors", phone="555-0101", address="City Center", vehicle_info="Toyota Corolla", opening_balance=0, current_balance=0, is_walk_in=False)
        db.add(c1)
        db.flush()
        
        c2 = Customer(customer_code=next_code(db, Customer, "customer_code", "CUST"), name="Bob Logistics", phone="555-0202", address="North Highway", vehicle_info="Ford Transit", opening_balance=0, current_balance=0, is_walk_in=False)
        db.add(c2)
        db.flush()

        # Add Items
        i1 = Item(item_code=next_code(db, Item, "item_code", "MT"), brand="Landi Renzo", size="60L Cylinder", pattern="Sequential Kit", type="CNG", category="Car Gas Kit", purchase_price=45000.00, sale_price=55000.00, current_stock=50, reorder_level=10, unit="Kit")
        db.add(i1)
        db.commit()
        
        i2 = Item(item_code=next_code(db, Item, "item_code", "MT"), brand="Lovato", size="55L Cylinder", pattern="EFI Kit", type="LPG", category="Car Gas Kit", purchase_price=35000.00, sale_price=42000.00, current_stock=30, reorder_level=8, unit="Kit")
        db.add(i2)
        db.commit()
        
        i3 = Item(item_code=next_code(db, Item, "item_code", "MT"), brand="Tomasetto", size="40L Cylinder", pattern="Carburetor Kit", type="CNG", category="Car Gas Kit", purchase_price=25000.00, sale_price=32000.00, current_stock=100, reorder_level=20, unit="Kit")
        db.add(i3)
        db.flush()

        db.commit()
        print("Dummy data seeded successfully! Added 2 Suppliers, 2 Customers, and 3 Items.")
except Exception as e:
    print(f"Error: {e}")
    db.rollback()
finally:
    db.close()
