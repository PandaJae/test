# 中国企业 USPTO 宣誓窗口监控工具

这个小程序用于半自动筛选：

1. 从 USPTO 导出的商标数据中，筛出中国主体；
2. 识别是否处于 5-6 年或 8-9 年宣誓/提交证据窗口；
3. 与你维护的“在美销售线索”数据做匹配；
4. 生成可跟进的汇总名单。

> 说明：本工具只做数据筛选与线索汇总，不构成法律意见。

## 输入文件

### 1) `data/uspto_cases.csv`
建议至少包含这些列（列名可配置）：

- `registration_number`
- `serial_number`
- `mark_text`
- `owner_name`
- `owner_country`
- `registration_date`（支持 `YYYY-MM-DD` / `YYYY/MM/DD` / `MM/DD/YYYY`）

### 2) `data/us_sales_signals.csv`
你维护的在美销售线索池，建议包含：

- `source`（如 Amazon / Walmart / Shopify / Customs 等）
- `seller_name`
- `brand_or_mark`
- `url`
- `confidence`（0~1，可选）

## 用法

```bash
python3 src/uspto_monitor.py \
  --uspto-csv data/uspto_cases.csv \
  --sales-csv data/us_sales_signals.csv \
  --output reports/targets.csv
```

## 输出

`reports/targets.csv` 主要字段：

- `registration_number`
- `serial_number`
- `mark_text`
- `owner_name`
- `owner_country`
- `registration_date`
- `declaration_window`（`year_5_6` / `year_8_9`）
- `years_since_registration`
- `sales_match`
- `matched_source`
- `matched_seller`
- `matched_brand`
- `matched_url`
- `match_score`

## 你可以怎么扩展

- 将 `data/uspto_cases.csv` 替换成你通过 USPTO API 拉取的数据；
- 在 `src/uspto_monitor.py` 的 `find_sales_match` 中接入爬虫/第三方搜索 API；
- 增加自动邮件提醒，把到期窗口客户推送给业务团队。
