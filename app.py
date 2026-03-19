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
    if "google_credentials" in st.secrets:
        creds_dict = json.loads(st.secrets["google_credentials"])
        creds = Credentials.from_service_account_info(creds_dict, scopes=scopes)
    else:
        creds = Credentials.from_service_account_file("credentials.json", scopes=scopes)
        
    client = gspread.authorize(creds)
    sheet = client.open("自煮買菜記帳本").worksheet("groceries")
except Exception as e:
    st.error(f"連線 Google 試算表失敗！錯誤訊息：{e}")
    st.stop()

# --- 2. 頁面基本設定 (改為置中排版，手機看更舒服) ---
st.set_page_config(page_title="自煮買菜記帳本", page_icon="🥬", layout="centered")
st.title("🥬 買菜記帳本")

# --- 3. 手機版核心：使用分頁 (Tabs) 切換功能 ---
tab1, tab2 = st.tabs(["📝 記一筆", "📊 本月明細與編輯"])

# === 分頁 1：新增紀錄 ===
with tab1:
    st.markdown("### 🛒 新增花費")
    with st.form("expense_form", clear_on_submit=True):
        date = st.date_input("購買日期", datetime.now())
        name = st.text_input("食材名稱 (例如：高麗菜 或 綜合採買)")
        category = st.selectbox("種類", ["蔬菜", "肉類", "海鮮", "水果", "調味料", "主食/麵包", "綜合採買", "其他"])
        
        # 數量和單位在手機上並排顯示
        col1, col2 = st.columns(2)
        with col1:
            quantity = st.number_input("數量", min_value=0.1, value=1.0, step=0.5)
        with col2:
            unit = st.text_input("單位 (例如：把、次)", "份")
            
        price = st.number_input("總價格 (元)", min_value=0, value=0, step=10)
        
        # 手機版優化：按鈕設定為滿版寬度 (use_container_width=True)，方便單手點擊
        submitted = st.form_submit_button("✅ 記上一筆", use_container_width=True)
        
        if submitted:
            if name and price > 0:
                new_row = [date.strftime("%Y-%m-%d"), category, name, quantity, unit, price]
                sheet.append_row(new_row)
                st.success(f"成功新增：{name} (${price})！")
            else:
                st.error("請填寫食材名稱，並確保價格大於 0 喔！")

# === 分頁 2：顯示數據與編輯 ===
df = df.sort_values(by='日期', ascending=False)
        display_df = df[['日期', '種類', '食材名稱', '數量', '單位', '價格']].copy()
        
        # 👉 關鍵升級：在表格最左邊插入一個「刪除」打勾欄位
        display_df.insert(0, '❌ 刪除', False)
        
        # 互動式表格
        edited_df = st.data_editor(
            display_df,
            num_rows="dynamic",
            use_container_width=True,
            hide_index=True
        )
        
        # 儲存按鈕也改成滿版
        if st.button("💾 儲存修改至雲端", use_container_width=True):
            # 1. 找出沒有被打勾 (要保留) 的資料
            final_df = edited_df[edited_df['❌ 刪除'] == False].copy()
            
            # 2. 把「刪除」這個輔助欄位拿掉，準備存回雲端
            final_df = final_df.drop(columns=['❌ 刪除'])
            final_df = final_df.fillna("")
            
            # 3. 轉換格式並存回 Google 試算表
            updated_data = [final_df.columns.tolist()] + final_df.values.tolist()
            try:
                sheet.clear()
                # 確保就算資料全刪光了，也要保留標題列
                if len(updated_data) > 1:
                    sheet.update(range_name="A1", values=updated_data)
                else:
                    sheet.update(range_name="A1", values=[final_df.columns.tolist()])
                    
                st.success("✅ 修改已成功同步！")
                st.rerun()
            except Exception as e:
                st.error(f"儲存失敗：{e}")
