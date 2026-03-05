export default function AuthLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="app-shell relative min-h-screen">
      <div className="app-bg" />
      <div className="app-grid" />
      <div className="app-scanlines" />
      <div className="pointer-events-none absolute -top-20 right-16 hidden h-56 w-56 rounded-full bg-gradient-to-br from-amber-400/40 via-orange-400/30 to-transparent blur-3xl animate-float lg:block" />
      <div className="pointer-events-none absolute bottom-[-120px] left-[-80px] hidden h-72 w-72 rounded-full bg-gradient-to-tr from-sky-400/40 via-blue-400/30 to-transparent blur-3xl animate-float lg:block" />
      <main className="relative z-10 flex min-h-screen items-center justify-center px-6 py-12">
        <div className="w-full max-w-md sm:max-w-md lg:max-w-lg">{children}</div>
      </main>
    </div>
  );
}
