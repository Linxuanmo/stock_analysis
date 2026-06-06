"""
测试数据读取：自动加载所有科创板股票，验证数据完整性和列名。
从项目根目录运行：python tests/test_load.py
"""
import sys                              # 系统相关，用于修改 sys.path
from pathlib import Path                # 文件路径处理

# 将项目根目录加入到 Python 的模块搜索路径中
# 这样无论从哪里运行此脚本，都能正确导入 core 模块
PROJECT_ROOT = Path(__file__).resolve().parent.parent  # 项目根目录
sys.path.insert(0, str(PROJECT_ROOT))   # 插入到 sys.path 的最前面

from core.data.oriental_fetcher import OrientalFetcher  # 导入我们自己写的数据读取器

def main():
    # 构造数据目录的绝对路径：项目根目录 / data / raw
    data_dir = PROJECT_ROOT / "data" / "raw"
    print(f"数据目录: {data_dir}")

    # 创建 OrientalFetcher 实例，并显式指定数据目录
    fetcher = OrientalFetcher(raw_dir=str(data_dir))

    # 加载所有股票数据，all_stocks 是一个字典 {代码: DataFrame}
    all_stocks = fetcher.load_all_stocks()
    print(f"\n成功加载 {len(all_stocks)} 只股票\n")

    # 如果没有加载到任何股票，给出提示并退出
    if len(all_stocks) == 0:
        print("未找到任何股票数据，请检查 data/raw 目录。")
        return

    # 预览前 10 只股票的基本信息
    preview_count = min(10, len(all_stocks))  # 如果不到10只，就预览全部
    for i, (code, df) in enumerate(all_stocks.items()):
        if i >= preview_count:
            break  # 预览完毕
        print(f"股票代码: {code}")
        print(f"  列名: {list(df.columns)}")   # 列出该 DataFrame 的所有列名
        # 检查是否有 'date' 列且数据不为空
        if "date" in df.columns and not df.empty:
            print(f"  数据行数: {len(df)}")
            print(f"  日期范围: {df['date'].min().date()} ~ {df['date'].max().date()}")
        else:
            print("  ⚠ 缺少 'date' 列或数据为空")
        print("-" * 50)  # 分隔线

    # 简单统计：看看各股票的数据行数分布
    lengths = {code: len(df) for code, df in all_stocks.items()}  # 字典推导式 {代码: 行数}
    print("\n数据行数统计：")
    # 找出最少行数的股票
    print(f"  最少: {min(lengths.values())} 行 (股票 {min(lengths, key=lambda k: lengths[k])})")
    # 找出最多行数的股票
    print(f"  最多: {max(lengths.values())} 行 (股票 {max(lengths, key=lambda k: lengths[k])})")
    # 计算平均行数
    print(f"  平均: {sum(lengths.values()) / len(lengths):.1f} 行")

# 这是 Python 的标准写法，当这个文件被直接运行时，执行 main() 函数
if __name__ == "__main__":
    main()