"""
Restaurant Order Management System
==================================
A console prototype of a restaurant order management system.

Features
  - Menu management       : add / update / remove menu items, view by category
  - Table management      : track which tables are free or occupied
  - Order placement       : take an order for a table (with item quantities and notes)
  - Order lifecycle       : PLACED -> PREPARING -> READY -> SERVED -> PAID  (or CANCELLED)
  - Kitchen queue         : first-come-first-served list of orders being prepared
  - Billing               : subtotal, discount, GST and grand total
  - Sales report          : revenue by category and top-selling items

Run:
    python restaurant_order_system.py               # automatic demo
    python restaurant_order_system.py --interactive # menu-driven console app
"""

import argparse
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from itertools import count

GST_RATE = 0.05          # 5% tax, change as needed
CURRENCY = "Rs."


# --------------------------------------------------------------------------
# Models
# --------------------------------------------------------------------------
class OrderStatus(Enum):
    PLACED = "Placed"
    PREPARING = "Preparing"
    READY = "Ready"
    SERVED = "Served"
    PAID = "Paid"
    CANCELLED = "Cancelled"


# Which status changes are allowed
ALLOWED_TRANSITIONS = {
    OrderStatus.PLACED: {OrderStatus.PREPARING, OrderStatus.CANCELLED},
    OrderStatus.PREPARING: {OrderStatus.READY},
    OrderStatus.READY: {OrderStatus.SERVED},
    OrderStatus.SERVED: {OrderStatus.PAID},
    OrderStatus.PAID: set(),
    OrderStatus.CANCELLED: set(),
}


@dataclass
class MenuItem:
    item_id: int
    name: str
    category: str
    price: float
    prep_time: int          # minutes
    available: bool = True


@dataclass
class OrderItem:
    menu_item: MenuItem
    quantity: int
    note: str = ""

    @property
    def line_total(self):
        return self.menu_item.price * self.quantity


@dataclass
class Order:
    order_id: int
    table_no: int
    items: list
    status: OrderStatus = OrderStatus.PLACED
    discount_pct: float = 0.0
    created_at: datetime = field(default_factory=datetime.now)

    @property
    def subtotal(self):
        return sum(i.line_total for i in self.items)

    @property
    def discount(self):
        return self.subtotal * self.discount_pct / 100

    @property
    def tax(self):
        return (self.subtotal - self.discount) * GST_RATE

    @property
    def total(self):
        return self.subtotal - self.discount + self.tax

    @property
    def prep_time(self):
        """Estimated kitchen time = the slowest dish (dishes cook in parallel)."""
        return max(i.menu_item.prep_time for i in self.items)


