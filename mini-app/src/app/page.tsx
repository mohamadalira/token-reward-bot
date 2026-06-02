'use client';

import { useState } from 'react';
import HomePage from '@/components/HomePage';
import EarnPage from '@/components/EarnPage';
import ShopPage from '@/components/ShopPage';
import ProfilePage from '@/components/ProfilePage';
import SponsorPage from '@/components/SponsorPage';
import AdminPage from '@/components/AdminPage';
import BottomNav from '@/components/BottomNav';

export type Tab = 'home' | 'earn' | 'shop' | 'profile' | 'sponsor' | 'admin';

export default function Page() {
  const [tab, setTab] = useState<Tab>('home');

  const renderPage = () => {
    switch (tab) {
      case 'home': return <HomePage onNavigate={setTab} />;
      case 'earn': return <EarnPage />;
      case 'shop': return <ShopPage />;
      case 'profile': return <ProfilePage />;
      case 'sponsor': return <SponsorPage />;
      case 'admin': return <AdminPage />;
    }
  };

  return (
    <main className="pb-20 max-w-lg mx-auto">
      {renderPage()}
      <BottomNav active={tab} onChange={setTab} />
    </main>
  );
}
