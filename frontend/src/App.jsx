import React, { useEffect, useRef, useState } from 'react';
import Sidebar from './components/Sidebar';
import Header from './components/Header';
import Dashboard from './pages/Dashboard';
import AnalyzeJob from './pages/AnalyzeJob';
import AnalysisResult from './pages/AnalysisResult';
import CompanyIntelligence from './pages/CompanyIntelligence';
import History from './pages/History';
import ModelData from './pages/ModelData';
import About from './pages/About';
import AuthPage from './pages/AuthPage';
import ExtensionPairingDialog from './components/ExtensionPairingDialog';
import GmailAccount from './pages/GmailAccount';
import api from './services/api';

const THEME_KEY = 'careershield_theme';

function getInitialTheme() {
  const storedTheme = localStorage.getItem(THEME_KEY);
  const theme = storedTheme === 'light' || storedTheme === 'dark' ? storedTheme : 'dark';
  document.documentElement.classList.toggle('dark', theme === 'dark');
  return theme;
}

export default function App() {
  const [theme, setTheme] = useState(getInitialTheme);
  const [user, setUser] = useState(null);
  const [authLoading, setAuthLoading] = useState(true);
  const [authError, setAuthError] = useState('');
  const [activePage, setActivePage] = useState(
    () => {
      const requestedPage = new URLSearchParams(window.location.search).get('page');
      return ['analyze', 'gmail'].includes(requestedPage) ? requestedPage : 'dashboard';
    },
  );
  const [currentAnalysis, setCurrentAnalysis] = useState(null);
  const [inspectCompanyTarget, setInspectCompanyTarget] = useState(null);
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const [extensionPairingOpen, setExtensionPairingOpen] = useState(false);
  const mobileMenuButtonRef = useRef(null);
  const mobileMenuWasOpen = useRef(false);
  const deepLinkHandledRef = useRef(false);

  useEffect(() => {
    if (!mobileMenuOpen && mobileMenuWasOpen.current) {
      mobileMenuButtonRef.current?.focus();
    }
    mobileMenuWasOpen.current = mobileMenuOpen;
  }, [mobileMenuOpen]);
  useEffect(() => {
    localStorage.removeItem('careershield_users');
    localStorage.removeItem('careershield_auth_user');

    let mounted = true;
    api.getCurrentUser()
      .then((account) => {
        if (mounted) setUser(account);
      })
      .catch((error) => {
        if (mounted && error.status !== 401) {
          setAuthError('Unable to verify your session. Check the backend connection and retry.');
        }
      })
      .finally(() => {
        if (mounted) setAuthLoading(false);
      });

    const handleUnauthorized = () => {
      setUser(null);
      setCurrentAnalysis(null);
      setActivePage('dashboard');
    };
    window.addEventListener('careershield:unauthorized', handleUnauthorized);
    return () => {
      mounted = false;
      window.removeEventListener('careershield:unauthorized', handleUnauthorized);
    };
  }, []);

  const handleAuthSuccess = (account) => {
    setAuthError('');
    setUser(account);
    setActivePage('dashboard');
  };

  const handleLogout = async () => {
    setAuthError('');
    try {
      await api.logout();
      setUser(null);
      setCurrentAnalysis(null);
      setActivePage('dashboard');
    } catch (error) {
      if (error.status === 401) {
        setUser(null);
        setCurrentAnalysis(null);
      } else {
        setAuthError('Unable to sign out. Check your connection and try again.');
      }
    }
  };

  const handleThemeToggle = () => {
    const nextTheme = theme === 'dark' ? 'light' : 'dark';
    document.documentElement.classList.toggle('dark', nextTheme === 'dark');
    localStorage.setItem(THEME_KEY, nextTheme);
    setTheme(nextTheme);
  };

  const handleAnalysisComplete = (result) => {
    setCurrentAnalysis(result);
    setActivePage('result');
  };

  const handleViewAnalysis = async (id) => {
    try {
      const fullAnalysis = await api.getAnalysis(id);
      setCurrentAnalysis(fullAnalysis);
      setActivePage('result');
    } catch (err) {
      console.error('Failed to view analysis:', err);
    }
  };

  useEffect(() => {
    if (!user || deepLinkHandledRef.current) return;
    const parameters = new URLSearchParams(window.location.search);
    const analysisId = parameters.get('analysisId');
    const requestedPage = parameters.get('page');
    if (analysisId && /^\d+$/.test(analysisId)) {
      deepLinkHandledRef.current = true;
      window.history.replaceState({}, '', window.location.pathname);
      api.getAnalysis(analysisId)
        .then((analysis) => {
          setCurrentAnalysis(analysis);
          setActivePage('result');
        })
        .catch(() => {
          setAuthError('Could not open that analysis. Check that it belongs to your account.');
        });
    } else if (requestedPage === 'analyze') {
      deepLinkHandledRef.current = true;
      window.history.replaceState({}, '', window.location.pathname);
    }
  }, [user]);

  const handleInspectCompany = (compName) => {
    setInspectCompanyTarget(compName);
    setActivePage('company');
  };

  if (authLoading) {
    return <div className="min-h-screen bg-shield-bg text-slate-300 flex items-center justify-center">Checking session...</div>;
  }

  if (!user) {
    return <AuthPage onAuthSuccess={handleAuthSuccess} serverError={authError} />;
  }

  return (
    <div className="flex h-screen bg-shield-bg text-shield-text overflow-hidden font-sans">
      {/* Sidebar: desktop sidebar + mobile drawer */}
      <Sidebar
        activePage={activePage}
        setActivePage={(page) => {
          setActivePage(page);
          setMobileMenuOpen(false);
        }}
        mobileOpen={mobileMenuOpen}
        onClose={() => setMobileMenuOpen(false)}
      />

      {/* Main Content Area */}
      <div className="flex-1 flex flex-col h-screen overflow-hidden min-w-0">
        {/* Top Header */}
        <Header
          activePage={activePage}
          user={user}
          onLogout={handleLogout}
          theme={theme}
          onThemeToggle={handleThemeToggle}
          mobileMenuOpen={mobileMenuOpen}
          mobileMenuButtonRef={mobileMenuButtonRef}
          onOpenMobileMenu={() => setMobileMenuOpen(true)}
          onPairExtension={() => setExtensionPairingOpen(true)}
        />

        {/* Scrollable Viewport */}
        <main className="flex-1 overflow-y-auto p-4 md:p-6 lg:p-8">
          {authError && (
            <div className="mb-4 rounded-lg border border-rose-500/40 bg-rose-950/30 px-4 py-3 text-sm text-rose-300">
              {authError}
            </div>
          )}
          {activePage === 'dashboard' && (
            <Dashboard
              onNavigate={(page) => setActivePage(page)}
              onViewAnalysis={handleViewAnalysis}
            />
          )}

          {activePage === 'analyze' && (
            <AnalyzeJob onAnalysisComplete={handleAnalysisComplete} />
          )}

          {activePage === 'result' && (
            <AnalysisResult
              result={currentAnalysis}
              onBack={() => setActivePage('analyze')}
              onInspectCompany={handleInspectCompany}
              onVerificationUpdate={(externalVerification) => {
                setCurrentAnalysis((previous) => (
                  previous
                    ? { ...previous, external_verification: externalVerification }
                    : previous
                ));
              }}
            />
          )}

          {activePage === 'company' && (
            <CompanyIntelligence initialCompany={inspectCompanyTarget} />
          )}

          {activePage === 'history' && (
            <History onViewAnalysis={handleViewAnalysis} />
          )}

          {activePage === 'models' && (
            <ModelData />
          )}

          {activePage === 'gmail' && (
            <GmailAccount />
          )}

          {activePage === 'about' && (
            <About />
          )}

        </main>
      </div>
      {extensionPairingOpen && (
        <ExtensionPairingDialog onClose={() => setExtensionPairingOpen(false)} />
      )}
    </div>
  );
}
