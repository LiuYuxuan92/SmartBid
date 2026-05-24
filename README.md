# SmartBid 招投标智能辅助系统

> Intelligent Bidding Assistant System — MVP / Proof of Concept

一个面向建筑工程企业的招投标全流程辅助系统，覆盖从信息采集到报价决策的核心链路。

An end-to-end intelligent bidding assistant for construction/engineering companies, covering the full pipeline from information crawling to price decision-making.

---

## 🏗️ 系统架构 / Architecture

```
┌─────────────┐    ┌─────────────┐    ┌─────────────┐    ┌─────────────┐
│  Crawler    │───▶│ DXF Parser  │───▶│RAG Generator│───▶│ Monte Carlo │
│  爬虫模块   │    │ 几何计算模块 │    │ 技术标生成  │    │ 报价模拟    │
└─────────────┘    └─────────────┘    └─────────────┘    └─────────────┘
```

## 📦 四大核心模块 / Core Modules

### 1. 分布式爬虫 / Distributed Crawler
- 抓取政府/企业公开招标平台信息
- 反爬对抗：代理IP轮换、滑块验证码自动化（Playwright）、动态Token逆向
- Scrapes public government/enterprise bidding platforms
- Anti-crawl: proxy rotation, slider CAPTCHA automation, dynamic token reverse-engineering

### 2. DXF 几何计算 / DXF Geometry Parser
- 解析文本格式 DXF（AutoCAD）图纸
- 提取多边形顶点、计算闭合面积（Shoelace算法）与延米
- 自动映射标准工程定额数据库
- Parses text-format DXF files, extracts polygon vertices, computes areas and linear meters
- Maps results to standard construction cost quota databases

### 3. RAG 技术标生成 / RAG-based Bid Generation
- ChromaDB 本地向量数据库存储历史标书嵌入
- 检索增强生成（RAG）：基于项目简介检索相关历史内容
- LLM API 生成技术标初稿 + python-docx 自动排版输出 Word 文件
- Local vector DB (ChromaDB) for historical bid document embeddings
- RAG retrieval + LLM generation + automated Word formatting

### 4. 蒙特卡洛报价模拟 / Monte Carlo Price Simulation
- 基于历史竞标数据建模竞争对手报价行为（正态/对数正态分布拟合）
- 10,000+ 次蒙特卡洛模拟，输出最优报价区间与中标概率
- Models competitor pricing behavior from historical data
- 10,000+ Monte Carlo iterations, outputs optimal bid price range with win probability

---

## 🚀 快速开始 / Quick Start

### 环境要求 / Requirements
- Python 3.12+
- Windows 10/11
- 16GB+ RAM (recommended)

### 安装 / Installation

```bash
git clone https://github.com/LiuYuxuan92/SmartBid.git
cd SmartBid

# 创建虚拟环境 (可选)
python -m venv venv
venv\Scripts\activate

# 安装依赖
pip install -r requirements.txt

# 安装 Playwright 浏览器
playwright install chromium
```

### 配置 / Configuration

```bash
# 复制配置模板
copy config.example.yaml config.yaml

# 编辑 config.yaml，填入：
# - LLM API Key (OpenAI/其他兼容API)
# - 代理IP列表（可选）
# - 目标平台URL
```

### 运行 / Usage

```bash
# 完整 pipeline
python main.py <项目ID> --dxf-paths path/to/file.dxf --iterations 10000

# 指定平台
python main.py my_project --platforms https://www.ccgp.gov.cn

# 自定义配置文件
python main.py my_project --config path/to/config.yaml
```

---

## 📁 项目结构 / Project Structure

```
D:/CADAI/
├── main.py                  # CLI 入口 / Entry point
├── config.example.yaml      # 配置模板 / Config template
├── requirements.txt         # Python 依赖 / Dependencies
├── src/
│   ├── crawler/             # 爬虫模块 / Crawler module
│   │   ├── crawler_module.py
│   │   ├── anti_crawl.py
│   │   └── platform_parsers/
│   ├── dxf_parser/          # DXF解析 / DXF parser
│   │   ├── parser.py
│   │   ├── geometry.py
│   │   └── quota_mapper.py
│   ├── rag_generator/       # RAG生成 / RAG generator
│   │   ├── ingestion.py
│   │   ├── retrieval.py
│   │   ├── generation.py
│   │   └── formatter.py
│   ├── monte_carlo/         # 蒙特卡洛 / Monte Carlo
│   │   ├── simulator.py
│   │   └── distribution.py
│   └── pipeline/            # 流水线 / Pipeline orchestrator
│       ├── orchestrator.py
│       └── config_loader.py
├── tests/                   # 单元测试 / Unit tests
├── data/                    # 示例数据 / Sample data
│   ├── demo_dxf/
│   ├── historical_bids/
│   └── quota_db.json
└── output/                  # 运行输出 / Pipeline output
```

---

## 🧪 测试 / Testing

```bash
# 运行全部单元测试
pytest tests/ -v

# 运行属性测试 (Property-Based Testing)
pytest tests/test_properties.py -v

# 运行实际集成测试 (需要网络/API)
python test_crawl_live.py
python test_rag_live.py
python test_monte_carlo_live.py
```

---

## ⚙️ 技术栈 / Tech Stack

| 类别 / Category | 工具 / Tools |
|---|---|
| 语言 / Language | Python 3.12 |
| 爬虫 / Crawling | Playwright, Scrapy, httpx |
| CAD解析 / CAD | ezdxf |
| 向量数据库 / Vector DB | ChromaDB |
| 大模型 / LLM | OpenAI API (可替换) |
| 文档生成 / Doc Gen | python-docx |
| 数据科学 / Data Science | NumPy, Pandas, scikit-learn |
| 测试 / Testing | pytest, Hypothesis (PBT) |

---

## 📋 开发状态 / Status

**Phase 1 MVP — 核心 Pipeline 验证完成 ✅**

- [x] 爬虫模块（多平台、反爬机制）
- [x] DXF 几何计算（面积、延米、定额映射）
- [x] RAG 技术标生成（向量检索 + LLM + Word输出）
- [x] 蒙特卡洛报价模拟（分布拟合 + 最优区间）
- [x] Pipeline CLI 编排
- [x] 配置管理 + 容错机制

---

## ⚠️ 注意事项 / Notes

- `config.yaml` 包含 API 密钥，已被 `.gitignore` 排除，不会提交到仓库
- 本项目仅用于合法的公开信息采集，请遵守目标平台的 robots.txt 和使用条款
- MVP 阶段不包含前端界面，纯 CLI 操作

- `config.yaml` contains API keys and is excluded via `.gitignore`
- This project only crawls publicly available bidding information. Respect target platform ToS.
- MVP phase is CLI-only, no frontend UI

---

## 📄 License

MIT
