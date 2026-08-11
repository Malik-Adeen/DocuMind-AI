import React from 'react';

export default function Sidebar({ activeTab, onSelectTab, onLogout, pendingCount }) {
  const mainNavItems = [
    { id: 'Dashboard', icon: 'dashboard', label: 'Dashboard' },
    { id: 'Upload', icon: 'cloud_upload', label: 'Upload' },
    { id: 'Processing', icon: 'settings_suggest', label: 'Processing', badge: pendingCount > 0 ? pendingCount : null },
    { id: 'Documents', icon: 'description', label: 'Documents' },
    { id: 'Analytics', icon: 'analytics', label: 'Analytics' },
    { id: 'Exports', icon: 'ios_share', label: 'Exports' },
    { id: 'Users', icon: 'group', label: 'Users' },
    { id: 'Settings', icon: 'settings', label: 'Settings' },
  ];

  return (
    <nav className="hidden md:flex flex-col bg-surface-container border-r border-white/10 w-64 h-screen fixed left-0 top-0 py-6 px-4 z-50">
      {/* Brand Header */}
      <div className="flex items-center gap-3 mb-8 px-2">
        <div className="w-10 h-10 rounded-lg bg-primary-container flex items-center justify-center text-white">
          <span className="material-symbols-outlined font-semibold text-2xl">document_scanner</span>
        </div>
        <div>
          <h1 className="font-headline-md text-headline-md text-primary leading-tight font-bold">DocuMind AI</h1>
          <p className="font-label-md text-[10px] text-on-surface-variant font-semibold tracking-wider uppercase">Enterprise Intelligence</p>
        </div>
      </div>

      {/* Main Navigation links */}
      <div className="flex-1 overflow-y-auto pr-1 space-y-1">
        {mainNavItems.map((item) => {
          const isActive = activeTab === item.id || (item.id === 'Documents' && activeTab === 'Review');
          return (
            <button
              key={item.id}
              onClick={() => onSelectTab(item.id)}
              className={`w-full flex items-center gap-3 px-3 py-2 rounded-lg font-label-md text-xs cursor-pointer transition-all duration-200 ${
                isActive
                  ? 'bg-primary-dark text-white font-bold shadow-sm'
                  : 'text-on-surface-variant hover:text-on-surface hover:bg-white/5'
              }`}
            >
              <span className={`material-symbols-outlined text-lg ${isActive ? 'text-secondary' : ''}`}>{item.icon}</span>
              <span className="flex-1 text-left">{item.label}</span>
              {item.badge && (
                <span className="px-1.5 py-0.5 rounded-full bg-primary text-white font-bold text-[9px]">
                  {item.badge}
                </span>
              )}
            </button>
          );
        })}
      </div>

      {/* Footer CTA & Secondary links */}
      <div className="mt-auto pt-6 border-t border-white/10 flex flex-col gap-4">
        <button 
          onClick={() => alert('Pricing tiers modal opened...')}
          className="w-full py-2.5 px-4 rounded-lg bg-gradient-to-r from-primary-container to-secondary-container text-white font-label-md text-xs font-bold hover:shadow-[0_0_15px_rgba(79,70,229,0.5)] transition-all flex items-center justify-center gap-2 cursor-pointer"
        >
          <span className="material-symbols-outlined text-base">rocket_launch</span>
          Upgrade Plan
        </button>

        <div className="space-y-1">
          <button
            onClick={() => onSelectTab('Help')}
            className={`w-full flex items-center gap-3 px-3 py-2 rounded-lg font-label-md text-xs cursor-pointer transition-all duration-200 ${
              activeTab === 'Help'
                ? 'bg-primary-dark text-white font-bold'
                : 'text-on-surface-variant hover:text-on-surface hover:bg-white/5'
            }`}
          >
            <span className={`material-symbols-outlined text-lg ${activeTab === 'Help' ? 'text-secondary' : ''}`}>help</span>
            <span className="text-left">Help</span>
          </button>
          
          <button
            onClick={onLogout}
            className="w-full flex items-center gap-3 px-3 py-2 rounded-lg font-label-md text-xs text-on-surface-variant hover:text-error hover:bg-error/10 cursor-pointer transition-all duration-200"
          >
            <span className="material-symbols-outlined text-lg">logout</span>
            <span className="text-left">Logout</span>
          </button>
        </div>
      </div>
    </nav>
  );
}
