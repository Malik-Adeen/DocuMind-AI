import React, { useState } from 'react';

export default function UserManagement() {
  const [users, setUsers] = useState([
    { id: 1, name: 'Sarah Jenkins', email: 'sarah.j@techcorp.com', role: 'Admin', org: 'TechCorp Global', lastActive: '2023-10-24 14:32:01', initials: 'SJ', avatar: 'https://lh3.googleusercontent.com/aida-public/AB6AXuAxCWWGlcAAsZ6u8lnUfIgHNs3nRgq3bes39otP7kzBQZqtj3o4nfIHJZCRJa4jSPm-GoMYw4cZbQShv41rUkxXUgMx3GAzmXecCKsVhh8z6qbf4Ci-gh1cMm9a1rfk6wEeURFcnbmSHh2JOIJ_YlrxqRx575k6THcdNPpZBwZtifc5BkRtJM1-2cOzBzia-zeRAR8-pWMeocOYGJVoWJYijF_jZCF1mf36w3ekaiAu_RiMMlW22dnH' },
    { id: 2, name: 'Marcus Chen', email: 'm.chen@novadynamics.io', role: 'Editor', org: 'Nova Dynamics', lastActive: '2023-10-24 09:15:44', initials: 'MC', avatar: 'https://lh3.googleusercontent.com/aida-public/AB6AXuABdL-Sn1Aj-vcf96TretHPeylNKVmOGBqDu2MjeCbt7hdNQPM2-0oHZ6xPxzaBU99hpyPh_ehklxoXd1kZRtN8a4uVQ9wTUHmEPbotokDyr5AqdiRQohwCrUDyHa_wrPXbgTFtqCjIpASK736H7RcieJfh4gUsIdS9uLFxXCQP0KmJpc-iCIBJkDJOpiHQYZmR0ruMSC45ltu9T7n0ATrRpGyOC4LZpRuUu6umyZlFmOQeFKrFFXfu' },
    { id: 3, name: 'Elena Rostova', email: 'elena.r@quantum.eu', role: 'Viewer', org: 'Quantum EU', lastActive: '2023-10-23 18:05:12', initials: 'ER', avatar: '' },
    { id: 4, name: 'David Wright', email: 'david.w@techcorp.com', role: 'Viewer', org: 'TechCorp Global', lastActive: '--', initials: 'DW', avatar: '', pending: true },
  ]);

  const [searchTerm, setSearchTerm] = useState('');
  const [showInviteModal, setShowInviteModal] = useState(false);
  const [inviteName, setInviteName] = useState('');
  const [inviteEmail, setInviteEmail] = useState('');
  const [inviteRole, setInviteRole] = useState('Viewer');
  const [inviteOrg, setInviteOrg] = useState('TechCorp Global');

  const filteredUsers = users.filter(user =>
    user.name.toLowerCase().includes(searchTerm.toLowerCase()) ||
    user.email.toLowerCase().includes(searchTerm.toLowerCase()) ||
    user.org.toLowerCase().includes(searchTerm.toLowerCase())
  );

  const handleInviteSubmit = (e) => {
    e.preventDefault();
    if (!inviteName || !inviteEmail) return;

    const newUser = {
      id: Date.now(),
      name: inviteName,
      email: inviteEmail,
      role: inviteRole,
      org: inviteOrg,
      lastActive: '--',
      initials: inviteName.split(' ').map(n => n[0]).join('').toUpperCase().slice(0, 2),
      avatar: '',
      pending: true
    };

    setUsers(prev => [...prev, newUser]);
    setShowInviteModal(false);
    setInviteName('');
    setInviteEmail('');
  };

  const handleRevokeAccess = (id) => {
    setUsers(prev => prev.filter(user => user.id !== id));
  };

  return (
    <div className="flex flex-col gap-stack-lg w-full max-w-7xl mx-auto p-4 md:p-6 lg:p-10 animate-fadeIn">
      {/* Header Actions */}
      <div className="flex flex-col sm:flex-row justify-between items-start sm:items-end gap-4 mb-2">
        <div>
          <h2 className="font-headline-lg text-headline-lg text-on-surface mb-2 tracking-tight">User Management</h2>
          <p className="font-body-md text-body-md text-on-surface-variant">
            Manage organization members, assign roles, and control access permissions across the platform.
          </p>
        </div>
        <div className="flex items-center gap-3 w-full sm:w-auto">
          <div className="relative flex-1 sm:flex-initial">
            <span className="material-symbols-outlined absolute left-3 top-1/2 -translate-y-1/2 text-on-surface-variant text-base">search</span>
            <input 
              className="w-full sm:w-60 bg-surface-variant border border-outline-variant text-on-surface rounded-lg py-2 pl-9 pr-4 text-xs focus:outline-none focus:border-primary transition-all" 
              placeholder="Search users, roles..." 
              type="text"
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
            />
          </div>
          <button 
            onClick={() => setShowInviteModal(true)}
            className="flex items-center gap-2 bg-primary hover:bg-primary-dark text-white px-4 py-2 rounded-lg shadow-md hover:shadow-primary/20 transition-all font-label-md text-xs cursor-pointer border-none"
          >
            <span className="material-symbols-outlined text-base">person_add</span>
            Invite User
          </button>
        </div>
      </div>

      {/* Stats Row */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-stack-md">
        <div className="glass-card rounded-xl p-6 relative overflow-hidden group">
          <div className="absolute top-0 right-0 w-32 h-32 bg-primary-container/15 rounded-full blur-3xl -mr-10 -mt-10 transition-transform group-hover:scale-110"></div>
          <div className="relative z-10 flex flex-col h-full justify-between">
            <div className="flex items-center justify-between mb-4">
              <span className="font-label-md text-xs text-on-surface-variant uppercase tracking-wider">Total Users</span>
              <span className="material-symbols-outlined text-primary text-xl">group</span>
            </div>
            <div className="flex items-baseline gap-2">
              <span className="font-display-lg text-3xl font-bold text-on-surface">{users.length}</span>
              <span className="text-emerald-400 font-label-md text-xs flex items-center">
                <span className="material-symbols-outlined text-xs">arrow_upward</span> 12%
              </span>
            </div>
          </div>
        </div>
        <div className="glass-card rounded-xl p-6 relative overflow-hidden group">
          <div className="absolute top-0 right-0 w-32 h-32 bg-secondary-container/15 rounded-full blur-3xl -mr-10 -mt-10 transition-transform group-hover:scale-110"></div>
          <div className="relative z-10 flex flex-col h-full justify-between">
            <div className="flex items-center justify-between mb-4">
              <span className="font-label-md text-xs text-on-surface-variant uppercase tracking-wider">Active Today</span>
              <span className="material-symbols-outlined text-secondary text-xl font-bold">vital_signs</span>
            </div>
            <div className="flex items-baseline gap-2">
              <span className="font-display-lg text-3xl font-bold text-on-surface">
                {users.filter(u => !u.pending).length}
              </span>
              <span className="text-on-surface-variant font-label-md text-xs">/ 85% activity</span>
            </div>
          </div>
        </div>
        <div className="glass-card rounded-xl p-6 relative overflow-hidden group">
          <div className="absolute top-0 right-0 w-32 h-32 bg-error-container/15 rounded-full blur-3xl -mr-10 -mt-10 transition-transform group-hover:scale-110"></div>
          <div className="relative z-10 flex flex-col h-full justify-between">
            <div className="flex items-center justify-between mb-4">
              <span className="font-label-md text-xs text-on-surface-variant uppercase tracking-wider">Pending Invites</span>
              <span className="material-symbols-outlined text-error text-xl">mark_email_unread</span>
            </div>
            <div className="flex items-baseline gap-2">
              <span className="font-display-lg text-3xl font-bold text-on-surface">
                {users.filter(u => u.pending).length}
              </span>
              <span className="text-error font-label-md text-xs">Requires action</span>
            </div>
          </div>
        </div>
      </div>

      {/* Main Table Area */}
      <div className="glass-card rounded-xl flex flex-col min-h-[400px] relative overflow-hidden">
        {/* Table Header */}
        <div className="grid grid-cols-12 gap-4 px-6 py-4 border-b border-[#1E293B] font-label-md text-xs text-on-surface-variant bg-surface-container-low/50 sticky top-0 z-10">
          <div className="col-span-5 md:col-span-4 flex items-center">User</div>
          <div className="col-span-3 md:col-span-2 flex items-center">Role</div>
          <div className="col-span-4 md:col-span-3 flex items-center">Organization</div>
          <div className="hidden md:col-span-2 md:flex items-center justify-end pr-8">Last Active</div>
          <div className="col-span-1 flex items-center justify-end">Actions</div>
        </div>

        {/* Table Body */}
        <div className="flex-1 overflow-y-auto divide-y divide-white/5 font-body-sm text-sm">
          {filteredUsers.map((user) => (
            <div key={user.id} className="grid grid-cols-12 gap-4 px-6 py-3.5 hover:bg-white/[0.02] transition-colors items-center">
              <div className="col-span-5 md:col-span-4 flex items-center gap-3">
                <div className="w-10 h-10 rounded-full overflow-hidden border border-[#1E293B] flex items-center justify-center bg-surface-container-highest text-primary font-bold">
                  {user.avatar ? (
                    <img alt={user.name} className="w-full h-full object-cover" src={user.avatar}/>
                  ) : (
                    <span>{user.initials}</span>
                  )}
                </div>
                <div className="flex flex-col min-w-0 pr-2">
                  <span className={`font-semibold truncate ${user.pending ? 'text-on-surface-variant italic' : 'text-white'}`}>
                    {user.name} {user.pending && '(Pending)'}
                  </span>
                  <span className="font-label-md text-[11px] text-on-surface-variant truncate">{user.email}</span>
                </div>
              </div>
              
              <div className="col-span-3 md:col-span-2 flex items-center">
                <span className={`inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full border font-label-md text-[10px] ${
                  user.role === 'Admin' 
                    ? 'bg-primary-container/20 text-primary border-primary/30' 
                    : user.role === 'Editor' 
                    ? 'bg-secondary-container/20 text-secondary border-secondary/30' 
                    : 'bg-surface-variant text-on-surface-variant border-outline-variant'
                }`}>
                  <span className={`w-1 h-1 rounded-full ${user.role === 'Admin' ? 'bg-primary' : user.role === 'Editor' ? 'bg-secondary' : 'bg-outline'}`}></span>
                  {user.role}
                </span>
              </div>
              
              <div className="col-span-4 md:col-span-3 flex items-center text-on-surface-variant">
                {user.org}
              </div>
              
              <div className="hidden md:col-span-2 md:flex items-center justify-end pr-8 font-label-md text-on-surface-variant text-xs">
                {user.lastActive}
              </div>
              
              <div className="col-span-1 flex items-center justify-end">
                <button 
                  onClick={() => handleRevokeAccess(user.id)}
                  className="text-on-surface-variant hover:text-error hover:bg-error/10 p-1.5 rounded transition-colors cursor-pointer"
                  title="Revoke / Delete User"
                >
                  <span className="material-symbols-outlined text-base">delete</span>
                </button>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Invite User Modal */}
      {showInviteModal && (
        <div className="fixed inset-0 bg-black/60 backdrop-blur-sm z-[100] flex items-center justify-center p-4">
          <div className="glass-card max-w-md w-full rounded-xl p-6 relative overflow-hidden flex flex-col gap-4 animate-scaleUp border border-white/10 shadow-2xl">
            <div className="flex justify-between items-center border-b border-white/10 pb-3">
              <h3 className="font-headline-md text-lg text-white font-bold flex items-center gap-2">
                <span className="material-symbols-outlined text-primary">person_add</span>
                Invite New User
              </h3>
              <button 
                onClick={() => setShowInviteModal(false)}
                className="text-on-surface-variant hover:text-white transition-colors cursor-pointer"
              >
                <span className="material-symbols-outlined">close</span>
              </button>
            </div>
            
            <form onSubmit={handleInviteSubmit} className="flex flex-col gap-4">
              <div className="flex flex-col gap-1">
                <label className="font-label-md text-xs text-on-surface-variant uppercase tracking-wider">Full Name</label>
                <input 
                  type="text" 
                  value={inviteName}
                  onChange={(e) => setInviteName(e.target.value)}
                  placeholder="e.g. John Doe"
                  required
                  className="bg-surface-variant border border-outline-variant rounded-lg py-2.5 px-3.5 text-sm text-on-surface focus:outline-none focus:border-primary"
                />
              </div>

              <div className="flex flex-col gap-1">
                <label className="font-label-md text-xs text-on-surface-variant uppercase tracking-wider">Email Address</label>
                <input 
                  type="email" 
                  value={inviteEmail}
                  onChange={(e) => setInviteEmail(e.target.value)}
                  placeholder="e.g. john@company.com"
                  required
                  className="bg-surface-variant border border-outline-variant rounded-lg py-2.5 px-3.5 text-sm text-on-surface focus:outline-none focus:border-primary"
                />
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div className="flex flex-col gap-1">
                  <label className="font-label-md text-xs text-on-surface-variant uppercase tracking-wider">Access Role</label>
                  <select 
                    value={inviteRole}
                    onChange={(e) => setInviteRole(e.target.value)}
                    className="bg-surface-variant border border-outline-variant rounded-lg py-2 px-3 text-sm text-on-surface focus:outline-none focus:border-primary"
                  >
                    <option value="Admin">Admin</option>
                    <option value="Editor">Editor</option>
                    <option value="Viewer">Viewer</option>
                  </select>
                </div>
                
                <div className="flex flex-col gap-1">
                  <label className="font-label-md text-xs text-on-surface-variant uppercase tracking-wider">Organization</label>
                  <select 
                    value={inviteOrg}
                    onChange={(e) => setInviteOrg(e.target.value)}
                    className="bg-surface-variant border border-outline-variant rounded-lg py-2 px-3 text-sm text-on-surface focus:outline-none focus:border-primary"
                  >
                    <option value="TechCorp Global">TechCorp Global</option>
                    <option value="Nova Dynamics">Nova Dynamics</option>
                    <option value="Quantum EU">Quantum EU</option>
                  </select>
                </div>
              </div>

              <div className="flex gap-3 mt-4 border-t border-white/5 pt-4">
                <button 
                  type="button"
                  onClick={() => setShowInviteModal(false)}
                  className="flex-1 py-2 px-4 border border-outline-variant hover:bg-white/5 rounded-lg text-sm text-on-surface cursor-pointer"
                >
                  Cancel
                </button>
                <button 
                  type="submit"
                  className="flex-1 py-2 px-4 bg-primary hover:bg-primary-dark text-white font-bold rounded-lg text-sm cursor-pointer hover:shadow-lg hover:shadow-primary/20 transition-all border-none"
                >
                  Send Invitation
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
