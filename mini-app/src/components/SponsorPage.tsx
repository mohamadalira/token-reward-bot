'use client';

import { useEffect, useState } from 'react';
import { apiFetch, formatTokens } from '@/lib/api';
import { useTelegram } from '@/lib/telegram';
import {
  BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer,
  LineChart, Line, CartesianGrid,
} from 'recharts';

interface Campaign {
  id: number;
  title: string;
  reward_per_join: number;
  total_budget: number;
  remaining_budget: number;
  distributed_tokens: number;
  total_joins: number;
  total_views: number;
  conversion_rate: number;
  estimated_remaining_joins: number;
  status: string;
}

interface Dashboard {
  wallet_balance: number;
  total_purchased: number;
  total_consumed: number;
  allocated: number;
  available: number;
  campaigns: Campaign[];
}

const statusLabels: Record<string, string> = {
  active: '🟢 فعال',
  paused: '⏸ متوقف',
  exhausted: '🔴 تمام شده',
  pending_approval: '⏳ در انتظار',
  payment_pending: '💳 پرداخت',
};

export default function SponsorPage() {
  const { initData, isReady } = useTelegram();
  const [data, setData] = useState<Dashboard | null>(null);
  const [selectedCampaign, setSelectedCampaign] = useState<number | null>(null);
  const [analytics, setAnalytics] = useState<any>(null);
  const [loading, setLoading] = useState(true);

  const load = () => {
    apiFetch<Dashboard>('/sponsor/dashboard', initData)
      .then(setData)
      .catch(() => setData(null))
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    if (isReady) load();
  }, [isReady, initData]);

  const loadAnalytics = async (campaignId: number) => {
    setSelectedCampaign(campaignId);
    const res = await apiFetch<any>(`/sponsor/campaigns/${campaignId}/analytics`, initData);
    setAnalytics(res);
  };

  const pauseCampaign = async (id: number) => {
    await apiFetch(`/sponsor/campaigns/${id}/pause`, initData, { method: 'POST' });
    load();
  };

  const resumeCampaign = async (id: number) => {
    await apiFetch(`/sponsor/campaigns/${id}/resume`, initData, { method: 'POST' });
    load();
  };

  if (loading) return <div className="p-4 text-center opacity-60">بارگذاری...</div>;

  if (!data) {
    return (
      <div className="p-4 text-center space-y-4">
        <p className="opacity-60">پنل اسپانسر</p>
        <p className="text-sm">از ربات درخواست اسپانسری بده 🚀</p>
      </div>
    );
  }

  const chartData = analytics?.hourly_views
    ? Object.entries(analytics.hourly_views).map(([hour, count]) => ({
        hour: `${hour}:۰۰`,
        views: count,
      }))
    : [];

  return (
    <div className="p-4 space-y-4">
      <h2 className="text-xl font-bold">📢 پنل اسپانسر</h2>

      <div className="card space-y-2">
        <h3 className="font-bold">💳 کیف پول</h3>
        <div className="grid grid-cols-2 gap-2 text-sm">
          <WalletItem label="موجودی" value={data.wallet_balance} />
          <WalletItem label="قابل استفاده" value={data.available} />
          <WalletItem label="خریداری شده" value={data.total_purchased} />
          <WalletItem label="مصرف شده" value={data.total_consumed} />
        </div>
      </div>

      <h3 className="font-bold">📊 کمپین‌ها</h3>
      {data.campaigns.map((c) => (
        <div key={c.id} className="card space-y-2">
          <div className="flex justify-between">
            <span className="font-bold">{c.title}</span>
            <span className="text-xs">{statusLabels[c.status] || c.status}</span>
          </div>
          <div className="grid grid-cols-2 gap-1 text-xs opacity-80">
            <span>💰 پاداش: {formatTokens(c.reward_per_join)}</span>
            <span>📦 باقی: {formatTokens(c.remaining_budget)}</span>
            <span>👥 عضویت: {formatTokens(c.total_joins)}</span>
            <span>📈 تبدیل: {formatTokens(c.conversion_rate)}%</span>
            <span>🎯 باقی‌مانده: {formatTokens(c.estimated_remaining_joins)}</span>
            <span>📤 توزیع: {formatTokens(c.distributed_tokens)}</span>
          </div>
          <div className="flex gap-2">
            {c.status === 'active' && (
              <button className="btn-secondary !py-2 text-xs flex-1" onClick={() => pauseCampaign(c.id)}>
                ⏸ توقف
              </button>
            )}
            {c.status === 'paused' && (
              <button className="btn-primary !py-2 text-xs flex-1" onClick={() => resumeCampaign(c.id)}>
                ▶️ ادامه
              </button>
            )}
            <button className="btn-secondary !py-2 text-xs flex-1" onClick={() => loadAnalytics(c.id)}>
              📈 آمار
            </button>
          </div>
        </div>
      ))}

      {selectedCampaign && analytics && (
        <div className="card space-y-3">
          <h3 className="font-bold">📈 آنalytics کمپین #{selectedCampaign}</h3>
          <div className="grid grid-cols-3 gap-2 text-center text-sm">
            <div><p className="font-bold">{formatTokens(analytics.total_views)}</p><p className="opacity-60">بازدید</p></div>
            <div><p className="font-bold">{formatTokens(analytics.total_joins)}</p><p className="opacity-60">عضویت</p></div>
            <div><p className="font-bold">{formatTokens(analytics.conversion_rate)}%</p><p className="opacity-60">تبدیل</p></div>
          </div>
          {chartData.length > 0 && (
            <ResponsiveContainer width="100%" height={200}>
              <BarChart data={chartData}>
                <CartesianGrid strokeDasharray="3 3" opacity={0.2} />
                <XAxis dataKey="hour" tick={{ fontSize: 10 }} />
                <YAxis tick={{ fontSize: 10 }} />
                <Tooltip />
                <Bar dataKey="views" fill="#3b82f6" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          )}
        </div>
      )}
    </div>
  );
}

function WalletItem({ label, value }: { label: string; value: number }) {
  return (
    <div className="card !p-2 text-center">
      <p className="font-bold">{formatTokens(value)}</p>
      <p className="opacity-60 text-xs">{label}</p>
    </div>
  );
}
