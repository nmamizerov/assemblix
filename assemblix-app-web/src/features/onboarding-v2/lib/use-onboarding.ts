import { useCallback, useRef } from "react";
import { useTranslation } from "react-i18next";
import { driver } from "driver.js";
import type { Driver } from "driver.js";
import "driver.js/dist/driver.css";

import { useMeQuery, useUpdateMeMutation } from "@/entities/session";
import { getCommunityLinks } from "@/shared/lib/community-links";

export const useOnboarding = () => {
  const { t, i18n } = useTranslation();

  const { data: user } = useMeQuery();
  const [updateMe] = useUpdateMeMutation();
  const driverRef = useRef<Driver | null>(null);

  const isNewUser = !!user && user.onboarding?.seenWelcome !== true;

  // Запуск тура по canvas с driver.js
  const startCanvasTour = useCallback(() => {
    // Ждём пока элементы отрендерятся на странице
    const waitForElement = (selector: string, timeout = 5000): Promise<Element | null> => {
      return new Promise((resolve) => {
        const element = document.querySelector(selector);
        if (element) {
          resolve(element);
          return;
        }

        const observer = new MutationObserver(() => {
          const element = document.querySelector(selector);
          if (element) {
            observer.disconnect();
            resolve(element);
          }
        });

        observer.observe(document.body, {
          childList: true,
          subtree: true,
        });

        setTimeout(() => {
          observer.disconnect();
          resolve(null);
        }, timeout);
      });
    };

    // Ждём появления сайдбара перед запуском тура
    waitForElement('[data-tour="sidebar"]').then((sidebarElement) => {
      if (!sidebarElement) {
        console.warn('Sidebar not found, skipping tour');
        return;
      }

      const driverObj = driver({
        showProgress: true,
        progressText: t("onboarding.progress", {
          current: "{{current}}",
          total: "{{total}}",
        }),
        nextBtnText: t("common.next"),
        prevBtnText: t("common.back"),
        doneBtnText: t("onboarding.steps.final.startButton"),
        allowClose: true,
        smoothScroll: true,
        stagePadding: 8,
        stageRadius: 8,
        onDestroyed: async () => {
          await updateMe({ onboarding: { tourCompleted: true } });
          driverRef.current = null;

          // Автоматически открываем Debug Panel после завершения тура
          setTimeout(() => {
            const debugButton = document.querySelector<HTMLElement>('[data-tour="debug-button"]');
            if (debugButton) {
              debugButton.click();
            }
          }, 300);
        },
        steps: [
        // Step 1: Sidebar с нодами
        {
          element: '[data-tour="sidebar"]',
          popover: {
            title: t("onboarding.steps.sidebar.title"),
            description: t("onboarding.steps.sidebar.description"),
            side: "right",
            align: "start",
          },
        },
        // Step 2: Агентская нода в сайдбаре
        {
          element: '[data-tour="agent-node"]',
          popover: {
            title: t("onboarding.steps.agentNode.title"),
            description: t("onboarding.steps.agentNode.description"),
            side: "right",
            align: "center",
          },
        },
        // Step 3: Debug mode
        {
          element: '[data-tour="debug-button"]',
          popover: {
            title: t("onboarding.steps.debug.title"),
            description: t("onboarding.steps.debug.description"),
            side: "bottom",
            align: "center",
          },
        },
        // Step 4: Publish
        {
          element: '[data-tour="publish-button"]',
          popover: {
            title: t("onboarding.steps.publish.title"),
            description: t("onboarding.steps.publish.description"),
            side: "bottom",
            align: "center",
          },
        },
        // Step 5: Final
        {
          popover: {
            title: t("onboarding.steps.final.title"),
            description: t("onboarding.steps.final.description"),
            side: "over",
            showButtons: ['close'], // Показываем кнопку закрытия
          },
          // @ts-expect-error - onPopoverRender exists in driver.js but not in type definitions
          onPopoverRender: (popover: { footerButtons: HTMLElement }) => {
            // Кнопка завершения
            const doneBtn = document.createElement("button");
            doneBtn.className = "driver-popover-btn driver-popover-prev-btn";
            doneBtn.textContent = t("onboarding.steps.final.startButton");
            doneBtn.onclick = () => {
              driverObj.destroy();
            };

            // Кнопка Telegram
            const telegramBtn = document.createElement("button");
            telegramBtn.className =
              "driver-popover-btn driver-popover-next-btn";
            telegramBtn.textContent = t(
              "onboarding.steps.final.telegramButton"
            );
            telegramBtn.onclick = () => {
              window.open(getCommunityLinks(i18n.language).community, "_blank");
            };

            // Добавляем кастомные кнопки к существующим
            popover.footerButtons.appendChild(doneBtn);
            popover.footerButtons.appendChild(telegramBtn);
          },
        },
      ],
      });

      driverRef.current = driverObj;
      driverObj.drive();
    });
  }, [t, updateMe, i18n.language]);

  // Отмечаем, что приветствие просмотрено
  const completeWelcome = useCallback(async () => {
    await updateMe({ onboarding: { seenWelcome: true } });
  }, [updateMe]);

  return {
    isNewUser,
    startCanvasTour,
    completeWelcome,
  };
};
