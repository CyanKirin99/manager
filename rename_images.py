#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
一个用于根据特定规则批量重命名并复制图片文件的脚本。

该脚本支持两种操作模式：
1. 'subfolder': 处理分散在多个子文件夹中的图片，每个子文件夹代表一个样本。
2. 'single_folder': 处理存放在单个文件夹中的大量图片。该模式通过识别特定格式的“引导图”进行分组。

所有必需的参数都通过命令行传递。

命令行使用示例:

# 示例 1: 使用 'subfolder' 模式
# - 地区代码 'HR', 日期 '250701'
# - 脚本将处理 './HR250701' 目录下的子文件夹
python rename_images.py --region HR --date 250701 --mode subfolder

# 示例 2: 使用 'single_folder' 模式（新版分组逻辑）
# - 假设 'SY250623/phone_image' 目录下有 '...-01.jpg', 'img1.jpg', 'img2.jpg'..., '...-02.jpg', ...
# - 角度数量为4 (A, B, C, D)
python rename_images.py --region SY --date 250623 --mode single_folder --angle_num 4

# 示例 3: 使用 'single_folder' 模式并指定角度数量为3 (A, B, C)
python rename_images.py --region SY --date 250623 --mode single_folder --angle_num 3

# 示例 4: 指定非标准的源目录和图片子文件夹
python rename_images.py --region SY --date 250623 --mode single_folder --angle_num 4 --source_dir /path/to/data --image_folder my_images
"""

import os
import shutil
import re
import argparse
from typing import List, Dict

# --- 全局常量配置 ---
RENAMED_FOLDER_NAME = 'renamed'
SUPPORTED_IMAGE_EXTENSIONS = ('.jpg', '.jpeg', '.png', '.gif', '.bmp', '.tiff')  # 支持的图片格式


def create_renamed_directory(base_dir):
    """在指定基础目录下创建或确认 'renamed' 文件夹存在"""
    renamed_dir_path = os.path.join(base_dir, RENAMED_FOLDER_NAME)
    os.makedirs(renamed_dir_path, exist_ok=True)
    print(f"创建或确认重命名目标文件夹: {renamed_dir_path}")
    return renamed_dir_path


def rename_and_copy_subfolder_mode(base_work_dir, region_code, date_code):
    """
    模式 1: 遍历工作目录，重命名子文件夹中的图片 (4张一组)，并复制到新的'renamed'文件夹。
    文件名格式: REGION-DATE-SAMPLEID-ANGLE.EXT
    """
    angle_suffixes = ['A', 'B', 'C', 'D']
    renamed_dir_path = create_renamed_directory(base_work_dir)

    for root, dirs, files in os.walk(base_work_dir):
        if os.path.normpath(root) == os.path.normpath(renamed_dir_path):
            continue
        if os.path.normpath(root) == os.path.normpath(base_work_dir):
            continue

        sample_number = os.path.basename(root)
        if not sample_number.isdigit() or len(sample_number) != 4:
            print(f"跳过 '{root}': 文件夹名称 '{sample_number}' 不符合4位数字的样本编号格式。")
            continue

        image_files = sorted([f for f in files if f.lower().endswith(SUPPORTED_IMAGE_EXTENSIONS)])
        if not image_files:
            print(f"警告: 文件夹 '{root}' 中没有找到支持的图片文件，跳过。")
            continue

        print(f"\n正在处理文件夹 (模式1): {root}")
        for i, original_filename in enumerate(image_files):
            if i >= len(angle_suffixes):
                print(f"注意: 文件夹 '{root}' 中的图片数量超出 {len(angle_suffixes)} 张，额外图片将不再分配角度后缀。")
                break

            angle_suffix = angle_suffixes[i]
            file_extension = os.path.splitext(original_filename)[1].lower()
            new_filename = f"{region_code}-{date_code}-{sample_number}-{angle_suffix}{file_extension}"
            original_filepath = os.path.join(root, original_filename)
            new_filepath = os.path.join(renamed_dir_path, new_filename)

            try:
                shutil.copy2(original_filepath, new_filepath)
                print(f"  复制并重命名: '{original_filename}' -> '{new_filename}'")
            except Exception as e:
                print(f"  错误: 复制文件 '{original_filepath}' 到 '{new_filepath}' 失败: {e}")

    print("\n模式 1 (子文件夹模式) 完成。所有符合条件的图片已重命名并复制。")


def rename_and_copy_single_folder_mode(base_work_dir, single_folder_path, region_code, date_code, angle_num):
    """
    模式 2: (已重构) 处理单个文件夹中的图片。
    通过识别以'-XX'结尾的“手势/引导图”来自动分组。
    文件名格式: REGION-DATE-BATCHIDGROUPID-ANGLE.EXT
    """
    if not os.path.isdir(single_folder_path):
        print(f"错误: 单文件夹模式路径 '{single_folder_path}' 不存在。请检查路径是否正确。")
        return

    renamed_dir_path = create_renamed_directory(base_work_dir)
    all_files = sorted([f for f in os.listdir(single_folder_path) if f.lower().endswith(SUPPORTED_IMAGE_EXTENSIONS)])

    if not all_files:
        print(f"警告: 文件夹 '{single_folder_path}' 中没有找到支持的图片文件。")
        return

    # --- 新的动态分组逻辑 ---
    # 1. 识别引导图 (文件名以 '-XX' 结尾, XX为两位字母或数字)
    #    这个正则表达式能匹配如 '...-01.jpg', '...-AB.png' 等格式的文件
    
    # --- FIX START: 应用正则表达式错误修复 ---
    # 移除了字符串中的 (?i)，并将 re.IGNORECASE 作为标志传递
    pattern_string = r'-([a-zA-Z0-9]{2})\.(' + '|'.join(ext.lstrip('.') for ext in SUPPORTED_IMAGE_EXTENSIONS) + ')$'
    guide_photo_pattern = re.compile(pattern_string, re.IGNORECASE)
    # --- FIX END ---
    
    guide_photos_info = []
    for i, filename in enumerate(all_files):
        match = guide_photo_pattern.search(filename)
        if match:
            guide_photos_info.append({
                'filename': filename,
                'index': i,
                'batch_id': match.group(1) # 提取 '01', 'AB' 等作为批次号
            })

    if not guide_photos_info:
        print(f"错误: 在 '{single_folder_path}' 中未能找到任何符合 '...-XX.ext' 格式的引导图片。无法进行分组。")
        return

    # 2. 根据引导图构建批次 (batches)
    batches: List[Dict] = []
    for i, guide_info in enumerate(guide_photos_info):
        start_index = guide_info['index']
        # 下一个引导图的索引，如果是最后一个，则到文件列表末尾
        end_index = guide_photos_info[i + 1]['index'] if i + 1 < len(guide_photos_info) else len(all_files)
        
        batch_files = all_files[start_index:end_index]
        batches.append({
            'guide_file': guide_info['filename'],
            'batch_id': guide_info['batch_id'],
            'files_to_rename': batch_files[1:] # 引导图之后的所有文件
        })

    # 3. 检查所有批次中待重命名文件的数量是否一致
    if len(batches) > 1:
        num_files_in_first_batch = len(batches[0]['files_to_rename'])
        is_consistent = all(len(b['files_to_rename']) == num_files_in_first_batch for b in batches)
        if not is_consistent:
            print("错误: 检测到各组（批次）的图片数量不一致！请检查文件分组是否正确。")
            for b in batches:
                print(f"  - 引导图 '{b['guide_file']}' 后面跟随了 {len(b['files_to_rename'])} 张待处理图片。")
            return
            
    num_files_per_batch = len(batches[0]['files_to_rename'])
    if num_files_per_batch == 0:
        print("警告: 找到了引导图，但它们之间没有任何其他图片可以处理。")
    elif num_files_per_batch % angle_num != 0:
        print(f"错误: 每组待处理的图片数量 ({num_files_per_batch}) 不是指定的角度数量 ({angle_num}) 的整数倍。")
        print("请检查文件数量或调整 --angle_num 参数。")
        return

    # --- 开始处理 ---
    print(f"\n正在处理文件夹 (模式2): {single_folder_path}")
    print(f"检测到 {len(batches)} 个批次，每批次待处理 {num_files_per_batch} 张图片，角度参数 angle_num={angle_num}。")

    # 根据 angle_num 动态生成角度标签，例如 angle_num=3 -> ['A', 'B', 'C']
    group_labels = [chr(ord('A') + i) for i in range(angle_num)]

    total_renamed_count = 0
    for i, batch in enumerate(batches):
        batch_id = batch['batch_id']
        print(f"\n  处理批次 {i + 1} (引导图: {batch['guide_file']}, 批次ID: {batch_id})")

        # 复制引导图 (保持原名)
        try:
            shutil.copy2(os.path.join(single_folder_path, batch['guide_file']), os.path.join(renamed_dir_path, batch['guide_file']))
            print(f"    复制引导图: '{batch['guide_file']}'")
        except Exception as e:
            print(f"    错误: 复制引导图 '{batch['guide_file']}' 失败: {e}")

        # 重命名并复制批次中的其他图片
        for j, filename_to_rename in enumerate(batch['files_to_rename']):
            # (j // angle_num) + 1 计算出当前是第几小组 (1, 2, 3...)
            # j % angle_num  计算出在小组内的角度索引 (0, 1, 2...)
            group_id = (j // angle_num) + 1
            angle_suffix = group_labels[j % angle_num]
            file_extension = os.path.splitext(filename_to_rename)[1].lower()

            new_filename = f"{region_code}-{date_code}-{batch_id}{group_id:02d}-{angle_suffix}{file_extension}"
            
            src_path = os.path.join(single_folder_path, filename_to_rename)
            dst_path = os.path.join(renamed_dir_path, new_filename)

            try:
                shutil.copy2(src_path, dst_path)
                print(f"    复制并重命名: '{filename_to_rename}' → '{new_filename}'")
                total_renamed_count += 1
            except Exception as e:
                print(f"    错误: 复制文件 '{src_path}' 到 '{dst_path}' 失败: {e}")

    # 检查是否有任何文件在最后一个引导图之后被遗漏
    if guide_photos_info:
        last_guide_photo_index = guide_photos_info[-1]['index']
        # 计算最后一个批次结束的位置
        last_processed_index = last_guide_photo_index + len(batches[-1]['files_to_rename'])
        if last_processed_index < len(all_files) -1:
            remaining_files = all_files[last_processed_index + 1:]
            if remaining_files:
                print(f"\n警告: 在最后一个批次处理完毕后，仍有 {len(remaining_files)} 个文件未被处理。")
                print("未处理的文件: " + ", ".join(remaining_files))

    print(f"\n模式 2 (单文件夹批处理模式) 完成。共复制并重命名了 {total_renamed_count} 张图片。")


def main():
    """主函数，用于解析命令行参数并执行相应操作"""
    parser = argparse.ArgumentParser(
        description="一个用于根据特定规则批量重命名并复制图片文件的脚本。",
        formatter_class=argparse.RawTextHelpFormatter  # 保持帮助信息中的换行
    )

    # --- 定义命令行参数 ---
    parser.add_argument(
        '--region',
        type=str,
        required=True,
        help="地区代码 (2个字符, 例如: 'HR', 'SY')"
    )
    parser.add_argument(
        '--date',
        type=str,
        required=True,
        help="日期代码 (6个字符, 例如: '250701')"
    )
    parser.add_argument(
        '--mode',
        type=str,
        required=True,
        choices=['subfolder', 'single_folder'],
        help="选择重命名模式:\n"
             "'subfolder': 适用于图片在多个子文件夹中 (每文件夹4张图) 的情况。\n"
             "'single_folder': (新) 适用于所有图片在一个文件夹中，通过识别'...-XX.jpg'格式的引导图来自动分组。"
    )
    parser.add_argument(
        '--source_dir',
        type=str,
        default=None,
        help="[可选] 指定要处理的基础源目录。\n"
             "如果未提供，将默认使用 './{REGION}{DATE}' 格式的路径。"
    )
    parser.add_argument(
        '--image_folder',
        type=str,
        default='phone_image',
        help="[可选] 在 'single_folder' 模式下，包含所有图片的子文件夹名称。\n"
             "默认为 'phone_image'。"
    )
    # --- 新增参数 ---
    parser.add_argument(
        '--angle_num',
        type=int,
        default=4,
        help="[仅 'single_folder' 模式] 指定每个小组包含的角度数量。\n"
             "例如: 3 表示每组图片命名为 A, B, C; 4 表示 A, B, C, D。\n"
             "默认为 4。"
    )

    args = parser.parse_args()

    # --- 根据参数设置变量 ---
    region_code = args.region.upper()
    date_code = args.date
    renaming_mode = args.mode

    # 确定基础工作目录
    if args.source_dir:
        base_work_directory = args.source_dir
        print(f"使用用户指定的基础目录: {base_work_directory}")
    else:
        base_work_directory = f'./{region_code}{date_code}'
        print(f"使用默认基础目录: {base_work_directory}")

    # 检查基础目录是否存在
    if not os.path.isdir(base_work_directory):
        print(f"错误: 基础工作目录 '{base_work_directory}' 不存在。请检查路径是否正确。")
        return  # 提前退出

    # --- 根据选择的模式执行相应的函数 ---
    if renaming_mode == 'subfolder':
        rename_and_copy_subfolder_mode(base_work_directory, region_code, date_code)
    elif renaming_mode == 'single_folder':
        # 确定 single_folder 模式下的图片路径
        single_folder_path = os.path.join(base_work_directory, args.image_folder)
        rename_and_copy_single_folder_mode(base_work_directory, single_folder_path, region_code, date_code, args.angle_num)

    print("\n脚本执行完毕。")


if __name__ == "__main__":
    main()