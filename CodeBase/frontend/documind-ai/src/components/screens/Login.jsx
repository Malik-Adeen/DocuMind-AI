import React, { useState } from 'react';
import { login, ApiError } from '../../api/client';

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
    <div className="bg-background text-on-surface min-h-screen w-full flex items-center justify-center overflow-hidden relative font-body-sm selection:bg-primary-light selection:text-white">
      {/* Ambient background blur circles */}
      <div className="absolute inset-0 z-0 pointer-events-none opacity-20">
        <div className="absolute top-[-10%] left-[-10%] w-[450px] h-[450px] bg-primary/20 rounded-full blur-[130px]"></div>
        <div className="absolute bottom-[-10%] right-[-10%] w-[550px] h-[550px] bg-secondary/30 rounded-full blur-[150px]"></div>
      </div>
      
      {/* Back to Home floating action */}
      <button 
        onClick={onBackToHome}
        className="absolute top-6 left-6 z-50 flex items-center gap-2 px-3 py-1.5 rounded-lg bg-surface border border-outline-variant text-xs font-semibold hover:bg-surface-variant transition-colors text-on-surface cursor-pointer shadow-sm"
      >
        <span className="material-symbols-outlined text-base">arrow_back</span>
        Back to Home
      </button>

      {/* Main Container */}
      <div className="relative z-10 w-full max-w-5xl h-screen md:h-[80vh] md:max-h-[800px] md:min-h-[580px] md:rounded-2xl md:overflow-hidden flex flex-col md:flex-row mx-auto shadow-2xl border border-outline-variant bg-surface">
        
        {/* Left Side: Premium Floating Documents Scanning (Option B Dark Contrast) */}
        <div className="hidden md:flex flex-1 relative bg-[#111713] border-r border-outline-variant items-center justify-center overflow-hidden p-12">
          
          {/* Subtle Grid backdrop */}
          <div className="absolute inset-0 opacity-[0.03] bg-[linear-gradient(to_right,#ffffff_1px,transparent_1px),linear-gradient(to_bottom,#ffffff_1px,transparent_1px)] bg-[size:30px_30px]"></div>
          
          <div className="relative z-20 flex flex-col justify-between h-full w-full">
            <div className="flex items-center gap-2.5">
              <div className="w-8 h-8 rounded-lg bg-primary flex items-center justify-center text-white shadow-lg shadow-primary/20">
                <span className="material-symbols-outlined text-lg" style={{ fontVariationSettings: "'FILL' 1" }}>psychology</span>
              </div>
              <span className="font-headline-md text-base font-bold tracking-tight text-white">DocuMind</span>
            </div>

            {/* Document scanning visual animation container */}
            <div className="relative flex flex-col items-center justify-center w-full h-80">
              
              {/* Animated Floating Pages */}
              <div className="absolute w-40 h-52 bg-white/5 border border-white/10 rounded-lg shadow-2xl flex flex-col p-4 gap-3 -rotate-12 translate-y-[-15px] translate-x-[-30px] animate-floatSlow">
                <div className="h-2 w-12 bg-white/20 rounded"></div>
                <div className="space-y-1.5">
                  <div className="h-1 bg-white/10 rounded w-full"></div>
                  <div className="h-1 bg-white/10 rounded w-5/6"></div>
                  <div className="h-1 bg-white/10 rounded w-4/6"></div>
                </div>
              </div>

              {/* Floating Extracted structured cards */}
              <div className="absolute w-36 h-16 bg-[#18221C]/95 border border-primary/45 rounded-lg shadow-xl flex items-center gap-3 p-3 rotate-6 translate-x-[60px] translate-y-[35px] animate-floatFast">
                <div className="w-8 h-8 rounded bg-primary/20 flex items-center justify-center text-primary-light">
                  <span className="material-symbols-outlined text-base">verified</span>
                </div>
                <div className="flex-1 min-w-0">
                  <div className="h-1.5 w-8 bg-white/30 rounded"></div>
                  <div className="h-2 w-16 bg-white rounded mt-1.5"></div>
                </div>
              </div>

              {/* Laser scanning effect */}
              <div className="absolute w-44 h-[1px] bg-gradient-to-r from-transparent via-primary to-transparent shadow-[0_0_8px_var(--color-primary)] animate-laserFast z-30"></div>
            </div>

            <div className="max-w-md">
              <h2 className="font-display-lg text-2xl text-white font-bold leading-tight mb-4">Enterprise intelligence.</h2>
              <p className="font-body-lg text-sm text-[#B8C5BE] leading-relaxed">
                Connect your business files and watch DocuMind synthesize critical variables in real time. Compliance validated and SOC2 ready.
              </p>
              <div className="flex items-center gap-3 mt-6 text-xs text-[#87928C] font-label-md">
                <span className="flex h-2 w-2 rounded-full bg-primary"></span>
                <span>Active Workspace Protection Enabled</span>
              </div>
            </div>
          </div>
          {/* Subtle gradient shadow covering bottom */}
          <div className="absolute inset-0 bg-gradient-to-t from-[#111713] via-transparent to-transparent z-10 pointer-events-none"></div>
        </div>

        {/* Right Side: Redesigned Credentials Form */}
        <div className="flex-1 flex flex-col justify-center px-8 py-12 md:px-16 lg:px-20 bg-surface">
          {/* Mobile Logo */}
          <div className="md:hidden flex items-center gap-2.5 mb-10">
            <div className="w-8 h-8 rounded-lg bg-primary flex items-center justify-center text-white">
              <span className="material-symbols-outlined text-lg" style={{ fontVariationSettings: "'FILL' 1" }}>psychology</span>
            </div>
            <span className="font-headline-md text-base font-bold tracking-tight text-on-surface">DocuMind</span>
          </div>

          <div className="w-full max-w-sm mx-auto">
            <div className="mb-8 text-left">
              <h1 className="font-headline-lg text-2xl text-on-surface font-bold tracking-tight mb-1.5">Welcome back</h1>
              <p className="font-body-md text-xs text-on-surface-variant leading-relaxed">Please enter your credentials to access your workspace.</p>
            </div>

            <form onSubmit={handleSubmit} className="space-y-5">
              {error && (
                <div className="px-3 py-2.5 rounded-lg bg-error/10 border border-error/25 text-error text-xs font-label-md">
                  {error}
                </div>
              )}
              <div className="space-y-4">
                {/* Email Input */}
                <div className="space-y-1">
                  <label className="block font-label-md text-[11px] text-on-surface-variant uppercase tracking-wider font-semibold" htmlFor="email">Email address</label>
                  <div className="relative border border-outline-variant bg-background rounded-lg transition-all duration-200 focus-within:border-primary focus-within:ring-2 focus-within:ring-primary/20">
                    <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
                      <span className="material-symbols-outlined text-on-surface-variant text-base">mail</span>
                    </div>
                    <input 
                      className="block w-full pl-9 pr-3 py-2.5 bg-transparent rounded-lg text-on-surface focus:outline-none font-body-md text-xs placeholder-on-surface-variant transition-colors" 
                      id="email" 
                      name="email" 
                      placeholder="sarah.jenkins@company.com" 
                      required 
                      type="email"
                      value={email}
                      onChange={(e) => setEmail(e.target.value)}
                    />
                  </div>
                </div>

                {/* Password Input */}
                <div className="space-y-1">
                  <label className="block font-label-md text-[11px] text-on-surface-variant uppercase tracking-wider font-semibold" htmlFor="password">Password</label>
                  <div className="relative border border-outline-variant bg-background rounded-lg transition-all duration-200 focus-within:border-primary focus-within:ring-2 focus-within:ring-primary/20">
                    <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
                      <span className="material-symbols-outlined text-on-surface-variant text-base">lock</span>
                    </div>
                    <input 
                      className="block w-full pl-9 pr-9 py-2.5 bg-transparent rounded-lg text-on-surface focus:outline-none font-body-md text-xs placeholder-on-surface-variant transition-colors" 
                      id="password" 
                      name="password" 
                      placeholder="••••••••" 
                      required 
                      type={showPassword ? "text" : "password"}
                      value={password}
                      onChange={(e) => setPassword(e.target.value)}
                    />
                    <button 
                      className="absolute inset-y-0 right-0 pr-3 flex items-center text-on-surface-variant hover:text-on-surface transition-colors focus:outline-none cursor-pointer" 
                      type="button"
                      onClick={() => setShowPassword(!showPassword)}
                    >
                      <span className="material-symbols-outlined text-base">
                        {showPassword ? "visibility" : "visibility_off"}
                      </span>
                    </button>
                  </div>
                </div>
              </div>

              <div className="flex items-center justify-between text-xs font-label-md">
                <div className="flex items-center">
                  <input className="h-4.5 w-4.5 bg-background border-outline-variant rounded text-primary focus:ring-primary focus:ring-offset-transparent cursor-pointer" id="remember-me" name="remember-me" type="checkbox"/>
                  <label className="ml-2 block text-on-surface-variant cursor-pointer" htmlFor="remember-me">
                    Keep me signed in
                  </label>
                </div>
                <a className="text-primary hover:underline transition-all" href="#forgot" onClick={(e) => { e.preventDefault(); alert('Password reset module initialized...'); }}>
                  Forgot password?
                </a>
              </div>

              <button 
                className="w-full flex justify-center items-center py-2.5 px-4 rounded-lg text-white font-headline-md text-xs font-bold focus:outline-none bg-primary hover:bg-primary-dark hover:shadow-lg hover:shadow-primary/20 transition-all cursor-pointer transform active:scale-[0.98] disabled:opacity-50 border-none"
                type="submit"
                disabled={isLoading}
              >
                {isLoading ? (
                  <div className="w-5 h-5 rounded-full border-2 border-white/30 border-t-white animate-spin"></div>
                ) : (
                  'Sign in to Workspace'
                )}
              </button>
            </form>

            <div className="mt-8 text-center">
              <p className="font-body-sm text-[11px] text-on-surface-variant">
                Need specialized enterprise integration? 
                <a className="font-label-md text-primary hover:underline ml-1" href="#contact" onClick={(e) => { e.preventDefault(); alert('Redirecting to help center support ticket...'); }}>Contact Support</a>
              </p>
            </div>
          </div>
        </div>

      </div>
    </div>
  );
}
