import { signIn } from '@/auth';

export default function LoginPage() {
  return (
    <main className="flex min-h-screen items-center justify-center">
      <div className="flex flex-col items-center gap-6">
        <h1 className="font-mono text-2xl font-bold tracking-wide">Habits</h1>
        <p className="text-muted-foreground font-mono text-sm">
          Sign in to get started
        </p>
        <form
          action={async () => {
            'use server';
            await signIn('google', { redirectTo: '/' });
          }}
        >
          <button
            type="submit"
            className="bg-foreground text-background hover:bg-foreground/90 cursor-pointer rounded-md px-6 py-3 font-mono text-sm font-medium transition-colors"
          >
            Sign in with Google
          </button>
        </form>
      </div>
    </main>
  );
}
