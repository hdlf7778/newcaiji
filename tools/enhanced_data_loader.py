"""
加载采集源增强数据_探测版.xlsx — 9,615 条已探测结果
"""
import os
import pandas as pd

DEFAULT_PATH = os.path.join(os.path.dirname(__file__), '..', '..', '采集源增强数据_探测版.xlsx')


def load_enhanced_data(path: str = None) -> pd.DataFrame:
    """加载增强数据，返回 DataFrame"""
    path = path or DEFAULT_PATH
    if not os.path.exists(path):
        # 尝试 Desktop 路径
        path = os.path.expanduser('~/Desktop/xincaiji/采集源增强数据_探测版.xlsx')
    if not os.path.exists(path):
        raise FileNotFoundError(f"采集源增强数据文件未找到: {path}")

    df = pd.read_excel(path, sheet_name='最终增强采集源')
    print(f"加载增强数据: {len(df)} 条")
    return df


def get_template_stats(df: pd.DataFrame) -> dict:
    """统计模板分布"""
    return df['最终模板'].value_counts().to_dict()


def get_platform_stats(df: pd.DataFrame) -> dict:
    """统计已识别平台"""
    platforms = df[df['所属平台'].notna() & (df['所属平台'] != '')]
    return platforms['所属平台'].value_counts().to_dict()


def get_probed_domains(df: pd.DataFrame) -> set:
    """获取已探测的域名集合"""
    return set(df['域名'].dropna().str.lower())


if __name__ == '__main__':
    df = load_enhanced_data()
    print(f"\n模板分布:")
    for tpl, cnt in get_template_stats(df).items():
        print(f"  {tpl}: {cnt} ({cnt/len(df)*100:.1f}%)")
    print(f"\n已识别平台:")
    for plat, cnt in get_platform_stats(df).items():
        print(f"  {plat}: {cnt}")
    print(f"\n已探测域名数: {len(get_probed_domains(df))}")
