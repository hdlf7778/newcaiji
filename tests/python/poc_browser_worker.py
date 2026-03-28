"""
T02: Browser Worker 并发模型 PoC
验证多进程 Playwright (ProcessPoolExecutor, 5进程) 的稳定性

验证标准: 无崩溃, 内存在预期范围 (每进程 300-400MB)
"""
import time
import os
import json
from concurrent.futures import ProcessPoolExecutor, as_completed
from multiprocessing import Process, Queue

# 5 个需要浏览器渲染的测试网站（覆盖模板 B/F/G 类型）
TEST_URLS = [
    ("https://www.pku.edu.cn/", "高校门户-北大"),
    ("https://www.fudan.edu.cn/", "高校门户-复旦"),
    ("https://www.sjtu.edu.cn/", "高校门户-上交"),
    ("https://www.ustc.edu.cn/", "高校门户-中科大"),
    ("https://www.tsinghua.edu.cn/", "高校门户-清华"),
]

PROCESS_COUNT = 5

def get_memory_mb():
    try:
        import resource
        return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024 / 1024
    except:
        return 0


def browser_worker(url, name, worker_id):
    """单个浏览器进程：启动 Playwright → 打开页面 → 提取内容 → 关闭"""
    result = {
        "worker_id": worker_id,
        "url": url,
        "name": name,
        "pid": os.getpid(),
        "status": "unknown",
        "title": "",
        "links_count": 0,
        "content_length": 0,
        "elapsed_ms": 0,
        "memory_mb": 0,
        "error": None,
    }

    start = time.time()
    try:
        from playwright.sync_api import sync_playwright

        with sync_playwright() as p:
            browser = p.chromium.launch(
                headless=True,
                args=["--no-sandbox", "--disable-gpu", "--disable-dev-shm-usage"]
            )
            context = browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                viewport={"width": 1280, "height": 720},
            )
            # 屏蔽图片/字体加速
            context.route("**/*.{png,jpg,jpeg,gif,svg,ico,woff,woff2,ttf}", lambda route: route.abort())

            page = context.new_page()
            page.goto(url, wait_until="domcontentloaded", timeout=30000)
            page.wait_for_timeout(2000)  # 等待 JS 渲染

            # 提取基本信息
            result["title"] = page.title() or ""
            result["content_length"] = len(page.content())
            result["links_count"] = page.locator("a[href]").count()

            page.close()
            context.close()
            browser.close()

        result["status"] = "success"
        result["elapsed_ms"] = int((time.time() - start) * 1000)
        result["memory_mb"] = round(get_memory_mb(), 1)

    except Exception as e:
        result["status"] = "failed"
        result["error"] = f"{type(e).__name__}: {str(e)[:100]}"
        result["elapsed_ms"] = int((time.time() - start) * 1000)
        result["memory_mb"] = round(get_memory_mb(), 1)

    return result


