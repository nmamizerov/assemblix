import { useState, useEffect, useCallback, useRef, useMemo } from "react";
import { useTranslation } from "react-i18next";
import { useSelector } from "react-redux";
import { BaseForm } from "./base-form";
import { FallbackModelRow } from "./fallback-model-row";
import { useNodeDataChange } from "./useNodeDataChange";
import { VoiceOutputPicker } from "./voice-output-picker";
import { Input } from "@/shared/ui/input";
import { Label } from "@/shared/ui/label";
import { Button } from "@/shared/ui/button";
import {
  CELTextarea,
  type CELTextareaRef,
  type CELVariableType,
} from "@/shared/ui/cel-input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/shared/ui/select";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
  DialogDescription,
} from "@/shared/ui/dialog";
import {
  JsonSchemaBuilder,
  type OpenAPISchema,
} from "@/shared/ui/json-schema-builder";
import {
  Provider,
  Role,
  NodeType,
  type AgentNodeConfig,
  type FallbackModelConfig,
  type Instructions,
  type Workflow,
} from "../../../../model/types";
import { VariableSuggestionsPopover } from "../state/variableSuggestionsPopover";
import {
  PlusIcon,
  TrashIcon,
  Settings2,
  X,
  Search,
  Maximize2,
  HelpCircle,
  BookMarked,
  ChevronDown,
  ChevronRight,
} from "lucide-react";
import { Switch } from "@/shared/ui/switch";
import { Tooltip, TooltipTrigger, TooltipContent } from "@/shared/ui/tooltip";
import {
  CredentialSelect,
  getCredentialTypeForProvider,
} from "@/entities/credential";
import { selectCurrentProjectId } from "@/entities/organization";
import { selectHasAvatarConfig } from "../../model/editor-mode.slice";
import { useGetServerConfigQuery } from "@/entities/config";
import { useGetBillingUsageQuery } from "@/entities/billing";
import { useGetKnowledgeBasesQuery } from "@/entities/knowledge-base";
import {
  DynamicParamForm,
  useGetLLMProvidersQuery,
  useGetLLMProviderSchemaQuery,
  type ModelMetadata,
} from "@/entities/llm-provider";

const AVAILABLE_TOOLS = [
  { value: "web_search", label: "Web Search", icon: Search },
] as const;

// Sentinel for the "whole answer" option in the history-field picker (Radix
// SelectItem values must be non-empty strings).
const HISTORY_FIELD_FULL = "__full__";

interface AgentNodeFormProps {
  nodeId: string;
  config?: AgentNodeConfig;
  workflow: Workflow;
  projectId?: string;
}

const defaultConfig: AgentNodeConfig = {
  name: "",
  provider: Provider.OPENAI,
  model: "",
  instructions: [{ role: Role.USER, content: "" }],
  credentialId: "",
  includeChatHistory: true,
  saveToHistory: true,
};

