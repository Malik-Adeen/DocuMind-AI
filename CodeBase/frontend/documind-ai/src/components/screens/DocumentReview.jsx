import React, { useState, useEffect, useRef, useCallback, useMemo } from 'react';
import { getExtraction, getDocumentFile, correctExtraction, ApiError } from '../../api/client';
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button, buttonVariants } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { cn } from '@/lib/utils';
import { Alert, AlertDescription } from '@/components/ui/alert';
import {
  FileText,
  CheckCircle2,
  XCircle,
  HelpCircle,
  ArrowLeft,
  ShieldCheck,
  UserCheck,
  AlertCircle,
  Loader2,
  SearchX,
  Download,
  Save,
  MapPin,
} from 'lucide-react';

const EXTENSION_BY_TYPE = {
  'application/pdf': '.pdf',
  'image/png': '.png',
  'image/jpeg': '.jpg',
  'image/tiff': '.tiff',
};

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

function confidenceBadgeVariant(confidence) {
  if (confidence >= 0.85) return 'success';
  if (confidence >= 0.6) return 'warning';
  return 'destructive';
}

const MONEY_FIELDS = new Set(['mrc', 'otc', 'subtotal', 'tax', 'total']);
const MONEY_PATTERN = /^-?[0-9]+\.[0-9]{2}$/;
const EMPTY_FIELD = { value: null, confidence: 0, verified: false, gate: null, gate_error: null, source: null };

function fieldBBox(field) {
  const bbox = field?.source?.bbox;
  if (!Array.isArray(bbox) || bbox.length !== 4) return null;
  if (!bbox.every((n) => typeof n === 'number' && Number.isFinite(n))) return null;
  return bbox;
}

function highlightableRowProps(hasBBox, fieldKey, onToggleHighlight) {
  if (!hasBBox) return {};
  return {
    onClick: () => onToggleHighlight(fieldKey),
    role: 'button',
    tabIndex: 0,
    onKeyDown: (e) => {
      if (e.key === 'Enter' || e.key === ' ') {
        e.preventDefault();
        onToggleHighlight(fieldKey);
      }
    },
  };
}

function FieldRow({ label, field, fieldKey, isHighlighted, onToggleHighlight }) {
  if (!field) return null;
  const confVariant = confidenceBadgeVariant(field.confidence);
  const hasBBox = Boolean(fieldBBox(field));
  return (
    <div
      className={cn(
        'group space-y-1.5 p-3 rounded-lg border transition-colors',
        isHighlighted
          ? 'bg-primary/10 border-primary/50 ring-1 ring-primary/40'
          : 'bg-muted/20 border-border/30 hover:border-border/60'
      )}
    >
      <div
        className={cn('flex flex-wrap justify-between items-center gap-2', hasBBox && 'cursor-pointer')}
        {...highlightableRowProps(hasBBox, fieldKey, onToggleHighlight)}
      >
        <label className="font-body-sm text-xs font-medium text-muted-foreground flex items-center gap-1">
          {label}
          {hasBBox && <MapPin className="w-3 h-3 text-primary/70" />}
        </label>
        {/* INVARIANT 2: Confidence and Verification are separate signals with separate visual badges */}
        <div className="flex items-center gap-1.5">
          <Badge variant={confVariant} className="text-[10px] py-0 px-1.5 font-label-md">
            Score: {Math.round(field.confidence * 100)}%
          </Badge>
          {field.verified ? (
            <Badge variant="success" className="text-[10px] py-0 px-1.5 font-label-md" title="Confirmed by a deterministic gate or a human correction">
              <ShieldCheck className="w-3 h-3 text-emerald-400" />
              Verified
            </Badge>
          ) : (
            <Badge variant="unconfirmed" className="text-[10px] py-0 px-1.5 font-label-md" title="Not confirmed by a deterministic gate">
              <HelpCircle className="w-3 h-3 text-slate-400" />
              Unverified
            </Badge>
          )}
        </div>
      </div>
      <div className="w-full bg-background/80 border border-input rounded-md py-2 px-3 text-xs text-foreground font-body-sm min-h-[36px] flex items-center">
        {field.value !== null && field.value !== '' ? (
          <span className="font-medium text-foreground">{field.value}</span>
        ) : (
          <span className="text-muted-foreground italic text-[11px]">absent</span>
        )}
      </div>
      {field.gate_error && (
        <p className="text-destructive text-[11px] font-label-md mt-1">{field.gate_error}</p>
      )}
    </div>
  );
}

