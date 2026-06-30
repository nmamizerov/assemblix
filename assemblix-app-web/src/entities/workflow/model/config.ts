import { Braces, Hash, ToggleLeft, Type, type LucideProps } from "lucide-react";
import type { ForwardRefExoticComponent, RefAttributes } from "react";

export interface VariableTypeConfigItem {
  type: "string" | "number" | "boolean" | "object";
  label: string;
  icon: ForwardRefExoticComponent<LucideProps & RefAttributes<SVGSVGElement>>;
  color: string;
}

export const VARIABLE_TYPE_CONFIG: Record<
  "string" | "number" | "boolean" | "object",
  VariableTypeConfigItem
> = {
  string: {
    type: "string",
    label: "String",
    icon: Type,
    color: "text-indigo-500",
  },
  number: {
    type: "number",
    label: "Number",
    icon: Hash,
    color: "text-green-500",
  },
  boolean: {
    type: "boolean",
    label: "Boolean",
    icon: ToggleLeft,
    color: "text-purple-500",
  },
  object: {
    type: "object",
    label: "Object",
    icon: Braces,
    color: "text-orange-500",
  },
};
