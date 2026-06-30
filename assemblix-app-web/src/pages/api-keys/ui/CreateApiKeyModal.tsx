import { useState, useEffect } from "react";
import { useSelector } from "react-redux";
import { useTranslation } from "react-i18next";
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
import { AlertTriangle, Check, Copy } from "lucide-react";
import { useCreateApiKeyMutation } from "@/entities/api-key";
import { selectCurrentProjectId } from "@/entities/organization";
import { toast } from "sonner";

type CreateApiKeyModalProps = {
  open: boolean;
  onOpenChange: (open: boolean) => void;
};

type Step = "create" | "show";

export const CreateApiKeyModal = ({
  open,
  onOpenChange,
}: CreateApiKeyModalProps) => {
  const { t } = useTranslation();
  const [step, setStep] = useState<Step>("create");
  const [name, setName] = useState("");
  const [apiKey, setApiKey] = useState("");
  const [copied, setCopied] = useState(false);
  const currentProjectId = useSelector(selectCurrentProjectId);

  const [createApiKey, { isLoading }] = useCreateApiKeyMutation();

  // Сброс состояния при закрытии модалки
  useEffect(() => {
    if (!open) {
      // Небольшая задержка для плавности анимации закрытия
      const timer = setTimeout(() => {
        setStep("create");
        setName("");
        setApiKey("");
        setCopied(false);
      }, 200);
      return () => clearTimeout(timer);
    }
  }, [open]);

  const handleCreate = async () => {
    if (!name.trim()) {
      toast.error(t("apiKeys.enterKeyName"));
      return;
    }

    if (!currentProjectId) {
      toast.error(t("apiKeys.selectProject"));
      return;
    }

    try {
      const result = await createApiKey({
        name: name.trim(),
        projectId: currentProjectId,
      }).unwrap();
      setApiKey(result.apiKey);
      setStep("show");
      toast.success(t("apiKeys.createSuccess"));
    } catch (error) {
      console.error(error);
      toast.error(t("apiKeys.createError"));
    }
  };

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(apiKey);
      setCopied(true);
      toast.success(t("apiKeys.copySuccess"));
      setTimeout(() => setCopied(false), 2000);
    } catch (error) {
      console.error(error);
      toast.error(t("apiKeys.copyError"));
    }
  };

  const handleClose = () => {
    onOpenChange(false);
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-lg">
        {step === "create" && (
          <>
            <DialogHeader>
              <DialogTitle>{t("apiKeys.modal.createTitle")}</DialogTitle>
              <DialogDescription>
                {t("apiKeys.modal.createDescription")}
              </DialogDescription>
            </DialogHeader>
            <div className="space-y-4 py-4">
              <div className="space-y-2">
                <Label htmlFor="name">{t("apiKeys.name")}</Label>
                <Input
                  id="name"
                  placeholder={t("apiKeys.modal.namePlaceholder")}
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === "Enter" && !isLoading) {
                      handleCreate();
                    }
                  }}
                  autoFocus
                />
              </div>
            </div>
            <DialogFooter>
              <Button
                variant="outline"
                onClick={handleClose}
                disabled={isLoading}
              >
                {t("common.cancel")}
              </Button>
              <Button onClick={handleCreate} disabled={isLoading}>
                {isLoading ? t("apiKeys.modal.creating") : t("common.create")}
              </Button>
            </DialogFooter>
          </>
        )}

        {step === "show" && (
          <>
            <DialogHeader>
              <div className="flex items-center gap-3">
                <div className="flex h-10 w-10 items-center justify-center rounded-full bg-warning/10">
                  <AlertTriangle className="h-5 w-5 text-warning" />
                </div>
                <DialogTitle>{t("apiKeys.modal.saveTitle")}</DialogTitle>
              </div>
              <DialogDescription className="pt-4 text-left">
                <span className="font-semibold text-warning">
                  {t("apiKeys.modal.saveWarning")}
                </span>
                <br />
                {t("apiKeys.modal.saveDescription")}
              </DialogDescription>
            </DialogHeader>
            <div className="space-y-4 py-4">
              <div className="space-y-2">
                <Label>{t("apiKeys.modal.yourKey")}</Label>
                <div className="flex gap-2">
                  <Input
                    value={apiKey}
                    readOnly
                    className="font-mono text-sm"
                  />
                  <Button
                    size="icon"
                    variant="outline"
                    onClick={handleCopy}
                    className="shrink-0"
                  >
                    {copied ? (
                      <Check className="h-4 w-4 text-success" />
                    ) : (
                      <Copy className="h-4 w-4" />
                    )}
                  </Button>
                </div>
              </div>
              <div className="rounded-lg border border-warning/20 bg-warning/5 p-4">
                <p className="text-sm text-muted-foreground">
                  {t("apiKeys.modal.useInHeader")}
                  <br />
                  <code className="mt-2 block rounded bg-muted px-2 py-1 font-mono text-xs">
                    Authorization: Bearer {apiKey}
                  </code>
                </p>
              </div>
            </div>
            <DialogFooter>
              <Button onClick={handleClose} className="w-full sm:w-auto">
                {t("apiKeys.modal.done")}
              </Button>
            </DialogFooter>
          </>
        )}
      </DialogContent>
    </Dialog>
  );
};
