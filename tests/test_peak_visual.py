"""
高峰切割可视化测试脚本
用于验证 ImagePeakAnalyzer 的切割效果：
  - 在K线图上标记出识别到的高峰
  - 用虚线标出每个切割片段的边界
  - 支持峰间切割和中心窗口两种模式

从项目根目录运行：python tests/test_peak_visual.py
"""
import sys
from pathlib import Path
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.dates as mdates

# 将项目根目录加入 sys.path，确保可以导入 core 模块
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from core.data.oriental_fetcher import OrientalFetcher
from core.features.image_peak_analyzer import ImagePeakAnalyzer

# ============================================================
#  配  置  区 （可根据需要修改）
# ============================================================

# 要观察的股票代码（6位数字，如 '688469'）
STOCK_CODE = '688469'

# 数据目录（默认为项目根目录下的 data/raw）
DATA_DIR = PROJECT_ROOT / "data" / "raw"

# 分析器参数（与 image_peak_analyzer.py 中的配置区同步调整）
PROMINENCE = 0.1            # 高峰显著程度
CUT_MODE = 'peak_to_peak'   # 切割模式：'peak_to_peak' 或 'center_window'
MAX_SEGMENT_LEN = 100       # 峰间切割下的最大片段长度
WINDOW_HALF_LEN = 20        # 中心窗口模式下的窗口半长
DISCARD_FIRST_LAST = True   # 是否丢弃首尾不完整片段

# 图表显示设置
SHOW_SEGMENT_BOUNDARIES = True   # 是否显示片段边界虚线
SHOW_PEAKS = True                # 是否显示高峰标记点
FIGURE_SIZE = (14, 6)            # 图表尺寸（宽, 高）

# 中文字体设置（根据你的系统，以下字体均可用）
# 已测试可用的字体：'SimHei', 'Microsoft YaHei', 'KaiTi', 'FangSong',
#                  'Microsoft JhengHei', 'SimSun', 'HYSWLongFangSong'
CHINESE_FONT = 'SimHei'          # 当前使用黑体，可自行更换
plt.rcParams['font.sans-serif'] = [CHINESE_FONT]    # 设置默认字体
plt.rcParams['axes.unicode_minus'] = False          # 解决负号显示为方块

# ============================================================
#  主 程 序
# ============================================================
def main():
    # 1. 加载数据
    fetcher = OrientalFetcher(raw_dir=str(DATA_DIR))
    df = fetcher.load_stock(STOCK_CODE)
    print(f"已加载股票 {STOCK_CODE}，共 {len(df)} 行数据")
    print(f"日期范围：{df['date'].min().date()} ～ {df['date'].max().date()}")

    # 2. 初始化分析器
    analyzer = ImagePeakAnalyzer(
        prominence=PROMINENCE,
        max_segment_len=MAX_SEGMENT_LEN,
        cut_mode=CUT_MODE,
        window_half_len=WINDOW_HALF_LEN,
        discard_first_last=DISCARD_FIRST_LAST
    )

    # 3. 获取价格序列和高峰索引
    price = df['close']
    peaks = analyzer.find_peaks(price)
    print(f"识别到 {len(peaks)} 个高峰")

    # 4. 根据模式获取切割片段
    if CUT_MODE == 'center_window':
        segments = analyzer.cut_segments_center_window(price, peaks)
    else:
        segments = analyzer.cut_segments_peak_to_peak(price, peaks)

    # 若开启首尾舍弃，从列表中移除（仅用于显示边界，实际分析时由 analyzer.analyze() 处理）
    if DISCARD_FIRST_LAST and len(segments) >= 3:
        segments = segments[1:-1]

    print(f"切割出 {len(segments)} 个片段（已根据配置去除首尾）")

    # 5. 绘图
    plt.figure(figsize=FIGURE_SIZE)

    # 绘制收盘价曲线
    plt.plot(df['date'], price, label='收盘价', color='black', linewidth=1.0)

    # 标记高峰位置
    if SHOW_PEAKS and len(peaks) > 0:
        plt.scatter(df['date'].iloc[peaks], price.iloc[peaks],
                    color='red', s=40, zorder=5, label='高峰')

    # 绘制片段边界（虚线）
    if SHOW_SEGMENT_BOUNDARIES:
        for i, seg in enumerate(segments):
            start_date = df['date'].iloc[seg.index[0]]
            end_date = df['date'].iloc[seg.index[-1]]
            # 片段起始边界
            plt.axvline(x=start_date, color='gray', linestyle='--', alpha=0.4, linewidth=0.8)
            # 最后一个片段的结束边界也画出来
            if i == len(segments) - 1:
                plt.axvline(x=end_date, color='gray', linestyle='--', alpha=0.4, linewidth=0.8)

    # 格式化日期轴
    plt.gca().xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m'))
    plt.gca().xaxis.set_major_locator(mdates.MonthLocator(interval=1))
    plt.xticks(rotation=45)

    plt.title(f"股票 {STOCK_CODE} 高峰切割效果图 (模式: {CUT_MODE})")
    plt.xlabel("日期")
    plt.ylabel("价格")
    plt.legend()
    plt.grid(True, alpha=0.3)
    plt.tight_layout()
    plt.show()

if __name__ == "__main__":
    main()