function EditableFieldRow({
  fieldKey,
  label,
  field,
  value,
  onChange,
  validationError,
  isHighlighted,
  onToggleHighlight,
}) {
  const confVariant = confidenceBadgeVariant(field.confidence);
  const isMoney = MONEY_FIELDS.has(fieldKey);
  const hasBBox = Boolean(fieldBBox(field));
  return (
    <div
      className={cn(
        'group space-y-1.5 p-3 rounded-lg border transition-colors',
        isHighlighted
          ? 'bg-primary/10 border-primary/50 ring-1 ring-primary/40'
          : 'bg-muted/20 border-border/30 hover:border-border/60'
      )}
    >
      <div
        className={cn('flex flex-wrap justify-between items-center gap-2', hasBBox && 'cursor-pointer')}
        {...highlightableRowProps(hasBBox, fieldKey, onToggleHighlight)}
      >
        <label className="font-body-sm text-xs font-medium text-muted-foreground flex items-center gap-1" htmlFor={`field-${fieldKey}`}>
          {label}
          {hasBBox && <MapPin className="w-3 h-3 text-primary/70" />}
        </label>
        {/* INVARIANT 2: Confidence and Verification are separate signals with separate visual badges */}
        <div className="flex items-center gap-1.5">
          <Badge variant={confVariant} className="text-[10px] py-0 px-1.5 font-label-md">
            Score: {Math.round(field.confidence * 100)}%
          </Badge>
          {field.verified ? (
            <Badge variant="success" className="text-[10px] py-0 px-1.5 font-label-md" title="Confirmed by a deterministic gate or a human correction">
              <ShieldCheck className="w-3 h-3 text-emerald-400" />
              Verified
            </Badge>
          ) : (
            <Badge variant="unconfirmed" className="text-[10px] py-0 px-1.5 font-label-md" title="Not confirmed by a deterministic gate">
              <HelpCircle className="w-3 h-3 text-slate-400" />
              Unverified
            </Badge>
          )}
          {field.source?.origin === 'human' && (
            <Badge variant="outline" className="text-[10px] py-0 px-1.5 font-label-md" title="Corrected by a human reviewer">
              <UserCheck className="w-3 h-3" />
              Human
            </Badge>
          )}
        </div>
      </div>
      <Input
        id={`field-${fieldKey}`}
        value={value}
        onChange={(e) => onChange(fieldKey, e.target.value)}
        placeholder={isMoney ? '0.00' : 'absent'}
        className={`text-xs h-9 font-body-sm ${validationError ? 'border-destructive focus-visible:ring-destructive' : ''}`}
      />
      {validationError ? (
        <p className="text-destructive text-[11px] font-label-md mt-1">{validationError}</p>
      ) : field.gate_error ? (
        <p className="text-destructive text-[11px] font-label-md mt-1">{field.gate_error}</p>
      ) : null}
    </div>
  );
}

