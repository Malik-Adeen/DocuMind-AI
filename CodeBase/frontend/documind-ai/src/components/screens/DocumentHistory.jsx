import React, { useState, useEffect } from 'react';
import { listDocuments, ApiError } from '../../api/client';
import { Card } from '@/components/ui/card';
import { Table, TableHeader, TableBody, TableRow, TableHead, TableCell } from '@/components/ui/table';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Search, Eye, Trash2, ChevronLeft, ChevronRight, FileText, AlertCircle, Loader2 } from 'lucide-react';

const STATUS_VARIANT = {
  complete: 'success',
  needs_review: 'warning',
  failed: 'destructive',
};

export default function DocumentHistory({ onSelectDocument }) {
  const [documents, setDocuments] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [searchTerm, setSearchTerm] = useState('');
  const [pageSize, setPageSize] = useState(10);
  const [currentPage, setCurrentPage] = useState(1);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);
    listDocuments({})
      .then((result) => {
        if (!cancelled) setDocuments(result.items);
      })
      .catch((err) => {
        if (!cancelled) {
          setError(err instanceof ApiError ? err.message : 'Failed to load documents.');
        }
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const handleDismiss = (documentId) => {
    setDocuments((prev) => prev.filter((doc) => doc.document_id !== documentId));
  };

  const filteredDocs = documents.filter((doc) =>
    doc.filename.toLowerCase().includes(searchTerm.toLowerCase()) ||
    doc.document_type.toLowerCase().includes(searchTerm.toLowerCase()) ||
    doc.status.toLowerCase().includes(searchTerm.toLowerCase())
  );

  const totalPages = Math.ceil(filteredDocs.length / pageSize) || 1;
  const startIndex = (currentPage - 1) * pageSize;
  const paginatedDocs = filteredDocs.slice(startIndex, startIndex + pageSize);

  return (
    <div className="flex flex-col gap-6 w-full max-w-7xl mx-auto p-4 md:p-6 lg:p-8 animate-fadeIn">
      {/* Header */}
      <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4">
        <div>
          <h2 className="font-headline-lg text-2xl font-bold text-foreground">Document History</h2>
          <p className="text-sm text-muted-foreground mt-1">Review and inspect historical parsed enterprise records.</p>
        </div>
        <div className="w-full sm:w-64 relative">
          <Search className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground" />
          <Input
            placeholder="Search filename, type, status…"
            value={searchTerm}
            onChange={(e) => {
              setSearchTerm(e.target.value);
              setCurrentPage(1);
            }}
            className="pl-9 h-9"
          />
        </div>
      </div>

      {error && (
        <Alert variant="destructive">
          <AlertCircle className="w-4 h-4" />
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}

      {/* Table Card */}
      <Card className="overflow-hidden">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Filename</TableHead>
              <TableHead>Doc Type</TableHead>
              <TableHead>Status</TableHead>
              <TableHead>Uploaded</TableHead>
              <TableHead className="text-right">Needs Review</TableHead>
              <TableHead className="text-right">Actions</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {loading ? (
              <TableRow>
                <TableCell colSpan={6} className="h-32 text-center text-muted-foreground text-xs">
                  <div className="flex items-center justify-center gap-2">
                    <Loader2 className="w-4 h-4 animate-spin" />
                    Loading documents…
                  </div>
                </TableCell>
              </TableRow>
            ) : paginatedDocs.length === 0 ? (
              <TableRow>
                <TableCell colSpan={6} className="h-32 text-center text-muted-foreground text-xs">
                  {error ? 'Could not load documents.' : 'No documents found.'}
                </TableCell>
              </TableRow>
            ) : (
              paginatedDocs.map((doc) => (
                <TableRow
                  key={doc.document_id}
                  onClick={() => onSelectDocument(doc)}
                  className="cursor-pointer"
                >
                  <TableCell>
                    <div className="flex items-center gap-2 font-semibold text-foreground text-xs">
                      <FileText className="w-4 h-4 text-primary-light shrink-0" />
                      <span className="truncate max-w-[220px]" title={doc.filename}>{doc.filename}</span>
                    </div>
                  </TableCell>

                  <TableCell className="font-label-md text-muted-foreground text-xs">{doc.document_type}</TableCell>

                  <TableCell>
                    <Badge variant={STATUS_VARIANT[doc.status] || 'default'}>{doc.status}</Badge>
                  </TableCell>

                  <TableCell className="font-label-md text-muted-foreground text-xs">{doc.uploaded_at}</TableCell>

                  <TableCell className={`text-right font-label-md text-xs font-semibold ${
                    doc.needs_review_count > 0 ? 'text-destructive' : 'text-muted-foreground'
                  }`}>
                    {doc.needs_review_count}
                  </TableCell>

                  <TableCell className="text-right" onClick={(e) => e.stopPropagation()}>
                    <div className="flex justify-end gap-1">
                      <Button
                        variant="ghost"
                        size="icon"
                        onClick={() => onSelectDocument(doc)}
                        className="h-8 w-8 text-muted-foreground hover:text-foreground"
                        title="View / Review"
                      >
                        <Eye className="w-4 h-4" />
                      </Button>
                      <Button
                        variant="ghost"
                        size="icon"
                        onClick={() => handleDismiss(doc.document_id)}
                        className="h-8 w-8 text-muted-foreground hover:text-destructive hover:bg-destructive/10"
                        title="Remove from this list"
                      >
                        <Trash2 className="w-4 h-4" />
                      </Button>
                    </div>
                  </TableCell>
                </TableRow>
              ))
            )}
          </TableBody>
        </Table>

        {/* Pagination Bar */}
        <div className="bg-muted/20 border-t border-border/40 px-6 py-3 flex flex-col sm:flex-row justify-between items-center gap-4 text-xs">
          <div className="flex items-center gap-2 text-muted-foreground">
            <span>Show</span>
            <select
              value={pageSize}
              onChange={(e) => {
                setPageSize(Number(e.target.value));
                setCurrentPage(1);
              }}
              className="bg-background border border-input text-foreground font-label-md text-xs rounded px-2 py-1 focus:outline-none"
            >
              <option value={5}>5</option>
              <option value={10}>10</option>
              <option value={20}>20</option>
            </select>
            <span>per page</span>
          </div>

          <div className="flex items-center gap-4 text-muted-foreground">
            <span>
              {filteredDocs.length === 0 ? 0 : startIndex + 1}-{Math.min(startIndex + pageSize, filteredDocs.length)} of {filteredDocs.length}
            </span>
            <div className="flex items-center gap-1">
              <Button
                variant="ghost"
                size="icon"
                onClick={() => setCurrentPage((prev) => Math.max(prev - 1, 1))}
                disabled={currentPage === 1}
                className="h-7 w-7"
              >
                <ChevronLeft className="w-4 h-4" />
              </Button>

              {Array.from({ length: totalPages }).map((_, i) => (
                <Button
                  key={i}
                  variant={currentPage === i + 1 ? 'default' : 'ghost'}
                  size="sm"
                  onClick={() => setCurrentPage(i + 1)}
                  className="h-7 w-7 p-0 text-xs font-label-md"
                >
                  {i + 1}
                </Button>
              ))}

              <Button
                variant="ghost"
                size="icon"
                onClick={() => setCurrentPage((prev) => Math.min(prev + 1, totalPages))}
                disabled={currentPage === totalPages}
                className="h-7 w-7"
              >
                <ChevronRight className="w-4 h-4" />
              </Button>
            </div>
          </div>
        </div>
      </Card>
    </div>
  );
}
