import { useEditor, EditorContent } from "@tiptap/react";
import { Extension } from "@tiptap/core";
import Document from "@tiptap/extension-document";
import Paragraph from "@tiptap/extension-paragraph";
import Text from "@tiptap/extension-text";
import { Placeholder } from "@tiptap/extensions";
import { Plugin, PluginKey, TextSelection } from "@tiptap/pm/state";
import { Decoration, DecorationSet } from "@tiptap/pm/view";
import { cn } from "@/shared/lib/utils";
import { useEffect, forwardRef, useImperativeHandle, useRef } from "react";

export type CELVariableType =
  | "input"
  | "state"
  | "workflow"
  | "project"
  | "other"
  | "metadata";

// Функция для проверки, находится ли курсор внутри {{...}}
function isCursorInsideBraces(text: string, cursorPos: number): boolean {
  let openBraces = 0;
  let lastOpenPos = -1;

  for (let i = 0; i < cursorPos - 1; i++) {
    if (text[i] === "{" && text[i + 1] === "{") {
      openBraces++;
      lastOpenPos = i;
      i++; // пропускаем вторую скобку
    } else if (text[i] === "}" && text[i + 1] === "}") {
      if (openBraces > 0) {
        openBraces--;
        lastOpenPos = -1;
      }
      i++; // пропускаем вторую скобку
    }
  }

  return openBraces > 0 && lastOpenPos !== -1;
}

// Функция для анализа токена у курсора и вызова соответствующих колбэков
function analyzeTokenAtCursor(
  editor: ReturnType<typeof useEditor>,
  onShowHelpers?: (type?: CELVariableType, term?: string) => void,
  onHideHelpers?: () => void,
  highlightMode?: "always" | "inside-braces",
  disableOtherSuggestions?: boolean,
  suppressHelpersRef?: React.RefObject<boolean>
) {
  if (!editor) return;

  // Если helpers подавлены (после Enter), не показываем их
  if (suppressHelpersRef?.current) {
    onHideHelpers?.();
    return;
  }

  const { state } = editor;
  const { selection } = state;
  const cursorPos = selection.from;

  // Получаем весь текст документа
  const fullText = editor.getText();

  // Если текст пустой, показываем все подсказки
  if (!fullText.trim()) {
    onShowHelpers?.();
    return;
  }

  // Если режим inside-braces, проверяем, находится ли курсор внутри {{...}}
  if (highlightMode === "inside-braces") {
    if (!isCursorInsideBraces(fullText, cursorPos)) {
      onHideHelpers?.();
      return;
    }
  }

  // Получаем текст до курсора
  const textBeforeCursor = fullText.substring(0, cursorPos - 1); // -1 потому что позиция 1 = начало параграфа

  // Находим последний токен перед курсором
  // Разделители: пробелы, операторы, скобки и т.д.
  const tokenMatch = textBeforeCursor.match(/[^\s+\-*/()[\]{},;:]+$/);
  const currentToken = tokenMatch ? tokenMatch[0] : "";

  // 1. Проверяем: начинается ли ввод переменной (частичный ввод input/state/workflow/project/metadata)
  const partialVarMatch = currentToken.match(
    /^(i|in|inp|inpu|input|s|st|sta|stat|state|w|wo|wor|work|workf|workfl|workflo|workflow|p|pr|pro|proj|proje|projec|project|m|me|met|meta|metad|metada|metadat|metadata)$/
  );
  if (partialVarMatch) {
    onShowHelpers?.();
    return;
  }

  // 2. Проверяем: переменная с точкой и термином (input.foo, state.bar, project.baz, metadata.qux)
  const varWithTermMatch = currentToken.match(
    /^(input|state|workflow|project|metadata)\.([a-zA-Z0-9_]*)$/
  );
  if (varWithTermMatch) {
    const varType = varWithTermMatch[1] as CELVariableType;
    const term = varWithTermMatch[2];
    onShowHelpers?.(varType, term);
    return;
  }

  // 3. Проверяем: переменная только с точкой (input., state., workflow., project., metadata.)
  const varWithDotMatch = currentToken.match(
    /^(input|state|workflow|project|metadata)\.$/
  );
  if (varWithDotMatch) {
    const varType = varWithDotMatch[1] as CELVariableType;
    onShowHelpers?.(varType);
    return;
  }

  // 4. Проверяем: пробел после значения (для подсказки операторов)
  // Пропускаем, если disableOtherSuggestions=true
  if (!disableOtherSuggestions && textBeforeCursor.match(/[^\s]\s+$/)) {
    // Список операторов, после которых не нужно показывать подсказки
    const operators = ["==", "!=", "<=", ">=", "<", ">", "?", "||", "&&"];

    // Проверяем, не заканчивается ли текст перед пробелом на оператор
    const trimmedText = textBeforeCursor.trim();
    const endsWithOperator = operators.some((op) => trimmedText.endsWith(op));

    if (endsWithOperator) {
      // Если последнее что ввели - оператор, не показываем подсказки
      onHideHelpers?.();
      return;
    }

    // Проверяем, что перед пробелом не было частичной переменной (незаконченный ввод типа "inp", "st", "pr")
    const tokenBeforeSpace =
      trimmedText.match(/[^\s+\-*/()[\]{},;:!=<>?|&]+$/)?.[0] || "";
    const isNotPartialVar = !tokenBeforeSpace.match(
      /^(in|inp|inpu|input|st|sta|stat|state|wo|wor|work|workf|workfl|workflo|workflow|pr|pro|proj|proje|projec|project|m|me|met|meta|metad|metada|metadat|metadata)$/
    );

    // Если перед пробелом есть текст и это не частичная переменная без точки
    if (isNotPartialVar && tokenBeforeSpace.length > 0) {
      onShowHelpers?.("other");
      return;
    }
  }

  // 5. Иначе - скрываем подсказки
  onHideHelpers?.();
}

