import React, { useState } from 'react';
import { setAuthToken, clearAuthToken } from './api/client';
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

export default function App() {
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [view, setView] = useState('landing');
  const [activeScreen, setActiveScreen] = useState('Dashboard');
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);

  const [queueItems, setQueueItems] = useState([]);

  // Seed processed documents
  const [processedDocuments, setProcessedDocuments] = useState([
    { id: 'D-01', type: 'Invoice', customer: 'Acme Corp', ref: 'INV-2023-0891', status: 'Processed', date: '2023-10-24 14:32', score: '98.5%' },
    { id: 'D-02', type: 'Contract', customer: 'Stark Industries', ref: 'NDA-STK-002', status: 'In Review', date: '2023-10-24 11:15', score: '72.1%' },
    { id: 'D-03', type: 'Purchase Order', customer: 'Wayne Ent.', ref: 'PO-WAY-9932', status: 'Processed', date: '2023-10-23 09:45', score: '99.2%' },
    { id: 'D-04', type: 'Invoice', customer: 'Internal HR', ref: 'HR-W4-2023-EMP12', status: 'Processed', date: '2023-10-22 16:20', score: '95.0%' },
    { id: 'D-05', type: 'Invoice', customer: 'External Vendor', ref: 'ID-VND-884', status: 'Failed', date: '2023-10-22 10:05', score: '45.3%' },
  ]);

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
    setQueueItems(prev => [
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
    setActiveScreen('Processing');
  };

  const handleUpdateQueueItem = (documentId, patch) => {
    setQueueItems(prev =>
      prev.map(item => (item.document_id === documentId ? { ...item, ...patch } : item))
    );
  };

  const handleDismissItem = (documentId) => {
    setQueueItems(prev => prev.filter(item => item.document_id !== documentId));
  };

  const handleSelectDocument = (doc) => {
    setSelectedReviewDoc(doc.document_id || doc.id);
    setActiveScreen('Review');
  };

  const handleDeleteDocument = (id) => {
    setProcessedDocuments(prev => prev.filter(doc => doc.id !== id));
  };

  if (!isAuthenticated) {
    if (view === 'login') {
      return <Login onLogin={handleLogin} onBackToHome={() => setView('landing')} />;
    }
    return <LandingPage onNavigateToLogin={() => setView('login')} />;
  }

  // Get active queue length to display navigation notification badge
  const TERMINAL_STATUSES = ['complete', 'needs_review', 'failed'];
  const pendingQueueCount = queueItems.filter(item => !TERMINAL_STATUSES.includes(item.status)).length;

  return (
    <div className="dashboard-theme bg-background text-on-surface font-body-md antialiased min-h-screen flex w-full">
      {/* Sidebar Navigation (Desktop) */}
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
        
        {/* TopNavBar */}
        <header className="flex justify-between items-center px-6 sticky top-0 z-40 w-full h-16 bg-surface/60 backdrop-blur-xl border-b border-white/10 shadow-sm shrink-0">
          <div className="flex items-center gap-4">
            <button 
              onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
              className="md:hidden text-on-surface-variant hover:text-white p-2 rounded-full hover:bg-white/5 transition-colors cursor-pointer"
            >
              <span className="material-symbols-outlined">{mobileMenuOpen ? 'close' : 'menu'}</span>
            </button>
            <div className="md:hidden font-headline-md text-base font-bold text-primary">DocuMind AI</div>
            
            {/* Global Search (Desktop only) */}
            <div className="hidden md:flex relative items-center ml-2">
              <span className="material-symbols-outlined absolute left-3 text-on-surface-variant text-base">search</span>
              <input 
                className="bg-[#0F172A] border border-[#1E293B] text-on-surface rounded-full pl-9 pr-4 py-1.5 focus:outline-none focus:border-primary-container transition-all font-body-sm text-xs w-64 h-8" 
                placeholder="Search documents, entities, logs..." 
                type="text"
              />
            </div>
          </div>

          <div className="flex items-center gap-2">
            <button 
              onClick={() => alert('No new notifications.')}
              className="p-2 text-on-surface-variant hover:bg-white/5 rounded-full transition-all cursor-pointer active:scale-95 text-base"
              title="Notifications"
            >
              <span className="material-symbols-outlined text-xl">notifications</span>
            </button>
            <button 
              onClick={() => alert('Dark Theme is set by default.')}
              className="p-2 text-on-surface-variant hover:bg-white/5 rounded-full transition-all cursor-pointer active:scale-95 text-base"
              title="Dark Mode Toggle"
            >
              <span className="material-symbols-outlined text-xl">dark_mode</span>
            </button>
            <div className="h-6 w-px bg-white/10 mx-2"></div>
            
            <div className="flex items-center gap-2.5">
              <div 
                onClick={() => setActiveScreen('Settings')}
                className="w-8 h-8 rounded-full overflow-hidden border border-white/10 cursor-pointer hover:border-primary transition-all flex items-center justify-center bg-surface-container"
              >
                <img 
                  alt="Sarah Jenkins Profile" 
                  className="w-full h-full object-cover" 
                  src="https://lh3.googleusercontent.com/aida-public/AB6AXuB0uqWAqQhiy3hgHoojSo8S7ov1aepwXy8MARwHjyel5a1dmt4DNn5dzGxypeTb_oeMUWYme8sFNWWm08gUFoIbRhnrc3_HkvT5JeGTZIBLflEXyVgtvHvu9ev-_mjx1HNE97BEIMcZZuzfewTZRAcioyTv9V1fCcnrDSp49Ggjza-xF6QLsKsVJLNMsygubBDU24kSbZ55EACUpph8ZyMCNoj2xDdelEA1pXhUIXP7Ae0LGV46uv9u"
                />
              </div>
              <span className="font-label-md text-xs text-on-surface-variant hidden lg:block select-none">Sarah Jenkins</span>
            </div>
          </div>
        </header>

        {/* Mobile Navigation Drawer Overlay */}
        {mobileMenuOpen && (
          <div className="md:hidden fixed inset-0 z-50 flex animate-fadeIn">
            {/* Backdrop */}
            <div className="fixed inset-0 bg-black/60 backdrop-blur-sm" onClick={() => setMobileMenuOpen(false)}></div>
            {/* Drawer */}
            <div className="relative flex flex-col bg-[#0b1c30] w-64 h-full p-6 border-r border-white/10 animate-slideIn">
              <div className="flex items-center justify-between mb-8">
                <span className="font-headline-md text-lg font-bold text-primary">DocuMind AI</span>
                <button onClick={() => setMobileMenuOpen(false)} className="text-on-surface-variant hover:text-white">
                  <span className="material-symbols-outlined">close</span>
                </button>
              </div>
              <div className="flex flex-col gap-2 flex-1 overflow-y-auto">
                {['Dashboard', 'Upload', 'Processing', 'Documents', 'Analytics', 'Exports', 'Users', 'Settings', 'Help'].map((tab) => (
                  <button
                    key={tab}
                    onClick={() => {
                      setActiveScreen(tab);
                      setMobileMenuOpen(false);
                    }}
                    className={`w-full text-left py-2 px-3 rounded-lg text-sm transition-all ${
                      activeScreen === tab ? 'bg-primary-container text-white font-bold' : 'text-on-surface-variant hover:bg-white/5'
                    }`}
                  >
                    {tab}
                  </button>
                ))}
              </div>
              <button 
                onClick={handleLogout}
                className="mt-auto py-2.5 px-4 text-center bg-error-container/20 text-error rounded-lg text-sm border border-error/25 font-bold cursor-pointer"
              >
                Logout
              </button>
            </div>
          </div>
        )}

        {/* Active Screen Render Pane */}
        <div className="flex-1 overflow-y-auto w-full flex flex-col">
          {activeScreen === 'Dashboard' && (
            <Dashboard 
              onNavigateToUpload={() => setActiveScreen('Upload')} 
              onNavigateToQueue={() => setActiveScreen('Processing')} 
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
            <DocumentHistory 
              documents={processedDocuments} 
              onSelectDocument={handleSelectDocument} 
              onDeleteDocument={handleDeleteDocument} 
            />
          )}
          {activeScreen === 'Review' && (
            <DocumentReview
              documentId={selectedReviewDoc}
              onBack={() => setActiveScreen('Documents')}
            />
          )}
          {activeScreen === 'Analytics' && (
            <Analytics />
          )}
          {activeScreen === 'Exports' && (
            <ExportCenter />
          )}
          {activeScreen === 'Users' && (
            <UserManagement />
          )}
          {activeScreen === 'Settings' && (
            <Settings />
          )}
          {activeScreen === 'Help' && (
            <HelpCenter />
          )}
        </div>
      </div>
    </div>
  );
}
