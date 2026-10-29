import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { ArrowDownIcon, ArrowUpIcon, PlusIcon, TrashIcon } from "lucide-react";
import { BaseForm } from "./base-form";
import { useNodeDataChange } from "./useNodeDataChange";
import { Label } from "@/shared/ui/label";
import { Input } from "@/shared/ui/input";
import { Textarea } from "@/shared/ui/textarea";
import { Switch } from "@/shared/ui/switch";
import { Button } from "@/shared/ui/button";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/shared/ui/select";
import { CredentialSelect, CredentialType } from "@/entities/credential";

type JevQuestionType = "noul" | "choice" | "score";

type JevChoiceOption = { name: string; description: string };

type JevQuestion = {
  name: string;
  type: JevQuestionType;
  instructions: string;
  trueCriteria?: string;
  falseCriteria?: string;
  options?: JevChoiceOption[];
  levels?: string[];
};

type JevNodeConfig = {
  credentialId?: string;
  model: string;
  state: string;
  questions: JevQuestion[];
  longContext: boolean;
  outputKey: string;
};

interface JevNodeFormProps {
  nodeId: string;
  config?: Partial<JevNodeConfig>;
  projectId?: string;
}

const MAX_SCORE_LEVELS = 10;

const newQuestion = (index: number): JevQuestion => ({
  name: `q${index + 1}`,
  type: "noul",
  instructions: "",
});

/**
 * Config form for the "jev" node: one TypeSafe System One request with any number
 * of yes/no (noul), choice and score questions. Branching is done by a following
 * Condition node on input.<outputKey>.<name>.*.
 */
