import { useState, useEffect, createContext, useRef } from 'react';
import Login from './Login';
import { LogOut, Sun, Moon, ChevronDown, Check } from 'lucide-react';
import { logout as apiLogout, setAuthToken, getQuota } from './utils/api';
import StorageBar from './components/StorageBar'
import FileBrowser from './components/FileBrowser';
import { useTranslation } from 'react-i18next';

interface ContextMenuPosition {
  x: number;
  y: number;
}

interface ContextMenuContextType {
  ctxMenuPosition: ContextMenuPosition | null;
  setCtxMenuPosition: (pos: ContextMenuPosition | null) => void;
  handleContextMenuClick: () => void;
}

const ContextMenuContext = createContext<ContextMenuContextType>({
  ctxMenuPosition: null,
  setCtxMenuPosition: () => { },
  handleContextMenuClick: () => { },
});

function App() {
  const { t, i18n } = useTranslation();
  const [ctxMenuPosition, setCtxMenuPosition] = useState<ContextMenuPosition | null>(null);
  const [isLoggedIn, setIsLoggedIn] = useState(!!localStorage.getItem('authToken'));
  const [authError, setAuthError] = useState<string | null>(null);
  const [storage, setStorage] = useState<{ used: number; total: number }>({
    used: 0,
    total: 0,
  });

  const [isDark, setIsDark] = useState(() => {
    const saved = localStorage.getItem('theme');
    return saved ? saved === 'dark' : true;
  });

  const [isLangMenuOpen, setIsLangMenuOpen] = useState(false);
  const langMenuRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (isDark) {
      document.documentElement.classList.add('dark');
      localStorage.setItem('theme', 'dark');
    } else {
      document.documentElement.classList.remove('dark');
      localStorage.setItem('theme', 'light');
    }
  }, [isDark]);

  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (langMenuRef.current && !langMenuRef.current.contains(e.target as Node)) {
        setIsLangMenuOpen(false);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  const handleLogout = async () => {
    try {
      await apiLogout();
    } catch (e) {
      console.error('Logout failed', e);
    } finally {
      setIsLoggedIn(false);
      setAuthError(null);
    }
  };

  const handleAuthError = (code?: string) => {
    let msg = t('app.logged_out_msg');
    if (code === 'E_AUTH_INVALID') {
      msg = t('app.invalid_auth');
    } else if (code === 'E_AUTH_EXPIRED' || code === 'E_AUTH_REVOKED') {
      msg = t('app.logged_out_msg');
    }
    setAuthError(msg);
    setIsLoggedIn(false);
    setAuthToken('');
  };

  useEffect(() => {
    if (!isLoggedIn) return;

    let isMounted = true;

    const fetchStorage = async () => {
      try {
        const data = await getQuota();
        if (isMounted) setStorage({ used: data.used, total: data.quota });
      }
      catch (err) {
        console.error("Failed to fetch storage:", err);
      }
    };

    fetchStorage(); // initial fetch

    const interval = setInterval(fetchStorage, 5000); // every 5 seconds
    return () => {
      isMounted = false;
      clearInterval(interval);
    };
  }, [isLoggedIn]);

  if (!isLoggedIn) {
    return <Login
      initialError={authError}
      onLoginSuccess={() => {
        setIsLoggedIn(true);
        setAuthError(null);
      }}
    />;
  }

  const handleContextMenuClick = () => setCtxMenuPosition(null); // hide menu

  return (
    <ContextMenuContext.Provider value={{ ctxMenuPosition, setCtxMenuPosition, handleContextMenuClick }}>
      <div className="min-h-[100dvh] bg-gray-50 dark:bg-zinc-950 text-gray-900 dark:text-gray-100 flex flex-col transition-colors duration-300" onClick={handleContextMenuClick}>
        <header className="bg-white dark:bg-zinc-900 shadow-sm ring-1 ring-gray-900/5 dark:ring-white/10 py-4 px-6 md:px-8 flex items-center justify-between">
          <div className="flex-1">
            <h1 className="text-xl font-bold text-transparent bg-clip-text bg-gradient-to-r from-indigo-500 to-purple-600 inline-block">
              {t('app.title')}
            </h1>
          </div>

          <div className="flex-1 flex justify-center items-center hidden md:flex">
            {((storage.used == 0) && (storage.total == 0)) || <StorageBar used={storage.used} total={storage.total} />}
          </div>

          <div className="flex-1 flex items-center justify-end gap-4">
            {/* Add a compact storage bar for mobile devices */}
            <div className="md:hidden">
              {((storage.used == 0) && (storage.total == 0)) || <StorageBar used={storage.used} total={storage.total} />}
            </div>

            <div className="relative" ref={langMenuRef}>
              <button
                onClick={() => setIsLangMenuOpen(!isLangMenuOpen)}
                className="flex items-center gap-2 px-3 py-2 text-sm font-medium bg-gray-100 dark:bg-zinc-800 border border-transparent rounded-lg focus:ring-2 focus:ring-indigo-500 focus:outline-none text-gray-700 dark:text-gray-200 cursor-pointer hover:bg-gray-200 dark:hover:bg-zinc-700 transition-colors"
              >
                <span>{i18n.language.startsWith('it') ? '🇮🇹 Italiano' : '🇬🇧 English'}</span>
                <ChevronDown className={`w-4 h-4 transition-transform ${isLangMenuOpen ? 'rotate-180' : ''}`} />
              </button>

              {isLangMenuOpen && (
                <div className="absolute right-0 mt-2 w-40 bg-white dark:bg-zinc-800 rounded-lg shadow-lg border border-gray-100 dark:border-zinc-700 overflow-hidden z-50">
                  <div className="py-1">
                    <button
                      onClick={() => {
                        i18n.changeLanguage('en');
                        localStorage.setItem('appLanguage', 'en');
                        setIsLangMenuOpen(false);
                      }}
                      className="w-full flex items-center justify-between px-4 py-2 text-sm text-gray-700 dark:text-gray-200 hover:bg-gray-50 dark:hover:bg-zinc-700/50 transition-colors"
                    >
                      <span className="flex items-center gap-2">🇬🇧 English</span>
                      {i18n.language.startsWith('en') && <Check className="w-4 h-4 text-indigo-500" />}
                    </button>
                    <button
                      onClick={() => {
                        i18n.changeLanguage('it');
                        localStorage.setItem('appLanguage', 'it');
                        setIsLangMenuOpen(false);
                      }}
                      className="w-full flex items-center justify-between px-4 py-2 text-sm text-gray-700 dark:text-gray-200 hover:bg-gray-50 dark:hover:bg-zinc-700/50 transition-colors"
                    >
                      <span className="flex items-center gap-2">🇮🇹 Italiano</span>
                      {i18n.language.startsWith('it') && <Check className="w-4 h-4 text-indigo-500" />}
                    </button>
                  </div>
                </div>
              )}
            </div>

            <button
              onClick={() => setIsDark(!isDark)}
              className="p-2 text-gray-700 bg-gray-100 dark:text-gray-200 dark:bg-zinc-800 rounded-lg hover:bg-gray-200 dark:hover:bg-zinc-700 transition-colors focus:outline-none focus:ring-2 focus:ring-indigo-500"
              aria-label="Toggle Dark Mode"
            >
              {isDark ? <Sun className="w-4 h-4" /> : <Moon className="w-4 h-4" />}
            </button>

            <button
              onClick={handleLogout}
              className="flex items-center gap-2 px-4 py-2 text-sm font-medium text-gray-700 bg-gray-100 dark:text-gray-200 dark:bg-zinc-800 rounded-lg hover:bg-gray-200 dark:hover:bg-zinc-700 transition-colors"
            >
              <LogOut className="w-4 h-4" />
              <span className="hidden sm:inline">{t('app.logout')}</span>
            </button>
          </div>
        </header>

        <main className="flex-1 max-w-7xl w-full mx-auto p-4 md:p-8">
          <FileBrowser onAuthError={handleAuthError} />
        </main>
      </div>
    </ContextMenuContext.Provider>
  );
}

export default App;
export { ContextMenuContext };