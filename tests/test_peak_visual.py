"""
交互式高峰切割可视化
====================
运行流程：
  1. 确认数据文件夹路径（回车使用默认值）
  2. 选择股票筛选模式：
     1 - 按序号范围选择
     2 - 按前N只选择
     3 - 直接输入6位代码
  3. 根据所选模式列出可用的股票，输入对应的股票代码进行可视化
  4. 显示该股票的高峰切割效果图

从项目根目录运行：python tests/test_peak_visual.py
"""
import sys
from pathlib import Path
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.dates as mdates

# 将项目根目录加入模块搜索路径
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from core.data.oriental_fetcher import OrientalFetcher
from core.features.image_peak_analyzer import ImagePeakAnalyzer

# ============================================================
#  默 认 配 置 区 （可在此修改常用值）
# ============================================================
# 默认数据文件夹（可改为你自己的路径，程序启动时会询问）
DEFAULT_DATA_DIR = r"D:\desk_file\Me\school\大一下\股票\stock_analysis\data\raw\2026_5_29__688__50__total"

# 分析器参数（与 image_peak_analyzer.py 配置区保持同步）
PROMINENCE = 0.1
CUT_MODE = 'peak_to_peak'   # 'peak_to_peak' 或 'center_window'
MAX_SEGMENT_LEN = 100
WINDOW_HALF_LEN = 20
DISCARD_FIRST_LAST = True

# 可视化参数
SHOW_SEGMENT_BOUNDARIES = True
SHOW_PEAKS = True
FIGURE_SIZE = (14, 6)

# 中文字体（已测试通过）
CHINESE_FONT = 'SimHei'
plt.rcParams['font.sans-serif'] = [CHINESE_FONT]
plt.rcParams['axes.unicode_minus'] = False

# ============================================================
#  辅 助 函 数
# ============================================================
def list_files_in_dir(data_dir: Path):
    """
    扫描数据目录下所有 .xls 文件，返回文件名列表（不含路径）。
    """
    files = list(data_dir.glob("*.xls"))
    if not files:
        print(f"错误：在 {data_dir} 下未找到任何 .xls 文件。")
        return []
    # 按文件名排序（如 1_688469, 2_688538...）
    files.sort(key=lambda f: f.name)
    return files

def extract_code_and_order(filename: str):
    """
    从文件名（如 '1_688469.xls'）中提取：序号(int)、股票代码(str)。
    如果格式不正确，返回 None。
    """
    import re
    stem = Path(filename).stem           # 去掉后缀
    # 匹配 "数字_6位数字" 格式
    match = re.match(r'(\d+)_(\d{6})', stem)
    if match:
        order = int(match.group(1))
        code = match.group(2)
        return order, code
    return None

def select_stock_interactively(data_dir: Path):
    """
    交互式选择一只股票：
      - 询问选择模式
      - 根据模式列出可选股票
      - 返回选中的股票代码(str)
    """
    files = list_files_in_dir(data_dir)
    if not files:
        return None

    # 解析所有文件的序号和代码
    stock_list = []   # [(order, code, filename), ...]
    for f in files:
        info = extract_code_and_order(f.name)
        if info:
            stock_list.append((info[0], info[1], f.name))
    if not stock_list:
        print("没有找到格式为 '序号_6位代码.xls' 的文件，请检查文件名。")
        return None

    # 显示当前目录下有多少只股票
    print(f"\n在 {data_dir} 中找到 {len(stock_list)} 个有效股票文件。")
    print("\n请选择股票筛选模式：")
    print("  1 - 按序号范围筛选（输入起始和结束序号）")
    print("  2 - 按前N只筛选（输入数量）")
    print("  3 - 直接输入6位股票代码")
    mode = input("请输入模式编号 (1/2/3): ").strip()

    if mode == '1':
        # 序号范围模式
        try:
            start = int(input("请输入起始序号: "))
            end = int(input("请输入结束序号: "))
            if start > end:
                start, end = end, start
            # 筛选符合范围的股票
            filtered = [(order, code, fname) for order, code, fname in stock_list if start <= order <= end]
            if not filtered:
                print(f"在序号 {start}~{end} 范围内没有找到股票。")
                return None
            print(f"\n序号范围 {start}-{end} 内的股票：")
            for order, code, fname in filtered:
                print(f"  序号{order}: {code}  ({fname})")
            # 让用户输入代码选择具体一只
            code_input = input("请输入要查看的6位股票代码: ").strip()
            # 验证代码是否在筛选列表中
            valid_codes = [c for _, c, _ in filtered]
            if code_input in valid_codes:
                return code_input
            else:
                print("输入的代码不在当前范围内。")
                return None
        except ValueError:
            print("输入的不是有效数字。")
            return None

    elif mode == '2':
        # 前N只模式
        try:
            n = int(input("请输入要显示前几只股票: "))
            if n <= 0:
                print("数量必须大于0。")
                return None
            n = min(n, len(stock_list))
            print(f"\n前 {n} 只股票：")
            for i in range(n):
                order, code, fname = stock_list[i]
                print(f"  序号{order}: {code}  ({fname})")
            code_input = input("请输入要查看的6位股票代码: ").strip()
            valid_codes = [stock_list[i][1] for i in range(n)]
            if code_input in valid_codes:
                return code_input
            else:
                print("输入的代码不在前N只中。")
                return None
        except ValueError:
            print("输入的不是有效数字。")
            return None

    elif mode == '3':
        # 直接输入代码
        code_input = input("请输入6位股票代码: ").strip()
        if len(code_input) == 6 and code_input.isdigit():
            # 检查是否存在
            if any(code_input == code for _, code, _ in stock_list):
                return code_input
            else:
                print("未找到该代码对应的文件。")
                return None
        else:
            print("代码格式错误，必须是6位数字。")
            return None

    else:
        print("无效的模式编号。")
        return None

