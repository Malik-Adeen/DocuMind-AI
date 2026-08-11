import React from 'react';

export default function Dashboard({ onViewChange }) {
  const kpiData = [
    { label: 'Total Docs', value: '1.2M', desc: 'All time processed', icon: 'description' },
    { label: 'Processed', value: '984K', desc: 'Successfully validated', icon: 'check_circle' },
    { label: 'Queue', value: '1,240', desc: 'Active processing', icon: 'hourglass_empty', pulse: true },
    { label: 'Accuracy', value: '99.2%', desc: 'AI confidence target', icon: 'fact_check', highlight: true },
    { label: 'Confidence', value: '98.5%', desc: 'Avg. document score', icon: 'psychology' },
    { label: 'Active Users', value: '342', desc: 'Enterprise seats occupied', icon: 'group' },
    { label: 'MRC', value: '$14.2K', desc: 'Monthly recurring cost', icon: 'payments' },
    { label: 'OTC', value: '$2.4K', desc: 'One-time cost', icon: 'receipt_long' },
  ];

  const recentDocs = [
    { id: 'DOC-9082', name: 'invoice_google_cloud_2026.pdf', type: 'Invoice', size: '1.2 MB', score: '99.4%', status: 'Processed' },
    { id: 'DOC-9081', name: 'service_agreement_v4_draft.pdf', type: 'Contract', size: '4.8 MB', score: '94.2%', status: 'In Review' },
    { id: 'DOC-9080', name: 'receipt_uber_taxicab_trip.jpg', type: 'Receipt', size: '540 KB', score: '98.8%', status: 'Processed' },
    { id: 'DOC-9079', name: 'vendor_onboarding_form_corp.pdf', type: 'Form', size: '2.1 MB', score: '87.5%', status: 'In Review' },
  ];

  return (
    <div className="flex flex-col gap-stack-lg w-full max-w-7xl mx-auto p-4 md:p-6 lg:p-10 animate-fadeIn">
      {/* Header section */}
      <div className="flex flex-col md:flex-row justify-between items-start md:items-end gap-4">
        <div>
          <h2 className="font-headline-lg text-headline-lg text-white">Welcome back, Admin</h2>
          <p className="font-body-md text-body-md text-on-surface-variant mt-1">Here is what's happening with your documents today.</p>
        </div>
        <div className="font-label-md text-label-md text-on-surface-variant bg-surface-container px-3 py-1.5 rounded border border-white/5">
          Oct 24, 2023
        </div>
      </div>

      {/* KPI Cards Grid */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-stack-md">
        {kpiData.map((kpi, idx) => (
          <div key={idx} className="glass-card p-4 rounded-lg flex flex-col gap-2 hover:shadow-lg hover:border-white/20 transition-all duration-300">
            <div className="flex items-center justify-between text-on-surface-variant">
              <span className="font-label-md text-xs uppercase tracking-wider">{kpi.label}</span>
              <span className="material-symbols-outlined text-lg">{kpi.icon}</span>
            </div>
            <div className="flex items-center gap-2 mt-1">
              <span className={`font-headline-lg text-2xl md:text-3xl font-bold ${kpi.highlight ? 'text-secondary-fixed' : 'text-white'}`}>
                {kpi.value}
              </span>
              {kpi.pulse && (
                <span className="relative flex h-2.5 w-2.5">
                  <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-primary opacity-75"></span>
                  <span className="relative inline-flex rounded-full h-2.5 w-2.5 bg-primary"></span>
                </span>
              )}
            </div>
            <span className="font-body-sm text-xs text-on-surface-variant">{kpi.desc}</span>
          </div>
        ))}
      </div>

      {/* Grid: Chart & Recent activity */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-stack-lg">
        {/* SVG Chart Container */}
        <div className="lg:col-span-2 glass-card p-6 rounded-xl flex flex-col gap-4">
          <div className="flex justify-between items-center">
            <div>
              <h3 className="font-headline-md text-lg text-white">Extraction Throughput</h3>
              <p className="font-body-sm text-xs text-on-surface-variant">Document volume processed over the last 6 months</p>
            </div>
            <select className="bg-surface-container border border-white/10 rounded px-2.5 py-1 text-xs text-on-surface focus:outline-none">
              <option>Last 6 Months</option>
              <option>Last 30 Days</option>
            </select>
          </div>
          
          {/* SVG Line Graph */}
          <div className="relative h-64 w-full flex items-center justify-center bg-surface-variant rounded-lg overflow-hidden border border-outline-variant">
            <svg viewBox="0 0 500 200" className="w-full h-full p-4 overflow-visible">
              <defs>
                <linearGradient id="chartGrad" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor="#588B76" stopOpacity="0.4" />
                  <stop offset="100%" stopColor="#588B76" stopOpacity="0.0" />
                </linearGradient>
              </defs>
              {/* Grid lines */}
              <line x1="0" y1="50" x2="500" y2="50" stroke="rgba(255,255,255,0.03)" strokeDasharray="3,3" />
              <line x1="0" y1="100" x2="500" y2="100" stroke="rgba(255,255,255,0.03)" strokeDasharray="3,3" />
              <line x1="0" y1="150" x2="500" y2="150" stroke="rgba(255,255,255,0.03)" strokeDasharray="3,3" />
              {/* Line path */}
              <path 
                d="M 20 160 Q 100 120 180 140 T 340 70 T 480 50" 
                fill="none" 
                stroke="#588B76" 
                strokeWidth="3" 
                className="drop-shadow-[0_0_8px_rgba(88,139,118,0.3)]"
              />
              {/* Area path */}
              <path 
                d="M 20 160 Q 100 120 180 140 T 340 70 T 480 50 L 480 190 L 20 190 Z" 
                fill="url(#chartGrad)" 
              />
              {/* Data Points */}
              <circle cx="20" cy="160" r="4" fill="#588B76" />
              <circle cx="100" cy="122" r="4" fill="#588B76" />
              <circle cx="180" cy="140" r="4" fill="#588B76" />
              <circle cx="260" cy="100" r="4" fill="#588B76" />
              <circle cx="340" cy="70" r="4" fill="#588B76" />
              <circle cx="410" cy="55" r="4" fill="#588B76" />
              <circle cx="480" cy="50" r="4" fill="#588B76" />
            </svg>
            <div className="absolute bottom-2 left-4 right-4 flex justify-between font-label-md text-[10px] text-on-surface-variant">
              <span>May</span>
              <span>Jun</span>
              <span>Jul</span>
              <span>Aug</span>
              <span>Sep</span>
              <span>Oct</span>
            </div>
          </div>
        </div>

        {/* Recent Activity List */}
        <div className="glass-card p-6 rounded-xl flex flex-col gap-4">
          <div>
            <h3 className="font-headline-md text-lg text-white">Recent Activity</h3>
            <p className="font-body-sm text-xs text-on-surface-variant">Live document parsing updates</p>
          </div>
          
          <div className="flex flex-col gap-3">
            {recentDocs.map((doc, idx) => (
              <div key={idx} className="flex flex-col gap-1 p-3 bg-surface-variant/40 hover:bg-surface-variant/70 rounded-lg border border-outline-variant transition-all duration-200">
                <div className="flex justify-between items-center">
                  <span className="font-body-sm font-semibold text-white truncate max-w-[160px]">{doc.name}</span>
                  <span className={`px-2 py-0.5 rounded-full text-[10px] font-label-md font-bold ${
                    doc.status === 'Processed' ? 'bg-secondary text-primary-dark' : 'bg-primary-light/10 text-primary-light border border-primary-light/20'
                  }`}>
                    {doc.status}
                  </span>
                </div>
                <div className="flex justify-between items-center text-xs text-on-surface-variant mt-1">
                  <span className="font-label-md text-[11px]">{doc.id} • {doc.type}</span>
                  <span className="font-label-md text-xs text-primary-light">AI: {doc.score}</span>
                </div>
              </div>
            ))}
          </div>

          <button 
            onClick={() => onViewChange('Documents')}
            className="w-full mt-auto py-2 border border-outline-variant rounded font-label-md text-xs text-primary hover:bg-primary-dark/20 transition-colors cursor-pointer"
          >
            View Document History
          </button>
        </div>
      </div>
    </div>
  );
}
