#!/usr/bin/env python3
"""
自动化简历筛选器 —— 批量解析 PDF，根据可配置维度打分，输出 HTML + JSON。
用法: python resume_screener.py --resumes-dir ./resumes --config config.yaml --output-dir ./output
"""
import argparse
import json
import logging
import sys
from pathlib import Path
from typing import Dict, List, Optional, Any
import pdfplumber
import yaml
from jinja2 import Template
# -------------------- 日志配置 --------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger("resume_screener")
# -------------------- 配置加载 --------------------
def load_config(config_path: str) -> Dict[str, Any]:
    """加载 YAML 配置文件，返回包含 dimensions 的字典。"""
    with open(config_path, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)
    if not config or "dimensions" not in config:
        raise ValueError("配置文件必须包含 'dimensions' 字段")
    return config
# -------------------- PDF 文本提取 --------------------
def extract_text_from_pdf(pdf_path: str) -> str:
    """
    使用 pdfplumber 提取 PDF 文本。
    遇到非 PDF 或损坏文件会抛出异常，由调用方处理。
    """
    text_parts = []
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            page_text = page.extract_text()
            if page_text:
                text_parts.append(page_text)
    return "\n".join(text_parts)
# -------------------- 评分逻辑（可配置维度）-------------------
def score_dimension(text: str, dimension: Dict[str, Any]) -> float:
    """
    根据单个维度的配置对文本打分 (0~100)：
    - keywords: 统计每个关键词的出现次数，总点击数 / 关键词数量 * 100，上限 100
    - regex_patterns: 统计每个正则匹配次数，同上归一化
    - 二者可叠加（取最高分或自定义公式，这里简单叠加并 clip 到 100）
    """
    total_hits = 0
    total_items = 0
    # 关键词匹配（忽略大小写）
    keywords = dimension.get("keywords", [])
    if keywords:
        text_lower = text.lower()
        for kw in keywords:
            count = text_lower.count(kw.lower())
            total_hits += count
        total_items += len(keywords)
    # 正则匹配
    import re
    regex_patterns = dimension.get("regex_patterns", [])
    if regex_patterns:
        for pat_str in regex_patterns:
            try:
                matches = re.findall(pat_str, text, re.IGNORECASE)
                total_hits += len(matches)
            except re.error:
                logger.warning("无效的正则表达式: %s", pat_str)
        total_items += len(regex_patterns)
    if total_items == 0:
        return 0.0
    # 归一化，最多给 100 分（多次命中不代表翻倍）
    score = min(100.0, (total_hits / total_items) * 100)
    return round(score, 2)
def calculate_scores(
    text: str, dimensions: List[Dict[str, Any]]
) -> Dict[str, Any]:
    """
    遍历所有维度计算得分，返回包含各维度得分、加权总分、归一化总分的字典。
    """
    # 校验权重和是否为 1
    weight_sum = sum(float(d.get("weight", 0)) for d in dimensions)
    if abs(weight_sum - 1.0) > 0.001:
        logger.warning("维度权重之和为 %.3f，建议调整为 1.0，否则总分可能失真", weight_sum)
    dim_results = []
    raw_total = 0.0
    for dim in dimensions:
        name = dim.get("name", "Unnamed")
        weight = float(dim.get("weight", 0))
        raw_score = score_dimension(text, dim)
        weighted = raw_score * weight
        dim_results.append(
            {
                "name": name,
                "weight": weight,
                "raw_score": raw_score,
                "weighted_score": round(weighted, 2),
            }
        )
        raw_total += weighted
    # 归一化到 0-100（确保总分最高 100）
    total_weight = sum(float(d.get("weight", 0)) for d in dimensions)
    normalized_total = round((raw_total / total_weight), 2) if total_weight > 0 else 0.0
    return {
        "dimensions": dim_results,
        "total_score": normalized_total,
    }
# -------------------- 单份简历处理 --------------------
def process_resume(
    pdf_path: str,
    dimensions: List[Dict[str, Any]],
    identifier: str,
) -> Dict[str, Any]:
    """处理单份简历，返回包含得分和状态的字典。"""
    result: Dict[str, Any] = {
        "file": pdf_path,
        "identifier": identifier,
        "status": "success",
        "error": None,
        "summary": {},
    }
    try:
        text = extract_text_from_pdf(pdf_path)
        if not text.strip():
            raise ValueError("提取出的文本为空")
        scores = calculate_scores(text, dimensions)
        result["summary"] = scores
    except Exception as e:
        logger.error("处理失败 %s: %s", pdf_path, str(e))
        result["status"] = "error"
        result["error"] = str(e)
        result["summary"] = {"dimensions": [], "total_score": 0}
    return result
