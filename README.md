
# 兒童早療記錄小幫手 v9｜家長登入版

## 本版功能
- 家長 Email/密碼登入
- 家長建立帳號
- 忘記密碼
- 登出
- 資料改存 Supabase 雲端資料庫
- 每位家長登入後只能看到自己的資料
- 保留 v8 功能：
  - 新增兒童資料
  - 每週預設療程
  - 實際治療紀錄
  - 療程編號
  - 療程次數
  - 到期日紅字
  - 超過到期日不可新增
  - 勾選刪除
  - 兒童復健風格背景

## 使用前設定

請先將：

`.streamlit/secrets.example.toml`

複製成：

`.streamlit/secrets.toml`

並填入你的 Supabase：

```toml
SUPABASE_URL = "你的 API URL"
SUPABASE_KEY = "你的 Publishable key"
```

## 安裝套件

```bash
pip install -r requirements.txt
```

## 執行 App

```bash
streamlit run app.py
```
