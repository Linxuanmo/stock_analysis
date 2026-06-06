"""
整体时序规律分析器（视角B）
不切割序列，在完整时间轴上统计上升/下降波段、反转形态、动量及主力方向。
所有可调参数集中在开头的配置区。
"""
import pandas as pd
import numpy as np
from typing import Dict

# ============================================================
#  配  置  区
# ============================================================
PRICE_COL = 'close'
VOLUME_COL = 'volume'

MIN_WAVE_PCT = 0.02           # 波段最小变化阈值（2%）
MOMENTUM_MA_PERIOD = 20       # 动量均线周期
TREND_THRESHOLD_DAYS = 5      # 顺势/逆势判断的最小连续天数

# ============================================================
#  分 析 器 类
# ============================================================
class SequentialAnalyzer:
    def _find_waves(self, series: pd.Series) -> Dict:
        if len(series) < 2:
            return {}
        waves_up, waves_down = [], []
        changes_up, changes_down = [], []
        current_dir = None
        start_idx = 0
        start_price = series.iloc[0]

        for i in range(1, len(series)):
            price = series.iloc[i]
            change = (price - start_price) / start_price if start_price != 0 else 0
            if current_dir is None:
                if change >= MIN_WAVE_PCT:
                    current_dir = 1
                    start_idx, start_price = i, price
                elif change <= -MIN_WAVE_PCT:
                    current_dir = -1
                    start_idx, start_price = i, price
                continue

            # 趋势反转检测
            if current_dir == 1 and change <= -MIN_WAVE_PCT:
                duration = i - start_idx
                if duration > 0:
                    waves_up.append(duration)
                    changes_up.append(change)
                current_dir = -1
                start_idx, start_price = i, price
            elif current_dir == -1 and change >= MIN_WAVE_PCT:
                duration = i - start_idx
                if duration > 0:
                    waves_down.append(duration)
                    changes_down.append(change)
                current_dir = 1
                start_idx, start_price = i, price

        return {
            'up_wave_count': len(waves_up),
            'down_wave_count': len(waves_down),
            'up_wave_avg_days': np.mean(waves_up) if waves_up else 0,
            'down_wave_avg_days': np.mean(waves_down) if waves_down else 0,
            'up_wave_avg_pct': np.mean(changes_up) if changes_up else 0,
            'down_wave_avg_pct': np.mean(changes_down) if changes_down else 0,
        }

    def _compute_momentum(self, series: pd.Series) -> Dict:
        if len(series) < MOMENTUM_MA_PERIOD:
            return {'momentum': np.nan, 'trend_state': 'unknown', 'consecutive_days_vs_ma': 0}
        ma = series.rolling(window=MOMENTUM_MA_PERIOD).mean()
        latest_price = series.iloc[-1]
        latest_ma = ma.iloc[-1]
        momentum = (latest_price - latest_ma) / latest_ma if latest_ma != 0 else 0.0

        above = series > ma
        consecutive = 0
        if above.iloc[-1]:
            for val in reversed(above.values):
                if val: consecutive += 1
                else: break
            state = 'above' if consecutive >= TREND_THRESHOLD_DAYS else 'mixed'
        else:
            for val in reversed(above.values):
                if not val: consecutive += 1
                else: break
            state = 'below' if consecutive >= TREND_THRESHOLD_DAYS else 'mixed'
        return {'momentum': momentum, 'trend_state': state, 'consecutive_days_vs_ma': consecutive}

    def analyze(self, df: pd.DataFrame, price_col: str = None, volume_col: str = None) -> Dict:
        if price_col is None: price_col = PRICE_COL
        if volume_col is None: volume_col = VOLUME_COL
        price = df[price_col]
        feats = {}
        feats['total_days'] = len(df)
        if 'date' in df.columns:
            feats['start_date'] = df['date'].iloc[0]
            feats['end_date'] = df['date'].iloc[-1]
        feats['overall_return'] = (price.iloc[-1] - price.iloc[0]) / price.iloc[0] if price.iloc[0] != 0 else 0.0
        feats['volatility'] = price.pct_change().std()

        wave_feats = self._find_waves(price)
        feats.update(wave_feats)

        moment_feats = self._compute_momentum(price)
        feats.update(moment_feats)

        if volume_col in df.columns:
            vol = df[volume_col]
            feats['avg_volume'] = vol.mean()
            feats['volume_trend'] = (vol.iloc[-1] - vol.iloc[0]) / vol.iloc[0] if vol.iloc[0] != 0 else 0.0

        return feats