import { useState, useEffect, useRef, useCallback } from "react";
import { useTranslation } from "react-i18next";
import { BaseForm } from "./base-form";
import { useNodeDataChange } from "./useNodeDataChange";
import { Label } from "@/shared/ui/label";
import { Input } from "@/shared/ui/input";
import {
  CELTextarea,
  type CELTextareaRef,
  type CELVariableType,
} from "@/shared/ui/cel-input";
import { Button } from "@/shared/ui/button";
import { CELHelper } from "@/shared/ui/cel-helper";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/shared/ui/select";
import {
  NodeType,
  type HTTPRequestNodeConfig,
  type Workflow,
} from "../../../../model/types";
import { PlusIcon, TrashIcon } from "lucide-react";
import { VariableSuggestionsPopover } from "../state/variableSuggestionsPopover";

interface HTTPRequestNodeFormProps {
  nodeId: string;
  config?: HTTPRequestNodeConfig;
  workflow: Workflow;
  projectId?: string;
}

const defaultConfig: HTTPRequestNodeConfig = {
  url: "",
  method: "GET",
  headers: {},
  timeout: 30,
};

export const HTTPRequestNodeForm = ({
  nodeId,
  config,
  workflow,
  projectId,
}: HTTPRequestNodeFormProps) => {
  const { t } = useTranslation();
  const [formData, setFormData] = useState<HTTPRequestNodeConfig>(
    config || defaultConfig
  );
  const [showHelpers, setShowHelpers] = useState<{
    field: "url" | "body";
    type?: CELVariableType;
    term?: string;
  } | null>(null);

  const urlTextareaRef = useRef<CELTextareaRef | null>(null);
  const bodyTextareaRef = useRef<CELTextareaRef | null>(null);
  const urlContainerRef = useRef<HTMLDivElement | null>(null);
  const bodyContainerRef = useRef<HTMLDivElement | null>(null);

  const handleDataChange = useNodeDataChange(nodeId);

  // Вызываем handleDataChange при каждом изменении formData
  useEffect(() => {
    handleDataChange(formData);
  }, [formData, handleDataChange]);

  const handleShowHelpers = useCallback(
    (field: "url" | "body", type?: CELVariableType, term?: string) => {
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
    []
  );

  const handleHideHelpers = useCallback(() => {
    setShowHelpers((prev) => {
      if (prev === null) {
        return prev;
      }
      return null;
    });
  }, []);

  const handleMethodChange = (
    value: "GET" | "POST" | "PUT" | "PATCH" | "DELETE"
  ) => {
    setFormData((prev) => ({ ...prev, method: value }));
  };

  const handleUrlChange = (value: string) => {
    setFormData((prev) => ({ ...prev, url: value }));
  };

  const handleBodyChange = (value: string) => {
    setFormData((prev) => ({ ...prev, body: value }));
  };

  const handleTimeoutChange = (value: string) => {
    const numValue = parseInt(value, 10);
    if (!isNaN(numValue) && numValue > 0) {
      setFormData((prev) => ({ ...prev, timeout: numValue }));
    }
  };

  // Headers управление
  const addHeader = () => {
    const headers = formData.headers || {};
    const newKey = `header_${Object.keys(headers).length + 1}`;
    setFormData((prev) => ({
      ...prev,
      headers: { ...headers, [newKey]: "" },
    }));
  };

  const updateHeaderKey = (oldKey: string, newKey: string) => {
    const headers = formData.headers || {};
    if (oldKey === newKey) return;

    const newHeaders = { ...headers };
    const value = newHeaders[oldKey];
    delete newHeaders[oldKey];
    newHeaders[newKey] = value;

    setFormData((prev) => ({ ...prev, headers: newHeaders }));
  };

  const updateHeaderValue = (key: string, value: string) => {
    const headers = formData.headers || {};
    setFormData((prev) => ({
      ...prev,
      headers: { ...headers, [key]: value },
    }));
  };

  const removeHeader = (key: string) => {
    const headers = { ...formData.headers };
    delete headers[key];
    setFormData((prev) => ({
      ...prev,
      headers: Object.keys(headers).length > 0 ? headers : undefined,
    }));
  };

  // Query params управление
  const addQueryParam = () => {
    const queryParams = formData.query_params || {};
    const newKey = `param_${Object.keys(queryParams).length + 1}`;
    setFormData((prev) => ({
      ...prev,
      query_params: { ...queryParams, [newKey]: "" },
    }));
  };

  const updateQueryParamKey = (oldKey: string, newKey: string) => {
    const queryParams = formData.query_params || {};
    if (oldKey === newKey) return;

    const newQueryParams = { ...queryParams };
    const value = newQueryParams[oldKey];
    delete newQueryParams[oldKey];
    newQueryParams[newKey] = value;

    setFormData((prev) => ({ ...prev, query_params: newQueryParams }));
  };

  const updateQueryParamValue = (key: string, value: string) => {
    const queryParams = formData.query_params || {};
    setFormData((prev) => ({
      ...prev,
      query_params: { ...queryParams, [key]: value },
    }));
  };

  const removeQueryParam = (key: string) => {
    const queryParams = { ...formData.query_params };
    delete queryParams[key];
    setFormData((prev) => ({
      ...prev,
      query_params:
        Object.keys(queryParams).length > 0 ? queryParams : undefined,
    }));
  };

  const headers = formData.headers || {};
  const queryParams = formData.query_params || {};
  const showBody = ["POST", "PUT", "PATCH"].includes(formData.method);

  return (
    <>
      <BaseForm
        nodeType={NodeType.HTTP_REQUEST}
        label={t("nodeForms.httpRequest.title")}
        projectId={projectId}
      >
        <div className="space-y-4">
          {/* Method */}
          <div className="flex justify-between items-center">
            <Label htmlFor="http-method">
              {t("nodeForms.httpRequest.method")}
            </Label>
            <Select value={formData.method} onValueChange={handleMethodChange}>
              <SelectTrigger
                id="http-method"
                className="border-none shadow-none ring-0! text-xs"
              >
                <SelectValue
                  placeholder={t("nodeForms.httpRequest.selectMethod")}
                />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="GET" className="text-xs">
                  GET
                </SelectItem>
                <SelectItem value="POST" className="text-xs">
                  POST
                </SelectItem>
                <SelectItem value="PUT" className="text-xs">
                  PUT
                </SelectItem>
                <SelectItem value="PATCH" className="text-xs">
                  PATCH
                </SelectItem>
                <SelectItem value="DELETE" className="text-xs">
                  DELETE
                </SelectItem>
              </SelectContent>
            </Select>
          </div>

          {/* URL */}
          <div className="space-y-2">
            <Label htmlFor="http-url">{t("nodeForms.httpRequest.url")}</Label>
            <div ref={urlContainerRef}>
              <CELTextarea
                ref={urlTextareaRef}
                id="http-url"
                className="text-xs placeholder:text-xs"
                value={formData.url}
                onChange={handleUrlChange}
                placeholder={t("nodeForms.httpRequest.urlPlaceholder")}
                isHelpersVisible={showHelpers?.field === "url"}
                onShowHelpers={(type, term) => {
                  handleShowHelpers("url", type, term);
                }}
                onHideHelpers={handleHideHelpers}
              />
              <CELHelper />
            </div>
          </div>

          {/* Headers */}
          <div className="space-y-2">
            <div className="flex items-center justify-between">
              <Label>{t("nodeForms.httpRequest.headers")}</Label>
              <Button
                type="button"
                size="icon-sm"
                variant="ghost"
                onClick={addHeader}
              >
                <PlusIcon />
              </Button>
            </div>
            <div className="flex flex-col gap-2">
              {Object.entries(headers).map(([key, value]) => (
                <div key={key} className="flex gap-2 items-center">
                  <Input
                    className="text-xs flex-1"
                    value={key}
                    onChange={(e) => updateHeaderKey(key, e.target.value)}
                    placeholder={t("nodeForms.httpRequest.headerKey")}
                  />
                  <Input
                    className="text-xs flex-1"
                    value={value}
                    onChange={(e) => updateHeaderValue(key, e.target.value)}
                    placeholder={t("nodeForms.httpRequest.headerValue")}
                  />
                  <Button
                    type="button"
                    size="icon-sm"
                    variant="ghost"
                    onClick={() => removeHeader(key)}
                  >
                    <TrashIcon className="size-3" />
                  </Button>
                </div>
              ))}
            </div>
          </div>

          {/* Query Params */}
          <div className="space-y-2">
            <div className="flex items-center justify-between">
              <Label>{t("nodeForms.httpRequest.queryParams")}</Label>
              <Button
                type="button"
                size="icon-sm"
                variant="ghost"
                onClick={addQueryParam}
              >
                <PlusIcon />
              </Button>
            </div>
            <div className="flex flex-col gap-2">
              {Object.entries(queryParams).map(([key, value]) => (
                <div key={key} className="flex gap-2 items-center">
                  <Input
                    className="text-xs flex-1"
                    value={key}
                    onChange={(e) => updateQueryParamKey(key, e.target.value)}
                    placeholder={t("nodeForms.httpRequest.paramKey")}
                  />
                  <Input
                    className="text-xs flex-1"
                    value={value}
                    onChange={(e) => updateQueryParamValue(key, e.target.value)}
                    placeholder={t("nodeForms.httpRequest.paramValue")}
                  />
                  <Button
                    type="button"
                    size="icon-sm"
                    variant="ghost"
                    onClick={() => removeQueryParam(key)}
                  >
                    <TrashIcon className="size-3" />
                  </Button>
                </div>
              ))}
            </div>
          </div>

          {/* Body (только для POST/PUT/PATCH) */}
          {showBody && (
            <div className="space-y-2">
              <Label htmlFor="http-body">
                {t("nodeForms.httpRequest.body")}
              </Label>
              <div ref={bodyContainerRef}>
                <CELTextarea
                  ref={bodyTextareaRef}
                  id="http-body"
                  className="text-xs placeholder:text-xs"
                  value={formData.body || ""}
                  onChange={handleBodyChange}
                  placeholder={t("nodeForms.httpRequest.bodyPlaceholder")}
                  isHelpersVisible={showHelpers?.field === "body"}
                  onShowHelpers={(type, term) => {
                    handleShowHelpers("body", type, term);
                  }}
                  onHideHelpers={handleHideHelpers}
                />
                <CELHelper />
              </div>
            </div>
          )}

          {/* Timeout */}
          <div className="flex justify-between gap-4 items-center">
            <Label htmlFor="http-timeout">
              {t("nodeForms.httpRequest.timeout")}
            </Label>
            <Input
              id="http-timeout"
              type="number"
              min="1"
              value={formData.timeout || 30}
              onChange={(e) => handleTimeoutChange(e.target.value)}
              placeholder="30"
              className="w-24"
            />
          </div>
        </div>
      </BaseForm>
      {showHelpers && (
        <VariableSuggestionsPopover
          showHelpers={{
            index: 0,
            type: showHelpers.type,
            term: showHelpers.term,
          }}
          workflow={workflow}
          currentNodeId={nodeId}
          getTextareaContainerRef={() =>
            showHelpers.field === "url"
              ? urlContainerRef.current
              : bodyContainerRef.current
          }
          getTextareaRef={() =>
            showHelpers.field === "url"
              ? urlTextareaRef.current
              : bodyTextareaRef.current
          }
          onClose={handleHideHelpers}
        />
      )}
    </>
  );
};
