import {
  BriefcaseBusiness,
  ChevronLeft,
  ChevronDown,
  ChevronRight,
  FilePlus2,
  LayoutDashboard,
  Menu,
  Settings2,
  Sparkles,
  UserRound,
  Users,
  X,
} from "lucide-react";
import { useState } from "react";
import { NavLink, Outlet, useLocation } from "react-router-dom";

import whyYouLogo from "../../assets/whyyou-logo.png";

const navigation = [
  { label: "대시보드", to: "/company", icon: LayoutDashboard },
  { label: "채용 포지션", to: "/positions", icon: BriefcaseBusiness },
  { label: "지원자 관리", to: "/applicants", icon: Users },
  { label: "AI 어시스턴트", to: "/ai-assistant", icon: Sparkles },
  { label: "채용 관리", to: "/hiring", icon: FilePlus2 },
] as const;

const pageTitles = [
  { path: "/company", title: "대시보드" },
  { path: "/positions/", title: "포지션 운영" },
  { path: "/positions", title: "채용 포지션" },
  { path: "/applicants", title: "지원자 관리" },
  { path: "/ai-assistant", title: "AI 채용 어시스턴트" },
  { path: "/hiring", title: "채용 관리" },
  { path: "/review", title: "지원자 검토" },
] as const;

/* On paper only the page content is the document; navigation stays outside the report. */
const SHELL =
  "company-shell-layout min-h-screen bg-canvas transition-[grid-template-columns]" +
  " duration-[160ms] print:block print:bg-transparent";
const SHELL_EXPANDED = `${SHELL} grid-cols-[224px_minmax(0,1fr)]`;
const SHELL_COLLAPSED = `${SHELL} grid-cols-[64px_minmax(0,1fr)]`;
const SKIP_LINK =
  "fixed top-2 left-2 z-200 -translate-y-[160%] rounded-md bg-brand-strong" +
  " px-[11px] py-[7px] text-surface focus-visible:translate-y-0 print:hidden";

const SIDEBAR =
  "company-sidebar-layout z-40 flex flex-col overflow-hidden border-r border-r-border" +
  " bg-surface transition-[width,transform] duration-[160ms] print:hidden";
// These widths must match SHELL_EXPANDED/SHELL_COLLAPSED exactly. Spacing-scale widths use
// rem units, so a browser default font size above 16px makes the sidebar wider than its grid
// column and lets it cover the workspace.
const SIDEBAR_DESKTOP_OPEN = "w-[224px]";
const SIDEBAR_DESKTOP_CLOSED = "w-[64px]";
const SIDEBAR_TOGGLE =
  "absolute top-[30px] right-2 z-10 grid size-6 place-items-center border-0" +
  " bg-transparent p-0 text-subtle transition-colors hover:text-brand";
const SCRIM =
  "hidden mw-760:fixed mw-760:inset-0 mw-760:z-[35] mw-760:block" +
  " mw-760:bg-[rgb(31_35_40_/_35%)] print:hidden";

const BRAND_ROW = "flex min-h-22 items-center px-[22px]";
const BRAND_ROW_COLLAPSED = "min-h-22";
const BRAND = "flex min-w-0 items-center";
const BRAND_LOGO = "h-auto w-[126px] object-contain";

const NAVIGATION = "flex-1 overflow-y-auto p-[10px_14px]";
const NAVIGATION_COLLAPSED = "flex-1 overflow-y-auto px-2 py-2.5";
const NAV_LABEL =
  "p-[10px_12px_6px] font-mono text-[10px] font-semibold text-subtle uppercase";
/*
 * `.company-navigation__item.is-active::before` is set to `display: none` by the later
 * declaration, so the active rail is not reproduced — only the tint, colour and `svg` colour.
 */
const NAV_ITEM =
  "relative my-[3px] flex min-h-11 items-center gap-3 rounded-[9px] px-[13px]" +
  " text-[14px] text-muted hover:bg-surface-strong hover:text-ink";
