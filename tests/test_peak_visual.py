"""
交互式高峰切割可视化（支持日线/月线等多周期）
=============================================
运行流程：
  1. 选择数据周期（日线/月线/自定义）
  2. 根据周期自动给出默认数据文件夹，可回车确认或修改
  3. 选择股票筛选模式（序号范围 / 前N只 / 六位代码）
  4. 显示所选股票的高峰切割效果图

从项目根目录运行：python tests/test_peak_visual.py
"""
import sys                              # 系统相关，用于修改 Python 模块搜索路径
from pathlib import Path                # 面向对象的文件路径处理
import pandas as pd                     # 数据处理库，DataFrame
import matplotlib.pyplot as plt         # 绘图库
import matplotlib.dates as mdates       # 处理日期格式的刻度定位器和格式化器

# 将项目根目录加入 sys.path，确保无论从哪里运行都能导入 core 模块
PROJECT_ROOT = Path(__file__).resolve().parent.parent   # 获取项目根目录的绝对路径
sys.path.insert(0, str(PROJECT_ROOT))                  # 将根目录插入到模块搜索路径的最前面

from core.data.oriental_fetcher import OrientalFetcher         # 数据读取器
from core.features.image_peak_analyzer import ImagePeakAnalyzer # 高峰切割分析器

# ============================================================
#  默 认 配 置 区 （可根据需要修改）
# ============================================================
# ---- 不同周期的默认数据文件夹 ----
# 字典结构，方便根据用户输入的数字键直接获取对应的标签和路径
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

# ---- 分析器参数（与 image_peak_analyzer.py 保持同步） ----
PROMINENCE = 0.1            # 高峰显著程度，值越小找到的峰越多
CUT_MODE = 'peak_to_peak'   # 切割模式：'peak_to_peak'（峰间切割）或 'center_window'（中心窗口）
MAX_SEGMENT_LEN = 100       # 峰间切割模式下片段的最大长度（交易日数）
WINDOW_HALF_LEN = 20        # 中心窗口模式下的窗口半长
DISCARD_FIRST_LAST = True   # 是否丢弃首尾不完整片段

# ---- 可视化参数 ----
SHOW_SEGMENT_BOUNDARIES = True   # 是否在图上绘制片段的边界虚线
SHOW_PEAKS = True                # 是否标出高峰点
FIGURE_SIZE = (14, 6)            # 图表宽高（英寸）

# ---- 中文字体设置 ----
CHINESE_FONT = 'SimHei'                   # 使用黑体作为默认字体
plt.rcParams['font.sans-serif'] = [CHINESE_FONT]  # 设置 matplotlib 全局字体
plt.rcParams['axes.unicode_minus'] = False        # 解决负号 '-' 显示为方块的问题

# ============================================================
#  辅 助 函 数
# ============================================================
def list_files_in_dir(data_dir: Path):
    """
    扫描指定目录下所有 .xls 文件，返回按文件名排序的 Path 对象列表。
    如果目录下没有 .xls 文件，打印错误并返回空列表。
    """
    files = list(data_dir.glob("*.xls"))          # 查找所有 .xls 文件
    if not files:                                 # 如果没有找到文件
        print(f"错误：在 {data_dir} 下未找到任何 .xls 文件。")
        return []
    files.sort(key=lambda f: f.name)              # 按文件名排序（保证 1_, 2_, ... 顺序）
    return files

def extract_code_and_order(filename: str):
    """
    从文件名（如 '1_688469.xls'）中提取序号和6位股票代码。
    返回 (序号, 股票代码) 元组；如果格式不匹配，返回 None。
    """
    import re                                     # 正则表达式模块（局部导入不影响性能）
    stem = Path(filename).stem                    # 去掉文件后缀，得到 '1_688469'
    match = re.match(r'(\d+)_(\d{6})', stem)      # 匹配“数字_6位数字”格式
    if match:
        order = int(match.group(1))               # 提取序号（第一组数字）
        code = match.group(2)                     # 提取股票代码（第二组6位数字）
        return (order, code)
    return None

