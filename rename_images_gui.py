#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
一个用于根据特定规则批量重命名并复制图片文件的GUI应用程序。
本脚本是原始命令行工具的图形化界面版本。

依赖: customtkinter (pip install customtkinter)
"""

import os
import shutil
import re
import argparse
import threading
from typing import List, Dict

import customtkinter as ctk
from tkinter import filedialog

# --- 核心逻辑函数 (从原始脚本移植并稍作修改) ---
# 这些函数现在接受一个 `logger` 对象，用于将信息输出到GUI界面而不是控制台。

RENAMED_FOLDER_NAME = 'renamed'
SUPPORTED_IMAGE_EXTENSIONS = ('.jpg', '.jpeg', '.png', '.gif', '.bmp', '.tiff')

def create_renamed_directory(base_dir, logger):
    """在指定基础目录下创建或确认 'renamed' 文件夹存在"""
    renamed_dir_path = os.path.join(base_dir, RENAMED_FOLDER_NAME)
    os.makedirs(renamed_dir_path, exist_ok=True)
    logger.log(f"创建或确认重命名目标文件夹: {renamed_dir_path}")
    return renamed_dir_path


def rename_and_copy_subfolder_mode(base_work_dir, region_code, date_code, logger):
    """
    模式 1: 遍历工作目录，重命名子文件夹中的图片 (4张一组)，并复制到新的'renamed'文件夹。
    """
    angle_suffixes = ['A', 'B', 'C', 'D']
    renamed_dir_path = create_renamed_directory(base_work_dir, logger)

    for root, dirs, files in os.walk(base_work_dir):
        if os.path.normpath(root) == os.path.normpath(renamed_dir_path):
            continue
        if os.path.normpath(root) == os.path.normpath(base_work_dir):
            continue

        sample_number = os.path.basename(root)
        if not sample_number.isdigit() or len(sample_number) != 4:
            logger.log(f"跳过 '{root}': 文件夹名称 '{sample_number}' 不符合4位数字的样本编号格式。")
            continue

        image_files = sorted([f for f in files if f.lower().endswith(SUPPORTED_IMAGE_EXTENSIONS)])
        if not image_files:
            logger.log(f"警告: 文件夹 '{root}' 中没有找到支持的图片文件，跳过。")
            continue

        logger.log(f"\n正在处理文件夹 (模式1): {root}")
        for i, original_filename in enumerate(image_files):
            if i >= len(angle_suffixes):
                logger.log(f"注意: 文件夹 '{root}' 中的图片数量超出 {len(angle_suffixes)} 张，额外图片将不再分配角度后缀。")
                break

            angle_suffix = angle_suffixes[i]
            file_extension = os.path.splitext(original_filename)[1].lower()
            new_filename = f"{region_code}-{date_code}-{sample_number}-{angle_suffix}{file_extension}"
            original_filepath = os.path.join(root, original_filename)
            new_filepath = os.path.join(renamed_dir_path, new_filename)

            try:
                shutil.copy2(original_filepath, new_filepath)
                logger.log(f"  复制并重命名: '{original_filename}' -> '{new_filename}'")
            except Exception as e:
                logger.log(f"  错误: 复制文件 '{original_filepath}' 到 '{new_filepath}' 失败: {e}")

    logger.log("\n模式 1 (子文件夹模式) 完成。所有符合条件的图片已重命名并复制。")


def rename_and_copy_single_folder_mode(base_work_dir, single_folder_path, region_code, date_code, angle_num, logger):
    """
    模式 2: 处理单个文件夹中的图片，通过识别引导图来自动分组。
    """
    if not os.path.isdir(single_folder_path):
        logger.log(f"错误: 单文件夹模式路径 '{single_folder_path}' 不存在。请检查路径是否正确。")
        return

    renamed_dir_path = create_renamed_directory(base_work_dir, logger)
    all_files = sorted([f for f in os.listdir(single_folder_path) if f.lower().endswith(SUPPORTED_IMAGE_EXTENSIONS)])

    if not all_files:
        logger.log(f"警告: 文件夹 '{single_folder_path}' 中没有找到支持的图片文件。")
        return
        
    pattern_string = r'-([a-zA-Z0-9]{2})\.(' + '|'.join(ext.lstrip('.') for ext in SUPPORTED_IMAGE_EXTENSIONS) + ')$'
    guide_photo_pattern = re.compile(pattern_string, re.IGNORECASE)
    
    guide_photos_info = []
    for i, filename in enumerate(all_files):
        match = guide_photo_pattern.search(filename)
        if match:
            guide_photos_info.append({'filename': filename, 'index': i, 'batch_id': match.group(1)})

    if not guide_photos_info:
        logger.log(f"错误: 在 '{single_folder_path}' 中未能找到任何符合 '...-XX.ext' 格式的引导图片。无法进行分组。")
        return

    batches: List[Dict] = []
    for i, guide_info in enumerate(guide_photos_info):
        start_index = guide_info['index']
        end_index = guide_photos_info[i + 1]['index'] if i + 1 < len(guide_photos_info) else len(all_files)
        batch_files = all_files[start_index:end_index]
        batches.append({'guide_file': guide_info['filename'], 'batch_id': guide_info['batch_id'], 'files_to_rename': batch_files[1:]})

    if len(batches) > 1:
        num_files_in_first_batch = len(batches[0]['files_to_rename'])
        is_consistent = all(len(b['files_to_rename']) == num_files_in_first_batch for b in batches)
        if not is_consistent:
            logger.log("错误: 检测到各组（批次）的图片数量不一致！请检查文件分组是否正确。")
            for b in batches:
                logger.log(f"  - 引导图 '{b['guide_file']}' 后面跟随了 {len(b['files_to_rename'])} 张待处理图片。")
            return
            
    num_files_per_batch = len(batches[0]['files_to_rename'])
    if num_files_per_batch == 0:
        logger.log("警告: 找到了引导图，但它们之间没有任何其他图片可以处理。")
    elif num_files_per_batch % angle_num != 0:
        logger.log(f"错误: 每组待处理的图片数量 ({num_files_per_batch}) 不是指定的角度数量 ({angle_num}) 的整数倍。")
        logger.log("请检查文件数量或调整 --angle_num 参数。")
        return

    logger.log(f"\n正在处理文件夹 (模式2): {single_folder_path}")
    logger.log(f"检测到 {len(batches)} 个批次，每批次待处理 {num_files_per_batch} 张图片，角度参数 angle_num={angle_num}。")

    group_labels = [chr(ord('A') + i) for i in range(angle_num)]
    total_renamed_count = 0
    for i, batch in enumerate(batches):
        batch_id = batch['batch_id']
        logger.log(f"\n  处理批次 {i + 1} (引导图: {batch['guide_file']}, 批次ID: {batch_id})")

        try:
            shutil.copy2(os.path.join(single_folder_path, batch['guide_file']), os.path.join(renamed_dir_path, batch['guide_file']))
            logger.log(f"    复制引导图: '{batch['guide_file']}'")
        except Exception as e:
            logger.log(f"    错误: 复制引导图 '{batch['guide_file']}' 失败: {e}")

        for j, filename_to_rename in enumerate(batch['files_to_rename']):
            group_id = (j // angle_num) + 1
            angle_suffix = group_labels[j % angle_num]
            file_extension = os.path.splitext(filename_to_rename)[1].lower()
            new_filename = f"{region_code}-{date_code}-{batch_id}{group_id:02d}-{angle_suffix}{file_extension}"
            src_path = os.path.join(single_folder_path, filename_to_rename)
            dst_path = os.path.join(renamed_dir_path, new_filename)

            try:
                shutil.copy2(src_path, dst_path)
                logger.log(f"    复制并重命名: '{filename_to_rename}' → '{new_filename}'")
                total_renamed_count += 1
            except Exception as e:
                logger.log(f"    错误: 复制文件 '{src_path}' 到 '{dst_path}' 失败: {e}")

    logger.log(f"\n模式 2 (单文件夹批处理模式) 完成。共复制并重命名了 {total_renamed_count} 张图片。")


# --- GUI 应用部分 ---

class App(ctk.CTk):
    def __init__(self):
        super().__init__()

        # --- 窗口配置 ---
        self.title("图片批量重命名工具")
        self.geometry("800x650")
        ctk.set_appearance_mode("System")  # Options: "System", "Dark", "Light"
        ctk.set_default_color_theme("blue")

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(2, weight=1)

        # --- GUI 组件 ---
        
        # -- 1. 主设置框 --
        self.main_settings_frame = ctk.CTkFrame(self)
        self.main_settings_frame.grid(row=0, column=0, padx=10, pady=10, sticky="ew")
        self.main_settings_frame.grid_columnconfigure(1, weight=1)
        
        # 源目录
        self.source_dir_label = ctk.CTkLabel(self.main_settings_frame, text="源文件夹:")
        self.source_dir_label.grid(row=0, column=0, padx=10, pady=5, sticky="w")
        self.source_dir_entry = ctk.CTkEntry(self.main_settings_frame, placeholder_text="点击“浏览”选择文件夹")
        self.source_dir_entry.grid(row=0, column=1, padx=10, pady=5, sticky="ew")
        self.browse_button = ctk.CTkButton(self.main_settings_frame, text="浏览...", width=80, command=self.browse_source_directory)
        self.browse_button.grid(row=0, column=2, padx=10, pady=5)

        # 地区和日期代码
        self.region_label = ctk.CTkLabel(self.main_settings_frame, text="地区代码 (Region):")
        self.region_label.grid(row=1, column=0, padx=10, pady=5, sticky="w")
        self.region_entry = ctk.CTkEntry(self.main_settings_frame, placeholder_text="例如: HR")
        self.region_entry.grid(row=1, column=1, padx=(10,0), pady=5, sticky="ew")

        self.date_label = ctk.CTkLabel(self.main_settings_frame, text="日期代码 (Date):")
        self.date_label.grid(row=2, column=0, padx=10, pady=5, sticky="w")
        self.date_entry = ctk.CTkEntry(self.main_settings_frame, placeholder_text="例如: 250701")
        self.date_entry.grid(row=2, column=1, padx=(10,0), pady=5, sticky="ew")
        
        # -- 2. 模式选择框 --
        self.mode_frame = ctk.CTkFrame(self)
        self.mode_frame.grid(row=1, column=0, padx=10, pady=(0, 10), sticky="ew")
        self.mode_frame.grid_columnconfigure((1,2), weight=1)

        self.mode_label = ctk.CTkLabel(self.mode_frame, text="处理模式:")
        self.mode_label.grid(row=0, column=0, padx=10, pady=10, sticky="w")

        self.mode_var = ctk.StringVar(value="subfolder")
        self.radio_subfolder = ctk.CTkRadioButton(self.mode_frame, text="子文件夹模式 (Subfolder)", variable=self.mode_var, value="subfolder", command=self.update_mode_options)
        self.radio_subfolder.grid(row=0, column=1, padx=10, pady=10, sticky="w")
        
        self.radio_single_folder = ctk.CTkRadioButton(self.mode_frame, text="单文件夹模式 (Single Folder)", variable=self.mode_var, value="single_folder", command=self.update_mode_options)
        self.radio_single_folder.grid(row=0, column=2, padx=10, pady=10, sticky="w")

        # -- 单文件夹模式的特定选项 (默认隐藏) --
        self.single_folder_options_frame = ctk.CTkFrame(self.mode_frame, fg_color="transparent")
        self.single_folder_options_frame.grid(row=1, column=0, columnspan=3, padx=5, pady=5, sticky="ew")
        self.single_folder_options_frame.grid_columnconfigure(1, weight=1)
        
        self.image_folder_label = ctk.CTkLabel(self.single_folder_options_frame, text="图片子文件夹名:")
        self.image_folder_label.grid(row=0, column=0, padx=10, pady=5, sticky="w")
        self.image_folder_entry = ctk.CTkEntry(self.single_folder_options_frame)
        self.image_folder_entry.insert(0, "phone_image")
        self.image_folder_entry.grid(row=0, column=1, padx=10, pady=5, sticky="ew")
        
        self.angle_num_label = ctk.CTkLabel(self.single_folder_options_frame, text="每组角度数量:")
        self.angle_num_label.grid(row=1, column=0, padx=10, pady=5, sticky="w")
        self.angle_num_entry = ctk.CTkEntry(self.single_folder_options_frame)
        self.angle_num_entry.insert(0, "4")
        self.angle_num_entry.grid(row=1, column=1, padx=10, pady=5, sticky="w")

        # -- 3. 日志输出框 --
        self.log_textbox = ctk.CTkTextbox(self, state="disabled", wrap="word")
        self.log_textbox.grid(row=2, column=0, padx=10, pady=(0, 10), sticky="nsew")

        # -- 4. 控制按钮 --
        self.control_frame = ctk.CTkFrame(self)
        self.control_frame.grid(row=3, column=0, padx=10, pady=10, sticky="ew")
        self.control_frame.grid_columnconfigure(0, weight=1)

        self.start_button = ctk.CTkButton(self.control_frame, text="开始重命名", command=self.start_processing_thread)
        self.start_button.grid(row=0, column=0, padx=10, pady=10, sticky="ew")
        
        # --- 初始化状态 ---
        self.update_mode_options()

    def log(self, message):
        """线程安全地向日志框中添加消息"""
        self.log_textbox.configure(state="normal")
        self.log_textbox.insert("end", message + "\n")
        self.log_textbox.configure(state="disabled")
        self.log_textbox.see("end")

    def browse_source_directory(self):
        """打开文件夹选择对话框"""
        dir_path = filedialog.askdirectory(title="请选择包含图片的源文件夹")
        if dir_path:
            self.source_dir_entry.delete(0, "end")
            self.source_dir_entry.insert(0, dir_path)
            
            # 自动填充地区和日期
            try:
                folder_name = os.path.basename(dir_path)
                match = re.match(r'([A-Za-z]{2})(\d{6})', folder_name)
                if match:
                    region, date = match.groups()
                    self.region_entry.delete(0, "end")
                    self.region_entry.insert(0, region.upper())
                    self.date_entry.delete(0, "end")
                    self.date_entry.insert(0, date)
            except Exception:
                pass # 自动填充失败也无妨

    def update_mode_options(self):
        """根据选择的模式显示或隐藏特定选项"""
        if self.mode_var.get() == "single_folder":
            self.single_folder_options_frame.grid(row=1, column=0, columnspan=3, padx=5, pady=5, sticky="ew")
        else:
            self.single_folder_options_frame.grid_forget()

    def start_processing_thread(self):
        """启动一个新的线程来处理文件，防止GUI冻结"""
        self.start_button.configure(state="disabled", text="正在处理...")
        
        # 清空日志
        self.log_textbox.configure(state="normal")
        self.log_textbox.delete("1.0", "end")
        self.log_textbox.configure(state="disabled")

        processing_thread = threading.Thread(target=self.run_rename_logic)
        processing_thread.daemon = True
        processing_thread.start()

    def run_rename_logic(self):
        """执行核心重命名逻辑"""
        try:
            # --- 1. 从GUI获取所有参数 ---
            base_work_dir = self.source_dir_entry.get()
            region_code = self.region_entry.get().upper()
            date_code = self.date_entry.get()
            mode = self.mode_var.get()

            # --- 2. 输入验证 ---
            if not base_work_dir or not os.path.isdir(base_work_dir):
                self.log("❌ 错误: 请选择一个有效的源文件夹。")
                return
            if not re.match(r'^[A-Za-z]{2}$', region_code):
                self.log("❌ 错误: 地区代码必须是2个英文字母。")
                return
            if not re.match(r'^\d{6}$', date_code):
                self.log("❌ 错误: 日期代码必须是6位数字。")
                return

            self.log(f"--- 操作开始 ---\n源文件夹: {base_work_dir}\n模式: {mode}")

            # --- 3. 根据模式调用相应函数 ---
            if mode == 'subfolder':
                rename_and_copy_subfolder_mode(base_work_dir, region_code, date_code, self)
            
            elif mode == 'single_folder':
                image_folder = self.image_folder_entry.get()
                try:
                    angle_num = int(self.angle_num_entry.get())
                except ValueError:
                    self.log("❌ 错误: '每组角度数量' 必须是一个整数。")
                    return
                
                if not image_folder:
                    self.log("❌ 错误: 在 'single_folder' 模式下，必须指定图片子文件夹名。")
                    return
                
                single_folder_path = os.path.join(base_work_dir, image_folder)
                rename_and_copy_single_folder_mode(base_work_dir, single_folder_path, region_code, date_code, angle_num, self)
            
            self.log("\n✅ 操作执行完毕。")

        except Exception as e:
            self.log(f"\n❌ 发生意外错误: {e}")
        finally:
            # --- 4. 恢复按钮状态 ---
            self.start_button.configure(state="normal", text="开始重命名")


if __name__ == "__main__":
    app = App()
    app.mainloop()