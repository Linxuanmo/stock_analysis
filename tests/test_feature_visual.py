"""
特征向量可视化脚本
==================
功能：
  - 交互选择股票（与 test_peak_visual 相同的数据选择方式）
  - 显示该股票的片段特征分布（长度、涨跌幅、波动率）
  - 绘制所有片段的归一化价格形态重叠图，直观展示峰段形态的多样性

数据来源：优先从 data/processed/peak_features.csv 加载，如无则实时计算。
"""
import sys
from pathlib import Path
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt

# 项目根目录
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from core.data.oriental_fetcher import OrientalFetcher
from core.features.image_peak_analyzer import ImagePeakAnalyzer

# ============================================================
#  配  置  区
# ============================================================
# 不同周期的默认数据目录（与 test_peak_visual 保持一致）
PERIOD_DEFAULT_DIRS = {
    '1': {
        'label': '日线',
        'path': str(PROJECT_ROOT / "data" / "raw" / "daily" / "2026_5_29__688__50__total")
    },
    '2': {
        'label': '月线',
        'path': str(PROJECT_ROOT / "data" / "raw" / "monthly" / "2026_06_07__688__30__monthly")
    },
    '3': {
        'label': '自定义周期',
        'path': ''
    }
}

# 分析器参数（用于实时生成特征，若 CSV 存在则优先加载）
PEAK_PROMINENCE = 0.1
PEAK_CUT_MODE = 'peak_to_peak'
PEAK_MAX_SEGMENT_LEN = 100
PEAK_WINDOW_HALF_LEN = 20
PEAK_DISCARD_FIRST_LAST = True

# 输出目录（用于查找已保存的特征 CSV）
PROCESSED_DIR = PROJECT_ROOT / "data" / "processed"

# 可视化参数
FIGURE_SIZE = (14, 8)
CHINESE_FONT = 'SimHei'
plt.rcParams['font.sans-serif'] = [CHINESE_FONT]
plt.rcParams['axes.unicode_minus'] = False

# ============================================================
#  辅 助 函 数（复用 test_peak_visual 的交互逻辑）
# ============================================================
def list_files_in_dir(data_dir: Path):
    files = list(data_dir.glob("*.xls"))
    if not files:
        print(f"错误：在 {data_dir} 下未找到任何 .xls 文件。")
        return []
    files.sort(key=lambda f: f.name)
    return files

def extract_code_and_order(filename: str):
    import re
    stem = Path(filename).stem
    match = re.match(r'(\d+)_(\d{6})', stem)
    if match:
        return int(match.group(1)), match.group(2)
    return None

def select_stock_interactively(data_dir: Path):
    files = list_files_in_dir(data_dir)
    if not files:
        return None
    stock_list = []
    for f in files:
        info = extract_code_and_order(f.name)
        if info:
            stock_list.append((info[0], info[1], f.name))
    if not stock_list:
        print("没有找到格式为 '序号_6位代码.xls' 的文件。")
        return None
    print(f"\n在 {data_dir} 中找到 {len(stock_list)} 个有效股票文件。")
    print("\n请选择股票筛选模式：")
    print("  1 - 按序号范围筛选")
    print("  2 - 按前N只筛选")
    print("  3 - 直接输入6位股票代码")
    mode = input("请输入模式编号 (1/2/3): ").strip()
    if mode == '1':
        try:
            start = int(input("起始序号: "))
            end = int(input("结束序号: "))
            if start > end:
                start, end = end, start
            filtered = [(o, c, f) for o, c, f in stock_list if start <= o <= end]
            if not filtered:
                print("该范围内没有股票。")
                return None
            print(f"\n序号 {start}-{end} 内的股票：")
            for o, c, f in filtered:
                print(f"  序号{o}: {c}  ({f})")
            code_input = input("请输入6位代码: ").strip()
            if code_input in [c for _, c, _ in filtered]:
                return code_input
            else:
                print("代码不在范围内。")
                return None
        except ValueError:
            print("无效数字。")
            return None
    elif mode == '2':
        try:
            n = int(input("显示前几只: "))
            if n <= 0:
                print("数量必须大于0。")
                return None
            n = min(n, len(stock_list))
            print(f"\n前 {n} 只股票：")
            for i in range(n):
                o, c, f = stock_list[i]
                print(f"  序号{o}: {c}  ({f})")
            code_input = input("请输入6位代码: ").strip()
            if code_input in [stock_list[i][1] for i in range(n)]:
                return code_input
            else:
                print("代码不在前N只中。")
                return None
        except ValueError:
            print("无效数字。")
            return None
    elif mode == '3':
        code_input = input("请输入6位代码: ").strip()
        if len(code_input) == 6 and code_input.isdigit():
            if any(code_input == c for _, c, _ in stock_list):
                return code_input
            else:
                print("未找到该代码。")
                return None
        else:
            print("格式错误，需要6位数字。")
            return None
    else:
        print("无效模式。")
        return None

