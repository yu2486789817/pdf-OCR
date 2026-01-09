"use client";

import { useEffect, useMemo, useState } from "react";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE || "http://127.0.0.1:8000/api";

const formatBytes = (bytes) => {
  if (!bytes && bytes !== 0) return "-";
  const sizes = ["B", "KB", "MB", "GB"];
  const i = Math.min(Math.floor(Math.log(bytes) / Math.log(1024)), sizes.length - 1);
  return `${(bytes / Math.pow(1024, i)).toFixed(i === 0 ? 0 : 1)} ${sizes[i]}`;
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
          return `?${page.page + 1}?\n${page.paragraphs.join("\n\n")}`;
        }
        return `?${page.page + 1}?\n${page.text || ""}`;
      })
      .join("\n\n");
  }
  return "";
};

const parsePageInput = (value) => {
  const raw = value.replace(/?/g, ",").replace(/\s+/g, "").trim();
  if (!raw) return { pages: null };
  const pages = [];
  for (const part of raw.split(",")) {
    if (!part) continue;
    if (part.includes("-")) {
      const [startStr, endStr] = part.split("-");
      const start = Number(startStr);
      const end = Number(endStr);
      if (!Number.isInteger(start) || !Number.isInteger(end) || start <= 0 || end <= 0) {
        return { error: "???????" };
      }
      const [from, to] = start <= end ? [start, end] : [end, start];
      for (let i = from; i <= to; i += 1) pages.push(i);
    } else {
      const num = Number(part);
      if (!Number.isInteger(num) || num <= 0) return { error: "???????" };
      pages.push(num);
    }
  }
  const unique = Array.from(new Set(pages)).sort((a, b) => a - b);
  if (!unique.length) return { error: "????" };
  return { pages: unique };
};

