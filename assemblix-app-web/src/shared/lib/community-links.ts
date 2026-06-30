export const COMMUNITY_LINKS = {
  en: {
    community: "https://discord.gg/KJyaWfJ9",
    support: "https://discord.gg/KJyaWfJ9",
    label: "Discord Community",
    supportLabel: "Help",
  },
} as const;

export const getCommunityLinks = (lang: string) =>
  COMMUNITY_LINKS[lang as keyof typeof COMMUNITY_LINKS] ?? COMMUNITY_LINKS.en;
