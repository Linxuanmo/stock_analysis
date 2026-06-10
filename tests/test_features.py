"""
批量特征提取脚本
================
功能：
  1. 加载 data/raw 下所有股票数据（使用 OrientalFetcher）
  2. 对每只股票运行：
     - 视角A：高峰向量切割分析 (ImagePeakAnalyzer)
     - 视角B：整体时序规律分析 (SequentialAnalyzer)
  3. 将结果保存到 data/processed/ 下：
     - peak_features.csv       （片段级别特征）
     - sequential_features.csv （股票级别特征）
  4. 打印简要统计信息

从项目根目录运行：python tests/test_features.py
"""
import sys
from pathlib import Path
import pandas as pd
import numpy as np

# 将项目根目录加入 sys.path，确保能导入 core 模块
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from core.data.oriental_fetcher import OrientalFetcher
from core.features.image_peak_analyzer import ImagePeakAnalyzer
from core.features.sequential_analyzer import SequentialAnalyzer

# ============================================================
#  配  置  区
# ============================================================
# 数据目录（默认为项目根目录下的 data/raw）
RAW_DATA_DIR = PROJECT_ROOT / "data" / "raw"
# 输出目录（存放特征文件）
PROCESSED_DIR = PROJECT_ROOT / "data" / "processed"

# 分析器参数
# 视角A：高峰切割
PEAK_PROMINENCE = 0.1
PEAK_CUT_MODE = 'peak_to_peak'   # 'peak_to_peak' 或 'center_window'
PEAK_MAX_SEGMENT_LEN = 100
PEAK_WINDOW_HALF_LEN = 20
PEAK_DISCARD_FIRST_LAST = True

# 视角B：整体时序（使用默认配置，也可以在 sequential_analyzer.py 中修改）

# 是否打印详细进度
VERBOSE = True

# ============================================================
#  主 程 序
# ============================================================
def main():
    # 1. 确保输出目录存在
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)

    # 2. 加载所有股票数据
    print("正在加载股票数据...")
    fetcher = OrientalFetcher(raw_dir=str(RAW_DATA_DIR))
    all_stocks = fetcher.load_all_stocks()   # 返回字典 {code: DataFrame}
    print(f"成功加载 {len(all_stocks)} 只股票\n")

    if len(all_stocks) == 0:
        print("未找到任何股票数据，请检查 data/raw 目录。")
        return

    # 3. 初始化两个分析器
    peak_analyzer = ImagePeakAnalyzer(
        prominence=PEAK_PROMINENCE,
        max_segment_len=PEAK_MAX_SEGMENT_LEN,
        cut_mode=PEAK_CUT_MODE,
        window_half_len=PEAK_WINDOW_HALF_LEN,
        discard_first_last=PEAK_DISCARD_FIRST_LAST
    )
    seq_analyzer = SequentialAnalyzer()

    # 用于收集所有片段的列表（视角A）
    all_peak_features = []
    # 用于收集所有股票的整体特征列表（视角B）
    sequential_features_list = []

    # 4. 逐只股票处理
    for code, df in all_stocks.items():
        if VERBOSE:
            print(f"分析股票 {code} ... ({len(df)} 行)")

        # 4.1 视角A：获取片段特征 DataFrame
        peak_df = peak_analyzer.analyze(df)
        peak_df['code'] = code   # 添加股票代码列，方便区分
        all_peak_features.append(peak_df)

        # 4.2 视角B：获取整体特征字典
        seq_feats = seq_analyzer.analyze(df)
        seq_feats['code'] = code
        sequential_features_list.append(seq_feats)

    # 5. 合并所有片段特征并保存
    peak_all = pd.concat(all_peak_features, ignore_index=True)
    peak_path = PROCESSED_DIR / "peak_features.csv"
    peak_all.to_csv(peak_path, index=False, encoding='utf-8-sig')
    print(f"\n视角A 片段特征已保存至: {peak_path}")
    print(f"  共 {len(peak_all)} 个片段")

    # 6. 合并所有整体特征并保存
    seq_all = pd.DataFrame(sequential_features_list)
    seq_path = PROCESSED_DIR / "sequential_features.csv"
    seq_all.to_csv(seq_path, index=False, encoding='utf-8-sig')
    print(f"视角B 整体特征已保存至: {seq_path}")
    print(f"  共 {len(seq_all)} 只股票")

    # 7. 简要统计
    print("\n--- 片段特征统计 ---")
    print(peak_all.describe())
    print("\n--- 整体特征统计 ---")
    print(seq_all.describe())

if __name__ == "__main__":
    main()