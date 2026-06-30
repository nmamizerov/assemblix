import { ChevronLeft, ChevronRight } from "lucide-react";
import { Button } from "./button";
import { cn } from "@/shared/lib/utils";

interface PaginationProps {
  currentPage: number;
  totalPages: number;
  onPageChange: (page: number) => void;
  className?: string;
}

export const Pagination = ({
  currentPage,
  totalPages,
  onPageChange,
  className,
}: PaginationProps) => {
  const handlePrevious = () => {
    if (currentPage > 1) {
      onPageChange(currentPage - 1);
    }
  };

  const handleNext = () => {
    if (currentPage < totalPages) {
      onPageChange(currentPage + 1);
    }
  };

  if (totalPages <= 1) {
    return null;
  }

  return (
    <div
      className={cn("flex items-center justify-center gap-2 py-4", className)}
    >
      <Button
        variant="outline"
        size="sm"
        onClick={handlePrevious}
        disabled={currentPage === 1}
      >
        <ChevronLeft className="h-4 w-4" />
        Предыдущая
      </Button>

      <span className="text-sm text-muted-foreground">
        Страница {currentPage} из {totalPages}
      </span>

      <Button
        variant="outline"
        size="sm"
        onClick={handleNext}
        disabled={currentPage === totalPages}
      >
        Следующая
        <ChevronRight className="h-4 w-4" />
      </Button>
    </div>
  );
};
