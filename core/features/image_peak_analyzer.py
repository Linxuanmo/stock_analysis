"""
基于高峰的结构化向量子分析器（新）
==================================
将每一个显著高峰转化为一个独立的“向量子”，包含：
  - 起止时间与价格
  - 左右半段斜率与涨幅
  - 波动率与成交量
  - 归一化形态序列

所有参数集中在开头的配置区。
"""
import pandas as pd
import numpy as np
from scipy.signal import find_peaks
from typing import List, Dict, Optional

# ============================================================
#  配  置  区
# ============================================================
# 高峰识别参数
PEAK_PROMINENCE = 0.1        # 高峰显著程度
VALLEY_PROMINENCE = 0.1      # 低谷显著程度（与高峰类似，但作用于 -price）

# 最低片段长度限制
MIN_SEGMENT_LEN = 3          # 若向量子总长度小于此值则丢弃

# 列名配置
PRICE_COL = 'close'
VOLUME_COL = 'volume'

# ============================================================
#  分 析 器 类
# ============================================================
class ImagePeakAnalyzer:
    """
    高峰向量子分析器
    用法：
        analyzer = ImagePeakAnalyzer()
        vectors_df = analyzer.analyze(df)   # df 为清洗后的单只股票DataFrame
    """
    def __init__(self, peak_prominence: float = None, valley_prominence: float = None):
        self.peak_prominence = peak_prominence if peak_prominence is not None else PEAK_PROMINENCE
        self.valley_prominence = valley_prominence if valley_prominence is not None else VALLEY_PROMINENCE
        self.min_seg_len = MIN_SEGMENT_LEN

    def find_peaks(self, series: pd.Series) -> np.ndarray:
        """找局部极大值（高峰）"""
        peaks, _ = find_peaks(series.values, prominence=self.peak_prominence)
        return peaks

    def find_valleys(self, series: pd.Series) -> np.ndarray:
        """找局部极小值（低谷），通过将价格取反后用 find_peaks"""
        valleys, _ = find_peaks(-series.values, prominence=self.valley_prominence)
        return valleys

    def build_peak_vectors(self, df: pd.DataFrame,
                           price_col: str = PRICE_COL,
                           volume_col: str = VOLUME_COL) -> pd.DataFrame:
        """
        为每个高峰构建结构化的向量子，返回 DataFrame。
        """
        price = df[price_col]
        volume = df[volume_col] if volume_col in df.columns else None

        peaks = self.find_peaks(price)
        valleys = self.find_valleys(price)

        # 如果没有足够的高峰或低谷，返回空
        if len(peaks) == 0:
            return pd.DataFrame()

        # 将谷底索引与数据边界组合，方便查找左右谷
        all_valleys = list(valleys)
        # 加入边界：0 和 len(price)-1 也视为谷底候选（如果边界是局部最低则用，否则也会被考虑）
        # 但直接加 0 和 -1 可能导致不合理片段，我们仅将其作为备用。
        # 更稳妥：只使用检测到的谷底，若找不到则用边界。
        if len(all_valleys) == 0:
            all_valleys = [0, len(price)-1]

        vectors = []
        data_start_date = df['date'].iloc[0].strftime('%Y-%m-%d') if 'date' in df.columns else ''
        data_end_date = df['date'].iloc[-1].strftime('%Y-%m-%d') if 'date' in df.columns else ''
        data_period = f"{data_start_date}_{data_end_date}"

        for idx, peak in enumerate(peaks):
            # 找左侧最近谷底（索引小于 peak 的最大谷底）
            left_valleys = [v for v in all_valleys if v < peak]
            if left_valleys:
                start_idx = max(left_valleys)   # 最近的左侧谷
            else:
                start_idx = 0                   # 没有则用第一个点

            # 找右侧最近谷底（索引大于 peak 的最小谷底）
            right_valleys = [v for v in all_valleys if v > peak]
            if right_valleys:
                end_idx = min(right_valleys)    # 最近的右侧谷
            else:
                end_idx = len(price) - 1        # 没有则用最后一个点

            # 过滤过短的片段
            if end_idx - start_idx < self.min_seg_len:
                continue

            # 提取价格子序列
            seg = price.iloc[start_idx:end_idx+1]
            start_price = price.iloc[start_idx]
            peak_price = price.iloc[peak]
            end_price = price.iloc[end_idx]

            rise_dur = peak - start_idx
            fall_dur = end_idx - peak
            total_dur = end_idx - start_idx

            # 计算斜率（若时长为0则斜率记为0）
            rise_slope = (peak_price - start_price) / rise_dur if rise_dur > 0 else 0.0
            fall_slope = (end_price - peak_price) / fall_dur if fall_dur > 0 else 0.0
            rise_change = peak_price - start_price
            fall_change = end_price - peak_price

            # 波动率
            returns = seg.pct_change().dropna()
            volatility = returns.std() if len(returns) > 0 else 0.0

            # 平均成交量
            avg_vol = volume.iloc[start_idx:end_idx+1].mean() if volume is not None else np.nan

            # 归一化序列
            min_val = seg.min()
            max_val = seg.max()
            if max_val > min_val:
                normalized = (seg.values - min_val) / (max_val - min_val)
            else:
                normalized = np.zeros_like(seg.values)
            normalized_str = np.array2string(normalized, separator=',', max_line_width=10000)

            # 组装向量子
            vec = {
                'code': None,  # 外部填写
                'peak_id': idx,
                'start_date': df['date'].iloc[start_idx] if 'date' in df.columns else None,
                'peak_date': df['date'].iloc[peak] if 'date' in df.columns else None,
                'end_date': df['date'].iloc[end_idx] if 'date' in df.columns else None,
                'start_price': start_price,
                'peak_price': peak_price,
                'end_price': end_price,
                'rise_duration': rise_dur,
                'fall_duration': fall_dur,
                'total_duration': total_dur,
                'rise_slope': rise_slope,
                'fall_slope': fall_slope,
                'rise_change': rise_change,
                'fall_change': fall_change,
                'volatility': volatility,
                'avg_volume': avg_vol,
                'normalized_series': normalized_str,
                'data_period': data_period
            }
            vectors.append(vec)

        return pd.DataFrame(vectors)

    def analyze(self, df: pd.DataFrame, price_col: str = None, volume_col: str = None) -> pd.DataFrame:
        """
        主分析入口：返回高峰向量子 DataFrame。
        """
        if price_col is None:
            price_col = PRICE_COL
        if volume_col is None:
            volume_col = VOLUME_COL
        vectors_df = self.build_peak_vectors(df, price_col, volume_col)
        if not vectors_df.empty:
            # 这里 code 字段由外部填写，analyze 不负责填 code
            pass
        return vectors_df