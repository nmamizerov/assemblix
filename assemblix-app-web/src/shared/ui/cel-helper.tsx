import { useState } from "react";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/shared/ui/dialog";
import { Button } from "@/shared/ui/button";

export function CELHelper() {
  const [open, setOpen] = useState(false);

  return (
    <>
      <div className="text-xs text-muted-foreground">
        Используйте Common Expression Language для создания выражения.{" "}
        <button
          type="button"
          onClick={() => setOpen(true)}
          className="text-primary hover:underline font-medium"
        >
          Узнать больше
        </button>
      </div>

      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent className="max-w-2xl max-h-[80vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle>Common Expression Language</DialogTitle>
          </DialogHeader>

          <div className="space-y-6 text-sm">
            <p className="text-muted-foreground">
              CEL позволяет писать небольшие, но мощные выражения для проверки и
              преобразования данных вашего агента. Вы можете комбинировать
              переменные и операторы для выражения сложной логики без написания
              полноценной программы.
            </p>

            {/* Доступ к переменным */}
            <div className="space-y-3">
              <h3 className="font-semibold text-base">Доступ к переменным</h3>
              <div className="space-y-2">
                <div className="rounded-md bg-muted p-3">
                  <code className="text-sm font-mono text-purple-600 dark:text-purple-400">
                    state.customer.tier
                  </code>
                  <p className="text-xs text-muted-foreground mt-1">
                    – глобальное состояние, хранимое между узлами
                  </p>
                </div>
                <div className="rounded-md bg-muted p-3">
                  <code className="text-sm font-mono text-purple-600 dark:text-purple-400">
                    input.results[0]
                  </code>
                  <p className="text-xs text-muted-foreground mt-1">
                    – значения из предыдущего узла
                  </p>
                </div>
                <div className="rounded-md bg-muted p-3">
                  <code className="text-sm font-mono text-purple-600 dark:text-purple-400">
                    workflow.input_as_text
                  </code>
                  <p className="text-xs text-muted-foreground mt-1">
                    – входные значения для этого запуска workflow
                  </p>
                </div>
              </div>
            </div>

            {/* Сравнения */}
            <div className="space-y-3">
              <h3 className="font-semibold text-base">Сравнения</h3>
              <div className="space-y-2">
                <div className="rounded-md bg-muted p-3">
                  <code className="text-sm font-mono">
                    input.score <span className="text-foreground">&gt;=</span>{" "}
                    <span className="text-purple-600 dark:text-purple-400">
                      0.8
                    </span>
                  </code>
                </div>
                <div className="rounded-md bg-muted p-3">
                  <code className="text-sm font-mono">
                    state.customer.tier{" "}
                    <span className="text-foreground">==</span>{" "}
                    <span className="text-purple-600 dark:text-purple-400">
                      "gold"
                    </span>
                  </code>
                </div>
                <div className="rounded-md bg-muted p-3">
                  <code className="text-sm font-mono">
                    input.tags <span className="text-foreground">!=</span> null
                  </code>
                </div>
              </div>
            </div>

            {/* Операторы */}
            <div className="space-y-3">
              <h3 className="font-semibold text-base">Операторы</h3>
              <div className="space-y-2">
                <div className="rounded-md bg-muted p-3">
                  <code className="text-sm font-mono">
                    (input.score <span className="text-foreground">*</span>{" "}
                    <span className="text-purple-600 dark:text-purple-400">
                      100
                    </span>
                    ) <span className="text-foreground">-</span>{" "}
                    <span className="text-purple-600 dark:text-purple-400">
                      20
                    </span>
                  </code>
                </div>
                <div className="rounded-md bg-muted p-3">
                  <code className="text-sm font-mono">
                    input.score <span className="text-foreground">&gt;</span>{" "}
                    (state.flags.beta <span className="text-foreground">?</span>{" "}
                    <span className="text-purple-600 dark:text-purple-400">
                      0.9
                    </span>{" "}
                    <span className="text-foreground">:</span>{" "}
                    <span className="text-purple-600 dark:text-purple-400">
                      0.8
                    </span>
                    )
                  </code>
                </div>
                <div className="rounded-md bg-muted p-3">
                  <code className="text-sm font-mono">
                    <span className="text-purple-600 dark:text-purple-400">
                      "The region is: "
                    </span>{" "}
                    <span className="text-foreground">+</span> input.metadata[
                    <span className="text-purple-600 dark:text-purple-400">
                      "region"
                    </span>
                    ]
                  </code>
                </div>
              </div>
            </div>

            {/* Макросы */}
            <div className="space-y-3">
              <h3 className="font-semibold text-base">Макросы</h3>
              <div className="space-y-2">
                <div className="rounded-md bg-muted p-3">
                  <code className="text-sm font-mono">
                    input.authors[size(input.authors){" "}
                    <span className="text-foreground">-</span>{" "}
                    <span className="text-purple-600 dark:text-purple-400">
                      1
                    </span>
                    ]
                  </code>
                </div>
                <div className="rounded-md bg-muted p-3">
                  <code className="text-sm font-mono">
                    <span className="text-purple-600 dark:text-purple-400">
                      "Patrick Star"
                    </span>{" "}
                    <span className="text-foreground">in</span> state.employees
                  </code>
                </div>
                <div className="rounded-md bg-muted p-3">
                  <code className="text-sm font-mono">
                    state.emails.all(email, email.contains(
                    <span className="text-purple-600 dark:text-purple-400">
                      "@"
                    </span>
                    ))
                  </code>
                </div>
              </div>
            </div>

            {/* Ссылка */}
            <div className="pt-4 border-t">
              <p className="text-xs text-muted-foreground">
                Узнайте больше на{" "}
                <a
                  href="https://cel.dev"
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-primary hover:underline font-medium"
                >
                  cel.dev
                </a>
              </p>
            </div>

            {/* Кнопка закрыть */}
            <div className="flex justify-end pt-2">
              <Button onClick={() => setOpen(false)} variant="outline">
                Закрыть
              </Button>
            </div>
          </div>
        </DialogContent>
      </Dialog>
    </>
  );
}