def main():
    print("=" * 60)
    print("T02 PoC: Browser Worker 多进程并发模型验证")
    print(f"  测试URL数: {len(TEST_URLS)}")
    print(f"  进程数: {PROCESS_COUNT}")
    print(f"  模型: ProcessPoolExecutor + Playwright sync API")
    print("=" * 60)

    # 检查 Playwright 是否安装
    try:
        from playwright.sync_api import sync_playwright
        print("  ✅ Playwright 已安装")
    except ImportError:
        print("  ❌ Playwright 未安装，请运行: pip install playwright && playwright install chromium")
        return False

    mem_before = get_memory_mb()
    overall_start = time.time()
    results = []

    # 多进程并发执行
    print(f"\n开始 {PROCESS_COUNT} 进程并发渲染...")
    with ProcessPoolExecutor(max_workers=PROCESS_COUNT) as executor:
        futures = {}
        for i, (url, name) in enumerate(TEST_URLS):
            future = executor.submit(browser_worker, url, name, f"browser-worker-{i:02d}")
            futures[future] = (url, name)

        for future in as_completed(futures):
            url, name = futures[future]
            try:
                result = future.result(timeout=60)
                results.append(result)
                status = "✅" if result["status"] == "success" else "❌"
                print(f"  {status} [{result['worker_id']}] PID={result['pid']} {result['name']}: "
                      f"{result['elapsed_ms']}ms, {result['links_count']}links, "
                      f"{result['content_length']}bytes, {result['memory_mb']}MB")
            except Exception as e:
                results.append({"url": url, "name": name, "status": "crashed", "error": str(e)[:100]})
                print(f"  ❌ {name}: 进程异常 - {e}")

    overall_elapsed = time.time() - overall_start
    mem_after = get_memory_mb()

    # 汇总
    success = sum(1 for r in results if r["status"] == "success")
    failed = sum(1 for r in results if r["status"] != "success")
    total = len(results)
    success_rate = success / total * 100 if total else 0
    avg_elapsed = sum(r.get("elapsed_ms", 0) for r in results) / total if total else 0
    max_memory = max((r.get("memory_mb", 0) for r in results), default=0)
    avg_memory = sum(r.get("memory_mb", 0) for r in results) / total if total else 0
    total_links = sum(r.get("links_count", 0) for r in results)

    print(f"\n{'=' * 60}")
    print("汇总报告:")
    print(f"{'=' * 60}")
    print(f"  总页面数:     {total}")
    print(f"  成功渲染:     {success}")
    print(f"  失败/崩溃:    {failed}")
    print(f"  成功率:       {success_rate:.1f}%")
    print(f"  总耗时:       {overall_elapsed:.2f}s (并行)")
    print(f"  平均渲染:     {avg_elapsed:.0f}ms/页")
    print(f"  提取链接总数: {total_links}")
    print(f"  主进程内存:   {mem_after:.1f}MB")
    print(f"  子进程最大:   {max_memory:.1f}MB")
    print(f"  子进程平均:   {avg_memory:.1f}MB")

    # 错误详情
    errors = [r for r in results if r["status"] != "success"]
    if errors:
        print(f"\n  错误详情:")
        for r in errors:
            print(f"    {r.get('name', r.get('url','?'))}: {r.get('error', 'unknown')}")

    # 验证标准
    print(f"\n{'=' * 60}")
    print("验证标准检查:")
    print(f"{'=' * 60}")

    checks = []

    # 1. 无崩溃
    crashed = sum(1 for r in results if r["status"] == "crashed")
    check1 = crashed == 0
    checks.append(check1)
    print(f"  {'✅' if check1 else '❌'} 无进程崩溃: {crashed} crashed {'PASS' if check1 else 'FAIL'}")

    # 2. 成功率 > 80%（浏览器渲染允许略低于 HTTP）
    check2 = success_rate > 80
    checks.append(check2)
    print(f"  {'✅' if check2 else '❌'} 成功率 > 80%: {success_rate:.1f}% {'PASS' if check2 else 'FAIL'}")

    # 3. 并发有效
    serial_estimate = sum(r.get("elapsed_ms", 0) for r in results)
    speedup = serial_estimate / (overall_elapsed * 1000) if overall_elapsed > 0 else 0
    check3 = speedup > 2
    checks.append(check3)
    print(f"  {'✅' if check3 else '❌'} 并发有效（加速比>2x）: {speedup:.1f}x {'PASS' if check3 else 'FAIL'}")

    # 4. 子进程内存在预期范围（技术方案预期 300-400MB/进程）
    check4 = max_memory < 600  # macOS 上 Chromium 可能偏高
    checks.append(check4)
    print(f"  {'✅' if check4 else '⚠️'} 子进程内存 < 600MB: max={max_memory:.1f}MB {'PASS' if check4 else 'WARNING'}")

    # 5. 性能估算
    per_page_ms = avg_elapsed
    browser_sites = 40000 * 0.24  # F=23.9%, 约 9600 站需 Browser
    estimated_mins = browser_sites * per_page_ms / PROCESS_COUNT / 1000 / 60
    print(f"\n  性能推算 (模板 F/B/G, 约 {browser_sites:.0f} 站):")
    print(f"    单页平均渲染: {per_page_ms:.0f}ms")
    print(f"    {PROCESS_COUNT} 进程预估: {estimated_mins:.0f} 分钟")
    print(f"    2 副本×{PROCESS_COUNT} 进程={PROCESS_COUNT*2} 并发预估: {estimated_mins/2:.0f} 分钟")
    within_2h = estimated_mins / 2 < 120
    print(f"    {'✅' if within_2h else '⚠️'} 2小时窗口内完成: {'YES' if within_2h else 'NEEDS OPTIMIZATION'}")

    # 内存总量估算
    total_mem = PROCESS_COUNT * avg_memory / 1024  # GB
    print(f"\n  内存估算:")
    print(f"    2 副本×{PROCESS_COUNT} 进程 ≈ {2 * PROCESS_COUNT * avg_memory / 1024:.1f}GB")
    print(f"    技术方案预估: ~3GB (2副本×1.5GB)")

    all_pass = all(checks)
    print(f"\n{'=' * 60}")
    if all_pass:
        print("✅ Browser Worker PoC 全部验证通过")
    else:
        print("⚠️ Browser Worker PoC 部分验证未通过，请检查上述结果")
    print(f"{'=' * 60}")
    return all_pass


if __name__ == "__main__":
    main()
