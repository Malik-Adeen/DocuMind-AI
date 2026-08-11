import React, { useState } from 'react';

export default function DocumentHistory({ documents, onSelectDocument, onDeleteDocument }) {
  const [searchTerm, setSearchTerm] = useState('');
  const [pageSize, setPageSize] = useState(10);
  const [currentPage, setCurrentPage] = useState(1);

  const filteredDocs = documents.filter(doc =>
    (doc.name && doc.name.toLowerCase().includes(searchTerm.toLowerCase())) ||
    (doc.type && doc.type.toLowerCase().includes(searchTerm.toLowerCase())) ||
    (doc.customer && doc.customer.toLowerCase().includes(searchTerm.toLowerCase())) ||
    (doc.ref && doc.ref.toLowerCase().includes(searchTerm.toLowerCase()))
  );

  const totalPages = Math.ceil(filteredDocs.length / pageSize) || 1;
  const startIndex = (currentPage - 1) * pageSize;
  const paginatedDocs = filteredDocs.slice(startIndex, startIndex + pageSize);

  return (
    <div className="flex flex-col gap-stack-lg w-full max-w-7xl mx-auto p-4 md:p-6 lg:p-10 animate-fadeIn">
      {/* Header Section */}
      <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4 mb-2">
        <div>
          <h2 className="font-headline-lg text-headline-lg text-on-surface mb-1">Document History</h2>
          <p className="font-body-sm text-body-sm text-on-surface-variant">Review and manage processed enterprise documents.</p>
        </div>
        <div className="flex items-center gap-3 w-full sm:w-auto">
          <div className="relative flex-1 sm:flex-initial">
            <span className="material-symbols-outlined absolute left-3 top-1/2 -translate-y-1/2 text-outline text-base">search</span>
            <input 
              className="w-full sm:w-64 bg-surface border border-outline-variant rounded-lg py-2 pl-9 pr-4 text-xs text-on-surface focus:outline-none focus:border-primary transition-all" 
              placeholder="Search by name, client, ID..." 
              type="text"
              value={searchTerm}
              onChange={(e) => {
                setSearchTerm(e.target.value);
                setCurrentPage(1);
              }}
            />
          </div>
        </div>
      </div>

      {/* Data Table Container */}
      <div className="glass-card rounded-xl overflow-hidden flex flex-col">
        <div className="overflow-x-auto">
          <table className="w-full text-left border-collapse min-w-[800px]">
            <thead>
              <tr className="border-b border-white/10 bg-surface/30 font-label-md text-xs text-on-surface-variant font-medium">
                <th className="py-3 px-6">Doc Type</th>
                <th className="py-3 px-6">Client / Customer</th>
                <th className="py-3 px-6">Ref Number</th>
                <th className="py-3 px-6">Status</th>
                <th className="py-3 px-6">Processed Date</th>
                <th className="py-3 px-6 text-right">Confidence %</th>
                <th className="py-3 px-6 text-right">Actions</th>
              </tr>
            </thead>
            <tbody className="font-body-sm text-sm divide-y divide-white/5">
              {paginatedDocs.length === 0 ? (
                <tr>
                  <td colSpan="7" className="py-12 px-6 text-center text-on-surface-variant font-body-md">
                    No documents found.
                  </td>
                </tr>
              ) : (
                paginatedDocs.map((doc) => (
                  <tr 
                    key={doc.id} 
                    onClick={() => onSelectDocument(doc)}
                    className="hover:bg-white/[0.02] transition-colors cursor-pointer group"
                  >
                    <td className="py-4 px-6">
                      <div className="flex items-center gap-2">
                        <span className="material-symbols-outlined text-outline-variant text-lg">
                          {doc.type === 'Invoice' ? 'receipt_long' : doc.type === 'Contract' ? 'contract' : 'description'}
                        </span>
                        <span className="font-semibold text-white">{doc.type}</span>
                      </div>
                    </td>
                    <td className="py-4 px-6 text-on-surface">{doc.customer}</td>
                    <td className="py-4 px-6 font-label-md text-outline text-xs">{doc.ref}</td>
                    <td className="py-4 px-6">
                      <span className={`inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full border font-label-md text-[11px] ${
                        doc.status === 'Processed'
                          ? 'bg-secondary-container/20 text-secondary border-secondary-container/30'
                          : doc.status === 'In Review'
                          ? 'bg-tertiary-container/20 text-tertiary border-tertiary-container/30'
                          : 'bg-error-container/20 text-error border-error-container/30'
                      }`}>
                        <span className={`w-1.5 h-1.5 rounded-full ${
                          doc.status === 'Processed' ? 'bg-secondary' : doc.status === 'In Review' ? 'bg-tertiary' : 'bg-error'
                        }`}></span>
                        {doc.status === 'Processed' ? 'Success' : doc.status === 'In Review' ? 'Warning' : 'Failed'}
                      </span>
                    </td>
                    <td className="py-4 px-6 font-label-md text-on-surface-variant text-xs">{doc.date}</td>
                    <td className={`py-4 px-6 text-right font-label-md ${doc.score.startsWith('4') || doc.score.startsWith('5') ? 'text-error' : 'text-primary'}`}>
                      {doc.score}
                    </td>
                    <td className="py-4 px-6 text-right" onClick={(e) => e.stopPropagation()}>
                      <div className="flex justify-end gap-2 text-outline-variant">
                        <button 
                          onClick={() => onSelectDocument(doc)} 
                          className="hover:text-primary p-1 rounded hover:bg-white/5 transition-colors cursor-pointer" 
                          title="View / Review"
                        >
                          <span className="material-symbols-outlined text-base">visibility</span>
                        </button>
                        <button 
                          onClick={() => onDeleteDocument(doc.id)} 
                          className="hover:text-error p-1 rounded hover:bg-white/5 transition-colors cursor-pointer" 
                          title="Delete"
                        >
                          <span className="material-symbols-outlined text-base">delete</span>
                        </button>
                      </div>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>

        {/* Pagination Footer */}
        <div className="bg-surface/50 border-t border-white/10 px-6 py-4 flex flex-col sm:flex-row justify-between items-center gap-4">
          <div className="flex items-center gap-2">
            <span className="font-body-sm text-xs text-on-surface-variant">Show</span>
            <select 
              value={pageSize}
              onChange={(e) => {
                setPageSize(Number(e.target.value));
                setCurrentPage(1);
              }}
              className="bg-surface border border-outline-variant text-on-surface font-label-md text-xs rounded-md py-1 px-2.5 pr-8 focus:outline-none focus:border-primary"
            >
              <option value={5}>5</option>
              <option value={10}>10</option>
              <option value={20}>20</option>
            </select>
            <span className="font-body-sm text-xs text-on-surface-variant">per page</span>
          </div>
          <div className="flex items-center gap-4">
            <span className="font-body-sm text-xs text-on-surface-variant">
              {filteredDocs.length === 0 ? 0 : startIndex + 1}-{Math.min(startIndex + pageSize, filteredDocs.length)} of {filteredDocs.length}
            </span>
            <div className="flex items-center gap-1">
              <button 
                onClick={() => setCurrentPage(prev => Math.max(prev - 1, 1))}
                disabled={currentPage === 1}
                className="p-1 rounded text-outline hover:text-on-surface hover:bg-white/5 disabled:opacity-30 disabled:hover:bg-transparent cursor-pointer"
              >
                <span className="material-symbols-outlined text-sm">chevron_left</span>
              </button>
              
              {Array.from({ length: totalPages }).map((_, i) => (
                <button 
                  key={i}
                  onClick={() => setCurrentPage(i + 1)}
                  className={`w-7 h-7 rounded font-label-md text-xs flex items-center justify-center cursor-pointer ${
                    currentPage === i + 1 ? 'bg-primary-container text-white font-bold' : 'text-on-surface-variant hover:bg-white/5'
                  }`}
                >
                  {i + 1}
                </button>
              ))}

              <button 
                onClick={() => setCurrentPage(prev => Math.min(prev + 1, totalPages))}
                disabled={currentPage === totalPages}
                className="p-1 rounded text-outline hover:text-on-surface hover:bg-white/5 disabled:opacity-30 disabled:hover:bg-transparent cursor-pointer"
              >
                <span className="material-symbols-outlined text-sm">chevron_right</span>
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
