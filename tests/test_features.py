"""
批量提取高峰向量子特征
======================
调用 ImagePeakAnalyzer 为每只股票生成结构化的高峰向量子，
保存到 data/processed/peak_vectors.csv。
"""
import sys
from pathlib import Path
import pandas as pd

# 项目根目录
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from core.data.oriental_fetcher import OrientalFetcher
from core.features.image_peak_analyzer import ImagePeakAnalyzer

# ============================================================
#  配  置  区
# ============================================================
RAW_DATA_DIR = PROJECT_ROOT / "data" / "raw"   # 原始数据目录
PROCESSED_DIR = PROJECT_ROOT / "data" / "processed"  # 输出目录

# 分析器参数（与 image_peak_analyzer 配置同步）
PEAK_PROMINENCE = 0.1
VALLEY_PROMINENCE = 0.1

# ============================================================
#  主 程 序
# ============================================================
def main():
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)

    # 加载所有股票
    fetcher = OrientalFetcher(raw_dir=str(RAW_DATA_DIR))
    all_stocks = fetcher.load_all_stocks()
    print(f"已加载 {len(all_stocks)} 只股票")

    analyzer = ImagePeakAnalyzer(
        peak_prominence=PEAK_PROMINENCE,
        valley_prominence=VALLEY_PROMINENCE
    )

    all_vectors = []
    for code, df in all_stocks.items():
        print(f"分析 {code} ... ({len(df)} 行)")
        vec_df = analyzer.analyze(df)
        if vec_df.empty:
            continue
        vec_df['code'] = code
        all_vectors.append(vec_df)

    if not all_vectors:
        print("没有生成任何向量子，请调整 prominence 参数。")
        return

    result = pd.concat(all_vectors, ignore_index=True)
    output_path = PROCESSED_DIR / "peak_vectors.csv"
    result.to_csv(output_path, index=False, encoding='utf-8-sig')
    print(f"\n向量子特征已保存至: {output_path}")
    print(f"共 {len(result)} 个高峰向量子")

    # 简要统计
    print("\n---- 数值字段统计 ----")
    numeric_cols = ['rise_duration', 'fall_duration', 'total_duration',
                    'rise_slope', 'fall_slope', 'rise_change', 'fall_change',
                    'volatility', 'avg_volume']
    for col in numeric_cols:
        if col in result.columns:
            print(f"{col}: 均值={result[col].mean():.4f}, 标准差={result[col].std():.4f}")

if __name__ == "__main__":
    main()