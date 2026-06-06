"""
列出系统中所有可能支持中文的字体名称。
用于解决 matplotlib 中文显示问题。
"""
import matplotlib.font_manager as fm

# 获取系统所有字体
all_fonts = fm.fontManager.ttflist
chinese_fonts = set()

# 常见中文字体关键字（可根据需要补充）
keywords = ['CJK', 'Hei', 'Song', 'Kai', 'Ming', 'Fang', 'Yuan', 'SimSun', 'SimHei', 'YaHei', 'LiSu', 'ST']

for font in all_fonts:
    name = font.name
    # 检查字体名称或文件路径是否包含关键字
    if any(kw.lower() in name.lower() for kw in keywords):
        chinese_fonts.add(name)

if chinese_fonts:
    print("找到以下可能的中文字体：")
    for f in sorted(chinese_fonts):
        print(f"  {f}")
else:
    print("未检测到明确的中文字体，以下列出所有可用字体名称（手动筛选）：")
    for f in sorted([font.name for font in all_fonts]):
        print(f"  {f}")