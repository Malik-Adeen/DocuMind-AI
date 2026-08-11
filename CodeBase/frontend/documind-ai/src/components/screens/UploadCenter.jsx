import React, { useState, useRef } from 'react';
import { uploadDocument, ApiError } from '../../api/client';

const CLASSIFICATIONS = [
  { value: 'public', label: 'Public — publicly available document' },
  { value: 'synthetic', label: 'Synthetic — generated, no real party in it' },
  { value: 'restricted', label: 'Restricted — anything else' },
];

export default function UploadCenter({ onAddDocumentToQueue }) {
  const [uploads, setUploads] = useState([]);
  const [dragging, setDragging] = useState(false);
  const [dataClassification, setDataClassification] = useState('');
  const [classificationError, setClassificationError] = useState('');
  const fileInputRef = useRef(null);

  const formatSize = (bytes) => (bytes / (1024 * 1024)).toFixed(1) + ' MB';

  const submitFile = async (file) => {
    if (!dataClassification) {
      setClassificationError('Select a data classification before uploading.');
      return;
    }
    setClassificationError('');

    const uploadId = Date.now();
    const pendingUpload = {
      id: uploadId,
      name: file.name,
      size: formatSize(file.size),
      status: 'uploading',
      error: null,
      type: file.name.toLowerCase().endsWith('.pdf') ? 'pdf' : 'image',
    };
    setUploads(prev => [pendingUpload, ...prev]);

    try {
      const response = await uploadDocument(file, dataClassification);
      setUploads(prev =>
        prev.map(item =>
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
      setUploads(prev =>
        prev.map(item =>
          item.id === uploadId ? { ...item, status: 'failed', error: message } : item
        )
      );
    }
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
    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      submitFile(e.dataTransfer.files[0]);
    }
  };

  const handleFileChange = (e) => {
    if (e.target.files && e.target.files[0]) {
      submitFile(e.target.files[0]);
    }
    e.target.value = '';
  };

  const handleBrowseClick = (e) => {
    e.stopPropagation();
    fileInputRef.current.click();
  };

  return (
    <div className="flex flex-col gap-stack-lg w-full max-w-6xl mx-auto p-4 md:p-6 lg:p-10 animate-fadeIn">
      <div className="mb-stack-lg">
        <h2 className="font-headline-lg text-headline-lg text-white mb-2">Upload Center</h2>
        <p className="font-body-lg text-body-lg text-on-surface-variant">
          Securely ingest documents for AI analysis and data extraction.
        </p>
      </div>

      {/* Data classification selector */}
      <div className="glass-card rounded-xl p-6">
        <label className="block font-label-md text-[11px] text-on-surface-variant uppercase tracking-wider font-semibold mb-2" htmlFor="data_classification">
          Data classification (required)
        </label>
        <select
          id="data_classification"
          className="w-full bg-background border border-outline-variant rounded-lg px-3 py-2.5 text-xs text-on-surface focus:outline-none focus:border-primary transition-all"
          value={dataClassification}
          onChange={(e) => {
            setDataClassification(e.target.value);
            setClassificationError('');
          }}
        >
          <option value="">Select classification…</option>
          {CLASSIFICATIONS.map((c) => (
            <option key={c.value} value={c.value}>{c.label}</option>
          ))}
        </select>
        <p className="font-body-sm text-xs text-on-surface-variant mt-2">
          Immutable once set — reclassifying a document means uploading it again.
        </p>
        {classificationError && (
          <p className="font-label-md text-xs text-error mt-2">{classificationError}</p>
        )}
      </div>

      {/* Hidden file input */}
      <input
        type="file"
        ref={fileInputRef}
        onChange={handleFileChange}
        className="hidden"
        accept=".pdf,.png,.jpg,.jpeg,.tiff"
      />

      {/* Upload Zone */}
      <div
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        onDrop={handleDrop}
        onClick={handleBrowseClick}
        className={`glass-card relative rounded-xl p-stack-lg mb-stack-lg border-2 border-dashed flex flex-col items-center justify-center text-center min-h-[300px] cursor-pointer group transition-all duration-300 ${
          dragging ? 'border-primary bg-primary-container/10 scale-[0.99] shadow-inner' : 'border-outline-variant hover:border-primary/60'
        }`}
      >
        <div className="bg-primary-container/10 p-4 rounded-full mb-6 group-hover:scale-110 transition-transform duration-300">
          <span className="material-symbols-outlined text-5xl text-primary" style={{ fontVariationSettings: "'FILL' 1" }}>
            cloud_upload
          </span>
        </div>
        <h3 className="font-headline-md text-headline-md text-on-surface mb-stack-sm">
          {dragging ? 'Drop the file here' : 'Drag and drop files here'}
        </h3>
        <p className="font-body-md text-body-md text-on-surface-variant mb-stack-md">
          or click to browse from your computer
        </p>
        <button
          onClick={handleBrowseClick}
          className="bg-transparent border border-outline-variant hover:bg-white/5 text-on-surface font-label-md text-label-md py-2 px-6 rounded-lg transition-colors mb-stack-lg cursor-pointer"
        >
          Browse Files
        </button>
        <div className="flex items-center gap-4 text-outline font-label-md text-xs">
          <span>Supported types:</span>
          <span className="bg-surface-container-high px-2 py-1 rounded">PDF</span>
          <span className="bg-surface-container-high px-2 py-1 rounded">PNG</span>
          <span className="bg-surface-container-high px-2 py-1 rounded">JPG</span>
          <span className="bg-surface-container-high px-2 py-1 rounded">TIFF</span>
        </div>
      </div>

      {/* Upload History */}
      <div className="glass-card rounded-xl overflow-hidden relative">
        <div className="px-6 py-4 border-b border-white/10 flex justify-between items-center bg-surface-container-low/50">
          <h3 className="font-headline-md text-headline-md text-on-surface text-xl">Recent Uploads</h3>
          <span className="text-on-surface-variant font-label-md text-xs">History Log</span>
        </div>
        <div className="flex flex-col">
          {uploads.length === 0 ? (
            <div className="px-6 py-12 text-center text-on-surface-variant font-body-md">
              No uploads yet this session.
            </div>
          ) : (
            uploads.map((upload) => (
              <div key={upload.id} className="px-6 py-4 border-b border-white/5 flex items-center gap-4 hover:bg-white/5 transition-colors">
                <div className={`p-3 rounded-lg ${upload.type === 'pdf' ? 'bg-surface-container-highest text-secondary' : 'bg-surface-container-highest text-outline'}`}>
                  <span className="material-symbols-outlined">
                    {upload.type === 'pdf' ? 'picture_as_pdf' : 'image'}
                  </span>
                </div>
                <div className="flex-1 min-w-0">
                  <div className="flex justify-between items-center mb-1">
                    <span className="font-label-md text-label-md text-on-surface truncate pr-4">{upload.name}</span>
                    {upload.status === 'uploading' ? (
                      <div className="w-4 h-4 rounded-full border-2 border-primary/30 border-t-primary animate-spin"></div>
                    ) : upload.status === 'failed' ? (
                      <span className="material-symbols-outlined text-error text-sm">error</span>
                    ) : (
                      <span className="material-symbols-outlined text-green-400 text-sm">check_circle</span>
                    )}
                  </div>
                  <div className="font-body-sm text-xs text-on-surface-variant mt-1">
                    {upload.status === 'failed' ? (
                      <span className="text-error">{upload.error}</span>
                    ) : upload.status === 'uploading' ? (
                      'Uploading…'
                    ) : (
                      `${upload.size} • status: ${upload.status}`
                    )}
                  </div>
                </div>
              </div>
            ))
          )}
        </div>
      </div>
    </div>
  );
}
