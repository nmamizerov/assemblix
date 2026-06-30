import { useMemo, useState } from "react";
import { useTranslation } from "react-i18next";
import { Input } from "../input";
import { Label } from "../label";
import { Button } from "../button";
import { Tabs, TabsList, TabsTrigger } from "../tabs";
import { Plus } from "lucide-react";
import { SchemaPropertyItem } from "./schema-property";
import { JsonCodeEditor } from "./json-code-editor";
import {
  type SchemaProperty,
  type OpenAPISchema,
} from "./types";
import { generateSchema, parseSchemaToProperties } from "./schema-utils";

interface JsonSchemaBuilderProps {
  initialSchema?: OpenAPISchema;
  onSchemaChange?: (schema: OpenAPISchema) => void;
}

export const JsonSchemaBuilder = ({
  initialSchema,
  onSchemaChange,
}: JsonSchemaBuilderProps) => {
  const { t } = useTranslation();
  const [schemaName, setSchemaName] = useState(
    initialSchema?.title || "responseSchema"
  );
  const [properties, setProperties] = useState<SchemaProperty[]>(() =>
    parseSchemaToProperties(initialSchema)
  );
  const [editorMode, setEditorMode] = useState<"simple" | "advanced">(
    "simple"
  );

  // Единый источник правды для JSON-редактора: пересоздаётся только когда
  // реально меняются свойства или название схемы (а не на каждый рендер).
  const currentSchema = useMemo(
    () => generateSchema(properties, schemaName),
    [properties, schemaName]
  );

  const handleAddProperty = () => {
    const newProperty: SchemaProperty = {
      id: crypto.randomUUID(),
      name: "",
      type: "string",
      description: "",
      required: false,
    };
    const updated = [...properties, newProperty];
    setProperties(updated);
    notifySchemaChange(updated);
  };

  const handleUpdateProperty = (index: number, updated: SchemaProperty) => {
    const newProperties = [...properties];
    newProperties[index] = updated;
    setProperties(newProperties);
    notifySchemaChange(newProperties);
  };

  const handleDeleteProperty = (index: number) => {
    const newProperties = properties.filter((_, i) => i !== index);
    setProperties(newProperties);
    notifySchemaChange(newProperties);
  };

  const notifySchemaChange = (props: SchemaProperty[]) => {
    if (onSchemaChange) {
      const schema = generateSchema(props, schemaName);
      onSchemaChange(schema);
    }
  };

  const handleSchemaNameChange = (name: string) => {
    setSchemaName(name);
    if (onSchemaChange) {
      const schema = generateSchema(properties, name);
      onSchemaChange(schema);
    }
  };

  const handleAdvancedSchemaChange = (schema: OpenAPISchema) => {
    if (schema.title) {
      setSchemaName(schema.title);
    }
    const parsed = parseSchemaToProperties(schema);
    setProperties(parsed);
    if (onSchemaChange) {
      onSchemaChange(schema);
    }
  };

  return (
    <div className="space-y-4">
      {/* Заголовок и переключатель режимов */}
      <div className="flex items-center justify-between">
        <div>
          <Label className="text-sm font-medium">
            {t("schemaBuilder.title")}
          </Label>
          <p className="text-xs text-muted-foreground">
            {t("schemaBuilder.description")}
          </p>
        </div>
        <Tabs
          value={editorMode}
          onValueChange={(v) =>
            setEditorMode(v as "simple" | "advanced")
          }
        >
          <TabsList className="h-7">
            <TabsTrigger value="simple" className="text-xs h-6 px-2">
              {t("schemaBuilder.simpleMode")}
            </TabsTrigger>
            <TabsTrigger value="advanced" className="text-xs h-6 px-2">
              {t("schemaBuilder.advancedMode")}
            </TabsTrigger>
          </TabsList>
        </Tabs>
      </div>

      {/* Название схемы */}
      <div className="space-y-2">
        <Label htmlFor="schema-name" className="text-xs">
          {t("schemaBuilder.schemaName")}
        </Label>
        <Input
          id="schema-name"
          value={schemaName}
          onChange={(e) => handleSchemaNameChange(e.target.value)}
          placeholder="responseSchema"
          className="text-xs"
        />
      </div>

      {editorMode === "simple" ? (
        <>
          {/* Свойства */}
          <div className="space-y-2">
            <Label className="text-xs font-medium">
              {t("schemaBuilder.properties")}
            </Label>
            <div className="space-y-2 border rounded-lg p-3 bg-muted/30 max-h-[400px] overflow-y-auto">
              {properties.length === 0 ? (
                <div className="text-center text-xs text-muted-foreground py-4">
                  {t("schemaBuilder.noProperties")}
                </div>
              ) : (
                properties.map((property, index) => (
                  <SchemaPropertyItem
                    key={property.id}
                    property={property}
                    onUpdate={(updated) =>
                      handleUpdateProperty(index, updated)
                    }
                    onDelete={() => handleDeleteProperty(index)}
                  />
                ))
              )}
            </div>

            {/* Кнопка добавления свойства */}
            <Button
              type="button"
              size="sm"
              variant="ghost"
              onClick={handleAddProperty}
              className="w-full"
            >
              <Plus className="h-4 w-4" />
              {t("schemaBuilder.addProperty")}
            </Button>
          </div>
        </>
      ) : (
        <JsonCodeEditor
          schema={currentSchema}
          onSchemaChange={handleAdvancedSchemaChange}
        />
      )}
    </div>
  );
};
