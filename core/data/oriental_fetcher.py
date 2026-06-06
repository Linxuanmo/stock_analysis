"""
东方财富/通达信数据读取器
所有可调参数均在文件开头的“配置区”中设置。
逐行注释版 —— 帮助学习每一行代码的作用。
"""
import pandas as pd               # 数据处理库，提供DataFrame、read_csv、read_excel等
from pathlib import Path          # 面向对象的文件路径操作，比字符串拼接更安全
import glob                       # 文件名模式匹配，例如查找所有 *.xls 文件
import re                         # 正则表达式，用于从文件名中提取股票代码
from typing import Dict, List, Optional  # 类型注解，让函数签名更清晰

# ============================================================
#  配  置  区 （可根据需要修改这些参数）
# ============================================================

# 原始数据存放的根目录（相对于项目根目录的路径）
RAW_DATA_DIR = "data/raw"

# 数据文件的搜索模式
# '**/*.xls'   → 递归搜索 raw 下所有子文件夹中的 .xls 文件
# '*.xls'      → 只搜索 raw 根目录下的 .xls 文件
FILE_PATTERN = "**/*.xls"

# 股票代码提取正则：匹配连续的6位数字（如 688006）
CODE_PATTERN = r'(\d{6})'

# 表头所在行（0 索引，即第几行为列名）
# 通达信导出的文件：第1行是股票名称，第2行是列名 → 所以 header=1
HEADER_ROW = 1

# 中文列名到英文简写的映射字典
COLUMN_MAP = {
    "时间": "date",       # 日期
    "开盘": "open",       # 开盘价
    "最高": "high",       # 最高价
    "最低": "low",        # 最低价
    "收盘": "close",      # 收盘价
    "成交量": "volume",   # 成交量
}

# 是否剔除成交量为 0 的行（停牌或无效数据）
DROP_ZERO_VOLUME = True
# 是否剔除价格列中小于等于 0 的行（异常数据）
DROP_NON_POSITIVE_PRICE = True
# 参与价格清洗的列名列表
PRICE_COLS = ["open", "high", "low", "close"]

