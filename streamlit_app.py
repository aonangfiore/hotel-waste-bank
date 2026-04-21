import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
from datetime import datetime

# ตั้งค่าหน้าจอสำหรับมือถือ
st.set_page_config(page_title="Green Hotel Waste Bank", layout="centered")

# เชื่อมต่อ Google Sheets (ต้องตั้งค่า Secrets ใน Streamlit Cloud)
conn = st.connection("gsheets", type=GSheetsConnection)

# 1. ฟังก์ชันโหลดข้อมูลพนักงาน
def load_employees():
    # ไม่ต้องระบุชื่อ worksheet เพื่อให้มันดึงแผ่นแรกสุดมาเลย
    return conn.read()

# --- ส่วนของ Login ---
if 'logged_in' not in st.session_state:
    st.session_state.logged_in = False

if not st.session_state.logged_in:
    st.title("🏨 Waste Bank Login")
    emp_id = st.text_input("รหัสพนักงาน")
    pin = st.text_input("รหัส PIN (4 หลัก)", type="password")
    
    if st.button("เข้าสู่ระบบ", use_container_width=True):
        df_emp = load_employees()
        # ตรวจสอบรหัส
        user = df_emp[(df_emp['EmployeeID'] == emp_id) & (df_emp['PIN'].astype(str) == pin)]
        if not user.empty:
            st.session_state.logged_in = True
            st.session_state.user_info = user.iloc.to_dict()
            st.rerun()
        else:
            st.error("รหัสพนักงานหรือ PIN ไม่ถูกต้อง")

# --- ส่วนของเมนูหลัก (เมื่อ Login แล้ว) ---
else:
    user = st.session_state.user_info
    st.sidebar.write(f"ผู้ใช้: {user['Name']} ({user['Department']})")
    if st.sidebar.button("ออกจากระบบ"):
        st.session_state.logged_in = False
        st.rerun()

    menu = st.tabs(["♻️ บันทึกขยะ", "📊 สรุปผลเปรียบเทียบ"])

    # --- Tab 1: บันทึกขยะ (หน้างาน) ---
    with menu:
        st.header("บันทึกการทิ้งขยะ")
        category = st.selectbox("ประเภทขยะ", ["เศษอาหาร (Organic)", "ขวดพลาสติก (PET)", "กระป๋องอลูมิเนียม", "ลังกระดาษ"])
        weight = st.number_input("น้ำหนัก (กก.)", min_value=0.0, step=0.1)
        
        if st.button("บันทึกข้อมูล ✅", type="primary", use_container_width=True):
            new_data = pd.DataFrame([{
                "Timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "EmployeeID": user['EmployeeID'],
                "Category": category,
                "Weight_kg": weight
            }])
            # ส่งข้อมูลไปต่อท้ายใน Google Sheets
            conn.create(worksheet="WasteLog", data=new_data)
            st.success("บันทึกสำเร็จ! ข้อมูลถูกส่งไปที่ระบบส่วนกลางแล้ว")
            st.balloons()

    # --- Tab 2: เปรียบเทียบ การซื้อ vs ขยะ (Dashboard) ---
    with menu:
        st.header("การซื้อ vs ขยะที่เกิดขึ้น")
        df_p = conn.read(worksheet="Purchases")
        df_w = conn.read(worksheet="WasteLog")
        
        # ตัวอย่างการคำนวณเปรียบเทียบ
        # (ในหน้างานจริงต้อง GroupBy Category และหมวดหมู่ที่ตรงกัน)
        st.write("ข้อมูลเปรียบเทียบรายหมวดหมู่ (ตัวอย่าง)")
        col1, col2 = st.columns(2)
        col1.metric("ยอดซื้อรวม (กก.)", f"{df_p['Quantity'].sum():.2f}")
        col2.metric("ปริมาณขยะรวม (กก.)", f"{df_w['Weight_kg'].sum():.2f}")
        
        # แสดงกราฟเปรียบเทียบ
        st.bar_chart(df_w.set_index('Category')['Weight_kg'])
