'use client';

import { useEffect, useState } from 'react';
import { apiFetch, formatTokens } from '@/lib/api';
import { useTelegram } from '@/lib/telegram';
import { Tab } from '@/app/page';

interface Profile {
  token_balance: number;
  total_earned: number;
  total_spent: number;
  referral_count: number;
  rank: number;
  first_name: string;
}

export default function HomePage({ onNavigate }: { onNavigate: (tab: Tab) => void }) {
  const { initData, isReady } = useTelegram();
  const [profile, setProfile] = useState<Profile | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!isReady) return;
    apiFetch<Profile>('/user/profile', initData)
      .then(setProfile)
      .catch(console.error)
      .finally(() => setLoading(false));
  }, [isReady, initData]);

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-[60vh]">
        <div className="animate-pulse text-lg opacity-60">در حال بارگذاری...</div>
      </div>
    );
  }

  return (
    <div className="p-4 space-y-4">
      <div className="text-center pt-4">
        <h1 className="text-2xl font-bold">سلام {profile?.first_name || 'دوست'} 👋</h1>
        <p className="text-sm opacity-60 mt-1">به داشبورد خوش اومدی</p>
      </div>

      <div className="card text-center py-6">
        <p className="text-sm opacity-60">موجودی توکن</p>
        <p className="text-4xl font-bold mt-1 text-blue-500">
          {formatTokens(profile?.token_balance || 0)}
        </p>
        <p className="text-xs opacity-50 mt-1">توکن</p>
      </div>

      <div className="grid grid-cols-2 gap-3">
        <StatCard label="کل درآمد" value={formatTokens(profile?.total_earned || 0)} icon="📈" />
        <StatCard label="کل خرج" value={formatTokens(profile?.total_spent || 0)} icon="📉" />
        <StatCard label="دعوت‌ها" value={formatTokens(profile?.referral_count || 0)} icon="👥" />
        <StatCard label="رتبه" value={`#${formatTokens(profile?.rank || 0)}`} icon="🏅" />
      </div>

      <div className="grid grid-cols-2 gap-3 pt-2">
        <button className="btn-primary" onClick={() => onNavigate('earn')}>
          💰 کسب توکن
        </button>
        <button className="btn-secondary" onClick={() => onNavigate('shop')}>
          🛒 خرید کانفیگ
        </button>
      </div>
    </div>
  );
}

function StatCard({ label, value, icon }: { label: string; value: string; icon: string }) {
  return (
    <div className="card text-center py-3">
      <span className="text-lg">{icon}</span>
      <p className="text-lg font-bold mt-1">{value}</p>
      <p className="text-xs opacity-60">{label}</p>
    </div>
  );
}
