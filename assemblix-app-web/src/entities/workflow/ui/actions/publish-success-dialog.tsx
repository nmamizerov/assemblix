import { useEffect, useRef, useState } from "react";
import { useSelector } from "react-redux";
import { useTranslation } from "react-i18next";
import { Check, Copy } from "lucide-react";
import { toast } from "sonner";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/shared/ui/dialog";
import { Button } from "@/shared/ui/button";
import { Input } from "@/shared/ui/input";
import { Label } from "@/shared/ui/label";
import {
  useCreateApiKeyMutation,
  useGetApiKeysQuery,
} from "@/entities/api-key";
import { selectCurrentProjectId } from "@/entities/organization";
import { CodeBlock } from "@/shared/ui/code-block";
import { apiConfig, appConfig } from "@/shared/config/app.config";

interface PublishSuccessDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  workflowId: string;
  workflowName: string;
  version: number;
}

type CopyField = "workflowId" | "apiKey" | null;

const BASE_URL = `${appConfig.url}${apiConfig.baseUrl}`;

const buildSnippets = (workflowId: string, authToken: string) => {
  const endpoint = `/workflows/${workflowId}/execute`;
  return [
    {
      language: "cURL",
      code: `curl -X POST \\
  ${BASE_URL}${endpoint} \\
  -H "Authorization: Bearer ${authToken}" \\
  -H "Content-Type: application/json" \\
  -d '{"input": {"message": "Hello!"}}'`,
    },
    {
      language: "Python",
      code: `import httpx

url = "${BASE_URL}${endpoint}"
headers = {
    "Authorization": "Bearer ${authToken}",
    "Content-Type": "application/json"
}
data = {"input": {"message": "Hello!"}}

response = httpx.post(url, headers=headers, json=data)
print(response.json())`,
    },
    {
      language: "JavaScript",
      code: `const response = await fetch("${BASE_URL}${endpoint}", {
  method: "POST",
  headers: {
    "Authorization": "Bearer ${authToken}",
    "Content-Type": "application/json"
  },
  body: JSON.stringify({ input: { message: "Hello!" } })
});

const result = await response.json();
console.log(result);`,
    },
  ];
};

