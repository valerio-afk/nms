import { useState, useEffect, createContext } from 'react';
import Login from './Login';
import { LogOut } from 'lucide-react';
import { logout as apiLogout, setAuthToken, getQuota } from './utils/api';
import StorageBar from './components/StorageBar'
import FileBrowser from './FileBrowser';

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
  const [ctxMenuPosition, setCtxMenuPosition] = useState<ContextMenuPosition | null>(null);
  const [isLoggedIn, setIsLoggedIn] = useState(!!localStorage.getItem('authToken'));
  const [authError, setAuthError] = useState<string | null>(null);
  const [storage, setStorage] = useState<{ used: number; total: number }>({
    used: 0,
    total: 0,
  });

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
    let msg = "You've been logged out";
    if (code === 'E_AUTH_INVALID') {
      msg = "Invalid authentication";
    } else if (code === 'E_AUTH_EXPIRED' || code === 'E_AUTH_REVOKED') {
      msg = "You've been logged out";
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
          <h1 className="text-xl font-bold text-transparent bg-clip-text bg-gradient-to-r from-indigo-500 to-purple-600">
            NMS Box
          </h1>

          {((storage.used == 0) && (storage.total == 0)) || <StorageBar used={storage.used} total={storage.total} />}

          <button
            onClick={handleLogout}
            className="flex items-center gap-2 px-4 py-2 text-sm font-medium text-gray-700 bg-gray-100 dark:text-gray-200 dark:bg-zinc-800 rounded-lg hover:bg-gray-200 dark:hover:bg-zinc-700 transition-colors"
          >
            <LogOut className="w-4 h-4" />
            Logout
          </button>
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