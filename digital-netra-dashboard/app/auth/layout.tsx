export default function AuthLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="relative min-h-screen overflow-hidden bg-[#0b1020]">
      <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(1200px_circle_at_15%_12%,rgba(255,255,255,0.12),rgba(9,15,30,0.85)_45%,rgba(6,10,20,0.98)_70%)]" />
      <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(1000px_circle_at_85%_5%,rgba(120,170,255,0.22),rgba(7,12,25,0.0)_35%)]" />
      <div className="pointer-events-none absolute inset-0 bg-[linear-gradient(180deg,rgba(15,23,42,0.15),rgba(2,6,23,0.9))]" />
      <main className="relative z-10 flex min-h-[100svh] items-center justify-center px-6 py-6 box-border sm:py-10 [@media(max-height:700px)]:py-3">
        <div className="w-full max-w-md">{children}</div>
      </main>
    </div>
  );
}
