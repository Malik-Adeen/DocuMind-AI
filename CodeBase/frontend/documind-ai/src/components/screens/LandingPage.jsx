import React, { useState, useEffect } from 'react';

export default function LandingPage({ onNavigateToLogin }) {
  // Parallax tracking states
  const [mouseOffset, setMouseOffset] = useState({ x: 0, y: 0 });
  const [scrollY, setScrollY] = useState(0);
  const [scrolled, setScrolled] = useState(false);

  // Animation staggering states
  const [entranceFinished, setEntranceFinished] = useState(false);
  const [visibleFields, setVisibleFields] = useState(0);
  const [activeInteractiveField, setActiveInteractiveField] = useState(null);

  // Track cursor movement on hero container for parallax effect
  const handleMouseMove = (e) => {
    // Check reduced motion preference
    if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) return;
    const x = (e.clientX - window.innerWidth / 2) / 65;
    const y = (e.clientY - window.innerHeight / 2) / 65;
    setMouseOffset({ x, y });
  };

  useEffect(() => {
    // Scroll event listener
    const handleScroll = () => {
      setScrollY(window.scrollY);
      setScrolled(window.scrollY > 20);
    };
    window.addEventListener('scroll', handleScroll, { passive: true });

    // Stagger entrance transitions for headline words
    const entranceTimer = setTimeout(() => {
      setEntranceFinished(true);
    }, 1500);

    // Stagger right-side card fields animation
    const fieldsTimer = setInterval(() => {
      setVisibleFields(prev => {
        if (prev >= 4) {
          clearInterval(fieldsTimer);
          return 4;
        }
        return prev + 1;
      });
    }, 350);

    return () => {
      window.removeEventListener('scroll', handleScroll);
      clearTimeout(entranceTimer);
      clearInterval(fieldsTimer);
    };
  }, []);

  const extractionFields = [
    { id: 'vendor', label: 'Vendor / Supplier', value: 'Acme Corporation', confidence: '99%', boxClass: 'top-[110px] left-[45px] w-[180px] h-[35px]' },
    { id: 'invNum', label: 'Invoice Number', value: 'INV-2026-1042', confidence: '98%', boxClass: 'top-[160px] left-[550px] w-[150px] h-[25px]' },
    { id: 'amount', label: 'Total Amount', value: '$12,450.00', confidence: '97%', boxClass: 'top-[830px] left-[550px] w-[160px] h-[30px]' },
    { id: 'dueDate', label: 'Due Date', value: '28 Aug 2026', confidence: '95%', boxClass: 'top-[200px] left-[550px] w-[130px] h-[25px]' }
  ];

  return (
    <div className="bg-background text-on-surface min-h-screen w-full font-body-sm relative overflow-x-hidden selection:bg-primary-light selection:text-white">
      
      {/* Subtle Noise and Radial Overlay Background */}
      <div className="absolute inset-0 pointer-events-none z-0 overflow-hidden bg-noise opacity-[0.015]"></div>
      <div className="absolute inset-0 pointer-events-none z-0 overflow-hidden">
        {/* Soft centered brand secondary tint glow */}
        <div className="absolute top-[20%] left-1/2 -translate-x-1/2 w-[80%] max-w-[800px] h-[400px] bg-secondary/35 rounded-full blur-[140px] opacity-70"></div>
        {/* Clean grid lines pattern */}
        <div className="absolute inset-0 opacity-[0.25] bg-[linear-gradient(to_right,var(--color-border)_1px,transparent_1px),linear-gradient(to_bottom,var(--color-border)_1px,transparent_1px)] bg-[size:48px_48px]"></div>
      </div>

      {/* Dynamic Sticky Header Navigation */}
      <header className={`fixed top-0 left-0 right-0 z-50 flex items-center justify-between px-6 md:px-12 transition-all duration-300 ${
        scrolled 
          ? 'h-14 bg-background/90 border-b border-outline-variant/60 backdrop-blur-md shadow-sm' 
          : 'h-20 bg-transparent border-b border-transparent'
      }`}>
        <div className="flex items-center gap-2 cursor-pointer" onClick={() => window.scrollTo({ top: 0, behavior: 'smooth' })}>
          <div className="w-7.5 h-7.5 rounded-lg bg-primary flex items-center justify-center text-white shadow-sm">
            <span className="material-symbols-outlined text-lg font-bold" style={{ fontVariationSettings: "'FILL' 1" }}>psychology</span>
          </div>
          <span className="font-headline-md text-base font-bold tracking-tight text-on-surface">DocuMind</span>
        </div>

        <nav className="hidden md:flex items-center gap-8 text-xs font-label-md tracking-wider text-on-surface-variant font-semibold">
          <a href="#how-it-works" className="hover:text-primary transition-colors">How it works</a>
          <a href="#interactive-demo" className="hover:text-primary transition-colors">Interactive Demo</a>
          <a href="#features" className="hover:text-primary transition-colors">AI Capabilities</a>
          <a href="#security" className="hover:text-primary transition-colors">Security</a>
        </nav>

        <div className="flex items-center gap-4">
          <button 
            onClick={onNavigateToLogin}
            className="text-xs font-label-md font-semibold text-on-surface-variant hover:text-primary transition-colors px-3 py-1.5 cursor-pointer"
          >
            Sign In
          </button>
          <button 
            onClick={onNavigateToLogin}
            className="text-xs font-label-md font-bold text-white bg-primary hover:bg-primary-dark px-4 py-2 rounded-lg hover:shadow-md transition-all cursor-pointer transform active:scale-95"
          >
            Get Started
          </button>
        </div>
      </header>

      {/* Main Art-directed Hero Area */}
      <section 
        onMouseMove={handleMouseMove}
        className="relative z-10 min-h-[92vh] flex flex-col items-center justify-center px-4 md:px-12 pt-28 pb-10 max-w-7xl mx-auto w-full overflow-visible"
      >
        
        {/* Parallax SVG Connection Overlay */}
        <div className="absolute inset-0 w-full h-full pointer-events-none z-10 overflow-visible select-none hidden lg:block">
          <svg className="w-full h-full" viewBox="0 0 1000 600" preserveAspectRatio="none">
            {/* Soft Flow Paths linking Document and Card */}
            <path id="pathLeftRight1" d="M 180 260 C 320 180, 680 180, 820 260" fill="none" stroke="var(--color-secondary)" strokeWidth="1" strokeOpacity="0.45" />
            <path id="pathLeftRight2" d="M 180 320 C 320 400, 680 400, 820 320" fill="none" stroke="var(--color-secondary)" strokeWidth="1" strokeOpacity="0.25" strokeDasharray="4 4" />
            
            {/* Animated particles travelling on path 1 */}
            <circle r="3.5" fill="#588B76" className="opacity-60">
              <animateMotion dur="8s" repeatCount="indefinite" path="M 180 260 C 320 180, 680 180, 820 260" />
            </circle>
            <circle r="2.5" fill="#7FA692" className="opacity-40">
              <animateMotion dur="11s" begin="2.5s" repeatCount="indefinite" path="M 180 260 C 320 180, 680 180, 820 260" />
            </circle>
            <circle r="3" fill="#3F6957" className="opacity-50">
              <animateMotion dur="9s" begin="5s" repeatCount="indefinite" path="M 180 260 C 320 180, 680 180, 820 260" />
            </circle>

            {/* Animated particles travelling on path 2 */}
            <circle r="2.5" fill="#588B76" className="opacity-40">
              <animateMotion dur="10s" begin="1s" repeatCount="indefinite" path="M 180 320 C 320 400, 680 400, 820 320" />
            </circle>
            <circle r="3.5" fill="#D0DED8" className="opacity-75">
              <animateMotion dur="12s" begin="4s" repeatCount="indefinite" path="M 180 320 C 320 400, 680 400, 820 320" />
            </circle>
          </svg>
        </div>

        {/* Triple Layout Grid */}
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-8 lg:gap-4 items-center justify-center w-full relative z-20 min-h-[480px]">
          
          {/* Left Visual: Floating HTML/CSS Document Stack */}
          <div 
            className="col-span-1 lg:col-span-3 flex justify-center items-center relative min-h-[300px] lg:min-h-[440px] order-2 lg:order-1 transition-transform duration-200 ease-out"
            style={{
              transform: `translate(${-(mouseOffset.x + scrollY * 0.12)}px, ${-(mouseOffset.y - scrollY * 0.04)}px)`
            }}
          >
            {/* Background Layer 2 (Rotated -14deg) */}
            <div className="absolute w-[200px] h-[270px] bg-white rounded-lg border border-outline-variant shadow-md animate-docLayer2 opacity-35 select-none pointer-events-none flex flex-col p-4 gap-2 z-0">
              <div className="w-10 h-2 bg-primary/20 rounded"></div>
              <div className="w-full h-px bg-outline-variant/30"></div>
              <div className="space-y-1.5 mt-2">
                <div className="w-full h-1 bg-on-surface-variant/10 rounded"></div>
                <div className="w-3/4 h-1 bg-on-surface-variant/10 rounded"></div>
                <div className="w-5/6 h-1 bg-on-surface-variant/10 rounded"></div>
              </div>
            </div>

            {/* Background Layer 1 (Rotated -10deg) */}
            <div className="absolute w-[200px] h-[270px] bg-white rounded-lg border border-outline-variant shadow-lg animate-docLayer1 opacity-60 select-none pointer-events-none flex flex-col p-4 gap-2 z-10">
              <div className="w-12 h-2 bg-primary/30 rounded"></div>
              <div className="w-full h-px bg-outline-variant/30"></div>
              <div className="space-y-1.5 mt-2">
                <div className="w-full h-1.5 bg-on-surface-variant/10 rounded"></div>
                <div className="w-full h-1.5 bg-on-surface-variant/10 rounded"></div>
                <div className="w-2/3 h-1.5 bg-on-surface-variant/10 rounded"></div>
              </div>
            </div>

            {/* Foreground Main Invoice Document Card (Rotated -6deg) */}
            <div className="w-[210px] h-[280px] bg-white rounded-lg border border-outline-variant shadow-2xl flex flex-col p-5 gap-3.5 animate-docStackFloat z-20 hover:scale-[1.02] hover:border-primary-light transition-all select-none">
              <div className="flex justify-between items-center border-b border-outline-variant pb-2">
                <span className="font-label-md text-[8px] font-bold text-primary tracking-wider">INVOICE</span>
                <span className="text-[7px] font-body-sm text-on-surface-variant">Ref: 2026-1042</span>
              </div>

              <div className="flex justify-between text-[7px] font-body-sm leading-tight text-on-surface-variant">
                <div>
                  <span className="block text-[6px] font-bold uppercase text-on-surface-variant/75">Billed To</span>
                  <span className="font-semibold text-on-surface">Acme Corp</span>
                </div>
                <div className="text-right">
                  <span className="block text-[6px] font-bold uppercase text-on-surface-variant/75">Due Date</span>
                  <span className="font-semibold text-on-surface">28 Aug 2026</span>
                </div>
              </div>

              {/* Invoice line item blocks */}
              <div className="space-y-1.5 flex-1 mt-1">
                <div className="flex justify-between text-[6px] text-on-surface-variant font-bold border-b border-outline-variant pb-0.5">
                  <span>Item</span>
                  <span>Qty</span>
                  <span className="text-right">Amount</span>
                </div>
                <div className="flex justify-between text-[6px] text-on-surface leading-none">
                  <span className="font-semibold">AI Data Core Platform</span>
                  <span>1</span>
                  <span className="font-semibold text-right">$10,000.00</span>
                </div>
                <div className="flex justify-between text-[6px] text-on-surface leading-none">
                  <span className="font-semibold">Custom Ingress Node</span>
                  <span>1</span>
                  <span className="font-semibold text-right">$2,450.00</span>
                </div>
              </div>

              <div className="flex justify-between items-center pt-2 border-t border-outline-variant mt-auto">
                <span className="text-[8px] font-bold text-on-surface-variant">TOTAL</span>
                <span className="text-[10px] font-bold text-primary-dark">$12,450.00</span>
              </div>
            </div>

            {/* Orbit scanning circle path */}
            <div className="absolute w-[240px] h-[310px] rounded-full border border-outline-variant/30 scale-x-[1.25] rotate-[20deg] pointer-events-none z-30">
              <div className="w-1.5 h-1.5 bg-primary rounded-full absolute top-[10%] left-[20%] animate-pulse"></div>
            </div>
          </div>

          {/* Center Column: Kinetic Editorial Typography Hero Headline */}
          <div 
            className="col-span-1 lg:col-span-6 flex flex-col items-center justify-center text-center gap-7 select-none order-1 lg:order-2"
            style={{
              transform: `translateY(${scrollY * -0.15}px)`
            }}
          >
            {/* Staggered Word Kinetic Stack */}
            <h1 className="flex flex-col items-center leading-none tracking-tight gap-1 w-full md:max-w-xl mx-auto">
              <span 
                className={`font-display-serif text-5xl md:text-7xl font-light text-on-surface inline-block ${
                  entranceFinished ? 'animate-floatWordFrom' : 'animate-fadeBlurIn'
                }`}
                style={{ animationDelay: entranceFinished ? undefined : '0ms' }}
              >
                From documents
              </span>
              
              {/* Transitional Italic Word "to" */}
              <span 
                className={`font-display-serif-alt italic text-3xl md:text-5xl text-primary relative py-1 mx-2 inline-block ${
                  entranceFinished ? 'animate-floatWordTo' : 'animate-fadeBlurIn'
                }`}
                style={{ animationDelay: entranceFinished ? undefined : '160ms' }}
              >
                to
                <svg className="absolute bottom-[-1px] left-0 w-full h-[3px] pointer-events-none" viewBox="0 0 50 4" fill="none">
                  <path d="M 1 2 Q 25 4, 49 2" stroke="var(--color-primary)" strokeWidth="1.5" strokeLinecap="round" className="animate-drawLine" />
                </svg>
              </span>
              
              <span 
                className={`font-display-serif text-6xl md:text-8xl font-semibold text-primary-dark tracking-normal mt-1.5 inline-block ${
                  entranceFinished ? 'animate-floatWordDecisions' : 'animate-fadeBlurIn'
                }`}
                style={{ animationDelay: entranceFinished ? undefined : '320ms' }}
              >
                decisions.
              </span>
            </h1>

            <p className="font-body-md text-sm md:text-base text-on-surface-variant max-w-[560px] leading-relaxed px-4">
              Upload invoices, contracts, PDFs, and business documents. DocuMind uses multi-modal AI to extract, understand, and organize the information you need — automatically.
            </p>

            {/* Action buttons */}
            <div className="flex flex-col sm:flex-row gap-4 mt-1">
              <button 
                onClick={onNavigateToLogin}
                className="group px-7 py-3 rounded-lg bg-primary hover:bg-primary-dark text-white font-headline-md text-xs font-bold hover:shadow-lg transition-all cursor-pointer flex items-center justify-center gap-1.5 transform active:scale-95 border-none"
              >
                Try DocuMind Free
                <span className="material-symbols-outlined text-sm font-bold transition-transform group-hover:translate-x-1">arrow_forward</span>
              </button>
              <a 
                href="#interactive-demo"
                className="group px-7 py-3 rounded-lg border border-outline-variant hover:bg-surface-variant text-on-surface font-headline-md text-xs font-semibold transition-all flex items-center justify-center gap-1.5 cursor-pointer transform active:scale-95"
              >
                See how it works
                <span className="material-symbols-outlined text-sm transition-transform group-hover:translate-y-0.5">arrow_downward</span>
              </a>
            </div>
          </div>

          {/* Right Visual: Floating UI Extraction Panel */}
          <div 
            className="col-span-1 lg:col-span-3 flex justify-center items-center relative min-h-[300px] lg:min-h-[440px] order-3 transition-transform duration-200 ease-out"
            style={{
              transform: `translate(${mouseOffset.x + scrollY * 0.12}px, ${mouseOffset.y - scrollY * 0.04}px)`
            }}
          >
            {/* Product Extraction Card (Rotated 4deg) */}
            <div className="w-[220px] bg-white border border-outline-variant rounded-xl shadow-2xl p-5 flex flex-col gap-4 animate-cardFloat hover:scale-[1.02] hover:border-primary transition-all z-20 hover:shadow-lg select-none">
              <div className="flex items-center gap-2 border-b border-outline-variant pb-2">
                <span className="material-symbols-outlined text-primary text-base font-bold">check_circle</span>
                <span className="font-label-md text-[9px] font-bold text-on-surface tracking-wider">EXTRACTED DATA</span>
              </div>

              {/* Live Staggered Extraction Fields */}
              <div className="space-y-3.5 flex-1 min-h-[170px]">
                {/* Vendor Field */}
                <div className={`transition-all duration-500 flex flex-col gap-0.5 ${visibleFields >= 1 ? 'opacity-100 transform translate-y-0' : 'opacity-0 transform translate-y-2'}`}>
                  <span className="text-[7px] font-label-md text-on-surface-variant uppercase tracking-wider font-semibold">Vendor Name</span>
                  <div className="flex items-center justify-between mt-0.5">
                    <span className="text-[10px] font-bold text-on-surface">Acme Corporation</span>
                    <span className="text-[6px] font-label-md text-emerald-500 font-bold">99%</span>
                  </div>
                </div>

                {/* Invoice Number Field */}
                <div className={`transition-all duration-500 flex flex-col gap-0.5 ${visibleFields >= 2 ? 'opacity-100 transform translate-y-0' : 'opacity-0 transform translate-y-2'}`}>
                  <span className="text-[7px] font-label-md text-on-surface-variant uppercase tracking-wider font-semibold">Invoice Number</span>
                  <div className="flex items-center justify-between mt-0.5">
                    <span className="text-[10px] font-bold text-on-surface">INV-2026-1042</span>
                    <span className="text-[6px] font-label-md text-emerald-500 font-bold">98%</span>
                  </div>
                </div>

                {/* Amount Field */}
                <div className={`transition-all duration-500 flex flex-col gap-0.5 ${visibleFields >= 3 ? 'opacity-100 transform translate-y-0' : 'opacity-0 transform translate-y-2'}`}>
                  <span className="text-[7px] font-label-md text-on-surface-variant uppercase tracking-wider font-semibold">Amount</span>
                  <div className="flex items-center justify-between mt-0.5">
                    <span className="text-[10px] font-bold text-primary-dark font-display-serif-alt italic">$12,450.00</span>
                    <span className="text-[6px] font-label-md text-emerald-500 font-bold">97%</span>
                  </div>
                </div>

                {/* Due Date Field */}
                <div className={`transition-all duration-500 flex flex-col gap-0.5 ${visibleFields >= 4 ? 'opacity-100 transform translate-y-0' : 'opacity-0 transform translate-y-2'}`}>
                  <span className="text-[7px] font-label-md text-on-surface-variant uppercase tracking-wider font-semibold">Due Date</span>
                  <div className="flex items-center justify-between mt-0.5">
                    <span className="text-[10px] font-bold text-on-surface">28 Aug 2026</span>
                    <span className="text-[6px] font-label-md text-emerald-500 font-bold">95%</span>
                  </div>
                </div>
              </div>

              <div className="flex items-center justify-center border-t border-outline-variant pt-2">
                <span className="text-[8px] font-semibold text-on-surface-variant flex items-center gap-1">
                  <span className="material-symbols-outlined text-[10px] font-bold text-primary">add</span>
                  12 more fields extracted
                </span>
              </div>
            </div>
          </div>

        </div>

        {/* Minimal Understated Trust / Feature Bar */}
        <div 
          className="w-full border-t border-outline-variant/60 pt-8 mt-12 grid grid-cols-2 md:grid-cols-4 gap-6 items-center justify-center select-none"
          style={{
            opacity: Math.max(1 - scrollY / 250, 0),
            pointerEvents: scrollY > 200 ? 'none' : 'auto'
          }}
        >
          <div className="flex flex-col items-center text-center gap-1.5">
            <div className="flex items-center gap-1.5 text-primary">
              <span className="material-symbols-outlined text-base">security</span>
              <span className="font-headline-md text-xs font-bold text-on-surface">Enterprise Security</span>
            </div>
            <span className="text-[10px] font-label-md text-on-surface-variant uppercase tracking-wider">SOC 2 • GDPR • Encrypted</span>
          </div>

          <div className="flex flex-col items-center text-center gap-1.5">
            <div className="flex items-center gap-1.5 text-primary">
              <span className="material-symbols-outlined text-base">fact_check</span>
              <span className="font-headline-md text-xs font-bold text-on-surface">AI Accuracy</span>
            </div>
            <span className="text-[10px] font-label-md text-on-surface-variant uppercase tracking-wider">High precision extraction</span>
          </div>

          <div className="flex flex-col items-center text-center gap-1.5">
            <div className="flex items-center gap-1.5 text-primary">
              <span className="material-symbols-outlined text-base">layers</span>
              <span className="font-headline-md text-xs font-bold text-on-surface">Supports 50+ Formats</span>
            </div>
            <span className="text-[10px] font-label-md text-on-surface-variant uppercase tracking-wider">PDF, DOCX, PNG & more</span>
          </div>

          <div className="flex flex-col items-center text-center gap-1.5">
            <div className="flex items-center gap-1.5 text-primary">
              <span className="material-symbols-outlined text-base">group</span>
              <span className="font-headline-md text-xs font-bold text-on-surface">Trusted by Teams</span>
            </div>
            <span className="text-[10px] font-label-md text-on-surface-variant uppercase tracking-wider">Across 20+ industries</span>
          </div>
        </div>

      </section>

      {/* Interactive Demonstration Pipeline Center (Original features retained below the redesigned Hero) */}
      <section id="interactive-demo" className="relative z-10 py-24 px-6 md:px-12 border-t border-outline-variant bg-surface-secondary/40">
        <div className="max-w-6xl mx-auto flex flex-col lg:flex-row gap-12 items-center">
          
          <div className="flex-1 space-y-6">
            <div className="inline-flex items-center gap-2 px-3 py-1 rounded bg-secondary text-primary-dark border border-primary/20 text-[10px] font-label-md font-bold uppercase tracking-wider">
              Live Interactive Workspace
            </div>
            <h2 className="font-headline-lg text-3xl font-bold tracking-tight text-on-surface">
              Know exactly where <br/> information came from.
            </h2>
            <p className="font-body-md text-base text-on-surface-variant leading-relaxed">
              DocuMind preserves auditability. Hover over any extracted database field to reveal the exact physical segment our model read to generate the data point.
            </p>
            
            <div className="flex flex-col gap-2.5 mt-4">
              {extractionFields.map((field) => (
                <div 
                  key={field.id}
                  onMouseEnter={() => setActiveInteractiveField(field.id)}
                  onMouseLeave={() => setActiveInteractiveField(null)}
                  className={`p-4 rounded-lg border cursor-pointer transition-all flex items-center justify-between ${
                    activeInteractiveField === field.id 
                      ? 'bg-secondary-light border-primary translate-x-2' 
                      : 'bg-surface border-outline-variant hover:border-primary-light'
                  }`}
                >
                  <div className="flex flex-col">
                    <span className="text-[10px] font-label-md text-on-surface-variant uppercase tracking-wider">{field.label}</span>
                    <span className="text-sm font-semibold text-on-surface mt-1">{field.value}</span>
                  </div>
                  <span className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded text-[10px] font-label-md bg-secondary text-primary-dark border border-primary/10">
                    {field.confidence} Conf
                  </span>
                </div>
              ))}
            </div>
          </div>

          <div className="flex-1 flex justify-center w-full">
            {/* Invoice Graphic with hovered box highlight */}
            <div className="w-full max-w-[460px] h-[590px] bg-white rounded-lg shadow-xl relative overflow-hidden flex-shrink-0 select-none border border-outline-variant">
              <div 
                className="w-full h-full bg-cover bg-center" 
                style={{ 
                  backgroundImage: "url('https://lh3.googleusercontent.com/aida-public/AB6AXuCNkLukXcdabcNgZHUlabZpgNockogAoPATzHMt2gChLka2u9-UOsSX_qblCBp7VEGzNgcURtigvNtg6aXcWH_GlD3NLeG4m7c4vrSvlJQpnkDOcfhzqhDdn_R5T26YQdAkyEMys8MbCztMWp8SJ2rsjJW6O2wpvPfApWE2aOkbkoS_BftyVZDQueAr72l2u8SX7Hqqasy7cGZjyGtsBzB2FbZcDrN7O4Jtc7-jnmVhCCFdMAiQkyEI')",
                  backgroundSize: 'cover'
                }}
              >
                {/* Active Highlight Overlays */}
                {extractionFields.map((field) => (
                  <div 
                    key={field.id}
                    className={`absolute rounded transition-all duration-300 border-2 flex items-start justify-end p-1 ${
                      activeInteractiveField === field.id 
                        ? 'border-primary bg-primary/15 scale-102 opacity-100 shadow-[0_0_10px_rgba(88,139,118,0.4)]' 
                        : 'border-transparent bg-transparent opacity-0 pointer-events-none'
                    } ${field.boxClass}`}
                  >
                    <span className="bg-primary text-white font-label-md text-[8px] px-1 rounded-sm shadow-sm font-semibold uppercase leading-none">
                      {field.id === 'invNum' ? 'Ref Number' : field.id === 'dueDate' ? 'Due' : field.id}
                    </span>
                  </div>
                ))}
              </div>
            </div>
          </div>

        </div>
      </section>

      {/* How it Works: Scroll-based Carousel */}
      <section id="how-it-works" className="relative z-10 py-24 px-6 md:px-12 max-w-7xl mx-auto">
        <div className="text-center mb-16 flex flex-col items-center gap-4">
          <h2 className="font-headline-lg text-3xl font-bold text-on-surface tracking-tight">Structured Document Flow</h2>
          <p className="font-body-md text-base text-on-surface-variant max-w-2xl leading-relaxed">
            From ingestion to backend automation, DocuMind manages every processing step with microsecond precision.
          </p>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-4 gap-6">
          <div className="bg-surface rounded-xl p-6 border border-outline-variant hover:border-primary-light transition-colors flex flex-col gap-4 shadow-sm">
            <div className="w-10 h-10 rounded-lg bg-secondary-light flex items-center justify-center text-primary border border-primary/20">
              <span className="material-symbols-outlined">upload_file</span>
            </div>
            <div>
              <h3 className="font-headline-md text-base font-semibold text-on-surface">1. Secure Upload</h3>
              <p className="font-body-sm text-xs text-on-surface-variant mt-2 leading-relaxed">
                Ingest PDF scan nodes, receipts, or contracts securely. TLS 1.3 encryption ensures complete security.
              </p>
            </div>
          </div>

          <div className="bg-surface rounded-xl p-6 border border-outline-variant hover:border-primary-light transition-colors flex flex-col gap-4 shadow-sm">
            <div className="w-10 h-10 rounded-lg bg-secondary-light flex items-center justify-center text-primary border border-primary/20">
              <span className="material-symbols-outlined">settings_suggest</span>
            </div>
            <div>
              <h3 className="font-headline-md text-base font-semibold text-on-surface">2. AI Layout Analysis</h3>
              <p className="font-body-sm text-xs text-on-surface-variant mt-2 leading-relaxed">
                Models identify text layers, extract coordinates, index tabular items, and construct bounding trees.
              </p>
            </div>
          </div>

          <div className="bg-surface rounded-xl p-6 border border-outline-variant hover:border-primary-light transition-colors flex flex-col gap-4 shadow-sm">
            <div className="w-10 h-10 rounded-lg bg-secondary-light flex items-center justify-center text-primary border border-primary/20">
              <span className="material-symbols-outlined">analytics</span>
            </div>
            <div>
              <h3 className="font-headline-md text-base font-semibold text-on-surface">3. Verify & Review</h3>
              <p className="font-body-sm text-xs text-on-surface-variant mt-2 leading-relaxed">
                Low confidence anomalies trigger human-in-the-loop alerts inside our split-screen verification workspace.
              </p>
            </div>
          </div>

          <div className="bg-surface rounded-xl p-6 border border-outline-variant hover:border-primary-light transition-colors flex flex-col gap-4 shadow-sm">
            <div className="w-10 h-10 rounded-lg bg-secondary-light flex items-center justify-center text-primary border border-primary/20">
              <span className="material-symbols-outlined">ios_share</span>
            </div>
            <div>
              <h3 className="font-headline-md text-base font-semibold text-on-surface">4. Output Integration</h3>
              <p className="font-body-sm text-xs text-on-surface-variant mt-2 leading-relaxed">
                Export clean CSV, JSON structures, or hook directly to Salesforce, SAP, AWS S3, and developer REST nodes.
              </p>
            </div>
          </div>
        </div>
      </section>

      {/* Security & Integrations Grid */}
      <section id="security" className="relative z-10 py-24 px-6 md:px-12 border-t border-outline-variant bg-surface-secondary/40">
        <div className="max-w-6xl mx-auto grid grid-cols-1 lg:grid-cols-2 gap-12 items-center">
          <div>
            <h2 className="font-headline-lg text-3xl font-bold tracking-tight text-on-surface">Enterprise-grade security. <br/> Zero compliance risks.</h2>
            <p className="font-body-md text-base text-on-surface-variant mt-4 leading-relaxed">
              We know your business documents are highly sensitive. DocuMind guarantees isolated container sandboxing. Your documents are never used for general model retraining.
            </p>
            <div className="grid grid-cols-2 gap-4 mt-8">
              <div className="flex gap-2 items-start">
                <span className="material-symbols-outlined text-primary text-base mt-0.5">verified_user</span>
                <div>
                  <h4 className="text-on-surface text-xs font-bold">SOC2 Type II</h4>
                  <p className="text-[10px] text-on-surface-variant mt-0.5">Continuous automated systems audits.</p>
                </div>
              </div>
              <div className="flex gap-2 items-start">
                <span className="material-symbols-outlined text-primary text-base mt-0.5">security_update_good</span>
                <div>
                  <h4 className="text-on-surface text-xs font-bold">AES-256 Encryption</h4>
                  <p className="text-[10px] text-on-surface-variant mt-0.5">Documents encrypted at rest and in transit.</p>
                </div>
              </div>
            </div>
          </div>

          <div className="bg-surface rounded-2xl p-6 border border-outline-variant relative overflow-hidden flex flex-col gap-6 shadow-sm">
            <h3 className="text-on-surface text-sm font-bold uppercase tracking-wider font-label-md">Active Cloud Integrations</h3>
            <div className="grid grid-cols-3 gap-4 text-center text-xs">
              <div className="p-4 bg-surface-secondary border border-outline-variant rounded-lg flex flex-col items-center justify-center gap-2">
                <span className="material-symbols-outlined text-primary">cloud</span>
                <span className="text-[11px] font-semibold text-on-surface">AWS S3</span>
              </div>
              <div className="p-4 bg-surface-secondary border border-outline-variant rounded-lg flex flex-col items-center justify-center gap-2">
                <span className="material-symbols-outlined text-primary">window</span>
                <span className="text-[11px] font-semibold text-on-surface">Azure Blob</span>
              </div>
              <div className="p-4 bg-surface-secondary border border-outline-variant rounded-lg flex flex-col items-center justify-center gap-2">
                <span className="material-symbols-outlined text-primary">backup</span>
                <span className="text-[11px] font-semibold text-on-surface">Google Cloud</span>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* CTA Section */}
      <section className="relative z-10 py-24 px-6 md:px-12 text-center max-w-5xl mx-auto">
        <div className="bg-surface rounded-3xl p-12 border border-outline-variant relative overflow-hidden flex flex-col items-center gap-6 shadow-sm">
          <div className="absolute inset-0 bg-primary-light/10 opacity-30"></div>
          <h2 className="font-headline-lg text-3xl font-bold tracking-tight text-on-surface relative z-10">
            Automate your document workflow today.
          </h2>
          <p className="font-body-md text-base text-on-surface-variant max-w-lg leading-relaxed relative z-10">
            Join thousands of modern enterprises using DocuMind AI to process millions of transactions monthly.
          </p>
          <button 
            onClick={onNavigateToLogin}
            className="px-8 py-3.5 rounded-lg bg-primary hover:bg-primary-dark text-white font-headline-md text-sm font-bold hover:shadow-lg hover:shadow-primary/20 transition-all cursor-pointer relative z-10 transform active:scale-95 border-none"
          >
            Create Your Free Account
          </button>
        </div>
      </section>

      {/* Footer */}
      <footer className="relative z-10 border-t border-outline-variant py-12 px-6 md:px-12 flex flex-col md:flex-row items-center justify-between gap-6 max-w-7xl mx-auto text-xs text-on-surface-variant font-label-md">
        <div className="flex items-center gap-2">
          <div className="w-6 h-6 rounded bg-primary flex items-center justify-center text-white">
            <span className="material-symbols-outlined text-sm font-bold">psychology</span>
          </div>
          <span className="font-bold text-on-surface tracking-tight">DocuMind AI</span>
        </div>
        <div>
          © 2026 DocuMind. Designed by Farhad Ali
        </div>
      </footer>
    </div>
  );
}
