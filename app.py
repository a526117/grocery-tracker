import streamlit as st
import pandas as pd
from datetime import datetime, timedelta, timezone
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

# --- 2. 頁面基本設定 ---
st.set_page_config(page_title="自煮買菜記帳本", page_icon="🥬", layout="centered")
st.title("🥬 買菜記帳本")

# --- 3. 分頁切換 ---
tab1, tab2 = st.tabs(["📝 記一筆", "📊 本月明細與編輯"])

# === 分頁 1：新增紀錄 ===
with tab1:
    st.markdown("### 🛒 新增花費")
    with st.form("expense_form", clear_on_submit=True):
        # 設定台灣時區 (UTC+8)
        tw_tz = timezone(timedelta(hours=8))
        date = st.date_input("購買日期", datetime.now(tw_tz))
        name = st.text_input("食材名稱 (例如：高麗菜 或 綜合採買)")
        category = st.selectbox("種類", ["蔬菜", "肉類", "海鮮", "水果", "調味料", "主食/麵包", "綜合採買", "其他"])
        
        col1, col2 = st.columns(2)
        with col1:
            quantity = st.number_input("數量", min_value=0.1, value=1.0, step=0.5)
        with col2:
            unit = st.text_input("單位 (例如：把、次)", "份")
            
        price = st.number_input("總價格 (元)", min_value=0, value=0, step=10)
        
        submitted = st.form_submit_button("✅ 記上一筆", use_container_width=True)
        
        if submitted:
            if name and price > 0:
                new_row = [date.strftime("%Y-%m-%d"), category, name, quantity, unit, price]
                sheet.append_row(new_row)
                st.success(f"成功新增：{name} (${price})！已同步至雲端。")
            else:
                st.error("請填寫食材名稱，並確保價格大於 0 喔！")

# === 分頁 2：顯示數據與編輯 ===
with tab2:
    data = sheet.get_all_records()

    if not data:
        st.info("目前還沒有紀錄，快去「記一筆」吧！")
    else:
        df = pd.DataFrame(data)
        df['價格'] = pd.to_numeric(df['價格'], errors='coerce').fillna(0)
        
        tw_tz = timezone(timedelta(hours=8))
        current_month = datetime.now(tw_tz).strftime("%Y-%m")
        df['日期'] = df['日期'].astype(str)
        monthly_df = df[df['日期'].str.startswith(current_month)]
        monthly_spent = int(monthly_df['價格'].sum())
        
        st.metric(label=f"💰 本月 ({current_month}) 總花費", value=f"${monthly_spent:,}")
        st.markdown("---")
        
        # 👉 新增：如果有備份資料，就顯示「復原」按鈕
        if "backup_data" in st.session_state:
            st.warning("⚠️ 剛剛有資料被修改或刪除了。")
            if st.button("↩️ 哎呀！按錯了，復原上一次的狀態", use_container_width=True):
                try:
                    sheet.clear()
                    # 把記憶體裡的舊資料寫回去
                    sheet.update(range_name="A1", values=st.session_state["backup_data"])
                    # 復原後就把備份清空
                    del st.session_state["backup_data"]
                    st.success("✅ 已成功復原資料！")
                    st.rerun()
                except Exception as e:
                    st.error(f"復原失敗：{e}")
            st.markdown("---")

        st.markdown("💡 **提示**：勾選最左邊的「❌ 刪除」可以刪除該筆資料。修改完記得按最下方的儲存按鈕！")
        
        df = df.sort_values(by='日期', ascending=False)
        display_df = df[['日期', '種類', '食材名稱', '數量', '單位', '價格']].copy()
        
        display_df.insert(0, '❌ 刪除', False)
        
        edited_df = st.data_editor(
            display_df,
            num_rows="dynamic",
            use_container_width=True,
            hide_index=True
        )
        
        if st.button("💾 儲存修改至雲端", use_container_width=True):
            final_df = edited_df[edited_df['❌ 刪除'] == False].copy()
            final_df = final_df.drop(columns=['❌ 刪除'])
            final_df = final_df.fillna("")
            updated_data = [final_df.columns.tolist()] + final_df.values.tolist()
            
            try:
                # 👉 新增：在清空並覆蓋 Google 試算表之前，先抓取目前的資料當作備份
                current_sheet_data = sheet.get_all_values()
                st.session_state["backup_data"] = current_sheet_data
                
                sheet.clear()
                if len(updated_data) > 1:
                    sheet.update(range_name="A1", values=updated_data)
                else:
                    sheet.update(range_name="A1", values=[final_df.columns.tolist()])
                    
                st.success("✅ 修改已成功同步！")
                st.rerun()
            except Exception as e:
                st.error(f"儲存失敗：{e}")
