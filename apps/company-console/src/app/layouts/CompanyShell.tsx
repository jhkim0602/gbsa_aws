import {
  Bell,
  BriefcaseBusiness,
  ChevronDown,
  ExternalLink,
  FilePlus2,
  LayoutDashboard,
  Menu,
  PanelLeftClose,
  Settings2,
  UserRound,
  Users,
  X,
} from "lucide-react";
import { useState } from "react";
import { NavLink, Outlet, useLocation } from "react-router-dom";

const navigation = [
  { label: "대시보드", to: "/company", icon: LayoutDashboard },
  { label: "채용 포지션", to: "/positions", icon: BriefcaseBusiness },
  { label: "지원자 관리", to: "/applicants", icon: Users },
  { label: "채용 관리", to: "/hiring", icon: FilePlus2 },
] as const;

const pageTitles = [
  { path: "/company", title: "대시보드" },
  { path: "/positions/", title: "포지션 운영" },
  { path: "/positions", title: "채용 포지션" },
  { path: "/applicants", title: "지원자 관리" },
  { path: "/hiring", title: "채용 관리" },
  { path: "/review", title: "지원자 검토" },
] as const;

export function CompanyShell() {
  const location = useLocation();
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const [userMenuOpen, setUserMenuOpen] = useState(false);
  const pageTitle =
    pageTitles.find((item) => location.pathname.startsWith(item.path))?.title ??
    "기업 콘솔";
  const applicantAppUrl =
    import.meta.env.VITE_APPLICANT_APP_URL ?? "http://localhost:5174/access";

  return (
    <div className="company-shell">
      <a className="skip-link" href="#company-main">
        본문으로 이동
      </a>

      <aside
        className={`company-sidebar ${mobileMenuOpen ? "is-open" : ""}`}
        aria-label="기업 콘솔 주 탐색"
      >
        <div className="company-brand-row">
          <NavLink className="company-brand" to="/company">
            <span className="company-brand__mark" aria-hidden="true">
              IE
            </span>
            <span>
              <strong>InterviewEP</strong>
              <small>Hiring Operations</small>
            </span>
          </NavLink>
          <button
            className="icon-button company-sidebar__close"
            type="button"
            aria-label="탐색 닫기"
            onClick={() => setMobileMenuOpen(false)}
          >
            <PanelLeftClose size={18} aria-hidden="true" />
          </button>
        </div>

        <nav className="company-navigation" aria-label="업무 메뉴">
          <p className="company-navigation__label">채용 운영</p>
          {navigation.map((item) => {
            const Icon = item.icon;
            return (
              <NavLink
                key={item.to}
                aria-label={item.label}
                className={({ isActive }) =>
                  `company-navigation__item ${isActive ? "is-active" : ""}`
                }
                to={item.to}
                onClick={() => setMobileMenuOpen(false)}
              >
                <Icon size={18} strokeWidth={1.8} aria-hidden="true" />
                <span>{item.label}</span>
              </NavLink>
            );
          })}

          <div className="company-navigation__divider" />
          <p className="company-navigation__label">지원자 경험</p>
          <a
            className="company-navigation__item"
            href={applicantAppUrl}
            aria-label="지원자 화면"
          >
            <ExternalLink size={18} strokeWidth={1.8} aria-hidden="true" />
            <span>지원자 화면</span>
          </a>

          {location.pathname.startsWith("/review") ? (
            <span
              className="company-navigation__item is-active"
              aria-current="page"
            >
              <Settings2 size={18} strokeWidth={1.8} aria-hidden="true" />
              <span>지원자 검토</span>
            </span>
          ) : null}
        </nav>

        <div className="company-sidebar__support">
          <span aria-hidden="true">?</span>
          <div>
            <strong>채용 운영 도움말</strong>
            <small>설정 흐름을 확인하세요</small>
          </div>
        </div>

        <div className="company-user">
          <button
            className="company-user__trigger"
            type="button"
            aria-label="사용자 메뉴"
            aria-expanded={userMenuOpen}
            onClick={() => setUserMenuOpen((open) => !open)}
          >
            <span className="company-user__avatar" aria-hidden="true">
              <UserRound size={15} />
            </span>
            <span className="company-user__identity">
              <strong>채용 담당자</strong>
              <small>기업 계정</small>
            </span>
            <ChevronDown size={15} aria-hidden="true" />
          </button>
          {userMenuOpen ? (
            <div className="company-user__menu">
              <p>
                <strong>기업 계정</strong>
                <span>인증된 워크스페이스</span>
              </p>
              <button type="button" onClick={() => setUserMenuOpen(false)}>
                <X size={14} aria-hidden="true" />
                닫기
              </button>
            </div>
          ) : null}
        </div>
      </aside>

      {mobileMenuOpen ? (
        <button
          className="company-sidebar__scrim"
          type="button"
          aria-label="탐색 닫기"
          onClick={() => setMobileMenuOpen(false)}
        />
      ) : null}

      <div className="company-shell__workspace">
        <header className="company-topbar">
          <button
            className="icon-button company-topbar__menu"
            type="button"
            aria-label="탐색 열기"
            onClick={() => setMobileMenuOpen(true)}
          >
            <Menu size={19} aria-hidden="true" />
          </button>
          <div className="company-topbar__title">
            <span>채용 운영</span>
            <strong>{pageTitle}</strong>
          </div>
          <div className="company-topbar__actions">
            <a href={applicantAppUrl} className="company-topbar__applicant">
              지원자 화면
              <ExternalLink size={14} aria-hidden="true" />
            </a>
            <button className="icon-button" type="button" aria-label="알림">
              <Bell size={17} aria-hidden="true" />
            </button>
          </div>
        </header>
        <main id="company-main" className="company-main">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
