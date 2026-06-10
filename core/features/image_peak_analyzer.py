"""
基于高峰的向量切割分析器（视角A）- 优化版
新增功能：
  - 舍弃首尾不完整片段（防止缺失价格语境）
  - 中心窗口切片模式（以高峰为中心，左右对称取固定长度窗口）
  - 保留峰间切割模式，两种模式自由切换
所有可调参数集中在开头的配置区。
"""
import pandas as pd                     # 数据处理库，DataFrame
import numpy as np                      # 数值计算库，提供数学函数和数组
from scipy.signal import find_peaks     # 信号处理库，用于识别序列中的峰值
from typing import List, Dict, Optional, Tuple  # 类型注解，使函数签名更清晰

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
PRICE_COL = 'close'       # 价格列名称
VOLUME_COL = 'volume'     # 成交量列名称

# ============================================================
#  分 析 器 类
# ============================================================
class ImagePeakAnalyzer:
    """
    高峰向量切割分析器（支持峰间切割和中心窗口两种模式）
    用法：
        analyzer = ImagePeakAnalyzer(prominence=0.1, cut_mode='peak_to_peak')
        features_df = analyzer.analyze(df)   # df 是清洗后的单只股票DataFrame
    """
    def __init__(self, prominence: float = None, max_segment_len: int = None,
                 cut_mode: str = None, window_half_len: int = None,
                 discard_first_last: bool = None):
        """
        初始化分析器。允许在创建对象时覆盖配置区的默认参数。
        不传参数则使用配置区的值。
        """
        # 如果传入了参数就用传入的，否则用配置区的默认值
        self.prominence = prominence if prominence is not None else PROMINENCE
        self.max_segment_len = max_segment_len if max_segment_len is not None else MAX_SEGMENT_LEN
        self.cut_mode = cut_mode if cut_mode is not None else CUT_MODE
        self.window_half_len = window_half_len if window_half_len is not None else WINDOW_HALF_LEN
        self.discard_first_last = discard_first_last if discard_first_last is not None else DISCARD_FIRST_LAST
        self.min_segment_len = MIN_SEGMENT_LEN   # 最短片段长度（直接使用配置区的值）

    def find_peaks(self, series: pd.Series) -> np.ndarray:
        """
        在价格序列中找出所有显著高峰的位置索引。
        参数:
            series: 收盘价序列
        返回:
            峰值索引数组（已按时间顺序排列）
        """
        # find_peaks 返回 (峰值索引, 属性字典)，我们只需要索引
        peaks, _ = find_peaks(series.values, prominence=self.prominence)
        return peaks

    # ----------------- 峰间切割模式 -----------------
    def cut_segments_peak_to_peak(self, series: pd.Series, peaks: np.ndarray) -> List[pd.Series]:
        """
        按峰间关系切割片段。
        每个片段从前一个峰之后开始，到当前峰（含峰）结束。
        第一个片段从序列起点开始。
        如果片段长度超过 max_segment_len，只保留末尾部分。
        参数:
            series: 完整的收盘价序列
            peaks:   高峰索引数组
        返回:
            片段列表，每个元素是一个 pd.Series
        """
        segments = []                         # 存放切割出的所有片段
        start = 0                             # 当前片段的起始索引

        for peak in peaks:                    # 遍历每一个高峰
            seg = series.iloc[start: peak + 1]  # 截取从 start 到当前峰的子序列
            # 如果片段过长，只保留最近 max_segment_len 个交易日
            if len(seg) > self.max_segment_len:
                seg = seg.iloc[-self.max_segment_len:]
            segments.append(seg)              # 将片段加入列表
            start = peak + 1                  # 下一个片段的起点是当前峰之后

        # 最后一个峰之后可能还有剩余数据
        if start < len(series):
            remaining = series.iloc[start:]   # 获取剩余部分
            # 只有长度达到最小要求的剩余片段才保留
            if len(remaining) >= self.min_segment_len:
                segments.append(remaining)
        return segments

    # ----------------- 中心窗口切割模式 -----------------
    def cut_segments_center_window(self, series: pd.Series, peaks: np.ndarray) -> List[pd.Series]:
        """
        以每个高峰为中心，向左右各取 window_half_len 个交易日，
        生成标准长度的片段向量，用于形态相似度比对。
        参数:
            series: 完整的收盘价序列
            peaks:   高峰索引数组
        返回:
            片段列表
        """
        segments = []
        total_len = len(series)               # 序列总长度

        for peak in peaks:                    # 遍历每一个高峰
            # 计算窗口左边界（不能小于0）
            left = max(0, peak - self.window_half_len)
            # 计算窗口右边界（不能超过序列总长度，切片右端不含所以+1）
            right = min(total_len, peak + self.window_half_len + 1)
            seg = series.iloc[left:right]     # 截取窗口内的子序列
            segments.append(seg)
        return segments

    # ----------------- 片段特征提取 -----------------
    def extract_segment_features(self, segment: pd.Series,
                                 volume_segment: pd.Series = None) -> Dict:
        """
        从单个收盘价片段中提取特征字典（适用于两种模式）。
        提取的特征包括：长度、价格变化率、最高/最低价、波动率、平均成交量、趋势斜率，
        以及归一化后的价格序列（用于相似度计算）。
        """
        feats = {}

        # 1. 片段长度（交易日数）
        feats['length'] = len(segment)

        # 2. 价格变化率 (末价 - 首价) / 首价
        if segment.iloc[0] != 0:
            feats['price_change'] = (segment.iloc[-1] - segment.iloc[0]) / segment.iloc[0]
        else:
            feats['price_change'] = 0.0   # 防止除以零

        # 3. 片段内的最高价和最低价
        feats['max_price'] = segment.max()
        feats['min_price'] = segment.min()

        # 4. 波动率：日收益率的标准差
        returns = segment.pct_change().dropna()   # 计算日涨跌幅，并去掉第一个NaN
        feats['volatility'] = returns.std() if len(returns) > 0 else 0.0

        # 5. 平均成交量（如果提供了成交量序列）
        if volume_segment is not None and len(volume_segment) > 0:
            feats['avg_volume'] = volume_segment.mean()
        else:
            feats['avg_volume'] = np.nan

        # 6. 趋势斜率：（末价 - 首价）/ 长度，简单线性趋势
        if len(segment) > 1:
            feats['trend_slope'] = (segment.iloc[-1] - segment.iloc[0]) / len(segment)
        else:
            feats['trend_slope'] = 0.0

        # 7. 归一化价格序列（用于形态相似度比对）
        min_val = segment.min()                  # 片段内的最小值
        max_val = segment.max()                  # 片段内的最大值
        if max_val > min_val:
            # 将价格映射到 [0, 1] 区间
            normalized = (segment.values - min_val) / (max_val - min_val)
        else:
            # 如果最大最小值相等（价格不变），全部置为0
            normalized = np.zeros_like(segment.values)
        feats['normalized_series'] = normalized   # 存入特征字典

        return feats

    # ----------------- 主分析入口 -----------------
    def analyze(self, df: pd.DataFrame,
                price_col: str = None,
                volume_col: str = None) -> pd.DataFrame:
        """
        对一只股票的 DataFrame 执行高峰切割分析。
        参数:
            df:         清洗后的股票数据，必须包含日期、价格和成交量列
            price_col:  价格列名，默认取配置区的 PRICE_COL
            volume_col: 成交量列名，默认取配置区的 VOLUME_COL
        返回:
            DataFrame，每行为一个片段的特征（包括归一化序列）
        """
        # 使用传入的列名，或配置区的默认值
        if price_col is None:
            price_col = PRICE_COL
        if volume_col is None:
            volume_col = VOLUME_COL

        # 从 DataFrame 中取出价格序列和成交量序列
        price = df[price_col]
        volume = df[volume_col] if volume_col in df.columns else None

        # 1. 找高峰
        peaks = self.find_peaks(price)

        # 2. 根据切割模式选择对应的切割函数
        if self.cut_mode == 'center_window':
            segments = self.cut_segments_center_window(price, peaks)
        else:  # 默认峰间切割
            segments = self.cut_segments_peak_to_peak(price, peaks)

        # 3. 若设置舍弃首尾，且片段数足够（≥3），移除第一个和最后一个
        if self.discard_first_last and len(segments) >= 3:
            segments = segments[1:-1]

        # 4. 遍历每个片段，提取特征
        feature_list = []                      # 存放每个片段的特征字典
        for i, seg in enumerate(segments):
            # 获取片段在原 DataFrame 中的起始和结束索引
            start_idx = seg.index[0]
            end_idx = seg.index[-1]
            # 提取日期（如果存在 date 列）
            start_date = df.loc[start_idx, 'date'] if 'date' in df.columns else None
            end_date = df.loc[end_idx, 'date'] if 'date' in df.columns else None

            # 提取对应的成交量片段
            vol_seg = volume.loc[seg.index] if volume is not None else None

            # 提取特征字典
            feats = self.extract_segment_features(seg, vol_seg)

            # 补充片段标识和日期信息
            feats['segment_id'] = i            # 片段编号
            feats['start_date'] = start_date   # 片段起始日期
            feats['end_date'] = end_date       # 片段结束日期

            feature_list.append(feats)

        # 将所有片段的特征字典列表转换为 DataFrame
        return pd.DataFrame(feature_list)