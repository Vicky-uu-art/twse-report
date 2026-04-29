# 📊 台股每日成交金額前30名自動報表

每日盤後自動抓取台股成交金額前30名，產生含柱狀圖、概念股標記、個股新聞的 HTML 報表，並透過 **GitHub Pages** 提供可分享的網頁連結。

---

## 功能特色

- 📊 **互動式柱狀圖**：一眼看出前30名成交金額差距
- 🟡 **新進榜個股 Highlight**：與前一日比較，黃色標記今日新進榜
- 🟠 **新概念族群 Highlight**：橘色標記今日首次出現的概念股
- 📰 **個股新聞**：自動抓取鉅亨網＋Yahoo股市當日相關新聞
- 📅 **歷史回顧**：每日報表永久保存，頁面上方可切換日期
- 🔗 **可分享網址**：任何人都能用網址瀏覽，不需登入

---

## 設定步驟（一次性，約 15 分鐘）

### 步驟一：建立 GitHub 帳號
1. 前往 https://github.com/signup
2. 輸入 Email、密碼、使用者名稱，完成驗證

### 步驟二：建立 Repository
1. 登入後點右上角 **＋** → **New repository**
2. Repository name 輸入：`twse-report`
3. 選擇 **Public**（公開，這樣 GitHub Pages 才免費）
4. 勾選 **Add a README file**
5. 點 **Create repository**

### 步驟三：上傳程式碼
1. 在 repository 頁面點 **Add file** → **Upload files**
2. 按照以下結構上傳所有檔案：
   ```
   .github/workflows/daily_report.yml
   scripts/fetch_and_report.py
   reports/          （空資料夾，放一個 .gitkeep 空檔）
   data/             （空資料夾，放一個 .gitkeep 空檔）
   ```

### 步驟四：啟用 GitHub Pages
1. 在 repository 頁面點 **Settings**
2. 左側選單點 **Pages**
3. Source 選 **Deploy from a branch**
4. Branch 選 **main**，資料夾選 **/ (root)**
5. 點 **Save**

> ⚠️ 注意：GitHub Pages 需要設定指向 `reports/` 子目錄。  
> 您的報表網址會是：`https://您的帳號.github.io/twse-report/reports/`

### 步驟五：手動執行第一次
1. 點 repository 上方的 **Actions** 頁籤
2. 左側選「台股每日成交金額報表」
3. 右側點 **Run workflow** → **Run workflow**
4. 等待約 2–3 分鐘，完成後前往 Pages 網址查看

---

## 自動執行時間

每週一到週五，台灣時間 **下午 4:35** 自動執行。  
（證交所通常在 4:30 前後更新盤後資料）

---

## 檔案結構

```
twse-report/
├── .github/workflows/
│   └── daily_report.yml     ← 自動排程設定
├── scripts/
│   └── fetch_and_report.py  ← 主程式
├── reports/
│   ├── index.html           ← 歷史總覽首頁
│   ├── 2026-04-28.html      ← 每日報表
│   └── ...
├── data/
│   ├── 2026-04-28.json      ← 每日原始資料（供比較用）
│   └── ...
└── README.md
```

---

## 注意事項

- 台灣證交所 API 在休市日（假日、颱風假）不會有資料，程式會跳過
- 新聞抓取可能因網站結構異動而需要更新程式
- 若某日 GitHub Actions 執行失敗，可手動到 Actions 頁面重新執行
