---
name: technews-fetch
category: research
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

建議分工：

- SKILL / agent：理解使用者需求，先決定應該抓哪些分類
- `scripts/fetch_technews.py`：接收明確分類後執行抓取與輸出

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
若要讓 SKILL 取得目前可用分類，優先執行：

```bash
python scripts/fetch_technews.py --dump-category-registry
```

這會輸出機器可讀 JSON，包含 `slug`、`label`、`parent`，適合 agent 先做分類決策。

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

- 一個或多個明確分類
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

### 1.5 直接讀取單篇文章

若 SKILL 已經從前一步拿到文章連結，或使用者直接指定某篇 TechNews 文章，優先直接讀單篇文章，不必重新從分類頁巡覽。

可使用：

```bash
python scripts/fetch_technews.py --article-url <article-url> --format json
```

適合情境：

- 使用者要看某篇文章全文
- 已從列表結果挑出少數文章，準備補抓正文
- 想驗證文章頁 selector 是否仍然有效

### 1.6 從既有列表補抓正文

若 SKILL 已經先抓到文章列表，後續只想對少數文章補抓正文，優先使用既有列表檔，不要重跑分類頁。

可使用：

```bash
python scripts/fetch_technews.py --input-file <list-json-or-csv> --hydrate-content --limit 3 --output <output-json>
```

適合情境：

- 先抓列表，再補前幾篇正文
- 只想對人工挑選後的文章補抓內容
- 想降低重複抓分類頁的成本

若要先挑文章再補抓，可搭配：

- `--filter-keyword <keyword>`：只保留標題、內容或連結含關鍵字的列；可重複傳入多個關鍵字
- `--sort-by-date newest|oldest`：先排序再套用 `--limit`
- `--select-links-file <txt-file>`：只補抓指定 URL 清單中的文章

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

1. 先執行 `python scripts/fetch_technews.py --dump-category-registry` 取得目前可用分類
2. 根據使用者意圖決定一個或多個相關分類
3. 先用單一分類、單一頁測 selector 是否仍有效
4. 再擴大抓取頁數或增加其他分類
5. 驗證文章內文 selector 是否抓得到正文
6. 最後輸出 CSV 或 JSON，並回報實際抓取分類、總筆數、失敗筆數、實際抓取頁數

對模糊需求，不要只依賴腳本內建的 `--topic` 猜測單一分類。像「能源政策」、「供應鏈風險」、「美中科技戰」這類任務，應由 SKILL 先判斷可能涉及的多個分類，再多次傳入 `--category` 執行。

例如：

```bash
python scripts/fetch_technews.py --category 能源科技 --category finance/金融政策 --period last-7-days --summary --format json
```

## 模糊主題決策規則

當使用者沒有直接指定分類，而是描述一個主題、議題、政策、風險或趨勢時，SKILL 應先做分類決策，再執行抓取。

### 1. 先判斷需求類型

- 若使用者給的是明確分類或 slug，例如 `ai`、`semiconductor/chip/gpu`，直接用該分類
- 若使用者給的是具體名詞，且高度對應單一分類，例如 `比特幣`、`GPU`、`核能`，可先從 registry 找最接近的 1 至 2 個分類
- 若使用者給的是抽象主題或任務描述，例如「能源政策」、「供應鏈風險」、「美中科技戰」，預設視為多分類需求

### 2. 選分類時的優先順序

- 先看 `label` 是否直接對應主題核心詞
- 再看 `slug` 與 `parent` 階層是否能補足語境
- 優先選擇能完整覆蓋主題的父分類與最相關子分類
- 若主題同時含有產業面與政策面，至少各選一個相關分類
- 若不確定是否需要某分類，先少量測試 1 頁，再決定是否擴大

### 3. 類型對應規則

- 技術名詞：優先對應技術或產業分類，例如 `GPU` -> `semiconductor/chip/gpu`
- 公司名稱：優先對應公司或平台分類，例如 `Google` -> `google`
- 產業議題：同時考慮產業主分類與相關子分類，例如 `半導體供應鏈` -> `semiconductor` 加上 `semiconductor/chip`
- 政策 / 法規 / 金融影響：除了主題產業分類外，補入政策或金融分類，例如 `能源政策` -> `能源科技` 加上 `finance/金融政策`
- 跨境或地緣議題：補入 `國際貿易` 或其子分類，例如 `美中科技戰` -> `semiconductor`、`國際貿易`

### 4. 建議選取數量

- 明確單一主題：1 個分類
- 具體但可能跨面向的主題：2 至 3 個分類
- 抽象議題或政策題：3 至 5 個分類
- 除非使用者明確要求廣泛蒐集，否則不要一次選太多分類，避免噪音過高

### 5. 預設執行策略

- 先抓最近 7 天或使用者指定期間
- 先不加 `--include-content`
- 先抓每個分類 1 至 2 頁驗證訊號品質
- 若結果過少，再擴大頁數或補更多分類
- 若結果噪音過高，再縮減分類或之後加文章層關鍵字過濾

## 決策示例

### 示例：能源政策

使用者需求：

```text
找出本周對於能源政策的相關文章
```

建議判斷：

- 主題核心是能源
- 次要面向是政策
- 這不是單一分類問題，應至少涵蓋能源面與政策面

建議分類：

- `能源科技`
- `能源科技/nuclear`
- `能源科技/solar-energy`
- `能源科技/wind-power`
- `能源科技/電力儲存`
- `finance/金融政策`

若要先做低成本驗證，可先從：

- `能源科技`
- `finance/金融政策`

開始執行：

```bash
python scripts/fetch_technews.py --category 能源科技 --category finance/金融政策 --period last-7-days --summary --format json
```

若結果仍不足，再加入能源子分類。

### 示例：美中科技戰

使用者需求：

```text
整理本周美中科技戰相關文章
```

建議分類：

- `semiconductor`
- `ai`
- `國際貿易`
- `國際貿易/國際金融`

### 示例：比特幣

使用者需求：

```text
抓最近 7 天比特幣新聞
```

建議分類：

- `fintech/cryptocurrency`

這類具體名詞可視情況搭配 `--topic` 做快速探索，但正式抓取仍建議改用明確 `--category`。

### 示例：讀取單篇文章內容

使用者需求：

```text
請把這篇 TechNews 文章內容讀出來：https://technews.tw/...
```

建議做法：

- 不要先跑分類頁
- 直接使用 `--article-url`
- 若只是要看內容，可不指定 `--output`，直接印 JSON
- 若要後續保存，再指定 `--output`

例如：

```bash
python scripts/fetch_technews.py --article-url https://technews.tw/... --format json
```

### 示例：先列表再補正文

使用者需求：

```text
先抓 TechNews 的 ai 分類最近 7 天文章列表，挑出最重要的 3 篇後，再把那 3 篇全文抓出來。
```

建議做法：

- 第一輪先跑分類列表，不加 `--include-content`
- 第二輪直接讀取第一輪輸出的 JSON 或 CSV
- 用 `--hydrate-content --limit 3` 補抓前 3 篇內容

例如：

```bash
python scripts/fetch_technews.py --category ai --period last-7-days --format json --output outputs/technews-ai-list.json
python scripts/fetch_technews.py --input-file outputs/technews-ai-list.json --hydrate-content --limit 3 --output outputs/technews-ai-top3-content.json
```

若想只補抓最新、且和 AI 電力議題相關的文章，可改成：

```bash
python scripts/fetch_technews.py --input-file outputs/technews-ai-list.json --filter-keyword AI --filter-keyword 電力 --sort-by-date newest --limit 3 --hydrate-content --output outputs/technews-ai-power-top3-content.json
```

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
