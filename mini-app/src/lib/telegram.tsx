'use client';

import { createContext, useContext, useEffect, useState, ReactNode } from 'react';

interface TelegramContextType {
  initData: string;
  user: { id: number; first_name?: string; username?: string } | null;
  isReady: boolean;
  isDark: boolean;
}

const TelegramContext = createContext<TelegramContextType>({
  initData: '',
  user: null,
  isReady: false,
  isDark: false,
});

export function TelegramProvider({ children }: { children: ReactNode }) {
  const [initData, setInitData] = useState('');
  const [user, setUser] = useState<TelegramContextType['user']>(null);
  const [isReady, setIsReady] = useState(false);
  const [isDark, setIsDark] = useState(false);

  useEffect(() => {
    const tg = (window as any).Telegram?.WebApp;
    if (tg) {
      tg.ready();
      tg.expand();
      setInitData(tg.initData || '');
      setUser(tg.initDataUnsafe?.user || null);
      setIsDark(tg.colorScheme === 'dark');
      if (tg.colorScheme === 'dark') {
        document.documentElement.classList.add('dark');
      }
      tg.setHeaderColor(tg.themeParams.bg_color || '#ffffff');
      tg.setBackgroundColor(tg.themeParams.bg_color || '#ffffff');
    } else {
      setInitData('dev_mode');
      setUser({ id: 123456789, first_name: 'تست' });
    }
    setIsReady(true);
  }, []);

  return (
    <TelegramContext.Provider value={{ initData, user, isReady, isDark }}>
      {children}
    </TelegramContext.Provider>
  );
}

export function useTelegram() {
  return useContext(TelegramContext);
}
