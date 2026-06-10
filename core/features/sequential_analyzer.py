"""
整体时序规律分析器（视角B）
不切割序列，在完整时间轴上统计上升/下降波段、反转形态、动量及主力方向。
所有可调参数集中在开头的配置区。
"""
import pandas as pd               # 数据处理库
import numpy as np                # 数值计算库
from typing import Dict           # 类型注解

# ============================================================
#  配  置  区
# ============================================================
PRICE_COL = 'close'               # 价格列名称
VOLUME_COL = 'volume'             # 成交量列名称

MIN_WAVE_PCT = 0.02               # 波段最小变化阈值（2%）
MOMENTUM_MA_PERIOD = 20           # 动量均线周期
TREND_THRESHOLD_DAYS = 5          # 顺势/逆势判断的最小连续天数

# ============================================================
#  分 析 器 类
# ============================================================
class SequentialAnalyzer:
    """
    整体时序规律分析器，输出一只股票的一组全局特征字典。
    """

    def _find_waves(self, series: pd.Series) -> Dict:
        """
        识别价格序列中的上升波段和下降波段。
        工作原理：
          - 从第一个有效价格开始，记录当前趋势方向（1上升，-1下降）
          - 当价格相对于波段起点的累计变化反向超过 MIN_WAVE_PCT 时，当前波段结束
        返回字典包含波段数量、平均持续天数、平均涨跌幅。
        """
        # 至少需要两个数据点才能判断波段
        if len(series) < 2:
            return {}

        waves_up = []              # 存储每个上升波段的持续天数
        waves_down = []            # 存储每个下降波段的持续天数
        changes_up = []            # 存储每个上升波段的累计涨幅
        changes_down = []          # 存储每个下降波段的累计跌幅

        current_dir = None         # 当前趋势方向：1上升，-1下降，None未确定
        start_idx = 0              # 当前波段的起始索引
        start_price = series.iloc[0]  # 当前波段的起始价格

        # 从第二个数据点开始遍历
        for i in range(1, len(series)):
            price = series.iloc[i]
            # 计算相对于波段起点的变化率
            change = (price - start_price) / start_price if start_price != 0 else 0

            # 如果方向未确定，尝试根据当前变化判断初始方向
            if current_dir is None:
                if change >= MIN_WAVE_PCT:           # 涨幅超过阈值，确定为上升
                    current_dir = 1
                    start_idx, start_price = i, price
                elif change <= -MIN_WAVE_PCT:        # 跌幅超过阈值，确定为下降
                    current_dir = -1
                    start_idx, start_price = i, price
                continue                             # 方向刚确定，不检测反转

            # 趋势反转检测：上升转下降
            if current_dir == 1 and change <= -MIN_WAVE_PCT:
                duration = i - start_idx             # 波段持续天数
                if duration > 0:
                    waves_up.append(duration)
                    changes_up.append(change)
                current_dir = -1                     # 开始新的下降波段
                start_idx, start_price = i, price

            # 趋势反转检测：下降转上升
            elif current_dir == -1 and change >= MIN_WAVE_PCT:
                duration = i - start_idx
                if duration > 0:
                    waves_down.append(duration)
                    changes_down.append(change)
                current_dir = 1                      # 开始新的上升波段
                start_idx, start_price = i, price

        # 返回统计结果
        return {
            'up_wave_count': len(waves_up),          # 上升波段总数
            'down_wave_count': len(waves_down),      # 下降波段总数
            'up_wave_avg_days': np.mean(waves_up) if waves_up else 0,
            'down_wave_avg_days': np.mean(waves_down) if waves_down else 0,
            'up_wave_avg_pct': np.mean(changes_up) if changes_up else 0,
            'down_wave_avg_pct': np.mean(changes_down) if changes_down else 0,
        }

    def _compute_momentum(self, series: pd.Series) -> Dict:
        """
        计算长周期动量指标和价格相对于均线的状态。
        返回：动量值、趋势状态（above/below/mixed）、连续在均线上/下方的天数。
        """
        # 数据不足一个均线周期，无法计算
        if len(series) < MOMENTUM_MA_PERIOD:
            return {'momentum': np.nan, 'trend_state': 'unknown', 'consecutive_days_vs_ma': 0}

        # 计算简单移动平均线
        ma = series.rolling(window=MOMENTUM_MA_PERIOD).mean()
        latest_price = series.iloc[-1]               # 最新收盘价
        latest_ma = ma.iloc[-1]                      # 最新均线值

        # 动量 = (价格 - 均线) / 均线
        momentum = (latest_price - latest_ma) / latest_ma if latest_ma != 0 else 0.0

        # 判断价格在均线上方还是下方
        above = series > ma                          # 布尔序列，每天是否在均线上方
        consecutive = 0                              # 连续天数计数器

        if above.iloc[-1]:                           # 最后一天在均线上方
            # 从最后一天向前数，直到出现不在上方的日子
            for val in reversed(above.values):
                if val:
                    consecutive += 1
                else:
                    break
            state = 'above' if consecutive >= TREND_THRESHOLD_DAYS else 'mixed'
        else:                                        # 最后一天在均线下方
            for val in reversed(above.values):
                if not val:                          # 注意：not val 表示在下方
                    consecutive += 1
                else:
                    break
            state = 'below' if consecutive >= TREND_THRESHOLD_DAYS else 'mixed'

        return {
            'momentum': momentum,
            'trend_state': state,
            'consecutive_days_vs_ma': consecutive
        }

    def analyze(self, df: pd.DataFrame, price_col: str = None, volume_col: str = None) -> Dict:
        """
        对一只股票的整体序列进行分析，返回特征字典。
        """
        if price_col is None:
            price_col = PRICE_COL
        if volume_col is None:
            volume_col = VOLUME_COL

        price = df[price_col]                        # 价格序列
        feats = {}

        # 1. 基本统计
        feats['total_days'] = len(df)                # 总交易日数
        if 'date' in df.columns:
            feats['start_date'] = df['date'].iloc[0] # 数据起始日期
            feats['end_date'] = df['date'].iloc[-1]  # 数据结束日期

        # 整体收益率
        if price.iloc[0] != 0:
            feats['overall_return'] = (price.iloc[-1] - price.iloc[0]) / price.iloc[0]
        else:
            feats['overall_return'] = 0.0

        # 整体波动率
        feats['volatility'] = price.pct_change().std()

        # 2. 上升/下降波段统计
        wave_feats = self._find_waves(price)
        feats.update(wave_feats)                     # 将波段统计合并到总特征字典

        # 3. 动量与趋势状态
        moment_feats = self._compute_momentum(price)
        feats.update(moment_feats)

        # 4. 成交量相关特征
        if volume_col in df.columns:
            vol = df[volume_col]
            feats['avg_volume'] = vol.mean()
            if vol.iloc[0] != 0:
                feats['volume_trend'] = (vol.iloc[-1] - vol.iloc[0]) / vol.iloc[0]
            else:
                feats['volume_trend'] = 0.0

        return feats