const NAV_ITEM_ACTIVE = `${NAV_ITEM} bg-[#f2f3ff] font-semibold text-brand [&_svg]:text-brand`;
const NAV_ITEM_COLLAPSED = "justify-center gap-0 px-0";
const SUPPORT =
  "m-[0_14px_12px] grid grid-cols-[28px_minmax(0,1fr)] items-center gap-[9px]" +
  " rounded-[10px] border border-[#e6e8ed] bg-[#fbfbfd] p-3";
const SUPPORT_MARK =
  "grid size-7 place-items-center rounded-full bg-[#f2f3ff] font-bold text-brand";

const USER = "relative border-t border-t-border-muted p-[9px_8px]";
const USER_TRIGGER =
  "grid w-full grid-cols-[25px_minmax(0,1fr)_14px] items-center gap-2" +
  " rounded-lg bg-transparent p-[5px_7px] text-left hover:bg-surface-strong";
const USER_TRIGGER_COLLAPSED =
  "flex w-full items-center justify-center rounded-lg p-[5px] hover:bg-surface-strong";
const USER_AVATAR =
  "grid size-6 place-items-center rounded-full border border-border" +
  " bg-[#edf6ff] text-brand";
const USER_IDENTITY = "grid min-w-0 gap-px";
const USER_MENU =
  "absolute inset-x-2 bottom-[52px] z-[4] rounded-md border border-border" +
  " bg-white p-2.5 shadow-float";
const USER_MENU_COLLAPSED =
  "absolute bottom-[52px] left-2 z-[4] w-[200px] rounded-md border" +
  " border-border bg-white p-2.5 shadow-float";
const USER_MENU_BUTTON =
  "flex min-h-7 w-full items-center justify-center gap-1.5 rounded-[5px]" +
  " border border-border bg-white text-[10px]";

const WORKSPACE =
  "col-start-2 min-w-0 min-h-screen bg-canvas print:bg-transparent";
const TOPBAR =
  "sticky top-0 z-30 flex min-h-[58px] items-center justify-center px-[26px]" +
  " border-b border-border bg-[rgb(255_255_255_/_96%)] backdrop-blur-[12px]" +
  " mw-760:px-[14px] print:hidden";
const TOPBAR_MENU =
  "absolute left-[14px] hidden size-8 place-items-center rounded-md border border-border bg-surface" +
  " font-semibold text-muted hover:bg-surface-muted hover:text-ink mw-760:inline-grid";
const TOPBAR_TITLE = "flex items-center gap-2";
const TOPBAR_CRUMB =
  "text-[12px] text-muted after:ml-2 after:text-subtle after:content-['/']" +
  " mw-760:hidden";
const MAIN = "min-w-0 min-h-[calc(100vh-58px)] print:min-h-0";

