import React, { useState, useEffect, useRef } from 'react';
import { getDocumentStatus, ApiError } from '../../api/client';

const TERMINAL_STATUSES = ['complete', 'needs_review', 'failed'];

const STATUS_LABELS = {
  queued: 'Queued',
  ocr: 'OCR',
  extracting: 'Extracting',
  validating: 'Validating',
  needs_review: 'Needs Review',
  complete: 'Complete',
  failed: 'Failed',
};

export default function ProcessingQueue({ queueItems, onUpdateItem, onDismissItem }) {
  const [searchTerm, setSearchTerm] = useState('');
  const intervalsRef = useRef({});

  useEffect(() => {
    queueItems.forEach((item) => {
      const isTerminal = TERMINAL_STATUSES.includes(item.status);
      const hasInterval = intervalsRef.current[item.document_id];

      if (!isTerminal && !hasInterval) {
        intervalsRef.current[item.document_id] = setInterval(async () => {
          try {
            const status = await getDocumentStatus(item.document_id);
            onUpdateItem(item.document_id, {
              status: status.status,
              progress: status.progress,
              stage_detail: status.stage_detail,
              error: status.error,
            });
            if (TERMINAL_STATUSES.includes(status.status)) {
              clearInterval(intervalsRef.current[item.document_id]);
              delete intervalsRef.current[item.document_id];
            }
          } catch (err) {
            clearInterval(intervalsRef.current[item.document_id]);
            delete intervalsRef.current[item.document_id];
            onUpdateItem(item.document_id, {
              status: 'failed',
              error: err instanceof ApiError ? err.message : 'Status check failed.',
            });
          }
        }, 2000);
      }

      if (isTerminal && hasInterval) {
        clearInterval(hasInterval);
        delete intervalsRef.current[item.document_id];
      }
    });

    Object.keys(intervalsRef.current).forEach((documentId) => {
      if (!queueItems.find((item) => item.document_id === documentId)) {
        clearInterval(intervalsRef.current[documentId]);
        delete intervalsRef.current[documentId];
      }
    });
  }, [queueItems, onUpdateItem]);

  useEffect(() => {
    return () => {
      Object.values(intervalsRef.current).forEach(clearInterval);
    };
  }, []);

  const filteredItems = queueItems.filter(item =>
    item.filename.toLowerCase().includes(searchTerm.toLowerCase())
  );

  const activeCount = queueItems.filter(item => !TERMINAL_STATUSES.includes(item.status)).length;
  const completedCount = queueItems.filter(item => item.status === 'complete').length;
  const failedCount = queueItems.filter(item => item.status === 'failed' || item.status === 'needs_review').length;

  return (
    <div className="flex flex-col gap-stack-lg w-full max-w-7xl mx-auto p-4 md:p-6 lg:p-10 animate-fadeIn">
      {/* Page Header */}
      <div className="flex flex-col md:flex-row md:items-end justify-between gap-4">
        <div>
          <h2 className="font-headline-lg text-headline-lg-mobile md:text-headline-lg text-on-surface">Processing Queue</h2>
          <p className="text-on-surface-variant mt-2 text-body-md">Monitoring AI extraction and OCR tasks in real-time.</p>
        </div>
        <div className="flex gap-3">
          <div className="relative">
            <span className="material-symbols-outlined absolute left-3 top-1/2 -translate-y-1/2 text-on-surface-variant text-base">search</span>
            <input
              className="bg-surface border border-outline-variant rounded-lg py-2 pl-9 pr-4 text-xs text-on-surface focus:outline-none focus:border-primary transition-all"
              placeholder="Search active tasks..."
              type="text"
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
            />
          </div>
        </div>
      </div>

      {/* Stats Overview Bento */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <div className="glass-card p-6 rounded-xl flex items-center gap-4 border-l-4 border-primary">
          <div className="w-12 h-12 rounded-full bg-primary-container/20 flex items-center justify-center text-primary-container border border-primary-container/30">
            <span className="material-symbols-outlined animate-spin-slow">sync</span>
          </div>
          <div>
            <p className="text-on-surface-variant text-xs font-semibold uppercase tracking-wider">Active Tasks</p>
            <p className="font-display-lg text-[32px] text-on-surface font-bold">{activeCount}</p>
          </div>
        </div>
        <div className="glass-card p-6 rounded-xl flex items-center gap-4 border-l-4 border-green-500">
          <div className="w-12 h-12 rounded-full bg-emerald-500/20 flex items-center justify-center text-emerald-400 border border-emerald-500/30">
            <span className="material-symbols-outlined">task_alt</span>
          </div>
          <div>
            <p className="text-on-surface-variant text-xs font-semibold uppercase tracking-wider">Completed</p>
            <p className="font-display-lg text-[32px] text-on-surface font-bold">{completedCount}</p>
          </div>
        </div>
        <div className="glass-card p-6 rounded-xl flex items-center gap-4 border-l-4 border-red-500">
          <div className="w-12 h-12 rounded-full bg-error/20 flex items-center justify-center text-error border border-error/30">
            <span className="material-symbols-outlined">error</span>
          </div>
          <div>
            <p className="text-on-surface-variant text-xs font-semibold uppercase tracking-wider">Failed / Review</p>
            <p className="font-display-lg text-[32px] text-on-surface font-bold">{failedCount}</p>
          </div>
        </div>
      </div>

      {/* Queue List */}
      <div className="glass-card rounded-xl overflow-hidden relative">
        <div className="overflow-x-auto">
          <table className="w-full text-left border-collapse">
            <thead>
              <tr className="border-b border-white/10 bg-surface-container-high/50 font-label-md text-xs text-on-surface-variant font-medium">
                <th className="px-6 py-4">Filename</th>
                <th className="px-6 py-4">Status</th>
                <th className="px-6 py-4 w-1/4">Progress</th>
                <th className="px-6 py-4">Stage</th>
                <th className="px-6 py-4 text-right">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-white/5 font-body-sm text-sm">
              {filteredItems.length === 0 ? (
                <tr>
                  <td colSpan="5" className="px-6 py-12 text-center text-on-surface-variant font-body-md">
                    No active processing documents in the queue.
                  </td>
                </tr>
              ) : (
                filteredItems.map((item) => {
                  const isFailed = item.status === 'failed';
                  const isNeedsReview = item.status === 'needs_review';
                  const isComplete = item.status === 'complete';
                  const isTerminal = TERMINAL_STATUSES.includes(item.status);
                  const label = STATUS_LABELS[item.status] || item.status;
                  const progressPct = Math.round((item.progress ?? 0) * 100);

                  return (
                    <tr key={item.document_id} className={`hover:bg-white/[0.02] transition-colors group ${isFailed ? 'bg-error/5' : ''}`}>
                      <td className="px-6 py-4">
                        <div className="flex items-center gap-3">
                          <span className={`material-symbols-outlined text-outline ${isFailed ? 'text-error' : ''}`}>
                            {item.filename.toLowerCase().endsWith('.pdf') ? 'picture_as_pdf' : 'image'}
                          </span>
                          <span className="font-semibold text-on-surface truncate max-w-[240px]">{item.filename}</span>
                        </div>
                      </td>
                      <td className="px-6 py-4">
                        <div className="flex items-center gap-2">
                          {isFailed ? (
                            <>
                              <div className="w-2 h-2 rounded-full bg-error"></div>
                              <span className="font-label-md text-xs text-error font-semibold">{label}</span>
                            </>
                          ) : isNeedsReview ? (
                            <>
                              <div className="w-2 h-2 rounded-full bg-amber-500"></div>
                              <span className="font-label-md text-xs text-amber-400 font-semibold">{label}</span>
                            </>
                          ) : isComplete ? (
                            <>
                              <div className="w-2 h-2 rounded-full bg-primary-dark"></div>
                              <span className="font-label-md text-xs text-primary font-semibold">{label}</span>
                            </>
                          ) : (
                            <>
                              <div className="w-2 h-2 rounded-full bg-primary animate-pulse shadow-[0_0_8px_var(--color-primary)]"></div>
                              <span className="font-label-md text-xs text-primary">{label}</span>
                            </>
                          )}
                        </div>
                        {isFailed && item.error && (
                          <p className="text-error text-xs mt-1 max-w-[220px]">{item.error}</p>
                        )}
                      </td>
                      <td className="px-6 py-4">
                        <div className="flex items-center gap-3">
                          <div className="w-full h-1.5 bg-surface-container-highest rounded-full overflow-hidden relative">
                            <div
                              className={`h-full relative transition-all duration-300 ${
                                isFailed ? 'bg-error' : isComplete ? 'bg-primary-dark' : 'bg-primary'
                              }`}
                              style={{ width: `${progressPct}%` }}
                            >
                              {!isTerminal && (
                                <div className="absolute inset-0 shimmer"></div>
                              )}
                            </div>
                          </div>
                          <span className={`font-label-md text-xs text-on-surface-variant w-10 text-right ${isFailed ? 'text-error font-bold' : ''}`}>
                            {isFailed ? 'Error' : `${progressPct}%`}
                          </span>
                        </div>
                      </td>
                      <td className="px-6 py-4 font-label-md text-xs text-on-surface-variant">
                        {item.stage_detail || '—'}
                      </td>
                      <td className="px-6 py-4 text-right">
                        <button
                          onClick={() => onDismissItem(item.document_id)}
                          className="p-1.5 text-on-surface-variant hover:text-error hover:bg-error/10 rounded-md transition-colors cursor-pointer"
                          title="Dismiss"
                        >
                          <span className="material-symbols-outlined text-[18px]">
                            {isTerminal ? 'delete' : 'cancel'}
                          </span>
                        </button>
                      </td>
                    </tr>
                  );
                })
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
