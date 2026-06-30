import { useState, useEffect } from "react";
import { useTranslation } from "react-i18next";
import { BaseForm } from "./base-form";
import { useNodeDataChange } from "./useNodeDataChange";
import { Label } from "@/shared/ui/label";
import { NodeType, type StickerNodeConfig } from "../../../../model/types";
import { Textarea } from "@/shared/ui/textarea";

interface StickerNodeFormProps {
  nodeId: string;
  config?: StickerNodeConfig;
  projectId?: string;
}

const defaultConfig: StickerNodeConfig = {
  text: "",
};

export const StickerNodeForm = ({ nodeId, config, projectId }: StickerNodeFormProps) => {
  const { t } = useTranslation();
  const initialConfig = config || defaultConfig;
  const [formData, setFormData] = useState<StickerNodeConfig>(initialConfig);
  const handleDataChange = useNodeDataChange(nodeId);

  // Вызываем handleDataChange при каждом изменении formData
  useEffect(() => {
    handleDataChange(formData);
  }, [formData, handleDataChange]);

  const handleTextChange = (value: string) => {
    setFormData((prev) => ({ ...prev, text: value }));
  };

  return (
    <BaseForm nodeType={NodeType.STICKER} label={t("nodeForms.sticker.title")} projectId={projectId}>
      <div className="space-y-4">
        {/* Название */}
        <div className="space-y-2">
          <Label htmlFor="end-name">{t("nodeForms.sticker.text")}</Label>
          <Textarea
            id="sticker-text"
            value={formData.text}
            onChange={(e) => handleTextChange(e.target.value)}
            placeholder={t("nodeForms.sticker.placeholder")}
          />
        </div>
      </div>
    </BaseForm>
  );
};