export function CompanyShell() {
  const location = useLocation();
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const [userMenuOpen, setUserMenuOpen] = useState(false);
  const pageTitle =
    pageTitles.find((item) => location.pathname.startsWith(item.path))?.title ??
    "기업 콘솔";
  const sidebarClassName = [
    SIDEBAR,
    sidebarCollapsed ? SIDEBAR_DESKTOP_CLOSED : SIDEBAR_DESKTOP_OPEN,
  ].join(" ");
  const compactSidebar = sidebarCollapsed && !mobileMenuOpen;

  return (
    <div className={sidebarCollapsed ? SHELL_COLLAPSED : SHELL_EXPANDED}>
      <a className={SKIP_LINK} href="#company-main">
        본문으로 이동
      </a>

      <aside
        aria-label="기업 콘솔 주 탐색"
        className={sidebarClassName}
        data-mobile-open={mobileMenuOpen}
      >
        <div className={compactSidebar ? BRAND_ROW_COLLAPSED : BRAND_ROW}>
          {compactSidebar ? null : (
            <NavLink className={BRAND} to="/company" aria-label="WhyYou 홈">
              <img
                className={BRAND_LOGO}
                src={whyYouLogo}
                alt="WhyYou"
                width="800"
                height="260"
              />
            </NavLink>
          )}
          <button
            className={SIDEBAR_TOGGLE}
            type="button"
            aria-label={compactSidebar ? "탐색 펼치기" : "탐색 접기"}
            onClick={() => {
              setMobileMenuOpen(false);
              setSidebarCollapsed((collapsed) => !collapsed);
              setUserMenuOpen(false);
            }}
          >
            {compactSidebar ? (
              <ChevronRight size={19} aria-hidden="true" />
            ) : (
              <ChevronLeft size={19} aria-hidden="true" />
            )}
          </button>
        </div>

        <nav
          className={compactSidebar ? NAVIGATION_COLLAPSED : NAVIGATION}
          aria-label="업무 메뉴"
        >
          {compactSidebar ? null : <p className={NAV_LABEL}>채용 운영</p>}
          {navigation.map((item) => {
            const Icon = item.icon;
            return (
              <NavLink
                key={item.to}
                aria-label={item.label}
                className={({ isActive }) =>
                  `${isActive ? NAV_ITEM_ACTIVE : NAV_ITEM} ${
                    compactSidebar ? NAV_ITEM_COLLAPSED : ""
                  }`
                }
                to={item.to}
                title={compactSidebar ? item.label : undefined}
                onClick={() => setMobileMenuOpen(false)}
              >
                <Icon size={18} strokeWidth={1.8} aria-hidden="true" />
                {compactSidebar ? null : <span>{item.label}</span>}
              </NavLink>
            );
          })}

          {location.pathname.startsWith("/review") ? (
            <span
              className={`${NAV_ITEM_ACTIVE} ${compactSidebar ? NAV_ITEM_COLLAPSED : ""}`}
              aria-current="page"
              title={compactSidebar ? "지원자 검토" : undefined}
            >
              <Settings2 size={18} strokeWidth={1.8} aria-hidden="true" />
              {compactSidebar ? null : <span>지원자 검토</span>}
            </span>
          ) : null}
        </nav>

        {compactSidebar ? null : (
          <div className={SUPPORT}>
            <span className={SUPPORT_MARK} aria-hidden="true">
              ?
            </span>
            <div className="grid gap-0.5">
              <strong className="text-[11px]">채용 운영 도움말</strong>
              <small className="text-[9px] text-muted">
                설정 흐름을 확인하세요
              </small>
            </div>
          </div>
        )}

        <div className={USER}>
          <button
            className={compactSidebar ? USER_TRIGGER_COLLAPSED : USER_TRIGGER}
            type="button"
            aria-label="사용자 메뉴"
            aria-expanded={userMenuOpen}
            onClick={() => setUserMenuOpen((open) => !open)}
          >
            <span className={USER_AVATAR} aria-hidden="true">
              <UserRound size={15} />
            </span>
            {compactSidebar ? null : (
              <>
                <span className={USER_IDENTITY}>
                  <strong className="truncate text-[11px]">채용 담당자</strong>
                  <small className="truncate text-[9px] text-muted">
                    기업 계정
                  </small>
                </span>
                <ChevronDown size={15} aria-hidden="true" />
              </>
            )}
          </button>
          {userMenuOpen ? (
            <div className={compactSidebar ? USER_MENU_COLLAPSED : USER_MENU}>
              <p className="mb-2 grid gap-0.5">
                <strong className="text-[11px]">기업 계정</strong>
                <span className="text-[9px] text-muted">
                  인증된 워크스페이스
                </span>
              </p>
              <button
                className={USER_MENU_BUTTON}
                type="button"
                onClick={() => setUserMenuOpen(false)}
              >
                <X size={14} aria-hidden="true" />
                닫기
              </button>
            </div>
          ) : null}
        </div>
      </aside>

      {mobileMenuOpen ? (
        <button
          className={SCRIM}
          type="button"
          aria-label="탐색 닫기"
          onClick={() => setMobileMenuOpen(false)}
        />
      ) : null}

      <div className={WORKSPACE}>
        <header className={TOPBAR}>
          <button
            className={TOPBAR_MENU}
            type="button"
            aria-label="탐색 열기"
            onClick={() => {
              setMobileMenuOpen(true);
              setSidebarCollapsed(false);
            }}
          >
            <Menu size={19} aria-hidden="true" />
          </button>
          <div className={TOPBAR_TITLE}>
            <span className={TOPBAR_CRUMB}>채용 운영</span>
            <strong className="text-[14px]">{pageTitle}</strong>
          </div>
        </header>
        <main id="company-main" className={MAIN}>
          <Outlet />
        </main>
      </div>
    </div>
  );
}