# ============================================================
#  主 程 序
# ============================================================
def main():
    # 1. 确认数据目录
    print("=" * 50)
    print("交互式高峰切割可视化工具")
    print("=" * 50)
    data_dir_input = input(f"请输入数据文件夹路径 (直接回车使用默认): \n  默认: {DEFAULT_DATA_DIR}\n  >> ").strip()
    if data_dir_input == '':
        data_dir = Path(DEFAULT_DATA_DIR)
    else:
        data_dir = Path(data_dir_input)
    if not data_dir.exists():
        print(f"错误：文件夹 {data_dir} 不存在。")
        return

    # 2. 交互选择股票
    selected_code = select_stock_interactively(data_dir)
    if selected_code is None:
        print("未选择任何股票，程序退出。")
        return

    print(f"\n即将分析股票: {selected_code}")

    # 3. 加载数据
    # 注意：这里直接使用数据目录和代码，需要借助 fetcher 读取单个文件
    # 由于我们的 OrientalFetcher 需要扫描 raw 目录，这里传递 data_dir 的父目录作为 raw_dir？
    # 简单起见，直接使用 fetcher 并指定 raw_dir 为 data_dir 的父目录吗？但我们的文件在子文件夹中。
    # 更稳健的方式是：直接构造文件的完整路径，使用 fetcher.read_local_xls 读取。
    # 但为了保持调用方式一致，我们仍可以创建一个临时的 fetcher，让它能定位到这个文件。
    # 既然用户指定了 data_dir，我们可以将 raw_dir 设为 data_dir 的上级目录，但这样会扫描所有文件。
    # 为了准确加载选中的股票，使用 fetcher.load_stock 可能因为文件路径问题找不到。
    # 最好是直接通过文件路径读取，因为我们有 code 可以定位文件。
    # 改进：写一个辅助函数通过代码在 data_dir 中找到文件，然后调用 fetcher.read_local_xls
    fetcher = OrientalFetcher(raw_dir=str(data_dir.parent))  # 父目录作为 raw_dir
    # 但我们的文件在子文件夹 data_dir 里，fetcher 的 _find_files 使用递归搜索，所以可以找到
    try:
        df = fetcher.load_stock(selected_code)
    except FileNotFoundError:
        # 如果找不到，尝试直接构造路径读取
        # 列出所有文件找到匹配的
        files = list(data_dir.glob(f"*_{selected_code}.xls"))
        if not files:
            print(f"在 {data_dir} 中未找到代码为 {selected_code} 的文件。")
            return
        file_path = files[0]
        df = fetcher.read_local_xls(file_path)

    print(f"已加载股票 {selected_code}，共 {len(df)} 行数据")
    print(f"日期范围：{df['date'].min().date()} ～ {df['date'].max().date()}")

    # 4. 初始化分析器
    analyzer = ImagePeakAnalyzer(
        prominence=PROMINENCE,
        max_segment_len=MAX_SEGMENT_LEN,
        cut_mode=CUT_MODE,
        window_half_len=WINDOW_HALF_LEN,
        discard_first_last=DISCARD_FIRST_LAST
    )

    price = df['close']
    peaks = analyzer.find_peaks(price)
    print(f"识别到 {len(peaks)} 个高峰")

    if CUT_MODE == 'center_window':
        segments = analyzer.cut_segments_center_window(price, peaks)
    else:
        segments = analyzer.cut_segments_peak_to_peak(price, peaks)

    if DISCARD_FIRST_LAST and len(segments) >= 3:
        segments = segments[1:-1]
    print(f"切割出 {len(segments)} 个片段（已去除首尾不完整片段）")

    # 5. 绘图
    plt.figure(figsize=FIGURE_SIZE)
    plt.plot(df['date'], price, label='收盘价', color='black', linewidth=1.0)

    if SHOW_PEAKS and len(peaks) > 0:
        plt.scatter(df['date'].iloc[peaks], price.iloc[peaks],
                    color='red', s=40, zorder=5, label='高峰')

    if SHOW_SEGMENT_BOUNDARIES:
        for i, seg in enumerate(segments):
            start_date = df['date'].iloc[seg.index[0]]
            end_date = df['date'].iloc[seg.index[-1]]
            plt.axvline(x=start_date, color='gray', linestyle='--', alpha=0.4, linewidth=0.8)
            if i == len(segments) - 1:
                plt.axvline(x=end_date, color='gray', linestyle='--', alpha=0.4, linewidth=0.8)

    plt.gca().xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m'))
    plt.gca().xaxis.set_major_locator(mdates.MonthLocator(interval=1))
    plt.xticks(rotation=45)

    plt.title(f"股票 {selected_code} 高峰切割效果图 (模式: {CUT_MODE})")
    plt.xlabel("日期")
    plt.ylabel("价格")
    plt.legend()
    plt.grid(True, alpha=0.3)
    plt.tight_layout()
    plt.show()

if __name__ == "__main__":
    main()