# --------------------------------------------------------------------------
# System
# --------------------------------------------------------------------------
class RestaurantSystem:
    def __init__(self, num_tables=6):
        self.menu = {}
        self.tables = {n: None for n in range(1, num_tables + 1)}   # table -> active order id
        self.orders = {}
        self._order_ids = count(1001)
        self._item_ids = count(1)

    # ---- menu management ----
    def add_menu_item(self, name, category, price, prep_time):
        item = MenuItem(next(self._item_ids), name, category, price, prep_time)
        self.menu[item.item_id] = item
        return item

    def update_price(self, item_id, new_price):
        self.menu[item_id].price = new_price

    def set_availability(self, item_id, available):
        self.menu[item_id].available = available

    def remove_menu_item(self, item_id):
        self.menu.pop(item_id, None)

    def show_menu(self):
        print("\n" + "=" * 52)
        print("  MENU")
        print("=" * 52)
        for cat in sorted({m.category for m in self.menu.values()}):
            print(f"\n  {cat.upper()}")
            for m in self.menu.values():
                if m.category == cat:
                    tag = "" if m.available else "  (sold out)"
                    print(f"    {m.item_id:>2}. {m.name:<24}{CURRENCY} {m.price:>6.0f}{tag}")

    # ---- order placement ----
    def place_order(self, table_no, items, discount_pct=0.0):
        """items = list of (item_id, quantity) or (item_id, quantity, note)."""
        if table_no not in self.tables:
            raise ValueError(f"Table {table_no} does not exist")
        if self.tables[table_no] is not None:
            raise ValueError(f"Table {table_no} already has an active order")
        order_items = []
        for entry in items:
            item_id, qty = entry[0], entry[1]
            note = entry[2] if len(entry) > 2 else ""
            item = self.menu.get(item_id)
            if item is None:
                raise ValueError(f"Menu item {item_id} not found")
            if not item.available:
                raise ValueError(f"'{item.name}' is sold out")
            if qty < 1:
                raise ValueError("Quantity must be at least 1")
            order_items.append(OrderItem(item, qty, note))
        if not order_items:
            raise ValueError("An order needs at least one item")

        order = Order(next(self._order_ids), table_no, order_items, discount_pct=discount_pct)
        self.orders[order.order_id] = order
        self.tables[table_no] = order.order_id
        return order

    # ---- status handling ----
    def update_status(self, order_id, new_status):
        order = self.orders[order_id]
        if new_status not in ALLOWED_TRANSITIONS[order.status]:
            raise ValueError(f"Cannot move order {order_id} from "
                             f"{order.status.value} to {new_status.value}")
        order.status = new_status
        if new_status in (OrderStatus.PAID, OrderStatus.CANCELLED):
            self.tables[order.table_no] = None      # table is free again

    def cancel_order(self, order_id):
        self.update_status(order_id, OrderStatus.CANCELLED)

    # ---- kitchen ----
    def kitchen_queue(self):
        """Orders waiting for or being cooked, oldest first (FCFS)."""
        active = [o for o in self.orders.values()
                  if o.status in (OrderStatus.PLACED, OrderStatus.PREPARING)]
        return sorted(active, key=lambda o: o.created_at)

    def show_kitchen_queue(self):
        print("\n  KITCHEN QUEUE (oldest first)")
        queue = self.kitchen_queue()
        if not queue:
            print("    No pending orders")
        for o in queue:
            dishes = ", ".join(f"{i.quantity}x {i.menu_item.name}" for i in o.items)
            print(f"    #{o.order_id}  Table {o.table_no}  [{o.status.value}]  "
                  f"~{o.prep_time} min  {dishes}")

    # ---- billing ----
    def print_bill(self, order_id):
        o = self.orders[order_id]
        print("\n" + "-" * 44)
        print(f"  BILL   Order #{o.order_id}   Table {o.table_no}")
        print("-" * 44)
        for i in o.items:
            print(f"  {i.quantity} x {i.menu_item.name:<22}{CURRENCY} {i.line_total:>7.2f}")
        print("-" * 44)
        print(f"  {'Subtotal':<27}{CURRENCY} {o.subtotal:>7.2f}")
        if o.discount_pct:
            print(f"  {'Discount (' + str(int(o.discount_pct)) + '%)':<26}-{CURRENCY} {o.discount:>7.2f}")
        print(f"  {'GST (' + str(int(GST_RATE * 100)) + '%)':<27}{CURRENCY} {o.tax:>7.2f}")
        print(f"  {'TOTAL':<27}{CURRENCY} {o.total:>7.2f}")
        print("-" * 44)

    # ---- reports ----
    def sales_report(self):
        paid = [o for o in self.orders.values() if o.status == OrderStatus.PAID]
        by_category, by_item = {}, {}
        for o in paid:
            for i in o.items:
                by_category[i.menu_item.category] = by_category.get(i.menu_item.category, 0) + i.line_total
                by_item[i.menu_item.name] = by_item.get(i.menu_item.name, 0) + i.quantity
        return {
            "orders_paid": len(paid),
            "cancelled": sum(1 for o in self.orders.values() if o.status == OrderStatus.CANCELLED),
            "revenue": sum(o.total for o in paid),
            "by_category": by_category,
            "top_items": sorted(by_item.items(), key=lambda kv: kv[1], reverse=True),
        }

    def show_sales_report(self):
        r = self.sales_report()
        print("\n" + "=" * 52)
        print("  DAILY SALES REPORT")
        print("=" * 52)
        print(f"  Orders paid      : {r['orders_paid']}")
        print(f"  Orders cancelled : {r['cancelled']}")
        print(f"  Total revenue    : {CURRENCY} {r['revenue']:.2f}  (incl. GST)")
        print("\n  Sales by category (before tax and discount)")
        for cat, amt in sorted(r["by_category"].items(), key=lambda kv: kv[1], reverse=True):
            print(f"    {cat:<12}{CURRENCY} {amt:>8.2f}")
        print("\n  Top selling items (quantity)")
        for name, qty in r["top_items"][:3]:
            print(f"    {name:<24}{qty}")

    def show_tables(self):
        print("\n  TABLES: " + "  ".join(
            f"T{n}:{'busy' if o else 'free'}" for n, o in self.tables.items()))