export const JevNodeForm = ({
  nodeId,
  config,
  projectId,
}: JevNodeFormProps) => {
  const { t } = useTranslation();
  const handleDataChange = useNodeDataChange(nodeId);
  const [formData, setFormData] = useState<JevNodeConfig>({
    credentialId: config?.credentialId,
    model: config?.model ?? "jev-latest",
    state: config?.state ?? "{{ input.message }}",
    questions: config?.questions?.length ? config.questions : [newQuestion(0)],
    longContext: config?.longContext ?? false,
    outputKey: config?.outputKey ?? "jev",
  });

  useEffect(() => {
    handleDataChange(formData);
  }, [formData, handleDataChange]);

  const updateQuestion = (index: number, patch: Partial<JevQuestion>) =>
    setFormData((prev) => ({
      ...prev,
      questions: prev.questions.map((q, i) =>
        i === index ? { ...q, ...patch } : q,
      ),
    }));

  const handleAddQuestion = () =>
    setFormData((prev) => ({
      ...prev,
      questions: [...prev.questions, newQuestion(prev.questions.length)],
    }));

  const handleRemoveQuestion = (index: number) =>
    setFormData((prev) => ({
      ...prev,
      questions: prev.questions.filter((_, i) => i !== index),
    }));

  const handleMoveQuestion = (index: number, offset: -1 | 1) =>
    setFormData((prev) => {
      const target = index + offset;
      if (target < 0 || target >= prev.questions.length) return prev;
      const questions = [...prev.questions];
      [questions[index], questions[target]] = [
        questions[target],
        questions[index],
      ];
      return { ...prev, questions };
    });

  const handleTypeChange = (index: number, type: JevQuestionType) => {
    const question = formData.questions[index];
    updateQuestion(index, {
      type,
      options:
        type === "choice" && !question.options?.length
          ? [{ name: "", description: "" }]
          : question.options,
      levels:
        type === "score" && (question.levels?.length ?? 0) < 2
          ? ["", ""]
          : question.levels,
    });
  };

  const renderNoulFields = (question: JevQuestion, index: number) => (
    <div className="flex flex-col gap-2">
      <Input
        className="text-xs"
        value={question.trueCriteria ?? ""}
        onChange={(e) =>
          updateQuestion(index, { trueCriteria: e.target.value })
        }
        placeholder={t("nodeForms.jev.trueCriteria")}
      />
      <Input
        className="text-xs"
        value={question.falseCriteria ?? ""}
        onChange={(e) =>
          updateQuestion(index, { falseCriteria: e.target.value })
        }
        placeholder={t("nodeForms.jev.falseCriteria")}
      />
    </div>
  );

  const renderChoiceFields = (question: JevQuestion, index: number) => {
    const options = question.options ?? [];
    const setOptions = (next: JevChoiceOption[]) =>
      updateQuestion(index, { options: next });
    return (
      <div className="space-y-2">
        <div className="flex items-center justify-between">
          <Label className="text-xs">{t("nodeForms.jev.options")}</Label>
          <Button
            type="button"
            size="icon-sm"
            variant="ghost"
            onClick={() =>
              setOptions([...options, { name: "", description: "" }])
            }
          >
            <PlusIcon />
          </Button>
        </div>
        {options.map((option, optionIndex) => (
          <div key={optionIndex} className="flex gap-2 items-center">
            <Input
              className="text-xs w-1/3"
              value={option.name}
              onChange={(e) =>
                setOptions(
                  options.map((o, i) =>
                    i === optionIndex ? { ...o, name: e.target.value } : o,
                  ),
                )
              }
              placeholder={t("nodeForms.jev.optionName")}
            />
            <Input
              className="text-xs flex-1"
              value={option.description}
              onChange={(e) =>
                setOptions(
                  options.map((o, i) =>
                    i === optionIndex
                      ? { ...o, description: e.target.value }
                      : o,
                  ),
                )
              }
              placeholder={t("nodeForms.jev.optionDescription")}
            />
            <Button
              type="button"
              size="icon-sm"
              variant="ghost"
              onClick={() =>
                setOptions(options.filter((_, i) => i !== optionIndex))
              }
            >
              <TrashIcon className="size-3" />
            </Button>
          </div>
        ))}
      </div>
    );
  };

  const renderScoreFields = (question: JevQuestion, index: number) => {
    const levels = question.levels ?? [];
    const setLevels = (next: string[]) =>
      updateQuestion(index, { levels: next });
    return (
      <div className="space-y-2">
        <div className="flex items-center justify-between">
          <Label className="text-xs">{t("nodeForms.jev.levels")}</Label>
          <Button
            type="button"
            size="icon-sm"
            variant="ghost"
            disabled={levels.length >= MAX_SCORE_LEVELS}
            onClick={() => setLevels([...levels, ""])}
          >
            <PlusIcon />
          </Button>
        </div>
        {levels.map((level, levelIndex) => (
          <div key={levelIndex} className="flex gap-2 items-center">
            <span className="text-xs text-muted-foreground w-4">
              {levelIndex}
            </span>
            <Input
              className="text-xs flex-1"
              value={level}
              onChange={(e) =>
                setLevels(
                  levels.map((l, i) => (i === levelIndex ? e.target.value : l)),
                )
              }
              placeholder={t("nodeForms.jev.levelDescription")}
            />
            <Button
              type="button"
              size="icon-sm"
              variant="ghost"
              disabled={levels.length <= 2}
              onClick={() =>
                setLevels(levels.filter((_, i) => i !== levelIndex))
              }
            >
              <TrashIcon className="size-3" />
            </Button>
          </div>
        ))}
      </div>
    );
  };

  return (
    <BaseForm
      nodeType="jev"
      label={t("nodeForms.jev.title")}
      projectId={projectId}
    >
      <div className="space-y-4">
        <div className="flex flex-col gap-1.5">
          <Label className="text-xs">{t("nodeForms.jev.credential")}</Label>
          <CredentialSelect
            selectedCredentialId={formData.credentialId}
            onSelect={(credentialId) =>
              setFormData((prev) => ({ ...prev, credentialId }))
            }
            credentialType={CredentialType.TYPESAFE_TOKEN}
            placeholder={t("nodeForms.jev.selectCredential")}
            showSystemToken={false}
          />
        </div>

        <div className="flex flex-col gap-1.5">
          <Label htmlFor="jev-model" className="text-xs">
            {t("nodeForms.jev.model")}
          </Label>
          <Input
            id="jev-model"
            className="text-xs"
            value={formData.model}
            onChange={(e) =>
              setFormData((prev) => ({ ...prev, model: e.target.value }))
            }
            placeholder="jev-latest"
          />
        </div>

        <div className="flex flex-col gap-1.5">
          <Label htmlFor="jev-state" className="text-xs">
            {t("nodeForms.jev.state")}
          </Label>
          <Textarea
            id="jev-state"
            className="text-xs font-mono"
            value={formData.state}
            onChange={(e) =>
              setFormData((prev) => ({ ...prev, state: e.target.value }))
            }
          />
          <p className="text-xs text-muted-foreground">
            {t("nodeForms.jev.stateHint")}
          </p>
        </div>

        <div className="space-y-2">
          <div className="flex items-center justify-between">
            <Label>{t("nodeForms.jev.questions")}</Label>
            <Button
              type="button"
              size="icon-sm"
              variant="ghost"
              onClick={handleAddQuestion}
            >
              <PlusIcon />
            </Button>
          </div>
          {formData.questions.map((question, index) => (
            <div key={index} className="space-y-2 rounded-md border p-2">
              <div className="flex gap-2 items-center">
                <Input
                  className="text-xs flex-1"
                  value={question.name}
                  onChange={(e) =>
                    updateQuestion(index, { name: e.target.value })
                  }
                  placeholder={t("nodeForms.jev.questionName")}
                />
                <Select
                  value={question.type}
                  onValueChange={(value) =>
                    handleTypeChange(index, value as JevQuestionType)
                  }
                >
                  <SelectTrigger className="text-xs w-28">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="noul" className="text-xs">
                      {t("nodeForms.jev.typeNoul")}
                    </SelectItem>
                    <SelectItem value="choice" className="text-xs">
                      {t("nodeForms.jev.typeChoice")}
                    </SelectItem>
                    <SelectItem value="score" className="text-xs">
                      {t("nodeForms.jev.typeScore")}
                    </SelectItem>
                  </SelectContent>
                </Select>
                <Button
                  type="button"
                  size="icon-sm"
                  variant="ghost"
                  disabled={index === 0}
                  onClick={() => handleMoveQuestion(index, -1)}
                >
                  <ArrowUpIcon className="size-3" />
                </Button>
                <Button
                  type="button"
                  size="icon-sm"
                  variant="ghost"
                  disabled={index === formData.questions.length - 1}
                  onClick={() => handleMoveQuestion(index, 1)}
                >
                  <ArrowDownIcon className="size-3" />
                </Button>
                <Button
                  type="button"
                  size="icon-sm"
                  variant="ghost"
                  disabled={formData.questions.length === 1}
                  onClick={() => handleRemoveQuestion(index)}
                >
                  <TrashIcon className="size-3" />
                </Button>
              </div>
              <Textarea
                className="text-xs"
                value={question.instructions}
                onChange={(e) =>
                  updateQuestion(index, { instructions: e.target.value })
                }
                placeholder={t("nodeForms.jev.instructions")}
              />
              {question.type === "noul" && renderNoulFields(question, index)}
              {question.type === "choice" &&
                renderChoiceFields(question, index)}
              {question.type === "score" && renderScoreFields(question, index)}
              <p className="text-xs text-muted-foreground font-mono">
                input.{formData.outputKey || "jev"}.{question.name || "…"}.
                {question.type}
              </p>
            </div>
          ))}
        </div>

        <div className="flex justify-between gap-4 items-center">
          <Label htmlFor="jev-long-context">
            {t("nodeForms.jev.longContext")}
          </Label>
          <Switch
            id="jev-long-context"
            checked={formData.longContext}
            onCheckedChange={(checked) =>
              setFormData((prev) => ({ ...prev, longContext: checked }))
            }
            showIcons={false}
          />
        </div>
        <p className="text-xs text-muted-foreground">
          {t("nodeForms.jev.longContextHint")}
        </p>

        <div className="flex flex-col gap-1.5">
          <Label htmlFor="jev-output-key" className="text-xs">
            {t("nodeForms.jev.outputKey")}
          </Label>
          <Input
            id="jev-output-key"
            className="text-xs"
            value={formData.outputKey}
            onChange={(e) =>
              setFormData((prev) => ({ ...prev, outputKey: e.target.value }))
            }
          />
        </div>
      </div>
    </BaseForm>
  );
};
