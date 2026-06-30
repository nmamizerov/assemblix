import { useMemo, useState, useEffect, useCallback } from "react";
import { createPortal } from "react-dom";
import type { CELTextareaRef, CELVariableType } from "@/shared/ui/cel-input";
import type { Workflow, StateVariable } from "@/entities/workflow/model/types";
import { AvailableVariables } from "./availableVariables";

interface VariableSuggestionsPopoverProps {
  showHelpers: {
    index: number;
    type?: CELVariableType;
    term?: string;
  } | null;
  workflow: Workflow;
  currentNodeId?: string;
  getTextareaContainerRef: (index: number) => HTMLDivElement | null;
  getTextareaRef: (index: number) => CELTextareaRef | null;
  onClose: () => void;
}

type FlatItem = {
  type: "variable" | "operator";
  prefix?: string;
  variable?: StateVariable;
  operator?: string;
};

export const VariableSuggestionsPopover = ({
  showHelpers,
  workflow,
  currentNodeId,
  getTextareaContainerRef,
  getTextareaRef,
  onClose,
}: VariableSuggestionsPopoverProps) => {
  const POPOVER_WIDTH = 300;
  const VIEWPORT_MARGIN = 8;

  // Состояние для выбранного элемента
  const [selectedIndex, setSelectedIndex] = useState(0);

  // Плоский список всех элементов для навигации
  const [flatItems, setFlatItems] = useState<FlatItem[]>([]);

  // Коллбэк для получения списка элементов от AvailableVariables
  const handleItemsChange = useCallback(
    (items: FlatItem[]) => {
      setFlatItems(items);
      // Сброс индекса, если он выходит за пределы
      setSelectedIndex((prev) => (prev >= items.length ? 0 : prev));
    },
    [setSelectedIndex]
  );

  // Обработчик вставки выбранного элемента
  const handleInsertSelected = useCallback(() => {
    if (!showHelpers || flatItems.length === 0) return;

    const selectedItem = flatItems[selectedIndex];
    if (!selectedItem) return;

    const textareaRef = getTextareaRef(showHelpers.index);
    if (!textareaRef) return;

    let textToInsert = "";
    if (
      selectedItem.type === "variable" &&
      selectedItem.variable &&
      selectedItem.prefix
    ) {
      textToInsert = `${selectedItem.prefix}.${selectedItem.variable.name}`;
    } else if (selectedItem.type === "operator" && selectedItem.operator) {
      textToInsert = ` ${selectedItem.operator} `;
    }

    if (textToInsert) {
      textareaRef.replaceCurrentToken(textToInsert);
      onClose();
    }
  }, [showHelpers, flatItems, selectedIndex, getTextareaRef, onClose]);

  // Обработчик клавиш
  useEffect(() => {
    if (!showHelpers) return;

    const handleKeyDown = (event: KeyboardEvent) => {
      if (!flatItems.length) return;

      // Игнорируем все события с модификаторами (кроме Escape)
      // Это позволяет Shift+Enter работать для переноса строки
      if (
        event.key !== "Escape" &&
        (event.shiftKey || event.ctrlKey || event.metaKey || event.altKey)
      ) {
        return;
      }

      switch (event.key) {
        case "ArrowDown":
          event.preventDefault();
          setSelectedIndex((prev) => (prev + 1) % flatItems.length);
          break;
        case "ArrowUp":
          event.preventDefault();
          setSelectedIndex(
            (prev) => (prev - 1 + flatItems.length) % flatItems.length
          );
          break;
        case "Enter":
          event.preventDefault();
          handleInsertSelected();
          break;
        case "Escape":
          event.preventDefault();
          onClose();
          break;
      }
    };

    document.addEventListener("keydown", handleKeyDown);
    return () => {
      document.removeEventListener("keydown", handleKeyDown);
    };
  }, [showHelpers, flatItems, handleInsertSelected, onClose]);

  // Вычисляем позицию popover напрямую при рендере
  const popoverPosition = useMemo(() => {
    if (!showHelpers) return null;

    const textareaContainerRef = getTextareaContainerRef(showHelpers.index);
    const textareaRef = getTextareaRef(showHelpers.index);

    // 1) Пытаемся якориться к курсору (критично для модалки)
    const cursorCoords = textareaRef?.getCursorCoords?.();
    if (cursorCoords) {
      // По умолчанию показываем справа от курсора
      const preferredLeft = cursorCoords.left + VIEWPORT_MARGIN;
      const canShowRight =
        window.innerWidth - preferredLeft >= POPOVER_WIDTH + VIEWPORT_MARGIN;

      const left = canShowRight
        ? preferredLeft
        : cursorCoords.left - VIEWPORT_MARGIN;

      const transformX = canShowRight ? "" : " translateX(-100%)";

      // По умолчанию показываем под курсором, но если не помещается — над ним
      const preferredTop = cursorCoords.bottom + VIEWPORT_MARGIN;
      const minPopoverVisibleHeight = 160;
      const canShowBelow =
        window.innerHeight - preferredTop >= minPopoverVisibleHeight;

      const top = canShowBelow
        ? preferredTop
        : cursorCoords.top - VIEWPORT_MARGIN;

      const transformY = canShowBelow ? "" : " translateY(-100%)";

      const maxHeight = canShowBelow
        ? Math.max(
            minPopoverVisibleHeight,
            window.innerHeight - top - VIEWPORT_MARGIN
          )
        : Math.max(minPopoverVisibleHeight, top - VIEWPORT_MARGIN);

      return {
        top,
        left,
        transform: `${transformX}${transformY}`.trim() || undefined,
        maxHeight,
      };
    }

    // 2) Фолбек: якоримся к контейнеру (старое поведение)
    if (!textareaContainerRef) return null;

    const rect = textareaContainerRef.getBoundingClientRect();
    return {
      top: rect.top,
      left: rect.left - 8, // 8px отступ
      transform: "translateX(-100%)",
      maxHeight: Math.max(160, window.innerHeight - rect.top - VIEWPORT_MARGIN),
    };
  }, [showHelpers, getTextareaContainerRef, getTextareaRef]);

  // Не рендерим popover если подсказки не нужны или позиция не вычислена
  if (!showHelpers || !popoverPosition) {
    return null;
  }

  return createPortal(
    <div
      className="fixed w-[300px] max-w-[calc(100vw-16px)] overflow-y-auto rounded-md border bg-popover text-popover-foreground shadow-md outline-none"
      style={{
        top: `${popoverPosition.top}px`,
        left: `${popoverPosition.left}px`,
        transform: popoverPosition.transform,
        maxHeight: `${popoverPosition.maxHeight}px`,
        zIndex: 9999,
      }}
    >
      <AvailableVariables
        term={showHelpers.term}
        type={showHelpers.type}
        workflow={workflow}
        currentNodeId={currentNodeId}
        selectedIndex={selectedIndex}
        onItemsChange={handleItemsChange}
        onInsertText={(text) => {
          const textareaRef = getTextareaRef(showHelpers.index);
          textareaRef?.replaceCurrentToken(text);
        }}
        onSelect={onClose}
      />
    </div>,
    document.body
  );
};
