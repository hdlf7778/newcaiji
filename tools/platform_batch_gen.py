"""
平台批量配置生成工具 — T34

为聚类后的平台站点批量生成采集源配置并导入系统。

接入顺序（基于实测分布）:
  第一批: 模板I（政务云 36.8%）— 直接复用平台参数，批量导入效率最高
  第二批: 模板A（静态列表 32.6%）— 需要 LLM 规则生成
  第三批: 模板F（登录态 23.9%）— 需配合反爬能力

使用方式:
  # 通过 API 批量导入（需要 task-manager 运行）
  python platform_batch_gen.py --platform jpaas_zhejiang --input gov_sites.csv --api http://localhost:8080

  # 生成导入 CSV（离线，不调用 API）
  python platform_batch_gen.py --platform jpaas_zhejiang --input gov_sites.csv --output import_ready.csv

  # 从增强数据中按模板导出
  python platform_batch_gen.py --from-enhanced --template I --output gov_cloud_import.csv

  # 查看支持的平台列表
  python platform_batch_gen.py --list-platforms
"""
import argparse
import csv
import json
import sys
import os

sys.path.insert(0, os.path.dirname(__file__))

import pandas as pd

try:
    import httpx
except ImportError:
    httpx = None

from enhanced_data_loader import load_enhanced_data

# ============================================================
# 平台配置模板（一个平台一套默认参数）
# ============================================================
PLATFORM_CONFIGS = {
    "jpaas_zhejiang": {
        "name": "浙江JPAAS政务云",
        "template": "gov_cloud_platform",
        "default_list_rule": {
            "list_container": ".xxgk_list ul",
            "list_item": "li",
            "title_selector": "a",
            "url_selector": "a",
            "date_selector": "span.date",
            "max_items": 20,
        },
        "default_detail_rule": {
            "title_selector": "h1",
            "content_selector": ".article",
            "publish_time_selector": ".ly span",
            "remove_selectors": ["script", "style", ".share-bar"],
        },
        "csv_fields": ["name", "column_name", "url", "web_id", "page_id", "node_id", "xxgk_id"],
        "platform_params_map": {
            "web_id": "web_id",
            "page_id": "page_id",
            "node_id": "node_id",
            "xxgk_id": "xxgk_id",
        },
    },
    "dfwsrc": {
        "name": "dfwsrc系列(福建)",
        "template": "iframe_loader",
        "default_list_rule": {"max_items": 20},
        "default_detail_rule": {},
        "csv_fields": ["name", "column_name", "url", "zone_id"],
        "platform_params_map": {"zone_id": "zone_id"},
    },
    "standard_gov": {
        "name": "标准政务网站",
        "template": "gov_cloud_platform",
        "default_list_rule": {"max_items": 20},
        "default_detail_rule": {
            "title_selector": "h1",
            "content_selector": ".TRS_Editor, .article_con, .content, .bt_content",
            "publish_time_selector": "span",
            "remove_selectors": ["script", "style", "nav", "footer"],
        },
        "csv_fields": ["name", "column_name", "url", "region"],
        "platform_params_map": {},
    },
    "static_list": {
        "name": "静态列表页(通用)",
        "template": "static_list",
        "default_list_rule": {
            "list_container": "ul",
            "list_item": "li",
            "title_selector": "a",
            "url_selector": "a",
            "date_selector": "span",
            "max_items": 20,
        },
        "default_detail_rule": {
            "title_selector": "h1, h2",
            "content_selector": ".TRS_Editor, .content, .article-content",
            "publish_time_selector": "span",
            "remove_selectors": ["script", "style"],
        },
        "csv_fields": ["name", "column_name", "url", "region"],
        "platform_params_map": {},
    },
}


def list_platforms():
    """列出支持的平台"""
    print("支持的平台:")
    print(f"{'平台代码':<20} {'名称':<25} {'模板':<25} {'接入优先级'}")
    print("-" * 85)
    priority_map = {
        "jpaas_zhejiang": "第一批(I=36.8%)",
        "dfwsrc": "第一批(B<1%)",
        "standard_gov": "第一批(I=36.8%)",
        "static_list": "第二批(A=32.6%)",
    }
    for code, cfg in PLATFORM_CONFIGS.items():
        print(f"{code:<20} {cfg['name']:<25} {cfg['template']:<25} {priority_map.get(code, '')}")
    print(f"\n共 {len(PLATFORM_CONFIGS)} 个平台配置")


