# SmartPDF-OCR

**面向中文场景的智能 PDF OCR 系统**

## 🚀 功能特性

- ✅ **PDF 类型自动检测**：智能判断文字型/图片型 PDF
- ✅ **高精度中文 OCR**：基于 PaddleOCR，支持中英混排
- ✅ **图像预处理**：去噪、二值化、倾斜校正
- ✅ **智能后处理**：段落重建、页眉页脚消除
- ✅ **多格式导出**：TXT、DOCX、可搜索 PDF
- ✅ **Web 界面**：Gradio 可视化操作界面
- ✅ **RESTful API**：FastAPI 后端服务

## 📦 安装

### 环境要求

- Python 3.10+
- Windows / Linux / macOS

### 安装依赖

```bash
# 创建虚拟环境（推荐）
python -m venv venv
source venv/bin/activate  # Linux/macOS
# 或
.\venv\Scripts\activate  # Windows

# 安装依赖
pip install -r requirements.txt
```

## 🎯 快速开始

### 启动 Web 界面

```bash
python frontend/app.py
```

访问 http://localhost:7860 使用 Web 界面。

### 启动 API 服务

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

API 文档：http://localhost:8000/docs

## 📁 项目结构

```
SmartPDF-OCR/
├── app/
│   ├── main.py              # FastAPI 应用入口
│   ├── config.py            # 配置文件
│   ├── api/                 # API 路由
│   ├── core/                # 核心功能模块
│   ├── preprocess/          # 图像预处理
│   ├── ocr/                 # OCR 引擎与后处理
│   ├── export/              # 导出模块
│   └── utils/               # 工具函数
├── frontend/
│   └── app.py               # Gradio 界面
├── tests/                   # 测试代码
├── uploads/                 # 上传文件临时存储
├── outputs/                 # 输出文件存储
├── requirements.txt
└── README.md
```

## 🔧 API 接口

| 端点 | 方法 | 描述 |
|------|------|------|
| `/api/upload` | POST | 上传 PDF 文件 |
| `/api/detect/{task_id}` | GET | 获取 PDF 类型检测结果 |
| `/api/ocr/{task_id}` | POST | 启动 OCR 处理 |
| `/api/status/{task_id}` | GET | 获取任务进度 |
| `/api/export/{task_id}` | GET | 下载处理结果 |

## 📝 使用示例

### Python 代码调用

```python
from app.core.pdf_detector import detect_pdf_type
from app.core.pdf_renderer import render_pdf_to_images
from app.ocr.engine import OCREngine
from app.export.txt_export import export_to_txt

# 检测 PDF 类型
pdf_type = detect_pdf_type("example.pdf")
print(f"PDF 类型: {pdf_type}")

# 渲染为图片
images = render_pdf_to_images("example.pdf", dpi=300)

# OCR 识别
engine = OCREngine()
results = []
for img in images:
    result = engine.recognize(img)
    results.append(result)

# 导出为 TXT
export_to_txt(results, "output.txt")
```

## 🛠️ 技术栈

- **OCR 引擎**：PaddleOCR
- **PDF 解析**：pdfplumber
- **PDF 渲染**：PyMuPDF
- **图像处理**：OpenCV
- **后端框架**：FastAPI
- **前端框架**：Gradio

## 📄 License

MIT License

## Frontend (Next.js + Tailwind)

The Gradio UI has been replaced with a Next.js frontend.

```bash
cd frontend
npm install
npm run dev -- --hostname 0.0.0.0 --port 7860
```

Open http://127.0.0.1:7860
