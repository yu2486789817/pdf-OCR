"""
Gradio 前端界面
"""

import gradio as gr
import requests
import time
import os
import json
from pathlib import Path

# 配置 API 地址
API_HOST = "http://127.0.0.1:8000"
API_URL = f"{API_HOST}/api"

def upload_pdf(file):
    """上传 PDF 文件"""
    if file is None:
        return None, "请选择文件"
    
    url = f"{API_URL}/upload"
    files = {"file": open(file, "rb")}
    
    try:
        response = requests.post(url, files=files)
        response.raise_for_status()
        data = response.json()
        return data["task_id"], f"上传成功: {data['filename']} ({data['pdf_type']})"
    except Exception as e:
        return None, f"上传失败: {str(e)}"

def start_ocr_process(task_id, preprocess, denoise, binarize, deskew, dpi):
    """启动 OCR 处理"""
    if not task_id:
        return "请先上传文件"
    
    url = f"{API_URL}/ocr/{task_id}"
    data = {
        "preprocess": preprocess,
        "denoise": denoise,
        "binarize": binarize,
        "deskew": deskew,
        "dpi": dpi
    }
    
    try:
        response = requests.post(url, json=data)
        response.raise_for_status()
        return "OCR 任务已启动，请等待处理完成..."
    except Exception as e:
        return f"启动失败: {str(e)}"

def check_status(task_id):
    """检查任务状态"""
    if not task_id:
        return "未开始", 0, ""
    
    url = f"{API_URL}/ocr/{task_id}/status"
    
    try:
        response = requests.get(url)
        response.raise_for_status()
        data = response.json()
        
        status_text = f"状态: {data['status']}\n消息: {data['message']}"
        if data['status'] == "processing":
            status_text += f"\n当前页: {data['current_page']}/{data['total_pages']}"
            
        return status_text, data['progress'], data['status']
    except Exception as e:
        return f"查询失败: {str(e)}", 0, "error"

def get_ocr_result(task_id):
    """获取 OCR 结果预览"""
    if not task_id:
        return "暂无结果"
    
    url = f"{API_URL}/ocr/{task_id}/result"
    
    try:
        response = requests.get(url)
        if response.status_code != 200:
            return "任务尚未完成或出错"
            
        data = response.json()
        
        # 格式化显示
        if data.get("type") == "text":
            return data.get("content", "")
        
        result_text = ""
        if "pages" in data:
            for page in data["pages"]:
                result_text += f"--- 第 {page['page'] + 1} 页 ---\n\n"
                if "paragraphs" in page:
                    result_text += "\n\n".join(page["paragraphs"])
                else:
                    result_text += page.get("text", "")
                result_text += "\n\n"
                
        return result_text
    except Exception as e:
        return f"获取结果失败: {str(e)}"

def export_result(task_id, format_type):
    """导出结果"""
    if not task_id:
        return None, "请先完成 OCR 处理"
    
    url = f"{API_URL}/export/{task_id}"
    data = {"format": format_type, "include_page_numbers": True}
    
    try:
        response = requests.post(url, json=data)
        response.raise_for_status()
        res_data = response.json()
        
        filename = res_data["filename"]
        download_url = f"{API_URL}/export/{task_id}/download/{filename}"
        
        # 下载文件到本地临时目录
        local_path = Path("outputs") / filename
        local_path.parent.mkdir(exist_ok=True)
        
        file_res = requests.get(download_url)
        with open(local_path, "wb") as f:
            f.write(file_res.content)
            
        return str(local_path), f"导出成功: {filename}"
    except Exception as e:
        return None, f"导出失败: {str(e)}"

# 构建 Gradio 界面
with gr.Blocks(title="SmartPDF-OCR") as demo:
    gr.Markdown("# SmartPDF-OCR 智能文档识别系统")
    
    # 状态存储
    task_id_state = gr.State(value=None)
    
    with gr.Row():
        with gr.Column(scale=1):
            # 上传区域
            file_input = gr.File(label="上传 PDF 文件", file_types=[".pdf"])
            upload_btn = gr.Button("确认上传", variant="primary")
            upload_status = gr.Textbox(label="上传状态", interactive=False)
            
            # 配置区域
            with gr.Accordion("高级设置", open=False):
                preprocess_chk = gr.Checkbox(label="启用图像预处理", value=True)
                denoise_chk = gr.Checkbox(label="去噪", value=True)
                binarize_chk = gr.Checkbox(label="二值化 (建议扫描件开启)", value=False)
                deskew_chk = gr.Checkbox(label="倾斜校正", value=True)
                dpi_slider = gr.Slider(label="渲染 DPI", minimum=150, maximum=600, value=300, step=50)
            
            # 操作按钮
            ocr_btn = gr.Button("开始识别", variant="primary")
            
            # 进度显示
            progress_bar = gr.Slider(label="处理进度", minimum=0, maximum=100, value=0, interactive=False)
            status_box = gr.TextArea(label="任务状态", interactive=False, lines=4)
            
            # 自动刷新组件
            timer = gr.Timer(value=2.0, active=False)
            
        with gr.Column(scale=2):
            # 结果预览
            result_preview = gr.TextArea(label="OCR 识别结果预览", lines=20, interactive=False)
            
            # 导出区域
            with gr.Row():
                format_radio = gr.Radio(choices=["txt", "docx", "pdf"], value="docx", label="导出格式")
                export_btn = gr.Button("导出下载")
            
            download_file = gr.File(label="下载文件")
            export_msg = gr.Textbox(label="导出消息", interactive=False)

    # 事件绑定
    upload_btn.click(
        upload_pdf, 
        inputs=[file_input], 
        outputs=[task_id_state, upload_status]
    )
    
    def on_ocr_click(task_id, pre, den, bin, des, dpi):
        msg = start_ocr_process(task_id, pre, den, bin, des, dpi)
        return msg, True # 启动定时器
        
    ocr_btn.click(
        on_ocr_click,
        inputs=[task_id_state, preprocess_chk, denoise_chk, binarize_chk, deskew_chk, dpi_slider],
        outputs=[status_box, timer]
    )
    
    def on_timer_tick(task_id):
        msg, prog, status = check_status(task_id)
        
        # 如果完成或失败，停止定时器
        active = True
        if status in ["completed", "failed"]:
            active = False
            
        # 如果完成，自动加载结果
        res_text = gr.UPDATE
        if status == "completed":
            res_text = get_ocr_result(task_id)
            
        return msg, prog, active, res_text
        
    timer.tick(
        on_timer_tick,
        inputs=[task_id_state],
        outputs=[status_box, progress_bar, timer, result_preview]
    )
    
    export_btn.click(
        export_result,
        inputs=[task_id_state, format_radio],
        outputs=[download_file, export_msg]
    )

if __name__ == "__main__":
    demo.queue().launch(
        server_name="0.0.0.0", 
        server_port=7860,
        share=False,
        theme=gr.themes.Soft()
    )
