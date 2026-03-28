"""
URL 聚类分析脚本 — T33

功能:
1. 加载已有 9,615 条探测数据作为基础
2. 对新 URL 做 HTTP HEAD 探测 + 指纹提取
3. 聚类输出：平台覆盖列表 + 模板分布 + 统计报告

使用:
  # 仅查看已有数据统计
  python url_classifier.py --stats-only

  # 对新 CSV 文件中的 URL 做探测+分类
  python url_classifier.py --input new_urls.csv --output classified.xlsx --concurrency 200

  # 对已有数据生成导入文件
  python url_classifier.py --export-import sources_to_import.csv
"""
import argparse
import asyncio
import re
import sys
import os
import time
from urllib.parse import urlparse
from collections import Counter

sys.path.insert(0, os.path.dirname(__file__))

import pandas as pd

try:
    import httpx
except ImportError:
    print("请安装 httpx: pip install httpx")
    sys.exit(1)

from enhanced_data_loader import load_enhanced_data, get_template_stats, get_platform_stats, get_probed_domains

# 已知平台域名特征 → 模板映射
PLATFORM_RULES = {
    'mp.weixin.qq.com': ('微信公众号', 'D'),
    'dfwsrc.com': ('dfwsrc系列', 'B'),
}

GOV_CMS_PATTERNS = [
    (r'/col/col\d+', '政务CMS(col模式)', 'I'),
    (r'xxgk\.html|xxgk\.jhtml|zwgk', '政务信息公开平台', 'I'),
    (r'/module/web/jpage', '政务CMS(jpage)', 'I'),
    (r'eportal|portal\.php', '电子政务门户', 'I'),
]

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
    'Accept': 'text/html,application/xhtml+xml',
}


async def probe_url(client: httpx.AsyncClient, sem: asyncio.Semaphore, url: str) -> dict:
    """对单个 URL 做 HTTP 探测"""
    result = {'url': url, 'status': 0, 'template': '', 'platform': '', 'error': ''}
    async with sem:
        try:
            resp = await client.get(url, follow_redirects=True, timeout=httpx.Timeout(connect=8, read=12))
            result['status'] = resp.status_code
            html = resp.text[:5000] if len(resp.text) > 0 else ''

            # 域名规则
            domain = urlparse(url).netloc.lower()
            for pattern, (platform, tpl) in PLATFORM_RULES.items():
                if pattern in domain:
                    result['template'] = tpl
                    result['platform'] = platform
                    return result

            # 政务云特征
            for pattern, platform, tpl in GOV_CMS_PATTERNS:
                if re.search(pattern, url, re.I) or re.search(pattern, html[:2000], re.I):
                    result['template'] = tpl
                    result['platform'] = platform
                    return result

            # 响应分析
            ct = resp.headers.get('content-type', '')
            if 'application/json' in ct:
                result['template'] = 'C'
                return result
            if '<rss' in html[:500] or '<feed' in html[:500]:
                result['template'] = 'H'
                return result

            # 登录态检测
            if resp.status_code == 403:
                result['template'] = 'F'
                return result
            if any(k in html[:3000].lower() for k in ['请登录', 'login', 'captcha', '验证码']):
                result['template'] = 'F'
                return result

            # SPA 检测
            has_vue = 'vue' in html.lower() or 'id="app"' in html
            has_react = 'react' in html.lower() or '__next' in html
            body_text = re.sub(r'<script.*?</script>', '', html, flags=re.DOTALL|re.I)
            body_text = re.sub(r'<[^>]+>', '', body_text).strip()
            if (has_vue or has_react) and len(body_text) < 200:
                result['template'] = 'G'
                return result

            # 政府/高校默认
            if domain.endswith('.gov.cn'):
                result['template'] = 'A'
                return result
            if domain.endswith('.edu.cn'):
                result['template'] = 'A'
                return result

            # 有足够链接 → 静态列表
            links = len(re.findall(r'<a\s+[^>]*href=', html))
            if links >= 5:
                result['template'] = 'A'
            else:
                result['template'] = 'A?'

        except httpx.TimeoutException:
            result['error'] = 'TIMEOUT'
        except Exception as e:
            result['error'] = f'{type(e).__name__}'

    return result


async def probe_urls(urls: list[str], concurrency: int = 200) -> list[dict]:
    """批量探测 URL"""
    sem = asyncio.Semaphore(concurrency)
    results = []
    total = len(urls)

    async with httpx.AsyncClient(headers=HEADERS, verify=False, follow_redirects=True) as client:
        tasks = [probe_url(client, sem, url) for url in urls]
        batch_size = 500
        for i in range(0, len(tasks), batch_size):
            batch = await asyncio.gather(*tasks[i:i+batch_size], return_exceptions=True)
            for r in batch:
                if isinstance(r, Exception):
                    results.append({'url': '', 'error': str(r), 'template': 'ERR'})
                else:
                    results.append(r)
            done = min(i + batch_size, total)
            print(f"  探测进度: {done}/{total}")

    return results


