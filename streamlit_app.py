import streamlit as st
import pandas as pd
from github import Github
from datetime import datetime
import io

# 1. ตั้งค่าหน้าจอ
st.set_page_config(page_title="Hotel Waste Bank (GitHub DB)", layout="centered")

# 2. เชื่อมต่อ GitHub API
try:
    # ตรวจสอบว่ามีวงเล็บปิดครบถ้วน
    g = Github(st.secrets["GITHUB_TOKEN"])
    repo = g.get_repo(st.secrets["REPO_NAME"])
except Exception as e:
    st.error(f"การเชื่อมต่อ GitHub ผิดพลาด: {e}")
    st.stop()

# ฟังก์ชันอ่านไฟล์ CSV จาก GitHub
def read_github_csv(file_path):
    try:
        file_content = repo.get_contents(file_path)
        return pd.read_csv(io.StringIO(file_content.decoded_content.decode('utf-8')))
    except:
        return pd.DataFrame()

# ฟังก์ชันเขียนไฟล์ CSV กลับไป GitHub (Update/Append)
def write_github_csv(file_path, df, message):
    file_content = repo.get_contents(file_path)
    repo.update_file(file_path, message, df.to_csv(index=False), file_content.sha)

# --- ระบบ Login ---
if 'logged_in' not in st.session_state:
    st.session_state.logged_in = False

if not st.session_state.logged_in:
    st.title("🏨 Waste Bank (GitHub Edition)")
    emp_id = st.text_input("รหัสพนักงาน")
    pin = st.text_input("รหัส PIN", type="password")
    
    if st.button("เข้าสู่ระบบ", use_container_width=True):
        df_emp = read_github_csv("employees.csv")
        user = df_emp[(df_emp['EmployeeID'].astype(str) == emp_id) & (df_emp['PIN'].astype(str) == pin)]
        
        if not user.empty:
            st.session_state.logged_in = True
            st.session_state.user_info = user.iloc[0].to_dict()
            st.rerun()
        else:
            st.error("ID หรือ PIN ไม่ถูกต้อง")

# --- เมนูหลักเมื่อ Login แล้ว ---
else:
    user = st.session_state.user_info
    st.sidebar.write(f"พนักงาน: {user['Name']}")
    if st.sidebar.button("ออกจากระบบ"):
        st.session_state.logged_in = False
        st.rerun()

    tab1, tab2 = st.tabs(["♻️ บันทึกขยะ", "📊 สรุปผล"])

    with tab1:
        st.header("บันทึกการทิ้งขยะ")
        cat_list = ["ขวดพลาสติก (PET)", "กระป๋องอลูมิเนียม", "เศษอาหาร", "ลังกระดาษ"]
        category = st.selectbox("ประเภทขยะ", cat_list)
        weight = st.number_input("น้ำหนัก (กก.)", min_value=0.0, step=0.1)
        
        if st.button("บันทึกข้อมูล ✅", type="primary", use_container_width=True):
            with st.spinner("กำลังบันทึกลง GitHub..."):
                existing_df = read_github_csv("waste_log.csv")
                new_entry = pd.DataFrame([{
                    "Timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "EmployeeID": user['EmployeeID'],
                    "Category": category,
                    "Weight_kg": weight
                }])
                updated_df = pd.concat([existing_df, new_entry], ignore_index=True)
                write_github_csv("waste_log.csv", updated_df, f"Add log by {user['Name']}")
                st.success("บันทึกสำเร็จ!")
                st.balloons()

    with tab2:
        st.header("📊 เปรียบเทียบ การซื้อ vs ขยะ")
        df_p = read_github_csv("purchases.csv")
        df_w = read_github_csv("waste_log.csv")
        
        if not df_p.empty and not df_w.empty:
            buy_sum = df_p.groupby('Category')['Quantity'].sum().reset_index()
            waste_sum = df_w.groupby('Category')['Weight_kg'].sum().reset_index()
            comp = pd.merge(buy_sum, waste_sum, on='Category', how='left').fillna(0)
            comp['Waste_Ratio'] = (comp['Weight_kg'] / comp['Quantity'].replace(0, 1)) * 100
            
            st.bar_chart(comp.set_index('Category')[['Quantity', 'Weight_kg']])
            st.dataframe(comp)
        else:
            st.info("ยังไม่มีข้อมูลเพียงพอ")
