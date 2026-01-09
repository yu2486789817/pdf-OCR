"use client";

import { useEffect, useMemo, useState } from "react";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE || "http://127.0.0.1:8000/api";

const formatBytes = (bytes) => {
  if (!bytes && bytes !== 0) return "-";
  const sizes = ["B", "KB", "MB", "GB"];
  const i = Math.min(Math.floor(Math.log(bytes) / Math.log(1024)), sizes.length - 1);
  return `${(bytes / Math.pow(1024, i)).toFixed(i === 0 ? 0 : 1)} ${sizes[i]}`;
};

const statusMap = {
  idle: "已就绪",
  uploaded: "等待开始",
  pending: "排队中",
  processing: "处理中",
  completed: "已完成",
  failed: "失败"
};

const buildPreview = (result) => {
  if (!result) return "";
  const pages = Array.isArray(result) ? result : result.pages;
  if (result.type === "text") {
    return result.content || "";
  }
  if (Array.isArray(pages)) {
    return pages
      .map((page) => {
        if (Array.isArray(page.paragraphs) && page.paragraphs.length > 0) {
          return `--- 第 ${page.page + 1} 页 ---\n${page.paragraphs.join("\n\n")}`;
        }
        return `--- 第 ${page.page + 1} 页 ---\n${page.text || ""}`;
      })
      .join("\n\n");
  }
  return "";
};

const parsePageInput = (value) => {
  const raw = value.replace(/，/g, ",").replace(/\s+/g, "").trim();
  if (!raw) return { pages: null };
  const pages = [];
  for (const part of raw.split(",")) {
    if (!part) continue;
    if (part.includes("-")) {
      const [startStr, endStr] = part.split("-");
      const start = Number(startStr);
      const end = Number(endStr);
      if (!Number.isInteger(start) || !Number.isInteger(end) || start <= 0 || end <= 0) {
        return { error: "页码格式错误" };
      }
      const [from, to] = start <= end ? [start, end] : [end, start];
      for (let i = from; i <= to; i += 1) pages.push(i);
    } else {
      const num = Number(part);
      if (!Number.isInteger(num) || num <= 0) return { error: "页码格式错误" };
      pages.push(num);
    }
  }
  const unique = Array.from(new Set(pages)).sort((a, b) => a - b);
  if (!unique.length) return { error: "无有效页码" };
  return { pages: unique };
};

