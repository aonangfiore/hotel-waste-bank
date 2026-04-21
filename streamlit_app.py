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
        # ตรวจสอบรหัส (แปลง EmployeeID เป็น string ด้วยเพื่อป้องกันปัญหา Data Type ไม่ตรงกัน)
        user = df_emp[(df_emp['EmployeeID'].astype(str) == emp_id) & (df_emp['PIN'].astype(str) == pin)]
        
        if not user.empty:
            st.session_state.logged_in = True
            # [แก้ไขแล้ว] ต้องระบุ Index [0] ก่อนใช้ .to_dict() เพื่อเลือกแถวแรกที่เจอ
            st.session_state.user_info = user.iloc[0].to_dict() 
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

    # [แก้ไขแล้ว] แยกตัวแปร tab ออกมาให้ชัดเจน แทนที่จะใช้ตัวแปรเดียว (menu)
    tab1, tab2 = st.tabs(["♻️ บันทึกขยะ", "📊 สรุปผลเปรียบเทียบ"])

    # --- Tab 1: บันทึกขยะ (หน้างาน) ---
    with tab1:
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
            
            # [แก้ไขแล้ว] streamlit-gsheets ไม่มี conn.create() 
            # ต้องอ่านข้อมูลเก่ามาต่อท้าย (concat) แล้วอัปเดตกลับไป (update)
            try:
                existing_data = conn.read(worksheet="WasteLog")
                updated_data = pd.concat([existing_data, new_data], ignore_index=True)
                conn.update(worksheet="WasteLog", data=updated_data)
                
                # ล้างแคชเพื่อให้ดึงข้อมูลใหม่เสมอเมื่อข้ามไปแท็บสรุปผล
                st.cache_data.clear() 
                
                st.success("บันทึกสำเร็จ! ข้อมูลถูกส่งไปที่ระบบส่วนกลางแล้ว")
                st.balloons()
            except Exception as e:
                st.error(f"เกิดข้อผิดพลาด: {e} (โปรดตรวจสอบว่ามีแผ่นงานชื่อ WasteLog อยู่หรือไม่)")

    with tab2:
    st.header("📊 สรุปผลเปรียบเทียบ (Purchase vs Waste)")
    
    # ดึงข้อมูลจาก Sheets
    df_p = conn.read(worksheet="Purchases")
    df_w = conn.read(worksheet="WasteLog")
    
    # รวมยอดตามหมวดหมู่
    buy_sum = df_p.groupby('Category')['Quantity'].sum().reset_index()
    waste_sum = df_w.groupby('Category')['Weight_kg'].sum().reset_index()
    
    # รวมข้อมูลเข้าด้วยกัน (Merge)
    comparison = pd.merge(buy_sum, waste_sum, on='Category', how='left').fillna(0)
    
    # คำนวณ % Waste
    comparison['Waste_Percentage'] = (comparison['Weight_kg'] / comparison['Quantity']) * 100
    
    # แสดงผลด้วย Metric
    cols = st.columns(len(comparison))
    for i, row in comparison.iterrows():
        cols[i].metric(
            label=f"% Waste: {row['Category']}", 
            value=f"{row['Weight_kg']:.1f} kg", 
            delta=f"{row['Waste_Percentage']:.1f}% ของยอดซื้อ",
            delta_color="inverse" # สีแดงถ้าเปอร์เซ็นต์สูง
        )
    
    # กราฟแท่งเปรียบเทียบ
    st.bar_chart(comparison.set_index('Category')[['Quantity', 'Weight_kg']])
