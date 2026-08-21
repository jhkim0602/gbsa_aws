import {
  Bell,
  BriefcaseBusiness,
  ChevronDown,
  ExternalLink,
  FilePlus2,
  LayoutDashboard,
  Mail,
  Menu,
  PanelLeftClose,
  Settings2,
  UserRound,
  Users,
  X,
} from "lucide-react";
import { useState } from "react";
import { NavLink, Outlet, useLocation } from "react-router-dom";

import { ICON_BUTTON } from "../styles/primitives";

const navigation = [
  { label: "대시보드", to: "/company", icon: LayoutDashboard },
  { label: "채용 포지션", to: "/positions", icon: BriefcaseBusiness },
  { label: "지원자 관리", to: "/applicants", icon: Users },
  { label: "채용 관리", to: "/hiring", icon: FilePlus2 },
] as const;

const settingsNavigation = [
  { label: "초대 메일 템플릿", to: "/settings/invitation-email", icon: Mail },
] as const;

const pageTitles = [
  { path: "/company", title: "대시보드" },
  { path: "/positions/", title: "포지션 운영" },
  { path: "/positions", title: "채용 포지션" },
  { path: "/applicants", title: "지원자 관리" },
  { path: "/hiring", title: "채용 관리" },
  { path: "/review", title: "지원자 검토" },
  { path: "/settings/invitation-email", title: "초대 메일 템플릿" },
] as const;

/*
 * On paper only the page content is the document — the sidebar and topbar are navigation, and
 * printing a review report used to repeat them on every sheet. The `print:` variant emits
 * after `mw-760:`, so the print rules win at every width without extra specificity.
 */
const SHELL =
  "grid min-h-screen bg-canvas transition-[grid-template-columns] duration-[160ms]" +
  " mw-760:block print:block print:bg-transparent";
const SHELL_EXPANDED = `${SHELL} grid-cols-[224px_minmax(0,1fr)]`;
const SHELL_COLLAPSED = `${SHELL} grid-cols-[0_minmax(0,1fr)]`;
const SKIP_LINK =
  "fixed top-2 left-2 z-200 -translate-y-[160%] rounded-md bg-brand-strong" +
  " px-[11px] py-[7px] text-surface focus-visible:translate-y-0 print:hidden";

const SIDEBAR =
  "fixed inset-[0_auto_0_0] z-40 flex h-screen w-56 flex-col border-r" +
  " border-r-border bg-surface transition-transform duration-[160ms]" +
  " mw-760:top-0 mw-760:h-screen mw-760:w-[min(292px,88vw)] mw-760:shadow-float" +
  " print:hidden";
const SIDEBAR_DESKTOP_OPEN = "translate-x-0";
const SIDEBAR_DESKTOP_CLOSED = "invisible -translate-x-[105%]";
const SIDEBAR_MOBILE_OPEN = "mw-760:translate-x-0";
const SIDEBAR_MOBILE_CLOSED = "mw-760:-translate-x-[105%]";
/*
 * `.company-sidebar__close { display: none }` and its 760px `display: inline-flex` are both
 * outranked in the bundle: hiring.css's `.icon-button { display: inline-grid }` is declared
 * later at equal specificity, so the button has always been visible at every width. Same for
 * `.company-topbar__menu` below. Reproducing the rendered result, not the source intent.
 */
const SIDEBAR_CLOSE = `ml-auto ${ICON_BUTTON}`;
const SCRIM =
  "hidden mw-760:fixed mw-760:inset-0 mw-760:z-[35] mw-760:block" +
  " mw-760:bg-[rgb(31_35_40_/_35%)] print:hidden";

const BRAND_ROW = "flex min-h-22 items-center px-[22px]";
const BRAND = "flex min-w-0 items-center gap-[11px]";
const BRAND_MARK =
  "grid size-9 flex-[0_0_36px] place-items-center rounded-[10px] bg-brand" +
  " text-[12px] font-extrabold text-white";
const BRAND_TEXT = "grid gap-0.5";
const BRAND_NAME = "text-[17px] tracking-[-0.01em]";
const BRAND_TAGLINE = "text-[9px] tracking-[0.08em] text-muted uppercase";

const NAVIGATION = "flex-1 overflow-y-auto p-[10px_14px]";
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
const NAV_DIVIDER = "m-[10px_8px] border-t border-t-border-muted";

const SUPPORT =
  "m-[0_14px_12px] grid grid-cols-[28px_minmax(0,1fr)] items-center gap-[9px]" +
  " rounded-[10px] border border-[#e6e8ed] bg-[#fbfbfd] p-3";
const SUPPORT_MARK =
  "grid size-7 place-items-center rounded-full bg-[#f2f3ff] font-bold text-brand";

const USER = "relative border-t border-t-border-muted p-[9px_8px]";
const USER_TRIGGER =
  "grid w-full grid-cols-[25px_minmax(0,1fr)_14px] items-center gap-2" +
  " rounded-lg bg-transparent p-[5px_7px] text-left hover:bg-surface-strong";
const USER_AVATAR =
  "grid size-6 place-items-center rounded-full border border-border" +
  " bg-[#edf6ff] text-brand";
const USER_IDENTITY = "grid min-w-0 gap-px";
const USER_MENU =
  "absolute inset-x-2 bottom-[52px] z-[4] rounded-md border border-border" +
  " bg-white p-2.5 shadow-float";
const USER_MENU_BUTTON =
  "flex min-h-7 w-full items-center justify-center gap-1.5 rounded-[5px]" +
  " border border-border bg-white text-[10px]";

const WORKSPACE =
  "col-start-2 min-w-0 min-h-screen bg-canvas print:bg-transparent";
