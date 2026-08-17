import React, { useState, useRef } from 'react';
import { uploadDocument, ApiError } from '../../api/client';
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { UploadCloud, FileUp, FileCheck, AlertCircle, Loader2, FileText, Image as ImageIcon } from 'lucide-react';

const MAX_FILES_PER_DROP = 20;
const CLASSIFICATIONS = [
  { value: 'public', label: 'Public — publicly available document' },
  { value: 'synthetic', label: 'Synthetic — generated, no real party in it' },
  { value: 'restricted', label: 'Restricted — anything else, including anything not yet looked at' },
];

export default function UploadCenter({ onAddDocumentToQueue }) {
  const [uploads, setUploads] = useState([]);
  const [dragging, setDragging] = useState(false);
  const [uploadError, setUploadError] = useState('');
  const [classification, setClassification] = useState('');
  const fileInputRef = useRef(null);
  const nextUploadId = useRef(0);

  const formatSize = (bytes) => (bytes / (1024 * 1024)).toFixed(1) + ' MB';

  const submitFile = async (file) => {
    const uploadId = `${Date.now()}-${nextUploadId.current++}`;
    const pendingUpload = {
      id: uploadId,
      name: file.name,
      size: formatSize(file.size),
      status: 'uploading',
      error: null,
      type: file.name.toLowerCase().endsWith('.pdf') ? 'pdf' : 'image',
    };
    setUploads((prev) => [pendingUpload, ...prev]);

    try {
      const response = await uploadDocument(file, classification);
      setUploads((prev) =>
        prev.map((item) =>
          item.id === uploadId
            ? { ...item, status: response.status, document_id: response.document_id }
            : item
        )
      );
      if (onAddDocumentToQueue) {
        onAddDocumentToQueue(response);
      }
    } catch (err) {
      const message = err instanceof ApiError ? err.message : 'Upload failed.';
      setUploadError(message);
      setUploads((prev) =>
        prev.map((item) =>
          item.id === uploadId ? { ...item, status: 'failed', error: message } : item
        )
      );
    }
  };

  const submitFiles = (fileList) => {
    const files = Array.from(fileList);
    if (files.length === 0) return;

    if (!classification) {
      setUploadError('Select a data classification before uploading.');
      return;
    }

    setUploadError('');

    let toUpload = files;
    if (files.length > MAX_FILES_PER_DROP) {
      toUpload = files.slice(0, MAX_FILES_PER_DROP);
      setUploadError(
        `${files.length} files selected — only the first ${MAX_FILES_PER_DROP} were queued (limit is ${MAX_FILES_PER_DROP} files per drop).`
      );
    }

    // Fire one POST /documents per file, concurrently — the processing queue
    // already serializes the actual OCR/LLM work on the backend.
    toUpload.forEach((file) => {
      submitFile(file);
    });
  };

  const handleDragOver = (e) => {
    e.preventDefault();
    setDragging(true);
  };

  const handleDragLeave = () => {
    setDragging(false);
  };

  const handleDrop = (e) => {
    e.preventDefault();
    setDragging(false);
    if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
      submitFiles(e.dataTransfer.files);
    }
  };

  const handleFileChange = (e) => {
    if (e.target.files && e.target.files.length > 0) {
      submitFiles(e.target.files);
    }
    e.target.value = '';
  };

  const handleBrowseClick = (e) => {
    e.stopPropagation();
    fileInputRef.current?.click();
  };

  return (
    <div className="flex flex-col gap-6 w-full max-w-5xl mx-auto p-4 md:p-6 lg:p-8 animate-fadeIn">
      <div>
        <h2 className="font-headline-lg text-2xl font-bold text-foreground">Upload Center</h2>
        <p className="text-sm text-muted-foreground mt-1">
          Securely ingest business documents for AI analysis, OCR layout parsing, and field extraction.
        </p>
      </div>

      {uploadError && (
        <Alert variant="destructive">
          <AlertCircle className="w-4 h-4" />
          <AlertDescription>{uploadError}</AlertDescription>
        </Alert>
      )}

      {/* Data classification — required, no default (INV-6) */}
      <div className="flex flex-col gap-1.5">
        <label htmlFor="data-classification" className="text-xs font-label-md font-semibold text-foreground">
          Data classification <span className="text-destructive">*</span>
        </label>
        <select
          id="data-classification"
          value={classification}
          onChange={(e) => setClassification(e.target.value)}
          className="w-full max-w-sm rounded-lg border border-border/60 bg-card/40 px-3 py-2 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-primary/60"
        >
          <option value="" disabled>Select classification…</option>
          {CLASSIFICATIONS.map((c) => (
            <option key={c.value} value={c.value}>{c.label}</option>
          ))}
        </select>
        <p className="text-[11px] text-muted-foreground">
          Only <span className="font-semibold">public</span> and <span className="font-semibold">synthetic</span> documents may leave this machine. Choose <span className="font-semibold">restricted</span> for anything not yet looked at.
        </p>
      </div>

      {/* Hidden file input */}
      <input
        type="file"
        ref={fileInputRef}
        onChange={handleFileChange}
        className="hidden"
        accept=".pdf,.png,.jpg,.jpeg,.tiff"
        multiple
      />

      {/* Drag & Drop Upload Zone */}
      <div
        onDragOver={classification ? handleDragOver : undefined}
        onDragLeave={classification ? handleDragLeave : undefined}
        onDrop={classification ? handleDrop : undefined}
        onClick={classification ? handleBrowseClick : () => setUploadError('Select a data classification before uploading.')}
        aria-disabled={!classification}
        className={`relative rounded-xl p-10 border-2 border-dashed flex flex-col items-center justify-center text-center min-h-[280px] group transition-all duration-200 ${
          !classification
            ? 'cursor-not-allowed opacity-50 border-border/40 bg-card/20'
            : 'cursor-pointer'
        } ${
          classification && dragging
            ? 'border-primary bg-primary/10 scale-[0.99] shadow-inner'
            : classification
            ? 'border-border/60 hover:border-primary/60 bg-card/40 hover:bg-card/70'
            : ''
        }`}
      >
        <div className="p-4 rounded-full bg-primary/10 text-primary mb-4 group-hover:scale-110 transition-transform duration-200">
          <UploadCloud className="w-10 h-10" />
        </div>
        <h3 className="font-headline-md text-base font-semibold text-foreground mb-1">
          {dragging ? 'Drop document files here' : 'Drag and drop document files here'}
        </h3>
        <p className="text-xs text-muted-foreground mb-5">
          or click anywhere to browse from your device — select multiple files, up to {MAX_FILES_PER_DROP} at a time
        </p>
        <Button variant="outline" size="sm" onClick={handleBrowseClick} disabled={!classification} className="gap-2 mb-6">
          <FileUp className="w-4 h-4" />
          Browse Files
        </Button>
        <div className="flex items-center gap-2 text-[11px] font-label-md text-muted-foreground">
          <span>Supported formats:</span>
          <Badge variant="outline" className="text-[10px] uppercase">PDF</Badge>
          <Badge variant="outline" className="text-[10px] uppercase">PNG</Badge>
          <Badge variant="outline" className="text-[10px] uppercase">JPG</Badge>
          <Badge variant="outline" className="text-[10px] uppercase">TIFF</Badge>
        </div>
      </div>

      {/* Upload History Card */}
      <Card>
        <CardHeader className="py-4 border-b border-border/40 bg-muted/20">
          <div className="flex justify-between items-center">
            <CardTitle className="text-sm font-semibold">Session Upload History</CardTitle>
            <span className="text-xs font-label-md text-muted-foreground">Ingestion Log</span>
          </div>
        </CardHeader>
        <CardContent className="p-0 divide-y divide-border/20">
          {uploads.length === 0 ? (
            <div className="py-10 text-center text-muted-foreground text-xs">
              No files uploaded in this session yet.
            </div>
          ) : (
            uploads.map((upload) => (
              <div key={upload.id} className="p-4 flex items-center gap-4 hover:bg-muted/10 transition-colors">
                <div className="p-2.5 rounded-lg bg-muted/40 text-muted-foreground">
                  {upload.type === 'pdf' ? <FileText className="w-5 h-5 text-primary-light" /> : <ImageIcon className="w-5 h-5 text-accent-foreground" />}
                </div>
                <div className="flex-1 min-w-0">
                  <div className="flex justify-between items-center mb-1">
                    <span className="font-label-md text-xs font-semibold text-foreground truncate pr-4" title={upload.name}>{upload.name}</span>
                    {upload.status === 'uploading' ? (
                      <Loader2 className="w-4 h-4 text-primary animate-spin" />
                    ) : upload.status === 'failed' ? (
                      <Badge variant="destructive">Failed</Badge>
                    ) : (
                      <Badge variant="success" className="gap-1">
                        <FileCheck className="w-3 h-3" />
                        {upload.status}
                      </Badge>
                    )}
                  </div>
                  <p className="text-[11px] text-muted-foreground">
                    {upload.status === 'failed' ? (
                      <span className="text-destructive font-label-md">{upload.error}</span>
                    ) : upload.status === 'uploading' ? (
                      'Uploading document stream…'
                    ) : (
                      `${upload.size} • document_id: ${upload.document_id}`
                    )}
                  </p>
                </div>
              </div>
            ))
          )}
        </CardContent>
      </Card>
    </div>
  );
}
