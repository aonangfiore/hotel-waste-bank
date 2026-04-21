import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
from datetime import datetime

# 1. ตั้งค่าหน้าจอสำหรับมือถือ
st.set_page_config(page_title="Hotel Waste Bank", layout="centered")

# 2. เชื่อมต่อ Google Sheets
conn = st.connection("gsheets", type=GSheetsConnection)

# ฟังก์ชันโหลดข้อมูลพนักงาน (เพิ่ม ttl=0 เพื่อให้ข้อมูลเป็นปัจจุบันเสมอ)
def load_employees():
    return conn.read(ttl=0)

# --- ส่วนของ Login ---
if 'logged_in' not in st.session_state:
    st.session_state.logged_in = False

if not st.session_state.logged_in:
    st.title("🏨 Waste Bank Login")
    emp_id = st.text_input("รหัสพนักงาน")
    pin = st.text_input("รหัส PIN (4 หลัก)", type="password")
    
    if st.button("เข้าสู่ระบบ", use_container_width=True):
        df_emp = load_employees()
        # ตรวจสอบรหัส (แปลงเป็น string ทั้งคู่เพื่อป้องกัน Error)
        user = df_emp[(df_emp['EmployeeID'].astype(str) == str(emp_id)) & 
                      (df_emp['PIN'].astype(str) == str(pin))]
        
        if not user.empty:
            st.session_state.logged_in = True
            # แก้ไขจุดสำคัญ: ต้องใส่ [0] หลัง iloc เพื่อระบุแถวแรกที่เจอ
            st.session_state.user_info = user.iloc[0].to_dict()
            st.rerun()
        else:
            st.error("รหัสพนักงานหรือ PIN ไม่ถูกต้อง")

# --- ส่วนของเมนูหลัก (เมื่อ Login แล้ว) ---
else:
    user = st.session_state.user_info
    st.sidebar.write(f"👤 ผู้ใช้: {user['Name']}")
    st.sidebar.write(f"🏢 แผนก: {user['Department']}")
    if st.sidebar.button("ออกจากระบบ"):
        st.session_state.logged_in = False
        st.rerun()

    tab1, tab2 = st.tabs(["♻️ บันทึกขยะ", "📊 สรุปผลเปรียบเทียบ"])

    # --- Tab 1: บันทึกขยะ (หน้างาน) ---
    with tab1:
        st.header("บันทึกการทิ้งขยะ")
        category = st.selectbox("ประเภทขยะ", ["ขวดพลาสติก (PET)", "กระป๋องอลูมิเนียม", "เศษอาหาร", "ลังกระดาษ"])
        weight = st.number_input("น้ำหนัก (กก.)", min_value=0.0, step=0.1)
        
        if st.button("บันทึกข้อมูล ✅", type="primary", use_container_width=True):
            with st.spinner('กำลังบันทึกข้อมูล...'):
                # 1. ดึงข้อมูลเก่า (ใส่ ttl=0 เพื่อป้องกันการดึงข้อมูลเก่าจาก Cache)
                existing_data = conn.read(worksheet="WasteLog", ttl=0)
                
                # 2. สร้างข้อมูลใหม่
                new_entry = pd.DataFrame([{
                    "Timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "EmployeeID": user['EmployeeID'],
                    "Category": category,
                    "Weight_kg": weight
                }])
                
                # 3. รวมข้อมูลและอัปเดต
                updated_df = pd.concat([existing_data, new_entry], ignore_index=True)
                conn.update(worksheet="WasteLog", data=updated_df)
                
                st.success("บันทึกสำเร็จ!")
                st.balloons()

    # --- Tab 2: เปรียบเทียบ (Dashboard) ---
    with tab2:
        st.header("📊 สรุปผล Purchase vs Waste")
        
        df_p = conn.read(worksheet="Purchases", ttl=0)
        df_w = conn.read(worksheet="WasteLog", ttl=0)
        
        if not df_p.empty and not df_w.empty:
            # รวมยอดตาม Category
            buy_sum = df_p.groupby('Category')['Quantity'].sum().reset_index()
            waste_sum = df_w.groupby('Category')['Weight_kg'].sum().reset_index()
            
            # Merge ข้อมูล
            comparison = pd.merge(buy_sum, waste_sum, on='Category', how='left').fillna(0)
            comparison['Waste_%'] = (comparison['Weight_kg'] / comparison['Quantity'].replace(0, 1)) * 100
            
            # การแสดงผล Metric (ปรับปรุงให้รองรับมือถือ: แสดงแถวละ 2 ตัว)
            st.subheader("แยกตามประเภท")
            for i in range(0, len(comparison), 2):
                cols = st.columns(2)
                for j in range(2):
                    if i + j < len(comparison):
                        row = comparison.iloc[i + j]
                        cols[j].metric(
                            label=row['Category'],
                            value=f"{row['Weight_kg']:.1f} kg",
                            delta=f"{row['Waste_%']:.1f}% ของยอดซื้อ",
                            delta_color="inverse" # สีแดงเมื่อตัวเลขเพิ่มขึ้น (เพราะขยะเยอะไม่ดี)
                        )
            
            # กราฟ
            st.subheader("เปรียบเทียบ Quantity vs Waste")
            st.bar_chart(comparison.set_index('Category')[['Quantity', 'Weight_kg']])
            
            # ตารางสรุป
            st.dataframe(comparison, use_container_width=True)
        else:
            st.info("ยังไม่มีข้อมูลในระบบ")
