import React, { useState } from 'react';
import { login, ApiError } from '../../api/client';
import { Card } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Button } from '@/components/ui/button';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Mail, Lock, Eye, EyeOff, ArrowLeft, ShieldCheck, Cpu, Loader2, CheckCircle2 } from 'lucide-react';

export default function Login({ onLogin, onBackToHome }) {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState('');

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    setIsLoading(true);
    try {
      const response = await login(email, password);
      onLogin(response);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Login failed.');
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="bg-background text-foreground min-h-screen w-full flex items-center justify-center overflow-hidden relative font-sans selection:bg-primary selection:text-white">
      {/* Background ambient lighting */}
      <div className="absolute inset-0 z-0 pointer-events-none opacity-25">
        <div className="absolute top-[-10%] left-[-10%] w-[480px] h-[480px] bg-primary/20 rounded-full blur-[140px]"></div>
        <div className="absolute bottom-[-10%] right-[-10%] w-[520px] h-[520px] bg-accent/30 rounded-full blur-[160px]"></div>
      </div>

      {/* Back to Home floating action */}
      <Button
        variant="glass"
        size="sm"
        onClick={onBackToHome}
        className="absolute top-6 left-6 z-50 gap-2 shadow-sm"
      >
        <ArrowLeft className="w-4 h-4" />
        Back to Home
      </Button>

      {/* Main Container */}
      <Card className="relative z-10 w-full max-w-5xl h-screen md:h-[80vh] md:max-h-[780px] md:min-h-[560px] md:rounded-2xl md:overflow-hidden flex flex-col md:flex-row mx-4 shadow-2xl border-border/60 p-0 bg-card">
        
        {/* Left Side Visual Panel */}
        <div className="hidden md:flex flex-1 relative bg-background border-r border-border/40 flex-col justify-between p-10 overflow-hidden">
          <div className="absolute inset-0 opacity-[0.03] bg-[linear-gradient(to_right,#ffffff_1px,transparent_1px),linear-gradient(to_bottom,#ffffff_1px,transparent_1px)] bg-[size:32px_32px]"></div>

          <div className="relative z-20 flex items-center gap-3">
            <div className="p-2 rounded-lg bg-primary text-white shadow-lg shadow-primary/20">
              <Cpu className="w-5 h-5" />
            </div>
            <span className="font-bold text-lg text-foreground tracking-tight">DocuMind AI</span>
          </div>

          {/* Floating animated visual items */}
          <div className="relative flex flex-col items-center justify-center w-full h-72">
            <div className="absolute w-44 h-56 bg-card/60 border border-border/60 rounded-xl shadow-2xl flex flex-col p-4 gap-3 -rotate-12 -translate-y-3 -translate-x-6 animate-floatSlow">
              <div className="h-2 w-14 bg-muted-foreground/30 rounded"></div>
              <div className="space-y-1.5">
                <div className="h-1.5 bg-muted-foreground/20 rounded w-full"></div>
                <div className="h-1.5 bg-muted-foreground/20 rounded w-4/5"></div>
                <div className="h-1.5 bg-muted-foreground/20 rounded w-2/3"></div>
              </div>
            </div>

            <div className="absolute w-40 h-20 bg-card/90 border border-primary/50 rounded-xl shadow-xl flex items-center gap-3 p-3 rotate-6 translate-x-12 translate-y-8 animate-floatFast">
              <div className="p-2 rounded-lg bg-primary/20 text-primary-light">
                <ShieldCheck className="w-5 h-5" />
              </div>
              <div className="flex-1 min-w-0">
                <div className="h-2 w-10 bg-muted-foreground/30 rounded"></div>
                <div className="h-2.5 w-20 bg-foreground rounded mt-2"></div>
              </div>
            </div>

            <div className="absolute w-48 h-[1px] bg-gradient-to-r from-transparent via-primary to-transparent shadow-[0_0_8px_var(--color-primary)] animate-laserFast z-30"></div>
          </div>

          <div className="relative z-20 space-y-2">
            <h3 className="text-xl font-bold text-foreground">Document Intelligence Pipeline</h3>
            <p className="text-xs text-muted-foreground leading-relaxed">
              Automated OCR parsing, deterministic gate verification, and structured Excel generation for enterprise finance operations.
            </p>
            <div className="flex items-center gap-2 pt-2 text-[11px] font-label-md text-emerald-400">
              <CheckCircle2 className="w-3.5 h-3.5" />
              <span>Deterministic Gate Protection Active</span>
            </div>
          </div>
        </div>

        {/* Right Form Panel */}
        <div className="flex-1 flex flex-col justify-center px-8 py-12 md:px-14 lg:px-16 bg-card">
          <div className="w-full max-w-sm mx-auto space-y-6">
            <div className="space-y-1 text-left">
              <h1 className="text-2xl font-bold text-foreground tracking-tight">Welcome back</h1>
              <p className="text-xs text-muted-foreground">Sign in to access your document verification workspace.</p>
            </div>

            {error && (
              <Alert variant="destructive">
                <AlertDescription>{error}</AlertDescription>
              </Alert>
            )}

            <form onSubmit={handleSubmit} className="space-y-4">
              <div className="space-y-1.5">
                <label className="block text-[11px] font-label-md uppercase tracking-wider text-muted-foreground font-semibold" htmlFor="email">
                  Email address
                </label>
                <div className="relative">
                  <Mail className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground" />
                  <Input
                    id="email"
                    type="email"
                    placeholder="name@ptcl.internal"
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    className="pl-9 h-10"
                    required
                  />
                </div>
              </div>

              <div className="space-y-1.5">
                <label className="block text-[11px] font-label-md uppercase tracking-wider text-muted-foreground font-semibold" htmlFor="password">
                  Password
                </label>
                <div className="relative">
                  <Lock className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground" />
                  <Input
                    id="password"
                    type={showPassword ? 'text' : 'password'}
                    placeholder="••••••••"
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    className="pl-9 pr-9 h-10"
                    required
                  />
                  <button
                    type="button"
                    onClick={() => setShowPassword(!showPassword)}
                    className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground cursor-pointer"
                  >
                    {showPassword ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                  </button>
                </div>
              </div>

              <div className="flex items-center justify-between text-xs pt-1">
                <label className="flex items-center gap-2 text-muted-foreground cursor-pointer">
                  <input type="checkbox" className="rounded border-border bg-background text-primary focus:ring-primary" />
                  Remember me
                </label>
                <a
                  href="#forgot"
                  onClick={(e) => { e.preventDefault(); alert('Password reset module initialized.'); }}
                  className="text-primary hover:underline font-label-md"
                >
                  Forgot password?
                </a>
              </div>

              <Button type="submit" className="w-full h-10 font-bold" disabled={isLoading}>
                {isLoading ? <Loader2 className="w-4 h-4 animate-spin" /> : 'Sign in to Workspace'}
              </Button>
            </form>
          </div>
        </div>
      </Card>
    </div>
  );
}
