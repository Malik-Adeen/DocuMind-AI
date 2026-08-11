import React from 'react';
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { FileText, CheckCircle2, Hourglass, CheckSquare, Brain, Users, DollarSign, Receipt, ArrowRight } from 'lucide-react';

export default function Dashboard({ onViewChange }) {
  const kpiData = [
    { label: 'Total Docs', value: '1.2M', desc: 'All time processed', icon: FileText },
    { label: 'Processed', value: '984K', desc: 'Successfully validated', icon: CheckCircle2 },
    { label: 'Queue', value: '1,240', desc: 'Active processing', icon: Hourglass, pulse: true },
    { label: 'Accuracy', value: '99.2%', desc: 'AI confidence target', icon: CheckSquare, highlight: true },
    { label: 'Confidence', value: '98.5%', desc: 'Avg. document score', icon: Brain },
    { label: 'Active Users', value: '342', desc: 'Enterprise seats occupied', icon: Users },
    { label: 'MRC', value: '$14.2K', desc: 'Monthly recurring cost', icon: DollarSign },
    { label: 'OTC', value: '$2.4K', desc: 'One-time cost', icon: Receipt },
  ];

  const recentDocs = [
    { id: 'DOC-9082', name: 'invoice_google_cloud_2026.pdf', type: 'Invoice', size: '1.2 MB', score: '99.4%', status: 'Processed' },
    { id: 'DOC-9081', name: 'service_agreement_v4_draft.pdf', type: 'Contract', size: '4.8 MB', score: '94.2%', status: 'In Review' },
    { id: 'DOC-9080', name: 'receipt_uber_taxicab_trip.jpg', type: 'Receipt', size: '540 KB', score: '98.8%', status: 'Processed' },
    { id: 'DOC-9079', name: 'vendor_onboarding_form_corp.pdf', type: 'Form', size: '2.1 MB', score: '87.5%', status: 'In Review' },
  ];

  return (
    <div className="flex flex-col gap-6 w-full max-w-7xl mx-auto p-4 md:p-6 lg:p-8 animate-fadeIn">
      {/* Header */}
      <div className="flex flex-col md:flex-row justify-between items-start md:items-end gap-4">
        <div>
          <h2 className="font-headline-lg text-2xl font-bold text-foreground">Welcome back, Admin</h2>
          <p className="text-sm text-muted-foreground mt-1">Operational summary of active document parsing and validation throughput.</p>
        </div>
        <Badge variant="outline" className="font-label-md py-1 px-3 text-xs">
          Oct 24, 2023
        </Badge>
      </div>

      {/* KPI Cards Grid */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        {kpiData.map((kpi, idx) => {
          const IconComponent = kpi.icon;
          return (
            <Card key={idx} className="p-4 hover:border-border/80 transition-all">
              <div className="flex items-center justify-between text-muted-foreground mb-2">
                <span className="font-label-md text-[11px] uppercase tracking-wider font-semibold">{kpi.label}</span>
                <IconComponent className="w-4 h-4 text-muted-foreground" />
              </div>
              <div className="flex items-center gap-2">
                <span className={`text-2xl font-bold font-display-lg ${kpi.highlight ? 'text-emerald-400' : 'text-foreground'}`}>
                  {kpi.value}
                </span>
                {kpi.pulse && (
                  <span className="relative flex h-2 w-2">
                    <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-primary opacity-75"></span>
                    <span className="relative inline-flex rounded-full h-2 w-2 bg-primary"></span>
                  </span>
                )}
              </div>
              <p className="text-[11px] text-muted-foreground mt-1">{kpi.desc}</p>
            </Card>
          );
        })}
      </div>

      {/* Throughput Graph & Recent Activity */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* SVG Throughput Chart */}
        <Card className="lg:col-span-2 p-6 flex flex-col gap-4">
          <div className="flex justify-between items-center">
            <div>
              <CardTitle className="text-base font-bold">Extraction Throughput</CardTitle>
              <p className="text-xs text-muted-foreground mt-0.5">Document volume processed over the last 6 months</p>
            </div>
            <select className="bg-background border border-input rounded-md px-2.5 py-1 text-xs text-foreground focus:outline-none">
              <option>Last 6 Months</option>
              <option>Last 30 Days</option>
            </select>
          </div>

          <div className="relative h-64 w-full flex items-center justify-center bg-muted/20 rounded-lg overflow-hidden border border-border/40">
            <svg viewBox="0 0 500 200" className="w-full h-full p-4 overflow-visible">
              <defs>
                <linearGradient id="chartGrad" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor="#588B76" stopOpacity="0.4" />
                  <stop offset="100%" stopColor="#588B76" stopOpacity="0.0" />
                </linearGradient>
              </defs>
              <line x1="0" y1="50" x2="500" y2="50" stroke="rgba(255,255,255,0.05)" strokeDasharray="3,3" />
              <line x1="0" y1="100" x2="500" y2="100" stroke="rgba(255,255,255,0.05)" strokeDasharray="3,3" />
              <line x1="0" y1="150" x2="500" y2="150" stroke="rgba(255,255,255,0.05)" strokeDasharray="3,3" />

              <path
                d="M 20 160 Q 100 120 180 140 T 340 70 T 480 50"
                fill="none"
                stroke="#588B76"
                strokeWidth="3"
                className="drop-shadow-[0_0_8px_rgba(88,139,118,0.4)]"
              />
              <path
                d="M 20 160 Q 100 120 180 140 T 340 70 T 480 50 L 480 190 L 20 190 Z"
                fill="url(#chartGrad)"
              />
              <circle cx="20" cy="160" r="4" fill="#588B76" />
              <circle cx="100" cy="122" r="4" fill="#588B76" />
              <circle cx="180" cy="140" r="4" fill="#588B76" />
              <circle cx="260" cy="100" r="4" fill="#588B76" />
              <circle cx="340" cy="70" r="4" fill="#588B76" />
              <circle cx="410" cy="55" r="4" fill="#588B76" />
              <circle cx="480" cy="50" r="4" fill="#588B76" />
            </svg>
            <div className="absolute bottom-2 left-4 right-4 flex justify-between font-label-md text-[10px] text-muted-foreground">
              <span>May</span>
              <span>Jun</span>
              <span>Jul</span>
              <span>Aug</span>
              <span>Sep</span>
              <span>Oct</span>
            </div>
          </div>
        </Card>

        {/* Recent Activity List */}
        <Card className="p-6 flex flex-col gap-4">
          <div>
            <CardTitle className="text-base font-bold">Recent Activity</CardTitle>
            <p className="text-xs text-muted-foreground mt-0.5">Live document parsing updates</p>
          </div>

          <div className="space-y-2.5">
            {recentDocs.map((doc, idx) => (
              <div key={idx} className="p-3 rounded-lg bg-muted/20 border border-border/30 hover:border-border/60 transition-colors space-y-1">
                <div className="flex justify-between items-center text-xs">
                  <span className="font-semibold text-foreground truncate max-w-[150px]">{doc.name}</span>
                  <Badge variant={doc.status === 'Processed' ? 'success' : 'warning'} className="text-[9px]">
                    {doc.status}
                  </Badge>
                </div>
                <div className="flex justify-between items-center text-[11px] text-muted-foreground">
                  <span className="font-label-md">{doc.id} • {doc.type}</span>
                  <span className="font-label-md text-primary-light">AI: {doc.score}</span>
                </div>
              </div>
            ))}
          </div>

          <Button
            variant="outline"
            className="w-full mt-auto text-xs gap-2"
            onClick={() => onViewChange?.('Documents')}
          >
            View Document History
            <ArrowRight className="w-3.5 h-3.5" />
          </Button>
        </Card>
      </div>
    </div>
  );
}
