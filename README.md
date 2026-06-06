# technews-fetch

抓取 `https://technews.tw` 分類頁、單篇文章與文章正文的 TechNews skill。

目前提供：

- `SKILL.md`：skill 定義與分類決策規則
- `scripts/fetch_technews.py`：執行抓取、補正文與輸出
- `references/example-prompts.md`：可直接觸發 skill 的 prompt 範例
- `outputs/`：預設輸出目錄

## 使用原則

- SKILL / agent 先判斷要抓哪些分類
- 腳本負責執行明確分類、單篇文章或既有列表的後續處理
- 明確需求用 `--category`
- 模糊需求先用 `--dump-category-registry` 看可用分類，再決定 2 到 5 個 `--category`
- 預設先抓列表，不先抓全文

## 主要能力

- 匯出分類 registry：`--dump-category-registry`
- 單分類 / 多分類抓取：重複 `--category`
- 近期日期篩選：`--period today|last-7-days|last-30-days`
- 單篇文章讀取：`--article-url`
- 分類抓取時直接抓全文：`--include-content`
- 從既有 JSON / CSV 列表補抓正文：`--input-file --hydrate-content`
- 補正文前先篩選：`--filter-keyword`、`--sort-by-date`、`--select-links-file`
- 摘要輸出：`--summary`
- 輸出格式：`json` / `csv`

## 安裝

```bash
pip install requests beautifulsoup4
```

## 常用流程

### 1. 先看可用分類

```bash
python scripts/fetch_technews.py --dump-category-registry
```

### 2. 抓單一分類列表

```bash
python scripts/fetch_technews.py --category ai --period last-7-days --format json --summary
```

### 3. 抓多個分類

```bash
python scripts/fetch_technews.py --category 能源科技 --category finance/金融政策 --period last-7-days --format json --summary
```

### 4. 直接讀單篇文章

```bash
python scripts/fetch_technews.py --article-url https://technews.tw/2026/06/06/computex-ping-cheng-power-shortage-ai-biggest-challenge-delta-electronics-one-stop-vertical-integration-grid-chip/ --format json
```

### 5. 先抓列表，再補正文

```bash
python scripts/fetch_technews.py --category ai --period last-7-days --format json --output outputs/technews-ai-list.json
python scripts/fetch_technews.py --input-file outputs/technews-ai-list.json --hydrate-content --limit 3 --output outputs/technews-ai-top3-content.json
```

### 6. 先篩文章，再補正文

```bash
python scripts/fetch_technews.py --input-file outputs/technews-ai-list.json --filter-keyword AI --sort-by-date newest --limit 3 --hydrate-content --output outputs/technews-ai-filtered-top3.json
```

## 模糊需求建議流程

像「能源政策」、「供應鏈風險」、「美中科技戰」這類需求，不要直接依賴單一 `--topic`。

推薦做法：

1. 先執行 `--dump-category-registry`
2. 由 SKILL 選 2 到 5 個相關分類
3. 先抓最近 7 天或先抓 1 到 2 頁
4. 看結果是否過少或噪音過高，再調整分類
5. 需要正文時，再用 `--input-file --hydrate-content` 補抓

例如：`找出本周對於能源政策的相關文章`

先做低成本驗證：

```bash
python scripts/fetch_technews.py --category 能源科技 --category finance/金融政策 --period last-7-days --summary --format json
```

如果結果不足，再擴大：

```bash
python scripts/fetch_technews.py --category 能源科技 --category 能源科技/nuclear --category 能源科技/solar-energy --category 能源科技/wind-power --category 能源科技/電力儲存 --category finance/金融政策 --period last-7-days --summary --format json
```

## 補正文工作流

若已經有列表檔，可直接從既有資料補抓正文，不必重跑分類頁。

```bash
python scripts/fetch_technews.py --input-file outputs/technews-ai-list.json --hydrate-content --limit 3 --output outputs/technews-ai-top3-content.json
```

常用搭配：

- `--filter-keyword AI --filter-keyword 電力`：只保留同時命中的列
- `--sort-by-date newest`：先按日期排序再套用 `--limit`
- `--select-links-file selected-links.txt`：只補抓指定 URL 清單

## 輸出說明

輸出欄位：

- `category`
- `postID`
- `title`
- `link`
- `image`
- `date`
- `author`
- `content`

若未指定 `--output`，分類抓取時會自動輸出到 `outputs/`，檔名包含分類與日期區間，例如：

```text
outputs/technews-ai-2026-06-01_to_2026-06-07-20260606-184028.json
```

多分類時，預設檔名會像：

```text
outputs/technews-multi-2-categories-2026-06-01_to_2026-06-07-20260606-184028.json
```

單篇文章與 `--input-file` 模式若未指定 `--output`，會直接把 JSON 印到 stdout。

## 備註

- 支援分類以 `scripts/fetch_technews.py` 內的 `CATEGORY_REGISTRY` 為準
- `--topic` 仍可用於手動探索，但不建議當成主要決策入口
- 若要新增或調整分類，請修改 `scripts/fetch_technews.py`
