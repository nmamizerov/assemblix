import { memo, useCallback } from "react";
import type { Node, NodeProps, ResizeDragEvent, ResizeParams } from "@xyflow/react";
import { NodeResizer, useReactFlow } from "@xyflow/react";
import { useTranslation } from "react-i18next";

import { NodeType, type StickerNodeConfig } from "../../../../model/types";

export const StickerNode = memo(
  ({
    id,
    data,
    selected,
  }: NodeProps<Node<StickerNodeConfig, NodeType.STICKER>>) => {
    const { t } = useTranslation();
    const { updateNodeData } = useReactFlow();

    const handleTextChange = useCallback(
      (e: React.ChangeEvent<HTMLTextAreaElement>) => {
        updateNodeData(id, { text: e.target.value });
      },
      [id, updateNodeData],
    );

    const handleResizeEnd = useCallback(
      (_: ResizeDragEvent, params: ResizeParams) => {
        updateNodeData(id, { width: params.width, height: params.height });
      },
      [id, updateNodeData],
    );

    return (
      <>
        <NodeResizer
          isVisible={selected}
          minWidth={150}
          minHeight={80}
          lineClassName="border-yellow-500"
          handleClassName="h-2 w-2 rounded bg-yellow-500"
          onResizeEnd={handleResizeEnd}
        />
        <div className="w-full h-full bg-yellow-200 border-2 border-yellow-400 rounded-lg p-2 flex flex-col">
          <textarea
            value={data.text}
            onChange={handleTextChange}
            placeholder={t("nodeForms.sticker.placeholder")}
            className="nodrag nopan nowheel w-full h-full bg-transparent resize-none text-yellow-900 text-sm leading-relaxed placeholder:text-yellow-600/60 outline-none"
          />
        </div>
      </>
    );
  },
);