export const PublishSuccessDialog = ({
  open,
  onOpenChange,
  workflowId,
  workflowName,
  version,
}: PublishSuccessDialogProps) => {
  const { t } = useTranslation();
  const projectId = useSelector(selectCurrentProjectId);

  const { data: keysData, isLoading: isLoadingKeys } = useGetApiKeysQuery(
    { projectId: projectId ?? "" },
    { skip: !projectId || !open },
  );
  const [createApiKey, { isLoading: isCreating }] = useCreateApiKeyMutation();

  const [createdKey, setCreatedKey] = useState<string | null>(null);
  const [autoCreated, setAutoCreated] = useState(false);
  const [copiedField, setCopiedField] = useState<CopyField>(null);
  const autoCreateAttemptedRef = useRef(false);

  useEffect(() => {
    if (!open) {
      const timer = setTimeout(() => {
        setCreatedKey(null);
        setAutoCreated(false);
        setCopiedField(null);
        autoCreateAttemptedRef.current = false;
      }, 200);
      return () => clearTimeout(timer);
    }
  }, [open]);

  useEffect(() => {
    if (!open || !projectId) return;
    if (autoCreateAttemptedRef.current) return;
    if (isLoadingKeys) return;
    if ((keysData?.keys.length ?? 0) > 0) return;

    autoCreateAttemptedRef.current = true;
    createApiKey({
      name: `${workflowName} — integration`,
      projectId,
    })
      .unwrap()
      .then((res) => {
        setCreatedKey(res.apiKey);
        setAutoCreated(true);
      })
      .catch(() => {
        toast.error(t("publishSuccess.apiKeyCreateError"));
      });
  }, [
    open,
    projectId,
    isLoadingKeys,
    keysData,
    createApiKey,
    workflowName,
    t,
  ]);

  const handleManualCreate = async () => {
    if (!projectId) return;
    try {
      const res = await createApiKey({
        name: `${workflowName} — integration`,
        projectId,
      }).unwrap();
      setCreatedKey(res.apiKey);
      setAutoCreated(false);
    } catch {
      toast.error(t("publishSuccess.apiKeyCreateError"));
    }
  };

  const handleCopy = async (value: string, field: Exclude<CopyField, null>) => {
    try {
      await navigator.clipboard.writeText(value);
      setCopiedField(field);
      toast.success(t("publishSuccess.copySuccess"));
      setTimeout(() => setCopiedField((cur) => (cur === field ? null : cur)), 2000);
    } catch {
      // clipboard rarely fails; surfacing nothing extra to keep the modal calm
    }
  };

  const codeExamples = buildSnippets(workflowId, createdKey ?? "YOUR_API_KEY");
  const hasExistingKeys = (keysData?.keys.length ?? 0) > 0;

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-2xl max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <div className="flex items-center gap-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-full bg-green-100 dark:bg-green-900/30">
              <Check className="h-5 w-5 text-green-600 dark:text-green-400" />
            </div>
            <div>
              <DialogTitle>{t("publishSuccess.title")}</DialogTitle>
              <DialogDescription>
                {t("publishSuccess.version", { version })}
              </DialogDescription>
            </div>
          </div>
        </DialogHeader>

        <div className="mt-4 space-y-5 min-w-0">
          <div className="space-y-2">
            <Label htmlFor="workflow-id">
              {t("publishSuccess.workflowIdLabel")}
            </Label>
            <div className="flex gap-2">
              <Input
                id="workflow-id"
                value={workflowId}
                readOnly
                className="font-mono text-sm"
              />
              <Button
                size="icon"
                variant="outline"
                onClick={() => handleCopy(workflowId, "workflowId")}
                className="shrink-0"
                aria-label={t("publishSuccess.workflowIdLabel")}
              >
                {copiedField === "workflowId" ? (
                  <Check className="h-4 w-4 text-success" />
                ) : (
                  <Copy className="h-4 w-4" />
                )}
              </Button>
            </div>
          </div>

          <div className="space-y-2">
            <Label htmlFor="api-key">{t("publishSuccess.apiKeyLabel")}</Label>
            {createdKey ? (
              <>
                <div className="flex gap-2">
                  <Input
                    id="api-key"
                    value={createdKey}
                    readOnly
                    className="font-mono text-sm"
                  />
                  <Button
                    size="icon"
                    variant="outline"
                    onClick={() => handleCopy(createdKey, "apiKey")}
                    className="shrink-0"
                    aria-label={t("publishSuccess.apiKeyLabel")}
                  >
                    {copiedField === "apiKey" ? (
                      <Check className="h-4 w-4 text-success" />
                    ) : (
                      <Copy className="h-4 w-4" />
                    )}
                  </Button>
                </div>
                {autoCreated && (
                  <p className="text-xs text-muted-foreground">
                    {t("publishSuccess.apiKeyAutoCreated")}
                  </p>
                )}
              </>
            ) : isLoadingKeys || (isCreating && !hasExistingKeys) ? (
              <div className="h-10 rounded-md bg-muted/50 animate-pulse" />
            ) : (
              <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
                <p className="text-xs text-muted-foreground">
                  {t("publishSuccess.apiKeyHint")}
                </p>
                <Button
                  size="sm"
                  variant="outline"
                  onClick={handleManualCreate}
                  disabled={isCreating || !projectId}
                  className="shrink-0"
                >
                  {isCreating
                    ? t("publishSuccess.apiKeyCreating")
                    : t("publishSuccess.apiKeyCreate")}
                </Button>
              </div>
            )}
          </div>

          <div className="space-y-2 min-w-0">
            <h4 className="text-sm font-medium">
              {t("publishSuccess.examplesLabel")}
            </h4>
            <CodeBlock examples={codeExamples} />
          </div>

          <p className="text-xs text-muted-foreground">
            {t("publishSuccess.supportPrompt")}{" "}
            <a
              href="mailto:nikita.mamizerov@gmail.com"
              className="font-medium text-primary hover:underline"
            >
              nikita.mamizerov@gmail.com
            </a>
          </p>
        </div>

        <DialogFooter>
          <Button onClick={() => onOpenChange(false)} className="gap-2">
            <Check className="h-4 w-4" />
            {t("publishSuccess.close")}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
};