// Расширение для подсветки CEL переменных
const CELHighlight = (highlightMode: "always" | "inside-braces" = "always") =>
  Extension.create({
    name: "celHighlight",

    addProseMirrorPlugins() {
      return [
        new Plugin({
          key: new PluginKey("celHighlight"),
          props: {
            decorations: (state) => {
              const decorations: Decoration[] = [];
              const doc = state.doc;

              doc.descendants((node, pos) => {
                if (!node.isText) return;

                const text = node.text || "";

                if (highlightMode === "inside-braces") {
                  // Режим подсветки только внутри {{...}}
                  const braceRegex = /\{\{([^}]+)\}\}/g;
                  let braceMatch;

                  while ((braceMatch = braceRegex.exec(text)) !== null) {
                    const braceStart = pos + braceMatch.index;
                    const braceEnd = braceStart + braceMatch[0].length;
                    const innerContent = braceMatch[1];
                    const innerStart = braceStart + 2; // после {{

                    // Подсвечиваем фигурные скобки
                    decorations.push(
                      Decoration.inline(braceStart, braceStart + 2, {
                        class: "cel-braces",
                      })
                    );
                    decorations.push(
                      Decoration.inline(braceEnd - 2, braceEnd, {
                        class: "cel-braces",
                      })
                    );

                    // Подсветка строк внутри скобок
                    const stringRegex = /'[^']*'|"[^"]*"/g;
                    let match;
                    while ((match = stringRegex.exec(innerContent)) !== null) {
                      const from = innerStart + match.index;
                      const to = from + match[0].length;
                      decorations.push(
                        Decoration.inline(from, to, {
                          class: "cel-string",
                        })
                      );
                    }

                    // Подсветка чисел внутри скобок
                    const numberRegex = /\b\d+(\.\d+)?\b/g;
                    while ((match = numberRegex.exec(innerContent)) !== null) {
                      const from = innerStart + match.index;
                      const to = from + match[0].length;
                      decorations.push(
                        Decoration.inline(from, to, {
                          class: "cel-number",
                        })
                      );
                    }

                    // Подсветка CEL переменных внутри скобок
                    const celRegex =
                      /\b(input|state|workflow|project|metadata)(\.[a-zA-Z0-9_[\]]+)+/g;
                    while ((match = celRegex.exec(innerContent)) !== null) {
                      const from = innerStart + match.index;
                      const to = from + match[0].length;
                      decorations.push(
                        Decoration.inline(from, to, {
                          class: "cel-variable",
                        })
                      );
                    }

                    // ОШИБКИ внутри скобок
                    const incompleteVarRegex =
                      /\b(input|state|workflow|project|metadata)\.\s*(?![a-zA-Z0-9_[\]])/g;
                    while (
                      (match = incompleteVarRegex.exec(innerContent)) !== null
                    ) {
                      const from = innerStart + match.index;
                      const to = from + match[0].length;
                      decorations.push(
                        Decoration.inline(from, to, {
                          class: "cel-error",
                        })
                      );
                    }
                  }
                } else {
                  // Режим подсветки везде (по умолчанию)
                  // 1. Подсветка строк: '...' или "..."
                  const stringRegex = /'[^']*'|"[^"]*"/g;
                  let match;
                  while ((match = stringRegex.exec(text)) !== null) {
                    const from = pos + match.index;
                    const to = from + match[0].length;
                    decorations.push(
                      Decoration.inline(from, to, {
                        class: "cel-string",
                      })
                    );
                  }

                  // 2. Подсветка чисел
                  const numberRegex = /\b\d+(\.\d+)?\b/g;
                  while ((match = numberRegex.exec(text)) !== null) {
                    const from = pos + match.index;
                    const to = from + match[0].length;
                    decorations.push(
                      Decoration.inline(from, to, {
                        class: "cel-number",
                      })
                    );
                  }

                  // 3. Подсветка CEL переменных: input.*, state.*, workflow.*, project.*, metadata.*
                  const celRegex =
                    /\b(input|state|workflow|project|metadata)(\.[a-zA-Z0-9_[\]]+)+/g;
                  while ((match = celRegex.exec(text)) !== null) {
                    const from = pos + match.index;
                    const to = from + match[0].length;
                    decorations.push(
                      Decoration.inline(from, to, {
                        class: "cel-variable",
                      })
                    );
                  }

                  // 4. ОШИБКИ: input., state., workflow., project., metadata. без продолжения
                  const incompleteVarRegex =
                    /\b(input|state|workflow|project|metadata)\.\s*(?![a-zA-Z0-9_[\]])/g;
                  while ((match = incompleteVarRegex.exec(text)) !== null) {
                    const from = pos + match.index;
                    const to = from + match[0].length;
                    decorations.push(
                      Decoration.inline(from, to, {
                        class: "cel-error",
                      })
                    );
                  }
                }
              });

              return DecorationSet.create(doc, decorations);
            },
          },
        }),
      ];
    },
  });

