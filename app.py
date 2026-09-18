import streamlit as st
import sqlite3
import hashlib
from datetime import datetime

# -----------------------------
# PAGE CONFIG
# -----------------------------

st.set_page_config(
    page_title="MiniStore",
    page_icon="🛍️",
    layout="wide"
)

# -----------------------------
# DATABASE
# -----------------------------

DB = "store_new.db"

def connect_db():
    return sqlite3.connect(DB)


def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()


def init_database():
    conn = connect_db()
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            role TEXT NOT NULL
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            description TEXT,
            price REAL NOT NULL,
            inventory INTEGER NOT NULL
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL,
            total REAL NOT NULL,
            payment_method TEXT,
            created_at TEXT NOT NULL
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS order_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            order_id INTEGER NOT NULL,
            product_id INTEGER NOT NULL,
            product_name TEXT NOT NULL,
            quantity INTEGER NOT NULL,
            price REAL NOT NULL
        )
    """)

    # Demo accounts
    cur.execute(
        "INSERT OR IGNORE INTO users VALUES (?, ?, ?)",
        ("admin", hash_password("admin123"), "admin")
    )

    cur.execute(
        "INSERT OR IGNORE INTO users VALUES (?, ?, ?)",
        ("customer", hash_password("customer123"), "customer")
    )

    # Demo products
    cur.execute("SELECT COUNT(*) FROM products")

    if cur.fetchone()[0] == 0:
        products = [
            ("Wireless Headphones", "Comfortable wireless headphones", 59.99, 10),
            ("Minimal Backpack", "Everyday backpack", 39.99, 15),
            ("Desk Lamp", "Modern LED desk lamp", 24.99, 20),
            ("Water Bottle", "Reusable stainless steel bottle", 19.99, 25),
        ]

        cur.executemany("""
            INSERT INTO products
            (name, description, price, inventory)
            VALUES (?, ?, ?, ?)
        """, products)

    conn.commit()
    conn.close()


init_database()

# -----------------------------
# SESSION STATE
# -----------------------------

if "logged_in" not in st.session_state:
    st.session_state.logged_in = False

if "username" not in st.session_state:
    st.session_state.username = ""

if "role" not in st.session_state:
    st.session_state.role = ""

if "cart" not in st.session_state:
    st.session_state.cart = {}


# -----------------------------
# LOGIN
# -----------------------------

def login():
    st.title("🔐 Login")

    username = st.text_input("Username")
    password = st.text_input("Password", type="password")

    if st.button("Login"):

        conn = connect_db()
        cur = conn.cursor()

        cur.execute("""
            SELECT username, role
            FROM users
            WHERE username = ?
            AND password = ?
        """, (username, hash_password(password)))

        user = cur.fetchone()

        conn.close()

        if user:
            st.session_state.logged_in = True
            st.session_state.username = user[0]
            st.session_state.role = user[1]

            st.success("Login successful!")
            st.rerun()

        else:
            st.error("Invalid username or password.")


# -----------------------------
# REGISTER
# -----------------------------

def register():
    st.title("📝 Create Account")

    username = st.text_input("New username")
    password = st.text_input(
        "New password",
        type="password"
    )

    if st.button("Create account"):

        if len(password) < 6:
            st.error("Password must contain at least 6 characters.")
            return

        conn = connect_db()
        cur = conn.cursor()

        try:
            cur.execute("""
                INSERT INTO users
                (username, password, role)
                VALUES (?, ?, ?)
            """, (
                username,
                hash_password(password),
                "customer"
            ))

            conn.commit()

            st.success("Account created!")

        except sqlite3.IntegrityError:
            st.error("Username already exists.")

        conn.close()


# -----------------------------
# PRODUCTS
# -----------------------------

def get_products():
    conn = connect_db()

    products = conn.execute("""
        SELECT id, name, description, price, inventory
        FROM products
    """).fetchall()

    conn.close()

    return products


# -----------------------------
# STORE
# -----------------------------

def store():

    st.title("🛍️ MiniStore")
    st.write("Welcome to the online store!")

    products = get_products()

    columns = st.columns(4)

    for index, product in enumerate(products):

        product_id = product[0]
        name = product[1]
        description = product[2]
        price = product[3]
        inventory = product[4]

        with columns[index % 4]:

            st.subheader(name)

            st.write(description)

            st.write(f"💰 **${price:.2f}**")

            st.write(f"📦 Stock: {inventory}")

            if inventory > 0:

                quantity = st.number_input(
                    "Quantity",
                    min_value=1,
                    max_value=inventory,
                    value=1,
                    key=f"qty_{product_id}"
                )

                if st.button(
                    "Add to cart",
                    key=f"add_{product_id}"
                ):

                    current_quantity = st.session_state.cart.get(
                        product_id,
                        0
                    )

                    if current_quantity + quantity <= inventory:

                        st.session_state.cart[product_id] = (
                            current_quantity + quantity
                        )

                        st.success("Added!")

                    else:
                        st.error("Not enough stock.")

            else:
                st.error("Out of stock.")


# -----------------------------
# CART
# -----------------------------

def cart():

    st.title("🛒 Shopping Cart")

    if not st.session_state.cart:
        st.info("Your cart is empty.")
        return

    conn = connect_db()

    total = 0

    for product_id, quantity in list(
        st.session_state.cart.items()
    ):

        product = conn.execute("""
            SELECT name, price, inventory
            FROM products
            WHERE id = ?
        """, (product_id,)).fetchone()

        if not product:
            continue

        name, price, inventory = product

        subtotal = price * quantity
        total += subtotal

        st.write(
            f"### {name}"
        )

        st.write(
            f"${price:.2f} × {quantity} = "
            f"**${subtotal:.2f}**"
        )

        if st.button(
            f"Remove {name}",
            key=f"remove_{product_id}"
        ):

            del st.session_state.cart[product_id]
            st.rerun()

    conn.close()

    st.divider()

    st.subheader(
        f"Total: ${total:.2f}"
    )


# -----------------------------
# CHECKOUT
# -----------------------------

def checkout():

    st.title("💳 Checkout")

    if not st.session_state.cart:
        st.info("Your cart is empty.")
        return

    conn = connect_db()

    total = 0

    for product_id, quantity in st.session_state.cart.items():

        product = conn.execute("""
            SELECT name, price, inventory
            FROM products
            WHERE id = ?
        """, (product_id,)).fetchone()

        if product:

            name, price, inventory = product

            total += price * quantity

    st.subheader(
        f"Order total: ${total:.2f}"
    )

    st.info(
        "This is a demo payment system. "
        "No real payment will be charged."
    )

    name = st.text_input("Name on card")

    card = st.text_input(
        "Demo card number",
        placeholder="4242 4242 4242 4242"
    )

    payment_method = st.selectbox(
        "Payment method",
        ["Demo Card", "Demo Pay"]
    )

    if st.button("Pay & Place Order"):

        if not name or not card:
            st.error("Please complete the payment information.")
            conn.close()
            return

        # Check inventory again before completing order
        for product_id, quantity in st.session_state.cart.items():

            product = conn.execute("""
                SELECT inventory
                FROM products
                WHERE id = ?
            """, (product_id,)).fetchone()

            if not product or product[0] < quantity:

                st.error(
                    "There is not enough inventory "
                    "for one of your products."
                )

                conn.close()
                return

        # Create order
        cursor = conn.cursor()

        cursor.execute("""
            INSERT INTO orders
            (username, total, payment_method, created_at)
            VALUES (?, ?, ?, ?)
        """, (
            st.session_state.username,
            total,
            payment_method,
            datetime.now().strftime(
                "%Y-%m-%d %H:%M:%S"
            )
        ))

        order_id = cursor.lastrowid

        # Save order items + reduce inventory
        for product_id, quantity in st.session_state.cart.items():

            product = conn.execute("""
                SELECT name, price
                FROM products
                WHERE id = ?
            """, (product_id,)).fetchone()

            product_name, price = product

            cursor.execute("""
                INSERT INTO order_items
                (order_id, product_id, product_name, quantity, price)
                VALUES (?, ?, ?, ?, ?)
            """, (
                order_id,
                product_id,
                product_name,
                quantity,
                price
            ))

            cursor.execute("""
                UPDATE products
                SET inventory = inventory - ?
                WHERE id = ?
            """, (
                quantity,
                product_id
            ))

        conn.commit()
        conn.close()

        st.session_state.cart = {}

        st.success(
            f"Order #{order_id} completed successfully!"
        )

        st.balloons()


# -----------------------------
# ORDER HISTORY
# -----------------------------

def order_history():

    st.title("📜 Order History")

    conn = connect_db()

    orders = conn.execute("""
        SELECT id, total, payment_method, created_at
        FROM orders
        WHERE username = ?
        ORDER BY id DESC
    """, (
        st.session_state.username,
    )).fetchall()

    if not orders:
        st.info("You haven't placed any orders yet.")

    for order in orders:

        order_id = order[0]
        total = order[1]
        payment = order[2]
        date = order[3]

        with st.expander(
            f"Order #{order_id} — ${total:.2f}"
        ):

            st.write(f"Date: {date}")
            st.write(f"Payment: {payment}")

            items = conn.execute("""
                SELECT product_name, quantity, price
                FROM order_items
                WHERE order_id = ?
            """, (order_id,)).fetchall()

            for item in items:

                st.write(
                    f"{item[0]} × {item[1]} "
                    f"— ${item[2]:.2f}"
                )

    conn.close()


# -----------------------------
# ADMIN DASHBOARD
# -----------------------------

def admin_dashboard():

    st.title("👑 Admin Dashboard")

    tabs = st.tabs([
        "Inventory",
        "Add Product",
        "Orders"
    ])

    # INVENTORY
    with tabs[0]:

        st.subheader("Manage Inventory")

        products = get_products()

        for product in products:

            product_id = product[0]
            name = product[1]
            description = product[2]
            price = product[3]
            inventory = product[4]

            with st.expander(name):

                new_name = st.text_input(
                    "Name",
                    name,
                    key=f"name_{product_id}"
                )

                new_description = st.text_area(
                    "Description",
                    description,
                    key=f"description_{product_id}"
                )

                new_price = st.number_input(
                    "Price",
                    min_value=0.0,
                    value=float(price),
                    key=f"price_{product_id}"
                )

                new_inventory = st.number_input(
                    "Inventory",
                    min_value=0,
                    value=int(inventory),
                    key=f"inventory_{product_id}"
                )

                col1, col2 = st.columns(2)

                with col1:

                    if st.button(
                        "Save changes",
                        key=f"save_{product_id}"
                    ):

                        conn = connect_db()

                        conn.execute("""
                            UPDATE products
                            SET name = ?,
                                description = ?,
                                price = ?,
                                inventory = ?
                            WHERE id = ?
                        """, (
                            new_name,
                            new_description,
                            new_price,
                            new_inventory,
                            product_id
                        ))

                        conn.commit()
                        conn.close()

                        st.success("Product updated.")
                        st.rerun()

                with col2:

                    if st.button(
                        "Delete",
                        key=f"delete_{product_id}"
                    ):

                        conn = connect_db()

                        conn.execute("""
                            DELETE FROM products
                            WHERE id = ?
                        """, (product_id,))

                        conn.commit()
                        conn.close()

                        st.success("Product deleted.")
                        st.rerun()

    # ADD PRODUCT
    with tabs[1]:

        st.subheader("Add New Product")

        name = st.text_input("Product name")
        description = st.text_area("Description")
        price = st.number_input(
            "Price",
            min_value=0.0
        )
        inventory = st.number_input(
            "Inventory",
            min_value=0,
            step=1
        )

        if st.button("Add product"):

            if not name:
                st.error("Product name is required.")
            else:

                conn = connect_db()

                conn.execute("""
                    INSERT INTO products
                    (name, description, price, inventory)
                    VALUES (?, ?, ?, ?)
                """, (
                    name,
                    description,
                    price,
                    inventory
                ))

                conn.commit()
                conn.close()

                st.success("Product added!")
                st.rerun()

    # ORDERS
    with tabs[2]:

        st.subheader("All Orders")

        conn = connect_db()

        orders = conn.execute("""
            SELECT id, username, total,
                   payment_method, created_at
            FROM orders
            ORDER BY id DESC
        """).fetchall()

        for order in orders:

            st.write(
                f"**Order #{order[0]}** | "
                f"Customer: {order[1]} | "
                f"${order[2]:.2f} | "
                f"{order[3]} | "
                f"{order[4]}"
            )

        conn.close()


# -----------------------------
# LOGOUT
# -----------------------------

def logout():

    st.session_state.logged_in = False
    st.session_state.username = ""
    st.session_state.role = ""
    st.session_state.cart = {}

    st.rerun()


# -----------------------------
# MAIN APP
# -----------------------------

if not st.session_state.logged_in:

    st.sidebar.title("🛍️ MiniStore")

    page = st.sidebar.radio(
        "Menu",
        [
            "Store",
            "Login",
            "Register"
        ]
    )

    if page == "Store":
        store()

    elif page == "Login":
        login()

    else:
        register()

else:

    st.sidebar.title(
        f"👋 {st.session_state.username}"
    )

    st.sidebar.write(
        f"Role: {st.session_state.role}"
    )

    if st.session_state.role == "admin":

        page = st.sidebar.radio(
            "Menu",
            [
                "Admin Dashboard",
                "Store",
                "Logout"
            ]
        )

        if page == "Admin Dashboard":
            admin_dashboard()

        elif page == "Store":
            store()

        else:
            logout()

    else:

        page = st.sidebar.radio(
            "Menu",
            [
                "Store",
                "Cart",
                "Checkout",
                "Order History",
                "Logout"
            ]
        )

        if page == "Store":
            store()

        elif page == "Cart":
            cart()

        elif page == "Checkout":
            checkout()

        elif page == "Order History":
            order_history()

        else:
            logout()
