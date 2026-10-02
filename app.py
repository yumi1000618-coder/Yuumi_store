import streamlit as st
import sqlite3
import hashlib
from datetime import datetime

# =========================
# 基本設定
# =========================

st.set_page_config(
    page_title="我的線上商店",
    page_icon="🛍️",
    layout="wide"
)

DB = "shop.db"


# =========================
# 資料庫
# =========================

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

    # 建立管理員帳號
    cur.execute("""
        INSERT OR IGNORE INTO users
        (username, password, role)
        VALUES (?, ?, ?)
    """, (
        "admin",
        hash_password("admin123"),
        "admin"
    ))

    # 建立一般使用者
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


# =========================
# Session State
# =========================

if "logged_in" not in st.session_state:
    st.session_state.logged_in = False

if "username" not in st.session_state:
    st.session_state.username = ""

if "role" not in st.session_state:
    st.session_state.role = ""

if "cart" not in st.session_state:
    st.session_state.cart = {}


# =========================
# 登入
# =========================

def login():
    st.title("🛍️ 我的線上商店")

    st.subheader("🔐 登入")

    username = st.text_input("帳號")
    password = st.text_input("密碼", type="password")

    if st.button("登入", use_container_width=True):

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

            st.success("登入成功！")
            st.rerun()

        else:
            st.error("帳號或密碼錯誤")

    st.divider()

    st.info("""
    測試帳號：

    管理員：
    帳號：admin
    密碼：admin123

    顧客：
    帳號：customer
    密碼：customer123
    """)


# =========================
# 商品列表
# =========================

def show_products():

    st.title("🛍️ 商品商店")

    conn = connect_db()
    cur = conn.cursor()

    cur.execute("""
        SELECT id, name, price, stock
        FROM products
        ORDER BY id
    """)

    products = cur.fetchall()

    conn.close()

    if not products:
        st.warning("目前沒有商品")
        return

    cols = st.columns(3)

    for index, product in enumerate(products):

        product_id = product[0]
        name = product[1]
        price = product[2]
        stock = product[3]

        with cols[index % 3]:

            st.subheader(name)

            st.write(f"💰 價格：NT$ {price:.0f}")

            if stock > 0:
                st.write(f"📦 庫存：{stock}")

                quantity = st.number_input(
                    "數量",
                    min_value=1,
                    max_value=stock,
                    value=1,
                    key=f"qty_{product_id}"
                )

                if st.button(
                    "🛒 加入購物車",
                    key=f"add_{product_id}",
                    use_container_width=True
                ):

                    if product_id in st.session_state.cart:
                        st.session_state.cart[product_id] += quantity
                    else:
                        st.session_state.cart[product_id] = quantity

                    st.success(f"{name} 已加入購物車")

            else:
                st.error("售罄")

            st.divider()


# =========================
# 購物車
# =========================

def show_cart():

    st.title("🛒 我的購物車")

    if not st.session_state.cart:
        st.info("購物車目前是空的")
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
            st.write(f"數量：{quantity}")

        with col4:

            if st.button(
                "🗑️ 移除",
                key=f"remove_{product_id}"
            ):

                del st.session_state.cart[product_id]
                st.rerun()

    conn.close()

    st.divider()

    st.subheader(
        f"總金額：NT$ {total:.0f}"
    )

    if st.button(
        "💳 前往結帳",
        use_container_width=True
    ):
        st.session_state.page = "checkout"
        st.rerun()


# =========================
# 結帳
# =========================

