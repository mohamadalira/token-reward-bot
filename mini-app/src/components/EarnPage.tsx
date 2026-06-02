'use client';

import { useEffect, useState } from 'react';
import { apiFetch, formatTokens } from '@/lib/api';
import { useTelegram } from '@/lib/telegram';

interface Task {
  id: number;
  title: string;
  reward: number;
  invite_link: string;
}

interface Profile {
  referral_link: string;
  referral_count: number;
}

export default function EarnPage() {
  const { initData, isReady } = useTelegram();
  const [tasks, setTasks] = useState<Task[]>([]);
  const [profile, setProfile] = useState<Profile | null>(null);
  const [verifying, setVerifying] = useState<number | null>(null);
  const [message, setMessage] = useState('');

  useEffect(() => {
    if (!isReady) return;
    Promise.all([
      apiFetch<Task[]>('/user/tasks', initData),
      apiFetch<Profile>('/user/profile', initData),
    ]).then(([t, p]) => {
      setTasks(t);
      setProfile(p);
    }).catch(console.error);
  }, [isReady, initData]);

  const verify = async (taskId: number) => {
    setVerifying(taskId);
    setMessage('');
    try {
      const res = await apiFetch<{ success: boolean; message: string }>(
        `/user/tasks/${taskId}/verify`,
        initData,
        { method: 'POST' }
      );
      setMessage(res.message);
    } catch (e: any) {
      setMessage(e.message);
    } finally {
      setVerifying(null);
    }
  };

  const shareReferral = () => {
    const tg = (window as any).Telegram?.WebApp;
    const link = profile?.referral_link || '';
    if (tg) {
      tg.openTelegramLink(`https://t.me/share/url?url=${encodeURIComponent(link)}&text=${encodeURIComponent('با لینک من عضو شو و توکن بگیر!')}`);
    }
  };

  return (
    <div className="p-4 space-y-4">
      <h2 className="text-xl font-bold">💰 کسب توکن</h2>

      <div className="card space-y-3">
        <h3 className="font-bold">👥 دعوت دوستان</h3>
        <p className="text-sm opacity-70 break-all">{profile?.referral_link}</p>
        <p className="text-sm">دعوت‌ها: {formatTokens(profile?.referral_count || 0)}</p>
        <button className="btn-primary" onClick={shareReferral}>🔗 اشتراک‌گذاری لینک</button>
      </div>

      <h3 className="font-bold">📢 تسک‌های اسپانسر</h3>
      {tasks.length === 0 && (
        <p className="text-center opacity-60 py-8">فعلاً تسکی نیست 😕</p>
      )}
      {tasks.map((task) => (
        <div key={task.id} className="card space-y-3">
          <div className="flex justify-between items-center">
            <span className="font-bold">{task.title}</span>
            <span className="text-sm bg-green-100 dark:bg-green-900 text-green-700 dark:text-green-300 px-2 py-1 rounded-lg">
              {formatTokens(task.reward)} توکن
            </span>
          </div>
          <div className="grid grid-cols-2 gap-2">
            <a href={task.invite_link} target="_blank" rel="noopener" className="btn-secondary text-center">
              🔗 عضویت
            </a>
            <button
              className="btn-primary"
              disabled={verifying === task.id}
              onClick={() => verify(task.id)}
            >
              {verifying === task.id ? '⏳' : '✅ تایید'}
            </button>
          </div>
        </div>
      ))}

      {message && (
        <div className="card text-center text-sm">{message}</div>
      )}
    </div>
  );
}