export default function Home() {
  const [file, setFile] = useState(null);
  const [taskId, setTaskId] = useState("");
  const [uploadInfo, setUploadInfo] = useState(null);
  const [uploadMessage, setUploadMessage] = useState("");
  const [uploadProgress, setUploadProgress] = useState(0);
  const [taskStatus, setTaskStatus] = useState({
    status: "idle",
    message: "等待上传 PDF 文件",
    progress: 0,
    current_page: 0,
    total_pages: 0
  });
  const [resultText, setResultText] = useState("");
  const [options, setOptions] = useState({
    preprocess: true,
    denoise: true,
    binarize: false,
    deskew: true,
    dpi: 300,
    ignore_top: 0,
    ignore_bottom: 0,
    ignore_left: 0,
    ignore_right: 0
  });
  const [pageInput, setPageInput] = useState("");
  const [exportFormat, setExportFormat] = useState("docx");
  const [exportTitle, setExportTitle] = useState("");
  const [exportMessage, setExportMessage] = useState("");
  const [busy, setBusy] = useState(false);
  const [history, setHistory] = useState([]);
  const [historyMessage, setHistoryMessage] = useState("正在获取...");
  const [isDragging, setIsDragging] = useState(false);
  
  // AI 增强相关状态
  const [aiEnabled, setAiEnabled] = useState(false);
  const [aiApiKey, setAiApiKey] = useState("");
  const [aiStatus, setAiStatus] = useState({ status: "idle", message: "" });

  const statusLabel = useMemo(() => {
    if (taskStatus.status === "processing") return "处理中";
    if (taskStatus.status === "completed") return "已完成";
    if (taskStatus.status === "failed") return "失败";
    if (taskStatus.status === "pending") return "排队中";
    if (taskStatus.status === "uploaded") return "等待开始";
    return "就绪";
  }, [taskStatus.status]);

  const progressLabel = useMemo(() => {
    if (taskStatus.status === "processing") {
      return `正在处理 第 ${taskStatus.current_page}/${taskStatus.total_pages} 页`;
    }
    if (taskStatus.status === "completed") {
      return "处理完成";
    }
    if (taskStatus.status === "failed") {
      return "失败";
    }
    return "未开始";
  }, [taskStatus]);

  const loadHistory = async () => {
    setHistoryMessage("正在加载...");
    try {
      const response = await fetch(`${API_BASE}/history`);
      if (!response.ok) throw new Error("获取历史记录失败");
      const data = await response.json();
      setHistory(data);
      setHistoryMessage(data.length ? "" : "暂无历史记录");
    } catch (error) {
      setHistoryMessage(error.message);
    }
  };

  useEffect(() => {
    loadHistory();
  }, []);

  useEffect(() => {
    if (!taskId) return;
    if (!["pending", "processing"].includes(taskStatus.status)) return;

    const timer = setInterval(async () => {
      try {
        const response = await fetch(`${API_BASE}/ocr/${taskId}/status`);
        if (!response.ok) {
          throw new Error("查询状态失败");
        }
        const data = await response.json();
        const statusMessage =
          data.status === "completed" ? "任务已完成" : data.message || "请求中...";
        setTaskStatus({
          status: data.status,
          message: statusMessage,
          progress: data.progress,
          current_page: data.current_page,
          total_pages: data.total_pages
        });

        if (data.status === "completed" && data.result) {
          setResultText(buildPreview(data.result));
          loadHistory();
        }
      } catch (error) {
        setTaskStatus((prev) => ({
          ...prev,
          status: "failed",
          message: "查询 OCR 状态失败"
        }));
      }
    }, 2000);

    return () => clearInterval(timer);
  }, [taskId, taskStatus.status]);

  const handleDragOver = (e) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(true);
  };

  const handleDragLeave = (e) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(false);
  };

  const handleDrop = (e) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(false);
    
    const droppedFiles = e.dataTransfer.files;
    if (droppedFiles && droppedFiles.length > 0) {
      const droppedFile = droppedFiles[0];
      if (droppedFile.type === "application/pdf") {
        setFile(droppedFile);
      } else {
        setUploadMessage("请上传有效的 PDF 文件");
      }
    }
  };

  const handleUpload = async () => {
    if (!file) {
      setUploadMessage("请先选择 PDF 文件");
      return;
    }
    setBusy(true);
    setUploadMessage("正在上传...");
    setExportMessage("");
    setResultText("");
    setUploadProgress(0);

    const payload = new FormData();
    payload.append("file", file);

    try {
      const data = await new Promise((resolve, reject) => {
        const xhr = new XMLHttpRequest();
        xhr.open("POST", `${API_BASE}/upload`);

        xhr.upload.onprogress = (event) => {
          if (event.lengthComputable) {
            const percent = (event.loaded / event.total) * 100;
            setUploadProgress(percent);
          }
        };

        xhr.onload = () => {
          if (xhr.status >= 200 && xhr.status < 300) {
            resolve(JSON.parse(xhr.responseText));
          } else {
            const errorData = JSON.parse(xhr.responseText || "{}");
            reject(new Error(errorData.detail || "上传失败"));
          }
        };

        xhr.onerror = () => reject(new Error("网络错误"));
        xhr.send(payload);
      });

      setTaskId(data.task_id);
      setUploadInfo({ file_size: data.file_size, filename: data.filename });
      setUploadMessage("文件已上传，正在解析 PDF...");
      setUploadProgress(100);
      
      // 开始轮询解析状态
      const pollParseStatus = async () => {
        try {
          const statusRes = await fetch(`${API_BASE}/upload/${data.task_id}/parse-status`);
          const statusData = await statusRes.json();
          
          if (statusData.status === "ready") {
            setUploadInfo(prev => ({
              ...prev,
              pdf_type: statusData.pdf_type,
              page_count: statusData.page_count
            }));
            setUploadMessage(`解析完成 | ${statusData.pdf_type?.toUpperCase()} | ${statusData.page_count} 页`);
            setTaskStatus({
              status: "uploaded",
              message: "准备好 OCR 任务",
              progress: 0,
              current_page: 0,
              total_pages: statusData.page_count
            });
            loadHistory();
            setBusy(false);
          } else if (statusData.status === "failed") {
            setUploadMessage(`解析失败: ${statusData.message}`);
            setBusy(false);
          } else {
            // 继续轮询
            setUploadMessage(`正在解析 PDF... ${Math.round(statusData.progress)}%`);
            setTimeout(pollParseStatus, 500);
          }
        } catch (err) {
          setUploadMessage("解析状态查询失败");
          setBusy(false);
        }
      };
      
      pollParseStatus();
    } catch (error) {
      setUploadMessage(error.message);
      setUploadProgress(0);
      setBusy(false);
    }
  };

  const startOcr = async () => {
    if (!taskId) return;
    const parsed = parsePageInput(pageInput);
    if (parsed.error) {
      setTaskStatus((prev) => ({
        ...prev,
        status: "failed",
        message: parsed.error
      }));
      return;
    }

    setBusy(true);
    setExportMessage("");
    setResultText("");
    try {
      const response = await fetch(`${API_BASE}/ocr/${taskId}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          ...options,
          pages: parsed.pages || undefined
        })
      });
      const data = await response.json();
      if (!response.ok) {
        throw new Error(data.detail || "OCR 启动失败");
      }
      setTaskStatus((prev) => ({
        ...prev,
        status: "pending",
        message: data.message
      }));
    } catch (error) {
      setTaskStatus((prev) => ({
        ...prev,
        status: "failed",
        message: error.message
      }));
    } finally {
      setBusy(false);
    }
  };

  const handleExport = async () => {
    if (!taskId) return;
    setExportMessage("正在生成导出文件...");
    try {
      const response = await fetch(`${API_BASE}/export/${taskId}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          format: exportFormat,
          include_page_numbers: true,
          title: exportTitle || undefined
        })
      });
      const data = await response.json();
      if (!response.ok) {
        throw new Error(data.detail || "导出失败");
      }
      const downloadUrl = `${API_BASE}/export/${taskId}/download/${data.filename}`;
      window.open(downloadUrl, "_blank");
      setExportMessage(`已导出 ${data.filename}`);
    } catch (error) {
      setExportMessage(error.message);
    }
  };

  const selectHistory = async (item) => {
    setTaskId(item.task_id);
    setUploadInfo({
      file_size: item.file_size || null,
      page_count: item.page_count,
      pdf_type: item.pdf_type
    });
    setUploadMessage(item.filename ? `历史记录: ${item.filename}` : `任务 ID: ${item.task_id}`);
    setTaskStatus({
      status: item.status || (item.has_result ? "completed" : "uploaded"),
      message: item.has_result ? "已完成" : "未开始",
      progress: item.has_result ? 100 : 0,
      current_page: 0,
      total_pages: item.page_count || 0
    });

    if (item.has_result) {
      try {
        const response = await fetch(`${API_BASE}/history/${item.task_id}/result`);
        if (!response.ok) throw new Error("结果拉取失败");
        const data = await response.json();
        setResultText(buildPreview({ type: "ocr", pages: data }));
      } catch (error) {
        setResultText("");
        setExportMessage(error.message);
      }
    } else {
      setResultText("");
    }
  };

  const startAiEnhance = async () => {
    if (!taskId) return;
    if (!aiApiKey) {
      setAiStatus({ status: "failed", message: "请先填写 AI API Key" });
      return;
    }
    
    setAiStatus({ status: "processing", message: "正在启动 AI 增强..." });
    
    try {
      const response = await fetch(`${API_BASE}/ai/${taskId}/enhance`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ api_key: aiApiKey })
      });
      const data = await response.json();
      if (!response.ok) {
        throw new Error(data.detail || "AI 增强启动失败");
      }
      
      // 轮询 AI 状态
      const pollAiStatus = async () => {
        try {
          const statusRes = await fetch(`${API_BASE}/ai/${taskId}/status`);
          const statusData = await statusRes.json();
          
          if (statusData.status === "completed") {
            setAiStatus({ status: "completed", message: "AI 增强完成" });
            // 获取增强后的结果
            const resultRes = await fetch(`${API_BASE}/ai/${taskId}/result`);
            const resultData = await resultRes.json();
            const formatted = resultData.pages
              .map(p => `--- 第 ${p.page + 1} 页 ---\n${p.formatted}`)
              .join("\n\n");
            setResultText(formatted);
          } else if (statusData.status === "failed") {
            setAiStatus({ status: "failed", message: statusData.message });
          } else {
            setAiStatus({ 
              status: "processing", 
              message: `正在处理... ${statusData.chunks_processed}/${statusData.chunks_total}` 
            });
            setTimeout(pollAiStatus, 1000);
          }
        } catch (err) {
          setAiStatus({ status: "failed", message: "查询状态失败" });
        }
      };
      
      pollAiStatus();
    } catch (error) {
      setAiStatus({ status: "failed", message: error.message });
    }
  };

  const resetAll = () => {
    setFile(null);
    setTaskId("");
    setUploadInfo(null);
    setUploadMessage("");
    setTaskStatus({
      status: "idle",
      message: "等待上传 PDF 文件",
      progress: 0,
      current_page: 0,
      total_pages: 0
    });
    setResultText("");
    setExportMessage("");
    setAiStatus({ status: "idle", message: "" });
  };

  return (
    <main className="min-h-screen px-6 py-10 lg:px-12">
      <div className="mx-auto flex max-w-6xl flex-col gap-10">
        <header className="flex flex-col gap-6">
          <div className="flex flex-wrap items-center justify-between gap-4">
            <div>
              <p className="text-sm uppercase tracking-[0.2em] text-slate-300">SmartPDF OCR Studio</p>
              <h1 className="section-title text-4xl font-semibold text-white sm:text-5xl">
                智能 PDF 文字识别
              </h1>
            </div>
            <div className="glass rounded-full px-4 py-2 text-xs text-slate-200">
              API: {API_BASE.replace("/api", "")}
            </div>
          </div>
          <p className="max-w-2xl text-base text-slate-200">
            高效精准的 PDF OCR 识别工具，支持扫描件转换、内容增强与多种格式导出。
          </p>
        </header>

        <section className="grid gap-6 lg:grid-cols-[1.05fr_0.95fr]">
          <div className="glass rounded-3xl p-6">
            <div className="flex items-center justify-between">
              <h2 className="section-title text-2xl text-white">操作控制</h2>
              <button
                className="rounded-full border border-slate-600 px-4 py-1 text-xs text-slate-300 hover:border-slate-400"
                onClick={resetAll}
                type="button"
              >
                重置
              </button>
            </div>

            <div className="mt-6 grid gap-4">
              <div className="rounded-2xl border border-slate-700/60 bg-slate-900/40 p-4">
                <p className="text-xs uppercase tracking-[0.3em] text-slate-400">步骤 1</p>
                <h3 className="mt-2 text-lg font-semibold text-white">上传 PDF</h3>
                <div className="mt-3 flex flex-col gap-3">
                  <div 
                    onDragOver={handleDragOver}
                    onDragLeave={handleDragLeave}
                    onDrop={handleDrop}
                    className={`relative flex flex-col items-center justify-center rounded-2xl border-2 border-dashed p-8 transition-all ${
                      isDragging 
                        ? "border-orange-500 bg-orange-500/10" 
                        : "border-slate-700 bg-slate-900/40 hover:border-slate-500"
                    }`}
                  >
                    <input
                      type="file"
                      accept=".pdf"
                      id="pdf-upload"
                      className="absolute inset-0 cursor-pointer opacity-0"
                      onChange={(event) => setFile(event.target.files?.[0] || null)}
                    />
                    <div className="flex flex-col items-center gap-3">
                      <div className={`rounded-full p-3 ${isDragging ? "bg-orange-500/20" : "bg-slate-800/50"}`}>
                        <svg className={`h-6 w-6 ${isDragging ? "text-orange-500" : "text-slate-400"}`} fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12" />
                        </svg>
                      </div>
                      <div className="text-center">
                        <p className="text-sm font-medium text-slate-200">
                          {file ? <span className="text-orange-400">{file.name}</span> : "点击或拖入 PDF 文件"}
                        </p>
                        <p className="mt-1 text-xs text-slate-500">支持最大 100MB 的 PDF 文档</p>
                      </div>
                    </div>
                  </div>
                  <button
                    className="w-full rounded-xl bg-orange-500 py-3 text-sm font-semibold text-white shadow-lg shadow-orange-500/30 hover:bg-orange-400 disabled:cursor-not-allowed disabled:opacity-60"
                    onClick={handleUpload}
                    disabled={busy || !file}
                    type="button"
                  >
                    {busy && uploadProgress < 100 ? `正在上传 ${Math.round(uploadProgress)}%` : "开始上传"}
                  </button>
                </div>
                {busy && uploadProgress > 0 && uploadProgress < 100 && (
                  <div className="mt-3 h-1.5 w-full overflow-hidden rounded-full bg-slate-800">
                    <div 
                      className="h-full bg-orange-500 transition-all duration-300" 
                      style={{ width: `${uploadProgress}%` }}
                    />
                  </div>
                )}
                <div className="mt-3 text-xs text-slate-300">
                  {uploadMessage || "请上传 PDF 以获取详细文件信息"}
                </div>
                {uploadInfo && (
                  <div className="mt-3 grid grid-cols-2 gap-2 text-xs text-slate-400">
                    <div>文件大小: {formatBytes(uploadInfo.file_size)}</div>
                    <div>页数: {uploadInfo.page_count ?? "-"}</div>
                    <div>类型: {uploadInfo.pdf_type || "-"}</div>
                    <div>任务 ID: {taskId.slice(0, 8)}...</div>
                  </div>
                )}
              </div>

              <div className="rounded-2xl border border-slate-700/60 bg-slate-900/40 p-4">
                <p className="text-xs uppercase tracking-[0.3em] text-slate-400">步骤 2</p>
                <h3 className="mt-2 text-lg font-semibold text-white">配置 OCR 参数</h3>
                <div className="mt-3 grid gap-3 sm:grid-cols-2">
                  {[
                    ["preprocess", "图像预处理"],
                    ["denoise", "自动去噪"],
                    ["binarize", "二值化增强"],
                    ["deskew", "自动纠偏"]
                  ].map(([key, label]) => (
                    <label
                      key={key}
                      className="flex items-center justify-between rounded-xl border border-slate-700/60 px-4 py-3 text-sm text-slate-200"
                    >
                      <span>{label}</span>
                      <input
                        type="checkbox"
                        checked={options[key]}
                        onChange={(event) =>
                          setOptions((prev) => ({ ...prev, [key]: event.target.checked }))
                        }
                        className="h-4 w-4 accent-teal-400"
                      />
                    </label>
                  ))}
                </div>
                <div className="mt-4">
                  <label className="text-xs uppercase tracking-[0.3em] text-slate-400">渲染精度 (DPI)</label>
                  <input
                    type="range"
                    min={150}
                    max={600}
                    step={50}
                    value={options.dpi}
                    onChange={(event) =>
                      setOptions((prev) => ({ ...prev, dpi: Number(event.target.value) }))
                    }
                    className="mt-3 w-full accent-orange-400"
                  />
                  <div className="mt-2 text-xs text-slate-300">当前建议: {options.dpi} DPI</div>
                </div>
                <div className="mt-4">
                  <label className="text-xs uppercase tracking-[0.3em] text-slate-400">页码范围</label>
                  <input
                    type="text"
                    value={pageInput}
                    onChange={(event) => setPageInput(event.target.value)}
                    placeholder="例如：1-3, 5, 8"
                    className="mt-3 w-full rounded-xl border border-slate-600 bg-slate-900/60 px-3 py-2 text-sm text-slate-200"
                  />
                </div>

                <div className="mt-4 border-t border-slate-800 pt-4">
                  <label className="text-xs uppercase tracking-[0.3em] text-slate-400">区域过滤 (忽略边距 %)</label>
                  <div className="mt-3 grid grid-cols-2 gap-3">
                    {[
                      ["ignore_top", "顶部"],
                      ["ignore_bottom", "底部"],
                      ["ignore_left", "左侧"],
                      ["ignore_right", "右侧"]
                    ].map(([key, label]) => (
                      <div key={key} className="flex items-center gap-2 rounded-xl border border-slate-700/60 bg-slate-950/20 px-3 py-2">
                        <span className="shrink-0 text-xs text-slate-400">{label}</span>
                        <input
                          type="number"
                          min={0}
                          max={50}
                          value={options[key]}
                          onChange={(e) => setOptions(prev => ({ ...prev, [key]: Number(e.target.value) }))}
                          className="w-full bg-transparent text-right text-sm text-teal-400 focus:outline-none"
                        />
                        <span className="text-[10px] text-slate-500">%</span>
                      </div>
                    ))}
                  </div>
                  <p className="mt-2 text-[10px] text-slate-500">建议：页眉/页脚通常设置 5-10%</p>
                </div>
              </div>

              <div className="rounded-2xl border border-slate-700/60 bg-slate-900/40 p-4">
                <p className="text-xs uppercase tracking-[0.3em] text-slate-400">步骤 3</p>
                <h3 className="mt-2 text-lg font-semibold text-white">执行 OCR</h3>
                <div className="mt-3 flex flex-wrap gap-3">
                  <button
                    className="rounded-xl bg-teal-500 px-5 py-3 text-sm font-semibold text-white shadow-lg shadow-teal-500/30 hover:bg-teal-400 disabled:cursor-not-allowed disabled:opacity-60"
                    onClick={startOcr}
                    disabled={!taskId || busy}
                    type="button"
                  >
                    启动 OCR
                  </button>
                  <div className="flex flex-1 flex-col justify-center text-xs text-slate-300">
                    {taskStatus.message}
                  </div>
                </div>
                <div className="mt-4">
                  <div className="flex items-center justify-between text-xs text-slate-300">
                    <span>{progressLabel}</span>
                    <span>{Math.round(taskStatus.progress)}%</span>
                  </div>
                  <div className="mt-2 h-2 w-full overflow-hidden rounded-full bg-slate-800">
                    <div
                      className="h-full rounded-full bg-gradient-to-r from-orange-400 via-teal-400 to-orange-300 transition-all"
                      style={{ width: `${Math.min(100, taskStatus.progress)}%` }}
                    />
                  </div>
                </div>
              </div>

              <div className="rounded-2xl border border-slate-700/60 bg-slate-900/40 p-4">
                <p className="text-xs uppercase tracking-[0.3em] text-slate-400">步骤 4</p>
                <h3 className="mt-2 text-lg font-semibold text-white">结果导出</h3>
                <div className="mt-3 grid gap-3 sm:grid-cols-[1fr_1fr]">
                  <select
                    value={exportFormat}
                    onChange={(event) => setExportFormat(event.target.value)}
                    className="w-full rounded-xl border border-slate-600 bg-slate-900/60 px-3 py-2 text-sm text-slate-200"
                  >
                    <option value="txt">TXT</option>
                    <option value="docx">DOCX</option>
                    <option value="pdf">双层 PDF</option>
                  </select>
                  <input
                    type="text"
                    value={exportTitle}
                    onChange={(event) => setExportTitle(event.target.value)}
                    placeholder="自定义文件名"
                    className="w-full rounded-xl border border-slate-600 bg-slate-900/60 px-3 py-2 text-sm text-slate-200"
                  />
                </div>
                <div className="mt-3 flex flex-wrap items-center gap-3">
                  <button
                    className="rounded-xl border border-slate-500 px-5 py-3 text-sm font-semibold text-slate-200 hover:border-slate-300"
                    onClick={handleExport}
                    disabled={taskStatus.status !== "completed"}
                    type="button"
                  >
                    导出到下载
                  </button>
                  <span className="text-xs text-slate-300">{exportMessage}</span>
                </div>

                {/* AI 增强区 */}
                <div className="mt-4 border-t border-slate-800 pt-4">
                  <div className="flex items-center justify-between">
                    <label className="text-xs uppercase tracking-[0.3em] text-slate-400">AI 语义优化</label>
                    <label className="flex items-center gap-2 text-xs text-slate-300">
                      <input
                        type="checkbox"
                        checked={aiEnabled}
                        onChange={(e) => setAiEnabled(e.target.checked)}
                        className="h-3 w-3 accent-purple-400"
                      />
                      启用
                    </label>
                  </div>
                  {aiEnabled && (
                    <div className="mt-3 flex flex-col gap-3">
                      <input
                        type="password"
                        value={aiApiKey}
                        onChange={(e) => setAiApiKey(e.target.value)}
                        placeholder="输入 OpenAI API Key"
                        className="w-full rounded-xl border border-slate-600 bg-slate-900/60 px-3 py-2 text-sm text-slate-200"
                      />
                      <div className="flex items-center gap-3">
                        <button
                          className="rounded-xl bg-purple-500 px-4 py-2 text-sm font-semibold text-white shadow-lg shadow-purple-500/30 hover:bg-purple-400 disabled:cursor-not-allowed disabled:opacity-60"
                          onClick={startAiEnhance}
                          disabled={taskStatus.status !== "completed" || aiStatus.status === "processing"}
                          type="button"
                        >
                          {aiStatus.status === "processing" ? "处理中..." : "AI 增强排版"}
                        </button>
                        <span className={`text-xs ${
                          aiStatus.status === "completed" ? "text-emerald-400" : 
                          aiStatus.status === "failed" ? "text-red-400" : "text-slate-400"
                        }`}>
                          {aiStatus.message}
                        </span>
                      </div>
                      <p className="text-[10px] text-slate-500">
                        使用 AI 修复断行、还原列表结构、修正错别字
                      </p>
                    </div>
                  )}
                </div>
              </div>
            </div>
          </div>

          <div className="glass rounded-3xl p-6">
            <div className="flex items-center justify-between">
              <h2 className="section-title text-2xl text-white">历史任务</h2>
              <button
                className="rounded-full border border-slate-600 px-3 py-1 text-xs text-slate-300 hover:border-slate-400"
                onClick={loadHistory}
                type="button"
              >
                刷新
              </button>
            </div>
            <div className="mt-4 max-h-40 overflow-auto rounded-2xl border border-slate-700/60 bg-slate-900/40 p-3 text-xs text-slate-300">
              {history.length ? (
                <div className="flex flex-col gap-2">
                  {history.map((item) => (
                    <button
                      key={item.task_id}
                      type="button"
                      onClick={() => selectHistory(item)}
                      className="flex items-center justify-between rounded-xl border border-slate-700/60 bg-slate-950/40 px-3 py-2 text-left text-xs text-slate-200 hover:border-slate-500"
                    >
                      <div className="flex flex-col">
                        <span className="font-semibold">{item.filename || item.task_id}</span>
                        <span className="text-[10px] text-slate-400">
                          {item.pdf_type || "未知类型"} | {item.page_count !== null && item.page_count !== undefined ? `${item.page_count} 页` : "页数未知"} | {statusMap[item.status] || item.status || "状态未知"}
                        </span>
                      </div>
                      <span className="text-[10px] text-slate-400">{item.has_result ? "已完成" : "进行中"}</span>
                    </button>
                  ))}
                </div>
              ) : (
                <div className="py-4 text-center">{historyMessage}</div>
              )}
            </div>

            <div className="mt-6 flex items-center justify-between">
              <h2 className="section-title text-2xl text-white">预览结果</h2>
              <div
                className={`rounded-full px-3 py-1 text-xs ${
                  taskStatus.status === "completed"
                    ? "bg-emerald-400/20 text-emerald-200"
                    : taskStatus.status === "failed"
                    ? "bg-red-400/20 text-red-200"
                    : "bg-slate-700/40 text-slate-200"
                }`}
              >
                {statusLabel}
              </div>
            </div>

            <div className="mt-6">
              <textarea
                readOnly
                value={resultText || "OCR 识别结果将显示在这里..."}
                className="h-[360px] w-full resize-none rounded-2xl border border-slate-700/60 bg-slate-950/60 p-4 text-sm text-slate-200 focus:outline-none"
              />
            </div>

            <div className="mt-6 grid gap-4 rounded-2xl border border-slate-700/60 bg-slate-900/40 p-4 text-sm text-slate-200">
              <div className="flex items-center justify-between">
                <span>任务 ID</span>
                <span className="text-xs text-slate-400">{taskId || "-"}</span>
              </div>
              <div className="flex items-center justify-between">
                <span>处理进度</span>
                <span className="text-xs text-slate-400">{Math.round(taskStatus.progress)}%</span>
              </div>
              <div className="flex items-center justify-between">
                <span>当前页码</span>
                <span className="text-xs text-slate-400">
                  {taskStatus.current_page}/{taskStatus.total_pages || "-"}
                </span>
              </div>
              <div className="flex items-center justify-between">
                <span>当前状态</span>
                <span className="text-xs text-slate-400">{taskStatus.message}</span>
              </div>
            </div>
          </div>
        </section>

        <footer className="flex flex-col items-start justify-between gap-3 text-xs text-slate-400 sm:flex-row sm:items-center">
          <span>SmartPDF OCR Studio | 基于 Next.js + Tailwind 构建</span>
          <span>API 运行端口 8000 | 模型后端服务 7860</span>
        </footer>
      </div>
    </main>
  );
}