# -------------------- HTML 报告生成 --------------------
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <title>简历筛选报告</title>
    <style>
        body { font-family: Arial, sans-serif; margin: 40px; }
        table { border-collapse: collapse; width: 100%; margin-top: 20px; }
        th, td { border: 1px solid #ddd; padding: 8px; text-align: left; }
        th { background-color: #f2f2f2; }
        tr:nth-child(even) { background-color: #f9f9f9; }
        .error { color: red; }
        .success { color: green; }
        .score-bar { background: #e0e0e0; border-radius: 5px; height: 20px; width: 150px; display: inline-block; margin-left: 5px; }
        .score-fill { background: #4caf50; height: 100%; border-radius: 5px; }
    </style>
</head>
<body>
    <h1>简历筛选报告</h1>
    <p>总简历数：{{ total }}，成功：{{ success_count }}，失败：{{ error_count }}</p>
    <table>
        <tr>
            <th>#</th>
            <th>简历文件</th>
            <th>状态</th>
            <th>总分</th>
            {% for dim in dimensions %}
            <th>{{ dim.name }} ({{ (dim.weight*100)|int }}%)</th>
            {% endfor %}
            <th>错误信息</th>
        </tr>
        {% for item in sorted_results %}
        <tr>
            <td>{{ loop.index }}</td>
            <td>{{ item.identifier }}</td>
            <td class="{{ item.status }}">{{ item.status }}</td>
            <td>
                {{ item.summary.total_score }}
                <div class="score-bar"><div class="score-fill" style="width: {{ item.summary.total_score }}%;"></div></div>
            </td>
            {% for dim in item.summary.dimensions %}
            <td>{{ dim.raw_score }}</td>
            {% endfor %}
            <td>{{ item.error or '' }}</td>
        </tr>
        {% endfor %}
    </table>
</body>
</html>
"""
def generate_report(
    results: List[Dict[str, Any]],
    dimensions: List[Dict[str, Any]],
    output_dir: str,
) -> None:
    """生成 HTML 报告和 JSON 数据。"""
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    # JSON 输出
    json_path = output_path / "results.json"
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    logger.info("JSON 结果已保存至 %s", json_path)
    # 按总分降序排序
    sorted_results = sorted(
        results, key=lambda x: x["summary"]["total_score"], reverse=True
    )
    # HTML 报告
    template = Template(HTML_TEMPLATE)
    html = template.render(
        total=len(results),
        success_count=sum(1 for r in results if r["status"] == "success"),
        error_count=sum(1 for r in results if r["status"] != "success"),
        dimensions=dimensions,
        sorted_results=sorted_results,
    )
    html_path = output_path / "report.html"
    with open(html_path, "w", encoding="utf-8") as f:
        f.write(html)
    logger.info("HTML 报告已保存至 %s", html_path)
# -------------------- 主入口 --------------------
def main():
    parser = argparse.ArgumentParser(description="自动化简历筛选器")
    parser.add_argument(
        "--resumes-dir",
        required=True,
        help="包含 PDF 简历的文件夹路径",
    )
    parser.add_argument(
        "--config",
        default="config.yaml",
        help="评分维度配置文件（YAML），默认为 config.yaml",
    )
    parser.add_argument(
        "--output-dir",
        default="./output",
        help="输出目录，默认为 ./output",
    )
    args = parser.parse_args()
    # 加载配置
    try:
        config = load_config(args.config)
    except Exception as e:
        logger.error("加载配置失败: %s", e)
        sys.exit(1)
    dimensions = config["dimensions"]
    # 扫描 PDF 文件
    resumes_dir = Path(args.resumes_dir)
    pdf_files = sorted(resumes_dir.glob("*.pdf")) + sorted(resumes_dir.glob("*.PDF"))
    if not pdf_files:
        logger.warning("未在 %s 下找到 PDF 文件", resumes_dir)
        sys.exit(0)
    logger.info("找到 %d 份简历", len(pdf_files))
    # 批量处理
    results = []
    for idx, pdf_file in enumerate(pdf_files, start=1):
        logger.info("正在处理 [%d/%d] %s", idx, len(pdf_files), pdf_file.name)
        res = process_resume(
            str(pdf_file),
            dimensions,
            pdf_file.name,
        )
        results.append(res)
    # 输出报告
    generate_report(results, dimensions, args.output_dir)
if __name__ == "__main__":
    main()