def generate_report(df_existing: pd.DataFrame, df_new: pd.DataFrame = None) -> str:
    """生成统计报告"""
    report = []
    report.append("=" * 60)
    report.append("采集源聚类分析报告")
    report.append("=" * 60)

    # 已有数据统计
    report.append(f"\n一、已探测数据 ({len(df_existing)} 条)")
    report.append("-" * 40)
    tpl_stats = get_template_stats(df_existing)
    for tpl, cnt in sorted(tpl_stats.items(), key=lambda x: -x[1]):
        report.append(f"  模板 {tpl}: {cnt:>6} ({cnt/len(df_existing)*100:.1f}%)")

    plat_stats = get_platform_stats(df_existing)
    if plat_stats:
        report.append(f"\n  已识别平台:")
        for plat, cnt in sorted(plat_stats.items(), key=lambda x: -x[1])[:10]:
            report.append(f"    {plat}: {cnt}")

    # 重点三类占比
    total = len(df_existing)
    i_cnt = tpl_stats.get('I', 0)
    a_cnt = tpl_stats.get('A', 0)
    f_cnt = tpl_stats.get('F', 0)
    report.append(f"\n  重点模板: I={i_cnt}({i_cnt/total*100:.1f}%) + A={a_cnt}({a_cnt/total*100:.1f}%) + F={f_cnt}({f_cnt/total*100:.1f}%) = {(i_cnt+a_cnt+f_cnt)/total*100:.1f}%")

    # 新探测数据统计
    if df_new is not None and len(df_new) > 0:
        report.append(f"\n二、新探测数据 ({len(df_new)} 条)")
        report.append("-" * 40)
        new_stats = df_new['template'].value_counts()
        for tpl, cnt in new_stats.items():
            report.append(f"  模板 {tpl}: {cnt:>6} ({cnt/len(df_new)*100:.1f}%)")

        errors = df_new[df_new['error'] != '']
        if len(errors) > 0:
            report.append(f"\n  探测失败: {len(errors)} 条")
            err_types = errors['error'].value_counts()
            for et, cnt in err_types.head(5).items():
                report.append(f"    {et}: {cnt}")

    # 合计
    if df_new is not None:
        combined = len(df_existing) + len(df_new)
        report.append(f"\n三、合计: {combined} 条")
    else:
        report.append(f"\n合计: {len(df_existing)} 条")

    return "\n".join(report)


def export_for_import(df: pd.DataFrame, output_path: str):
    """导出为系统批量导入格式 CSV"""
    import_df = pd.DataFrame({
        'url': df['网站链接'],
        'name': df['网站名称'],
        'column_name': df.get('栏目名称', ''),
        'region': df.get('省份', '').astype(str) + df.get('城市', '').astype(str),
        'template': df['最终模板'].map({
            'A': 'static_list', 'I': 'gov_cloud_platform', 'F': 'auth_required',
            'B': 'iframe_loader', 'C': 'api_json', 'G': 'spa_render',
            'H': 'rss_feed', 'D': 'wechat_article', 'A?': '',
        }).fillna(''),
        'platform': df.get('所属平台', '').fillna(''),
        'priority': 5,
    })
    import_df.to_csv(output_path, index=False, encoding='utf-8-sig')
    print(f"导出批量导入文件: {output_path} ({len(import_df)} 条)")


def main():
    parser = argparse.ArgumentParser(description='采集源 URL 聚类分析')
    parser.add_argument('--stats-only', action='store_true', help='仅显示已有数据统计')
    parser.add_argument('--input', help='新 URL 列表 CSV 文件')
    parser.add_argument('--output', default='classified_new.xlsx', help='探测结果输出文件')
    parser.add_argument('--concurrency', type=int, default=200, help='探测并发数')
    parser.add_argument('--export-import', help='导出系统批量导入格式 CSV')
    parser.add_argument('--enhanced-data', help='增强数据文件路径')
    args = parser.parse_args()

    # 加载已有数据
    try:
        df_existing = load_enhanced_data(args.enhanced_data)
    except FileNotFoundError as e:
        print(f"⚠️ {e}")
        df_existing = pd.DataFrame()

    if args.stats_only:
        print(generate_report(df_existing))
        return

    if args.export_import:
        if len(df_existing) == 0:
            print("无数据可导出")
            return
        export_for_import(df_existing, args.export_import)
        return

    if args.input:
        # 读取新 URL
        new_df = pd.read_csv(args.input)
        url_col = 'url' if 'url' in new_df.columns else new_df.columns[0]
        new_urls = new_df[url_col].dropna().tolist()

        # 排除已探测的
        probed_domains = get_probed_domains(df_existing) if len(df_existing) > 0 else set()
        unprobed = [u for u in new_urls if urlparse(str(u)).netloc.lower() not in probed_domains]
        print(f"新 URL: {len(new_urls)}, 排除已探测: {len(new_urls)-len(unprobed)}, 待探测: {len(unprobed)}")

        if unprobed:
            start = time.time()
            results = asyncio.run(probe_urls(unprobed, args.concurrency))
            elapsed = time.time() - start
            print(f"探测完成: {len(results)} 条, 耗时 {elapsed:.1f}s")

            df_new = pd.DataFrame(results)
            df_new.to_excel(args.output, index=False)
            print(f"结果保存: {args.output}")

            print(generate_report(df_existing, df_new))
        else:
            print("所有 URL 已探测，无需重复")
            print(generate_report(df_existing))
    else:
        print(generate_report(df_existing))
        print("\n使用 --input <csv> 探测新 URL，或 --export-import <csv> 导出导入文件")


if __name__ == '__main__':
    main()
