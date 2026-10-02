import streamlit as st
import sqlite3
import hashlib
import os
from datetime import datetime

# Groq
from groq import Groq


# =========================================================
# 基本設定
# =========================================================

st.set_page_config(
    page_title="Yuumi AI Store",
    page_icon="🛍️",
    layout="wide"
)

DB = "shop.db"


# =========================================================
# 資料庫
# =========================================================

def connect_db():
    return sqlite3.connect(DB)


def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()


def init_database():
    conn = connect_db()
    cur = conn.cursor()

    # 使用者
    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            role TEXT NOT NULL
        )
    """)

    # 商品
    cur.execute("""
        CREATE TABLE IF NOT EXISTS products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            price REAL NOT NULL,
            stock INTEGER NOT NULL
        )
    """)

    # 訂單
    cur.execute("""
        CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL,
            total REAL NOT NULL,
            created_at TEXT NOT NULL
        )
    """)

    # 訂單商品
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

    # 管理員
    cur.execute("""
        INSERT OR IGNORE INTO users
        (username, password, role)
        VALUES (?, ?, ?)
    """, (
        "admin",
        hash_password("admin123"),
        "admin"
    ))

    # 顧客
    cur.execute("""
        INSERT OR IGNORE INTO users
        (username, password, role)
        VALUES (?, ?, ?)
    """, (
        "customer",
        hash_password("customer123"),
        "customer"
    ))

    # 預設商品
    cur.execute("SELECT COUNT(*) FROM products")
    count = cur.fetchone()[0]

    if count == 0:
        products = [
            ("無線耳機", 599, 10),
            ("簡約後背包", 899, 15),
            ("桌上型檯燈", 499, 20),
            ("保溫水壺", 399, 25),
            ("手機支架", 299, 30),
        ]

        cur.executemany("""
            INSERT INTO products
            (name, price, stock)
            VALUES (?, ?, ?)
        """, products)

    conn.commit()
    conn.close()


# =========================================================
# Session State
# =========================================================

if "logged_in" not in st.session_state:
    st.session_state.logged_in = False

if "username" not in st.session_state:
    st.session_state.username = ""

if "role" not in st.session_state:
    st.session_state.role = ""

if "cart" not in st.session_state:
    st.session_state.cart = {}

if "chat_messages" not in st.session_state:
    st.session_state.chat_messages = []


# =========================================================
# Groq
# =========================================================

def get_groq_client():
    """
    API Key 優先從 Streamlit Secrets 讀取。
    如果本機有環境變數，也可以使用 GROQ_API_KEY。
    """

    api_key = None

    try:
        api_key = st.secrets["GROQ_API_KEY"]
    except Exception:
        api_key = os.environ.get("GROQ_API_KEY")

    if not api_key:
        return None

    return Groq(api_key=api_key)


# =========================================================
# 從資料庫取得全部商品
# =========================================================

def get_all_products():
    conn = connect_db()
    cur = conn.cursor()

    cur.execute("""
        SELECT id, name, price, stock
        FROM products
        ORDER BY id
    """)

    products = cur.fetchall()

    conn.close()

    return products


# =========================================================
# 搜尋商品
# =========================================================

def search_products(keyword):
    conn = connect_db()
    cur = conn.cursor()

    keyword = keyword.strip()

    cur.execute("""
        SELECT id, name, price, stock
        FROM products
        WHERE name LIKE ?
        ORDER BY id
    """, (f"%{keyword}%",))

    products = cur.fetchall()

    conn.close()

    return products


# =========================================================
# AI 商品客服
# =========================================================

def ai_store_chat(user_question):

    client = get_groq_client()

    if client is None:
        return (
            "⚠️ Groq API Key 還沒有設定。\n\n"
            "請到 Streamlit Secrets 設定 GROQ_API_KEY。"
        )

    # -----------------------------------------------------
    # 先從真正的資料庫取得商品
    # -----------------------------------------------------

    products = get_all_products()

    if not products:
        return "目前商店資料庫裡沒有商品。"

    product_text = ""

    for product_id, name, price, stock in products:

        if stock > 0:
            availability = "In stock"
        else:
            availability = "Out of stock"

        product_text += (
            f"ID: {product_id}\n"
            f"Product: {name}\n"
            f"Price: NT$ {price:.0f}\n"
            f"Stock: {stock}\n"
            f"Availability: {availability}\n"
            f"---\n"
        )

    # -----------------------------------------------------
    # System Prompt
    # -----------------------------------------------------

    system_prompt = f"""
