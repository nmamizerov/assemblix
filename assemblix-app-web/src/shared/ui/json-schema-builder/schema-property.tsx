import { Input } from "../input";
import { Label } from "../label";
import { Button } from "../button";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "../select";
import { Trash2, Plus, X } from "lucide-react";
import { type SchemaProperty, TYPE_LABELS, TYPE_ICONS } from "./types";
import type { SchemaPropertyType } from "./types";

interface SchemaPropertyItemProps {
  property: SchemaProperty;
  level?: number;
  onUpdate: (property: SchemaProperty) => void;
  onDelete: () => void;
}

export const SchemaPropertyItem = ({
  property,
  level = 0,
  onUpdate,
  onDelete,
}: SchemaPropertyItemProps) => {
  const handleNameChange = (name: string) => {
    onUpdate({ ...property, name });
  };

  const handleTypeChange = (type: SchemaPropertyType) => {
    const updatedProperty: SchemaProperty = { ...property, type };

    // Инициализируем дополнительные поля для типов
    if (type === "enum" && !updatedProperty.enumValues) {
      updatedProperty.enumValues = [];
    } else if (type === "object" && !updatedProperty.properties) {
      updatedProperty.properties = [];
    } else if (type === "array" && !updatedProperty.items) {
      updatedProperty.items = {
        id: crypto.randomUUID(),
        name: "item",
        type: "string",
        description: "",
      };
    }

    // Очищаем ненужные поля при смене типа
    if (type !== "enum") delete updatedProperty.enumValues;
    if (type !== "object") delete updatedProperty.properties;
    if (type !== "array") delete updatedProperty.items;

    onUpdate(updatedProperty);
  };

  const handleDescriptionChange = (description: string) => {
    onUpdate({ ...property, description });
  };

  const handleAddEnumValue = () => {
    const enumValues = [...(property.enumValues || []), ""];
    onUpdate({ ...property, enumValues });
  };

  const handleEnumValueChange = (index: number, value: string) => {
    const enumValues = [...(property.enumValues || [])];
    enumValues[index] = value;
    onUpdate({ ...property, enumValues });
  };

  const handleRemoveEnumValue = (index: number) => {
    const enumValues = property.enumValues?.filter((_, i) => i !== index);
    onUpdate({ ...property, enumValues });
  };

  const handleAddNestedProperty = () => {
    const newProperty: SchemaProperty = {
      id: crypto.randomUUID(),
      name: "",
      type: "string",
      description: "",
    };

    if (property.type === "object") {
      const properties = [...(property.properties || []), newProperty];
      onUpdate({ ...property, properties });
    }
  };

  const handleUpdateNestedProperty = (
    index: number,
    updated: SchemaProperty
  ) => {
    if (property.type === "object") {
      const properties = [...(property.properties || [])];
      properties[index] = updated;
      onUpdate({ ...property, properties });
    }
  };

  const handleDeleteNestedProperty = (index: number) => {
    if (property.type === "object") {
      const properties = property.properties?.filter((_, i) => i !== index);
      onUpdate({ ...property, properties });
    }
  };

  const handleUpdateArrayItem = (updated: SchemaProperty) => {
    onUpdate({ ...property, items: updated });
  };

  const paddingLeft = level * 24;

  return (
    <div className="space-y-2">
      {/* Основная строка свойства */}
      <div
        className="flex items-center gap-2"
        style={{ paddingLeft: `${paddingLeft}px` }}
      >
        {/* Иконка типа */}
        <div className="flex items-center justify-center w-6 h-6 text-muted-foreground text-xs shrink-0">
          {TYPE_ICONS[property.type]}
        </div>

        {/* Название */}
        <Input
          value={property.name}
          onChange={(e) => handleNameChange(e.target.value)}
          placeholder="Property name"
          className="h-8 text-xs flex-1 min-w-[120px]"
        />

        {/* Тип */}
        <Select value={property.type} onValueChange={handleTypeChange}>
          <SelectTrigger className="h-8 w-[80px] text-xs">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            {(Object.keys(TYPE_LABELS) as SchemaPropertyType[]).map((type) => (
              <SelectItem key={type} value={type} className="text-xs">
                {TYPE_LABELS[type]}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>

        {/* Описание */}
        <Input
          value={property.description}
          onChange={(e) => handleDescriptionChange(e.target.value)}
          placeholder="Add description"
          className="h-8 text-xs flex-1 min-w-[150px]"
        />

        {/* Удалить */}
        <Button
          type="button"
          size="icon-sm"
          variant="ghost"
          onClick={onDelete}
          className="shrink-0"
        >
          <Trash2 className="h-3 w-3" />
        </Button>
      </div>

      {/* Enum значения */}
      {property.type === "enum" && (
        <div
          className="space-y-2"
          style={{ paddingLeft: `${paddingLeft + 24}px` }}
        >
          <div className="flex flex-wrap gap-2 items-center">
            {property.enumValues?.map((value, index) => (
              <div
                key={index}
                className="flex items-center gap-1 bg-muted px-2 py-1 rounded text-xs"
              >
                <Input
                  value={value}
                  onChange={(e) => handleEnumValueChange(index, e.target.value)}
                  placeholder="value"
                  className="h-6 text-xs w-20 px-1"
                />
                <button
                  type="button"
                  onClick={() => handleRemoveEnumValue(index)}
                  className="hover:text-destructive"
                >
                  <X className="h-3 w-3" />
                </button>
              </div>
            ))}
            <Button
              type="button"
              size="sm"
              variant="ghost"
              onClick={handleAddEnumValue}
              className="h-6 text-xs"
            >
              <Plus className="h-3 w-3" />
              Add value
            </Button>
          </div>
        </div>
      )}

      {/* Вложенные свойства для object */}
      {property.type === "object" && (
        <div className="space-y-2">
          {property.properties?.map((nested, index) => (
            <SchemaPropertyItem
              key={nested.id}
              property={nested}
              level={level + 1}
              onUpdate={(updated) => handleUpdateNestedProperty(index, updated)}
              onDelete={() => handleDeleteNestedProperty(index)}
            />
          ))}
          <div style={{ paddingLeft: `${paddingLeft + 24}px` }}>
            <Button
              type="button"
              size="sm"
              variant="ghost"
              onClick={handleAddNestedProperty}
              className="h-7 text-xs"
            >
              <Plus className="h-3 w-3" />
              Add property
            </Button>
          </div>
        </div>
      )}

      {/* Элементы для array */}
      {property.type === "array" && property.items && (
        <div style={{ paddingLeft: `${paddingLeft + 24}px` }}>
          <Label className="text-xs text-muted-foreground mb-2">
            Array items type:
          </Label>
          <SchemaPropertyItem
            property={property.items}
            level={level + 1}
            onUpdate={handleUpdateArrayItem}
            onDelete={() => {
              // Нельзя удалить items, но можно сбросить на базовый тип
              handleUpdateArrayItem({
                id: crypto.randomUUID(),
                name: "item",
                type: "string",
                description: "",
              });
            }}
          />
        </div>
      )}
    </div>
  );
};