# ============================================================
#  数 据 读 取 器 类
# ============================================================
class OrientalFetcher:
    """
    东方财富/通达信数据读取器
    负责从 data/raw 目录中读取手动导出的 .xls 文件，并清洗为标准格式
    """
    def __init__(self, raw_dir: Optional[str] = None):
        """
        初始化时，可以指定 raw_dir，如果不指定则使用配置区的 RAW_DATA_DIR
        """
        # 如果传入了 raw_dir 参数就使用它，否则使用配置区的值
        self.raw_dir = Path(raw_dir if raw_dir is not None else RAW_DATA_DIR)

    def _extract_code(self, filename_stem: str) -> Optional[str]:
        """
        从文件名（不含后缀的部分）中提取6位股票代码
        例如 "1_688469" → "688469"
        """
        # 在文件名字符串中搜索符合 CODE_PATTERN 的部分
        match = re.search(CODE_PATTERN, filename_stem)
        # 如果找到，返回匹配到的第一组（即括号内的6位数字），否则返回 None
        return match.group(1) if match else None

    def _find_files(self) -> List[Path]:
        """
        在 raw_dir 下搜索所有符合 FILE_PATTERN 的数据文件
        返回 Path 对象的列表
        """
        # 构造搜索模式，例如 "data/raw/**/*.xls"
        pattern = str(self.raw_dir / FILE_PATTERN)
        # 使用 glob 进行递归文件匹配，返回所有匹配的文件路径字符串
        # 再用 map 转换为 Path 对象并返回列表
        return [Path(f) for f in glob.glob(pattern, recursive=True)]

    def _is_text_file(self, filepath: Path) -> bool:
        """
        检测文件是否为纯文本（而非二进制 Excel）
        原理：读取文件头部几个字节，查看是否为 Excel 的特征字节
        """
        try:
            # 以二进制只读方式打开文件
            with open(filepath, 'rb') as f:
                head = f.read(8)      # 读取前 8 个字节
            # 旧版 .xls 文件的开头特征码（OLE2 复合文档）
            if head[:4] == b'\xd0\xcf\x11\xe0':
                return False
            # 新版 .xlsx 文件的开头是 ZIP 文件头
            if head[:4] == b'PK\x03\x04':
                return False
            # 如果头部包含很多 0 字节，很可能是二进制文件
            if b'\x00' in head:
                return False
            # 其他情况视为文本文件
            return True
        except Exception:
            # 读取失败时，保守地认为不是文本文件
            return False

    def read_local_xls(self, filepath: Path) -> pd.DataFrame:
        """
        智能读取数据文件：
        - 如果检测为文本文件，优先按制表符分隔 + GBK 编码读取（通达信典型格式）
        - 否则按 Excel 读取，尝试多个引擎
        """
        # ----- 第1步：尝试以文本方式读取 -----
        if self._is_text_file(filepath):
            # 尝试1：固定用制表符分隔，GBK 编码，C 引擎速度快
            try:
                df = pd.read_csv(
                    filepath,
                    header=HEADER_ROW,        # 指定第几行为列名
                    encoding='gbk',           # 通达信导出文件一般是 GBK 编码
                    sep='\t',                 # 列之间用 Tab 分隔
                    comment='#',              # 忽略以 # 开头的注释行（如文件末尾的“数据来源”）
                    on_bad_lines='skip',      # 跳过格式异常的行（需 pandas ≥1.4）
                    engine='c'                # 使用 C 引擎，速度快
                )
                # 检查是否成功读取到多列（如果只有1列，说明分隔符可能不对）
                if df.shape[1] > 1:
                    print(f"提示：{filepath.name} 识别为文本文件 (制表符分隔)")
                    return self._clean_and_rename(df)   # 清洗并重命名后返回
            except Exception as e:
                print(f"文本方式(制表符)读取 {filepath.name} 失败: {e}")

            # 尝试2：自动检测分隔符，使用 Python 引擎（稍慢但更智能）
            try:
                df = pd.read_csv(
                    filepath,
                    header=HEADER_ROW,
                    encoding='gbk',
                    sep=None,                 # None 表示自动检测分隔符
                    comment='#',
                    on_bad_lines='skip',
                    engine='python'           # 自动检测分隔符必须用 Python 引擎
                )
                if df.shape[1] > 1:
                    print(f"提示：{filepath.name} 识别为文本文件 (自动检测分隔符)")
                    return self._clean_and_rename(df)
            except Exception as e:
                print(f"文本方式(自动检测)读取 {filepath.name} 失败: {e}")

            # 如果文本方式都失败，打印提示并继续尝试 Excel 引擎
            print(f"{filepath.name} 文本读取未成功，尝试Excel引擎...")

        # ----- 第2步：按二进制 Excel 方式读取 -----
        # 要尝试的引擎列表：openpyxl 支持新格式，xlrd 支持旧格式，None 让 pandas 自动选
        engines = ['openpyxl', 'xlrd', None]
        last_exception = None            # 记录最后一次错误，用于最后抛出
        for engine in engines:
            try:
                # 尝试用当前引擎读取 Excel
                df = pd.read_excel(filepath, header=HEADER_ROW, engine=engine)
                return self._clean_and_rename(df)   # 成功则清洗并返回
            except Exception as e:
                last_exception = e        # 记录错误，尝试下一个引擎
                continue                  # 继续下一个引擎

        # 所有方式都失败，抛出异常
        raise ValueError(f"无法读取 {filepath}。最后错误: {last_exception}")

    def _clean_and_rename(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        对读取后的 DataFrame 进行统一的清洗和列重命名：
        1. 去除列名前后的空格
        2. 将中文列名映射为英文简写
        3. 转换日期格式并排序
        4. 剔除无效数据（成交量为0、价格为非正、核心价格列为空）
        """
        # 1. 去除列名前后可能存在的空格（避免因 " 时间" 这样的列名导致映射失败）
        df.columns = [str(col).strip() for col in df.columns]

        # 2. 根据配置区的 COLUMN_MAP 重命名列名
        rename_dict = {}                         # 存放实际需要重命名的映射
        for orig_name, new_name in COLUMN_MAP.items():
            if orig_name in df.columns:          # 只映射实际存在的列
                rename_dict[orig_name] = new_name
        df.rename(columns=rename_dict, inplace=True)  # 执行重命名

        # 3. 处理日期列
        if "date" in df.columns:
            df["date"] = pd.to_datetime(df["date"])   # 转为标准 datetime 类型
            df.sort_values("date", inplace=True)       # 按日期升序排列

        # 4. 基础清洗 —— 剔除无效成交量
        if DROP_ZERO_VOLUME and "volume" in df.columns:
            df = df[df["volume"] > 0]   # 只保留成交量大于 0 的行

        # 5. 基础清洗 —— 剔除价格为非正的行
        if DROP_NON_POSITIVE_PRICE:
            for col in PRICE_COLS:                # 遍历每一个价格列
                if col in df.columns:
                    df = df[df[col] > 0]          # 只保留该列大于 0 的行

        # 6. 删除核心价格列中有缺失值的行（兼容旧版 pandas，不用 errors 参数）
        existing_price_cols = [c for c in PRICE_COLS if c in df.columns]
        if existing_price_cols:
            df.dropna(subset=existing_price_cols, inplace=True)  # 删除价格缺失的行

        # 7. 重置行索引（删除行后索引可能不连续）
        df.reset_index(drop=True, inplace=True)
        return df

    def load_stock(self, code: str) -> pd.DataFrame:
        """
        根据6位股票代码加载单只股票的数据
        例如：fetcher.load_stock('688469')
        """
        # 遍历所有找到的数据文件
        for filepath in self._find_files():
            # 提取该文件名中的股票代码
            extracted_code = self._extract_code(filepath.stem)
            # 如果提取出的代码与要查找的代码一致，读取并返回
            if extracted_code == code:
                return self.read_local_xls(filepath)
        # 遍历完都没找到，抛出异常
        raise FileNotFoundError(f"未找到股票 {code} 的数据文件")

    def load_all_stocks(self) -> Dict[str, pd.DataFrame]:
        """
        加载所有找到的股票数据
        返回一个字典，键是股票代码（字符串），值是对应的 DataFrame
        """
        stocks = {}                              # 用于存放结果的字典
        for filepath in self._find_files():      # 遍历每一个 .xls 文件
            code = self._extract_code(filepath.stem)  # 提取股票代码
            if code is None:                     # 如果提取失败，跳过这个文件
                continue
            stocks[code] = self.read_local_xls(filepath)  # 读取并存入字典
        return stocks

    def load_all_stocks_as_dataframe(self) -> pd.DataFrame:
        """
        将所有股票数据合并成一张大表
        每一行原本是某只股票的一条记录，新增一列 'code' 用来区分是哪只股票
        """
        stocks = self.load_all_stocks()   # 先加载所有股票
        if not stocks:                    # 如果没有数据，返回空 DataFrame
            return pd.DataFrame()
        df_list = []                      # 用于存放每只股票的 DataFrame
        for code, df in stocks.items():
            df = df.copy()                # 复制一份，避免修改原数据
            df['code'] = code             # 新增一列，填入股票代码
            df_list.append(df)
        # 将所有股票的数据纵向拼接成一张大表
        return pd.concat(df_list, ignore_index=True)