import streamlit as st
import pandas as pd
from datetime import datetime
import gspread
from google.oauth2.service_account import Credentials
import json

# --- 1. 設定 Google 試算表連線 ---
scopes = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"
]

try:
    # 嘗試從 Streamlit 的雲端保險箱 (Secrets) 讀取金鑰
    if "google_credentials" in st.secrets:
        creds_dict = json.loads(st.secrets["google_credentials"])
        creds = Credentials.from_service_account_info(creds_dict, scopes=scopes)
    else:
        # 如果不在雲端，就讀取本地端的 credentials.json
        creds = Credentials.from_service_account_file("credentials.json", scopes=scopes)
        
    client = gspread.authorize(creds)
    sheet = client.open("自煮買菜記帳本").worksheet("groceries")
except Exception as e:
    st.error(f"連線 Google 試算表失敗！錯誤訊息：{e}")
    st.stop()

# --- 2. 頁面基本設定 ---
st.set_page_config(page_title="自煮買菜記帳本", page_icon="🥬", layout="wide")
st.title("🥬 雲端版：自煮買菜記帳本")
st.write("資料已自動同步至 Google 試算表！")

# --- 3. 左側欄：新增紀錄的表單 ---
with st.sidebar:
    st.header("🛒 新增買菜紀錄")
    with st.form("expense_form", clear_on_submit=True):
        date = st.date_input("購買日期", datetime.now())
        name = st.text_input("食材名稱 (例如：高麗菜)")
        category = st.selectbox("種類", ["蔬菜", "肉類", "海鮮", "水果", "調味料", "主食/麵包", "其他"])
        
        col1, col2 = st.columns(2)
        with col1:
            quantity = st.number_input("數量", min_value=0.1, value=1.0, step=0.5)
        with col2:
            unit = st.text_input("單位 (例如：把、盒、克)", "把")
            
        price = st.number_input("總價格 (元)", min_value=0, value=0, step=10)
        
        submitted = st.form_submit_button("✅ 記上一筆")
        
        if submitted:
            if name and price > 0:
                new_row = [date.strftime("%Y-%m-%d"), category, name, quantity, unit, price]
                sheet.append_row(new_row)
                st.success(f"成功新增：{name} (${price})，已同步至雲端！")
            else:
                st.error("請填寫食材名稱，並確保價格大於 0 喔！")

# --- 4. 主畫面：顯示數據與紀錄 ---
data = sheet.get_all_records()

if not data:
    st.info("目前 Google 試算表裡還沒有紀錄，快從左邊新增一筆吧！")
else:
    df = pd.DataFrame(data)
    df['價格'] = pd.to_numeric(df['價格'], errors='coerce').fillna(0)
    
    total_spent = int(df['價格'].sum())
    st.metric(label="💰 總食材花費 (元)", value=f"${total_spent:,}")
    
    st.markdown("---")
    st.subheader("📝 詳細買菜明細")
    
    df['數量'] = df['數量'].astype(str).str.rstrip('0').str.rstrip('.')
    df['數量/單位'] = df['數量'] + df['單位']
    df = df.sort_values(by='日期', ascending=False)
    
    display_df = df[['日期', '種類', '食材名稱', '數量/單位', '價格']]
    st.dataframe(display_df, use_container_width=True, hide_index=True)