import React, { useState } from 'react';

export default function Settings() {
  const [activeTab, setActiveTab] = useState('Integrations');
  const [awsActive, setAwsActive] = useState(true);
  const [azureActive, setAzureActive] = useState(false);
  const [openaiActive, setOpenaiActive] = useState(true);
  const [gcpActive, setGcpActive] = useState(false);
  
  // API Keys state
  const [apiKeys, setApiKeys] = useState([
    { id: 1, name: 'Production Server Key', key: 'dm_live_••••••••••••••••3a9c', created: '2023-08-12', status: 'Active' },
    { id: 2, name: 'Staging Development Key', key: 'dm_test_••••••••••••••••92fb', created: '2023-09-05', status: 'Active' }
  ]);
  const [showNewKeyAlert, setShowNewKeyAlert] = useState('');

  const generateApiKey = () => {
    const chars = 'abcdefghijklmnopqrstuvwxyz0123456789';
    let randomStr = '';
    for (let i = 0; i < 24; i++) {
      randomStr += chars[Math.floor(Math.random() * chars.length)];
    }
    const newRawKey = `dm_live_${randomStr}`;
    const maskedKey = `${newRawKey.slice(0, 10)}••••••••••••••••${newRawKey.slice(-4)}`;
    
    const newKeyItem = {
      id: Date.now(),
      name: 'Generated Custom Key',
      key: maskedKey,
      created: new Date().toISOString().slice(0, 10),
      status: 'Active'
    };

    setApiKeys(prev => [...prev, newKeyItem]);
    setShowNewKeyAlert(newRawKey);
  };

  const tabs = [
    { id: 'Profile', icon: 'person', label: 'Profile' },
    { id: 'Notifications', icon: 'notifications_active', label: 'Notifications' },
    { id: 'Security', icon: 'security', label: 'Security' },
    { id: 'API Keys', icon: 'key', label: 'API Keys' },
    { id: 'Integrations', icon: 'integration_instructions', label: 'Integrations' },
    { id: 'Organization', icon: 'domain', label: 'Organization' },
  ];

  return (
    <div className="flex flex-col gap-stack-lg w-full max-w-7xl mx-auto p-4 md:p-6 lg:p-10 animate-fadeIn">
      {/* Header section */}
      <div className="flex flex-col gap-stack-sm mb-2">
        <h2 className="font-display-lg text-headline-lg text-white font-bold">Settings</h2>
        <p className="font-body-lg text-body-lg text-on-surface-variant">
          Manage your enterprise intelligence platform preferences.
        </p>
      </div>

      <div className="flex flex-col lg:flex-row gap-stack-lg flex-1">
        {/* Settings Sidebar Tabs */}
        <div className="w-full lg:w-64 flex-shrink-0">
          <div className="glass-card rounded-xl overflow-hidden flex flex-col p-2 gap-1">
            {tabs.map((tab) => (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id)}
                className={`font-body-md text-sm px-4 py-3 rounded-lg flex items-center gap-3 transition-colors cursor-pointer w-full text-left ${
                  activeTab === tab.id
                    ? 'text-primary font-bold bg-primary-dark/20 border-l-2 border-primary'
                    : 'text-on-surface-variant hover:bg-white/5'
                }`}
              >
                <span className="material-symbols-outlined text-lg">{tab.icon}</span>
                {tab.label}
              </button>
            ))}
          </div>
        </div>

        {/* Settings Content Area */}
        <div className="flex-1 space-y-stack-md">
          {activeTab === 'Integrations' && (
            <div className="glass-card rounded-xl p-6">
              <div className="mb-6">
                <h3 className="font-headline-md text-lg text-white font-semibold">Cloud & AI Integrations</h3>
                <p className="font-body-sm text-xs text-on-surface-variant mt-1">
                  Connect DocuMind AI to your external infrastructure and compute providers.
                </p>
              </div>

              <div className="space-y-4">
                {/* AWS */}
                <div className="flex items-center justify-between p-4 bg-surface-container rounded-lg border border-outline-variant hover:border-primary/50 transition-colors">
                  <div className="flex items-center gap-4">
                    <div className="w-10 h-10 rounded bg-white/5 flex items-center justify-center border border-white/10 text-primary">
                      <span className="material-symbols-outlined">cloud</span>
                    </div>
                    <div>
                      <h4 className="font-body-md font-semibold text-white text-sm">Amazon Web Services (AWS)</h4>
                      <p className="font-body-sm text-xs text-on-surface-variant">Connect S3 buckets for document ingestion.</p>
                    </div>
                  </div>
                  <button 
                    onClick={() => setAwsActive(!awsActive)}
                    className={`w-12 h-6 rounded-full p-1 transition-colors cursor-pointer ${awsActive ? 'bg-primary' : 'bg-outline-variant'}`}
                  >
                    <div className={`w-4 h-4 rounded-full bg-white transition-transform ${awsActive ? 'translate-x-6' : 'translate-x-0'}`}></div>
                  </button>
                </div>

                {/* Azure */}
                <div className="flex items-center justify-between p-4 bg-surface-container rounded-lg border border-outline-variant hover:border-primary/50 transition-colors">
                  <div className="flex items-center gap-4">
                    <div className="w-10 h-10 rounded bg-white/5 flex items-center justify-center border border-white/10 text-primary">
                      <span className="material-symbols-outlined">window</span>
                    </div>
                    <div>
                      <h4 className="font-body-md font-semibold text-white text-sm">Microsoft Azure</h4>
                      <p className="font-body-sm text-xs text-on-surface-variant">Sync with Azure Blob Storage.</p>
                    </div>
                  </div>
                  <button 
                    onClick={() => setAzureActive(!azureActive)}
                    className={`w-12 h-6 rounded-full p-1 transition-colors cursor-pointer ${azureActive ? 'bg-primary' : 'bg-outline-variant'}`}
                  >
                    <div className={`w-4 h-4 rounded-full bg-white transition-transform ${azureActive ? 'translate-x-6' : 'translate-x-0'}`}></div>
                  </button>
                </div>

                {/* OpenAI */}
                <div className="flex items-center justify-between p-4 bg-surface-container rounded-lg border border-outline-variant hover:border-primary/50 transition-colors">
                  <div className="flex items-center gap-4">
                    <div className="w-10 h-10 rounded bg-white/5 flex items-center justify-center border border-white/10 text-primary">
                      <span className="material-symbols-outlined">psychology</span>
                    </div>
                    <div>
                      <h4 className="font-body-md font-semibold text-white text-sm">OpenAI</h4>
                      <p className="font-body-sm text-xs text-on-surface-variant">Enable advanced LLM document parsing.</p>
                    </div>
                  </div>
                  <button 
                    onClick={() => setOpenaiActive(!openaiActive)}
                    className={`w-12 h-6 rounded-full p-1 transition-colors cursor-pointer ${openaiActive ? 'bg-primary' : 'bg-outline-variant'}`}
                  >
                    <div className={`w-4 h-4 rounded-full bg-white transition-transform ${openaiActive ? 'translate-x-6' : 'translate-x-0'}`}></div>
                  </button>
                </div>

                {/* Google Cloud */}
                <div className="flex items-center justify-between p-4 bg-surface-container rounded-lg border border-outline-variant hover:border-primary/50 transition-colors">
                  <div className="flex items-center gap-4">
                    <div className="w-10 h-10 rounded bg-white/5 flex items-center justify-center border border-white/10 text-primary">
                      <span className="material-symbols-outlined">backup</span>
                    </div>
                    <div>
                      <h4 className="font-body-md font-semibold text-white text-sm">Google Cloud Platform (GCP)</h4>
                      <p className="font-body-sm text-xs text-on-surface-variant">Connect GCP buckets and Vision API.</p>
                    </div>
                  </div>
                  <button 
                    onClick={() => setGcpActive(!gcpActive)}
                    className={`w-12 h-6 rounded-full p-1 transition-colors cursor-pointer ${gcpActive ? 'bg-primary' : 'bg-outline-variant'}`}
                  >
                    <div className={`w-4 h-4 rounded-full bg-white transition-transform ${gcpActive ? 'translate-x-6' : 'translate-x-0'}`}></div>
                  </button>
                </div>
              </div>

              <div className="mt-8 pt-6 border-t border-white/10 flex justify-end">
                <button 
                  onClick={() => alert('Settings saved successfully!')}
                  className="bg-primary hover:bg-primary-dark text-white font-label-md text-xs py-2.5 px-6 rounded-lg shadow-lg hover:shadow-primary/20 transition-all flex items-center gap-2 cursor-pointer font-bold border-none"
                >
                  <span className="material-symbols-outlined text-base">save</span>
                  Save Changes
                </button>
              </div>
            </div>
          )}

          {activeTab === 'API Keys' && (
            <div className="glass-card rounded-xl p-6 flex flex-col gap-6">
              <div>
                <div className="flex justify-between items-start">
                  <div>
                    <h3 className="font-headline-md text-lg text-white font-semibold">API Credentials</h3>
                    <p className="font-body-sm text-xs text-on-surface-variant mt-1">
                      Manage secret keys to integrate DocuMind AI services in your custom backend.
                    </p>
                  </div>
                  <button 
                    onClick={generateApiKey}
                    className="py-2 px-4 rounded bg-primary hover:bg-primary-dark text-white font-label-md text-xs font-semibold cursor-pointer transition-all border-none"
                  >
                    + Create API Key
                  </button>
                </div>
                
                {showNewKeyAlert && (
                  <div className="mt-4 p-4 bg-primary/10 border border-primary-light/50 text-white rounded-lg flex flex-col gap-2 animate-scaleUp">
                    <span className="font-body-sm text-xs font-bold uppercase text-primary-light">Key Created successfully!</span>
                    <span className="font-body-sm text-xs">Copy this key now. For security reasons, you will not be able to see it again.</span>
                    <div className="flex items-center justify-between bg-black/40 p-2 rounded border border-white/10 mt-1 font-label-md text-sm text-white">
                      <span>{showNewKeyAlert}</span>
                      <button 
                        onClick={() => {
                          navigator.clipboard.writeText(showNewKeyAlert);
                          alert('Copied to clipboard!');
                        }}
                        className="text-primary hover:text-white transition-colors cursor-pointer text-xs"
                      >
                        Copy
                      </button>
                    </div>
                  </div>
                )}
              </div>

              <div className="overflow-x-auto border border-white/5 rounded-lg">
                <table className="w-full text-left border-collapse">
                  <thead>
                    <tr className="bg-surface-container/30 border-b border-white/10 font-label-md text-xs text-on-surface-variant">
                      <th className="px-4 py-3">Key Name</th>
                      <th className="px-4 py-3">Secret Key</th>
                      <th className="px-4 py-3">Created</th>
                      <th className="px-4 py-3">Status</th>
                      <th className="px-4 py-3 text-right">Action</th>
                    </tr>
                  </thead>
                  <tbody className="font-body-sm text-sm text-on-surface divide-y divide-white/5">
                    {apiKeys.map((item) => (
                      <tr key={item.id}>
                        <td className="px-4 py-3 font-semibold text-white">{item.name}</td>
                        <td className="px-4 py-3 font-label-md text-xs text-on-surface-variant">{item.key}</td>
                        <td className="px-4 py-3 font-label-md text-xs text-on-surface-variant">{item.created}</td>
                        <td className="px-4 py-3">
                          <span className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded bg-green-500/10 text-green-400 font-label-md text-xs">
                            <span className="w-1 h-1 rounded-full bg-green-400"></span> Active
                          </span>
                        </td>
                        <td className="px-4 py-3 text-right">
                          <button 
                            onClick={() => setApiKeys(prev => prev.filter(k => k.id !== item.id))}
                            className="text-on-surface-variant hover:text-error transition-colors font-label-md text-xs font-semibold cursor-pointer"
                          >
                            Revoke
                          </button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {activeTab !== 'Integrations' && activeTab !== 'API Keys' && (
            <div className="glass-card rounded-xl p-6 text-center py-20">
              <span className="material-symbols-outlined text-4xl text-on-surface-variant mb-4">construction</span>
              <h3 className="font-headline-md text-lg text-white font-semibold">Tab Under Construction</h3>
              <p className="font-body-sm text-xs text-on-surface-variant mt-1">
                The {activeTab} settings section is currently being wired up in our workspace.
              </p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
