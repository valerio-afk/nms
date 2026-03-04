import { useState } from 'react';
import Login from './Login';
import { LogOut } from 'lucide-react';
import { logout as apiLogout } from './api';

function App() {
  const [isLoggedIn, setIsLoggedIn] = useState(!!localStorage.getItem('authToken'));
  const [username, setUsername] = useState('');

  const handleLogout = async () => {
    try {
      await apiLogout();
    } catch (e) {
      console.error('Logout failed', e);
    } finally {
      setIsLoggedIn(false);
      setUsername('');
    }
  };

  if (!isLoggedIn) {
    return <Login onLoginSuccess={(user) => {
      setIsLoggedIn(true);
      setUsername(user);
    }} />;
  }

  return (
    <div className="min-h-[100dvh] bg-gray-50 dark:bg-zinc-950 text-gray-900 dark:text-gray-100 flex flex-col transition-colors duration-300">
      <header className="bg-white dark:bg-zinc-900 shadow-sm ring-1 ring-gray-900/5 dark:ring-white/10 py-4 px-6 md:px-8 flex items-center justify-between">
        <h1 className="text-xl font-bold text-transparent bg-clip-text bg-gradient-to-r from-indigo-500 to-purple-600">
          NMS Dashboard
        </h1>
        <button
          onClick={handleLogout}
          className="flex items-center gap-2 px-4 py-2 text-sm font-medium text-gray-700 bg-gray-100 dark:text-gray-200 dark:bg-zinc-800 rounded-lg hover:bg-gray-200 dark:hover:bg-zinc-700 transition-colors"
        >
          <LogOut className="w-4 h-4" />
          Logout
        </button>
      </header>

      <main className="flex-1 max-w-7xl w-full mx-auto p-6 md:p-8">
        <div className="bg-white dark:bg-zinc-900 rounded-2xl shadow-sm ring-1 ring-gray-900/5 dark:ring-white/10 p-8 min-h-[500px] flex items-center justify-center">
          <div className="text-center space-y-4">
            <div className="inline-flex items-center justify-center w-20 h-20 rounded-full bg-green-100 dark:bg-green-900/30 mb-4">
              <span className="text-4xl">🎉</span>
            </div>
            <h2 className="text-3xl font-bold">Welcome Back{username ? `, ${username}` : ''}!</h2>
            <p className="text-gray-500 dark:text-gray-400 max-w-sm mx-auto">
              You have successfully authenticated via OTP. The dashboard is now accessible.
            </p>
          </div>
        </div>
      </main>
    </div>
  );
}

export default App;
