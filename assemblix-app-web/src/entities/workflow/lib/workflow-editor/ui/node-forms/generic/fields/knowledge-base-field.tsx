import { useSelector } from "react-redux";
import { Label } from "@/shared/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/shared/ui/select";
import { useGetKnowledgeBasesQuery } from "@/entities/knowledge-base";
import { selectCurrentProjectId } from "@/entities/organization";
import type { NodeProperty } from "../../../../../../model/types";

interface KnowledgeBaseFieldProps {
  property: NodeProperty;
  value: unknown;
  onChange: (value: unknown) => void;
}

/**
 * Knowledge-base picker field.
 * Reuses useGetKnowledgeBasesQuery (same hook as agent-node-form uses).
 * Stores a single KB id string.
 */
export const KnowledgeBaseField = ({ property, value, onChange }: KnowledgeBaseFieldProps) => {
  const currentProjectId = useSelector(selectCurrentProjectId);
  const { data: knowledgeBases = [], isLoading } = useGetKnowledgeBasesQuery(
    { projectId: currentProjectId! },
    { skip: !currentProjectId },
  );

  return (
    <div className="space-y-1.5">
      <Label className="text-xs">{property.displayName}</Label>
      <Select
        value={typeof value === "string" ? value : ""}
        onValueChange={(v) => onChange(v)}
        disabled={isLoading}
      >
        <SelectTrigger className="text-xs">
          <SelectValue placeholder={property.placeholder ?? property.displayName} />
        </SelectTrigger>
        <SelectContent>
          {knowledgeBases.map((kb) => (
            <SelectItem key={kb.id} value={kb.id} className="text-xs">
              {kb.name}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>
      {property.description && (
        <p className="text-[10px] text-muted-foreground">{property.description}</p>
      )}
    </div>
  );
};
