import { useState, useEffect, useRef, useCallback } from "react";
import { useTranslation } from "react-i18next";
import { useSelector } from "react-redux";
import { ChevronDown, ChevronRight } from "lucide-react";
import { BaseForm } from "./base-form";
import { useNodeDataChange } from "./useNodeDataChange";
import { Label } from "@/shared/ui/label";
import { Checkbox } from "@/shared/ui/checkbox";
import { Input } from "@/shared/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/shared/ui/select";
import {
  CELTextarea,
  type CELTextareaRef,
  type CELVariableType,
} from "@/shared/ui/cel-input";
import { Divider } from "@/shared/ui/divider";
import {
  NodeType,
  type EndNodeConfig,
  type Workflow,
  type OutputMode,
  type FilterMode,
} from "../../../../model/types";
import { AgentNodeSelect } from "../state/agentNodeSelect";
import { MultiVariableSelect } from "../state/multiVariableSelect";
import { VariableSuggestionsPopover } from "../state/variableSuggestionsPopover";
import {
  useGetVoiceProvidersQuery,
  useGetVoiceProviderModelsQuery,
  useGetCredentialVoicesQuery,
  useGetSystemVoicesQuery,
} from "@/entities/voice-model";
import {
  CredentialSelect,
  getCredentialTypeForProvider,
} from "@/entities/credential";
import { useGetBillingUsageQuery } from "@/entities/billing";
import { useGetServerConfigQuery } from "@/entities/config";
import { selectCurrentProjectId } from "@/entities/organization";

interface EndNodeFormProps {
  nodeId: string;
  config?: EndNodeConfig;
  workflow: Workflow;
  projectId?: string;
}

const defaultConfig: EndNodeConfig = {
  isSessionEnd: false,
  isError: false,
  outputMode: undefined, // undefined = "last_agent" по умолчанию
  stateFilter: "all",
  projectFilter: "all",
};

