import React, { useState, useEffect } from 'react';
import { getExtraction, ApiError } from '../../api/client';

const FIELD_ORDER = [
  'po_number', 'invoice_number', 'customer_name', 'vendor_name', 'cnic', 'iban',
  'service_type', 'effective_date', 'expiry_date', 'currency',
  'mrc', 'otc', 'subtotal', 'tax', 'total', 'billing_terms', 'notes',
];

const FIELD_LABELS = {
  po_number: 'PO Number',
  invoice_number: 'Invoice Number',
  customer_name: 'Customer Name',
  vendor_name: 'Vendor Name',
  cnic: 'CNIC',
  iban: 'IBAN',
  service_type: 'Service Type',
  effective_date: 'Effective Date',
  expiry_date: 'Expiry Date',
  currency: 'Currency',
  mrc: 'MRC (Monthly)',
  otc: 'OTC (One-Time)',
  subtotal: 'Subtotal',
  tax: 'Tax',
  total: 'Total',
  billing_terms: 'Billing Terms',
  notes: 'Notes',
};

function confidenceTone(confidence) {
  if (confidence >= 0.85) return 'high';
  if (confidence >= 0.6) return 'medium';
  return 'low';
}

const CONFIDENCE_STYLES = {
  high: 'bg-[#10B981]/10 text-[#10B981] border-[#10B981]/20',
  medium: 'bg-[#F59E0B]/10 text-[#F59E0B] border-[#F59E0B]/20',
  low: 'bg-[#EF4444]/10 text-[#EF4444] border-[#EF4444]/20',
};

function FieldRow({ label, field }) {
  if (!field) return null;
  const tone = confidenceTone(field.confidence);
  return (
    <div className="group">
      <div className="flex flex-wrap justify-between items-center mb-1 gap-x-2 gap-y-1">
        <label className="font-body-sm text-[12px] text-on-surface-variant">{label}</label>
        <div className="flex items-center gap-1.5">
          <span className={`inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[10px] font-label-md border ${CONFIDENCE_STYLES[tone]}`}>
            {Math.round(field.confidence * 100)}%
          </span>
          {field.verified ? (
            <span
              className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[10px] font-label-md bg-primary/10 text-primary border border-primary/30"
              title="Confirmed by a deterministic gate or a human correction"
            >
              <span className="material-symbols-outlined text-xs">verified</span> Verified
            </span>
          ) : (
            <span
              className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[10px] font-label-md bg-white/5 text-on-surface-variant border border-outline-variant"
              title="Not confirmed by a deterministic gate"
            >
              <span className="material-symbols-outlined text-xs">help</span> Unverified
            </span>
          )}
        </div>
      </div>
      <div className="w-full bg-surface-variant border border-outline-variant rounded-md py-2 px-3 text-on-surface font-body-sm min-h-[38px] flex items-center">
        {field.value !== null && field.value !== '' ? field.value : <span className="text-on-surface-variant italic">absent</span>}
      </div>
      {field.gate_error && (
        <p className="text-error text-[11px] mt-1">{field.gate_error}</p>
      )}
    </div>
  );
}

