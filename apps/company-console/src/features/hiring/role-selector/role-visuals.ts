export const ROLE_CATEGORY_VISUALS: Record<
  string,
  { icon: string; glowClassName: string }
> = {
  backend: {
    icon: "/role-category-selector/role-categories/role-category-backend.png",
    glowClassName: "bg-[#dceecf]",
  },
  frontend: {
    icon: "/role-category-selector/role-categories/role-category-frontend.png",
    glowClassName: "bg-[#d8edf6]",
  },
  mobile: {
    icon: "/role-category-selector/role-categories/role-category-mobile.png",
    glowClassName: "bg-[#e4edf8]",
  },
  devops: {
    icon: "/role-category-selector/role-categories/role-category-devops.png",
    glowClassName: "bg-[#dcf0ec]",
  },
  data: {
    icon: "/role-category-selector/role-categories/role-category-data.png",
    glowClassName: "bg-[#dceaf5]",
  },
  ai: {
    icon: "/role-category-selector/role-categories/role-category-ai-ml.png",
    glowClassName: "bg-[#e2f2d5]",
  },
  security: {
    icon: "/role-category-selector/role-categories/role-category-security.png",
    glowClassName: "bg-[#dce7f2]",
  },
  qa: {
    icon: "/role-category-selector/role-categories/role-category-qa-automation.png",
    glowClassName: "bg-[#e7f0dc]",
  },
};

export const ROLE_DETAIL_ICONS = {
  common: "/role-category-selector/role-details/role-detail-common.png",
  service: "/role-category-selector/role-details/role-detail-service.png",
  platform: "/role-category-selector/role-details/role-detail-platform.png",
  dataApi: "/role-category-selector/role-details/role-detail-data-api.png",
  operations: "/role-category-selector/role-details/role-detail-operations.png",
  quality: "/role-category-selector/role-details/role-detail-quality.png",
} as const;

export function getRoleCategoryVisual(categoryId: string) {
  return ROLE_CATEGORY_VISUALS[categoryId] ?? ROLE_CATEGORY_VISUALS.backend;
}

export function getRoleDetailIcon(roleId?: string | null) {
  if (!roleId) return ROLE_DETAIL_ICONS.common;
  if (/(platform|infra|cloud|sre|devops|mlops|mobile-platform)/.test(roleId)) {
    return ROLE_DETAIL_ICONS.platform;
  }
  if (/(data|api|analytics|bi)/.test(roleId)) {
    return ROLE_DETAIL_ICONS.dataApi;
  }
  if (/(security|qa|test|appsec|automation)/.test(roleId)) {
    return ROLE_DETAIL_ICONS.quality;
  }
  if (/(ops|reliability|transaction)/.test(roleId)) {
    return ROLE_DETAIL_ICONS.operations;
  }
  return ROLE_DETAIL_ICONS.service;
}