You are the AI customer assistant for Yuumi Online Store.

IMPORTANT RULES:

1. You MUST only use the store information provided below.
2. NEVER invent a product.
3. NEVER invent a price.
4. NEVER invent inventory.
5. If a product is not listed, say that the product is not currently in the store.
6. If stock is 0, clearly say it is out of stock.
7. When recommending products, only recommend products from the database.
8. Prefer recommending products that are currently in stock.
9. You can answer questions about:
   - product availability
   - price
   - inventory
   - simple product information
   - similar or related products
10. If the customer asks for something unrelated to the store, politely say that you mainly help with store products.
11. Answer clearly and briefly.
12. The store uses NT$ for prices.

REAL STORE DATABASE:

{product_text}
"""

    # -----------------------------------------------------
    # AI conversation
    # -----------------------------------------------------

    messages = [
        {
            "role": "system",
            "content": system_prompt
        }
    ]

    # 加入最近幾次對話
    for message in st.session_state.chat_messages[-6:]:
        messages.append({
            "role": message["role"],
            "content": message["content"]
        })

    messages.append({
        "role": "user",
        "content": user_question
    })

    try:

        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=messages,
            temperature=0.2,
            max_tokens=500
        )

        answer = response.choices[0].message.content

        return answer

    except Exception as e:

        return (
            "❌ AI 暫時無法回答。\n\n"
            f"錯誤：{str(e)}"
        )


# =========================================================
# 登入
# =========================================================

def login():

    st.title("🛍️ Yuumi Online Store")

    st.subheader("🔐 Login")

    username = st.text_input("Username")

    password = st.text_input(
        "Password",
        type="password"
    )

    if st.button(
        "Login",
        use_container_width=True
    ):

        conn = connect_db()
        cur = conn.cursor()

        cur.execute("""
            SELECT username, role
            FROM users
            WHERE username = ?
            AND password = ?
        """, (
            username,
            hash_password(password)
        ))

        user = cur.fetchone()

        conn.close()

        if user:

            st.session_state.logged_in = True
            st.session_state.username = user[0]
            st.session_state.role = user[1]

            st.success("Login successful!")

            st.rerun()

        else:

            st.error("Incorrect username or password.")

    st.divider()

    st.info("""
Test Accounts

Admin:
Username: admin
Password: admin123

