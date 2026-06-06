# technews-fetch

抓取 `https://technews.tw` 分類頁與文章內容的雛形 skill。

目前提供：

- `SKILL.md`：skill 定義與抓取策略
- `scripts/fetch_technews.py`：可執行的初版抓取腳本
- `references/example-prompts.md`：可直接拿來觸發 skill 的提示範例
- `outputs/`：預設輸出目錄

## 目前支援

- 指定分類，例如 `ai`
- 也可只給主題關鍵字，讓程式自動猜一個最適合的分類
- 自動猜分類時，會同時列出前幾個可用分類候選
- 支援子分類路徑，例如 `semiconductor/chip/cpu`
- 內建分類清單以程式碼中的 `CATEGORY_REGISTRY` 維護，可用 `--list-categories` 以樹狀查看
- 指定起始頁與結束頁
- 可加上日期區間過濾文章
- 可用 `--period today|last-7-days|last-30-days` 快速查近期資訊
- 抓文章列表與文章內文
- 預設只抓列表欄位，不抓全文；加上 `--include-content` 才抓正文
- 輸出 JSON 或 CSV
- 可加 `--summary` 直接輸出簡易摘要
- 空頁自動停止
- 會自動處理 category path，像 `semiconductor/chip/cpu` 可直接拿來組 URL

## 快速開始

```bash
pip install requests beautifulsoup4

python scripts/fetch_technews.py --category ai --start-page 1 --end-page 2 --format json
python scripts/fetch_technews.py --topic AI --show-category-candidates
python scripts/fetch_technews.py --category semiconductor --start-page 1 --end-page 2 --format csv
python scripts/fetch_technews.py --category semiconductor/chip/cpu --start-page 1 --end-page 1 --format json
python scripts/fetch_technews.py --category ai --start-page 1 --end-page 10 --start-date 2026-06-01 --end-date 2026-06-07 --format json
python scripts/fetch_technews.py --category ai --start-page 1 --end-page 1 --include-content --format json
python scripts/fetch_technews.py --topic AI --period last-7-days --summary --format json
python scripts/fetch_technews.py --category ai --list-categories
```

若未指定 `--output`，預設檔名會自動帶入 category path 與日期區間，例如：

```text
outputs/technews-ai-2026-06-01_to_2026-06-07-20260606-184028.json
```

## 輸出欄位

- `category`
- `postID`
- `title`
- `link`
- `image`
- `date`
- `author`
- `content`

## 目前分類

以下為目前收錄方向，實際以 `--list-categories` 輸出與 `CATEGORY_REGISTRY` 為準。

- `amazon`
- `ai`
- `biotech`
- `biotech/醫療`
- `ccc`
- `ccc/accessory`
- `component`
- `component/dian-chi`
- `component/display-c`
- `component/光電科技`
- `cutting-edge`
- `cutting-edge/drone`
- `cutting-edge/leos`
- `cutting-edge/奈米`
- `cutting-edge/材料`
- `cutting-edge/機器人`
- `cutting-edge/航太科技`
- `entertainment`
- `fb`
- `finance`
- `finance/financial_statement`
- `finance/finance-report`
- `finance/realestate`
- `finance/證券`
- `finance/金融政策`
- `fintech`
- `fintech/cryptocurrency`
- `google`
- `internet`
- `internet/開放資料`
- `internet/電子商務`
- `internet/雲端`
- `internet-of-things-internet`
- `mobiledevice`
- `natural-science`
- `natural-science/環境科學`
- `payment`
- `semiconductor`
- `semiconductor/chip`
- `semiconductor/chip/cpu`
- `semiconductor/chip/gpu`
- `semiconductor/chip/memory`
- `semiconductor/ic-設計`
- `semiconductor/封裝測試`
- `semiconductor/晶圓`
- `tech-life`
- `transport/car-tech`
- `國際貿易`
- `國際貿易/國際金融`
- `科技教育`
- `軍事科技`
- `能源科技`
- `能源科技/nuclear`
- `能源科技/solar-energy`
- `能源科技/wind-power`
- `能源科技/電力儲存`

## 後續可擴充

- 多分類批次抓取
- 續抓與去重
- 輸出 SQLite 或 markdown 摘要

註：分類 slug 目前以程式碼維護，並直接採用你提供的值，例如 `國際貿易`。
若要新增或調整支援分類，請直接修改 `scripts/fetch_technews.py` 內的 `CATEGORY_REGISTRY`。
輸出檔名則會把 `/` 轉成 `-`，避免路徑被誤判成資料夾。
若只給 `--topic`，程式會根據 `CATEGORY_REGISTRY` 的 category path 與顯示名稱自動猜一個最適合的分類，並列出前幾個候選。
若指定 `--summary`，抓取完成後會直接列出簡短 digest 與前 10 筆標題。
若有指定 `--start-date` / `--end-date`，預設檔名也會附上日期區間。
