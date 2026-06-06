---
name: technews-fetch
description: >-
  TechNews 科技新報文章抓取與分類頁爬取。Use when the user wants to
  scrape `technews.tw`, collect article lists by category, fetch full article
  content, or export TechNews articles to CSV/JSON.
---

# TechNews 科技新報文章抓取

## 用途

這個 skill 用於從 `https://technews.tw` 的分類頁抓取文章列表，並進一步進入文章頁抓取內文，整理成結構化資料，適合後續做：

- 新聞蒐集
- AI / 半導體 / 商業等主題資料集建立
- CSV / JSON 匯出
- 後續摘要、分類、embedding 或 RAG 前處理

## 適用情境

在使用這個 skill 時，使用者通常會提出類似需求：

- 抓 TechNews 某個分類近幾頁文章
- 把 TechNews 文章存成 CSV
- 抓 `ai` / `semiconductor` / `business` 分類新聞
- 從 TechNews 文章頁擷取標題、作者、日期、內文、圖片
- 建立科技新聞資料集

如果需求不是 TechNews 網站內容抓取，而是一般新聞摘要、搜尋或網站設計，不要使用這個 skill。

## 目標網站

- 網站：`https://technews.tw`
- 分類頁基底：`https://technews.tw/category/`
- 分類頁格式：`https://technews.tw/category/<category>/page/<page>/`
- 子分類頁格式：`https://technews.tw/category/<category>/<subcategory>/page/<page>/`

常見分類 slug 範例：

- `amazon`
- `ai`
- `semiconductor`
- `semiconductor/晶圓`
- `semiconductor/chip`
- `semiconductor/ic-設計`
- `semiconductor/封裝測試`
- `semiconductor/chip/cpu`
- `component`
- `finance`
- `fintech`
- `fb`
- `google`
- `internet`
- `internet-of-things-internet`
- `cutting-edge`
- `natural-science`
- `mobiledevice`
- `biotech`
- `ccc`
- `payment`
- `能源科技`
- `國際貿易`

注意：實際支援的分類與子分類清單應以程式碼中的 registry 為準，例如 `CATEGORY_REGISTRY`，不要只靠 `SKILL.md` 手動維護。

目前建議只收錄 `https://technews.tw/category/...` 路徑，排除：

- 外部子站，例如 `finance.technews.tw`、`infosecu.technews.tw`
- 非分類頁，例如專題頁、關於我們、企業入口頁

## 建議輸出欄位

每篇文章至少整理成以下欄位：

```json
{
  "category": "ai",
  "postID": "post-123456",
  "title": "文章標題",
  "link": "https://technews.tw/...",
  "image": "https://technews.tw/...jpg",
  "date": "2026-06-06 10:30",
  "author": "作者名稱",
  "content": "文章全文"
}
```

如有需要，可額外加入：

- `excerpt`
- `tags`
- `page`
- `fetched_at`
- `status_code`

## 抓取流程

### 1. 巡覽分類頁

輸入通常包含：

- `categoryIDList`
- `start_page`
- `end_page`
- 輸出格式，例如 CSV 或 JSON

分類頁 URL 規則：

```text
https://technews.tw/category/<category>/page/<page>/
```

若分類本身是多層 path，例如 `semiconductor/chip/cpu`，就直接代入，不需要拆開重組。

實作重點：

- 逐一走訪分類
- 每個分類再逐頁抓取
- 若頁面不存在、沒有文章、或結構異常，就停止該分類
- 不要盲目固定抓到第 200 頁，優先依「無資料即停止」處理

### 2. 解析分類頁文章列表

根據目前原型，優先使用這些 selector：

- 內容區：`section.site-content`
- 分類標題：`header.archive-header`
- 單篇文章：`article`
- 文章標題區：`header.entry-header`
- 文章摘要區：`div.entry-content`
- 作者與日期：`span.body`

應擷取欄位：

- `postID`: 來自 `article[id]`
- `title`: 來自文章連結的 `title`
- `link`: 來自文章連結的 `href`
- `image`: 優先取 `img[data-src]`，其次 `img[src]`
- `author`: `span.body` 的第一個值
- `date`: `span.body` 的第二個值

