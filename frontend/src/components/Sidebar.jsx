import React, { useEffect, useRef } from 'react';
import { 
  LayoutDashboard, 
  FileSearch, 
  Building, 
  History as HistoryIcon, 
  Shield,
  Cpu,
  BookOpen,
  Mail,
  X
} from 'lucide-react';

export default function Sidebar({ activePage, setActivePage, mobileOpen = false, onClose = () => {} }) {
  const closeButtonRef = useRef(null);

  const navItems = [
    { id: 'dashboard', label: 'Dashboard', icon: LayoutDashboard },
    { id: 'analyze', label: 'Analyze Job', icon: FileSearch },
    { id: 'company', label: 'Company Intelligence', icon: Building },
    { id: 'history', label: 'History', icon: HistoryIcon },
    { id: 'models', label: 'Model Transparency', icon: Cpu },
    { id: 'gmail', label: 'Gmail Connection', icon: Mail },
    { id: 'about', label: 'About & Whitepaper', icon: BookOpen },
  ];

  // Close drawer on Escape key press
  useEffect(() => {
    if (!mobileOpen) return;
    const handleKeyDown = (e) => {
      if (e.key === 'Escape') {
        onClose();
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [mobileOpen, onClose]);

  // Focus close button when drawer opens for keyboard accessibility
  useEffect(() => {
    if (mobileOpen && closeButtonRef.current) {
      closeButtonRef.current.focus();
    }
  }, [mobileOpen]);

  const handleNavClick = (pageId) => {
    setActivePage(pageId);
    if (onClose) {
      onClose();
    }
  };

  return (
    <>
      {/* Desktop Sidebar (hidden on mobile < 768px) */}
      <aside className="w-64 bg-shield-surface border-r border-shield-border hidden md:flex flex-col justify-between h-screen sticky top-0 shrink-0 select-none">
        <div>
          {/* Logo / Brand */}
          <div className="p-5 border-b border-shield-border">
            <div className="flex items-center gap-3">
              <div className="relative flex items-center justify-center w-10 h-10 rounded-lg bg-gradient-to-br from-cyan-500/20 to-blue-600/20 border border-cyan-500/40 text-cyan-400">
                <Shield className="w-5 h-5 text-cyan-400" />
              </div>
              <div>
                <div className="text-base font-bold tracking-tight text-slate-100 flex items-center gap-1.5">
                  <span>CareerShield</span>
                </div>
                <p className="text-[10px] text-slate-400 font-medium tracking-tight">Trust & Fraud Intelligence</p>
              </div>
            </div>
          </div>

          {/* Navigation */}
          <nav className="p-3 space-y-1">
            {navItems.map((item) => {
              const Icon = item.icon;
              const isActive = activePage === item.id;
              return (
                <button
                  key={item.id}
                  onClick={() => setActivePage(item.id)}
                  className={`w-full flex items-center gap-3 px-3.5 py-2.5 rounded-md text-xs font-medium transition-all text-left focus:outline-none focus-visible:ring-2 focus-visible:ring-cyan-500 ${
                    isActive
                      ? 'bg-cyan-950/50 text-cyan-400 border border-cyan-500/30 shadow-sm'
                      : 'text-slate-400 hover:text-slate-200 hover:bg-shield-card/60'
                  }`}
                >
                  <Icon className={`w-4 h-4 ${isActive ? 'text-cyan-400' : 'text-slate-400'}`} />
                  <span>{item.label}</span>
                </button>
              );
            })}
          </nav>
        </div>
      </aside>

      {/* Mobile Drawer (visible only on < 768px when opened) */}
      {mobileOpen && (
        <div className="fixed inset-0 z-50 md:hidden">
          {/* Backdrop overlay */}
          <div
            className="fixed inset-0 bg-slate-950/75 backdrop-blur-sm transition-opacity"
            onClick={onClose}
            aria-hidden="true"
          />

          {/* Mobile Navigation Drawer Panel */}
          <div
            id="mobile-navigation-drawer"
            role="dialog"
            aria-modal="true"
            aria-label="Navigation menu"
            className="relative z-50 w-72 max-w-[85vw] bg-shield-surface border-r border-shield-border flex flex-col justify-between h-full shadow-2xl"
          >
            <div>
              {/* Header with Brand & Close Button */}
              <div className="p-4 border-b border-shield-border flex items-center justify-between">
                <div className="flex items-center gap-2.5">
                  <div className="relative flex items-center justify-center w-9 h-9 rounded-lg bg-gradient-to-br from-cyan-500/20 to-blue-600/20 border border-cyan-500/40 text-cyan-400">
                    <Shield className="w-4 h-4 text-cyan-400" />
                  </div>
                  <div>
                    <div className="text-sm font-bold tracking-tight text-slate-100">
                      CareerShield
                    </div>
                    <p className="text-[10px] text-slate-400 font-medium tracking-tight">Trust & Fraud Intelligence</p>
                  </div>
                </div>

                <button
                  ref={closeButtonRef}
                  type="button"
                  onClick={onClose}
                  aria-label="Close navigation menu"
                  className="p-1.5 rounded-md text-slate-400 hover:text-slate-100 hover:bg-shield-card border border-shield-border transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-cyan-500"
                >
                  <X className="w-4 h-4" />
                </button>
              </div>

              {/* Navigation Items */}
              <nav className="p-3 space-y-1">
                {navItems.map((item) => {
                  const Icon = item.icon;
                  const isActive = activePage === item.id;
                  return (
                    <button
                      key={item.id}
                      onClick={() => handleNavClick(item.id)}
                      className={`w-full flex items-center gap-3 px-3.5 py-2.5 rounded-md text-xs font-medium transition-all text-left focus:outline-none focus-visible:ring-2 focus-visible:ring-cyan-500 ${
                        isActive
                          ? 'bg-cyan-950/50 text-cyan-400 border border-cyan-500/30 shadow-sm'
                          : 'text-slate-400 hover:text-slate-200 hover:bg-shield-card/60'
                      }`}
                    >
                      <Icon className={`w-4 h-4 ${isActive ? 'text-cyan-400' : 'text-slate-400'}`} />
                      <span>{item.label}</span>
                    </button>
                  );
                })}
              </nav>
            </div>
          </div>
        </div>
      )}
    </>
  );
}
