import React, { useState } from 'react';

export default function ExportCenter() {
  const [startDate, setStartDate] = useState('2023-10-01');
  const [endDate, setEndDate] = useState('2023-10-31');
  const [exports, setExports] = useState([
    { id: 'EXP-8492', format: 'Excel', icon: 'table_view', colorClass: 'text-secondary', dateTime: '2023-10-24 14:32:01', size: '2.4 MB', status: 'Completed' },
    { id: 'EXP-8491', format: 'JSON', icon: 'code', colorClass: 'text-primary', dateTime: '2023-10-24 10:15:44', size: '856 KB', status: 'Completed' },
    { id: 'EXP-8490', format: 'PDF', icon: 'picture_as_pdf', colorClass: 'text-error', dateTime: '2023-10-23 16:45:12', size: '4.2 MB', status: 'Processing' },
    { id: 'EXP-8489', format: 'CSV', icon: 'data_object', colorClass: 'text-tertiary', dateTime: '2023-10-22 09:05:33', size: '12.1 MB', status: 'Failed' },
  ]);

  const triggerExport = (format, icon, colorClass) => {
    const newId = 'EXP-' + (Math.floor(Math.random() * 9000) + 1000);
    const newExport = {
      id: newId,
      format: format,
      icon: icon,
      colorClass: colorClass,
      dateTime: new Date().toISOString().replace('T', ' ').slice(0, 19),
      size: '-',
      status: 'Processing'
    };

    setExports(prev => [newExport, ...prev]);

    // Simulate completion
    setTimeout(() => {
      setExports(prev => 
        prev.map(item => 
          item.id === newId 
            ? { ...item, status: 'Completed', size: (Math.random() * 5 + 0.5).toFixed(1) + ' MB' }
            : item
        )
      );
    }, 3000);
  };

  const handleRetry = (id) => {
    setExports(prev => 
      prev.map(item => 
        item.id === id 
          ? { ...item, status: 'Processing', size: '-' }
          : item
      )
    );

    setTimeout(() => {
      setExports(prev => 
        prev.map(item => 
          item.id === id 
            ? { ...item, status: 'Completed', size: (Math.random() * 5 + 0.5).toFixed(1) + ' MB' }
            : item
        )
      );
    }, 2500);
  };

  return (
    <div className="flex flex-col gap-stack-lg w-full max-w-7xl mx-auto p-4 md:p-6 lg:p-10 animate-fadeIn">
      {/* Page Header */}
      <div className="flex flex-col md:flex-row justify-between items-start md:items-end gap-stack-md border-b border-white/10 pb-4">
        <div>
          <h2 className="font-headline-lg text-headline-lg-mobile md:text-headline-lg text-on-surface">Export Center</h2>
          <p className="font-body-md text-body-md text-on-surface-variant mt-2">Manage and download your extracted data intelligence.</p>
        </div>
        
        {/* Filter: Date Range */}
        <div className="flex items-center gap-2 bg-surface-container-high rounded-lg p-2 border border-white/5 text-sm">
          <span className="material-symbols-outlined text-on-surface-variant text-base">calendar_today</span>
          <input 
            className="bg-transparent border-none text-on-surface font-label-md text-xs focus:ring-0 cursor-pointer outline-none" 
            type="date" 
            value={startDate}
            onChange={(e) => setStartDate(e.target.value)}
          />
          <span className="text-on-surface-variant">-</span>
          <input 
            className="bg-transparent border-none text-on-surface font-label-md text-xs focus:ring-0 cursor-pointer outline-none" 
            type="date" 
            value={endDate}
            onChange={(e) => setEndDate(e.target.value)}
          />
        </div>
      </div>

      {/* Export Options Bento Grid */}
      <section className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-stack-md">
        
        {/* Export to Excel */}
        <button 
          onClick={() => triggerExport('Excel', 'table_view', 'text-secondary')}
          className="glass-card relative rounded-xl p-6 flex flex-col items-start gap-4 group hover:bg-white/5 transition-all text-left cursor-pointer border border-transparent hover:border-primary/30"
        >
          <div className="p-3 bg-secondary-container/20 rounded-lg text-secondary">
            <span className="material-symbols-outlined text-[32px]">table_view</span>
          </div>
          <div>
            <h3 className="font-headline-md text-headline-md text-on-surface group-hover:text-primary transition-colors">Excel</h3>
            <p className="font-body-sm text-xs text-on-surface-variant mt-1">Structured spreadsheet format (.xlsx)</p>
          </div>
          <span className="material-symbols-outlined absolute top-6 right-6 text-on-surface-variant opacity-0 group-hover:opacity-100 transition-opacity">arrow_forward</span>
        </button>

        {/* Export to CSV */}
        <button 
          onClick={() => triggerExport('CSV', 'data_object', 'text-tertiary')}
          className="glass-card relative rounded-xl p-6 flex flex-col items-start gap-4 group hover:bg-white/5 transition-all text-left cursor-pointer border border-transparent hover:border-primary/30"
        >
          <div className="p-3 bg-tertiary-container/20 rounded-lg text-tertiary">
            <span className="material-symbols-outlined text-[32px]">data_object</span>
          </div>
          <div>
            <h3 className="font-headline-md text-headline-md text-on-surface group-hover:text-tertiary transition-colors">CSV</h3>
            <p className="font-body-sm text-xs text-on-surface-variant mt-1">Comma-separated values (.csv)</p>
          </div>
          <span className="material-symbols-outlined absolute top-6 right-6 text-on-surface-variant opacity-0 group-hover:opacity-100 transition-opacity">arrow_forward</span>
        </button>

        {/* Export to JSON */}
        <button 
          onClick={() => triggerExport('JSON', 'code', 'text-primary')}
          className="glass-card relative rounded-xl p-6 flex flex-col items-start gap-4 group hover:bg-white/5 transition-all text-left cursor-pointer border border-transparent hover:border-primary/30"
        >
          <div className="p-3 bg-primary-container/20 rounded-lg text-primary">
            <span className="material-symbols-outlined text-[32px]">code</span>
          </div>
          <div>
            <h3 className="font-headline-md text-headline-md text-on-surface group-hover:text-primary transition-colors">JSON</h3>
            <p className="font-body-sm text-xs text-on-surface-variant mt-1">Raw nested data structures (.json)</p>
          </div>
          <span className="material-symbols-outlined absolute top-6 right-6 text-on-surface-variant opacity-0 group-hover:opacity-100 transition-opacity">arrow_forward</span>
        </button>

        {/* Export to PDF */}
        <button 
          onClick={() => triggerExport('PDF', 'picture_as_pdf', 'text-error')}
          className="glass-card relative rounded-xl p-6 flex flex-col items-start gap-4 group hover:bg-white/5 transition-all text-left cursor-pointer border border-transparent hover:border-error/30"
        >
          <div className="p-3 bg-error-container/20 rounded-lg text-error">
            <span className="material-symbols-outlined text-[32px]">picture_as_pdf</span>
          </div>
          <div>
            <h3 className="font-headline-md text-headline-md text-on-surface group-hover:text-error transition-colors">PDF</h3>
            <p className="font-body-sm text-xs text-on-surface-variant mt-1">Formatted summary report (.pdf)</p>
          </div>
          <span className="material-symbols-outlined absolute top-6 right-6 text-on-surface-variant opacity-0 group-hover:opacity-100 transition-opacity">arrow_forward</span>
        </button>
      </section>

      {/* History Table */}
      <section className="glass-card rounded-xl overflow-hidden relative">
        <div className="px-6 py-4 border-b border-white/10 flex justify-between items-center bg-surface-container-low/50">
          <h3 className="font-headline-md text-headline-md text-on-surface text-lg">Recent Exports</h3>
          <span className="text-on-surface-variant font-label-md text-xs">Exports Log</span>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-left border-collapse">
            <thead>
              <tr className="bg-surface-container/30 border-b border-white/5 font-label-md text-xs text-on-surface-variant">
                <th className="px-6 py-3 font-medium">Export ID</th>
                <th className="px-6 py-3 font-medium">Format</th>
                <th className="px-6 py-3 font-medium">Date / Time</th>
                <th className="px-6 py-3 font-medium">Size</th>
                <th className="px-6 py-3 font-medium">Status</th>
                <th className="px-6 py-3 font-medium text-right">Action</th>
              </tr>
            </thead>
            <tbody className="font-body-sm text-sm text-on-surface divide-y divide-white/5">
              {exports.map((item) => (
                <tr key={item.id} className="hover:bg-white/[0.02] transition-colors">
                  <td className="px-6 py-3.5 font-label-md text-primary text-xs">{item.id}</td>
                  <td className="px-6 py-3.5 flex items-center gap-2">
                    <span className={`material-symbols-outlined ${item.colorClass} text-base`}>{item.icon}</span> 
                    <span className="font-semibold">{item.format}</span>
                  </td>
                  <td className="px-6 py-3.5 font-label-md text-on-surface-variant text-xs">{item.dateTime}</td>
                  <td className="px-6 py-3.5 font-label-md text-xs">{item.size}</td>
                  <td className="px-6 py-3.5">
                    <span className={`inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded text-[11px] font-label-md ${
                      item.status === 'Completed'
                        ? 'bg-green-500/10 text-green-400'
                        : item.status === 'Processing'
                        ? 'bg-yellow-500/10 text-yellow-400'
                        : 'bg-error-container/20 text-error'
                    }`}>
                      <span className={`w-1.5 h-1.5 rounded-full ${
                        item.status === 'Completed' ? 'bg-green-400' : item.status === 'Processing' ? 'bg-yellow-400 animate-pulse' : 'bg-error'
                      }`}></span> 
                      {item.status}
                    </span>
                  </td>
                  <td className="px-6 py-3.5 text-right">
                    {item.status === 'Completed' ? (
                      <a 
                        className="text-primary hover:text-primary-fixed transition-colors font-label-md text-xs font-semibold" 
                        href={`#download-${item.id}`}
                        onClick={(e) => {
                          e.preventDefault();
                          alert(`Downloading ${item.format} file (${item.size})...`);
                        }}
                      >
                        Download
                      </a>
                    ) : item.status === 'Failed' ? (
                      <button 
                        onClick={() => handleRetry(item.id)}
                        className="text-primary hover:underline transition-colors font-label-md text-xs font-semibold cursor-pointer"
                      >
                        Retry
                      </button>
                    ) : (
                      <span className="text-on-surface-variant font-label-md text-xs cursor-not-allowed">Processing</span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  );
}
