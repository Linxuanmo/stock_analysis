# tests/test_peak_visual.py (示例)
import matplotlib.pyplot as plt
from core.data.oriental_fetcher import OrientalFetcher
from core.features.image_peak_analyzer import ImagePeakAnalyzer

fetcher = OrientalFetcher()
df = fetcher.load_stock('688469')

analyzer = ImagePeakAnalyzer(cut_mode='peak_to_peak', prominence=0.1)
price = df['close']
peaks = analyzer.find_peaks(price)
segments = analyzer.cut_segments_peak_to_peak(price, peaks)

plt.figure(figsize=(12,4))
plt.plot(df['date'], price, label='close')
plt.plot(df['date'].iloc[peaks], price.iloc[peaks], 'ro', label='peaks')
for i, seg in enumerate(segments):
    plt.axvline(x=df['date'].iloc[seg.index[0]], color='gray', linestyle='--', alpha=0.5)
plt.legend()
plt.show()