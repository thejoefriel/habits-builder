import { headers } from 'next/headers';
import { auth, signOut } from '@/auth';
import { App } from '@/components/app/app';
import { getAppConfig } from '@/lib/utils';

export default async function Page() {
  const hdrs = await headers();
  const [appConfig, session] = await Promise.all([getAppConfig(hdrs), auth()]);

  return (
    <>
      <App appConfig={appConfig} />
      <div className="fixed top-4 right-4 z-50 flex items-center gap-3">
        <span className="text-muted-foreground font-mono text-xs">
          {session?.user?.email}
        </span>
        <form
          action={async () => {
            'use server';
            await signOut({ redirectTo: '/login' });
          }}
        >
          <button
            type="submit"
            className="text-muted-foreground hover:text-foreground cursor-pointer font-mono text-xs transition-colors"
          >
            Sign out
          </button>
        </form>
      </div>
    </>
  );
}