### 3. 解析文章詳頁

進入 `link` 後抓全文。

目前原型使用：

- `div.indent > p`

建議做法：

- 將所有段落文字串接為 `content`
- 保留段落順序
- 如果 selector 失效，先檢查網站結構，再補替代 selector，不要直接猜測

### 4. 日期格式轉換

目前原型的日期格式為：

```text
%Y 年 %m 月 %d 日 %H:%M
```

建議標準化輸出為：

```text
YYYY-MM-DD HH:MM
```

若解析失敗：

- 保留原始字串
- 記錄警告
- 不要直接中斷整批流程

## 錯誤處理

以下情況應視為正常抓取風險，而不是直接整體失敗：

- 某個分類頁不存在
- 某頁沒有文章
- 某篇文章無法進入詳頁
- 某篇文章缺圖、缺作者、缺日期
- HTML selector 因站點改版失效

建議策略：

- 分類頁請求失敗：停止該分類
- 文章頁請求失敗：略過該篇或保留空內容
- 缺少必要節點：印出簡短診斷資訊後繼續
- 每個分類都要在結束前儲存一次，避免中途資料全失

## 節流與反爬風險

此網站屬公開內容網站，但仍應避免高頻請求。

建議：

- 使用 `User-Agent`
- 每次請求之間加入隨機延遲
- 建議延遲區間 `0.5 ~ 2.0` 秒
- 不要平行大量抓取
- 若出現 403、429、跳轉異常或頁面內容明顯不是文章頁，應視為可能被擋

## 儲存策略

建議不要等全部抓完才存檔。

可採以下策略：

- 每 500 筆存一次
- 每換一個分類存一次
- 程式結束前再 flush 一次剩餘資料

建議輸出檔名包含：

- 分類名稱
- 日期
- 頁碼範圍

例如：

```text
outputs/technews-ai-page-1-20-2026-06-06.csv
outputs/technews-ai-page-1-20-2026-06-06.json
```

## 建議實作模式

如果使用 Python，優先考慮：

- `requests`
- `bs4` / `BeautifulSoup`
- `lxml`
- `csv` 或 `json`
- 視需求再用 `pandas`

若只是單純匯出，不必強制依賴 `pandas`，可優先用標準函式庫降低安裝負擔。

## Agent 執行流程

1. 先確認要抓哪些分類與頁數範圍
2. 先用單一分類、單一頁測 selector 是否仍有效
3. 再擴大抓取頁數
4. 驗證文章內文 selector 是否抓得到正文
5. 加入節流與中繼存檔
6. 最後輸出 CSV 或 JSON，並回報總筆數、失敗筆數、實際抓取頁數

## 最小驗證清單

完成腳本或調整後，至少驗證：

- 分類頁能抓到 `article`
- 標題與連結不為空
- 至少一篇文章能抓到全文
- 日期欄位格式合理
- 空頁會正確停止，而不是一直抓到最大頁數
- 輸出檔可正常開啟

## 原型邏輯摘要

你提供的原型邏輯可整理為：

- 以 `categoryIDList` 決定分類
- 逐頁抓 `https://technews.tw/category/<category>/page/<page>/`
- 從 `section.site-content` 取文章列表
- 逐篇取 `title`、`link`、`image`、`author`、`date`
- 進入文章頁抓 `div.indent > p` 內文
- 每 500 筆存一次
- 每個分類結束再存一次
- 全程以隨機 sleep 降低封鎖風險

## 回覆使用者時應提供的資訊

在實際執行這個 skill 後，回覆中應盡量包含：

- 抓取分類
- 抓取頁數範圍
- 成功筆數
- 失敗筆數
- 輸出檔路徑
- 是否遇到 selector 失效或反爬限制

## 後續可擴充方向

- 支援 `--category ai --start-page 1 --end-page 10`
- 支援 `--max-posts`
- 支援只抓列表、不進文章頁
- 支援續抓模式，避免重複文章
- 支援依日期停止抓取
- 支援輸出 markdown 摘要或 SQLite
