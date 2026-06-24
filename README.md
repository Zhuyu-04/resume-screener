# 自动化简历筛选器
> 命令行工具，批量解析 PDF 简历，通过 YAML 配置评分维度，输出 HTML 报告 + JSON 数据。
## ✨ 特色
- 📄 批量处理 PDF 简历，支持 ≥10 份
- ⚙️ 评分维度完全由 `config.yaml` 控制（维度、权重、关键词/正则）
- 📊 输出可视化 HTML 报告 + 结构化 JSON
- 🛡️ 健壮的异常处理：PDF 解析失败、字段缺失不崩溃
- 🤖 完整 AI 协作记录见 [ai-log.md](ai-log.md)
## 🚀 快速开始
```bash
# 1. 安装依赖
pip install -r requirements.txt
# 2. 准备简历 PDF 文件夹（如 sample_resumes/）
# 3. 修改 config.yaml 以匹配你的评分标准
# 4. 运行
python resume_screener.py --resumes-dir ./sample_resumes --config config.yaml --output-dir ./output