def select_stock_interactively(data_dir: Path):
    """
    在给定的数据目录中，通过交互方式让用户选择一只股票。
    提供三种筛选方式：按序号范围、按前N只、直接输入代码。
    返回选中的股票代码（字符串）；若操作取消则返回 None。
    """
    # 1. 获取该目录下所有有效文件的列表
    files = list_files_in_dir(data_dir)
    if not files:
        return None

    # 2. 解析每个文件的序号和代码，构建 stock_list
    stock_list = []   # 元素为 (序号, 代码, 文件名)
    for f in files:
        info = extract_code_and_order(f.name)     # 提取信息
        if info:
            stock_list.append((info[0], info[1], f.name))
    if not stock_list:                            # 如果没有格式正确的文件
        print("没有找到格式为 '序号_6位代码.xls' 的文件。")
        return None

    # 3. 显示文件数量并让用户选择筛选模式
    print(f"\n在 {data_dir} 中找到 {len(stock_list)} 个有效股票文件。")
    print("\n请选择股票筛选模式：")
    print("  1 - 按序号范围筛选")
    print("  2 - 按前N只筛选")
    print("  3 - 直接输入6位股票代码")
    mode = input("请输入模式编号 (1/2/3): ").strip()

    # 4. 根据模式处理
    if mode == '1':                               # 模式1：序号范围
        try:
            start = int(input("起始序号: "))
            end = int(input("结束序号: "))
            if start > end:                       # 确保起始不大于结束
                start, end = end, start
            # 筛选出序号在 [start, end] 范围内的股票
            filtered = [(o, c, f) for o, c, f in stock_list if start <= o <= end]
            if not filtered:
                print("该范围内没有股票。")
                return None
            # 列出范围内的股票
            print(f"\n序号 {start}-{end} 内的股票：")
            for o, c, f in filtered:
                print(f"  序号{o}: {c}  ({f})")
            code_input = input("请输入6位代码: ").strip()
            # 检查输入的代码是否在范围内
            if code_input in [c for _, c, _ in filtered]:
                return code_input
            else:
                print("代码不在范围内。")
                return None
        except ValueError:
            print("无效数字。")
            return None

    elif mode == '2':                             # 模式2：前N只
        try:
            n = int(input("显示前几只: "))
            if n <= 0:
                print("数量必须大于0。")
                return None
            n = min(n, len(stock_list))           # 防止超过总数
            print(f"\n前 {n} 只股票：")
            for i in range(n):
                o, c, f = stock_list[i]
                print(f"  序号{o}: {c}  ({f})")
            code_input = input("请输入6位代码: ").strip()
            # 检查代码是否在前N只中
            if code_input in [stock_list[i][1] for i in range(n)]:
                return code_input
            else:
                print("代码不在前N只中。")
                return None
        except ValueError:
            print("无效数字。")
            return None

    elif mode == '3':                             # 模式3：直接输入代码
        code_input = input("请输入6位代码: ").strip()
        if len(code_input) == 6 and code_input.isdigit():   # 格式校验
            # 检查代码是否存在于目录中
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
    """
    让用户选择数据周期（日线/月线/自定义），返回对应的数据文件夹路径字符串。
    """
    print("\n请选择数据周期：")
    # 展示所有周期选项
    for key, info in PERIOD_DEFAULT_DIRS.items():
        print(f"  {key} - {info['label']} (默认路径: {info['path']})")
    choice = input("请输入选项 (1/2/3): ").strip()

    if choice in PERIOD_DEFAULT_DIRS:             # 如果输入的是有效选项
        info = PERIOD_DEFAULT_DIRS[choice]
        default_path = info['path']
        # 自定义周期或默认路径为空时，强制用户输入完整路径
        if choice == '3' or not default_path:
            path = input("请输入数据文件夹完整路径: ").strip()
        else:
            path = input(f"请输入数据文件夹路径 (直接回车使用默认): \n  {default_path}\n  >> ").strip()
            if path == '':                        # 直接回车则使用默认值
                path = default_path
        return path
    else:
        print("无效选项，使用默认日线路径。")
        return PERIOD_DEFAULT_DIRS['1']['path']   # 兜底：返回日线默认路径

