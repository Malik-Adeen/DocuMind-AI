import React, { useState } from 'react';
import { Card } from '@/components/ui/card';
import { Table, TableHeader, TableBody, TableRow, TableHead, TableCell } from '@/components/ui/table';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Search, Eye, Trash2, ChevronLeft, ChevronRight, FileText, Receipt, FileCheck } from 'lucide-react';

export default function DocumentHistory({ documents, onSelectDocument, onDeleteDocument }) {
  const [searchTerm, setSearchTerm] = useState('');
  const [pageSize, setPageSize] = useState(10);
  const [currentPage, setCurrentPage] = useState(1);

  const filteredDocs = documents.filter((doc) =>
    (doc.name && doc.name.toLowerCase().includes(searchTerm.toLowerCase())) ||
    (doc.type && doc.type.toLowerCase().includes(searchTerm.toLowerCase())) ||
    (doc.customer && doc.customer.toLowerCase().includes(searchTerm.toLowerCase())) ||
    (doc.ref && doc.ref.toLowerCase().includes(searchTerm.toLowerCase()))
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
            placeholder="Search name, client, ID…"
            value={searchTerm}
            onChange={(e) => {
              setSearchTerm(e.target.value);
              setCurrentPage(1);
            }}
            className="pl-9 h-9"
          />
        </div>
      </div>

      {/* Table Card */}
      <Card className="overflow-hidden">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Doc Type</TableHead>
              <TableHead>Client / Customer</TableHead>
              <TableHead>Ref Number</TableHead>
              <TableHead>Status</TableHead>
              <TableHead>Processed Date</TableHead>
              <TableHead className="text-right">Confidence %</TableHead>
              <TableHead className="text-right">Actions</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {paginatedDocs.length === 0 ? (
              <TableRow>
                <TableCell colSpan={7} className="h-32 text-center text-muted-foreground text-xs">
                  No documents found matching query.
                </TableCell>
              </TableRow>
            ) : (
              paginatedDocs.map((doc) => (
                <TableRow
                  key={doc.id}
                  onClick={() => onSelectDocument(doc)}
                  className="cursor-pointer"
                >
                  <TableCell>
                    <div className="flex items-center gap-2 font-semibold text-foreground text-xs">
                      {doc.type === 'Invoice' ? (
                        <Receipt className="w-4 h-4 text-primary-light" />
                      ) : (
                        <FileText className="w-4 h-4 text-accent-foreground" />
                      )}
                      <span>{doc.type}</span>
                    </div>
                  </TableCell>

                  <TableCell className="text-foreground text-xs">{doc.customer}</TableCell>

                  <TableCell className="font-label-md text-muted-foreground text-xs">{doc.ref}</TableCell>

                  <TableCell>
                    <Badge variant={doc.status === 'Processed' ? 'success' : doc.status === 'In Review' ? 'warning' : 'destructive'}>
                      {doc.status}
                    </Badge>
                  </TableCell>

                  <TableCell className="font-label-md text-muted-foreground text-xs">{doc.date}</TableCell>

                  <TableCell className={`text-right font-label-md text-xs font-semibold ${
                    doc.score.startsWith('4') || doc.score.startsWith('5') ? 'text-destructive' : 'text-emerald-400'
                  }`}>
                    {doc.score}
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
                        onClick={() => onDeleteDocument(doc.id)}
                        className="h-8 w-8 text-muted-foreground hover:text-destructive hover:bg-destructive/10"
                        title="Delete"
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