def checkout():

    st.title("💳 結帳")

    if not st.session_state.cart:
        st.info("購物車是空的")
        return

    conn = connect_db()
    cur = conn.cursor()

    total = 0
    order_products = []

    for product_id, quantity in st.session_state.cart.items():

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
                f"{name} 庫存不足，目前只剩 {stock} 件"
            )
            conn.close()
            return

        subtotal = price * quantity
        total += subtotal

        order_products.append(
            (product_id, name, price, quantity)
        )

    st.subheader("訂單內容")

    for product_id, name, price, quantity in order_products:
        st.write(
            f"{name} × {quantity} = NT$ {price * quantity:.0f}"
        )

    st.divider()

    st.subheader(
        f"應付金額：NT$ {total:.0f}"
    )

    payment = st.selectbox(
        "付款方式",
        [
            "信用卡（示範）",
            "ATM（示範）",
            "超商付款（示範）"
        ]
    )

    st.info(
        f"目前選擇：{payment}"
    )

    if st.button(
        "✅ 確認付款並完成訂單",
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
        for product_id, name, price, quantity in order_products:

            cur.execute("""
                INSERT INTO order_items
                (order_id, product_id, product_name, quantity, price)
                VALUES (?, ?, ?, ?, ?)
            """, (
                order_id,
                product_id,
                name,
                quantity,
                price
            ))

            # 扣除庫存
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

        # 清空購物車
        st.session_state.cart = {}

        st.success(
            f"🎉 訂單完成！訂單編號：#{order_id}"
        )

        st.balloons()


# =========================
# 訂單紀錄
# =========================

def order_history():

    st.title("📦 我的訂單")

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
        st.info("目前沒有訂單")
        conn.close()
        return

    for order in orders:

        order_id = order[0]
        total = order[1]
        created_at = order[2]

        with st.expander(
            f"訂單 #{order_id}｜NT$ {total:.0f}｜{created_at}"
        ):

            cur.execute("""
                SELECT product_name, quantity, price
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


# =========================
# 管理員後台
# =========================

def admin_dashboard():

    st.title("🔧 管理員後台")

    tab1, tab2, tab3 = st.tabs([
        "📦 商品管理",
        "➕ 新增商品",
        "📊 訂單管理"
    ])

    # ---------------------
    # 商品管理
    # ---------------------

    with tab1:

        conn = connect_db()
        cur = conn.cursor()

        cur.execute("""
            SELECT id, name, price, stock
            FROM products
            ORDER BY id
        """)

        products = cur.fetchall()

        conn.close()

        for product in products:

            product_id, name, price, stock = product

            with st.expander(
                f"{name}｜NT$ {price:.0f}｜庫存 {stock}"
            ):

                new_name = st.text_input(
                    "商品名稱",
                    value=name,
                    key=f"name_{product_id}"
                )

                new_price = st.number_input(
                    "價格",
                    min_value=0.0,
                    value=float(price),
                    key=f"price_{product_id}"
                )

                new_stock = st.number_input(
                    "庫存",
                    min_value=0,
                    value=int(stock),
                    key=f"stock_{product_id}"
                )

                col1, col2 = st.columns(2)

                with col1:

                    if st.button(
                        "💾 儲存修改",
                        key=f"save_{product_id}",
                        use_container_width=True
                    ):

                        conn = connect_db()
                        cur = conn.cursor()

                        cur.execute("""
                            UPDATE products
                            SET name = ?, price = ?, stock = ?
                            WHERE id = ?
                        """, (
                            new_name,
                            new_price,
                            new_stock,
                            product_id
                        ))

                        conn.commit()
                        conn.close()

                        st.success("修改成功")
                        st.rerun()

                with col2:

                    if st.button(
                        "🗑️ 刪除商品",
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

                        st.success("商品已刪除")
                        st.rerun()

    # ---------------------
    # 新增商品
    # ---------------------

    with tab2:

        st.subheader("➕ 新增商品")

        name = st.text_input("商品名稱")

        price = st.number_input(
            "商品價格",
            min_value=0.0,
            value=100.0
        )

        stock = st.number_input(
            "商品庫存",
            min_value=0,
            value=10
        )

        if st.button(
            "新增商品",
            use_container_width=True
        ):

            if not name:
                st.error("請輸入商品名稱")

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

                st.success("商品新增成功！")
                st.rerun()

    # ---------------------
    # 訂單管理
    # ---------------------

    with tab3:

        conn = connect_db()
        cur = conn.cursor()

        cur.execute("""
            SELECT id, username, total, created_at
            FROM orders
            ORDER BY id DESC
        """)

        orders = cur.fetchall()

        conn.close()

        if not orders:
            st.info("目前沒有訂單")

        else:

            for order in orders:

                order_id, username, total, created_at = order

                st.write(
                    f"📦 訂單 #{order_id}｜"
                    f"顧客：{username}｜"
                    f"金額：NT$ {total:.0f}｜"
                    f"{created_at}"
                )

                st.divider()


# =========================
# 登出
# =========================

def logout():

    st.session_state.logged_in = False
    st.session_state.username = ""
    st.session_state.role = ""
    st.session_state.cart = {}

    st.rerun()


# =========================
# 啟動資料庫
# =========================

init_database()


# =========================
# 主程式
# =========================

if not st.session_state.logged_in:

    login()

else:

    st.sidebar.title("🛍️ 我的商店")

    st.sidebar.write(
        f"👤 使用者：{st.session_state.username}"
    )

    st.sidebar.write(
        f"身份：{st.session_state.role}"
    )

    st.sidebar.divider()

    if st.session_state.role == "admin":

        page = st.sidebar.radio(
            "功能",
            [
                "🔧 管理員後台",
                "🛍️ 商品商店"
            ]
        )

        if page == "🔧 管理員後台":
            admin_dashboard()

        elif page == "🛍️ 商品商店":
            show_products()

    else:

        page = st.sidebar.radio(
            "功能",
            [
                "🛍️ 商品商店",
                "🛒 購物車",
                "📦 我的訂單"
            ]
        )

        if page == "🛍️ 商品商店":
            show_products()

        elif page == "🛒 購物車":
            show_cart()

        elif page == "📦 我的訂單":
            order_history()

    st.sidebar.divider()

    if st.button("🚪 登出"):
        logout()
