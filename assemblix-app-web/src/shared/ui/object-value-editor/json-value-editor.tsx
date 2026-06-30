import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import CodeMirror from "@uiw/react-codemirror";
import { json } from "@codemirror/lang-json";
import type { JsonObject } from "./types";

interface JsonValueEditorProps {
  value: JsonObject;
  onChange: (value: JsonObject) => void;
  height?: string;
}

// Приводит JSON-строку к канонической форме, чтобы сравнивать содержимое,
// а не форматирование. При невалидном JSON возвращает исходную строку.
const normalizeJson = (val: string): string => {
  try {
    return JSON.stringify(JSON.parse(val));
  } catch {
    return val;
  }
};

export const JsonValueEditor = ({
  value,
  onChange,
  height = "280px",
}: JsonValueEditorProps) => {
  const { t } = useTranslation();
  const incomingJson = useMemo(
    () => JSON.stringify(value ?? {}, null, 2),
    [value],
  );
  const [text, setText] = useState(incomingJson);
  const [error, setError] = useState<string | null>(null);
  const [isDark, setIsDark] = useState(() =>
    document.documentElement.classList.contains("dark"),
  );
  const debounceRef = useRef<ReturnType<typeof setTimeout>>(undefined);
  // Каноническая форма последнего значения, которое редактор сам отправил
  // наверх — чтобы отличать «эхо» собственной правки от внешнего изменения.
  const [lastEmitted, setLastEmitted] = useState<string | null>(null);

  useEffect(() => {
    const observer = new MutationObserver(() => {
      setIsDark(document.documentElement.classList.contains("dark"));
    });
    observer.observe(document.documentElement, {
      attributes: true,
      attributeFilter: ["class"],
    });
    return () => observer.disconnect();
  }, []);

  // Подхватываем внешние изменения значения (правки в конструкторе) во время
  // рендера — официальный React-паттерн синхронизации state с пропом.
  // Не перетираем правку пользователя, если пришло «эхо» его же изменения.
  const [prevIncoming, setPrevIncoming] = useState(incomingJson);
  if (incomingJson !== prevIncoming) {
    setPrevIncoming(incomingJson);
    if (normalizeJson(incomingJson) !== lastEmitted) {
      setText(incomingJson);
      setError(null);
    }
  }

  const handleChange = useCallback(
    (val: string) => {
      setText(val);

      if (debounceRef.current) {
        clearTimeout(debounceRef.current);
      }

      debounceRef.current = setTimeout(() => {
        if (val.trim() === "") {
          setError(null);
          setLastEmitted(JSON.stringify({}));
          onChange({});
          return;
        }
        try {
          const parsed = JSON.parse(val);
          if (
            typeof parsed !== "object" ||
            parsed === null ||
            Array.isArray(parsed)
          ) {
            setError(t("objectValueEditor.mustBeObject"));
            return;
          }
          setError(null);
          setLastEmitted(JSON.stringify(parsed));
          onChange(parsed as JsonObject);
        } catch {
          setError(t("objectValueEditor.invalidJson"));
        }
      }, 300);
    },
    [onChange, t],
  );

  useEffect(() => {
    return () => {
      if (debounceRef.current) {
        clearTimeout(debounceRef.current);
      }
    };
  }, []);

  return (
    <div className="space-y-2">
      <div className="border rounded-lg overflow-hidden">
        <CodeMirror
          value={text}
          height={height}
          theme={isDark ? "dark" : "light"}
          extensions={[json()]}
          basicSetup={{
            lineNumbers: true,
            bracketMatching: true,
            foldGutter: true,
            highlightActiveLine: true,
            autocompletion: false,
          }}
          onChange={handleChange}
        />
      </div>
      {error && <p className="text-xs text-destructive">{error}</p>}
    </div>
  );
};