export default function Home() {
  const [file, setFile] = useState(null);
  const [taskId, setTaskId] = useState("");
  const [uploadInfo, setUploadInfo] = useState(null);
  const [uploadMessage, setUploadMessage] = useState("");
  const [taskStatus, setTaskStatus] = useState({
    status: "idle",
    message: "???? PDF?",
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
    dpi: 300
  });
  const [pageInput, setPageInput] = useState("");
  const [exportFormat, setExportFormat] = useState("docx");
  const [exportTitle, setExportTitle] = useState("");
  const [exportMessage, setExportMessage] = useState("");
  const [busy, setBusy] = useState(false);
  const [history, setHistory] = useState([]);
  const [historyMessage, setHistoryMessage] = useState("???...");

  const statusLabel = useMemo(() => {
    if (taskStatus.status === "processing") return "???";
    if (taskStatus.status === "completed") return "???";
    if (taskStatus.status === "failed") return "??";
    if (taskStatus.status === "pending") return "???";
    if (taskStatus.status === "uploaded") return "???";
    return "??";
  }, [taskStatus.status]);

  const progressLabel = useMemo(() => {
    if (taskStatus.status === "processing") {
      return `??? ${taskStatus.current_page}/${taskStatus.total_pages}`;
    }
    if (taskStatus.status === "completed") {
      return "???";
    }
    if (taskStatus.status === "failed") {
      return "??";
    }
    return "??";
  }, [taskStatus]);

  const loadHistory = async () => {
    setHistoryMessage("???...");
    try {
      const response = await fetch(`${API_BASE}/history`);
      if (!response.ok) throw new Error("????????");
      const data = await response.json();
      setHistory(data);
      setHistoryMessage(data.length ? "" : "??????");
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
          throw new Error("??????");
        }
        const data = await response.json();
        const statusMessage =
          data.status === "completed" ? "????" : data.message || "???...";
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
          message: "???? OCR ???"
        }));
      }
    }, 2000);

    return () => clearInterval(timer);
  }, [taskId, taskStatus.status]);

  const handleUpload = async () => {
    if (!file) {
      setUploadMessage("????? PDF ???");
      return;
    }
    setBusy(true);
    setUploadMessage("???...");
    setExportMessage("");
    setResultText("");

    const payload = new FormData();
    payload.append("file", file);

    try {
      const response = await fetch(`${API_BASE}/upload`, {
        method: "POST",
        body: payload
      });
      const data = await response.json();
      if (!response.ok) {
        throw new Error(data.detail || "????");
      }
      setTaskId(data.task_id);
      setUploadInfo(data);
      setUploadMessage(`${data.message} | ${data.pdf_type.toUpperCase()} | ${data.page_count} ?`);
      setTaskStatus({
        status: "uploaded",
        message: "???? OCR?",
        progress: 0,
        current_page: 0,
        total_pages: data.page_count
      });
      loadHistory();
    } catch (error) {
      setUploadMessage(error.message);
    } finally {
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
        throw new Error(data.detail || "OCR ????");
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
    setExportMessage("??????...");
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
        throw new Error(data.detail || "????");
      }
      const downloadUrl = `${API_BASE}/export/${taskId}/download/${data.filename}`;
      window.open(downloadUrl, "_blank");
      setExportMessage(`??? ${data.filename}`);
    } catch (error) {
      setExportMessage(error.message);
    }
  };

  const selectHistory = async (item) => {
    setTaskId(item.task_id);
    setUploadInfo({
      file_size: null,
      page_count: item.page_count,
      pdf_type: item.pdf_type
    });
    setUploadMessage(item.filename ? `????: ${item.filename}` : `????: ${item.task_id}`);
    setTaskStatus({
      status: item.status || (item.has_result ? "completed" : "uploaded"),
      message: item.has_result ? "????" : "???",
      progress: item.has_result ? 100 : 0,
      current_page: 0,
      total_pages: item.page_count || 0
    });

    if (item.has_result) {
      try {
        const response = await fetch(`${API_BASE}/history/${item.task_id}/result`);
        if (!response.ok) throw new Error("????????");
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

  const resetAll = () => {
    setFile(null);
    setTaskId("");
    setUploadInfo(null);
    setUploadMessage("");
    setTaskStatus({
      status: "idle",
      message: "???? PDF?",
      progress: 0,
      current_page: 0,
      total_pages: 0
    });
    setResultText("");
    setExportMessage("");
  };

  return (
    <main className="min-h-screen px-6 py-10 lg:px-12">
      <div className="mx-auto flex max-w-6xl flex-col gap-10">
        <header className="flex flex-col gap-6">
          <div className="flex flex-wrap items-center justify-between gap-4">
            <div>
              <p className="text-sm uppercase tracking-[0.2em] text-slate-300">SmartPDF OCR Studio</p>
              <h1 className="section-title text-4xl font-semibold text-white sm:text-5xl">
                ?? PDF ?????
              </h1>
            </div>
            <div className="glass rounded-full px-4 py-2 text-xs text-slate-200">
              API: {API_BASE.replace("/api", "")}
            </div>
          </div>
          <p className="max-w-2xl text-base text-slate-200">
            ?? PDF??? OCR ??????????????????????????????
          </p>
        </header>

        <section className="grid gap-6 lg:grid-cols-[1.05fr_0.95fr]">
          <div className="glass rounded-3xl p-6">
            <div className="flex items-center justify-between">
              <h2 className="section-title text-2xl text-white">????</h2>
              <button
                className="rounded-full border border-slate-600 px-4 py-1 text-xs text-slate-300 hover:border-slate-400"
                onClick={resetAll}
                type="button"
              >
                ??
              </button>
            </div>

            <div className="mt-6 grid gap-4">
              <div className="rounded-2xl border border-slate-700/60 bg-slate-900/40 p-4">
                <p className="text-xs uppercase tracking-[0.3em] text-slate-400">?? 1</p>
                <h3 className="mt-2 text-lg font-semibold text-white">?? PDF</h3>
                <div className="mt-3 flex flex-col gap-3 sm:flex-row sm:items-center">
                  <label className="flex flex-1 cursor-pointer items-center justify-between rounded-xl border border-dashed border-slate-600 px-4 py-3 text-sm text-slate-300 hover:border-slate-400">
                    {file ? file.name : "?? PDF ??"}
                    <input
                      type="file"
                      accept=".pdf"
                      className="hidden"
                      onChange={(event) => setFile(event.target.files?.[0] || null)}
                    />
                  </label>
                  <button
                    className="rounded-xl bg-orange-500 px-5 py-3 text-sm font-semibold text-white shadow-lg shadow-orange-500/30 hover:bg-orange-400 disabled:cursor-not-allowed disabled:opacity-60"
                    onClick={handleUpload}
                    disabled={busy || !file}
                    type="button"
                  >
                    ??
                  </button>
                </div>
                <div className="mt-3 text-xs text-slate-300">
                  {uploadMessage || "??? PDF????????????"}
                </div>
                {uploadInfo && (
                  <div className="mt-3 grid grid-cols-2 gap-2 text-xs text-slate-400">
                    <div>????: {formatBytes(uploadInfo.file_size)}</div>
                    <div>??: {uploadInfo.page_count}</div>
                    <div>??: {uploadInfo.pdf_type}</div>
                    <div>??: {taskId.slice(0, 8)}...</div>
                  </div>
                )}
              </div>

              <div className="rounded-2xl border border-slate-700/60 bg-slate-900/40 p-4">
                <p className="text-xs uppercase tracking-[0.3em] text-slate-400">?? 2</p>
                <h3 className="mt-2 text-lg font-semibold text-white">?? OCR ??</h3>
                <div className="mt-3 grid gap-3 sm:grid-cols-2">
                  {[
                    ["preprocess", "?????"],
                    ["denoise", "??"],
                    ["binarize", "???"],
                    ["deskew", "????"]
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
                  <label className="text-xs uppercase tracking-[0.3em] text-slate-400">?? DPI</label>
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
                  <div className="mt-2 text-xs text-slate-300">??: {options.dpi} DPI</div>
                </div>
                <div className="mt-4">
                  <label className="text-xs uppercase tracking-[0.3em] text-slate-400">????</label>
                  <input
                    type="text"
                    value={pageInput}
                    onChange={(event) => setPageInput(event.target.value)}
                    placeholder="??????? 1-3,5,8"
                    className="mt-3 w-full rounded-xl border border-slate-600 bg-slate-900/60 px-3 py-2 text-sm text-slate-200"
                  />
                </div>
              </div>

              <div className="rounded-2xl border border-slate-700/60 bg-slate-900/40 p-4">
                <p className="text-xs uppercase tracking-[0.3em] text-slate-400">?? 3</p>
                <h3 className="mt-2 text-lg font-semibold text-white">?? OCR</h3>
                <div className="mt-3 flex flex-wrap gap-3">
                  <button
                    className="rounded-xl bg-teal-500 px-5 py-3 text-sm font-semibold text-white shadow-lg shadow-teal-500/30 hover:bg-teal-400 disabled:cursor-not-allowed disabled:opacity-60"
                    onClick={startOcr}
                    disabled={!taskId || busy}
                    type="button"
                  >
                    ?? OCR
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
                <p className="text-xs uppercase tracking-[0.3em] text-slate-400">?? 4</p>
                <h3 className="mt-2 text-lg font-semibold text-white">????</h3>
                <div className="mt-3 grid gap-3 sm:grid-cols-[1fr_1fr]">
                  <select
                    value={exportFormat}
                    onChange={(event) => setExportFormat(event.target.value)}
                    className="w-full rounded-xl border border-slate-600 bg-slate-900/60 px-3 py-2 text-sm text-slate-200"
                  >
                    <option value="txt">TXT</option>
                    <option value="docx">DOCX</option>
                    <option value="pdf">??? PDF</option>
                  </select>
                  <input
                    type="text"
                    value={exportTitle}
                    onChange={(event) => setExportTitle(event.target.value)}
                    placeholder="??????"
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
                    ?????
                  </button>
                  <span className="text-xs text-slate-300">{exportMessage}</span>
                </div>
              </div>
            </div>
          </div>

          <div className="glass rounded-3xl p-6">
            <div className="flex items-center justify-between">
              <h2 className="section-title text-2xl text-white">????</h2>
              <button
                className="rounded-full border border-slate-600 px-3 py-1 text-xs text-slate-300 hover:border-slate-400"
                onClick={loadHistory}
                type="button"
              >
                ??
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
                          {item.pdf_type || "-"} | {item.page_count || "-"} ? | {item.status || "-"}
                        </span>
                      </div>
                      <span className="text-[10px] text-slate-400">{item.has_result ? "???" : "???"}</span>
                    </button>
                  ))}
                </div>
              ) : (
                <div>{historyMessage}</div>
              )}
            </div>

            <div className="mt-6 flex items-center justify-between">
              <h2 className="section-title text-2xl text-white">????</h2>
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
                value={resultText || "OCR ?????????"}
                className="h-[360px] w-full resize-none rounded-2xl border border-slate-700/60 bg-slate-950/60 p-4 text-sm text-slate-200 focus:outline-none"
              />
            </div>

            <div className="mt-6 grid gap-4 rounded-2xl border border-slate-700/60 bg-slate-900/40 p-4 text-sm text-slate-200">
              <div className="flex items-center justify-between">
                <span>?? ID</span>
                <span className="text-xs text-slate-400">{taskId || "-"}</span>
              </div>
              <div className="flex items-center justify-between">
                <span>??</span>
                <span className="text-xs text-slate-400">{Math.round(taskStatus.progress)}%</span>
              </div>
              <div className="flex items-center justify-between">
                <span>??</span>
                <span className="text-xs text-slate-400">
                  {taskStatus.current_page}/{taskStatus.total_pages || "-"}
                </span>
              </div>
              <div className="flex items-center justify-between">
                <span>??</span>
                <span className="text-xs text-slate-400">{taskStatus.message}</span>
              </div>
            </div>
          </div>
        </section>

        <footer className="flex flex-col items-start justify-between gap-3 text-xs text-slate-400 sm:flex-row sm:items-center">
          <span>SmartPDF OCR ???Next.js + Tailwind??</span>
          <span>API ?? 8000????? 7860?</span>
        </footer>
      </div>
    </main>
  );
}