# --------------------------------------------------------------------------
# Sample data + automatic demo
# --------------------------------------------------------------------------
def load_sample_menu(rs):
    rs.add_menu_item("Paneer Tikka", "Starter", 220, 12)         # 1
    rs.add_menu_item("Veg Spring Rolls", "Starter", 160, 10)     # 2
    rs.add_menu_item("Butter Chicken", "Main", 320, 20)          # 3
    rs.add_menu_item("Paneer Butter Masala", "Main", 260, 18)    # 4
    rs.add_menu_item("Veg Biryani", "Main", 240, 22)             # 5
    rs.add_menu_item("Garlic Naan", "Bread", 50, 6)              # 6
    rs.add_menu_item("Gulab Jamun", "Dessert", 90, 5)            # 7
    rs.add_menu_item("Masala Chai", "Beverage", 40, 4)           # 8
    rs.add_menu_item("Fresh Lime Soda", "Beverage", 70, 4)       # 9


def advance(rs, order_id, *statuses):
    for s in statuses:
        rs.update_status(order_id, s)


def run_demo():
    S = OrderStatus
    rs = RestaurantSystem(num_tables=6)
    load_sample_menu(rs)
    rs.show_menu()

    print("\n\n>>> 1. Customers place orders")
    o1 = rs.place_order(1, [(1, 2), (3, 1), (6, 4), (9, 2)])
    o2 = rs.place_order(2, [(5, 1), (8, 2, "less sugar"), (7, 1)])
    o3 = rs.place_order(3, [(4, 2), (6, 3), (7, 2), (2, 1)], discount_pct=10)
    o4 = rs.place_order(4, [(3, 1)])
    for o in (o1, o2, o3, o4):
        n = sum(i.quantity for i in o.items)
        print(f"    Order #{o.order_id} placed for table {o.table_no}: "
              f"{n} item{'s' if n != 1 else ''}")
    rs.show_tables()

    print("\n>>> 2. A customer cancels before cooking starts")
    rs.cancel_order(o4.order_id)
    print(f"    Order #{o4.order_id} -> {o4.status.value}")

    print("\n>>> 3. Kitchen queue")
    rs.show_kitchen_queue()

    print("\n>>> 4. Orders move through the lifecycle")
    advance(rs, o1.order_id, S.PREPARING, S.READY, S.SERVED, S.PAID)
    advance(rs, o2.order_id, S.PREPARING, S.READY, S.SERVED, S.PAID)
    advance(rs, o3.order_id, S.PREPARING, S.READY, S.SERVED, S.PAID)
    for o in (o1, o2, o3):
        print(f"    Order #{o.order_id} -> {o.status.value}")

    try:
        rs.update_status(o1.order_id, S.PREPARING)       # invalid on purpose
    except ValueError as e:
        print(f"    Blocked invalid change: {e}")

    print("\n>>> 5. Billing")
    rs.print_bill(o1.order_id)
    rs.print_bill(o3.order_id)

    rs.show_tables()
    rs.show_sales_report()


# --------------------------------------------------------------------------
# Interactive console app
# --------------------------------------------------------------------------
def run_interactive():
    rs = RestaurantSystem(num_tables=6)
    load_sample_menu(rs)
    actions = """
  1. Show menu            5. Show kitchen queue
  2. Place order          6. Print bill
  3. Update order status  7. Sales report
  4. Cancel order         8. Show tables
  0. Exit"""
    while True:
        print(actions)
        choice = input("Choose: ").strip()
        try:
            if choice == "1":
                rs.show_menu()
            elif choice == "2":
                table = int(input("Table number: "))
                items = []
                print("Enter items as 'item_id quantity' (blank line to finish)")
                while True:
                    line = input("  > ").strip()
                    if not line:
                        break
                    iid, qty = line.split()
                    items.append((int(iid), int(qty)))
                disc = float(input("Discount % (0 for none): ") or 0)
                o = rs.place_order(table, items, disc)
                print(f"Order #{o.order_id} placed. Estimated kitchen time: {o.prep_time} min")
            elif choice == "3":
                oid = int(input("Order id: "))
                names = [s.name for s in OrderStatus]
                new = input(f"New status {names}: ").strip().upper()
                rs.update_status(oid, OrderStatus[new])
                print("Status updated")
            elif choice == "4":
                rs.cancel_order(int(input("Order id: ")))
                print("Order cancelled")
            elif choice == "5":
                rs.show_kitchen_queue()
            elif choice == "6":
                rs.print_bill(int(input("Order id: ")))
            elif choice == "7":
                rs.show_sales_report()
            elif choice == "8":
                rs.show_tables()
            elif choice == "0":
                print("Goodbye!")
                break
            else:
                print("Invalid choice")
        except (ValueError, KeyError) as e:
            print(f"Error: {e}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Restaurant Order Management System")
    parser.add_argument("--interactive", action="store_true", help="run the menu-driven app")
    args = parser.parse_args()
    run_interactive() if args.interactive else run_demo()
