import React, { useState } from 'react';

export default function Analytics() {
  const [volumeFilter, setVolumeFilter] = useState('Monthly');

  // SVG Chart Data Definitions
  const volumeData = {
    Monthly: {
      points: "M 20 160 Q 80 120 160 145 T 320 80 T 480 60 L 480 190 L 20 190 Z",
      line: "M 20 160 Q 80 120 160 145 T 320 80 T 480 60",
      labels: ['Jan', 'Mar', 'May', 'Jul', 'Sep', 'Nov'],
      dots: [
        { cx: 20, cy: 160, val: '65K' },
        { cx: 110, cy: 125, val: '80K' },
        { cx: 200, cy: 140, val: '95K' },
        { cx: 290, cy: 95, val: '120K' },
        { cx: 380, cy: 75, val: '145K' },
        { cx: 480, cy: 60, val: '175K' }
      ]
    },
    Daily: {
      points: "M 20 140 Q 80 170 160 110 T 320 150 T 480 80 L 480 190 L 20 190 Z",
      line: "M 20 140 Q 80 170 160 110 T 320 150 T 480 80",
      labels: ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'],
      dots: [
        { cx: 20, cy: 140, val: '4.2K' },
        { cx: 110, cy: 155, val: '3.8K' },
        { cx: 200, cy: 120, val: '5.1K' },
        { cx: 290, cy: 135, val: '4.8K' },
        { cx: 380, cy: 110, val: '6.2K' },
        { cx: 480, cy: 80, val: '7.8K' }
      ]
    }
  };

  const currentVolume = volumeData[volumeFilter];

  const accuracyData = [
    { label: 'Invoices', ai: 99.2, ocr: 82.0 },
    { label: 'Receipts', ai: 98.5, ocr: 75.5 },
    { label: 'Contracts', ai: 97.8, ocr: 88.0 },
    { label: 'Forms', ai: 99.5, ocr: 85.0 },
    { label: 'IDs', ai: 99.9, ocr: 90.5 },
  ];

  const customers = [
    { id: 'CUST-8924', name: 'Global Logistics Corp', volume: '14,205', speed: '0.8s', status: 'Healthy' },
    { id: 'CUST-3319', name: 'FinTrust Bank', volume: '11,040', speed: '1.2s', status: 'Healthy' },
    { id: 'CUST-1045', name: 'MediCare Systems', volume: '8,750', speed: '2.4s', status: 'Warning' },
    { id: 'CUST-9921', name: 'Apex Legal Partners', volume: '5,320', speed: '0.9s', status: 'Healthy' },
  ];

  return (
    <div className="flex flex-col gap-stack-lg w-full max-w-7xl mx-auto p-4 md:p-6 lg:p-10 animate-fadeIn">
      {/* Page Header */}
      <header className="mb-2">
        <h1 className="font-headline-lg text-headline-lg-mobile md:text-headline-lg text-on-surface mb-2">Advanced Analytics</h1>
        <p className="font-body-lg text-body-lg text-on-surface-variant">Monitor AI extraction performance, document volumes, and customer metrics.</p>
      </header>

      {/* Grid Layout */}
      <div className="grid grid-cols-1 xl:grid-cols-3 gap-gutter">
        
        {/* Section 1: Interactive line charts for Processing Volume */}
        <div className="glass-card rounded-xl p-6 xl:col-span-2 flex flex-col gap-4">
          <div className="flex justify-between items-center mb-2">
            <h2 className="font-headline-md text-headline-md text-on-surface">Document Processing Volume</h2>
            <div className="flex gap-2">
              <button 
                onClick={() => setVolumeFilter('Daily')}
                className={`px-3 py-1 text-xs rounded border transition-all cursor-pointer ${
                  volumeFilter === 'Daily' 
                    ? 'bg-primary-container text-white border-primary-container' 
                    : 'bg-surface-variant text-on-surface-variant border-outline-variant hover:bg-white/5'
                }`}
              >
                Daily
              </button>
              <button 
                onClick={() => setVolumeFilter('Monthly')}
                className={`px-3 py-1 text-xs rounded border transition-all cursor-pointer ${
                  volumeFilter === 'Monthly' 
                    ? 'bg-primary-container text-white border-primary-container' 
                    : 'bg-surface-variant text-on-surface-variant border-outline-variant hover:bg-white/5'
                }`}
              >
                Monthly
              </button>
            </div>
          </div>
          
          <div className="relative min-h-[300px] w-full bg-[#010a14] rounded-lg border border-white/5 p-4 flex flex-col justify-between">
            <svg viewBox="0 0 500 200" className="w-full h-48 overflow-visible">
              <defs>
                <linearGradient id="volGrad" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor="#4f46e5" stopOpacity="0.4" />
                  <stop offset="100%" stopColor="#4f46e5" stopOpacity="0.0" />
                </linearGradient>
              </defs>
              {/* Grid Lines */}
              <line x1="0" y1="50" x2="500" y2="50" stroke="rgba(255,255,255,0.05)" strokeDasharray="3,3" />
              <line x1="0" y1="100" x2="500" y2="100" stroke="rgba(255,255,255,0.05)" strokeDasharray="3,3" />
              <line x1="0" y1="150" x2="500" y2="150" stroke="rgba(255,255,255,0.05)" strokeDasharray="3,3" />
              {/* Gradient Area */}
              <path d={currentVolume.points} fill="url(#volGrad)" className="transition-all duration-500" />
              {/* Stroke Line */}
              <path d={currentVolume.line} fill="none" stroke="#c3c0ff" strokeWidth="3" className="transition-all duration-500 drop-shadow-[0_0_8px_rgba(195,192,255,0.4)]" />
              {/* Interaction dots */}
              {currentVolume.dots.map((dot, index) => (
                <g key={index} className="group/dot cursor-pointer">
                  <circle cx={dot.cx} cy={dot.cy} r="5" fill="#c3c0ff" className="transition-all duration-500 group-hover/dot:r-7" />
                  <circle cx={dot.cx} cy={dot.cy} r="9" fill="transparent" stroke="#c3c0ff" strokeWidth="1.5" className="opacity-0 group-hover/dot:opacity-100 transition-opacity" />
                  <text x={dot.cx} y={dot.cy - 12} fill="#d3e4fe" fontSize="10" fontFamily="JetBrains Mono" textAnchor="middle" className="opacity-0 group-hover/dot:opacity-100 transition-opacity font-semibold">
                    {dot.val}
                  </text>
                </g>
              ))}
            </svg>
            <div className="flex justify-between px-2 font-label-md text-[10px] text-on-surface-variant border-t border-white/5 pt-2">
              {currentVolume.labels.map((label, index) => (
                <span key={index}>{label}</span>
              ))}
            </div>
          </div>
        </div>

        {/* Section 2: Bar charts for AI Accuracy vs OCR Accuracy */}
        <div className="glass-card rounded-xl p-6 xl:col-span-1 flex flex-col gap-4">
          <div>
            <h2 className="font-headline-md text-headline-md text-on-surface">Extraction Accuracy</h2>
            <p className="text-on-surface-variant text-xs mt-1">Comparison with standard OCR pipelines</p>
          </div>
          
          <div className="flex-grow flex flex-col justify-around bg-[#010a14] rounded-lg border border-white/5 p-4 min-h-[300px]">
            <div className="space-y-4">
              {accuracyData.map((item, index) => (
                <div key={index} className="space-y-1">
                  <div className="flex justify-between text-xs font-label-md">
                    <span className="text-white font-semibold">{item.label}</span>
                    <span className="text-primary font-bold">{item.ai}% vs <span className="text-on-surface-variant font-normal">{item.ocr}%</span></span>
                  </div>
                  {/* Accuracy Bar Graph */}
                  <div className="space-y-1">
                    {/* DocuMind AI */}
                    <div className="w-full h-2 bg-surface-container rounded-full overflow-hidden">
                      <div className="h-full bg-gradient-to-r from-primary-container to-primary rounded-full" style={{ width: `${item.ai}%` }}></div>
                    </div>
                    {/* Standard OCR */}
                    <div className="w-full h-1 bg-surface-container rounded-full overflow-hidden opacity-60">
                      <div className="h-full bg-outline rounded-full" style={{ width: `${item.ocr}%` }}></div>
                    </div>
                  </div>
                </div>
              ))}
            </div>
            
            <div className="flex items-center justify-between text-[11px] font-label-md text-on-surface-variant border-t border-white/5 pt-3">
              <div className="flex items-center gap-1.5">
                <div className="w-2.5 h-2.5 rounded-full bg-primary"></div>
                <span>DocuMind AI</span>
              </div>
              <div className="flex items-center gap-1.5">
                <div className="w-2.5 h-2.5 rounded-full bg-outline opacity-60"></div>
                <span>Standard OCR</span>
              </div>
            </div>
          </div>
        </div>

        {/* Section 3: Donut chart for Revenue by Category */}
        <div className="glass-card rounded-xl p-6 xl:col-span-1 flex flex-col gap-4">
          <h2 className="font-headline-md text-headline-md text-on-surface">Revenue by Category</h2>
          
          <div className="flex-1 bg-[#010a14] rounded-lg border border-white/5 p-6 flex flex-col items-center justify-center min-h-[250px]">
            {/* SVG Donut Chart */}
            <div className="relative w-40 h-40">
              <svg viewBox="0 0 36 36" className="w-full h-full transform -rotate-90">
                <circle cx="18" cy="18" r="15.915" fill="none" stroke="rgba(255,255,255,0.02)" strokeWidth="3" />
                
                {/* 55% Enterprise */}
                <circle cx="18" cy="18" r="15.915" fill="none" stroke="#4f46e5" strokeWidth="3.2" strokeDasharray="55 45" strokeDashoffset="0" />
                {/* 25% SMB */}
                <circle cx="18" cy="18" r="15.915" fill="none" stroke="#c3c0ff" strokeWidth="3.2" strokeDasharray="25 75" strokeDashoffset="-55" />
                {/* 15% API */}
                <circle cx="18" cy="18" r="15.915" fill="none" stroke="#0566d9" strokeWidth="3.2" strokeDasharray="15 85" strokeDashoffset="-80" />
                {/* 5% Individual */}
                <circle cx="18" cy="18" r="15.915" fill="none" stroke="#26364a" strokeWidth="3.2" strokeDasharray="5 95" strokeDashoffset="-95" />
              </svg>
              {/* Inner Hole text */}
              <div className="absolute inset-0 flex flex-col items-center justify-center">
                <span className="font-label-md text-2xl font-bold text-white">$234K</span>
                <span className="font-body-sm text-[10px] text-on-surface-variant uppercase tracking-wider">Total Revenue</span>
              </div>
            </div>

            {/* Legend Grid */}
            <div className="grid grid-cols-2 gap-x-4 gap-y-2 mt-6 w-full font-label-md text-[11px] text-on-surface-variant">
              <div className="flex items-center gap-1.5">
                <span className="w-2.5 h-2.5 rounded-full bg-[#4f46e5] inline-block"></span>
                <span>Enterprise (55%)</span>
              </div>
              <div className="flex items-center gap-1.5">
                <span className="w-2.5 h-2.5 rounded-full bg-[#c3c0ff] inline-block"></span>
                <span>SMB (25%)</span>
              </div>
              <div className="flex items-center gap-1.5">
                <span className="w-2.5 h-2.5 rounded-full bg-[#0566d9] inline-block"></span>
                <span>API (15%)</span>
              </div>
              <div className="flex items-center gap-1.5">
                <span className="w-2.5 h-2.5 rounded-full bg-[#26364a] inline-block"></span>
                <span>Individual (5%)</span>
              </div>
            </div>
          </div>
        </div>

        {/* Section 4: Summary table of top customers by volume */}
        <div className="glass-card rounded-xl p-6 xl:col-span-2 flex flex-col gap-4">
          <div className="flex justify-between items-center mb-2">
            <h2 className="font-headline-md text-headline-md text-on-surface">Top Customers by Volume</h2>
            <span className="font-label-md text-xs text-on-surface-variant bg-surface-container px-2 py-1 rounded">Active Clients</span>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-left border-collapse">
              <thead>
                <tr className="border-b border-white/10 text-on-surface-variant font-label-md text-xs">
                  <th className="py-3 px-3 font-semibold">Customer ID</th>
                  <th className="py-3 px-3 font-semibold">Company Name</th>
                  <th className="py-3 px-3 font-semibold">Total Docs (30d)</th>
                  <th className="py-3 px-3 font-semibold">Avg Processing Time</th>
                  <th className="py-3 px-3 font-semibold">Status</th>
                </tr>
              </thead>
              <tbody className="font-body-sm text-sm text-on-surface divide-y divide-white/5">
                {customers.map((cust, index) => (
                  <tr key={index} className="hover:bg-white/5 transition-colors">
                    <td className="py-3.5 px-3 font-label-md text-primary text-xs">{cust.id}</td>
                    <td className="py-3.5 px-3 font-semibold text-white">{cust.name}</td>
                    <td className="py-3.5 px-3 font-label-md text-xs">{cust.volume}</td>
                    <td className="py-3.5 px-3 font-label-md text-xs">{cust.speed}</td>
                    <td className="py-3.5 px-3">
                      <span className={`inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full text-[10px] font-medium border ${
                        cust.status === 'Healthy' 
                          ? 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20' 
                          : 'bg-amber-500/10 text-amber-400 border-amber-500/20'
                      }`}>
                        <div className={`w-1.5 h-1.5 rounded-full ${cust.status === 'Healthy' ? 'bg-emerald-400' : 'bg-amber-400'}`}></div>
                        {cust.status}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>

      </div>
    </div>
  );
}