def select_period():
    print("\n请选择数据周期：")
    for key, info in PERIOD_DEFAULT_DIRS.items():
        print(f"  {key} - {info['label']} (默认路径: {info['path']})")
    choice = input("请输入选项 (1/2/3): ").strip()
    if choice in PERIOD_DEFAULT_DIRS:
        info = PERIOD_DEFAULT_DIRS[choice]
        default_path = info['path']
        if choice == '3' or not default_path:
            path = input("请输入数据文件夹完整路径: ").strip()
        else:
            path = input(f"请输入数据文件夹路径 (直接回车使用默认): \n  {default_path}\n  >> ").strip()
            if path == '':
                path = default_path
        return path
    else:
        print("无效选项，使用默认日线路径。")
        return PERIOD_DEFAULT_DIRS['1']['path']

def load_or_compute_features(code: str, fetcher: OrientalFetcher, analyzer: ImagePeakAnalyzer):
    """
    尝试从 processed 目录加载该股票的片段特征，若不存在则实时计算。
    返回 DataFrame（片段特征表）
    """
    csv_path = PROCESSED_DIR / "peak_features.csv"
    if csv_path.exists():
        all_peak = pd.read_csv(csv_path)
        if 'code' in all_peak.columns:
            peak_df = all_peak[all_peak['code'] == code]
            if not peak_df.empty:
                print(f"从缓存加载 {code} 的特征数据 ({len(peak_df)} 个片段)")
                return peak_df
    # 未找到，实时计算
    try:
        df = fetcher.load_stock(code)
    except FileNotFoundError:
        print(f"找不到股票 {code} 的原始数据。")
        return pd.DataFrame()
    peak_df = analyzer.analyze(df)
    peak_df['code'] = code
    print(f"实时计算 {code} 的特征，得到 {len(peak_df)} 个片段")
    return peak_df