export const EndNodeForm = ({
  nodeId,
  config,
  workflow,
  projectId,
}: EndNodeFormProps) => {
  const { t } = useTranslation();
  const initialConfig = config || defaultConfig;
  const [formData, setFormData] = useState<EndNodeConfig>(initialConfig);
  const [isAdvancedOpen, setIsAdvancedOpen] = useState(false);
  const [showHelpers, setShowHelpers] = useState<{
    field: "errorMessage" | "customMessage";
    type?: CELVariableType;
    term?: string;
  } | null>(null);

  const errorMessageTextareaRef = useRef<CELTextareaRef | null>(null);
  const customMessageTextareaRef = useRef<CELTextareaRef | null>(null);
  const errorMessageContainerRef = useRef<HTMLDivElement | null>(null);
  const customMessageContainerRef = useRef<HTMLDivElement | null>(null);

  const handleDataChange = useNodeDataChange(nodeId);

  useEffect(() => {
    handleDataChange(formData);
  }, [formData, handleDataChange]);

  const handleShowHelpers = useCallback(
    (
      field: "errorMessage" | "customMessage",
      type?: CELVariableType,
      term?: string,
    ) => {
      setShowHelpers((prev) => {
        if (
          prev?.field === field &&
          prev?.type === type &&
          prev?.term === term
        ) {
          return prev;
        }
        return { field, type, term };
      });
    },
    [],
  );

  const handleHideHelpers = useCallback(() => {
    setShowHelpers((prev) => {
      if (prev === null) return prev;
      return null;
    });
  }, []);

  const handleSessionEndChange = (checked: boolean) => {
    setFormData((prev) => ({ ...prev, isSessionEnd: checked }));
  };

  const handleIsErrorChange = (checked: boolean) => {
    setFormData((prev) => ({
      ...prev,
      isError: checked,
      errorMessage: checked ? prev.errorMessage : undefined,
    }));
  };

  const handleOutputModeChange = (value: OutputMode) => {
    setFormData((prev) => ({
      ...prev,
      outputMode: value,
      sourceNodeId: value === "specific_agent" ? prev.sourceNodeId : undefined,
      customMessage: value === "custom" ? prev.customMessage : undefined,
    }));
  };

  const handleSourceNodeIdChange = (nodeId: string) => {
    setFormData((prev) => ({ ...prev, sourceNodeId: nodeId }));
  };

  const handleCustomMessageChange = (value: string) => {
    setFormData((prev) => ({ ...prev, customMessage: value }));
  };

  const handleStateFilterChange = (value: FilterMode) => {
    setFormData((prev) => ({
      ...prev,
      stateFilter: value,
      stateVariables:
        value === "selected" ? prev.stateVariables || [] : undefined,
    }));
  };

  const handleStateVariablesChange = (variables: string[]) => {
    setFormData((prev) => ({ ...prev, stateVariables: variables }));
  };

  const handleProjectFilterChange = (value: FilterMode) => {
    setFormData((prev) => ({
      ...prev,
      projectFilter: value,
      projectVariables:
        value === "selected" ? prev.projectVariables || [] : undefined,
    }));
  };

  const handleProjectVariablesChange = (variables: string[]) => {
    setFormData((prev) => ({ ...prev, projectVariables: variables }));
  };

  const handleOutputFormatChange = (value: "text" | "voice") => {
    setFormData((prev) => ({ ...prev, outputFormat: value }));
  };

  const handleVoiceProviderChange = (provider: string) => {
    setFormData((prev) => ({
      ...prev,
      // Reset model + credential + voice when the provider changes (same as
      // the agent node and the start node's voice-input picker).
      voice: { provider, model: "" },
    }));
  };

  const handleVoiceCredentialChange = (credentialId: string) => {
    setFormData((prev) => ({
      ...prev,
      voice: {
        provider: prev.voice?.provider ?? "",
        model: prev.voice?.model ?? "",
        credentialId,
        // The voice list is per-credential; reset it when the credential changes.
        voiceId: undefined,
      },
    }));
  };

  const handleVoiceIdChange = (voiceId: string) => {
    setFormData((prev) => ({
      ...prev,
      voice: {
        provider: prev.voice?.provider ?? "",
        model: prev.voice?.model ?? "",
        credentialId: prev.voice?.credentialId,
        voiceId,
      },
    }));
  };

  const handleVoiceModelChange = (model: string) => {
    setFormData((prev) => ({
      ...prev,
      voice: {
        provider: prev.voice?.provider ?? "",
        model,
        credentialId: prev.voice?.credentialId,
        voiceId: prev.voice?.voiceId,
      },
    }));
  };

  const handleVoiceMaxCharsChange = (value: string) => {
    setFormData((prev) => ({
      ...prev,
      voiceMaxChars: value ? Number(value) : undefined,
    }));
  };

  const outputMode = formData.outputMode || "last_agent";
  const stateFilter = formData.stateFilter || "all";
  const projectFilter = formData.projectFilter || "all";
  const outputFormat = formData.outputFormat || "text";

  // Voice output (TTS): provider → credential → voice → model picker, mirroring
  // the start node's voice-input picker.
  const { data: speechProviders = [] } = useGetVoiceProvidersQuery({
    capability: "speech",
  });
  const voiceProvider = formData.voice?.provider;
  const { data: speechModels = [], isLoading: isLoadingSpeechModels } =
    useGetVoiceProviderModelsQuery(
      { providerName: voiceProvider ?? "", capability: "speech" },
      { skip: !voiceProvider },
    );
  const { data: credentialVoices = [], isLoading: isLoadingCredentialVoices } =
    useGetCredentialVoicesQuery(
      { credentialId: formData.voice?.credentialId ?? "" },
      { skip: !formData.voice?.credentialId },
    );

  const currentProjectId = useSelector(selectCurrentProjectId);
  const { data: billingUsage } = useGetBillingUsageQuery(undefined, {
    skip: !currentProjectId,
  });
  const canUseOwnKeys = billingUsage?.features.canUseOwnKeys ?? false;
  const { data: serverConfig } = useGetServerConfigQuery();
  const voiceCredentialType = voiceProvider
    ? getCredentialTypeForProvider(voiceProvider)
    : undefined;
  const hasVoiceSystemKey = voiceProvider
    ? serverConfig
      ? Boolean(serverConfig.systemApiKeys[voiceProvider])
      : true
    : false;

  // No personal credential selected but the platform has a system key for
  // this provider: the run will use the system key, so list its voices.
  const usingSystemKey =
    Boolean(voiceProvider) && !formData.voice?.credentialId && hasVoiceSystemKey;
  const { data: systemVoices = [], isLoading: isLoadingSystemVoices } =
    useGetSystemVoicesQuery(
      { providerName: voiceProvider ?? "" },
      { skip: !usingSystemKey },
    );
  const availableVoices = formData.voice?.credentialId
    ? credentialVoices
    : systemVoices;
  const isLoadingVoices = formData.voice?.credentialId
    ? isLoadingCredentialVoices
    : isLoadingSystemVoices;

  return (
    <>
      <BaseForm
        nodeType={NodeType.END}
        label={t("nodeForms.end.title")}
        projectId={projectId}
      >
        <div className="space-y-4">
          {/* Session End */}
          <div className="flex flex-row items-start space-x-3 space-y-0 rounded-md border p-4">
            <Checkbox
              id="is-session-end"
              checked={formData.isSessionEnd}
              onCheckedChange={handleSessionEndChange}
            />
            <div className="space-y-1 leading-none">
              <Label htmlFor="is-session-end">
                {t("nodeForms.end.isSessionEnd")}
              </Label>
              <p className="text-sm text-muted-foreground">
                {t("nodeForms.end.sessionEndDescription")}
              </p>
            </div>
          </div>

          {/* Business Error */}
          <div className="space-y-2">
            <div className="flex flex-row items-start space-x-3 space-y-0 rounded-md border p-4">
              <Checkbox
                id="is-error"
                checked={formData.isError}
                onCheckedChange={handleIsErrorChange}
              />
              <div className="space-y-1 leading-none">
                <Label htmlFor="is-error">{t("nodeForms.end.isError")}</Label>
                <p className="text-sm text-muted-foreground">
                  {t("nodeForms.end.isErrorDescription")}
                </p>
              </div>
            </div>
          </div>

          <Divider />

          {/* Advanced Settings - Collapsible */}
          <div className="space-y-4">
            <button
              type="button"
              onClick={() => setIsAdvancedOpen(!isAdvancedOpen)}
              className="flex items-center gap-2 text-sm font-semibold hover:text-primary transition-colors"
            >
              {isAdvancedOpen ? (
                <ChevronDown className="h-4 w-4" />
              ) : (
                <ChevronRight className="h-4 w-4" />
              )}
              {t("nodeForms.end.advancedSettings")}
            </button>

            {isAdvancedOpen && (
              <div className="space-y-4 pl-6 border-l-2 border-muted">
                {/* Output Source */}
                <div className="space-y-2">
                  <Label>{t("nodeForms.end.outputSource")}</Label>
                  <Select
                    value={outputMode}
                    onValueChange={handleOutputModeChange}
                  >
                    <SelectTrigger className="text-xs">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="last_agent" className="text-xs">
                        {t("nodeForms.end.outputModeLastAgent")}
                      </SelectItem>
                      <SelectItem value="specific_agent" className="text-xs">
                        {t("nodeForms.end.outputModeSpecificAgent")}
                      </SelectItem>
                      <SelectItem value="custom" className="text-xs">
                        {t("nodeForms.end.outputModeCustom")}
                      </SelectItem>
                    </SelectContent>
                  </Select>

                  {/* Specific Agent Select - условное отображение */}
                  {outputMode === "specific_agent" && (
                    <AgentNodeSelect
                      workflow={workflow}
                      selectedNodeId={formData.sourceNodeId}
                      onSelect={handleSourceNodeIdChange}
                    />
                  )}

                  {/* Custom Message - условное отображение */}
                  {outputMode === "custom" && (
                    <div className="space-y-2">
                      <Label>{t("nodeForms.end.customMessage")}</Label>
                      <div ref={customMessageContainerRef}>
                        <CELTextarea
                          ref={customMessageTextareaRef}
                          highlightMode="inside-braces"
                          disableOtherSuggestions={true}
                          id="custom-message"
                          className="text-xs placeholder:text-xs"
                          value={formData.customMessage || ""}
                          onChange={handleCustomMessageChange}
                          placeholder={t(
                            "nodeForms.end.customMessagePlaceholder",
                          )}
                          isHelpersVisible={
                            showHelpers?.field === "customMessage"
                          }
                          onShowHelpers={(type, term) => {
                            handleShowHelpers("customMessage", type, term);
                          }}
                          onHideHelpers={handleHideHelpers}
                        />
                      </div>
                    </div>
                  )}
                </div>

                <Divider />

                {/* Data Filtering */}
                <div className="space-y-4">
                  <Label className="text-sm font-semibold">
                    {t("nodeForms.end.dataFiltering")}
                  </Label>

                  {/* State Filter */}
                  <div className="space-y-2">
                    <Label className="text-xs">
                      {t("nodeForms.end.stateFilter")}
                    </Label>
                    <Select
                      value={stateFilter}
                      onValueChange={handleStateFilterChange}
                    >
                      <SelectTrigger className="text-xs">
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="all" className="text-xs">
                          {t("nodeForms.end.filterAll")}
                        </SelectItem>
                        <SelectItem value="none" className="text-xs">
                          {t("nodeForms.end.filterNone")}
                        </SelectItem>
                        <SelectItem value="selected" className="text-xs">
                          {t("nodeForms.end.filterSelected")}
                        </SelectItem>
                      </SelectContent>
                    </Select>

                    {/* State Variables Multi-Select - условное отображение */}
                    {stateFilter === "selected" && (
                      <MultiVariableSelect
                        workflow={workflow}
                        selectedVariables={formData.stateVariables || []}
                        onSelect={handleStateVariablesChange}
                        variableType="state"
                      />
                    )}
                  </div>

                  {/* Project Filter */}
                  <div className="space-y-2">
                    <Label className="text-xs">
                      {t("nodeForms.end.projectFilter")}
                    </Label>
                    <Select
                      value={projectFilter}
                      onValueChange={handleProjectFilterChange}
                    >
                      <SelectTrigger className="text-xs">
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="all" className="text-xs">
                          {t("nodeForms.end.filterAll")}
                        </SelectItem>
                        <SelectItem value="none" className="text-xs">
                          {t("nodeForms.end.filterNone")}
                        </SelectItem>
                        <SelectItem value="selected" className="text-xs">
                          {t("nodeForms.end.filterSelected")}
                        </SelectItem>
                      </SelectContent>
                    </Select>

                    {/* Project Variables Multi-Select - условное отображение */}
                    {projectFilter === "selected" && (
                      <MultiVariableSelect
                        workflow={workflow}
                        selectedVariables={formData.projectVariables || []}
                        onSelect={handleProjectVariablesChange}
                        variableType="project"
                      />
                    )}
                  </div>
                </div>

                <Divider />

                {/* Voice Output (TTS) */}
                <div className="space-y-4">
                  <Label className="text-sm font-semibold">
                    {t("nodeForms.end.voiceOutput")}
                  </Label>

                  <div className="space-y-2">
                    <Label className="text-xs">
                      {t("nodeForms.end.outputFormat")}
                    </Label>
                    <Select
                      value={outputFormat}
                      onValueChange={handleOutputFormatChange}
                    >
                      <SelectTrigger className="text-xs">
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="text" className="text-xs">
                          {t("nodeForms.end.formatText")}
                        </SelectItem>
                        <SelectItem value="voice" className="text-xs">
                          {t("nodeForms.end.formatVoice")}
                        </SelectItem>
                      </SelectContent>
                    </Select>
                  </div>

                  {outputFormat === "voice" && (
                    <div className="space-y-3">
                      <div className="space-y-2">
                        <Label className="text-xs">
                          {t("nodeForms.end.voiceProvider")}
                        </Label>
                        <Select
                          value={formData.voice?.provider ?? ""}
                          onValueChange={handleVoiceProviderChange}
                        >
                          <SelectTrigger className="text-xs">
                            <SelectValue
                              placeholder={t(
                                "nodeForms.end.selectVoiceProvider",
                              )}
                            />
                          </SelectTrigger>
                          <SelectContent>
                            {speechProviders.map((p) => (
                              <SelectItem
                                key={p.name}
                                value={p.name}
                                className="text-xs"
                              >
                                {p.label}
                              </SelectItem>
                            ))}
                          </SelectContent>
                        </Select>
                      </div>

                      {canUseOwnKeys && voiceCredentialType && (
                        <div className="space-y-2">
                          <Label className="text-xs">
                            {t("nodeForms.end.voiceCredential")}
                          </Label>
                          <CredentialSelect
                            selectedCredentialId={formData.voice?.credentialId}
                            onSelect={handleVoiceCredentialChange}
                            credentialType={voiceCredentialType}
                            placeholder={t(
                              "nodeForms.end.selectVoiceCredential",
                            )}
                            showSystemToken={hasVoiceSystemKey}
                          />
                        </div>
                      )}

                      <div className="space-y-2">
                        <Label className="text-xs">
                          {t("nodeForms.end.voiceModel")}
                        </Label>
                        <Select
                          value={formData.voice?.model ?? ""}
                          onValueChange={handleVoiceModelChange}
                          disabled={
                            isLoadingSpeechModels || !formData.voice?.provider
                          }
                        >
                          <SelectTrigger className="text-xs">
                            <SelectValue
                              placeholder={
                                isLoadingSpeechModels
                                  ? t("nodeForms.end.loadingVoiceModels")
                                  : t("nodeForms.end.selectVoiceModel")
                              }
                            />
                          </SelectTrigger>
                          <SelectContent>
                            {speechModels.map((m) => (
                              <SelectItem
                                key={m.id}
                                value={m.id}
                                className="text-xs"
                              >
                                {m.label}
                              </SelectItem>
                            ))}
                          </SelectContent>
                        </Select>
                      </div>

                      {formData.voice?.provider &&
                        (formData.voice?.credentialId || usingSystemKey) && (
                          <div className="space-y-2">
                            <Label className="text-xs">
                              {t("nodeForms.end.voice")}
                            </Label>
                            <Select
                              value={formData.voice?.voiceId ?? ""}
                              onValueChange={handleVoiceIdChange}
                              disabled={isLoadingVoices}
                            >
                              <SelectTrigger className="text-xs">
                                <SelectValue
                                  placeholder={
                                    isLoadingVoices
                                      ? t("nodeForms.end.loadingVoices")
                                      : t("nodeForms.end.selectVoice")
                                  }
                                />
                              </SelectTrigger>
                              <SelectContent>
                                {availableVoices.map((v) => (
                                  <SelectItem
                                    key={v.id}
                                    value={v.id}
                                    className="text-xs"
                                  >
                                    {v.name}
                                  </SelectItem>
                                ))}
                              </SelectContent>
                            </Select>
                          </div>
                        )}

                      <div className="space-y-2">
                        <Label className="text-xs">
                          {t("nodeForms.end.voiceMaxChars")}
                        </Label>
                        <Input
                          type="number"
                          min={1}
                          className="text-xs"
                          value={formData.voiceMaxChars ?? ""}
                          onChange={(e) =>
                            handleVoiceMaxCharsChange(e.target.value)
                          }
                          placeholder={t(
                            "nodeForms.end.voiceMaxCharsPlaceholder",
                          )}
                        />
                      </div>

                      {!formData.voice?.voiceId && (
                        <p className="text-xs text-amber-600">
                          {t("nodeForms.end.voiceMissingWarning")}
                        </p>
                      )}
                    </div>
                  )}
                </div>
              </div>
            )}
          </div>
        </div>
      </BaseForm>

      {/* Variable Suggestions Popover */}
      {showHelpers && (
        <VariableSuggestionsPopover
          showHelpers={{
            index: 0,
            type: showHelpers.type,
            term: showHelpers.term,
          }}
          workflow={workflow}
          currentNodeId={nodeId}
          getTextareaContainerRef={() => {
            if (showHelpers.field === "errorMessage") {
              return errorMessageContainerRef.current;
            }
            return customMessageContainerRef.current;
          }}
          getTextareaRef={() => {
            if (showHelpers.field === "errorMessage") {
              return errorMessageTextareaRef.current;
            }
            return customMessageTextareaRef.current;
          }}
          onClose={handleHideHelpers}
        />
      )}
    </>
  );
};
