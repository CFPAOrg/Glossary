import csv
import json
import os

# 获取当前文件所在目录
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))

en_relative_path = '../assets/en_us.json'
zh_relative_path = '../assets/zh_cn.json'
depercated_relative_path = '../assets/deprecated.json'
tsv_relative_path = '../原版语言文件1.21.4.tsv'

def get_absolute_path(relative_path):
    """
    将相对路径转换为绝对路径。

    Args:
        relative_path (str): 要转换的相对路径。

    Returns:
        str: 规范化的绝对路径。
    """
    return os.path.normpath(os.path.join(CURRENT_DIR, relative_path))

def load_json(relative_path):
    with open(get_absolute_path(relative_path), 'r', encoding='utf-8') as f:
        return json.load(f)

en_data = load_json(en_relative_path)
zh_data = load_json(zh_relative_path)
deprecated_data = load_json(depercated_relative_path)

removed_keys = deprecated_data["removed"]
renamed_items = deprecated_data["renamed"]

tsv_data = [["键", "英文", "中文", "已移除", "改名前"]]

failed_keys = {}

for en_key in en_data:
    en_value: str = repr(en_data[en_key])[1:-1] # 保留 \n 的字面形式
    zh_value: str = None
    is_removed: str = "否"
    renamed_from: str = None
    if en_key in renamed_items:
        renamed_from = renamed_items[en_key]
    if en_key in removed_keys:
        is_removed = "是"
    if en_key in zh_data:
        zh_value = repr(zh_data[en_key])[1:-1]
        tsv_data.append([en_key, en_value, zh_value, is_removed, renamed_from])
    else:
        failed_keys[en_key] = "未在中文文件中找到对应的键。"

with open(get_absolute_path(tsv_relative_path), 'w', newline='', encoding='utf-8') as f:
    writer = csv.writer(f, delimiter='\t', quoting=csv.QUOTE_STRINGS)
    writer.writerows(tsv_data)






