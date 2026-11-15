import tkinter as tk
from tkinter import ttk, messagebox
import sqlite3
import hashlib
from pathlib import Path
from datetime import datetime

DB_PATH = Path(__file__).with_name("radhe_restaurant.db")
DEFAULT_MENU = [
    ("Pizza", 40.0),
    ("Pasta", 50.0),
    ("Burger", 60.0),
    ("Salad", 70.0),
    ("Coffee", 80.0),
]


def password_hash(password):
    return hashlib.sha256(password.encode("utf-8")).hexdigest()


class RestaurantDB:
    def __init__(self, path=DB_PATH):
        self.conn = sqlite3.connect(path)
        self.conn.row_factory = sqlite3.Row
        self.setup()

    def setup(self):
        cur = self.conn.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                role TEXT NOT NULL DEFAULT 'admin'
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS menu_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE NOT NULL,
                price REAL NOT NULL CHECK(price >= 0)
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS orders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at TEXT NOT NULL,
                total REAL NOT NULL
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS order_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                order_id INTEGER NOT NULL,
                item_name TEXT NOT NULL,
                quantity INTEGER NOT NULL,
                unit_price REAL NOT NULL,
                line_total REAL NOT NULL,
                FOREIGN KEY(order_id) REFERENCES orders(id)
            )
        """)
        cur.execute("INSERT OR IGNORE INTO users(username, password_hash, role) VALUES (?, ?, ?)",
                    ("admin", password_hash("admin123"), "admin"))
        cur.execute("SELECT COUNT(*) AS n FROM menu_items")
        if cur.fetchone()["n"] == 0:
            cur.executemany("INSERT INTO menu_items(name, price) VALUES (?, ?)", DEFAULT_MENU)
        self.conn.commit()

    def authenticate(self, username, password):
        row = self.conn.execute(
            "SELECT * FROM users WHERE username=? AND password_hash=?",
            (username.strip(), password_hash(password))
        ).fetchone()
        return row

    def menu(self):
        return self.conn.execute("SELECT * FROM menu_items ORDER BY name").fetchall()

    def add_menu_item(self, name, price):
        self.conn.execute("INSERT INTO menu_items(name, price) VALUES (?, ?)",
                          (name.strip(), price))
        self.conn.commit()

    def update_menu_item(self, item_id, name, price):
        self.conn.execute("UPDATE menu_items SET name=?, price=? WHERE id=?",
                          (name.strip(), price, item_id))
        self.conn.commit()

    def delete_menu_item(self, item_id):
        self.conn.execute("DELETE FROM menu_items WHERE id=?", (item_id,))
        self.conn.commit()

    def save_order(self, cart):
        total = sum(item["quantity"] * item["price"] for item in cart)
        cur = self.conn.cursor()
        cur.execute("INSERT INTO orders(created_at, total) VALUES (?, ?)",
                    (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), total))
        order_id = cur.lastrowid
        cur.executemany("""
            INSERT INTO order_items(order_id, item_name, quantity, unit_price, line_total)
            VALUES (?, ?, ?, ?, ?)
        """, [
            (order_id, item["name"], item["quantity"], item["price"],
             item["quantity"] * item["price"]) for item in cart
        ])
        self.conn.commit()
        return order_id, total

    def stats(self):
        return {
            "orders": self.conn.execute("SELECT COUNT(*) FROM orders").fetchone()[0],
            "sales": self.conn.execute("SELECT COALESCE(SUM(total), 0) FROM orders").fetchone()[0],
            "items": self.conn.execute("SELECT COUNT(*) FROM menu_items").fetchone()[0],
        }

    def order_history(self):
        return self.conn.execute(
            "SELECT id, created_at, total FROM orders ORDER BY id DESC"
        ).fetchall()

    def order_details(self, order_id):
        return self.conn.execute(
            "SELECT item_name, quantity, unit_price, line_total FROM order_items WHERE order_id=?",
            (order_id,)
        ).fetchall()

    def close(self):
        self.conn.close()


class RestaurantApp:
    BG = "#f1f5f9"
    NAVY = "#4E61A0"
    BLUE = "#2563eb"
    GREEN = "#16a34a"
    RED = "#dc2626"
    TEXT = "#0f172a"

    def __init__(self, root):
        self.root = root
        self.root.title("Radhe Restaurant | Management System")
        self.root.geometry("1060x700")
        self.root.minsize(900, 620)
        self.root.configure(bg=self.BG)
        self.db = RestaurantDB()
        self.cart = []
        self.current_user = None
        self.selected_menu_id = None
        self.show_login()
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

    def clear(self):
        for widget in self.root.winfo_children():
            widget.destroy()

    def style(self):
        style = ttk.Style()
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass
        style.configure("Treeview", rowheight=30, font=("Segoe UI", 10),
                        background="white", fieldbackground="white")
        style.configure("Treeview.Heading", font=("Segoe UI", 10, "bold"),
                        background="#e2e8f0", foreground=self.TEXT)
        style.map("Treeview", background=[("selected", "#dbeafe")],
                  foreground=[("selected", self.TEXT)])
        style.configure("TCombobox", padding=6)

    def button(self, parent, text, command, color=None):
        return tk.Button(parent, text=text, command=command,
                         font=("Segoe UI", 10, "bold"),
                         bg=color or self.BLUE, fg="white",
                         activebackground=color or self.BLUE,
                         activeforeground="white", relief="flat",
                         cursor="hand2", padx=14, pady=9)

    def show_login(self):
        self.clear()
        self.style()
        wrapper = tk.Frame(self.root, bg=self.BG)
        wrapper.pack(expand=True)
        card = tk.Frame(wrapper, bg="white", padx=42, pady=36,
                        highlightbackground="#dbe2ee", highlightthickness=1)
        card.pack()
        tk.Label(card, text="RADHE RESTAURANT", bg="white", fg=self.NAVY,
                 font=("Segoe UI", 23, "bold")).pack()
        tk.Label(card, text="Admin Login", bg="white", fg="#64748b",
                 font=("Segoe UI", 11)).pack(pady=(4, 24))

        tk.Label(card, text="Username", bg="white", fg=self.TEXT,
                 font=("Segoe UI", 10, "bold")).pack(anchor="w")
        self.username_entry = ttk.Entry(card, width=34, font=("Segoe UI", 11))
        self.username_entry.pack(ipady=7, pady=(5, 15))
        self.username_entry.insert(0, "admin")

        tk.Label(card, text="Password", bg="white", fg=self.TEXT,
                 font=("Segoe UI", 10, "bold")).pack(anchor="w")
        self.password_entry = ttk.Entry(card, width=34, show="•",
                                         font=("Segoe UI", 11))
        self.password_entry.pack(ipady=7, pady=(5, 20))
        self.password_entry.bind("<Return>", lambda _event: self.login())
        self.button(card, "LOGIN", self.login, self.BLUE).pack(fill="x")
        tk.Label(card, text="First login: admin  |  Password: admin123",
                 bg="white", fg="#64748b", font=("Segoe UI", 9)).pack(pady=(18, 0))
        self.username_entry.focus_set()

    def login(self):
        user = self.db.authenticate(self.username_entry.get(), self.password_entry.get())
        if not user:
            messagebox.showerror("Login failed", "Username or password is incorrect.")
            return
        self.current_user = user["username"]
        self.show_dashboard()

    def show_dashboard(self):
        self.clear()
        self.style()

        header = tk.Frame(self.root, bg=self.NAVY, padx=22, pady=15)
        header.pack(fill="x")
        tk.Label(header, text="RADHE RESTAURANT", bg=self.NAVY, fg="white",
                 font=("Segoe UI", 20, "bold")).pack(side="left")
        tk.Label(header, text=f"Logged in: {self.current_user}",
                 bg=self.NAVY, fg="#cbd5e1", font=("Segoe UI", 10)).pack(side="right")

        nav = tk.Frame(self.root, bg="#dbeafe", padx=14, pady=9)
        nav.pack(fill="x")
        for label, page in [
            ("Dashboard", self.dashboard_page),
            ("New Order / Billing", self.order_page),
            ("Menu Management", self.menu_page),
            ("Order History", self.history_page),
        ]:
            tk.Button(nav, text=label, command=page, bg="#dbeafe", fg=self.NAVY,
                      activebackground="#bfdbfe", relief="flat",
                      font=("Segoe UI", 10, "bold"), padx=13, pady=7,
                      cursor="hand2").pack(side="left", padx=3)
        self.button(nav, "Logout", self.logout, self.RED).pack(side="right")
        self.body = tk.Frame(self.root, bg=self.BG, padx=22, pady=20)
        self.body.pack(fill="both", expand=True)
        self.dashboard_page()

    def page_title(self, title, subtitle=""):
        for widget in self.body.winfo_children():
            widget.destroy()
        tk.Label(self.body, text=title, bg=self.BG, fg=self.NAVY,
                 font=("Segoe UI", 21, "bold")).pack(anchor="w")
        if subtitle:
            tk.Label(self.body, text=subtitle, bg=self.BG, fg="#64748b",
                     font=("Segoe UI", 10)).pack(anchor="w", pady=(2, 15))

    def dashboard_page(self):
        self.page_title("Admin Dashboard", "Restaurant performance overview")
        stats = self.db.stats()
        cards = tk.Frame(self.body, bg=self.BG)
        cards.pack(fill="x", pady=8)
        for title, value, color in [
            ("Total Orders", str(stats["orders"]), self.BLUE),
            ("Total Sales", f"Rs. {stats['sales']:.2f}", self.GREEN),
            ("Menu Items", str(stats["items"]), "#7c3aed"),
        ]:
            card = tk.Frame(cards, bg="white", padx=22, pady=20,
                            highlightbackground="#dbe2ee", highlightthickness=1)
            card.pack(side="left", fill="x", expand=True, padx=(0, 12))
            tk.Label(card, text=title, bg="white", fg="#64748b",
                     font=("Segoe UI", 10, "bold")).pack(anchor="w")
            tk.Label(card, text=value, bg="white", fg=color,
                     font=("Segoe UI", 23, "bold")).pack(anchor="w", pady=(7, 0))

        tk.Label(self.body, text="Recent Orders", bg=self.BG, fg=self.TEXT,
                 font=("Segoe UI", 14, "bold")).pack(anchor="w", pady=(22, 9))
        table = ttk.Treeview(self.body, columns=("id", "date", "total"),
                             show="headings", height=8)
        for col, heading, width in [
            ("id", "Order ID", 100), ("date", "Date & Time", 300),
            ("total", "Total (Rs.)", 180)
        ]:
            table.heading(col, text=heading)
            table.column(col, width=width, anchor="center")
        table.pack(fill="x")
        for order in self.db.order_history()[:8]:
            table.insert("", "end", values=(order["id"], order["created_at"],
                                            f'{order["total"]:.2f}'))

    def order_page(self):
        self.page_title("New Order & Billing", "Add food items, choose quantities and generate a bill")
        area = tk.Frame(self.body, bg=self.BG)
        area.pack(fill="both", expand=True)

        left = tk.Frame(area, bg="white", padx=18, pady=18,
                        highlightbackground="#dbe2ee", highlightthickness=1)
        left.pack(side="left", fill="y", padx=(0, 16))
        tk.Label(left, text="Add Item", bg="white", fg=self.NAVY,
                 font=("Segoe UI", 15, "bold")).pack(anchor="w", pady=(0, 14))
        tk.Label(left, text="Food item", bg="white").pack(anchor="w")
        menu = self.db.menu()
        self.order_menu_map = {row["name"]: row["price"] for row in menu}
        self.order_item_var = tk.StringVar(value=menu[0]["name"] if menu else "")
        self.order_combo = ttk.Combobox(left, textvariable=self.order_item_var,
                                        values=list(self.order_menu_map), state="readonly",
                                        width=23)
        self.order_combo.pack(fill="x", ipady=5, pady=(5, 14))
        tk.Label(left, text="Quantity", bg="white").pack(anchor="w")
        self.quantity_var = tk.StringVar(value="1")
        ttk.Entry(left, textvariable=self.quantity_var, width=25).pack(fill="x", ipady=5, pady=(5, 14))
        self.button(left, "Add to Cart", self.add_to_cart, self.GREEN).pack(fill="x")
        self.button(left, "Clear Cart", self.clear_cart, self.RED).pack(fill="x", pady=(9, 0))

        right = tk.Frame(area, bg="white", padx=18, pady=18,
                         highlightbackground="#dbe2ee", highlightthickness=1)
        right.pack(side="left", fill="both", expand=True)
        tk.Label(right, text="Current Cart", bg="white", fg=self.NAVY,
                 font=("Segoe UI", 15, "bold")).pack(anchor="w", pady=(0, 12))
        self.cart_table = ttk.Treeview(right, columns=("item", "qty", "price", "subtotal"),
                                       show="headings", height=11)
        for col, heading, width in [
            ("item", "Item", 170), ("qty", "Qty", 60),
            ("price", "Unit Price", 100), ("subtotal", "Subtotal", 110)
        ]:
            self.cart_table.heading(col, text=heading)
            self.cart_table.column(col, width=width, anchor="center")
        self.cart_table.pack(fill="both", expand=True)
        self.cart_total_label = tk.Label(right, text="Total: Rs. 0.00",
                                         bg="white", fg=self.NAVY,
                                         font=("Segoe UI", 17, "bold"))
        self.cart_total_label.pack(anchor="e", pady=12)
        self.button(right, "Remove Selected", self.remove_cart_item, "#64748b").pack(side="left")
        self.button(right, "Generate Bill & Save Order", self.checkout, self.BLUE).pack(side="right")
        self.refresh_cart()

    def add_to_cart(self):
        name = self.order_item_var.get()
        try:
            qty = int(self.quantity_var.get())
            if qty < 1:
                raise ValueError
        except ValueError:
            messagebox.showwarning("Invalid quantity", "Enter a whole number greater than zero.")
            return
        if name not in self.order_menu_map:
            messagebox.showwarning("No menu item", "Add a menu item first.")
            return
        for item in self.cart:
            if item["name"] == name:
                item["quantity"] += qty
                break
        else:
            self.cart.append({"name": name, "price": self.order_menu_map[name], "quantity": qty})
        self.refresh_cart()

    def refresh_cart(self):
        if not hasattr(self, "cart_table") or not self.cart_table.winfo_exists():
            return
        for row in self.cart_table.get_children():
            self.cart_table.delete(row)
        total = 0
        for index, item in enumerate(self.cart):
            subtotal = item["price"] * item["quantity"]
            total += subtotal
            self.cart_table.insert("", "end", iid=str(index),
                                   values=(item["name"], item["quantity"],
                                           f'{item["price"]:.2f}', f"{subtotal:.2f}"))
        self.cart_total_label.config(text=f"Total: Rs. {total:.2f}")

    def remove_cart_item(self):
        selected = self.cart_table.selection()
        if not selected:
            messagebox.showinfo("Select item", "Select a cart item to remove.")
            return
        for index in sorted((int(x) for x in selected), reverse=True):
            self.cart.pop(index)
        self.refresh_cart()

    def clear_cart(self):
        self.cart.clear()
        self.refresh_cart()

    def checkout(self):
        if not self.cart:
            messagebox.showwarning("Empty cart", "Add at least one item before checkout.")
            return
        order_id, total = self.db.save_order(self.cart)
        lines = ["RADHE RESTAURANT", f"Order #{order_id}", "-" * 34]
        for item in self.cart:
            lines.append(f'{item["name"]} x {item["quantity"]}  Rs. {item["price"] * item["quantity"]:.2f}')
        lines.extend(["-" * 34, f"TOTAL: Rs. {total:.2f}", "", "Thank you! Visit again."])
        messagebox.showinfo("Bill generated", "\n".join(lines))
        self.cart.clear()
        self.order_page()

    def menu_page(self):
        self.page_title("Menu Management", "Add, edit or delete restaurant menu items")
        form = tk.Frame(self.body, bg="white", padx=16, pady=16,
                        highlightbackground="#dbe2ee", highlightthickness=1)
        form.pack(fill="x", pady=(0, 15))
        tk.Label(form, text="Item name", bg="white").grid(row=0, column=0, sticky="w")
        self.menu_name_var = tk.StringVar()
        ttk.Entry(form, textvariable=self.menu_name_var, width=28).grid(row=1, column=0, padx=(0, 12), pady=6)
        tk.Label(form, text="Price (Rs.)", bg="white").grid(row=0, column=1, sticky="w")
        self.menu_price_var = tk.StringVar()
        ttk.Entry(form, textvariable=self.menu_price_var, width=18).grid(row=1, column=1, padx=(0, 12), pady=6)
        self.button(form, "Add Item", self.add_menu_item, self.GREEN).grid(row=1, column=2, padx=4)
        self.button(form, "Update Selected", self.update_menu_item, self.BLUE).grid(row=1, column=3, padx=4)
        self.button(form, "Delete Selected", self.delete_menu_item, self.RED).grid(row=1, column=4, padx=4)

        self.menu_table = ttk.Treeview(self.body, columns=("id", "name", "price"),
                                       show="headings", height=12)
        for col, heading, width in [("id", "ID", 70), ("name", "Item Name", 300),
                                    ("price", "Price (Rs.)", 160)]:
            self.menu_table.heading(col, text=heading)
            self.menu_table.column(col, width=width, anchor="center")
        self.menu_table.pack(fill="both", expand=True)
        self.menu_table.bind("<<TreeviewSelect>>", self.select_menu_item)
        self.refresh_menu()

    def refresh_menu(self):
        for row in self.menu_table.get_children():
            self.menu_table.delete(row)
        for item in self.db.menu():
            self.menu_table.insert("", "end", iid=str(item["id"]),
                                   values=(item["id"], item["name"], f'{item["price"]:.2f}'))

    def select_menu_item(self, _event=None):
        selected = self.menu_table.selection()
        if not selected:
            return
        values = self.menu_table.item(selected[0], "values")
        self.selected_menu_id = int(values[0])
        self.menu_name_var.set(values[1])
        self.menu_price_var.set(values[2])

    def add_menu_item(self):
        name = self.menu_name_var.get().strip()
        try:
            price = float(self.menu_price_var.get())
            if not name or price < 0:
                raise ValueError
            self.db.add_menu_item(name, price)
        except ValueError:
            messagebox.showwarning("Invalid input", "Enter an item name and a valid non-negative price.")
            return
        except sqlite3.IntegrityError:
            messagebox.showerror("Duplicate item", "That menu item already exists.")
            return
        self.menu_name_var.set("")
        self.menu_price_var.set("")
        self.refresh_menu()

    def update_menu_item(self):
        if not self.selected_menu_id:
            messagebox.showinfo("Select item", "Select a menu item to update.")
            return
        name = self.menu_name_var.get().strip()
        try:
            price = float(self.menu_price_var.get())
            if not name or price < 0:
                raise ValueError
            self.db.update_menu_item(self.selected_menu_id, name, price)
        except ValueError:
            messagebox.showwarning("Invalid input", "Enter an item name and a valid non-negative price.")
            return
        except sqlite3.IntegrityError:
            messagebox.showerror("Duplicate item", "That menu item already exists.")
            return
        self.selected_menu_id = None
        self.menu_name_var.set("")
        self.menu_price_var.set("")
        self.refresh_menu()

    def delete_menu_item(self):
        if not self.selected_menu_id:
            messagebox.showinfo("Select item", "Select a menu item to delete.")
            return
        if messagebox.askyesno("Delete item", "Delete the selected menu item?"):
            self.db.delete_menu_item(self.selected_menu_id)
            self.selected_menu_id = None
            self.menu_name_var.set("")
            self.menu_price_var.set("")
            self.refresh_menu()

    def history_page(self):
        self.page_title("Order History", "All saved orders from the SQLite database")
        self.history_table = ttk.Treeview(self.body, columns=("id", "date", "total"),
                                          show="headings", height=13)
        for col, heading, width in [
            ("id", "Order ID", 100), ("date", "Date & Time", 300),
            ("total", "Total (Rs.)", 180)
        ]:
            self.history_table.heading(col, text=heading)
            self.history_table.column(col, width=width, anchor="center")
        self.history_table.pack(fill="both", expand=True)
        self.button(self.body, "View Selected Bill Details", self.view_order).pack(anchor="e", pady=12)
        for order in self.db.order_history():
            self.history_table.insert("", "end", iid=str(order["id"]),
                                      values=(order["id"], order["created_at"],
                                              f'{order["total"]:.2f}'))

    def view_order(self):
        selected = self.history_table.selection()
        if not selected:
            messagebox.showinfo("Select order", "Select an order first.")
            return
        order_id = int(selected[0])
        details = self.db.order_details(order_id)
        lines = [f"RADHE RESTAURANT - Order #{order_id}", "-" * 34]
        for item in details:
            lines.append(f'{item["item_name"]} x {item["quantity"]}  Rs. {item["line_total"]:.2f}')
        total = sum(item["line_total"] for item in details)
        lines.extend(["-" * 34, f"TOTAL: Rs. {total:.2f}"])
        messagebox.showinfo("Order details", "\n".join(lines))

    def logout(self):
        self.cart.clear()
        self.current_user = None
        self.show_login()

    def on_close(self):
        self.db.close()
        self.root.destroy()


if __name__ == "__main__":
    root = tk.Tk()
    app = RestaurantApp(root)
    root.mainloop()
