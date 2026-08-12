import React, { useState, useEffect, useRef } from 'react';
import { getDocumentStatus, ApiError } from '../../api/client';
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/card';
import { Table, TableHeader, TableBody, TableRow, TableHead, TableCell } from '@/components/ui/table';
import { Progress } from '@/components/ui/progress';
import { Badge } from '@/components/ui/badge';
import { Input } from '@/components/ui/input';
import { Button } from '@/components/ui/button';
import { RefreshCw, CheckCircle2, AlertCircle, Eye, Search, Trash2, XCircle, FileText, Image as ImageIcon } from 'lucide-react';

const TERMINAL_STATUSES = ['complete', 'needs_review', 'failed'];

const STATUS_LABELS = {
  queued: 'Queued',
  ocr: 'OCR Processing',
  extracting: 'AI Extracting',
  validating: 'Gate Validation',
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
        const check = async () => {
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
        };
        intervalsRef.current[item.document_id] = setInterval(check, 2000);
        check();
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

  const filteredItems = queueItems.filter((item) =>
    item.filename.toLowerCase().includes(searchTerm.toLowerCase())
  );

  const activeCount = queueItems.filter((item) => !TERMINAL_STATUSES.includes(item.status)).length;
  const completedCount = queueItems.filter((item) => item.status === 'complete').length;
  const needsReviewCount = queueItems.filter((item) => item.status === 'needs_review').length;
  const failedCount = queueItems.filter((item) => item.status === 'failed').length;

  return (
    <div className="flex flex-col gap-6 w-full max-w-7xl mx-auto p-4 md:p-6 lg:p-8 animate-fadeIn">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-end justify-between gap-4">
        <div>
          <h2 className="font-headline-lg text-2xl font-bold text-foreground">Processing Queue</h2>
          <p className="text-sm text-muted-foreground mt-1">Real-time pipeline monitoring for active document parsing jobs.</p>
        </div>
        <div className="w-full md:w-64 relative">
          <Search className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground" />
          <Input
            placeholder="Filter queue by filename…"
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            className="pl-9 h-9"
          />
        </div>
      </div>

      {/* KPI Overview Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        <Card className="border-l-4 border-l-primary p-5 flex items-center gap-4">
          <div className="p-3 rounded-full bg-primary/10 text-primary-light border border-primary/20">
            <RefreshCw className="w-5 h-5 animate-spin" />
          </div>
          <div>
            <p className="text-[11px] font-label-md text-muted-foreground uppercase tracking-wider font-semibold">Active Jobs</p>
            <p className="text-2xl font-bold text-foreground font-display-lg mt-0.5">{activeCount}</p>
          </div>
        </Card>

        <Card className="border-l-4 border-l-emerald-500 p-5 flex items-center gap-4">
          <div className="p-3 rounded-full bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
            <CheckCircle2 className="w-5 h-5" />
          </div>
          <div>
            <p className="text-[11px] font-label-md text-muted-foreground uppercase tracking-wider font-semibold">Completed</p>
            <p className="text-2xl font-bold text-foreground font-display-lg mt-0.5">{completedCount}</p>
          </div>
        </Card>

        <Card className="border-l-4 border-l-amber-500 p-5 flex items-center gap-4">
          <div className="p-3 rounded-full bg-amber-500/10 text-amber-400 border border-amber-500/20">
            <Eye className="w-5 h-5" />
          </div>
          <div>
            <p className="text-[11px] font-label-md text-muted-foreground uppercase tracking-wider font-semibold">Needs Review</p>
            <p className="text-2xl font-bold text-foreground font-display-lg mt-0.5">{needsReviewCount}</p>
          </div>
        </Card>

        <Card className="border-l-4 border-l-destructive p-5 flex items-center gap-4">
          <div className="p-3 rounded-full bg-destructive/10 text-destructive border border-destructive/20">
            <AlertCircle className="w-5 h-5" />
          </div>
          <div>
            <p className="text-[11px] font-label-md text-muted-foreground uppercase tracking-wider font-semibold">Failed</p>
            <p className="text-2xl font-bold text-foreground font-display-lg mt-0.5">{failedCount}</p>
          </div>
        </Card>
      </div>

      {/* Queue Table */}
      <Card className="overflow-hidden">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Filename</TableHead>
              <TableHead>Status</TableHead>
              <TableHead className="w-1/4">Progress</TableHead>
              <TableHead>Stage Detail</TableHead>
              <TableHead className="text-right">Actions</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {filteredItems.length === 0 ? (
              <TableRow>
                <TableCell colSpan={5} className="h-32 text-center text-muted-foreground text-xs">
                  No active documents in the processing queue.
                </TableCell>
              </TableRow>
            ) : (
              filteredItems.map((item) => {
                const isFailed = item.status === 'failed';
                const isNeedsReview = item.status === 'needs_review';
                const isComplete = item.status === 'complete';
                const isTerminal = TERMINAL_STATUSES.includes(item.status);
                const label = STATUS_LABELS[item.status] || item.status;
                const progressPct = Math.round((item.progress ?? 0) * 100);

                return (
                  <TableRow key={item.document_id}>
                    <TableCell>
                      <div className="flex items-center gap-2.5">
                        {item.filename.toLowerCase().endsWith('.pdf') ? (
                          <FileText className="w-4 h-4 text-primary-light shrink-0" />
                        ) : (
                          <ImageIcon className="w-4 h-4 text-accent-foreground shrink-0" />
                        )}
                        <span className="font-semibold text-foreground truncate max-w-[240px] text-xs" title={item.filename}>
                          {item.filename}
                        </span>
                      </div>
                    </TableCell>

                    <TableCell>
                      <div className="flex flex-col gap-1">
                        {isFailed ? (
                          <Badge variant="destructive">{label}</Badge>
                        ) : isNeedsReview ? (
                          <Badge variant="warning">{label}</Badge>
                        ) : isComplete ? (
                          <Badge variant="success">{label}</Badge>
                        ) : (
                          <Badge variant="default" className="gap-1 animate-pulse">
                            <span className="w-1.5 h-1.5 rounded-full bg-primary-light animate-ping"></span>
                            {label}
                          </Badge>
                        )}
                        {isFailed && item.error && (
                          <span className="text-destructive text-[11px] font-label-md max-w-[220px]">
                            {item.error}
                          </span>
                        )}
                      </div>
                    </TableCell>

                    <TableCell>
                      <div className="flex items-center gap-3">
                        <Progress
                          value={progressPct}
                          isFailed={isFailed}
                          isComplete={isComplete}
                          className="flex-1"
                        />
                        <span className={`text-[11px] font-label-md font-semibold w-10 text-right ${isFailed ? 'text-destructive' : 'text-muted-foreground'}`}>
                          {isFailed ? 'Error' : `${progressPct}%`}
                        </span>
                      </div>
                    </TableCell>

                    <TableCell className="font-label-md text-[11px] text-muted-foreground">
                      {item.stage_detail || '—'}
                    </TableCell>

                    <TableCell className="text-right">
                      <Button
                        variant="ghost"
                        size="icon"
                        onClick={() => onDismissItem(item.document_id)}
                        className="h-8 w-8 text-muted-foreground hover:text-destructive hover:bg-destructive/10"
                        title="Dismiss"
                      >
                        {isTerminal ? <Trash2 className="w-4 h-4" /> : <XCircle className="w-4 h-4" />}
                      </Button>
                    </TableCell>
                  </TableRow>
                );
              })
            )}
          </TableBody>
        </Table>
      </Card>
    </div>
  );
}
