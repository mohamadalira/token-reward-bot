'use client';

import { useEffect, useState } from 'react';
import { apiFetch, formatTokens } from '@/lib/api';
import { useTelegram } from '@/lib/telegram';

interface Product {
  id: number;
  name: string;
  description: string;
  token_cost: number;
  category: string;
  config_type: string;
  stock: number;
}

export default function ShopPage() {
  const { initData, isReady } = useTelegram();
  const [products, setProducts] = useState<Product[]>([]);
  const [message, setMessage] = useState('');
  const [buying, setBuying] = useState<number | null>(null);

  useEffect(() => {
    if (!isReady) return;
    apiFetch<Product[]>('/user/shop', initData).then(setProducts).catch(console.error);
  }, [isReady, initData]);

  const buy = async (productId: number) => {
    setBuying(productId);
    setMessage('');
    try {
      const res = await apiFetch<{ success: boolean; message: string; config?: string }>(
        `/user/shop/${productId}/purchase`,
        initData,
        { method: 'POST' }
      );
      setMessage(res.message);
      if (res.config) {
        const tg = (window as any).Telegram?.WebApp;
        tg?.showAlert?.(`کانفیگ:\n${res.config.substring(0, 200)}...`);
      }
    } catch (e: any) {
      setMessage(e.message);
    } finally {
      setBuying(null);
    }
  };

  return (
    <div className="p-4 space-y-4">
      <h2 className="text-xl font-bold">🛒 فروشگاه کانفیگ</h2>

      {products.length === 0 && (
        <p className="text-center opacity-60 py-8">فعلاً محصولی نیست 😕</p>
      )}

      {products.map((p) => (
        <div key={p.id} className="card space-y-2">
          <div className="flex justify-between">
            <h3 className="font-bold">{p.name}</h3>
            <span className="text-xs opacity-60">{p.config_type}</span>
          </div>
          {p.description && <p className="text-sm opacity-70">{p.description}</p>}
          <div className="flex justify-between text-sm">
            <span>📂 {p.category}</span>
            <span>📊 موجودی: {formatTokens(p.stock)}</span>
          </div>
          <div className="flex justify-between items-center pt-2">
            <span className="text-lg font-bold text-blue-500">{formatTokens(p.token_cost)} توکن</span>
            <button
              className="btn-primary !w-auto px-6"
              disabled={buying === p.id}
              onClick={() => buy(p.id)}
            >
              {buying === p.id ? '⏳' : '🛒 خرید'}
            </button>
          </div>
        </div>
      ))}

      {message && <div className="card text-center text-sm">{message}</div>}
    </div>
  );
}
