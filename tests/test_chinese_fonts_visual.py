"""
依次测试中文字体显示效果。
每种字体生成一张临时图表，显示常见的中文股票术语。
运行后请手动关闭当前图表，自动弹出下一个字体的测试图。
"""
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm

# 上一步检测到的可能包含中文的字体列表（从 list_chinese_fonts.py 的输出中筛选）
# 剔除明显不包含中文的字体（如 STIX 系列、Symbol 等），保留最可能的
candidate_fonts = [
    'Adobe Fan Heiti Std',
    'Adobe Gothic Std',
    'Adobe Heiti Std',
    'Adobe Ming Std',
    'Adobe Myungjo Std',
    'Adobe Song Std',
    'FangSong',
    'HYSWLongFangSong',
    'KaiTi',
    'Microsoft JhengHei',
    'Microsoft YaHei',
    'MingLiU-ExtB',
    'SimHei',
    'SimSun',
    'SimSun-ExtB',
]

# 要显示的测试文本（常见乱码字）
test_text = "股票 价格 高峰 切割 日期 成交量 模式 效果"

for font_name in candidate_fonts:
    # 临时设置字体
    plt.rcParams['font.sans-serif'] = [font_name]
    plt.rcParams['axes.unicode_minus'] = False

    fig, ax = plt.subplots(figsize=(6, 2))
    ax.text(0.5, 0.5, f"字体: {font_name}\n{test_text}",
            ha='center', va='center', fontsize=16)
    ax.set_title(f"测试字体: {font_name}")
    ax.axis('off')
    plt.tight_layout()
    plt.show(block=True)   # 阻塞，手动关闭窗口后继续下一个