export const AgentNodeForm = ({
  nodeId,
  config,
  workflow,
  projectId,
}: AgentNodeFormProps) => {
  const { t } = useTranslation();
  const [formData, setFormData] = useState<AgentNodeConfig>(
    config || defaultConfig,
  );
  const [isSchemaModalOpen, setIsSchemaModalOpen] = useState(false);
  const [isModelSettingsModalOpen, setIsModelSettingsModalOpen] =
    useState(false);
  const [tempSchema, setTempSchema] = useState<OpenAPISchema | undefined>();
  const [selectedTools, setSelectedTools] = useState<string[]>(
    config?.tools || [],
  );
  const [currentToolValue, setCurrentToolValue] = useState<string>("");
  const [selectedKBIds, setSelectedKBIds] = useState<string[]>(
    config?.knowledgeBaseIds || [],
  );
  const [currentKBValue, setCurrentKBValue] = useState<string>("");
  const [modelSearchQuery, setModelSearchQuery] = useState<string>("");
  const [showHelpers, setShowHelpers] = useState<{
    index: number;
    type?: CELVariableType;
    term?: string;
  } | null>(null);
  const [isPromptModalOpen, setIsPromptModalOpen] = useState(false);
  const [isAdvancedOpen, setIsAdvancedOpen] = useState(false);
  const [expandedInstruction, setExpandedInstruction] = useState<{
    index: number | null;
    value: string;
  }>({
    index: null,
    value: "",
  });
  const textareaRefs = useRef<Array<CELTextareaRef | null>>([]);
  const textareaContainerRefs = useRef<Array<HTMLDivElement | null>>([]);
  const modalTextareaRef = useRef<CELTextareaRef | null>(null);
  const modalTextareaContainerRef = useRef<HTMLDivElement | null>(null);

  const handleDataChange = useNodeDataChange(nodeId);
  const currentProjectId = useSelector(selectCurrentProjectId);
  const hasAvatarConfig = useSelector(selectHasAvatarConfig);

  // Получаем информацию о биллинге для проверки canUseOwnKeys
  const { data: billingUsage } = useGetBillingUsageQuery(undefined, {
    skip: !currentProjectId,
  });

  const canUseOwnKeys = billingUsage?.features.canUseOwnKeys ?? false;

  // Получаем список баз знаний
  const { data: knowledgeBases = [], isLoading: isLoadingKBs } =
    useGetKnowledgeBasesQuery(
      { projectId: currentProjectId! },
      { skip: !currentProjectId },
    );

  // Список провайдеров — приходит с бэкенда. Один источник правды:
  // когда добавляем нового провайдера на бэке, он автоматически появляется
  // в дропдауне без правок фронта.
  const { data: providerList = [] } = useGetLLMProvidersQuery();

  // Server config — used to decide whether the "Assemblix system key" option is
  // offered for the current provider. Providers themselves are never hidden.
  const { data: serverConfig } = useGetServerConfigQuery();
  const hasSystemKeyForProvider = useCallback(
    (provider: Provider) =>
      serverConfig ? Boolean(serverConfig.systemApiKeys[provider]) : true,
    [serverConfig],
  );
  const hasSystemKey = hasSystemKeyForProvider(formData.provider);

  // Единый источник правды для всего LLM-домена: schema-эндпоинт возвращает
  // и `paramSchema`, и `models` за один поход. Капабилити-фильтрация
  // параметров делается на клиенте через `DynamicParamForm`, без
  // дополнительных сетевых запросов на каждое переключение модели.
  const {
    data: providerSchema,
    isLoading: isLoadingModels,
    error: modelsError,
  } = useGetLLMProviderSchemaQuery(
    { providerName: formData.provider },
    { skip: !formData.provider },
  );

  const models = useMemo<ModelMetadata[]>(
    () => providerSchema?.models ?? [],
    [providerSchema],
  );

  // Метаданные текущей выбранной модели (для capability-aware фильтрации параметров).
  const selectedModelMetadata = useMemo(
    () => models.find((m) => m.id === formData.model),
    [models, formData.model],
  );

  // `response_format` остаётся в боковой форме (он триггерит JSON-schema-чип
  // и важен на верхнем уровне), а все остальные динамические параметры
  // уходят в модалку "Настройки модели".
  const responseFormatSchema = useMemo(
    () =>
      providerSchema?.paramSchema.filter((p) => p.name === "response_format") ??
      [],
    [providerSchema],
  );

  const modalParamSchema = useMemo(
    () =>
      providerSchema?.paramSchema.filter((p) => p.name !== "response_format") ??
      [],
    [providerSchema],
  );

  // Текущие значения LLM-параметров. Backend хранит их в `params: dict`,
  // фронт сериализует туда же; ключи остаются провайдер-специфичными
  // (`temperature`, `reasoning_effort`, и т.д.).
  const llmParams = useMemo(
    () => (formData.params as Record<string, unknown> | undefined) ?? {},
    [formData.params],
  );

  const handleLLMParamChange = useCallback(
    (name: string, value: unknown) => {
      setFormData((prev) => {
        const prevParams = (prev.params as Record<string, unknown>) ?? {};
        const nextParams = { ...prevParams };
        if (value === undefined) {
          delete nextParams[name];
        } else {
          nextParams[name] = value;
        }
        // Зеркалим params.response_format в legacy-поле, чтобы старая логика
        // в orchestrator/AgentNodeConfig читалась без неожиданностей.
        const next = { ...prev, params: nextParams };
        if (name === "response_format") {
          next.responseFormat =
            value === "json_object" ? "json_object" : "text";
        }
        return next;
      });

      // Боковой эффект: открываем JSON-schema-builder сразу при выборе
      // структурированного ответа (UX, как было в старой форме).
      if (name === "response_format" && value === "json_object") {
        setTempSchema(formData.responseSchema as OpenAPISchema | undefined);
        setIsSchemaModalOpen(true);
      }
    },
    [formData.responseSchema],
  );

  // Коллбеки для управления подсказками
  const handleShowHelpers = useCallback(
    (index: number, type?: CELVariableType, term?: string) => {
      setShowHelpers((prev) => {
        // Проверяем, изменилось ли состояние
        if (
          prev?.index === index &&
          prev?.type === type &&
          prev?.term === term
        ) {
          return prev;
        }
        return { index, type, term };
      });
    },
    [],
  );

  const handleHideHelpers = useCallback(() => {
    setShowHelpers((prev) => {
      // Только если подсказки открыты
      if (prev === null) {
        return prev;
      }
      return null;
    });
  }, []);

  // Вызываем handleDataChange при каждом изменении formData
  useEffect(() => {
    handleDataChange(formData);
  }, [formData, handleDataChange]);

  const handleFieldChange = (
    field: keyof AgentNodeConfig,
    value: string | Instructions[],
  ) => {
    setFormData((prev) => ({ ...prev, [field]: value }));
  };

  const handleProviderChange = (value: Provider) => {
    // При смене провайдера сбрасываем всё, что от него зависело:
    // - model (у нового провайдера свой набор моделей)
    // - params (у нового провайдера своя param_schema; параметры со старыми
    //   именами могут быть некорректны или скрыты для новых моделей)
    // - credentialId (системный ключ по умолчанию).
    setFormData((prev) => ({
      ...prev,
      provider: value,
      credentialId: "",
      model: "",
      params: {},
    }));
  };

  const handleInstructionChange = (
    index: number,
    field: keyof Instructions,
    value: string,
  ) => {
    const newInstructions = [...formData.instructions];
    newInstructions[index] = { ...newInstructions[index], [field]: value };
    setFormData((prev) => ({ ...prev, instructions: newInstructions }));
  };

  const addInstruction = () => {
    const newInstructions = [
      ...formData.instructions,
      { role: "user" as Role, content: "" },
    ];
    setFormData((prev) => ({ ...prev, instructions: newInstructions }));
  };

  const removeInstruction = (index: number) => {
    const newInstructions = formData.instructions.filter((_, i) => i !== index);
    setFormData((prev) => ({ ...prev, instructions: newInstructions }));
  };

  const openPromptModal = (index: number) => {
    const targetInstruction = formData.instructions[index];
    setExpandedInstruction({
      index,
      value: targetInstruction?.content || "",
    });
    setIsPromptModalOpen(true);
  };

  const handlePromptModalChange = (value: string) => {
    setExpandedInstruction((prev) => ({ ...prev, value }));
  };

  const handlePromptModalSave = () => {
    if (expandedInstruction.index === null) {
      setIsPromptModalOpen(false);
      return;
    }

    handleInstructionChange(
      expandedInstruction.index,
      "content",
      expandedInstruction.value,
    );
    setIsPromptModalOpen(false);
  };

  // Обработка добавления инструмента
  const handleToolSelect = (toolValue: string) => {
    if (!selectedTools.includes(toolValue)) {
      const newTools = [...selectedTools, toolValue];
      setSelectedTools(newTools);
      setFormData((prev) => ({ ...prev, tools: newTools }));
    }
    // Сбрасываем значение селекта
    setCurrentToolValue("");
  };

  // Обработка удаления инструмента
  const handleToolRemove = (toolValue: string) => {
    const newTools = selectedTools.filter((t) => t !== toolValue);
    setSelectedTools(newTools);
    setFormData((prev) => ({
      ...prev,
      tools: newTools.length > 0 ? newTools : undefined,
    }));
    // Сбрасываем значение селекта на всякий случай
    setCurrentToolValue("");
  };

  // Обработка добавления базы знаний
  const handleKBSelect = (kbId: string) => {
    if (!selectedKBIds.includes(kbId)) {
      const newIds = [...selectedKBIds, kbId];
      setSelectedKBIds(newIds);
      setFormData((prev) => ({ ...prev, knowledgeBaseIds: newIds }));
    }
    setCurrentKBValue("");
  };

  // Обработка удаления базы знаний
  const handleKBRemove = (kbId: string) => {
    const newIds = selectedKBIds.filter((id) => id !== kbId);
    setSelectedKBIds(newIds);
    setFormData((prev) => ({
      ...prev,
      knowledgeBaseIds: newIds.length > 0 ? newIds : undefined,
    }));
    setCurrentKBValue("");
  };

  // Обработка изменения включения истории чата
  const handleIncludeChatHistoryChange = (checked: boolean) => {
    setFormData((prev) => ({ ...prev, includeChatHistory: checked }));
  };

  const handleBooleanFieldChange = (
    field: "enforceTimeoutOnLast" | "saveToHistory" | "stream",
    checked: boolean,
  ) => {
    setFormData((prev) => ({ ...prev, [field]: checked }));
  };

  // --- Надёжность (Фаза 3): ретраи / таймаут / фолбэк-модели ---
  const handleNumberFieldChange = (
    field: "maxRetries" | "timeoutSeconds",
    raw: string,
  ) => {
    const value = raw === "" ? undefined : Number(raw);
    setFormData((prev) => ({
      ...prev,
      [field]: value !== undefined && Number.isNaN(value) ? undefined : value,
    }));
  };

  const handleAddFallback = () => {
    setFormData((prev) => ({
      ...prev,
      fallbackModels: [
        ...(prev.fallbackModels ?? []),
        { provider: prev.provider, model: "" },
      ],
    }));
  };

  const handleFallbackChange = (index: number, next: FallbackModelConfig) => {
    setFormData((prev) => ({
      ...prev,
      fallbackModels: (prev.fallbackModels ?? []).map((fb, i) =>
        i === index ? next : fb,
      ),
    }));
  };

  const handleRemoveFallback = (index: number) => {
    setFormData((prev) => {
      const next = (prev.fallbackModels ?? []).filter((_, i) => i !== index);
      return { ...prev, fallbackModels: next.length > 0 ? next : undefined };
    });
  };

  // Сохраняем схему
  const handleSaveSchema = () => {
    if (tempSchema) {
      setFormData((prev) => ({
        ...prev,
        responseSchema: tempSchema as unknown as Record<string, unknown>,
      }));
    }
    setIsSchemaModalOpen(false);
  };

  // Открываем модальное окно для редактирования
  const handleEditSchema = () => {
    setTempSchema(formData.responseSchema as OpenAPISchema | undefined);
    setIsSchemaModalOpen(true);
  };

  // Фильтруем модели по поисковому запросу
  const filteredModels = useMemo(() => {
    if (!modelSearchQuery.trim()) {
      return models;
    }
    const query = modelSearchQuery.toLowerCase();
    return models.filter((model: ModelMetadata) => {
      const modelName = (model.label || model.id).toLowerCase();
      return modelName.includes(query);
    });
  }, [models, modelSearchQuery]);

  const credentialTypeForProvider = getCredentialTypeForProvider(
    formData.provider,
  );

  // params.response_format — единственный источник правды; legacy-поле
  // responseFormat зеркалится из него для backwards compatibility.
  const isJsonFormat = llmParams.response_format === "json_object";
  const currentSchema = formData.responseSchema as OpenAPISchema | undefined;
  // Field names for the "history field" picker — only when the answer is JSON.
  const schemaFieldNames =
    isJsonFormat && currentSchema?.properties
      ? Object.keys(currentSchema.properties)
      : [];

  return (
    <>
      <BaseForm
        nodeType={NodeType.AGENT}
        label={formData.name}
        projectId={projectId}
      >
        <div className="space-y-4">
          {/* Название агента */}
          <div className="flex justify-between gap-4 items-center">
            <Label htmlFor="agent-name">{t("nodeForms.agent.name")}</Label>
            <Input
              id="agent-name"
              value={formData.name}
              onChange={(e) => handleFieldChange("name", e.target.value)}
              placeholder={t("nodeForms.agent.namePlaceholder")}
            />
          </div>

          {/* Provider */}
          <div className="flex justify-between items-center">
            <Label htmlFor="agent-provider">
              {t("nodeForms.agent.provider")}
            </Label>
            <Select
              value={formData.provider}
              onValueChange={handleProviderChange}
            >
              <SelectTrigger
                id="agent-provider"
                className="border-none shadow-none ring-0! text-xs"
              >
                <SelectValue
                  placeholder={t("nodeForms.agent.selectProvider")}
                />
              </SelectTrigger>
              <SelectContent>
                {providerList.map((p) => (
                  <SelectItem key={p.name} value={p.name} className="text-xs">
                    {p.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          {/* Credential */}
          {canUseOwnKeys && credentialTypeForProvider && (
            <div className="flex justify-between gap-4 items-center">
              <Label htmlFor="agent-credential">
                {t("nodeForms.agent.credential")}
              </Label>
              <CredentialSelect
                selectedCredentialId={formData.credentialId}
                onSelect={(id) => handleFieldChange("credentialId", id)}
                credentialType={credentialTypeForProvider}
                placeholder={t("nodeForms.agent.selectCredential")}
                showSystemToken={hasSystemKey}
              />
            </div>
          )}

          {/* Model */}
          <div className="flex justify-between gap-2 items-center">
            <Label htmlFor="agent-model" className="shrink-0">
              {t("nodeForms.agent.model")}
            </Label>
            <div className="flex items-center gap-0.5 min-w-0">
              <Select
              value={formData.model}
              onValueChange={(value) => handleFieldChange("model", value)}
              disabled={isLoadingModels}
              onOpenChange={(open) => {
                if (!open) {
                  setModelSearchQuery("");
                }
              }}
            >
              <SelectTrigger
                id="agent-model"
                className="border-none shadow-none ring-0! text-xs"
              >
                <SelectValue
                  placeholder={
                    isLoadingModels
                      ? t("nodeForms.agent.loadingModels")
                      : modelsError
                        ? t("nodeForms.agent.modelsError")
                        : t("nodeForms.agent.selectModel")
                  }
                />
              </SelectTrigger>
              <SelectContent
                className="h-[300px] flex flex-col p-0"
                position="popper"
                sideOffset={5}
                align="end"
              >
                {models.length > 0 && (
                  <div className="sticky top-0 z-10 bg-popover p-2 border-b">
                    <div className="relative">
                      <Search className="absolute left-2 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-muted-foreground" />
                      <Input
                        placeholder={t("nodeForms.agent.searchModel")}
                        value={modelSearchQuery}
                        onChange={(e) => setModelSearchQuery(e.target.value)}
                        className="pl-8 h-8 text-xs"
                        onClick={(e) => e.stopPropagation()}
                        onKeyDown={(e) => {
                          e.stopPropagation();
                          // Предотвращаем удаление ноды при нажатии Backspace
                          if (e.key === "Backspace" || e.key === "Delete") {
                            e.stopPropagation();
                          }
                        }}
                      />
                    </div>
                  </div>
                )}
                <div className="overflow-y-auto flex-1 min-h-0">
                  {models.length === 0 && !isLoadingModels ? (
                    <div className="px-2 py-1.5 text-xs text-muted-foreground">
                      {t("nodeForms.agent.noModels")}
                    </div>
                  ) : filteredModels.length === 0 ? (
                    <div className="px-2 py-1.5 text-xs text-muted-foreground">
                      {t("nodeForms.agent.noModelsFound")}
                    </div>
                  ) : (
                    filteredModels.map((model: ModelMetadata) => (
                      <SelectItem
                        key={model.id}
                        value={model.id}
                        className="text-xs"
                      >
                        {model.label || model.id}
                      </SelectItem>
                    ))
                  )}
                </div>
              </SelectContent>
            </Select>
              {/* Иконка-шестерёнка справа от селектора модели — открывает
                  модалку с динамическими настройками LLM. Появляется только
                  когда модель выбрана и у провайдера есть параметры (кроме
                  response_format, который рендерится отдельно ниже). */}
              {modalParamSchema.length > 0 && formData.model && (
                <Tooltip>
                  <TooltipTrigger asChild>
                    <button
                      type="button"
                      onClick={() => setIsModelSettingsModalOpen(true)}
                      aria-label={t("nodeForms.agent.modelSettings")}
                      className="shrink-0 inline-flex items-center justify-center size-7 rounded-md bg-primary/10 text-primary hover:bg-primary/20 transition-colors cursor-pointer"
                    >
                      <Settings2 className="h-3.5 w-3.5" />
                    </button>
                  </TooltipTrigger>
                  <TooltipContent side="left" className="max-w-[260px]">
                    <p className="font-medium text-xs mb-0.5">
                      {t("nodeForms.agent.modelSettings")}
                    </p>
                    <p className="text-xs text-muted-foreground">
                      {t("nodeForms.agent.modelSettingsTooltip")}
                    </p>
                  </TooltipContent>
                </Tooltip>
              )}
            </div>
          </div>

          <div className="flex flex-col gap-2">
            <div className="flex items-center justify-between">
              <Label>{t("nodeForms.agent.instructions")}</Label>
              <Button
                type="button"
                size="icon-sm"
                variant="ghost"
                onClick={addInstruction}
              >
                <PlusIcon />
              </Button>
            </div>
            {formData.instructions.map((instruction, index) => (
              <div key={index} className="bg-muted rounded-lg relative">
                {index > 0 && (
                  <div className="flex items-center justify-between pr-2">
                    <Select
                      value={instruction.role}
                      onValueChange={(value) =>
                        handleInstructionChange(index, "role", value as Role)
                      }
                    >
                      <SelectTrigger
                        id={`instruction-role-${index}`}
                        className="border-none shadow-none ring-0! text-xs"
                      >
                        <SelectValue
                          placeholder={t("nodeForms.agent.selectRole")}
                        />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="user" className="text-xs">
                          {t("nodeForms.agent.roleUser")}
                        </SelectItem>
                        <SelectItem value="assistant" className="text-xs">
                          {t("nodeForms.agent.roleAssistant")}
                        </SelectItem>
                      </SelectContent>
                    </Select>
                    <Button
                      type="button"
                      size="icon-sm"
                      className="size-6"
                      variant="ghost"
                      onClick={() => removeInstruction(index)}
                    >
                      <TrashIcon className="size-3" />
                    </Button>
                  </div>
                )}

                <button
                  type="button"
                  onClick={() => openPromptModal(index)}
                  aria-label={t("nodeForms.agent.expandInstruction")}
                  className="absolute left-2 bottom-2 z-10 rounded p-1 text-muted-foreground hover:text-foreground hover:bg-background/60 transition-colors"
                >
                  <Maximize2 className="h-3 w-3" />
                </button>

                <div
                  ref={(el) => {
                    textareaContainerRefs.current[index] = el;
                  }}
                >
                  <CELTextarea
                    ref={(el) => {
                      textareaRefs.current[index] = el;
                    }}
                    highlightMode="inside-braces"
                    disableOtherSuggestions={true}
                    className="border-none shadow-none ring-0! max-h-[150px]"
                    id={`instruction-content-${index}`}
                    value={instruction.content}
                    onChange={(value) =>
                      handleInstructionChange(index, "content", value)
                    }
                    placeholder={t("nodeForms.agent.contentPlaceholder")}
                    isHelpersVisible={showHelpers?.index === index}
                    onShowHelpers={(type, term) => {
                      handleShowHelpers(index, type, term);
                    }}
                    onHideHelpers={handleHideHelpers}
                  />
                </div>
              </div>
            ))}
          </div>

          {/* Include Chat History */}
          <div className="flex justify-between gap-4 items-center">
            <div className="flex items-center gap-1.5">
              <Label htmlFor="include-chat-history">
                {t("nodeForms.agent.includeChatHistory")}
              </Label>
              <Tooltip>
                <TooltipTrigger asChild>
                  <button
                    type="button"
                    className="text-muted-foreground hover:text-foreground transition-colors"
                  >
                    <HelpCircle className="h-3.5 w-3.5" />
                  </button>
                </TooltipTrigger>
                <TooltipContent side="right" className="max-w-[250px]">
                  <p>{t("nodeForms.agent.includeChatHistoryTooltip")}</p>
                </TooltipContent>
              </Tooltip>
            </div>
            <Switch
              id="include-chat-history"
              checked={formData.includeChatHistory ?? true}
              onCheckedChange={handleIncludeChatHistoryChange}
              showIcons={false}
            />
          </div>

          {/* Voice input mode: how the agent consumes an audio turn */}
          <div className="flex justify-between gap-4 items-center">
            <div className="flex items-center gap-1.5">
              <Label htmlFor="audio-input">
                {t("nodeForms.agent.audioInput")}
              </Label>
              <Tooltip>
                <TooltipTrigger asChild>
                  <button
                    type="button"
                    className="text-muted-foreground hover:text-foreground transition-colors"
                  >
                    <HelpCircle className="h-3.5 w-3.5" />
                  </button>
                </TooltipTrigger>
                <TooltipContent side="right" className="max-w-[250px]">
                  <p>{t("nodeForms.agent.audioInputTooltip")}</p>
                </TooltipContent>
              </Tooltip>
            </div>
            <Select
              value={formData.audioInput ?? "auto"}
              onValueChange={(value) => handleFieldChange("audioInput", value)}
            >
              <SelectTrigger id="audio-input" className="w-[140px] text-xs">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="auto" className="text-xs">
                  {t("nodeForms.agent.audioInputAuto")}
                </SelectItem>
                <SelectItem value="audio" className="text-xs">
                  {t("nodeForms.agent.audioInputAudio")}
                </SelectItem>
                <SelectItem value="text" className="text-xs">
                  {t("nodeForms.agent.audioInputText")}
                </SelectItem>
              </SelectContent>
            </Select>
          </div>

          {/* Save answer to shared history */}
          <div className="flex justify-between gap-4 items-center">
            <div className="flex items-center gap-1.5">
              <Label htmlFor="save-to-history">
                {t("nodeForms.agent.saveToHistory")}
              </Label>
              <Tooltip>
                <TooltipTrigger asChild>
                  <button
                    type="button"
                    className="text-muted-foreground hover:text-foreground transition-colors"
                  >
                    <HelpCircle className="h-3.5 w-3.5" />
                  </button>
                </TooltipTrigger>
                <TooltipContent side="right" className="max-w-[250px]">
                  <p>{t("nodeForms.agent.saveToHistoryTooltip")}</p>
                </TooltipContent>
              </Tooltip>
            </div>
            <Switch
              id="save-to-history"
              checked={formData.saveToHistory ?? true}
              onCheckedChange={(checked) =>
                handleBooleanFieldChange("saveToHistory", checked)
              }
              showIcons={false}
            />
          </div>

          {/* Stream token output (text format only) */}
          {(formData.responseFormat ?? "text") === "text" && (
            <div className="flex justify-between gap-4 items-center">
              <div className="flex items-center gap-1.5">
                <Label htmlFor="agent-stream">
                  {t("nodeForms.agent.stream")}
                </Label>
                <Tooltip>
                  <TooltipTrigger asChild>
                    <button
                      type="button"
                      className="text-muted-foreground hover:text-foreground transition-colors"
                    >
                      <HelpCircle className="h-3.5 w-3.5" />
                    </button>
                  </TooltipTrigger>
                  <TooltipContent side="right" className="max-w-[250px]">
                    <p>{t("nodeForms.agent.streamTooltip")}</p>
                  </TooltipContent>
                </Tooltip>
              </div>
              <Switch
                id="agent-stream"
                checked={formData.stream ?? false}
                onCheckedChange={(checked) =>
                  handleBooleanFieldChange("stream", checked)
                }
                showIcons={false}
              />
            </div>
          )}

          {/* Output modality: text or realtime voice (text format only) */}
          {(formData.responseFormat ?? "text") === "text" && (
            <div className="space-y-3">
              <div className="space-y-2">
                <Label className="text-xs">
                  {t("nodeForms.agent.outputType")}
                </Label>
                <Select
                  value={formData.outputType ?? "text"}
                  onValueChange={(value) =>
                    setFormData((prev) => ({
                      ...prev,
                      outputType: value as "text" | "voice" | "avatar",
                    }))
                  }
                >
                  <SelectTrigger className="text-xs">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="text" className="text-xs">
                      {t("nodeForms.agent.outputTypeText")}
                    </SelectItem>
                    <SelectItem value="voice" className="text-xs">
                      {t("nodeForms.agent.outputTypeVoice")}
                    </SelectItem>
                    <SelectItem value="avatar" className="text-xs">
                      {t("nodeForms.agent.outputTypeAvatar")}
                    </SelectItem>
                  </SelectContent>
                </Select>
              </div>

              {formData.outputType === "voice" && (
                <>
                  <VoiceOutputPicker
                    value={formData.voice}
                    onChange={(voice) =>
                      setFormData((prev) => ({ ...prev, voice }))
                    }
                  />
                  {formData.voice?.realtime && !(formData.stream ?? false) && (
                    <p className="text-xs text-amber-600">
                      {t("nodeForms.agent.voiceStreamHint")}
                    </p>
                  )}
                </>
              )}

              {/* Avatar config is workflow-global (set once in the editor header,
                  not per node) — only surface a warning here if it's missing. */}
              {formData.outputType === "avatar" && (
                <>
                  {!hasAvatarConfig && (
                    <p className="text-xs text-amber-600">
                      {t("nodeForms.agent.avatarNotConfigured")}
                    </p>
                  )}
                  {!(formData.stream ?? false) && (
                    <p className="text-xs text-amber-600">
                      {t("nodeForms.agent.avatarStreamHint")}
                    </p>
                  )}
                </>
              )}
            </div>
          )}

          {/* History field (only for JSON answers with a schema) */}
          {(formData.saveToHistory ?? true) && schemaFieldNames.length > 0 && (
            <div className="flex justify-between gap-4 items-center">
              <div className="flex items-center gap-1.5">
                <Label htmlFor="history-field">
                  {t("nodeForms.agent.historyField")}
                </Label>
                <Tooltip>
                  <TooltipTrigger asChild>
                    <button
                      type="button"
                      className="text-muted-foreground hover:text-foreground transition-colors"
                    >
                      <HelpCircle className="h-3.5 w-3.5" />
                    </button>
                  </TooltipTrigger>
                  <TooltipContent side="right" className="max-w-[250px]">
                    <p>{t("nodeForms.agent.historyFieldTooltip")}</p>
                  </TooltipContent>
                </Tooltip>
              </div>
              <Select
                value={formData.historyField ?? HISTORY_FIELD_FULL}
                onValueChange={(value) =>
                  setFormData((prev) => ({
                    ...prev,
                    historyField:
                      value === HISTORY_FIELD_FULL ? undefined : value,
                  }))
                }
              >
                <SelectTrigger
                  id="history-field"
                  className="border-none shadow-none ring-0! text-xs w-auto"
                >
                  <SelectValue
                    placeholder={t("nodeForms.agent.historyFieldFull")}
                  />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value={HISTORY_FIELD_FULL} className="text-xs">
                    {t("nodeForms.agent.historyFieldFull")}
                  </SelectItem>
                  {schemaFieldNames.map((field) => (
                    <SelectItem key={field} value={field} className="text-xs">
                      {field}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          )}

          {/* Инструменты */}
          <div>
            <div className="flex justify-between items-center">
              <Label htmlFor="tools-select">{t("nodeForms.agent.tools")}</Label>
              <Select value={currentToolValue} onValueChange={handleToolSelect}>
                <SelectTrigger
                  id="tools-select"
                  className="border-none shadow-none ring-0! text-xs max-w-[200px]"
                  disabled={selectedTools.length === AVAILABLE_TOOLS.length}
                >
                  <SelectValue
                    placeholder={
                      selectedTools.length === AVAILABLE_TOOLS.length
                        ? t("nodeForms.agent.allToolsAdded")
                        : t("nodeForms.agent.addTool")
                    }
                  />
                </SelectTrigger>
                <SelectContent>
                  {AVAILABLE_TOOLS.filter(
                    (tool) => !selectedTools.includes(tool.value),
                  ).map((tool) => {
                    const Icon = tool.icon;
                    return (
                      <SelectItem
                        key={tool.value}
                        value={tool.value}
                        className="text-xs"
                      >
                        <div className="flex items-center gap-2">
                          <Icon className="h-3.5 w-3.5" />
                          {tool.label}
                        </div>
                      </SelectItem>
                    );
                  })}
                </SelectContent>
              </Select>
            </div>

            {/* Чипы с выбранными инструментами */}
            {selectedTools.length > 0 && (
              <div className="flex flex-wrap gap-2 mt-2">
                {selectedTools.map((toolValue) => {
                  const tool = AVAILABLE_TOOLS.find(
                    (t) => t.value === toolValue,
                  );
                  const Icon = tool?.icon;
                  return (
                    <button
                      key={toolValue}
                      type="button"
                      onClick={() => handleToolRemove(toolValue)}
                      className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full bg-primary/10 text-primary text-xs font-medium hover:bg-primary/20 transition-colors"
                    >
                      {Icon && <Icon className="h-3 w-3" />}
                      {tool?.label || toolValue}
                      <X className="h-3 w-3" />
                    </button>
                  );
                })}
              </div>
            )}
          </div>

          {/* Базы знаний */}
          <div>
            <div className="flex justify-between items-center">
              <Label htmlFor="kb-select">
                {t("nodeForms.agent.knowledgeBases")}
              </Label>
              <Select
                value={currentKBValue}
                onValueChange={handleKBSelect}
                disabled={
                  isLoadingKBs ||
                  knowledgeBases.filter((kb) => !selectedKBIds.includes(kb.id))
                    .length === 0
                }
              >
                <SelectTrigger
                  id="kb-select"
                  className="border-none shadow-none ring-0! text-xs max-w-[200px]"
                >
                  <SelectValue
                    placeholder={
                      isLoadingKBs
                        ? t("nodeForms.agent.loadingKnowledgeBases")
                        : knowledgeBases.filter(
                              (kb) => !selectedKBIds.includes(kb.id),
                            ).length === 0 && knowledgeBases.length > 0
                          ? t("nodeForms.agent.noKnowledgeBases")
                          : t("nodeForms.agent.selectKnowledgeBases")
                    }
                  />
                </SelectTrigger>
                <SelectContent>
                  {knowledgeBases
                    .filter((kb) => !selectedKBIds.includes(kb.id))
                    .map((kb) => (
                      <SelectItem key={kb.id} value={kb.id} className="text-xs">
                        <div className="flex items-center gap-2">
                          <BookMarked className="h-3.5 w-3.5" />
                          {kb.name}
                        </div>
                      </SelectItem>
                    ))}
                </SelectContent>
              </Select>
            </div>

            {/* Чипы с выбранными базами знаний */}
            {selectedKBIds.length > 0 && (
              <div className="flex flex-wrap gap-2 mt-2">
                {selectedKBIds.map((kbId) => {
                  const kb = knowledgeBases.find((k) => k.id === kbId);
                  return (
                    <button
                      key={kbId}
                      type="button"
                      onClick={() => handleKBRemove(kbId)}
                      className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full bg-primary/10 text-primary text-xs font-medium hover:bg-primary/20 transition-colors"
                    >
                      <BookMarked className="h-3 w-3" />
                      {kb?.name || kbId}
                      <X className="h-3 w-3" />
                    </button>
                  );
                })}
              </div>
            )}
          </div>

          {/* `response_format` живёт в самом низу формы — он определяет формат
              ответа модели (text/json_object) и триггерит JSON-schema-чип ниже. */}
          {responseFormatSchema.length > 0 && (
            <DynamicParamForm
              paramSchema={responseFormatSchema}
              model={selectedModelMetadata}
              values={llmParams}
              onChange={handleLLMParamChange}
            />
          )}

          {/* JSON-schema-builder бейдж: появляется только когда выбран
              `response_format=json_object` (через динамический paramSchema). */}
          {isJsonFormat && (
            <div className="flex justify-start">
              <button
                type="button"
                onClick={handleEditSchema}
                className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full bg-primary/10 text-primary text-xs font-medium hover:bg-primary/20 transition-colors"
              >
                <Settings2 className="h-3 w-3" />
                {currentSchema?.title || "responseSchema"}
              </button>
            </div>
          )}

          {/* Расширенные настройки: надёжность (ретраи / таймаут / фолбэк-модели) */}
          <div>
            <button
              type="button"
              onClick={() => setIsAdvancedOpen((prev) => !prev)}
              className="flex items-center gap-2 text-sm font-semibold hover:text-primary transition-colors"
            >
              {isAdvancedOpen ? (
                <ChevronDown className="h-4 w-4" />
              ) : (
                <ChevronRight className="h-4 w-4" />
              )}
              {t("nodeForms.agent.advancedSettings")}
            </button>

            {isAdvancedOpen && (
              <div className="space-y-4 pl-6 border-l-2 border-muted mt-3">
                {/* Число ретраев одного LLM-вызова */}
                <div className="space-y-1.5">
                  <Label htmlFor="agent-max-retries">
                    {t("nodeForms.agent.maxRetries")}
                  </Label>
                  <Input
                    id="agent-max-retries"
                    type="number"
                    min={0}
                    max={10}
                    placeholder={t("nodeForms.agent.maxRetriesPlaceholder")}
                    value={formData.maxRetries ?? ""}
                    onChange={(e) =>
                      handleNumberFieldChange("maxRetries", e.target.value)
                    }
                  />
                </div>

                {/* Таймаут всего агентского цикла (секунды) */}
                <div className="space-y-1.5">
                  <Label htmlFor="agent-timeout">
                    {t("nodeForms.agent.timeout")}
                  </Label>
                  <Input
                    id="agent-timeout"
                    type="number"
                    min={1}
                    placeholder={t("nodeForms.agent.timeoutPlaceholder")}
                    value={formData.timeoutSeconds ?? ""}
                    onChange={(e) =>
                      handleNumberFieldChange("timeoutSeconds", e.target.value)
                    }
                  />
                </div>

                {/* Жёсткий таймаут на последней модели */}
                <div className="flex justify-between gap-4 items-center">
                  <div className="flex items-center gap-1.5">
                    <Label htmlFor="enforce-timeout-on-last">
                      {t("nodeForms.agent.enforceTimeoutOnLast")}
                    </Label>
                    <Tooltip>
                      <TooltipTrigger asChild>
                        <button
                          type="button"
                          className="text-muted-foreground hover:text-foreground transition-colors"
                        >
                          <HelpCircle className="h-3.5 w-3.5" />
                        </button>
                      </TooltipTrigger>
                      <TooltipContent side="right" className="max-w-[250px]">
                        <p>{t("nodeForms.agent.enforceTimeoutOnLastTooltip")}</p>
                      </TooltipContent>
                    </Tooltip>
                  </div>
                  <Switch
                    id="enforce-timeout-on-last"
                    checked={formData.enforceTimeoutOnLast ?? true}
                    onCheckedChange={(checked) =>
                      handleBooleanFieldChange("enforceTimeoutOnLast", checked)
                    }
                    showIcons={false}
                  />
                </div>

                {/* Фолбэк-модели */}
                <div>
                  <div className="flex justify-between items-center">
                    <Label>{t("nodeForms.agent.fallbackModels")}</Label>
                    <Button
                      type="button"
                      variant="ghost"
                      size="sm"
                      className="text-xs"
                      onClick={handleAddFallback}
                    >
                      <PlusIcon className="h-3.5 w-3.5" />
                      {t("nodeForms.agent.addFallbackModel")}
                    </Button>
                  </div>
                  <p className="text-xs text-muted-foreground mt-1">
                    {t("nodeForms.agent.fallbackModelsHint")}
                  </p>
                  <div className="space-y-2 mt-2">
                    {(formData.fallbackModels ?? []).map((fb, index) => (
                      <FallbackModelRow
                        key={index}
                        index={index}
                        value={fb}
                        providerList={providerList}
                        canUseOwnKeys={canUseOwnKeys}
                        hasSystemKeyForProvider={hasSystemKeyForProvider}
                        onChange={(next) => handleFallbackChange(index, next)}
                        onRemove={() => handleRemoveFallback(index)}
                      />
                    ))}
                  </div>
                </div>
              </div>
            )}
          </div>
        </div>

        {/* Модальное окно для настройки JSON схемы */}
        <Dialog open={isSchemaModalOpen} onOpenChange={setIsSchemaModalOpen}>
          <DialogContent className="max-w-3xl max-h-[90vh] overflow-y-auto">
            <DialogHeader>
              <DialogTitle>{t("nodeForms.agent.schemaBuilder")}</DialogTitle>
              <DialogDescription>
                {t("nodeForms.agent.schemaDescription")}
              </DialogDescription>
            </DialogHeader>

            <JsonSchemaBuilder
              initialSchema={tempSchema}
              onSchemaChange={setTempSchema}
            />

            <DialogFooter>
              <Button
                type="button"
                variant="outline"
                onClick={() => setIsSchemaModalOpen(false)}
              >
                {t("nodeForms.agent.cancel")}
              </Button>
              <Button type="button" onClick={handleSaveSchema}>
                {t("nodeForms.agent.save")}
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>

        {/* Модальное окно с динамическими настройками выбранной LLM-модели.
            Поля формируются capability-aware из providerSchema.paramSchema. */}
        <Dialog
          open={isModelSettingsModalOpen}
          onOpenChange={setIsModelSettingsModalOpen}
        >
          <DialogContent className="max-w-xl max-h-[90vh] overflow-y-auto">
            <DialogHeader>
              <DialogTitle>
                {t("nodeForms.agent.modelSettingsModalTitle")}
              </DialogTitle>
              <DialogDescription>
                {t("nodeForms.agent.modelSettingsModalDescription")}
              </DialogDescription>
            </DialogHeader>

            {providerSchema && modalParamSchema.length > 0 && (
              <DynamicParamForm
                paramSchema={modalParamSchema}
                model={selectedModelMetadata}
                values={llmParams}
                onChange={handleLLMParamChange}
                expandAdvanced
              />
            )}

            <DialogFooter>
              <Button
                type="button"
                onClick={() => setIsModelSettingsModalOpen(false)}
              >
                {t("nodeForms.agent.close")}
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>

        <Dialog open={isPromptModalOpen} onOpenChange={setIsPromptModalOpen}>
          <DialogContent className="max-w-2xl max-h-[90vh] overflow-y-auto">
            <DialogHeader>
              <DialogTitle>{t("nodeForms.agent.promptModalTitle")}</DialogTitle>
            </DialogHeader>

            <div
              className="space-y-2"
              ref={(el) => {
                modalTextareaContainerRef.current = el;
              }}
            >
              <Label htmlFor="expanded-instruction">
                {t("nodeForms.agent.promptModalLabel")}
              </Label>
              <CELTextarea
                id="expanded-instruction"
                ref={(el) => {
                  modalTextareaRef.current = el;
                }}
                value={expandedInstruction.value}
                onChange={handlePromptModalChange}
                highlightMode="inside-braces"
                disableOtherSuggestions={true}
                className="border-none shadow-none ring-0! min-h-[320px]"
                placeholder={t("nodeForms.agent.contentPlaceholder")}
                isHelpersVisible={
                  isPromptModalOpen &&
                  expandedInstruction.index !== null &&
                  showHelpers?.index === expandedInstruction.index
                }
                onShowHelpers={(type, term) => {
                  if (expandedInstruction.index === null) return;
                  handleShowHelpers(expandedInstruction.index, type, term);
                }}
                onHideHelpers={handleHideHelpers}
              />
            </div>

            <DialogFooter>
              <Button
                type="button"
                variant="outline"
                onClick={() => setIsPromptModalOpen(false)}
              >
                {t("nodeForms.agent.cancel")}
              </Button>
              <Button type="button" onClick={handlePromptModalSave}>
                {t("nodeForms.agent.save")}
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
      </BaseForm>
      {showHelpers && (
        <VariableSuggestionsPopover
          showHelpers={showHelpers}
          workflow={workflow}
          currentNodeId={nodeId}
          getTextareaContainerRef={(index) => {
            if (isPromptModalOpen && expandedInstruction.index === index) {
              return modalTextareaContainerRef.current;
            }
            return textareaContainerRefs.current[index];
          }}
          getTextareaRef={(index) => {
            if (isPromptModalOpen && expandedInstruction.index === index) {
              return modalTextareaRef.current;
            }
            return textareaRefs.current[index];
          }}
          onClose={handleHideHelpers}
        />
      )}
    </>
  );
};
