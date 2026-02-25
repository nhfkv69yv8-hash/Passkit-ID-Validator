import streamlit as st
import pandas as pd
import requests
import time
import jwt  # 請確保 requirements.txt 中包含 PyJWT
import os

# 1. 基礎設定
st.set_page_config(page_title="PassKit REST 檢索工具", page_icon="⚡")

# 初始化 Session State 防止 NameError
if 'last_summary' not in st.session_state:
    st.session_state.last_summary = None

def get_config(key):
    val = st.secrets.get(key) or os.environ.get(key)
    # 解決 Port 等整數型態無法執行 replace 的問題
    return str(val).replace('\\n', '\n') if val else None

# --- 2. JWT 認證生成 (修復 build_jwt_token 未定義問題) ---
def build_jwt_token():
    api.key = get_config("PK_API_KEY")
    api.secret = get_config("PK_API_SECRET")
    
    if not key or not secret:
        st.error("❌ 缺少 PK_API_KEY 或 PK_API_SECRET，請檢查 Secrets 設定。")
        return None
        
    payload = {
        "iss": key,
        "iat": int(time.time()),
        "exp": int(time.time()) + 3600  # Token 有效期 1 小時
    }
    # 根據 PassKit 規範使用 HS256 加密
    return jwt.encode(payload, secret, algorithm="HS256")

# --- 3. REST API 核心搜尋邏輯 ---
def rest_batch_search(name_list):
    results = []
    missing_names = []
    program_id = get_config("PROGRAM_ID")
    
    # 使用您確認的 REST API Prefix
    url = f"https://api.pub2.passkit.io/members/member/list/{program_id}"
    
    token = build_jwt_token()
    if not token: return [], name_list
    
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }

    # 標準化搜尋名單 (限制前 50 筆)
    search_names = [n.strip() for n in name_list if n.strip()][:50]
    progress_bar = st.progress(0)

    for idx, name in enumerate(search_names):
        try:
            # 構建符合官方 Filter 規範的 JSON Body
            body = {
                "filters": {
                    "filterGroups": [
                        {
                            "condition": "AND",
                            "fieldFilters": [
                                {
                                    "filterField": "person.displayName",
                                    "filterValue": name,
                                    "filterOperator": "eq"
                                }
                            ]
                        }
                    ]
                }
            }

            resp = requests.post(url, headers=headers, json=body)
            
            if resp.status_code == 200:
                data = resp.json()
                members = data.get('members', [])
                if members:
                    for m in members:
                        # ✅ 符合要求：搜尋姓名、稱謂、系統名、Passkit ID (放最後)
                        results.append({
                            "搜尋姓名": name.upper(),
                            "稱謂 person.salutation": m.get('person', {}).get('salutation', ''),
                            "系統名 person.displayName": m.get('person', {}).get('displayName', ''),
                            "Passkit ID": m.get('id', '') 
                        })
                else:
                    missing_names.append(name)
            else:
                st.warning(f"搜尋 {name} 失敗: HTTP {resp.status_code}")
                
        except Exception as e:
            st.error(f"搜尋 {name} 時發生異常: {e}")
            
        progress_bar.progress((idx + 1) / len(search_names))

    progress_bar.empty()
    return results, missing_names

# --- 4. 網頁介面 ---
st.title("⚡ PassKit REST 批次查詢 (v4.1)")
st.info("此版本直接透過 REST API Prefix 進行過濾，解決 SDK 版本相容性問題。")

input_text = st.text_area("請輸入姓名名單 (每行一個)", height=250, placeholder="SUHAN CHAN\nYUCHUN LEE")

if st.button("執行批次搜尋", type="primary"):
    if not input_text.strip():
        st.warning("請輸入內容。")
    else:
        names = input_text.split('\n')
        with st.spinner("正在呼叫 PassKit REST API..."):
            matches, missing = rest_batch_search(names)
            
            if matches:
                st.success(f"✅ 搜尋完成！找到 {len(matches)} 筆相符資料。")
                # 強制 DataFrame 顯示順序
                df = pd.DataFrame(matches)[["搜尋姓名", "稱謂 person.salutation", "系統名 person.displayName", "Passkit ID"]]
                st.dataframe(df, use_container_width=True)
            
            if missing:
                with st.expander("❌ 未找到名單 (請確認大小寫與空格完全一致)"):
                    st.write(", ".join(missing))
