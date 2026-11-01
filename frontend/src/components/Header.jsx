
import React, { useEffect, useRef } from 'react';
import { LogOut, Moon, Sun, Menu, Puzzle } from 'lucide-react';

const PAGE_TITLES = {
  dashboard: 'Dashboard',
  analyze: 'Analyze a Job',
  result: 'Analysis Report',
  company: 'Company Intelligence',
  history: 'Your Analysis History',
  models: 'Model Transparency',
  about: 'About & Whitepaper',
};

export default function Header({
  activePage,
  systemStatus = {},
  user,
  onLogout,
  theme,
  onThemeToggle,
  mobileMenuOpen = false,
  mobileMenuButtonRef,
  onOpenMobileMenu = () => {},
  onPairExtension = () => {},
}) {
  const title = PAGE_TITLES[activePage] || 'CareerShield';
  const wasMobileMenuOpenRef = useRef(false);

  // Restore keyboard focus to the hamburger button when the mobile
  // navigation drawer closes.
  useEffect(() => {
    if (wasMobileMenuOpenRef.current && !mobileMenuOpen) {
      if (window.matchMedia('(max-width: 767px)').matches) {
        mobileMenuButtonRef?.current?.focus();
      }
    }

    wasMobileMenuOpenRef.current = mobileMenuOpen;
  }, [mobileMenuOpen, mobileMenuButtonRef]);

  return (
    <header className="h-16 border-b border-shield-border bg-shield-surface/80 backdrop-blur px-4 md:px-6 flex items-center justify-between sticky top-0 z-20">
      <div className="flex items-center gap-2.5 sm:gap-3 min-w-0">
        {/* Mobile navigation menu button */}
        <button
          ref={mobileMenuButtonRef}
          type="button"
          onClick={onOpenMobileMenu}
          aria-label="Open navigation menu"
          aria-expanded={mobileMenuOpen}
          aria-controls="mobile-navigation-drawer"
          className="md:hidden p-1.5 -ml-1 text-slate-400 hover:text-slate-100 hover:bg-shield-card rounded-md border border-shield-border transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-cyan-500 shrink-0"
        >
          <Menu className="w-5 h-5 text-slate-300" />
        </button>

        <h1 className="text-sm sm:text-base font-bold text-slate-100 flex items-center gap-2 truncate">
          <span className="truncate">{title}</span>
        </h1>
      </div>

      <div className="flex items-center gap-2 md:gap-4 shrink-0">
        <button
          type="button"
          onClick={onPairExtension}
          className="inline-flex items-center gap-1.5 rounded-md border border-shield-border bg-shield-card px-2.5 py-1.5 text-xs font-medium text-cyan-300 transition hover:border-cyan-500/50 focus:outline-none focus-visible:ring-2 focus-visible:ring-cyan-500"
        >
          <Puzzle className="h-3.5 w-3.5" />
          <span className="hidden sm:inline">Connect extension</span>
        </button>

        {/* Theme toggle */}
        <button
          type="button"
          onClick={onThemeToggle}
          aria-label={`Switch to ${theme === 'dark' ? 'light' : 'dark'} theme`}
          aria-pressed={theme === 'dark'}
          className="inline-flex items-center gap-1.5 md:gap-2 rounded-md border border-shield-border bg-shield-card px-2.5 md:px-3 py-1.5 md:py-2 text-xs font-medium text-shield-text transition hover:border-cyan-500/40 hover:text-cyan-500 focus:outline-none focus-visible:ring-2 focus-visible:ring-cyan-500"
        >
          {theme === 'dark' ? (
            <Sun className="h-4 w-4" />
          ) : (
            <Moon className="h-4 w-4" />
          )}

          <span className="hidden sm:inline">
            {theme === 'dark' ? 'Light mode' : 'Dark mode'}
          </span>
        </button>

        {/* User information and sign out */}
        <div className="flex items-center gap-2 md:gap-3 rounded-md border border-shield-border bg-shield-card px-2 md:px-3 py-1.5 text-xs text-slate-200">
          <div className="flex items-center gap-2">
            <div className="flex h-7 w-7 items-center justify-center rounded-full bg-cyan-500/15 text-cyan-300 font-semibold text-xs shrink-0">
              {user?.name?.charAt(0)?.toUpperCase() || 'U'}
            </div>

            <div className="hidden md:block">
              <div className="font-medium text-slate-100">
                {user?.name || 'User'}
              </div>

              <div className="text-[10px] text-slate-400">
                {user?.email || 'Signed in'}
              </div>
            </div>
          </div>

          <button
            type="button"
            onClick={onLogout}
            className="ml-0.5 sm:ml-1 inline-flex items-center gap-1 rounded-md border border-slate-700 bg-slate-900 px-2 py-1 text-[11px] text-slate-200 transition hover:border-cyan-500/40 hover:text-cyan-300 focus:outline-none focus-visible:ring-2 focus-visible:ring-cyan-500"
          >
            <LogOut className="w-3 h-3" />
            <span className="hidden sm:inline">Sign out</span>
          </button>
        </div>
      </div>
    </header>
  );
}