# ============================================================
#  主 程 序
# ============================================================
def main():
    print("=" * 50)
    print("特征向量可视化工具")
    print("=" * 50)

    # 1. 选择数据目录（与 test_peak_visual 完全一致）
    data_dir_path = select_period()
    data_dir = Path(data_dir_path)
    if not data_dir.exists():
        print(f"错误：文件夹 {data_dir} 不存在。")
        return

    # 2. 选择股票
    selected_code = select_stock_interactively(data_dir)
    if selected_code is None:
        print("未选择任何股票，程序退出。")
        return

    # 3. 初始化数据获取器和分析器（用于可能需要的实时计算）
    fetcher = OrientalFetcher(raw_dir=str(data_dir))
    analyzer = ImagePeakAnalyzer(
        prominence=PEAK_PROMINENCE,
        max_segment_len=PEAK_MAX_SEGMENT_LEN,
        cut_mode=PEAK_CUT_MODE,
        window_half_len=PEAK_WINDOW_HALF_LEN,
        discard_first_last=PEAK_DISCARD_FIRST_LAST
    )

    # 4. 获取该股票的片段特征 DataFrame
    peak_df = load_or_compute_features(selected_code, fetcher, analyzer)
    if peak_df.empty:
        print("无法获取特征数据，请检查数据或重新运行 test_features.py。")
        return

    # 5. 绘制图表
    fig, axes = plt.subplots(2, 2, figsize=FIGURE_SIZE)
    fig.suptitle(f"股票 {selected_code} 片段特征概览", fontsize=16)

    # 子图1：片段长度分布（柱状图）
    axes[0, 0].bar(peak_df['segment_id'], peak_df['length'], color='steelblue', alpha=0.7)
    axes[0, 0].set_title('片段长度（交易日）')
    axes[0, 0].set_xlabel('片段编号')
    axes[0, 0].set_ylabel('天数')
    axes[0, 0].grid(axis='y', alpha=0.3)

    # 子图2：涨跌幅与波动率散点图
    scatter = axes[0, 1].scatter(peak_df['price_change'], peak_df['volatility'],
                                 c=peak_df['length'], cmap='viridis', alpha=0.7)
    axes[0, 1].set_title('涨跌幅 vs 波动率 (颜色=长度)')
    axes[0, 1].set_xlabel('价格变化率')
    axes[0, 1].set_ylabel('波动率')
    plt.colorbar(scatter, ax=axes[0, 1], label='片段长度')
    axes[0, 1].grid(alpha=0.3)
    # 添加 y=0 和 x=0 参考线
    axes[0, 1].axhline(0, color='gray', linestyle='--', linewidth=0.5)
    axes[0, 1].axvline(0, color='gray', linestyle='--', linewidth=0.5)

    # 子图3：归一化价格形态重叠图（所有片段）
    ax_morph = axes[1, 0]
    for _, row in peak_df.iterrows():
        try:
            # normalized_series 存储为类似 "[0.12 0.25 ...]" 的字符串
            vec_str = row['normalized_series']
            if isinstance(vec_str, str):
                # 将字符串转换为 numpy 数组
                vec = np.fromstring(vec_str.strip('[]'), sep=' ')
            else:
                vec = np.array(vec_str)
            x = np.linspace(0, 1, len(vec))   # 将时间归一化到 [0,1]
            ax_morph.plot(x, vec, alpha=0.4, linewidth=0.5)
        except Exception as e:
            continue
    ax_morph.set_title('归一化价格形态重叠')
    ax_morph.set_xlabel('归一化时间')
    ax_morph.set_ylabel('归一化价格')
    ax_morph.grid(alpha=0.3)

    # 子图4：平均形态（所有片段的均值曲线）
    ax_mean = axes[1, 1]
    all_vecs = []
    max_len = 0
    for _, row in peak_df.iterrows():
        try:
            vec_str = row['normalized_series']
            if isinstance(vec_str, str):
                vec = np.fromstring(vec_str.strip('[]'), sep=' ')
            else:
                vec = np.array(vec_str)
            all_vecs.append(vec)
            max_len = max(max_len, len(vec))
        except:
            continue
    if all_vecs:
        # 将所有向量插值到相同长度
        from scipy.interpolate import interp1d
        interpolated = []
        for v in all_vecs:
            x_old = np.linspace(0, 1, len(v))
            f = interp1d(x_old, v, kind='linear')
            x_new = np.linspace(0, 1, max_len)
            interpolated.append(f(x_new))
        mean_vec = np.mean(interpolated, axis=0)
        std_vec = np.std(interpolated, axis=0)
        x_new = np.linspace(0, 1, max_len)
        ax_mean.plot(x_new, mean_vec, color='red', linewidth=2, label='平均形态')
        ax_mean.fill_between(x_new, mean_vec - std_vec, mean_vec + std_vec,
                             color='red', alpha=0.2, label='±1 标准差')
        ax_mean.legend()
    ax_mean.set_title('平均归一化形态')
    ax_mean.set_xlabel('归一化时间')
    ax_mean.set_ylabel('归一化价格')
    ax_mean.grid(alpha=0.3)

    plt.tight_layout()
    plt.show()

if __name__ == "__main__":
    main()