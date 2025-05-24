#!/usr/bin/env python
# -*- coding:utf-8 -*-

__author__ = 'Taisue'
__copyright__ = 'Copyright © 2025/05/23, Banyu Tech Ltd.'

import os, yaml
from typing import Any, Dict, List, Literal, Optional, Union
from utils.ollama import Ollama
from utils.classes import FailResult, PassResult, ValidationResult, ErrorSpan

current_file_path = os.path.abspath(__file__)
current_directory = os.path.dirname(current_file_path)

class DetectToxic():
    def __init__(self, model: str = "guard", base_url: str = "http://localhost:11434", api_key: Optional[str] = None):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model = model
        self.llm = Ollama(base_url, api_key)

    def load_test_data(self, json_file_path):
        """从JSON文件加载训练数据"""
        with open(json_file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return data

    def load_prompt_template(self, yaml_path="template.yaml"):
        """
        从YAML文件加载prompt模板
        :param yaml_path: YAML文件路径
        :return: 模板字符串
        """
        if not os.path.exists(yaml_path):
            print(f"Warning: Template file '{yaml_path}' not found.")
            return ""

        with open(yaml_path, 'r', encoding='utf-8') as file:
            try:
                data = yaml.safe_load(file)
                return data.get("check_prompt", "")
            except yaml.YAMLError as e:
                print(f"Error parsing YAML: {e}")
                return ""

    def validate(self, query=None, prompt=None):
        """
        发送消息到OLLAMA服务器并获取响应
        :param prompt: 直接提供的prompt (可选)
        :param query: 用于模板的查询内容 (可选)
        :return: OLLAMA模型的回复
        """
        if query is not None:
            template = self.load_prompt_template(os.path.join(current_directory, "template.yaml"))
            final_prompt = template.replace("{query}", query)
        else:
            final_prompt = prompt if prompt is not None else ""

        options = {
            "max_tokens": 10,  # 根据需要调整生成的token数量
            "stream": False
        }
        response = self.llm.generate(self.model, final_prompt, options=options)
        results =  response.json().get("response", "")

        if "未通过" in results:
            return FailResult(
                error_message=(response.json().get("response", "")),
                fix_value="",
            )
        else:
            return PassResult()





