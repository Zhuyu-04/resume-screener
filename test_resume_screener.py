import pytest
from resume_screener import score_dimension, calculate_scores
def test_keyword_matching():
    """测试纯关键词匹配：1 个命中 / 2 个关键词 = 50 分"""
    dim = {"name": "技术", "keywords": ["python", "java"]}
    text = "I have python experience"
    score = score_dimension(text, dim)
    assert score == 50.0
def test_regex_matching():
    """测试正则匹配：能识别"5+ years of experience"这类短语"""
    dim = {"name": "经验", "regex_patterns": [r"\d+\+?\s*years?\s*(of)?\s*experience"]}
    text = "5+ years of experience in Python"
    score = score_dimension(text, dim)
    assert score > 0  # 至少命中一次
def test_combined_keywords_and_regex():
    """同时用关键词和正则，得分叠加并归一化到 100"""
    dim = {
        "name": "混合",
        "keywords": ["python"],
        "regex_patterns": [r"\d+\s*years"]
    }
    text = "python, 10 years"
    score = score_dimension(text, dim)
    # 命中 python 一次（1/1），命中 "10 years" 一次（1/1）→ 总命中/总条目 = 2/2 *100 = 100
    assert score == 100.0
def test_empty_text():
    """空文本应得 0 分"""
    dim = {"name": "空", "keywords": ["a"]}
    score = score_dimension("", dim)
    assert score == 0.0
def test_calculate_scores_normalization():
    """测试加权总分计算是否正确：各 0.5 权重，一个满分一个零分 → 总分 50"""
    dimensions = [
        {"name": "a", "weight": 0.5, "keywords": ["python"]},
        {"name": "b", "weight": 0.5, "regex_patterns": [r"java"]},
    ]
    text = "python"
    result = calculate_scores(text, dimensions)
    assert result["total_score"] == 50.0
