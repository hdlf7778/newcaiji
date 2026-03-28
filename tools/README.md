# 站点接入工具

## url_classifier.py — URL 聚类分析

```bash
# 查看已有 9,615 条数据的统计
python url_classifier.py --stats-only

# 对新 URL 做探测+分类
python url_classifier.py --input new_urls.csv --output classified.xlsx --concurrency 200

# 导出为系统批量导入格式
python url_classifier.py --export-import sources_to_import.csv
```

## enhanced_data_loader.py — 加载增强数据

```python
from enhanced_data_loader import load_enhanced_data
df = load_enhanced_data()
```

## 数据文件

- `~/Desktop/xincaiji/采集源增强数据_探测版.xlsx` — 9,615 条已探测的增强数据
- `~/Desktop/xincaiji/rule_samples.json` — 45 条 CSS 选择器规则样本