function GatesSection({ gates }) {
  if (!gates || gates.length === 0) return null;
  const passed = gates.filter(g => g.result === 'passed');
  const unconfirmed = gates.filter(g => g.result === 'failed' || g.result === 'format_only');

  return (
    <div className="flex flex-col gap-3">
      <h3 className="font-label-md text-xs text-on-surface-variant uppercase tracking-wider font-semibold">Validation Gates</h3>
      {passed.length > 0 && (
        <div className="flex flex-col gap-2">
          {passed.map((g, i) => (
            <div key={i} className="flex items-start gap-2 px-3 py-2 rounded-md bg-primary/5 border border-primary/20">
              <span className="material-symbols-outlined text-primary text-base">check_circle</span>
              <div className="flex-1 min-w-0">
                <div className="flex items-center justify-between gap-2">
                  <span className="font-label-md text-xs text-on-surface">{g.name}</span>
                  <span className="text-[10px] text-primary font-semibold uppercase shrink-0">Passed</span>
                </div>
                {g.detail && <p className="text-[11px] text-on-surface-variant mt-0.5">{g.detail}</p>}
              </div>
            </div>
          ))}
        </div>
      )}
      {unconfirmed.length > 0 && (
        <div className="flex flex-col gap-2">
          <p className="text-[10px] text-on-surface-variant uppercase tracking-wider">Unconfirmed</p>
          {unconfirmed.map((g, i) => {
            const isFailed = g.result === 'failed';
            return (
              <div key={i} className={`flex items-start gap-2 px-3 py-2 rounded-md border ${isFailed ? 'bg-error/5 border-error/30' : 'bg-white/5 border-outline-variant'}`}>
                <span className={`material-symbols-outlined text-base ${isFailed ? 'text-error' : 'text-on-surface-variant'}`}>
                  {isFailed ? 'cancel' : 'help'}
                </span>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center justify-between gap-2">
                    <span className="font-label-md text-xs text-on-surface">{g.name}</span>
                    <span className={`text-[10px] font-semibold uppercase shrink-0 ${isFailed ? 'text-error' : 'text-on-surface-variant'}`}>
                      {isFailed ? 'Failed' : 'Format only'}
                    </span>
                  </div>
                  {g.detail && <p className="text-[11px] text-on-surface-variant mt-0.5">{g.detail}</p>}
                  {g.affected_fields && g.affected_fields.length > 0 && (
                    <p className="text-[11px] text-on-surface-variant mt-0.5">Fields: {g.affected_fields.join(', ')}</p>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}

function LineItemsSection({ lineItems }) {
  if (!lineItems || lineItems.length === 0) return null;
  return (
    <div className="flex flex-col gap-4">
      <h3 className="font-label-md text-xs text-on-surface-variant uppercase tracking-wider font-semibold">Line Items</h3>
      <div className="flex flex-col gap-4">
        {lineItems.map((item, i) => (
          <div key={i} className="flex flex-col gap-3 p-3 rounded-md border border-outline-variant/50 bg-surface-container-low/30">
            <FieldRow label="Description" field={item.description} />
            <div className="grid grid-cols-3 gap-3">
              <FieldRow label="Qty" field={item.quantity} />
              <FieldRow label="Unit Price" field={item.unit_price} />
              <FieldRow label="Line Total" field={item.line_total} />
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

export default function DocumentReview({ documentId, onBack }) {
  const [extraction, setExtraction] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [notReady, setNotReady] = useState(false);

  useEffect(() => {
    if (!documentId) {
      setExtraction(null);
      setError(null);
      setNotReady(false);
      return;
    }
    let cancelled = false;
    setLoading(true);
    setError(null);
    setNotReady(false);
    setExtraction(null);
    getExtraction(documentId)
      .then((result) => {
        if (!cancelled) setExtraction(result);
      })
      .catch((err) => {
        if (cancelled) return;
        if (err instanceof ApiError && err.code === 'NOT_READY') {
          setNotReady(true);
        } else {
          setError(err instanceof ApiError ? err.message : 'Failed to load extraction.');
        }
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [documentId]);

  return (
    <div className="flex-1 flex overflow-hidden w-full h-full animate-fadeIn">
      <div className="flex-1 flex flex-col md:flex-row overflow-hidden w-full">

        {/* Left Panel: no file-preview endpoint exists in the API */}
        <section className="flex-1 flex flex-col border-r border-outline-variant/30 bg-surface-container-lowest relative overflow-hidden h-[50vh] md:h-full">
          <div className="h-12 border-b border-outline-variant/30 bg-surface-container/80 backdrop-blur-md flex items-center justify-between px-4 shrink-0 z-10">
            <span className="font-label-md text-xs text-on-surface-variant">Document Preview</span>
            <button
              onClick={onBack}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded bg-white/5 border border-white/10 text-on-surface hover:bg-white/10 transition-colors font-label-md text-xs cursor-pointer"
            >
              <span className="material-symbols-outlined text-base">arrow_back</span>
              Exit Workspace
            </button>
          </div>
          <div className="flex-1 flex items-center justify-center bg-[#010811] text-on-surface-variant text-sm text-center p-8">
            No preview available — the API has no file-preview endpoint.
          </div>
        </section>

        {/* Right Panel: Real Extraction Data */}
        <section className="w-full md:w-[450px] flex flex-col bg-surface flex-shrink-0 border-l border-white/5 relative z-10 shadow-[-4px_0_24px_rgba(0,0,0,0.4)] h-[50vh] md:h-full">
          <div className="h-16 border-b border-outline-variant/30 flex items-center justify-between px-6 shrink-0 bg-surface-container/50 backdrop-blur-md">
            <h2 className="font-headline-md text-base font-semibold text-on-surface flex items-center gap-2">
              <span className="material-symbols-outlined text-primary text-xl">document_scanner</span>
              Extracted Data
            </h2>
            {extraction && (
              <span className="font-label-md text-xs text-on-surface-variant">
                {extraction.pipeline_version?.profile}
              </span>
            )}
          </div>

          <div className="flex-1 overflow-y-auto p-6 flex flex-col gap-5">
            {!documentId && (
              <p className="text-on-surface-variant text-sm text-center mt-10">Select a document to review.</p>
            )}

            {documentId && loading && (
              <div className="flex items-center justify-center mt-10">
                <div className="w-6 h-6 rounded-full border-2 border-primary/30 border-t-primary animate-spin"></div>
              </div>
            )}

            {documentId && !loading && notReady && (
              <div className="px-3 py-2.5 rounded-lg bg-white/5 border border-outline-variant text-on-surface-variant text-xs font-label-md mt-4">
                Not ready — this document is still processing. Extraction is only available once it reaches a terminal status.
              </div>
            )}

            {documentId && !loading && error && (
              <div className="px-3 py-2.5 rounded-lg bg-error/10 border border-error/25 text-error text-xs font-label-md mt-4">
                {error}
              </div>
            )}

            {extraction && !loading && (
              <>
                <div className="flex flex-col gap-3">
                  <div className="flex items-center justify-between">
                    <span className="font-label-md text-xs text-on-surface-variant uppercase tracking-wider">Status</span>
                    <span className="font-label-md text-xs text-on-surface">{extraction.status}</span>
                  </div>
                  {extraction.document_type && (
                    <div className="group">
                      <div className="flex justify-between items-center mb-1 gap-2">
                        <label className="font-body-sm text-[12px] text-on-surface-variant">Document Type</label>
                        <span className={`inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[10px] font-label-md border ${CONFIDENCE_STYLES[confidenceTone(extraction.document_type.confidence)]}`}>
                          {Math.round(extraction.document_type.confidence * 100)}%
                        </span>
                      </div>
                      <div className="w-full bg-surface-variant border border-outline-variant rounded-md py-2 px-3 text-on-surface font-body-sm">
                        {extraction.document_type.value}
                      </div>
                    </div>
                  )}
                  {extraction.review?.required && (
                    <div className="px-3 py-2.5 rounded-lg bg-amber-500/10 border border-amber-500/30 text-amber-400 text-xs font-label-md">
                      Review required{extraction.review.reason ? `: ${extraction.review.reason}` : ''}
                    </div>
                  )}
                </div>

                <div className="h-px w-full bg-outline-variant/30 my-1"></div>

                <div className="flex flex-col gap-4">
                  <h3 className="font-label-md text-xs text-on-surface-variant uppercase tracking-wider font-semibold">Fields</h3>
                  {FIELD_ORDER.map((key) => (
                    <FieldRow key={key} label={FIELD_LABELS[key]} field={extraction.fields?.[key]} />
                  ))}
                </div>

                <div className="h-px w-full bg-outline-variant/30 my-1"></div>

                <LineItemsSection lineItems={extraction.line_items} />

                <div className="h-px w-full bg-outline-variant/30 my-1"></div>

                <GatesSection gates={extraction.gates} />
              </>
            )}
          </div>
        </section>
      </div>
    </div>
  );
}