# ============================================================
#  主 程 序
# ============================================================
def main():
    """
    主函数：串联周期选择、股票选择、数据分析与可视化全流程。
    """
    print("=" * 50)
    print("交互式高峰切割可视化工具（支持多周期）")
    print("=" * 50)

    # 1. 选择周期，获取数据文件夹路径
    data_dir_path = select_period()               # 调用周期选择函数，得到路径字符串
    data_dir = Path(data_dir_path)                # 转为 Path 对象
    if not data_dir.exists():                     # 检查路径是否存在
        print(f"错误：文件夹 {data_dir} 不存在。")
        return

    # 2. 在选定的数据目录中交互选择一只股票
    selected_code = select_stock_interactively(data_dir)
    if selected_code is None:                     # 如果用户没有正常选择（返回 None）
        print("未选择任何股票，程序退出。")
        return

    print(f"\n即将分析股票: {selected_code}，数据来自: {data_dir}")

    # 3. 使用 OrientalFetcher 加载该股票的数据
    #    将 raw_dir 设置为用户选定的数据目录，以便 fetcher 能在其中找到文件
    fetcher = OrientalFetcher(raw_dir=str(data_dir))
    try:
        df = fetcher.load_stock(selected_code)    # 加载清洗后的数据
    except FileNotFoundError:
        print(f"找不到代码 {selected_code} 的文件，请确认。")
        return

    # 打印加载信息
    print(f"已加载股票 {selected_code}，共 {len(df)} 行数据")
    print(f"日期范围：{df['date'].min().date()} ～ {df['date'].max().date()}")

    # 4. 初始化高峰切割分析器（参数来自配置区）
    analyzer = ImagePeakAnalyzer(
        prominence=PROMINENCE,
        max_segment_len=MAX_SEGMENT_LEN,
        cut_mode=CUT_MODE,
        window_half_len=WINDOW_HALF_LEN,
        discard_first_last=DISCARD_FIRST_LAST
    )

    # 5. 获取收盘价序列，寻找高峰
    price = df['close']                           # 收盘价序列
    peaks = analyzer.find_peaks(price)            # 返回高峰索引数组
    print(f"识别到 {len(peaks)} 个高峰")

    # 6. 根据切割模式进行片段切割
    if CUT_MODE == 'center_window':
        segments = analyzer.cut_segments_center_window(price, peaks)
    else:
        segments = analyzer.cut_segments_peak_to_peak(price, peaks)

    # 如果设置丢弃首尾，从片段列表中移除第一个和最后一个
    if DISCARD_FIRST_LAST and len(segments) >= 3:
        segments = segments[1:-1]
    print(f"切割出 {len(segments)} 个片段（已去除首尾）")

    # 7. 绘制可视化图表
    plt.figure(figsize=FIGURE_SIZE)               # 设置画布大小
    plt.plot(df['date'], price, label='收盘价', color='black', linewidth=1.0)  # 收盘价曲线

    # 标出高峰点
    if SHOW_PEAKS and len(peaks) > 0:
        plt.scatter(df['date'].iloc[peaks], price.iloc[peaks],
                    color='red', s=40, zorder=5, label='高峰')

    # 标出片段边界（虚线）
    if SHOW_SEGMENT_BOUNDARIES:
        for i, seg in enumerate(segments):
            start_date = df['date'].iloc[seg.index[0]]
            end_date = df['date'].iloc[seg.index[-1]]
            plt.axvline(x=start_date, color='gray', linestyle='--', alpha=0.4, linewidth=0.8)
            if i == len(segments) - 1:            # 最后一个片段也画出结束边界
                plt.axvline(x=end_date, color='gray', linestyle='--', alpha=0.4, linewidth=0.8)

    # 设置日期轴格式
    plt.gca().xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m'))    # 显示为“年-月”
    plt.gca().xaxis.set_major_locator(mdates.MonthLocator(interval=1))    # 每月一个主刻度
    plt.xticks(rotation=45)                      # 旋转刻度标签，避免重叠

    plt.title(f"股票 {selected_code} 高峰切割效果图 (模式: {CUT_MODE})")  # 图表标题
    plt.xlabel("日期")
    plt.ylabel("价格")
    plt.legend()                                   # 显示图例
    plt.grid(True, alpha=0.3)                      # 显示半透明网格线
    plt.tight_layout()                             # 自动调整子图参数，使之填满整个图像区域
    plt.show()                                     # 显示图表窗口

# 程序的入口：当直接运行该脚本时，执行 main()
if __name__ == "__main__":
    main()