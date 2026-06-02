'use client';

import { Tab } from '@/app/page';

interface Props {
  active: Tab;
  onChange: (tab: Tab) => void;
}

const tabs: { id: Tab; label: string; icon: string }[] = [
  { id: 'home', label: 'خانه', icon: '🏠' },
  { id: 'earn', label: 'کسب توکن', icon: '💰' },
  { id: 'shop', label: 'فروشگاه', icon: '🛒' },
  { id: 'profile', label: 'پروفایل', icon: '👤' },
];

export default function BottomNav({ active, onChange }: Props) {
  return (
    <nav className="fixed bottom-0 inset-x-0 z-50 border-t border-gray-200 dark:border-gray-800 backdrop-blur-lg"
      style={{ backgroundColor: 'var(--tg-theme-bg-color)' }}>
      <div className="max-w-lg mx-auto flex justify-around py-2">
        {tabs.map((t) => (
          <button
            key={t.id}
            onClick={() => onChange(t.id)}
            className={`flex flex-col items-center gap-0.5 px-3 py-1 rounded-xl transition-all ${
              active === t.id ? 'opacity-100 scale-105' : 'opacity-50'
            }`}
          >
            <span className="text-xl">{t.icon}</span>
            <span className="text-xs font-medium">{t.label}</span>
          </button>
        ))}
      </div>
    </nav>
  );
}
