import React, { useEffect, useRef, useState } from 'react';
import { listDocuments, createExport, getExportStatus, downloadExport, ApiError } from '../../api/client';
import { Card } from '../ui/card';
import { Table, TableHeader, TableBody, TableRow, TableHead, TableCell } from '../ui/table';
import { Badge } from '../ui/badge';
import { Button } from '../ui/button';
import { Input } from '../ui/input';
import { Alert, AlertDescription } from '../ui/alert';
import {
  Search,
  FileSpreadsheet,
  Download,
  CheckCircle2,
  XCircle,
  Loader2,
  AlertCircle,
} from 'lucide-react';

const TERMINAL_EXPORT_STATUSES = ['complete', 'failed'];

const STATUS_VARIANT = {
  complete: 'success',
  needs_review: 'warning',
  failed: 'destructive',
};

export default function ExportCenter() {
  const [documents, setDocuments] = useState([]);
  const [loadingDocuments, setLoadingDocuments] = useState(false);
  const [documentsError, setDocumentsError] = useState(null);
  const [searchTerm, setSearchTerm] = useState('');
  const [selectedIds, setSelectedIds] = useState(() => new Set());

  const [exportsLog, setExportsLog] = useState([]);
  const [triggerError, setTriggerError] = useState(null);
  const intervalsRef = useRef({});

  useEffect(() => {
    let cancelled = false;
    setLoadingDocuments(true);
    setDocumentsError(null);
    listDocuments({})
      .then((result) => {
        if (!cancelled) setDocuments(result.items);
      })
      .catch((err) => {
        if (!cancelled) {
          setDocumentsError(err instanceof ApiError ? err.message : 'Failed to load documents.');
        }
      })
      .finally(() => {
        if (!cancelled) setLoadingDocuments(false);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    return () => {
      Object.values(intervalsRef.current).forEach(clearInterval);
    };
  }, []);

  const filteredDocuments = documents.filter((doc) =>
    doc.filename.toLowerCase().includes(searchTerm.toLowerCase())
  );

  const toggleSelected = (documentId) => {
    setSelectedIds((prev) => {
      const next = new Set(prev);
      if (next.has(documentId)) {
        next.delete(documentId);
      } else {
        next.add(documentId);
      }
      return next;
    });
  };

  const toggleSelectAllFiltered = () => {
    setSelectedIds((prev) => {
      const allSelected = filteredDocuments.length > 0 && filteredDocuments.every((doc) => prev.has(doc.document_id));
      const next = new Set(prev);
      filteredDocuments.forEach((doc) => {
        if (allSelected) {
          next.delete(doc.document_id);
        } else {
          next.add(doc.document_id);
        }
      });
      return next;
    });
  };

  const pollExport = (exportId) => {
    intervalsRef.current[exportId] = setInterval(async () => {
      try {
        const status = await getExportStatus(exportId);
        setExportsLog((prev) =>
          prev.map((item) => (item.export_id === exportId ? { ...item, ...status } : item))
        );
        if (TERMINAL_EXPORT_STATUSES.includes(status.status)) {
          clearInterval(intervalsRef.current[exportId]);
          delete intervalsRef.current[exportId];
        }
      } catch (err) {
        clearInterval(intervalsRef.current[exportId]);
        delete intervalsRef.current[exportId];
        setExportsLog((prev) =>
          prev.map((item) =>
            item.export_id === exportId
              ? { ...item, status: 'failed', error: err instanceof ApiError ? err.message : 'Status check failed.' }
              : item
          )
        );
      }
    }, 2000);
  };

  const handleTriggerExport = async () => {
    setTriggerError(null);
    const documentIds = Array.from(selectedIds);
    if (documentIds.length === 0) return;
    try {
      const created = await createExport(documentIds, 'xlsx');
      setExportsLog((prev) => [
        {
          export_id: created.export_id,
          status: created.status,
          document_count: documentIds.length,
          download_url: null,
          expires_at: null,
          triggered_at: new Date().toISOString(),
        },
        ...prev,
      ]);
      setSelectedIds(new Set());
      if (!TERMINAL_EXPORT_STATUSES.includes(created.status)) {
        pollExport(created.export_id);
      }
    } catch (err) {
      setTriggerError(err instanceof ApiError ? err.message : 'Failed to start export.');
    }
  };

  const handleDownload = async (exportId) => {
    try {
      const blob = await downloadExport(exportId);
      const url = URL.createObjectURL(blob);
      const anchor = document.createElement('a');
      anchor.href = url;
      anchor.download = `export-${exportId}.xlsx`;
      anchor.click();
      URL.revokeObjectURL(url);
    } catch (err) {
      setTriggerError(err instanceof ApiError ? err.message : 'Failed to download export.');
    }
  };

  const allFilteredSelected =
    filteredDocuments.length > 0 && filteredDocuments.every((doc) => selectedIds.has(doc.document_id));

  return (
    <div className="flex flex-col gap-6 w-full max-w-7xl mx-auto p-4 md:p-6 lg:p-8 animate-fadeIn">
      {/* Header */}
      <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4">
        <div>
          <h2 className="font-headline-lg text-2xl font-bold text-foreground">Export Center</h2>
          <p className="text-sm text-muted-foreground mt-1">
            Select documents and export their extracted, gate-verified fields to Excel.
          </p>
        </div>
        <div className="w-full sm:w-64 relative">
          <Search className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground" />
          <Input
            placeholder="Search by filename…"
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            className="pl-9 h-9"
          />
        </div>
      </div>

      {documentsError && (
        <Alert variant="destructive">
          <AlertCircle className="w-4 h-4" />
          <AlertDescription>{documentsError}</AlertDescription>
        </Alert>
      )}

      {triggerError && (
        <Alert variant="destructive">
          <AlertCircle className="w-4 h-4" />
          <AlertDescription>{triggerError}</AlertDescription>
        </Alert>
      )}

      {/* Document Picker */}
      <Card className="overflow-hidden">
        <div className="px-6 py-4 border-b border-border/40 bg-muted/20 flex flex-col sm:flex-row justify-between items-start sm:items-center gap-3">
          <span className="text-sm font-semibold text-foreground">
            {selectedIds.size > 0 ? `${selectedIds.size} document${selectedIds.size === 1 ? '' : 's'} selected` : 'Select documents to export'}
          </span>
          <Button size="sm" onClick={handleTriggerExport} disabled={selectedIds.size === 0} className="gap-1.5">
            <FileSpreadsheet className="w-4 h-4" />
            Export to Excel
          </Button>
        </div>
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead className="w-10">
                <input
                  type="checkbox"
                  className="rounded border-border bg-background text-primary focus:ring-primary cursor-pointer"
                  checked={allFilteredSelected}
                  onChange={toggleSelectAllFiltered}
                  aria-label="Select all filtered documents"
                />
              </TableHead>
              <TableHead>Filename</TableHead>
              <TableHead>Doc Type</TableHead>
              <TableHead>Status</TableHead>
              <TableHead>Uploaded</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {loadingDocuments ? (
              <TableRow>
                <TableCell colSpan={5} className="h-32 text-center text-muted-foreground text-xs">
                  <div className="flex items-center justify-center gap-2">
                    <Loader2 className="w-4 h-4 animate-spin" />
                    Loading documents…
                  </div>
                </TableCell>
              </TableRow>
            ) : filteredDocuments.length === 0 ? (
              <TableRow>
                <TableCell colSpan={5} className="h-32 text-center text-muted-foreground text-xs">
                  No documents found.
                </TableCell>
              </TableRow>
            ) : (
              filteredDocuments.map((doc) => (
                <TableRow
                  key={doc.document_id}
                  onClick={() => toggleSelected(doc.document_id)}
                  className="cursor-pointer"
                >
                  <TableCell onClick={(e) => e.stopPropagation()}>
                    <input
                      type="checkbox"
                      className="rounded border-border bg-background text-primary focus:ring-primary cursor-pointer"
                      checked={selectedIds.has(doc.document_id)}
                      onChange={() => toggleSelected(doc.document_id)}
                      aria-label={`Select ${doc.filename}`}
                    />
                  </TableCell>
                  <TableCell>
                    <span className="font-semibold text-foreground text-xs truncate max-w-[240px] block" title={doc.filename}>
                      {doc.filename}
                    </span>
                  </TableCell>
                  <TableCell className="font-label-md text-muted-foreground text-xs">{doc.document_type}</TableCell>
                  <TableCell>
                    <Badge variant={STATUS_VARIANT[doc.status] || 'default'}>{doc.status}</Badge>
                  </TableCell>
                  <TableCell className="font-label-md text-muted-foreground text-xs">{doc.uploaded_at}</TableCell>
                </TableRow>
              ))
            )}
          </TableBody>
        </Table>
      </Card>

      {/* Export History (session-local — no export-listing endpoint exists) */}
      <Card className="overflow-hidden">
        <div className="px-6 py-4 border-b border-border/40 bg-muted/20 flex justify-between items-center">
          <h3 className="text-sm font-semibold text-foreground">Session Export History</h3>
          <span className="text-xs font-label-md text-muted-foreground">Excel (.xlsx)</span>
        </div>
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Export ID</TableHead>
              <TableHead>Documents</TableHead>
              <TableHead>Status</TableHead>
              <TableHead>Triggered</TableHead>
              <TableHead className="text-right">Actions</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {exportsLog.length === 0 ? (
              <TableRow>
                <TableCell colSpan={5} className="h-24 text-center text-muted-foreground text-xs">
                  No exports triggered in this session yet.
                </TableCell>
              </TableRow>
            ) : (
              exportsLog.map((item) => (
                <TableRow key={item.export_id}>
                  <TableCell className="font-label-md text-xs text-foreground">{item.export_id}</TableCell>
                  <TableCell className="font-label-md text-xs text-muted-foreground">
                    {item.document_count} document{item.document_count === 1 ? '' : 's'}
                  </TableCell>
                  <TableCell>
                    {item.status === 'complete' ? (
                      <Badge variant="success" className="gap-1">
                        <CheckCircle2 className="w-3 h-3" />
                        Complete
                      </Badge>
                    ) : item.status === 'failed' ? (
                      <Badge variant="destructive" className="gap-1">
                        <XCircle className="w-3 h-3" />
                        Failed
                      </Badge>
                    ) : (
                      <Badge variant="default" className="gap-1 animate-pulse">
                        <Loader2 className="w-3 h-3 animate-spin" />
                        Queued
                      </Badge>
                    )}
                    {item.error && (
                      <p className="text-destructive text-[11px] font-label-md mt-1">{item.error}</p>
                    )}
                  </TableCell>
                  <TableCell className="font-label-md text-xs text-muted-foreground">
                    {new Date(item.triggered_at).toLocaleString()}
                  </TableCell>
                  <TableCell className="text-right">
                    {item.status === 'complete' ? (
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => handleDownload(item.export_id)}
                        className="gap-1.5 text-xs"
                      >
                        <Download className="w-4 h-4" />
                        Download
                      </Button>
                    ) : (
                      <span className="text-muted-foreground font-label-md text-xs">
                        {item.status === 'failed' ? '—' : 'Processing…'}
                      </span>
                    )}
                  </TableCell>
                </TableRow>
              ))
            )}
          </TableBody>
        </Table>
      </Card>
    </div>
  );
}
