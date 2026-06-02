'use client';

import { useEffect, useState } from 'react';
import { apiFetch, formatTokens } from '@/lib/api';
import { useTelegram } from '@/lib/telegram';

interface Profile {
  id: number;
  username: string;
  first_name: string;
  token_balance: number;
  total_earned: number;
  total_spent: number;
  referral_count: number;
  rank: number;
  join_date: string;
}

interface Transaction {
  amount: number;
  action_type: string;
  reason: string;
  created_at: string;
}

interface Purchase {
  product_name: string;
  token_cost: number;
  created_at: string;
}

export default function ProfilePage() {
  const { initData, isReady } = useTelegram();
  const [profile, setProfile] = useState<Profile | null>(null);
  const [transactions, setTransactions] = useState<Transaction[]>([]);
  const [purchases, setPurchases] = useState<Purchase[]>([]);
  const [tab, setTab] = useState<'info' | 'earn' | 'buy'>('info');

  useEffect(() => {
    if (!isReady) return;
    Promise.all([
      apiFetch<Profile>('/user/profile', initData),
      apiFetch<Transaction[]>('/user/transactions', initData),
      apiFetch<Purchase[]>('/user/purchases', initData),
    ]).then(([p, t, pu]) => {
      setProfile(p);
      setTransactions(t);
      setPurchases(pu);
    }).catch(console.error);
  }, [isReady, initData]);

  return (
    <div className="p-4 space-y-4">
      <h2 className="text-xl font-bold">👤 پروفایل</h2>

      {profile && (
        <div className="card space-y-2">
          <Row label="نام" value={profile.first_name || '—'} />
          <Row label="آیدی" value={formatTokens(profile.id)} />
          <Row label="یوزرنیم" value={profile.username ? `@${profile.username}` : '—'} />
          <Row label="موجودی" value={`${formatTokens(profile.token_balance)} توکن`} />
          <Row label="عضویت" value={profile.join_date} />
          <Row label="رتبه" value={`#${formatTokens(profile.rank)}`} />
        </div>
      )}

      <div className="flex gap-2">
        {(['info', 'earn', 'buy'] as const).map((t) => (
          <button
            key={t}
            onClick={() => setTab(t)}
            className={`flex-1 py-2 rounded-xl text-sm font-medium ${
              tab === t ? 'btn-primary !py-2' : 'card !p-2'
            }`}
          >
            {t === 'info' ? 'فعالیت' : t === 'earn' ? 'درآمد' : 'خرید'}
          </button>
        ))}
      </div>

      {tab === 'earn' && transactions.filter(t => t.amount > 0).map((t, i) => (
        <div key={i} className="card flex justify-between text-sm">
          <span className="text-green-500">+{formatTokens(t.amount)}</span>
          <span className="opacity-60">{t.action_type}</span>
        </div>
      ))}

      {tab === 'buy' && purchases.map((p, i) => (
        <div key={i} className="card flex justify-between text-sm">
          <span>{p.product_name}</span>
          <span className="text-red-500">-{formatTokens(p.token_cost)}</span>
        </div>
      ))}

      {tab === 'info' && transactions.slice(0, 10).map((t, i) => (
        <div key={i} className="card flex justify-between text-sm">
          <span className={t.amount > 0 ? 'text-green-500' : 'text-red-500'}>
            {t.amount > 0 ? '+' : ''}{formatTokens(t.amount)}
          </span>
          <span className="opacity-60 text-xs">{new Date(t.created_at).toLocaleDateString('fa-IR')}</span>
        </div>
      ))}
    </div>
  );
}

function Row({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex justify-between text-sm">
      <span className="opacity-60">{label}</span>
      <span className="font-medium">{value}</span>
    </div>
  );
}