function GatesSection({ gates }) {
  if (!gates || gates.length === 0) return null;

  // INVARIANT 1: gates[].result is passed/failed/format_only.
  // format_only renders grouped with failed under "Unconfirmed" — never green, never a checkmark, never adjacent to passed gates.
  const passed = gates.filter(g => g.result === 'passed');
  const unconfirmed = gates.filter(g => g.result === 'failed' || g.result === 'format_only');

  return (
    <div className="space-y-3 pt-2">
      <h4 className="font-label-md text-xs text-muted-foreground uppercase tracking-wider font-semibold">Validation Gates</h4>
      
      {passed.length > 0 && (
        <div className="space-y-2">
          {passed.map((g, i) => (
            <div key={i} className="flex items-start gap-2.5 p-3 rounded-lg bg-emerald-500/10 border border-emerald-500/20 text-xs">
              <CheckCircle2 className="w-4 h-4 text-emerald-400 shrink-0 mt-0.5" />
              <div className="flex-1 min-w-0">
                <div className="flex items-center justify-between gap-2">
                  <span className="font-label-md font-semibold text-foreground">{g.name}</span>
                  <Badge variant="success" className="text-[9px] py-0 px-1 uppercase tracking-wider">Passed</Badge>
                </div>
                {g.detail && <p className="text-[11px] text-muted-foreground mt-1">{g.detail}</p>}
              </div>
            </div>
          ))}
        </div>
      )}

      {unconfirmed.length > 0 && (
        <div className="space-y-2 pt-1">
          <p className="text-[10px] text-muted-foreground uppercase tracking-wider font-semibold">Unconfirmed Gates</p>
          {unconfirmed.map((g, i) => {
            const isFailed = g.result === 'failed';
            return (
              <div
                key={i}
                className={`flex items-start gap-2.5 p-3 rounded-lg border text-xs ${
                  isFailed
                    ? 'bg-destructive/10 border-destructive/30'
                    : 'bg-muted/40 border-border/40'
                }`}
              >
                {isFailed ? (
                  <XCircle className="w-4 h-4 text-destructive shrink-0 mt-0.5" />
                ) : (
                  <HelpCircle className="w-4 h-4 text-muted-foreground shrink-0 mt-0.5" />
                )}
                <div className="flex-1 min-w-0">
                  <div className="flex items-center justify-between gap-2">
                    <span className="font-label-md font-semibold text-foreground">{g.name}</span>
                    {isFailed ? (
                      <Badge variant="destructive" className="text-[9px] py-0 px-1 uppercase tracking-wider">Failed</Badge>
                    ) : (
                      <Badge variant="unconfirmed" className="text-[9px] py-0 px-1 uppercase tracking-wider">Format only</Badge>
                    )}
                  </div>
                  {g.detail && <p className="text-[11px] text-muted-foreground mt-1">{g.detail}</p>}
                  {g.affected_fields && g.affected_fields.length > 0 && (
                    <p className="text-[11px] text-muted-foreground/80 mt-1 font-label-md">Fields: {g.affected_fields.join(', ')}</p>
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

function LineItemsSection({ lineItems, highlightedField, onToggleHighlight }) {
  if (!lineItems || lineItems.length === 0) return null;
  return (
    <div className="space-y-3 pt-2">
      <h4 className="font-label-md text-xs text-muted-foreground uppercase tracking-wider font-semibold">Line Items</h4>
      <div className="space-y-3">
        {lineItems.map((item, i) => {
          const subFieldProps = (subKey) => {
            const key = `line_items[${i}].${subKey}`;
            return { fieldKey: key, isHighlighted: highlightedField === key, onToggleHighlight };
          };
          return (
            <div key={i} className="p-3 rounded-lg border border-border/40 bg-muted/20 space-y-3">
              <FieldRow label="Description" field={item.description} {...subFieldProps('description')} />
              <div className="grid grid-cols-1 gap-2.5">
                <FieldRow label="Qty" field={item.quantity} {...subFieldProps('quantity')} />
                <FieldRow label="Unit Price" field={item.unit_price} {...subFieldProps('unit_price')} />
                <FieldRow label="Line Total" field={item.line_total} {...subFieldProps('line_total')} />
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

export default function DocumentReview({ documentId, onBack }) {
  const [extraction, setExtraction] = useState(null);
  const [loading, setLoading] = useState(() => Boolean(documentId));
  const [error, setError] = useState(null);
  const [notReady, setNotReady] = useState(false);

  const [fileUrl, setFileUrl] = useState(null);
  const [fileType, setFileType] = useState(null);
  const [fileLoading, setFileLoading] = useState(() => Boolean(documentId));
  const [fileError, setFileError] = useState(null);

  const [editedValues, setEditedValues] = useState({});
  const [validationErrors, setValidationErrors] = useState({});
  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState(null);

  const [highlightedField, setHighlightedField] = useState(null);
  const [imageBox, setImageBox] = useState(null);
  const previewContainerRef = useRef(null);
  const imgRef = useRef(null);

  const recomputeImageBox = useCallback(() => {
    const img = imgRef.current;
    const container = previewContainerRef.current;
    if (!img || !container) return;
    const imgRect = img.getBoundingClientRect();
    const containerRect = container.getBoundingClientRect();
    if (imgRect.width === 0 || imgRect.height === 0) return;
    setImageBox({
      left: imgRect.left - containerRect.left,
      top: imgRect.top - containerRect.top,
      width: imgRect.width,
      height: imgRect.height,
    });
  }, []);

  const handleToggleHighlight = useCallback((key) => {
    setHighlightedField((prev) => (prev === key ? null : key));
  }, []);

  useEffect(() => {
    if (!documentId) {
      setFileUrl(null);
      setFileType(null);
      setFileError(null);
      return;
    }
    let cancelled = false;
    let objectUrl = null;
    setFileLoading(true);
    setFileError(null);
    setFileUrl(null);
    setFileType(null);
    getDocumentFile(documentId)
      .then((blob) => {
        if (cancelled) return;
        objectUrl = URL.createObjectURL(blob);
        setFileUrl(objectUrl);
        setFileType(blob.type);
      })
      .catch((err) => {
        if (!cancelled) {
          setFileError(err instanceof ApiError ? err.message : 'Failed to load document file.');
        }
      })
      .finally(() => {
        if (!cancelled) setFileLoading(false);
      });
    return () => {
      cancelled = true;
      if (objectUrl) URL.revokeObjectURL(objectUrl);
    };
  }, [documentId]);

  useEffect(() => {
    setEditedValues({});
    setValidationErrors({});
    setSaveError(null);
    setHighlightedField(null);
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

  const handleFieldChange = (key, value) => {
    setEditedValues((prev) => ({ ...prev, [key]: value }));
    setValidationErrors((prev) => {
      if (!(key in prev)) return prev;
      const next = { ...prev };
      delete next[key];
      return next;
    });
    setSaveError(null);
  };

  const handleDiscardChanges = () => {
    setEditedValues({});
    setValidationErrors({});
    setSaveError(null);
  };

  const dirtyKeys = Object.keys(editedValues).filter((key) => {
    const original = extraction?.fields?.[key]?.value ?? '';
    return editedValues[key] !== original;
  });

  const handleSaveCorrections = async () => {
    const nextErrors = {};
    const corrections = [];
    for (const key of dirtyKeys) {
      const raw = editedValues[key];
      const value = raw === '' ? null : raw;
      if (value !== null && MONEY_FIELDS.has(key) && !MONEY_PATTERN.test(value)) {
        nextErrors[key] = 'Must be a decimal with exactly two places, e.g. 1250.00';
        continue;
      }
      corrections.push({ field: key, value });
    }
    if (Object.keys(nextErrors).length > 0) {
      setValidationErrors(nextErrors);
      return;
    }
    if (corrections.length === 0) return;

    setSaving(true);
    setSaveError(null);
    try {
      const merged = await correctExtraction(documentId, corrections);
      setExtraction(merged);
      setEditedValues({});
      setValidationErrors({});
    } catch (err) {
      setSaveError(err instanceof ApiError ? err.message : 'Failed to save corrections.');
    } finally {
      setSaving(false);
    }
  };

  const previewPhase = !documentId
    ? 'empty'
    : fileLoading
      ? 'loading'
      : fileError
        ? 'error'
        : fileUrl && fileType?.startsWith('image/')
          ? 'image'
          : fileUrl
            ? 'download'
            : 'empty';

  useEffect(() => {
    if (previewPhase !== 'image') {
      setImageBox(null);
      return;
    }
    const container = previewContainerRef.current;
    if (!container) return;
    const observer = new ResizeObserver(recomputeImageBox);
    observer.observe(container);
    return () => observer.disconnect();
  }, [previewPhase, recomputeImageBox]);

  const highlightedBBox = useMemo(() => {
    if (!highlightedField || !extraction) return null;
    const lineItemMatch = /^line_items\[(\d+)\]\.(.+)$/.exec(highlightedField);
    const field = lineItemMatch
      ? extraction.line_items?.[Number(lineItemMatch[1])]?.[lineItemMatch[2]]
      : extraction.fields?.[highlightedField];
    return fieldBBox(field);
  }, [highlightedField, extraction]);

  return (
    <div className="flex-1 flex overflow-hidden w-full h-full animate-fadeIn">
      <div className="flex-1 flex flex-col md:flex-row overflow-hidden w-full">

        {/* Left Panel: No preview endpoint in API contract */}
        <section className="flex-1 flex flex-col border-r border-border/40 bg-background relative overflow-hidden h-[40vh] md:h-full">
          <div className="h-14 border-b border-border/40 bg-card/60 backdrop-blur-md flex items-center justify-between px-5 shrink-0 z-10">
            <span className="font-label-md text-xs text-muted-foreground font-semibold uppercase tracking-wider">Document Preview</span>
            <Button variant="glass" size="sm" onClick={onBack} className="gap-1.5 text-xs">
              <ArrowLeft className="w-4 h-4" />
              Exit Workspace
            </Button>
          </div>
          <div
            ref={previewContainerRef}
            className="flex-1 flex flex-col items-center justify-center text-muted-foreground text-xs text-center p-8 bg-card/20 overflow-hidden relative"
          >
            {(() => {
              switch (previewPhase) {
                case 'loading':
                  return (
                    <div className="flex flex-col items-center gap-2">
                      <Loader2 className="w-6 h-6 animate-spin text-primary" />
                      <span>Loading document…</span>
                    </div>
                  );

                case 'error':
                  return (
                    <>
                      <SearchX className="w-10 h-10 mb-3 text-muted-foreground/50" />
                      <p className="font-medium text-foreground">Could not load document</p>
                      <p className="text-muted-foreground mt-1 max-w-sm">{fileError}</p>
                    </>
                  );

                case 'image':
                  return (
                    <>
                      <img
                        ref={imgRef}
                        src={fileUrl}
                        alt="Document preview"
                        className="max-w-full max-h-full object-contain rounded-md shadow-lg"
                        onLoad={recomputeImageBox}
                      />
                      {imageBox && highlightedBBox && (
                        <div
                          className="absolute pointer-events-none border-2 border-primary bg-primary/20 rounded-sm"
                          style={{
                            left: imageBox.left + highlightedBBox[0] * imageBox.width,
                            top: imageBox.top + highlightedBBox[1] * imageBox.height,
                            width: (highlightedBBox[2] - highlightedBBox[0]) * imageBox.width,
                            height: (highlightedBBox[3] - highlightedBBox[1]) * imageBox.height,
                          }}
                        />
                      )}
                    </>
                  );

                case 'download':
                  return (
                    <div className="flex flex-col items-center gap-3">
                      <FileText className="w-10 h-10 text-muted-foreground/50" />
                      <p className="font-medium text-foreground">No inline preview for {fileType}</p>
                      <a
                        href={fileUrl}
                        download={`${documentId}${EXTENSION_BY_TYPE[fileType] || ''}`}
                        className={cn(buttonVariants({ size: 'sm', variant: 'outline' }), 'gap-1.5')}
                      >
                        <Download className="w-4 h-4" />
                        Download file
                      </a>
                    </div>
                  );

                case 'empty':
                default:
                  return (
                    <>
                      <FileText className="w-10 h-10 mb-3 text-muted-foreground/50" />
                      <p className="text-muted-foreground">
                        {documentId ? 'No preview available for this document.' : 'Select a document to preview.'}
                      </p>
                    </>
                  );
              }
            })()}
          </div>
        </section>

        {/* Right Panel: Extraction Results */}
        <section className="w-full md:w-[460px] flex flex-col bg-card flex-shrink-0 border-l border-border/40 relative z-10 shadow-2xl h-[60vh] md:h-full">
          <div className="h-14 border-b border-border/40 flex items-center justify-between px-6 shrink-0 bg-muted/20 backdrop-blur-md">
            <h3 className="font-headline-md text-sm font-bold text-foreground flex items-center gap-2">
              <FileText className="w-4 h-4 text-primary" />
              Extracted Workspace Data
            </h3>
            {extraction?.pipeline_version?.profile && (
              <Badge variant="outline" className="font-label-md text-[10px]">
                {extraction.pipeline_version.profile}
              </Badge>
            )}
          </div>

          <div className="flex-1 overflow-y-auto p-6 space-y-5">
            {!documentId && (
              <div className="text-center text-muted-foreground text-xs py-12">
                Select a document from document history to review extracted fields.
              </div>
            )}

            {documentId && loading && (
              <div className="flex flex-col items-center justify-center py-12 text-xs text-muted-foreground gap-2">
                <Loader2 className="w-6 h-6 animate-spin text-primary" />
                <span>Loading extraction data…</span>
              </div>
            )}

            {documentId && !loading && notReady && (
              <Alert variant="warning">
                <AlertCircle className="w-4 h-4" />
                <AlertDescription>
                  Not ready — this document is still processing. Extraction is available once it reaches terminal status.
                </AlertDescription>
              </Alert>
            )}

            {documentId && !loading && error && (
              <Alert variant="destructive">
                <AlertCircle className="w-4 h-4" />
                <AlertDescription>{error}</AlertDescription>
              </Alert>
            )}

            {extraction && !loading && (
              <>
                <div className="space-y-3">
                  <div className="flex items-center justify-between text-xs">
                    <span className="font-label-md text-muted-foreground uppercase tracking-wider">Status</span>
                    <Badge variant={extraction.status === 'complete' ? 'success' : 'secondary'}>
                      {extraction.status}
                    </Badge>
                  </div>

                  {extraction.document_type && (
                    <div className="p-3 rounded-lg bg-muted/20 border border-border/30 space-y-1.5">
                      <div className="flex justify-between items-center text-xs">
                        <label className="font-body-sm text-muted-foreground">Document Type</label>
                        <Badge variant={confidenceBadgeVariant(extraction.document_type.confidence)}>
                          {Math.round(extraction.document_type.confidence * 100)}%
                        </Badge>
                      </div>
                      <div className="font-medium text-foreground text-xs">
                        {extraction.document_type.value}
                      </div>
                    </div>
                  )}

                  {extraction.review?.required && (
                    <Alert variant="warning">
                      <AlertCircle className="w-4 h-4" />
                      <AlertDescription>
                        Review required{extraction.review.reason ? `: ${extraction.review.reason}` : ''}
                      </AlertDescription>
                    </Alert>
                  )}
                </div>

                <div className="h-px w-full bg-border/40"></div>

                <div className="space-y-3">
                  <h4 className="font-label-md text-xs text-muted-foreground uppercase tracking-wider font-semibold">Extracted Fields</h4>
                  {FIELD_ORDER.map((key) => {
                    const field = extraction.fields?.[key] ?? EMPTY_FIELD;
                    const value = key in editedValues ? editedValues[key] : (field.value ?? '');
                    return (
                      <EditableFieldRow
                        key={key}
                        fieldKey={key}
                        label={FIELD_LABELS[key]}
                        field={field}
                        value={value}
                        onChange={handleFieldChange}
                        validationError={validationErrors[key]}
                        isHighlighted={highlightedField === key}
                        onToggleHighlight={handleToggleHighlight}
                      />
                    );
                  })}

                  {saveError && (
                    <Alert variant="destructive">
                      <AlertCircle className="w-4 h-4" />
                      <AlertDescription>{saveError}</AlertDescription>
                    </Alert>
                  )}

                  {dirtyKeys.length > 0 && (
                    <div className="flex gap-2 pt-1">
                      <Button size="sm" onClick={handleSaveCorrections} disabled={saving} className="gap-1.5 flex-1">
                        {saving ? <Loader2 className="w-4 h-4 animate-spin" /> : <Save className="w-4 h-4" />}
                        Save {dirtyKeys.length} correction{dirtyKeys.length === 1 ? '' : 's'}
                      </Button>
                      <Button size="sm" variant="outline" onClick={handleDiscardChanges} disabled={saving}>
                        Discard
                      </Button>
                    </div>
                  )}
                </div>

                <div className="h-px w-full bg-border/40"></div>

                <LineItemsSection
                  lineItems={extraction.line_items}
                  highlightedField={highlightedField}
                  onToggleHighlight={handleToggleHighlight}
                />

                <div className="h-px w-full bg-border/40"></div>

                <GatesSection gates={extraction.gates} />
              </>
            )}
          </div>
        </section>
      </div>
    </div>
  );
}
