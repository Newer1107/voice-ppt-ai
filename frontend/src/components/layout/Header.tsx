'use client';

import { useAuthStore } from '@/stores/authStore';

export default function Header() {
  const user = useAuthStore((s) => s.user);

  return (
    <header className="h-16 bg-white dark:bg-slate-950 border-b border-slate-200 dark:border-slate-800 flex items-center justify-between px-6">
      <div>
        {/* Breadcrumbs could go here */}
      </div>
      <div className="flex items-center gap-4">
        {user && (
          <div className="text-sm text-slate-600 dark:text-slate-400">
            {user.full_name}
          </div>
        )}
      </div>
    </header>
  );
}
