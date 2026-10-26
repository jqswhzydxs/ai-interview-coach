import { useEffect, useRef, useState, type ReactNode } from "react";
import { History, Home, Menu, PlusCircle, X } from "lucide-react";
import { NavLink, useLocation } from "react-router-dom";

const navigation = [
  { to: "/", label: "首页", icon: Home },
  { to: "/prep/new", label: "创建准备任务", icon: PlusCircle },
  { to: "/history", label: "练习历史", icon: History },
];

export function AppShell({ children }: { children: ReactNode }) {
  const [mobileOpen, setMobileOpen] = useState(false);
  const triggerRef = useRef<HTMLButtonElement>(null);
  const location = useLocation();

  useEffect(() => {
    document.getElementById("main-content")?.focus();
  }, [location.pathname]);

  const closeNavigation = () => {
    setMobileOpen(false);
    window.requestAnimationFrame(() => triggerRef.current?.focus());
  };

  useEffect(() => {
    if (!mobileOpen) return undefined;
    const closeOnEscape = (event: globalThis.KeyboardEvent) => {
      if (event.key === "Escape") closeNavigation();
    };
    window.addEventListener("keydown", closeOnEscape);
    return () => window.removeEventListener("keydown", closeOnEscape);
  }, [mobileOpen]);

  return (
    <div className="app-shell">
      <a className="skip-link" href="#main-content">
        跳到主内容
      </a>
      <header className="app-header">
        <NavLink className="brand" to="/" aria-label="AI 面试准备助手首页">
          <span className="brand-mark" aria-hidden="true">AI</span>
          <span>面试准备助手</span>
        </NavLink>
        <button
          ref={triggerRef}
          className="icon-button mobile-menu-button"
          type="button"
          aria-label={mobileOpen ? "关闭导航" : "打开导航"}
          aria-expanded={mobileOpen}
          aria-controls="primary-navigation"
          onClick={() => setMobileOpen((current) => !current)}
        >
          {mobileOpen ? <X aria-hidden="true" /> : <Menu aria-hidden="true" />}
        </button>
      </header>
      <div className="app-layout">
        <nav
          id="primary-navigation"
          className={`primary-navigation ${mobileOpen ? "is-open" : ""}`}
          aria-label="主要导航"
        >
          {navigation.map(({ to, label, icon: Icon }) => (
            <NavLink
              key={to}
              to={to}
              end={to === "/"}
              onClick={() => setMobileOpen(false)}
              className={({ isActive }) => `nav-link ${isActive ? "is-active" : ""}`}
            >
              <Icon aria-hidden="true" size={20} />
              <span>{label}</span>
            </NavLink>
          ))}
        </nav>
        <main id="main-content" className="main-content" tabIndex={-1}>
          {children}
        </main>
      </div>
    </div>
  );
}
