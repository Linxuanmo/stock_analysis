"""
基于高峰的向量切割分析器（视角A）- 优化版
新增功能：
  - 舍弃首尾不完整片段（防止缺失价格语境）
  - 中心窗口切片模式（以高峰为中心，左右对称取固定长度窗口）
  - 保留峰间切割模式，两种模式自由切换
所有可调参数集中在开头的配置区。
"""
import pandas as pd
import numpy as np
from scipy.signal import find_peaks
from typing import List, Dict, Optional, Tuple

# ============================================================
#  配  置  区 （按需修改）
# ============================================================

# ----- 高峰识别参数 -----
PROMINENCE = 0.1          # 高峰显著程度（值越小，找到的峰越多）
MAX_SEGMENT_LEN = 100     # 峰间切割模式下的最大片段长度（交易日数）
MIN_SEGMENT_LEN = 5       # 最短片段长度（少于该天数的片段会被丢弃）

# ----- 切割模式选择 -----
# 模式1：'peak_to_peak'   → 峰到峰切割（传统模式）
# 模式2：'center_window'  → 以峰为中心，向左右各取固定窗口
CUT_MODE = 'peak_to_peak'  # 默认峰间切割，也可改为 'center_window'

# ----- 中心窗口模式专用参数 -----
WINDOW_HALF_LEN = 20      # 窗口半长（总窗口长度 = 2 * WINDOW_HALF_LEN + 1）

# ----- 首尾处理 -----
DISCARD_FIRST_LAST = True # 是否丢弃首尾不完整片段（推荐开启）

# ----- 列名配置 -----
PRICE_COL = 'close'
VOLUME_COL = 'volume'

# ============================================================
#  分 析 器 类
# ============================================================
class ImagePeakAnalyzer:
    """
    高峰向量切割分析器（支持峰间切割和中心窗口两种模式）
    """
    def __init__(self, prominence: float = None, max_segment_len: int = None,
                 cut_mode: str = None, window_half_len: int = None,
                 discard_first_last: bool = None):
        # 若未传入参数，使用配置区的默认值
        self.prominence = prominence if prominence is not None else PROMINENCE
        self.max_segment_len = max_segment_len if max_segment_len is not None else MAX_SEGMENT_LEN
        self.cut_mode = cut_mode if cut_mode is not None else CUT_MODE
        self.window_half_len = window_half_len if window_half_len is not None else WINDOW_HALF_LEN
        self.discard_first_last = discard_first_last if discard_first_last is not None else DISCARD_FIRST_LAST
        self.min_segment_len = MIN_SEGMENT_LEN

    def find_peaks(self, series: pd.Series) -> np.ndarray:
        """
        在价格序列中找出所有显著高峰的位置索引。
        返回：峰值索引数组（已按时间顺序排列）。
        """
        peaks, _ = find_peaks(series.values, prominence=self.prominence)
        return peaks

    # ----------------- 峰间切割模式 -----------------
    def cut_segments_peak_to_peak(self, series: pd.Series, peaks: np.ndarray) -> List[pd.Series]:
        """
        按峰间关系切割片段。
        返回片段列表，每个片段是从前一个峰之后到当前峰（含峰）的序列。
        """
        segments = []
        start = 0
        for peak in peaks:
            seg = series.iloc[start: peak + 1]
            if len(seg) > self.max_segment_len:
                seg = seg.iloc[-self.max_segment_len:]   # 只保留最近 max_segment_len 天
            segments.append(seg)
            start = peak + 1

        # 最后一个峰之后的剩余部分（如果长度>= min_segment_len）
        if start < len(series):
            remaining = series.iloc[start:]
            if len(remaining) >= self.min_segment_len:
                segments.append(remaining)
        return segments

    # ----------------- 中心窗口切割模式 -----------------
    def cut_segments_center_window(self, series: pd.Series, peaks: np.ndarray) -> List[pd.Series]:
        """
        以每个高峰为中心，向左右各取 window_half_len 个交易日，
        生成标准长度的片段向量，用于形态相似度比对。
        """
        segments = []
        total_len = len(series)
        for peak in peaks:
            left = max(0, peak - self.window_half_len)
            right = min(total_len, peak + self.window_half_len + 1)  # 切片右端点不含，所以+1
            seg = series.iloc[left:right]
            # 如果窗口不满（边界峰），跳过或保留，这里选择保留（但长度可能不同，后续可对齐）
            # 若要严格长度，可填充或丢弃，目前保留以便观察
            segments.append(seg)
        return segments

    # ----------------- 片段特征提取 -----------------
    def extract_segment_features(self, segment: pd.Series,
                                 volume_segment: pd.Series = None) -> Dict:
        """
        从单个片段中提取特征字典（适用于两种模式）。
        """
        feats = {}
        feats['length'] = len(segment)

        if segment.iloc[0] != 0:
            feats['price_change'] = (segment.iloc[-1] - segment.iloc[0]) / segment.iloc[0]
        else:
            feats['price_change'] = 0.0

        feats['max_price'] = segment.max()
        feats['min_price'] = segment.min()

        returns = segment.pct_change().dropna()
        feats['volatility'] = returns.std() if len(returns) > 0 else 0.0

        if volume_segment is not None and len(volume_segment) > 0:
            feats['avg_volume'] = volume_segment.mean()
        else:
            feats['avg_volume'] = np.nan

        if len(segment) > 1:
            feats['trend_slope'] = (segment.iloc[-1] - segment.iloc[0]) / len(segment)
        else:
            feats['trend_slope'] = 0.0

        # 附加：价格序列本身的归一化向量（可用于相似度计算）
        # 归一化到 [0,1] 区间，便于比较形态
        min_val = segment.min()
        max_val = segment.max()
        if max_val > min_val:
            normalized = (segment.values - min_val) / (max_val - min_val)
        else:
            normalized = np.zeros_like(segment.values)
        feats['normalized_series'] = normalized  # 存入特征字典（DataFrame中将以object形式存储）

        return feats

    # ----------------- 主分析入口 -----------------
    def analyze(self, df: pd.DataFrame,
                price_col: str = None,
                volume_col: str = None) -> pd.DataFrame:
        """
        对一只股票的 DataFrame 执行高峰切割分析。
        返回：DataFrame，每行为一个片段的特征（包括归一化序列）。
        """
        if price_col is None:
            price_col = PRICE_COL
        if volume_col is None:
            volume_col = VOLUME_COL

        price = df[price_col]
        volume = df[volume_col] if volume_col in df.columns else None

        # 1. 找高峰
        peaks = self.find_peaks(price)

        # 2. 根据模式切割
        if self.cut_mode == 'center_window':
            segments = self.cut_segments_center_window(price, peaks)
        else:  # 默认峰间切割
            segments = self.cut_segments_peak_to_peak(price, peaks)

        # 3. 若设置舍弃首尾，则移除第一个和最后一个片段（不完整）
        if self.discard_first_last and len(segments) >= 3:
            segments = segments[1:-1]

        # 4. 提取每个片段的特征
        feature_list = []
        for i, seg in enumerate(segments):
            start_idx = seg.index[0]
            end_idx = seg.index[-1]
            start_date = df.loc[start_idx, 'date'] if 'date' in df.columns else None
            end_date = df.loc[end_idx, 'date'] if 'date' in df.columns else None

            vol_seg = volume.loc[seg.index] if volume is not None else None
            feats = self.extract_segment_features(seg, vol_seg)
            feats['segment_id'] = i
            feats['start_date'] = start_date
            feats['end_date'] = end_date
            feature_list.append(feats)

        return pd.DataFrame(feature_list)