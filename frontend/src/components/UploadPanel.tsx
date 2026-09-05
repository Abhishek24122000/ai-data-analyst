import { useRef, useState } from "react";

interface Props {
  onUpload: (file: File) => Promise<void>;
  onLoadSample: () => Promise<void>;
  loading: boolean;
}

export default function UploadPanel({ onUpload, onLoadSample, loading }: Props) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [dragOver, setDragOver] = useState(false);

  const handleFiles = (files: FileList | null) => {
    if (files && files[0]) onUpload(files[0]);
  };

  return (
    <div className="flex flex-col items-center justify-center h-full gap-6 px-8 text-center">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">AI Data Analyst</h1>
        <p className="text-sm text-slate-400 mt-2 max-w-md">
          Upload a CSV/Excel file, or load the built-in sample sales dataset, to start asking
          natural-language questions backed by validated SQL.
        </p>
      </div>

      <div
        onDragOver={(e) => {
          e.preventDefault();
          setDragOver(true);
        }}
        onDragLeave={() => setDragOver(false)}
        onDrop={(e) => {
          e.preventDefault();
          setDragOver(false);
          handleFiles(e.dataTransfer.files);
        }}
        onClick={() => inputRef.current?.click()}
        className={`w-full max-w-md border-2 border-dashed rounded-xl py-10 px-6 cursor-pointer transition-colors ${
          dragOver ? "border-accent bg-accent/10" : "border-slate-700 hover:border-slate-500"
        }`}
      >
        <p className="font-medium">Drop a CSV / Excel file here</p>
        <p className="text-xs text-slate-500 mt-1">or click to browse (max 50 MB)</p>
        <input
          ref={inputRef}
          type="file"
          accept=".csv,.xlsx,.xls,.tsv"
          className="hidden"
          onChange={(e) => handleFiles(e.target.files)}
        />
      </div>

      <div className="flex items-center gap-3 text-slate-500 text-xs w-full max-w-md">
        <div className="flex-1 h-px bg-slate-800" />
        or
        <div className="flex-1 h-px bg-slate-800" />
      </div>

      <button
        onClick={() => onLoadSample()}
        disabled={loading}
        className="px-5 py-2.5 rounded-lg bg-accent hover:bg-indigo-500 transition-colors font-medium disabled:opacity-50"
      >
        {loading ? "Loading..." : "Load sample sales dataset"}
      </button>
    </div>
  );
}