interface CELInputProps {
  value?: string;
  onChange?: (value: string) => void;
  placeholder?: string;
  className?: string;
  id?: string;
  onShowHelpers?: (type?: CELVariableType, term?: string) => void;
  onHideHelpers?: () => void;
}

export function CELInput({
  value = "",
  onChange,
  placeholder = "input.foo",
  className,
  id,
  onShowHelpers,
  onHideHelpers,
}: CELInputProps) {
  const editor = useEditor({
    extensions: [
      Document,
      Paragraph.configure({
        HTMLAttributes: {
          class: "m-0",
        },
      }),
      Text,
      CELHighlight("always"),
      Placeholder.configure({
        placeholder,
      }),
    ],
    content: value,
    editorProps: {
      attributes: {
        class: "outline-none",
      },
      handleKeyDown: (_view, event) => {
        // Блокируем Enter для предотвращения переноса строк
        if (event.key === "Enter") {
          event.preventDefault();
          return true;
        }
        return false;
      },
      handlePaste: (view, event) => {
        event.preventDefault();

        // Получаем вставляемый текст (только plain text, игнорируем HTML)
        const text = event.clipboardData?.getData("text/plain");
        if (text) {
          // Удаляем все переносы строк и заменяем их пробелами
          const singleLineText = text.replace(/[\r\n]+/g, " ").trim();

          if (singleLineText) {
            // Вставляем очищенный текст
            const { state } = view;
            const { tr } = state;
            tr.insertText(singleLineText);
            view.dispatch(tr);
          }
        }
        return true;
      },
    },
    onUpdate: ({ editor }) => {
      let text = editor.getText();
      // Удаляем переносы строк, если они каким-то образом появились
      text = text.replace(/[\r\n]+/g, " ");
      onChange?.(text);

      // Анализируем токен у курсора для подсказок
      analyzeTokenAtCursor(
        editor,
        onShowHelpers,
        onHideHelpers,
        "always",
        false
      );
    },
    onFocus: ({ editor }) => {
      // При фокусе на пустом поле показываем все подсказки
      const text = editor.getText().trim();
      if (!text) {
        onShowHelpers?.();
      } else {
        // Иначе анализируем токен у курсора
        analyzeTokenAtCursor(
          editor,
          onShowHelpers,
          onHideHelpers,
          "always",
          false
        );
      }
    },
    onSelectionUpdate: ({ editor }) => {
      // Анализируем токен при перемещении курсора
      analyzeTokenAtCursor(
        editor,
        onShowHelpers,
        onHideHelpers,
        "always",
        false
      );
    },
  });

  // Синхронизация внешнего value с редактором
  useEffect(() => {
    if (editor && value !== editor.getText()) {
      editor.commands.setContent(value);
    }
  }, [value, editor]);

  const handleContainerClick = (e: React.MouseEvent) => {
    if (!editor) return;

    const target = e.target as HTMLElement;
    const isProseMirror = target.classList.contains("ProseMirror");
    const isInsideProseMirror = target.closest(".ProseMirror");

    // Если кликнули на контейнер, а не внутри редактора
    if (!isProseMirror && !isInsideProseMirror) {
      e.preventDefault();
      // Устанавливаем курсор в начало документа (позиция 1 = после открывающего тега параграфа)
      editor.chain().focus().setTextSelection(1).run();
    }
  };

  return (
    <div className={cn("relative w-full min-w-0", className)} id={id}>
      <div
        onClick={handleContainerClick}
        className={cn(
          "cel-input-container",
          "border-input placeholder:text-muted-foreground selection:bg-primary selection:text-primary-foreground",
          "h-9 w-full min-w-0 rounded-md border bg-transparent px-3 py-1 shadow-xs transition-[color,box-shadow] outline-none",
          "focus-within:border-ring focus-within:ring-ring/50 focus-within:ring-[3px]",
          "aria-invalid:ring-destructive/20 aria-invalid:border-destructive",
          "overflow-x-auto overflow-y-hidden"
        )}
      >
        <EditorContent editor={editor} className="text-xs  w-full" />
      </div>
    </div>
  );
}

