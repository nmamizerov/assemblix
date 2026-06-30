import { useMemo, useState } from "react";
import { useTranslation } from "react-i18next";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/shared/ui/dialog";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/shared/ui/tabs";
import { Button } from "@/shared/ui/button";
import { ObjectConstructor } from "./object-constructor";
import { JsonValueEditor } from "./json-value-editor";
import { objectToRows, rowsToObject } from "./conversions";
import type { JsonObject, PropertyRow } from "./types";

interface ObjectValueEditorProps {
  open: boolean;
  initialValue: JsonObject;
  onOpenChange: (open: boolean) => void;
  onSave: (value: JsonObject) => void;
}

type TabValue = "constructor" | "json";

interface EditorBodyProps {
  initialValue: JsonObject;
  onOpenChange: (open: boolean) => void;
  onSave: (value: JsonObject) => void;
}

const EditorBody = ({
  initialValue,
  onOpenChange,
  onSave,
}: EditorBodyProps) => {
  const { t } = useTranslation();
  const [tab, setTab] = useState<TabValue>("constructor");
  const [rows, setRows] = useState<PropertyRow[]>(() =>
    objectToRows(initialValue),
  );

  // Единый источник правды — rows. JSON-редактор получает объект, собранный
  // из rows, и при правке возвращает разобранный объект обратно в rows.
  const objectValue = useMemo(() => rowsToObject(rows), [rows]);

  const handleTabChange = (next: string) => {
    setTab(next as TabValue);
  };

  const handleSave = () => {
    onSave(rowsToObject(rows));
    onOpenChange(false);
  };

  return (
    <>
      <DialogHeader>
        <DialogTitle>{t("objectValueEditor.title")}</DialogTitle>
        <DialogDescription>
          {t("objectValueEditor.description")}
        </DialogDescription>
      </DialogHeader>

      <Tabs value={tab} onValueChange={handleTabChange}>
        <TabsList className="grid w-full grid-cols-2">
          <TabsTrigger value="constructor">
            {t("objectValueEditor.tabConstructor")}
          </TabsTrigger>
          <TabsTrigger value="json">
            {t("objectValueEditor.tabJson")}
          </TabsTrigger>
        </TabsList>

        <TabsContent value="constructor" className="mt-3">
          <div className="max-h-[420px] overflow-y-auto pr-1">
            <ObjectConstructor rows={rows} onChange={setRows} />
          </div>
        </TabsContent>

        <TabsContent value="json" className="mt-3">
          <JsonValueEditor
            value={objectValue}
            onChange={(next) => setRows(objectToRows(next))}
          />
        </TabsContent>
      </Tabs>

      <DialogFooter>
        <Button
          type="button"
          variant="ghost"
          onClick={() => onOpenChange(false)}
        >
          {t("common.cancel")}
        </Button>
        <Button type="button" onClick={handleSave}>
          {t("common.save")}
        </Button>
      </DialogFooter>
    </>
  );
};

export const ObjectValueEditor = ({
  open,
  initialValue,
  onOpenChange,
  onSave,
}: ObjectValueEditorProps) => {
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-xl">
        {open && (
          <EditorBody
            initialValue={initialValue}
            onOpenChange={onOpenChange}
            onSave={onSave}
          />
        )}
      </DialogContent>
    </Dialog>
  );
};
