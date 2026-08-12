import React, { useState } from 'react';
import { setAuthToken, clearAuthToken, getAuthToken } from './api/client';
import Login from './components/screens/Login';
import Dashboard from './components/screens/Dashboard';
import UploadCenter from './components/screens/UploadCenter';
import ProcessingQueue from './components/screens/ProcessingQueue';
import DocumentHistory from './components/screens/DocumentHistory';
import DocumentReview from './components/screens/DocumentReview';
import Analytics from './components/screens/Analytics';
import ExportCenter from './components/screens/ExportCenter';
import UserManagement from './components/screens/UserManagement';
import Settings from './components/screens/Settings';
import HelpCenter from './components/screens/HelpCenter';
import Sidebar from './components/Sidebar';
import LandingPage from './components/screens/LandingPage';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Search, Bell, Moon, Menu, X, LogOut, Cpu } from 'lucide-react';

export default function App() {
  const [isAuthenticated, setIsAuthenticated] = useState(() => Boolean(getAuthToken()));
  const [view, setView] = useState('landing');
  const [activeScreen, setActiveScreen] = useState('Dashboard');
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);

  const [queueItems, setQueueItems] = useState([]);

  const [selectedReviewDoc, setSelectedReviewDoc] = useState(null);

  const handleLogin = (loginResponse) => {
    setAuthToken(loginResponse.access_token);
    setIsAuthenticated(true);
    setActiveScreen('Dashboard');
  };

  const handleLogout = () => {
    clearAuthToken();
    setIsAuthenticated(false);
    setView('landing');
  };

  const handleDocumentUploaded = (document) => {
    setQueueItems((prev) => [
      {
        document_id: document.document_id,
        filename: document.filename,
        status: document.status,
        progress: 0,
        stage_detail: null,
        error: null,
      },
      ...prev,
    ]);
  };

  const handleUpdateQueueItem = (documentId, patch) => {
    setQueueItems((prev) =>
      prev.map((item) => (item.document_id === documentId ? { ...item, ...patch } : item))
    );
  };

  const handleDismissItem = (documentId) => {
    setQueueItems((prev) => prev.filter((item) => item.document_id !== documentId));
  };

  const handleSelectDocument = (doc) => {
    setSelectedReviewDoc(doc.document_id || doc.id);
    setActiveScreen('Review');
  };

  if (!isAuthenticated) {
    if (view === 'login') {
      return <Login onLogin={handleLogin} onBackToHome={() => setView('landing')} />;
    }
    return <LandingPage onNavigateToLogin={() => setView('login')} />;
  }

  const TERMINAL_STATUSES = ['complete', 'needs_review', 'failed'];
  const pendingQueueCount = queueItems.filter((item) => !TERMINAL_STATUSES.includes(item.status)).length;

  return (
    <div className="bg-background text-foreground font-sans antialiased min-h-screen flex w-full">
      {/* Desktop Navigation */}
      <Sidebar
        activeTab={activeScreen}
        onSelectTab={(tab) => {
          setActiveScreen(tab);
          setMobileMenuOpen(false);
        }}
        onLogout={handleLogout}
        pendingCount={pendingQueueCount}
      />

      {/* Main Content Pane */}
      <div className="flex-1 md:ml-64 flex flex-col min-h-screen relative overflow-hidden">
        
        {/* Top Header Bar */}
        <header className="flex justify-between items-center px-6 sticky top-0 z-40 w-full h-14 bg-card/70 backdrop-blur-xl border-b border-border/40 shrink-0">
          <div className="flex items-center gap-3">
            <Button
              variant="ghost"
              size="icon"
              onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
              className="md:hidden text-muted-foreground hover:text-foreground"
            >
              {mobileMenuOpen ? <X className="w-5 h-5" /> : <Menu className="w-5 h-5" />}
            </Button>
            
            <div className="md:hidden flex items-center gap-2 font-bold text-sm text-foreground">
              <Cpu className="w-4 h-4 text-primary" />
              <span>DocuMind AI</span>
            </div>

            {/* Desktop Search */}
            <div className="hidden md:flex relative items-center">
              <Search className="w-4 h-4 absolute left-3 text-muted-foreground pointer-events-none" />
              <Input
                placeholder="Search documents, entities, logs..."
                className="pl-9 h-8 w-64 text-xs bg-background/50 border-input"
              />
            </div>
          </div>

          <div className="flex items-center gap-2">
            <Button
              variant="ghost"
              size="icon"
              onClick={() => alert('No unread notifications.')}
              className="h-8 w-8 text-muted-foreground hover:text-foreground"
              title="Notifications"
            >
              <Bell className="w-4 h-4" />
            </Button>

            <Button
              variant="ghost"
              size="icon"
              onClick={() => alert('Dark theme is configured as default.')}
              className="h-8 w-8 text-muted-foreground hover:text-foreground"
              title="Dark Theme"
            >
              <Moon className="w-4 h-4" />
            </Button>

            <div className="h-4 w-px bg-border/60 mx-1"></div>

            <div
              onClick={() => setActiveScreen('Settings')}
              className="flex items-center gap-2 cursor-pointer p-1 rounded-full hover:bg-muted/40 transition-colors"
            >
              <div className="w-7 h-7 rounded-full overflow-hidden border border-border bg-muted flex items-center justify-center">
                <img
                  alt="Sarah Jenkins"
                  className="w-full h-full object-cover"
                  src="https://lh3.googleusercontent.com/aida-public/AB6AXuB0uqWAqQhiy3hgHoojSo8S7ov1aepwXy8MARwHjyel5a1dmt4DNn5dzGxypeTb_oeMUWYme8sFNWWm08gUFoIbRhnrc3_HkvT5JeGTZIBLflEXyVgtvHvu9ev-_mjx1HNE97BEIMcZZuzfewTZRAcioyTv9V1fCcnrDSp49Ggjza-xF6QLsKsVJLNMsygubBDU24kSbZ55EACUpph8ZyMCNoj2xDdelEA1pXhUIXP7Ae0LGV46uv9u"
                />
              </div>
              <span className="text-xs text-muted-foreground hidden lg:block select-none font-medium pr-1">
                Sarah Jenkins
              </span>
            </div>
          </div>
        </header>

        {/* Mobile Navigation Drawer */}
        {mobileMenuOpen && (
          <div className="md:hidden fixed inset-0 z-50 flex animate-fadeIn">
            <div className="fixed inset-0 bg-background/80 backdrop-blur-sm" onClick={() => setMobileMenuOpen(false)}></div>
            <div className="relative flex flex-col bg-card w-64 h-full p-6 border-r border-border shadow-2xl">
              <div className="flex items-center justify-between mb-6">
                <span className="font-bold text-sm text-foreground">DocuMind AI</span>
                <Button variant="ghost" size="icon" onClick={() => setMobileMenuOpen(false)} className="h-8 w-8">
                  <X className="w-4 h-4" />
                </Button>
              </div>

              <div className="flex flex-col gap-1 flex-1 overflow-y-auto">
                {['Dashboard', 'Upload', 'Processing', 'Documents', 'Analytics', 'Exports', 'Users', 'Settings', 'Help'].map((tab) => (
                  <button
                    key={tab}
                    onClick={() => {
                      setActiveScreen(tab);
                      setMobileMenuOpen(false);
                    }}
                    className={`w-full text-left py-2 px-3 rounded-md text-xs font-label-md transition-colors ${
                      activeScreen === tab ? 'bg-primary text-white font-bold' : 'text-muted-foreground hover:bg-muted/40'
                    }`}
                  >
                    {tab}
                  </button>
                ))}
              </div>

              <Button
                variant="destructive"
                size="sm"
                onClick={handleLogout}
                className="mt-auto gap-2 text-xs font-bold"
              >
                <LogOut className="w-4 h-4" />
                Logout
              </Button>
            </div>
          </div>
        )}

        {/* Active Screen Render Container */}
        <div className="flex-1 overflow-y-auto w-full flex flex-col">
          {activeScreen === 'Dashboard' && (
            <Dashboard
              onViewChange={(tab) => setActiveScreen(tab)}
            />
          )}
          {activeScreen === 'Upload' && (
            <UploadCenter onAddDocumentToQueue={handleDocumentUploaded} />
          )}
          {activeScreen === 'Processing' && (
            <ProcessingQueue
              queueItems={queueItems}
              onUpdateItem={handleUpdateQueueItem}
              onDismissItem={handleDismissItem}
            />
          )}
          {activeScreen === 'Documents' && (
            <DocumentHistory onSelectDocument={handleSelectDocument} />
          )}
          {activeScreen === 'Review' && (
            <DocumentReview
              documentId={selectedReviewDoc}
              onBack={() => setActiveScreen('Documents')}
            />
          )}
          {activeScreen === 'Analytics' && <Analytics />}
          {activeScreen === 'Exports' && <ExportCenter />}
          {activeScreen === 'Users' && <UserManagement />}
          {activeScreen === 'Settings' && <Settings />}
          {activeScreen === 'Help' && <HelpCenter />}
        </div>
      </div>
    </div>
  );
}