Customer:
Username: customer
Password: customer123
""")


# =========================================================
# 商品列表
# =========================================================

def show_products():

    st.title("🛍️ Products")

    products = get_all_products()

    if not products:
        st.warning("No products available.")
        return

    cols = st.columns(3)

    for index, product in enumerate(products):

        product_id = product[0]
        name = product[1]
        price = product[2]
        stock = product[3]

        with cols[index % 3]:

            st.subheader(name)

            st.write(
                f"💰 Price: NT$ {price:.0f}"
            )

            if stock > 0:

                st.write(
                    f"📦 Stock: {stock}"
                )

                quantity = st.number_input(
                    "Quantity",
                    min_value=1,
                    max_value=stock,
                    value=1,
                    key=f"qty_{product_id}"
                )

                if st.button(
                    "🛒 Add to Cart",
                    key=f"add_{product_id}",
                    use_container_width=True
                ):

                    current_quantity = (
                        st.session_state.cart.get(
                            product_id,
                            0
                        )
                    )

                    new_quantity = (
                        current_quantity + quantity
                    )

                    if new_quantity <= stock:

                        st.session_state.cart[
                            product_id
                        ] = new_quantity

                        st.success(
                            f"{name} added to cart!"
                        )

                    else:

                        st.error(
                            "Not enough stock."
                        )

            else:

                st.error("❌ Out of stock")

            st.divider()


# =========================================================
# AI Chatbot
# =========================================================

def chatbot_page():

    st.title("🤖 AI Store Assistant")

    st.write(
        "Ask me about product prices, stock, availability, "
        "or related products."
    )

    st.info(
        "💡 Example: Do you have wireless headphones in stock?"
    )

    # 顯示舊訊息
    for message in st.session_state.chat_messages:

        with st.chat_message(message["role"]):

            st.write(message["content"])

    user_question = st.chat_input(
        "Ask about our products..."
    )

    if user_question:

        # 顯示使用者問題
        st.session_state.chat_messages.append({
            "role": "user",
            "content": user_question
        })

        with st.chat_message("user"):
            st.write(user_question)

        # AI 回答
        with st.chat_message("assistant"):

            with st.spinner("Checking store database..."):

                answer = ai_store_chat(
                    user_question
                )

            st.write(answer)

        st.session_state.chat_messages.append({
            "role": "assistant",
            "content": answer
        })


# =========================================================
# 購物車
# =========================================================

def show_cart():

    st.title("🛒 My Cart")

    if not st.session_state.cart:

        st.info("Your cart is empty.")

        return

    conn = connect_db()
    cur = conn.cursor()

    total = 0

    for product_id, quantity in list(
        st.session_state.cart.items()
    ):

        cur.execute("""
            SELECT name, price, stock
            FROM products
            WHERE id = ?
        """, (product_id,))

        product = cur.fetchone()

        if not product:
            continue

        name, price, stock = product

        # 如果庫存變少，避免購物車數量超過庫存
        if quantity > stock:
            quantity = stock
            st.session_state.cart[
                product_id
            ] = stock

        if quantity <= 0:
            del st.session_state.cart[product_id]
            continue

        subtotal = price * quantity

        total += subtotal

        col1, col2, col3, col4 = st.columns(
            [3, 1, 1, 1]
        )

        with col1:
            st.write(f"**{name}**")

        with col2:
            st.write(f"NT$ {price:.0f}")

        with col3:
            st.write(f"Quantity: {quantity}")

        with col4:

            if st.button(
                "🗑️ Remove",
                key=f"remove_{product_id}"
            ):

                del st.session_state.cart[
                    product_id
                ]

                st.rerun()

    conn.close()

    st.divider()

    st.subheader(
        f"Total: NT$ {total:.0f}"
    )

    if st.button(
        "💳 Checkout",
        use_container_width=True
    ):

        st.session_state.page = "checkout"

        st.rerun()


# =========================================================
# 結帳
# =========================================================

def checkout():

    st.title("💳 Checkout")

    if not st.session_state.cart:

        st.info("Your cart is empty.")

        return

    conn = connect_db()
    cur = conn.cursor()

    total = 0

    order_products = []

    for product_id, quantity in (
        st.session_state.cart.items()
    ):

        cur.execute("""
            SELECT name, price, stock
            FROM products
            WHERE id = ?
        """, (product_id,))

        product = cur.fetchone()

        if not product:
            continue

        name, price, stock = product

        if quantity > stock:

            st.error(
                f"{name} only has {stock} left."
            )

            conn.close()

            return

        subtotal = price * quantity

        total += subtotal

        order_products.append(
            (
                product_id,
                name,
                price,
                quantity
            )
        )

    st.subheader("Order")

    for product_id, name, price, quantity in order_products:

        st.write(
            f"{name} × {quantity} = "
            f"NT$ {price * quantity:.0f}"
        )

    st.divider()

    st.subheader(
        f"Total: NT$ {total:.0f}"
    )

    payment = st.selectbox(
        "Payment Method",
        [
            "Credit Card (Demo)",
            "ATM (Demo)",
            "Convenience Store (Demo)"
        ]
    )

    st.info(
        f"Selected payment: {payment}"
    )

    if st.button(
        "✅ Complete Order",
        use_container_width=True
    ):

        # 建立訂單
        cur.execute("""
            INSERT INTO orders
            (username, total, created_at)
            VALUES (?, ?, ?)
        """, (
            st.session_state.username,
            total,
            datetime.now().strftime(
                "%Y-%m-%d %H:%M:%S"
            )
        ))

        order_id = cur.lastrowid

        # 建立訂單商品
        for (
            product_id,
            name,
            price,
            quantity
        ) in order_products:

            cur.execute("""
                INSERT INTO order_items
                (order_id, product_id,
                 product_name, quantity, price)
                VALUES (?, ?, ?, ?, ?)
            """, (
                order_id,
                product_id,
                name,
                quantity,
                price
            ))

            # 扣庫存
            cur.execute("""
                UPDATE products
                SET stock = stock - ?
                WHERE id = ?
            """, (
                quantity,
                product_id
            ))

        conn.commit()
        conn.close()

        st.session_state.cart = {}

        st.success(
            f"🎉 Order completed! "
            f"Order #{order_id}"
        )

        st.balloons()


# =========================================================
# 訂單紀錄
# =========================================================

def order_history():

    st.title("📦 My Orders")

    conn = connect_db()
    cur = conn.cursor()

    cur.execute("""
        SELECT id, total, created_at
        FROM orders
        WHERE username = ?
        ORDER BY id DESC
    """, (
        st.session_state.username,
    ))

    orders = cur.fetchall()

    if not orders:

        st.info("No orders yet.")

        conn.close()

        return

    for order in orders:

        order_id = order[0]
        total = order[1]
        created_at = order[2]

        with st.expander(
            f"Order #{order_id} | "
            f"NT$ {total:.0f} | "
            f"{created_at}"
        ):

            cur.execute("""
                SELECT product_name,
                       quantity,
                       price
                FROM order_items
                WHERE order_id = ?
            """, (order_id,))

            items = cur.fetchall()

            for item in items:

                name, quantity, price = item

                st.write(
                    f"{name} × {quantity} "
                    f"— NT$ {price * quantity:.0f}"
                )

    conn.close()


# =========================================================
# 管理員後台
# =========================================================

def admin_dashboard():

    st.title("🔧 Admin Dashboard")

    tab1, tab2, tab3 = st.tabs([
        "📦 Product Management",
        "➕ Add Product",
        "📊 Orders"
    ])

    # -----------------------------------------------------
    # 商品管理
    # -----------------------------------------------------

    with tab1:

        products = get_all_products()

        for product in products:

            product_id, name, price, stock = product

            with st.expander(
                f"{name} | "
                f"NT$ {price:.0f} | "
                f"Stock {stock}"
            ):

                new_name = st.text_input(
                    "Product Name",
                    value=name,
                    key=f"name_{product_id}"
                )

                new_price = st.number_input(
                    "Price",
                    min_value=0.0,
                    value=float(price),
                    key=f"price_{product_id}"
                )

                new_stock = st.number_input(
                    "Stock",
                    min_value=0,
                    value=int(stock),
                    key=f"stock_{product_id}"
                )

                col1, col2 = st.columns(2)

                with col1:

                    if st.button(
                        "💾 Save",
                        key=f"save_{product_id}",
                        use_container_width=True
                    ):

                        conn = connect_db()
                        cur = conn.cursor()

                        cur.execute("""
                            UPDATE products
                            SET name = ?,
                                price = ?,
                                stock = ?
                            WHERE id = ?
                        """, (
                            new_name,
                            new_price,
                            new_stock,
                            product_id
                        ))

                        conn.commit()
                        conn.close()

                        st.success("Product updated!")

                        st.rerun()

                with col2:

                    if st.button(
                        "🗑️ Delete",
                        key=f"delete_{product_id}",
                        use_container_width=True
                    ):

                        conn = connect_db()
                        cur = conn.cursor()

                        cur.execute("""
                            DELETE FROM products
                            WHERE id = ?
                        """, (product_id,))

                        conn.commit()
                        conn.close()

                        st.success(
                            "Product deleted!"
                        )

                        st.rerun()

    # -----------------------------------------------------
    # 新增商品
    # -----------------------------------------------------

    with tab2:

        st.subheader("➕ Add Product")

        name = st.text_input(
            "Product Name",
            key="new_product_name"
        )

        price = st.number_input(
            "Price",
            min_value=0.0,
            value=100.0,
            key="new_product_price"
        )

        stock = st.number_input(
            "Stock",
            min_value=0,
            value=10,
            key="new_product_stock"
        )

        if st.button(
            "Add Product",
            use_container_width=True
        ):

            if not name:

                st.error(
                    "Please enter a product name."
                )

            else:

                conn = connect_db()
                cur = conn.cursor()

                cur.execute("""
                    INSERT INTO products
                    (name, price, stock)
                    VALUES (?, ?, ?)
                """, (
                    name,
                    price,
                    stock
                ))

                conn.commit()
                conn.close()

                st.success(
                    "Product added!"
                )

                st.rerun()

    # -----------------------------------------------------
    # 訂單管理
    # -----------------------------------------------------

    with tab3:

        conn = connect_db()
        cur = conn.cursor()

        cur.execute("""
            SELECT id,
                   username,
                   total,
                   created_at
            FROM orders
            ORDER BY id DESC
        """)

        orders = cur.fetchall()

        conn.close()

        if not orders:

            st.info("No orders yet.")

        else:

            for order in orders:

                order_id, username, total, created_at = order

                st.write(
                    f"📦 Order #{order_id} | "
                    f"Customer: {username} | "
                    f"NT$ {total:.0f} | "
                    f"{created_at}"
                )

                st.divider()


# =========================================================
# 登出
# =========================================================

def logout():

    st.session_state.logged_in = False
    st.session_state.username = ""
    st.session_state.role = ""
    st.session_state.cart = {}
    st.session_state.chat_messages = []

    st.rerun()


# =========================================================
# 啟動資料庫
# =========================================================

init_database()


# =========================================================
# 主程式
# =========================================================

if not st.session_state.logged_in:

    login()

else:

    st.sidebar.title("🛍️ Yuumi Store")

    st.sidebar.write(
        f"👤 User: "
        f"{st.session_state.username}"
    )

    st.sidebar.write(
        f"Role: "
        f"{st.session_state.role}"
    )

    st.sidebar.divider()

    # -----------------------------------------------------
    # 管理員
    # -----------------------------------------------------

    if st.session_state.role == "admin":

        page = st.sidebar.radio(
            "Menu",
            [
                "🔧 Admin Dashboard",
                "🛍️ Store",
                "🤖 AI Assistant"
            ]
        )

        if page == "🔧 Admin Dashboard":

            admin_dashboard()

        elif page == "🛍️ Store":

            show_products()

        elif page == "🤖 AI Assistant":

            chatbot_page()

    # -----------------------------------------------------
    # 顧客
    # -----------------------------------------------------

    else:

        page = st.sidebar.radio(
            "Menu",
            [
                "🛍️ Store",
                "🛒 Cart",
                "📦 My Orders",
                "🤖 AI Assistant"
            ]
        )

        if page == "🛍️ Store":

            show_products()

        elif page == "🛒 Cart":

            show_cart()

        elif page == "📦 My Orders":

            order_history()

        elif page == "🤖 AI Assistant":

            chatbot_page()

    st.sidebar.divider()

    if st.sidebar.button("🚪 Logout"):

        logout()
