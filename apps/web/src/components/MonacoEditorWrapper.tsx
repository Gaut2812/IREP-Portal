"use client";

import React from "react";
import dynamic from "next/dynamic";

const MONACO_LANG_MAP: Record<string, string> = {
  python: "python",
  java: "java",
  cpp: "cpp",
  javascript: "javascript",
};

const Editor = dynamic(() => import("@monaco-editor/react"), {
  ssr: false,
  loading: () => (
    <div className="w-full h-full bg-[#1B2236] animate-pulse flex items-center justify-center text-xs text-[#64748B] font-mono">
      Loading Code Editor...
    </div>
  ),
});

interface MonacoEditorWrapperProps {
  value: string;
  language: string;
  onChange: (val: string) => void;
  readOnly?: boolean;
}

export const MonacoEditorWrapper: React.FC<MonacoEditorWrapperProps> = ({
  value,
  language,
  onChange,
  readOnly = false,
}) => {
  const monacoLang = MONACO_LANG_MAP[language] || "python";

  return (
    <div className="w-full h-full min-h-[350px]">
      <Editor
        height="100%"
        width="100%"
        language={monacoLang}
        value={value}
        theme="vs-dark"
        onChange={(val) => onChange(val || "")}
        options={{
          fontSize: 13,
          fontFamily: "'JetBrains Mono', 'Fira Code', 'Cascadia Code', Consolas, monospace",
          fontLigatures: true,
          minimap: { enabled: false },
          scrollBeyondLastLine: false,
          wordWrap: "on",
          lineNumbers: "on",
          renderLineHighlight: "line",
          cursorStyle: "line",
          automaticLayout: true,
          tabSize: 4,
          insertSpaces: true,
          readOnly,
          padding: { top: 12, bottom: 12 },
          scrollbar: {
            verticalScrollbarSize: 8,
            horizontalScrollbarSize: 8,
          },
          overviewRulerLanes: 0,
        }}
      />
    </div>
  );
};

