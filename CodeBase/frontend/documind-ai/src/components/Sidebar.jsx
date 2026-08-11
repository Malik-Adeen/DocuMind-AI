import React from 'react';
import {
  LayoutDashboard,
  UploadCloud,
  Cpu,
  FileText,
  BarChart3,
  Share2,
  Users,
  Settings,
  Rocket,
  HelpCircle,
  LogOut,
  FileSearch,
} from 'lucide-react';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';

export default function Sidebar({ activeTab, onSelectTab, onLogout, pendingCount }) {
  const mainNavItems = [
    { id: 'Dashboard', icon: LayoutDashboard, label: 'Dashboard' },
    { id: 'Upload', icon: UploadCloud, label: 'Upload' },
    { id: 'Processing', icon: Cpu, label: 'Processing', badge: pendingCount > 0 ? pendingCount : null },
    { id: 'Documents', icon: FileText, label: 'Documents' },
    { id: 'Analytics', icon: BarChart3, label: 'Analytics' },
    { id: 'Exports', icon: Share2, label: 'Exports' },
    { id: 'Users', icon: Users, label: 'Users' },
    { id: 'Settings', icon: Settings, label: 'Settings' },
  ];

  return (
    <nav className="hidden md:flex flex-col bg-card border-r border-border/40 w-64 h-screen fixed left-0 top-0 py-6 px-4 z-50">
      {/* Brand Header */}
      <div className="flex items-center gap-3 mb-8 px-2">
        <div className="p-2.5 rounded-lg bg-primary text-white shadow-lg shadow-primary/20">
          <FileSearch className="w-5 h-5" />
        </div>
        <div>
          <h1 className="font-bold text-sm text-foreground tracking-tight leading-tight">DocuMind AI</h1>
          <p className="font-label-md text-[10px] text-muted-foreground font-semibold tracking-wider uppercase">Enterprise Intelligence</p>
        </div>
      </div>

      {/* Main Navigation */}
      <div className="flex-1 overflow-y-auto pr-1 space-y-1">
        {mainNavItems.map((item) => {
          const IconComponent = item.icon;
          const isActive = activeTab === item.id || (item.id === 'Documents' && activeTab === 'Review');
          return (
            <button
              key={item.id}
              onClick={() => onSelectTab(item.id)}
              className={`w-full flex items-center gap-3 px-3 py-2 rounded-lg font-label-md text-xs cursor-pointer transition-all duration-200 ${
                isActive
                  ? 'bg-primary text-white font-bold shadow-sm'
                  : 'text-muted-foreground hover:text-foreground hover:bg-muted/40'
              }`}
            >
              <IconComponent className={`w-4 h-4 ${isActive ? 'text-white' : 'text-muted-foreground'}`} />
              <span className="flex-1 text-left">{item.label}</span>
              {item.badge && (
                <Badge variant="default" className="px-1.5 py-0 text-[9px] h-4 leading-none">
                  {item.badge}
                </Badge>
              )}
            </button>
          );
        })}
      </div>

      {/* Footer CTA & Actions */}
      <div className="mt-auto pt-6 border-t border-border/40 space-y-3">
        <Button
          onClick={() => alert('Upgrade tier options initialized.')}
          className="w-full text-xs font-bold gap-2 bg-gradient-to-r from-primary to-accent hover:opacity-95"
        >
          <Rocket className="w-4 h-4" />
          Upgrade Plan
        </Button>

        <div className="space-y-1">
          <button
            onClick={() => onSelectTab('Help')}
            className={`w-full flex items-center gap-3 px-3 py-2 rounded-lg font-label-md text-xs cursor-pointer transition-all duration-200 ${
              activeTab === 'Help'
                ? 'bg-primary text-white font-bold'
                : 'text-muted-foreground hover:text-foreground hover:bg-muted/40'
            }`}
          >
            <HelpCircle className="w-4 h-4" />
            <span className="text-left">Help</span>
          </button>

          <button
            onClick={onLogout}
            className="w-full flex items-center gap-3 px-3 py-2 rounded-lg font-label-md text-xs text-muted-foreground hover:text-destructive hover:bg-destructive/10 cursor-pointer transition-all duration-200"
          >
            <LogOut className="w-4 h-4" />
            <span className="text-left">Logout</span>
          </button>
        </div>
      </div>
    </nav>
  );
}
