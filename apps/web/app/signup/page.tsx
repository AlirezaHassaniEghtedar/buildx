import { AuthForm } from "@/components/features/AuthForm";
import { Logo } from "@/components/ui/Logo";
import { ThemeToggle } from "@/components/ui/ThemeToggle";

export default function SignupPage() {
  return (
    <main className="mx-auto flex min-h-dvh max-w-[1200px] flex-col px-6">
      <header className="flex items-center justify-between py-6">
        <Logo />
        <ThemeToggle />
      </header>
      <div className="flex flex-1 items-center justify-center pb-24">
        <AuthForm mode="signup" />
      </div>
    </main>
  );
}
