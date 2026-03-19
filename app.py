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
    # 打開指定的試算表與工作表（請確保名稱與你在 Google 雲端上設定的一模一樣）
    sheet = client.open("自煮買菜記帳本").worksheet("groceries")
except Exception as e:
    st.error(f"連線 Google 試算表失敗！錯誤訊息：{e}")
    st.stop()

# --- 2. 頁面基本設定 (置中排版，手機看更舒服) ---
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
        # 加入了「綜合採買」選項
        category = st.selectbox("種類", ["蔬菜", "肉類", "海鮮", "水果", "調味料", "主食/麵包", "綜合採買", "其他"])
        
        # 數量和單位在手機上並排顯示
        col1, col2 = st.columns(2)
        with col1:
            quantity = st.number_input("數量", min_value=0.1, value=1.0, step=0.5)
        with col2:
            unit = st.text_input("單位 (例如：把、次)", "份")
            
        price = st.number_input("總價格 (元)", min_value=0, value=0, step=10)
        
        # 手機版優化：按鈕設定為滿版寬度，方便單手點擊
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
    # 每次切換到這頁都會去 Google 試算表抓最新資料
    data = sheet.get_all_records()

    if not data:
        st.info("目前還沒有紀錄，快去「記一筆」吧！")
    else:
        df = pd.DataFrame(data)
        # 確保價格欄位是數字
        df['價格'] = pd.to_numeric(df['價格'], errors='coerce').fillna(0)
        
        # --- 計算當月總花費 ---
        current_month = datetime.now().strftime("%Y-%m")
        df['日期'] = df['日期'].astype(str)
        monthly_df = df[df['日期'].str.startswith(current_month)]
        monthly_spent = int(monthly_df['價格'].sum())
        
        # 顯示當月總花費
        st.metric(label=f"💰 本月 ({current_month}) 總花費", value=f"${monthly_spent:,}")
        
        st.markdown("---")
        st.markdown("💡 **提示**：勾選最左邊的「❌ 刪除」可以刪除該筆資料。修改完記得按最下方的儲存按鈕！")
        
        # 依照日期反向排序 (最新的在最上面)
        df = df.sort_values(by='日期', ascending=False)
        display_df = df[['日期', '種類', '食材名稱', '數量', '單位', '價格']].copy()
        
        # 👉 關鍵升級：在表格最左邊插入一個「刪除」打勾欄位
        display_df.insert(0, '❌ 刪除', False)
        
        # 互動式表格
        edited_df = st.data_editor(
            display_df,
            num_rows="dynamic", # 允許動態新增/刪除列
            use_container_width=True,
            hide_index=True
        )
        
        # 儲存按鈕也改成滿版
        if st.button("💾 儲存修改至雲端", use_container_width=True):
            # 1. 找出沒有被打勾 (要保留) 的資料
            final_df = edited_df[edited_df['❌ 刪除'] == False].copy()
            
            # 2. 把「刪除」這個輔助欄位拿掉，準備存回雲端
            final_df = final_df.drop(columns=['❌ 刪除'])
            final_df = final_df.fillna("") # 將空值填補
            
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
                st.rerun() # 重新整理網頁畫面
            except Exception as e:
                st.error(f"儲存失敗：{e}")