const TOPBAR =
  "sticky top-0 z-30 flex min-h-[58px] items-center justify-between px-[26px]" +
  " border-b border-border bg-[rgb(255_255_255_/_96%)] backdrop-blur-[12px]" +
  " mw-760:px-[14px] print:hidden";
const TOPBAR_MENU = ICON_BUTTON;
const TOPBAR_TITLE = "flex items-center gap-2";
const TOPBAR_CRUMB =
  "text-[12px] text-muted after:ml-2 after:text-subtle after:content-['/']" +
  " mw-760:hidden";
const TOPBAR_ACTIONS = "flex items-center gap-2";
const TOPBAR_APPLICANT =
  "inline-flex min-h-[34px] items-center gap-[7px] rounded-lg border" +
  " border-border bg-white px-2.5 text-[11px] mw-760:hidden";
const MAIN = "min-w-0 min-h-[calc(100vh-58px)] print:min-h-0";

export function CompanyShell() {
  const location = useLocation();
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const [userMenuOpen, setUserMenuOpen] = useState(false);
  const pageTitle =
    pageTitles.find((item) => location.pathname.startsWith(item.path))?.title ??
    "기업 콘솔";
  const applicantAppUrl =
    import.meta.env.VITE_APPLICANT_APP_URL ?? "http://localhost:5174/access";
  const sidebarClassName = [
    SIDEBAR,
    sidebarCollapsed ? SIDEBAR_DESKTOP_CLOSED : SIDEBAR_DESKTOP_OPEN,
    mobileMenuOpen ? SIDEBAR_MOBILE_OPEN : SIDEBAR_MOBILE_CLOSED,
  ].join(" ");

  return (
    <div className={sidebarCollapsed ? SHELL_COLLAPSED : SHELL_EXPANDED}>
      <a className={SKIP_LINK} href="#company-main">
        본문으로 이동
      </a>

      <aside
        aria-label="기업 콘솔 주 탐색"
        aria-hidden={sidebarCollapsed || undefined}
        className={sidebarClassName}
      >
        <div className={BRAND_ROW}>
          <NavLink className={BRAND} to="/company">
            <span className={BRAND_MARK} aria-hidden="true">
              IE
            </span>
            <span className={BRAND_TEXT}>
              <strong className={BRAND_NAME}>InterviewEP</strong>
              <small className={BRAND_TAGLINE}>Hiring Operations</small>
            </span>
          </NavLink>
          <button
            className={SIDEBAR_CLOSE}
            type="button"
            aria-label="탐색 닫기"
            onClick={() => {
              setMobileMenuOpen(false);
              setSidebarCollapsed(true);
            }}
          >
            <PanelLeftClose size={18} aria-hidden="true" />
          </button>
        </div>

        <nav className={NAVIGATION} aria-label="업무 메뉴">
          <p className={NAV_LABEL}>채용 운영</p>
          {navigation.map((item) => {
            const Icon = item.icon;
            return (
              <NavLink
                key={item.to}
                aria-label={item.label}
                className={({ isActive }) =>
                  isActive ? NAV_ITEM_ACTIVE : NAV_ITEM
                }
                to={item.to}
                onClick={() => setMobileMenuOpen(false)}
              >
                <Icon size={18} strokeWidth={1.8} aria-hidden="true" />
                <span>{item.label}</span>
              </NavLink>
            );
          })}

          <div className={NAV_DIVIDER} />
          <p className={NAV_LABEL}>지원자 경험</p>
          <a
            className={NAV_ITEM}
            href={applicantAppUrl}
            aria-label="지원자 화면"
          >
            <ExternalLink size={18} strokeWidth={1.8} aria-hidden="true" />
            <span>지원자 화면</span>
          </a>

          <div className={NAV_DIVIDER} />
          <p className={NAV_LABEL}>설정</p>
          {settingsNavigation.map((item) => {
            const Icon = item.icon;
            return (
              <NavLink
                key={item.to}
                aria-label={item.label}
                className={({ isActive }) =>
                  isActive ? NAV_ITEM_ACTIVE : NAV_ITEM
                }
                to={item.to}
                onClick={() => setMobileMenuOpen(false)}
              >
                <Icon size={18} strokeWidth={1.8} aria-hidden="true" />
                <span>{item.label}</span>
              </NavLink>
            );
          })}

          {location.pathname.startsWith("/review") ? (
            <span className={NAV_ITEM_ACTIVE} aria-current="page">
              <Settings2 size={18} strokeWidth={1.8} aria-hidden="true" />
              <span>지원자 검토</span>
            </span>
          ) : null}
        </nav>

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

        <div className={USER}>
          <button
            className={USER_TRIGGER}
            type="button"
            aria-label="사용자 메뉴"
            aria-expanded={userMenuOpen}
            onClick={() => setUserMenuOpen((open) => !open)}
          >
            <span className={USER_AVATAR} aria-hidden="true">
              <UserRound size={15} />
            </span>
            <span className={USER_IDENTITY}>
              <strong className="truncate text-[11px]">채용 담당자</strong>
              <small className="truncate text-[9px] text-muted">
                기업 계정
              </small>
            </span>
            <ChevronDown size={15} aria-hidden="true" />
          </button>
          {userMenuOpen ? (
            <div className={USER_MENU}>
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
          <div className={TOPBAR_ACTIONS}>
            <a href={applicantAppUrl} className={TOPBAR_APPLICANT}>
              지원자 화면
              <ExternalLink size={14} aria-hidden="true" />
            </a>
            <button className={ICON_BUTTON} type="button" aria-label="알림">
              <Bell size={17} aria-hidden="true" />
            </button>
          </div>
        </header>
        <main id="company-main" className={MAIN}>
          <Outlet />
        </main>
      </div>
    </div>
  );
}