def generate_import_csv(platform: str, input_csv: str, output_csv: str):
    """从平台 CSV 生成系统批量导入格式"""
    if platform not in PLATFORM_CONFIGS:
        print(f"❌ 未知平台: {platform}. 使用 --list-platforms 查看")
        sys.exit(1)

    cfg = PLATFORM_CONFIGS[platform]
    df = pd.read_csv(input_csv)
    print(f"读取 {len(df)} 条, 平台: {cfg['name']} ({cfg['template']})")

    rows = []
    for _, row in df.iterrows():
        # 构造 platform_params
        params = {}
        for csv_field, param_key in cfg["platform_params_map"].items():
            if csv_field in row and pd.notna(row[csv_field]):
                params[param_key] = str(row[csv_field])

        import_row = {
            "url": str(row.get("url", "")),
            "name": str(row.get("name", "")),
            "column_name": str(row.get("column_name", "")) if "column_name" in row else "",
            "region": str(row.get("region", "")) if "region" in row else "",
            "template": cfg["template"],
            "platform": platform,
            "platform_params": json.dumps(params, ensure_ascii=False) if params else "",
            "priority": 5,
        }
        rows.append(import_row)

    out_df = pd.DataFrame(rows)
    out_df.to_csv(output_csv, index=False, encoding='utf-8-sig')
    print(f"✅ 生成导入文件: {output_csv} ({len(out_df)} 条)")
    return out_df


def import_via_api(platform: str, input_csv: str, api_base: str, token: str = ""):
    """通过 API 批量导入"""
    if httpx is None:
        print("❌ 需要 httpx: pip install httpx")
        sys.exit(1)

    headers = {"Content-Type": "multipart/form-data"}
    if token:
        headers["Authorization"] = f"Bearer {token}"

    with open(input_csv, 'rb') as f:
        files = {"file": (os.path.basename(input_csv), f, "text/csv")}
        data = {"platform": platform}

        resp = httpx.post(
            f"{api_base}/api/sources/import-platform",
            files=files, data=data, headers={"Authorization": f"Bearer {token}"} if token else {},
            timeout=60,
        )

    if resp.status_code == 200:
        result = resp.json()
        data = result.get("data", {})
        print(f"✅ API 导入成功:")
        print(f"  总数: {data.get('total', '?')}")
        print(f"  导入: {data.get('imported', '?')}")
        print(f"  重复: {data.get('duplicates', '?')}")
        print(f"  无效: {data.get('invalid', '?')}")
    else:
        print(f"❌ API 导入失败: HTTP {resp.status_code}")
        print(f"  {resp.text[:300]}")


def export_from_enhanced(template: str, output_csv: str):
    """从增强数据中按模板类型导出"""
    df = load_enhanced_data()

    template_map = {'A': 'static_list', 'I': 'gov_cloud_platform', 'F': 'auth_required',
                     'B': 'iframe_loader', 'C': 'api_json', 'G': 'spa_render',
                     'H': 'rss_feed', 'D': 'wechat_article'}

    filtered = df[df['最终模板'] == template]
    print(f"模板 {template}: {len(filtered)} 条 (总 {len(df)} 条)")

    if len(filtered) == 0:
        print("⚠️ 无匹配数据")
        return

    rows = []
    for _, row in filtered.iterrows():
        rows.append({
            "url": row.get("网站链接", ""),
            "name": row.get("网站名称", ""),
            "column_name": row.get("栏目名称", ""),
            "region": str(row.get("省份", "")) + str(row.get("城市", "")),
            "template": template_map.get(template, ""),
            "platform": row.get("所属平台", "") if pd.notna(row.get("所属平台")) else "",
            "priority": 5,
        })

    out_df = pd.DataFrame(rows)
    out_df.to_csv(output_csv, index=False, encoding='utf-8-sig')
    print(f"✅ 导出: {output_csv} ({len(out_df)} 条)")


def main():
    parser = argparse.ArgumentParser(description='平台批量配置生成工具')
    parser.add_argument('--list-platforms', action='store_true', help='列出支持的平台')
    parser.add_argument('--platform', help='平台代码')
    parser.add_argument('--input', help='输入 CSV 文件')
    parser.add_argument('--output', help='输出 CSV 文件')
    parser.add_argument('--api', help='API 地址 (如 http://localhost:8080)')
    parser.add_argument('--token', default='', help='JWT Token')
    parser.add_argument('--from-enhanced', action='store_true', help='从增强数据导出')
    parser.add_argument('--template', help='模板类型 (与 --from-enhanced 配合)')
    args = parser.parse_args()

    if args.list_platforms:
        list_platforms()
        return

    if args.from_enhanced:
        if not args.template or not args.output:
            print("用法: --from-enhanced --template I --output output.csv")
            return
        export_from_enhanced(args.template, args.output)
        return

    if not args.platform or not args.input:
        print("用法: --platform <name> --input <csv> [--output <csv>] [--api <url>]")
        print("或:   --list-platforms")
        print("或:   --from-enhanced --template I --output output.csv")
        return

    if args.api:
        import_via_api(args.platform, args.input, args.api, args.token)
    else:
        output = args.output or f"import_{args.platform}.csv"
        generate_import_csv(args.platform, args.input, output)


if __name__ == '__main__':
    main()