interface CELTextareaProps {
  value?: string;
  onChange?: (value: string) => void;
  placeholder?: string;
  className?: string;
  id?: string;
  onShowHelpers?: (type?: CELVariableType, term?: string) => void;
  onHideHelpers?: () => void;
  highlightMode?: "always" | "inside-braces";
  disableOtherSuggestions?: boolean;
  isHelpersVisible?: boolean;
}

export interface CELTextareaRef {
  insertText: (text: string) => void;
  replaceCurrentToken: (text: string) => void;
  focus: () => void;
  getCursorCoords: () => {
    left: number;
    right: number;
    top: number;
    bottom: number;
  } | null;
}

export const CELTextarea = forwardRef<CELTextareaRef, CELTextareaProps>(
  (
    {
      value = "",
      onChange,
      placeholder = "input.foo",
      className,
      id,
      onShowHelpers,
      onHideHelpers,
      highlightMode = "always",
      disableOtherSuggestions = false,
      isHelpersVisible = false,
    },
    ref
  ) => {
    const suppressHelpersRef = useRef(false);

    // Функция для получения текста с переносами строк
    const getTextWithNewlines = (editor: ReturnType<typeof useEditor>) => {
      if (!editor) return "";
      const doc = editor.state.doc;
      const paragraphs: string[] = [];
      doc.forEach((node) => {
        paragraphs.push(node.textContent);
      });
      return paragraphs.join("\n");
    };

    // Функция для конвертации plain text с \n в HTML параграфы
    const convertTextToHtml = (text: string) => {
      return text
        .split("\n")
        .map((line) => `<p>${line || "<br>"}</p>`)
        .join("");
    };

    const editor = useEditor({
      extensions: [
        Document,
        Paragraph.configure({
          HTMLAttributes: {
            class: "m-0",
          },
        }),
        Text,
        CELHighlight(highlightMode),
        Placeholder.configure({
          placeholder,
        }),
      ],
      content: convertTextToHtml(value),
      editorProps: {
        attributes: {
          class: "outline-none",
        },
        handleKeyDown: (view, event) => {
          // Автопара: при вводе второй { автоматически добавляем }}
          // и ставим курсор между {{ и }}
          if (
            event.key === "{" &&
            !event.ctrlKey &&
            !event.metaKey &&
            !event.altKey
          ) {
            const { selection, doc } = view.state;
            if (selection.empty) {
              const cursorPos = selection.from;
              const fullText = doc.textBetween(0, doc.content.size, "\n", "\n");
              const charBeforeCursor = fullText[cursorPos - 2];
              if (charBeforeCursor === "{") {
                event.preventDefault();
                const tr = view.state.tr.insertText("{}}", cursorPos);
                tr.setSelection(
                  TextSelection.create(tr.doc, cursorPos + 1)
                );
                view.dispatch(tr);
                return true;
              }
            }
          }

          // Если Enter нажат когда подсказки не видны,
          // подавляем показ подсказок на короткое время (100ms)
          // чтобы предотвратить повторное открытие popover
          if (event.key === "Enter" && !isHelpersVisible) {
            suppressHelpersRef.current = true;
            setTimeout(() => {
              suppressHelpersRef.current = false;
            }, 100);
          }

          // Если подсказки НЕ видны, разрешаем Enter для переноса строки
          if (!isHelpersVisible) {
            return false; // Не блокируем ничего
          }

          // Если подсказки видны:
          // - Блокируем Enter без модификаторов (будет обработан popover)
          // - Разрешаем Shift+Enter для переноса строки
          if (event.key === "Enter" && !event.shiftKey) {
            event.preventDefault();
            return true;
          }

          // Разрешаем Shift+Enter и все остальные клавиши
          return false;
        },
      },
      onUpdate: ({ editor }) => {
        const text = getTextWithNewlines(editor);
        onChange?.(text);

        // Анализируем токен у курсора для подсказок
        analyzeTokenAtCursor(
          editor,
          onShowHelpers,
          onHideHelpers,
          highlightMode,
          disableOtherSuggestions,
          suppressHelpersRef
        );
      },
      onFocus: ({ editor }) => {
        // При фокусе на пустом поле показываем все подсказки
        const text = editor.getText().trim();
        if (!text) {
          // Не показываем подсказки на пустом поле, если disableOtherSuggestions=true
          if (!disableOtherSuggestions) {
            onShowHelpers?.();
          }
        } else {
          // Иначе анализируем токен у курсора
          analyzeTokenAtCursor(
            editor,
            onShowHelpers,
            onHideHelpers,
            highlightMode,
            disableOtherSuggestions,
            suppressHelpersRef
          );
        }
      },
      onSelectionUpdate: ({ editor }) => {
        // Анализируем токен при перемещении курсора
        analyzeTokenAtCursor(
          editor,
          onShowHelpers,
          onHideHelpers,
          highlightMode,
          disableOtherSuggestions,
          suppressHelpersRef
        );
      },
    });

    // Синхронизация внешнего value с редактором
    useEffect(() => {
      if (editor && value !== getTextWithNewlines(editor)) {
        editor.commands.setContent(convertTextToHtml(value));
      }
    }, [value, editor]);

    // Экспортируем методы через ref
    useImperativeHandle(
      ref,
      () => ({
        insertText: (text: string) => {
          if (editor) {
            editor.chain().focus().insertContent(text).run();
          }
        },
        replaceCurrentToken: (text: string) => {
          if (!editor) return;

          const { state } = editor;
          const { selection } = state;
          const cursorPos = selection.from;

          // Получаем весь текст документа (используем getText для работы с позициями)
          const fullText = editor.getText();

          // В режиме inside-braces оборачиваем в {{}} если курсор не внутри скобок
          const finalText =
            highlightMode === "inside-braces" &&
            !isCursorInsideBraces(fullText, cursorPos)
              ? `{{${text}}}`
              : text;

          // Получаем текст до курсора
          const textBeforeCursor = fullText.substring(0, cursorPos - 1);

          // Находим последний токен перед курсором
          const tokenMatch = textBeforeCursor.match(/[^\s+\-*/()[\]{},;:]+$/);

          if (tokenMatch) {
            const tokenLength = tokenMatch[0].length;
            const tokenStart = cursorPos - tokenLength;

            // Удаляем токен и вставляем новый текст
            editor
              .chain()
              .focus()
              .deleteRange({ from: tokenStart, to: cursorPos })
              .insertContent(finalText)
              .run();
          } else {
            // Если токен не найден, просто вставляем текст
            editor.chain().focus().insertContent(finalText).run();
          }
        },
        focus: () => {
          if (editor) {
            editor.chain().focus().run();
          }
        },
        getCursorCoords: () => {
          if (!editor) return null;
          const { state, view } = editor;
          const pos = state.selection.from;
          try {
            const coords = view.coordsAtPos(pos);
            return {
              left: coords.left,
              right: coords.right,
              top: coords.top,
              bottom: coords.bottom,
            };
          } catch {
            return null;
          }
        },
      }),
      [editor]
    );

    const handleTextareaClick = (e: React.MouseEvent) => {
      if (!editor) return;

      const target = e.target as HTMLElement;
      const isProseMirror = target.classList.contains("ProseMirror");
      const isInsideProseMirror = target.closest(".ProseMirror");

      // Если кликнули на контейнер, а не внутри редактора
      if (!isProseMirror && !isInsideProseMirror) {
        e.preventDefault();
        // Устанавливаем курсор в начало документа (позиция 1 = после открывающего тега параграфа)
        editor.chain().focus().setTextSelection(1).run();
      }
    };

    return (
      <div
        className={cn(
          "cel-textarea-container relative w-full pb-8!",
          "border-input placeholder:text-muted-foreground focus-within:border-ring focus-within:ring-ring/50",
          "aria-invalid:ring-destructive/20 dark:aria-invalid:ring-destructive/40 aria-invalid:border-destructive dark:bg-input/30",
          "flex flex-col min-h-16 rounded-md border bg-transparent px-3 py-2 shadow-xs transition-[color,box-shadow] outline-none",
          "focus-within:ring-[3px] resize-none overflow-hidden",
          "cursor-text",
          className
        )}
        id={id}
        onClick={handleTextareaClick}
      >
        <div className="flex-1 overflow-y-auto">
          <EditorContent
            editor={editor}
            className="text-base md:text-sm w-full break-all"
          />
        </div>
      </div>
    );
  }
);
