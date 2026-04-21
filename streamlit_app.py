import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
from datetime import datetime

# 1. ตั้งค่าหน้าจอสำหรับมือถือ
st.set_page_config(page_title="Hotel Waste Bank", layout="centered")

# 2. เชื่อมต่อ Google Sheets
conn = st.connection("gsheets", type=GSheetsConnection)

# ฟังก์ชันโหลดข้อมูลพนักงาน
def load_employees():
    # ดึงแผ่นงานแรก (Employees) ออกมา
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
        user = df_emp[(df_emp['EmployeeID'].astype(str) == emp_id) & (df_emp['PIN'].astype(str) == pin)]
        
        if not user.empty:
            st.session_state.logged_in = True
            # แก้ไขจุด iloc เพื่อดึงแถวแรกมาเป็น Dictionary
            st.session_state.user_info = user.iloc[0]to_dict()
            st.rerun()
        else:
            st.error("รหัสพนักงานหรือ PIN ไม่ถูกต้อง")

# --- ส่วนของเมนูหลัก (เมื่อ Login แล้ว) ---
else:
    user = st.session_state.user_info
    st.sidebar.write(f"ผู้ใช้: {user['Name']}")
    st.sidebar.write(f"แผนก: {user['Department']}")
    if st.sidebar.button("ออกจากระบบ"):
        st.session_state.logged_in = False
        st.rerun()

    # แก้ไขจุด st.tabs ให้เป็นตัวแปรเพื่อใช้กับ with
    tab1, tab2 = st.tabs(["♻️ บันทึกขยะ", "📊 สรุปผลเปรียบเทียบ"])

    # --- Tab 1: บันทึกขยะ (หน้างาน) ---
    with tab1:
        st.header("บันทึกการทิ้งขยะ")
        category = st.selectbox("ประเภทขยะ", ["ขวดพลาสติก (PET)", "กระป๋องอลูมิเนียม", "เศษอาหาร", "ลังกระดาษ"])
        weight = st.number_input("น้ำหนัก (กก.)", min_value=0.0, step=0.1)
        
        if st.button("บันทึกข้อมูล ✅", type="primary", use_container_width=True):
            # 1. ดึงข้อมูลเก่ามาก่อน
            existing_data = conn.read(worksheet="WasteLog")
            
            # 2. สร้างข้อมูลใหม่
            new_entry = pd.DataFrame([{
                "Timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "EmployeeID": user['EmployeeID'],
                "Category": category,
                "Weight_kg": weight
            }])
            
            # 3. รวมข้อมูล (Append) และอัปเดตกลับไป
            updated_df = pd.concat([existing_data, new_entry], ignore_index=True)
            conn.update(worksheet="WasteLog", data=updated_df)
            
            st.success("บันทึกสำเร็จ! ข้อมูลถูกส่งไปที่ระบบส่วนกลางแล้ว")
            st.balloons()

    # --- Tab 2: เปรียบเทียบ การซื้อ vs ขยะ (Dashboard) ---
    with tab2:
        st.header("📊 สรุปผลเปรียบเทียบ (Purchase vs Waste)")
        
        # ดึงข้อมูลจาก Sheets
        df_p = conn.read(worksheet="Purchases")
        df_w = conn.read(worksheet="WasteLog")
        
        if not df_p.empty and not df_w.empty:
            # รวมยอดซื้อและยอดขยะตาม Category
            buy_sum = df_p.groupby('Category')['Quantity'].sum().reset_index()
            waste_sum = df_w.groupby('Category')['Weight_kg'].sum().reset_index()
            
            # Merge ข้อมูลเข้าด้วยกัน
            comparison = pd.merge(buy_sum, waste_sum, on='Category', how='left').fillna(0)
            
            # คำนวณ % Waste (เลี่ยงการหารด้วยศูนย์)
            comparison['Waste_Percentage'] = (comparison['Weight_kg'] / comparison['Quantity'].replace(0, 1)) * 100
            
            # แสดง Metric สรุป
            st.subheader("สถานะแยกตามประเภท")
            m_cols = st.columns(len(comparison))
            for idx, row in comparison.iterrows():
                m_cols[idx].metric(
                    label=row['Category'],
                    value=f"{row['Weight_kg']:.1f} kg",
                    delta=f"{row['Waste_Percentage']:.1f}% ของยอดซื้อ",
                    delta_color="inverse"
                )
            
            # แสดงกราฟเปรียบเทียบ
            st.subheader("กราฟเปรียบเทียบยอดซื้อ vs ขยะ")
            st.bar_chart(comparison.set_index('Category')[['Quantity', 'Weight_kg']])
        else:
            st.info("ยังไม่มีข้อมูลการซื้อหรือข้อมูลขยะในระบบ")
