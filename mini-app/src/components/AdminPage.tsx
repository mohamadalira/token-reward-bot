'use client';

import { useEffect, useState } from 'react';
import { apiFetch, formatTokens } from '@/lib/api';
import { useTelegram } from '@/lib/telegram';
import {
  LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid,
} from 'recharts';

interface Dashboard {
  total_users: number;
  active_users: number;
  total_sponsors: number;
  active_campaigns: number;
  total_payments: number;
  tokens_distributed: number;
  total_revenue: number;
  pending_payments: number;
}

export default function AdminPage() {
  const { initData, isReady } = useTelegram();
  const [data, setData] = useState<Dashboard | null>(null);
  const [settings, setSettings] = useState<Record<string, string>>({});
  const [plisioTest, setPlisioTest] = useState('');
  const [error, setError] = useState('');

  useEffect(() => {
    if (!isReady) return;
    apiFetch<Dashboard>('/admin/dashboard', initData)
      .then(setData)
      .catch((e) => setError(e.message));
    apiFetch<Record<string, string>>('/admin/settings', initData)
      .then(setSettings)
      .catch(() => {});
  }, [isReady, initData]);

  const testPlisio = async () => {
    const res = await apiFetch<{ success: boolean; message: string }>(
      '/admin/plisio/test',
      initData,
      { method: 'POST' }
    );
    setPlisioTest(res.message);
  };

  const updateSetting = async (key: string, value: string) => {
    await apiFetch('/admin/settings', initData, {
      method: 'PUT',
      body: JSON.stringify({ key, value }),
    });
    setSettings((s) => ({ ...s, [key]: value }));
  };

  if (error) {
    return <div className="p-4 text-center opacity-60">دسترسی ادمین نداری 🚫</div>;
  }

  if (!data) return <div className="p-4 text-center opacity-60">بارگذاری...</div>;

  const chartData = [
    { name: 'کاربران', value: data.total_users },
    { name: 'فعال', value: data.active_users },
    { name: 'اسپانسر', value: data.total_sponsors },
    { name: 'کمپین', value: data.active_campaigns },
  ];

  return (
    <div className="p-4 space-y-4">
      <h2 className="text-xl font-bold">⚙️ پنل ادمین</h2>

      <div className="grid grid-cols-2 gap-2">
        <Stat label="👥 کاربران" value={data.total_users} />
        <Stat label="🟢 فعال" value={data.active_users} />
        <Stat label="📢 اسپانسر" value={data.total_sponsors} />
        <Stat label="🚀 کمپین" value={data.active_campaigns} />
        <Stat label="💳 پرداخت" value={data.total_payments} />
        <Stat label="🎁 توکن" value={data.tokens_distributed} />
        <Stat label="💰 درآمد" value={`$${data.total_revenue}`} />
        <Stat label="⏳ معلق" value={data.pending_payments} />
      </div>

      <ResponsiveContainer width="100%" height={180}>
        <LineChart data={chartData}>
          <CartesianGrid strokeDasharray="3 3" opacity={0.2} />
          <XAxis dataKey="name" tick={{ fontSize: 10 }} />
          <YAxis tick={{ fontSize: 10 }} />
          <Tooltip />
          <Line type="monotone" dataKey="value" stroke="#3b82f6" strokeWidth={2} />
        </LineChart>
      </ResponsiveContainer>

      <div className="card space-y-3">
        <h3 className="font-bold">⚙️ تنظیمات سریع</h3>
        <SettingInput
          label="حالت ربات"
          value={settings.bot_mode || 'combined'}
          options={['referral', 'task', 'combined']}
          onChange={(v) => updateSetting('bot_mode', v)}
        />
        <SettingInput
          label="پاداش دعوت"
          value={settings.referral_reward || '50'}
          onChange={(v) => updateSetting('referral_reward', v)}
        />
        <SettingInput
          label="قیمت توکن ($)"
          value={settings.token_price_usd || '0.01'}
          onChange={(v) => updateSetting('token_price_usd', v)}
        />
        <SettingInput
          label="حداقل بودجه کمپین"
          value={settings.min_campaign_tokens || '1000'}
          onChange={(v) => updateSetting('min_campaign_tokens', v)}
        />
      </div>

      <div className="card space-y-2">
        <h3 className="font-bold">💳 Plisio</h3>
        <button className="btn-primary" onClick={testPlisio}>🔌 تست اتصال</button>
        {plisioTest && <p className="text-sm text-center">{plisioTest}</p>}
      </div>
    </div>
  );
}

function Stat({ label, value }: { label: string; value: string | number }) {
  return (
    <div className="card text-center py-2">
      <p className="text-lg font-bold">{typeof value === 'number' ? formatTokens(value) : value}</p>
      <p className="text-xs opacity-60">{label}</p>
    </div>
  );
}

function SettingInput({
  label, value, onChange, options,
}: {
  label: string;
  value: string;
  onChange: (v: string) => void;
  options?: string[];
}) {
  return (
    <div className="flex justify-between items-center gap-2 text-sm">
      <span className="opacity-70">{label}</span>
      {options ? (
        <select
          value={value}
          onChange={(e) => onChange(e.target.value)}
          className="rounded-lg px-2 py-1 border border-gray-300 dark:border-gray-700 bg-transparent"
        >
          {options.map((o) => <option key={o} value={o}>{o}</option>)}
        </select>
      ) : (
        <input
          value={value}
          onChange={(e) => onChange(e.target.value)}
          className="rounded-lg px-2 py-1 border border-gray-300 dark:border-gray-700 bg-transparent w-24 text-left"
          dir="ltr"
        />
      )}
    </div>
  );
}
