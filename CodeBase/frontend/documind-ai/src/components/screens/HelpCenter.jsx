import React, { useState } from 'react';

export default function HelpCenter() {
  const [searchTerm, setSearchTerm] = useState('');
  const [openFaq, setOpenFaq] = useState(null);

  const faqs = [
    { q: 'How does DocuMind AI classify document types automatically?', a: 'Our system runs multi-modal deep learning models. By checking semantic layout markers, corporate logos, and vocabulary density, it determines with high confidence whether a document is an Invoice, Purchase Order, Contract, or custom type.' },
    { q: 'What is the pricing model for bulk OCR and extraction processing?', a: 'Pricing is tiered based on monthly document volume. Standard API usage costs $0.05 per document. Large enterprise volumes (above 10,000 documents/month) qualify for discounted pricing packages starting at $0.01 per document.' },
    { q: 'How secure is document storage in the cloud environment?', a: 'Every document uploaded is encrypted in transit using TLS 1.3 and at rest with AES-256 keys. We comply with GDPR, HIPAA, and SOC2 standards, ensuring that data is sandboxed and never shared for model retraining.' },
    { q: 'Can I integrate custom downstream webhook handlers?', a: 'Yes! Under Settings -> API Keys, you can generate keys. You can also configure Webhooks in the Developer Console to push extracted JSON records to your REST endpoints or database handlers in real-time.' }
  ];

  const filteredFaqs = faqs.filter(faq =>
    faq.q.toLowerCase().includes(searchTerm.toLowerCase()) ||
    faq.a.toLowerCase().includes(searchTerm.toLowerCase())
  );

  return (
    <div className="flex flex-col gap-stack-lg w-full max-w-7xl mx-auto p-4 md:p-6 lg:p-10 animate-fadeIn">
      {/* Hero Search Section */}
      <section className="max-w-4xl mx-auto mt-6 mb-10 text-center flex flex-col gap-4">
        <h2 className="font-display-lg text-3xl md:text-5xl text-white font-bold tracking-tight">How can we help?</h2>
        <p className="font-body-lg text-base md:text-lg text-on-surface-variant max-w-2xl mx-auto">
          Search our knowledge base or browse categories below to find answers.
        </p>
        <div className="relative max-w-2xl mx-auto w-full mt-4">
          <span className="material-symbols-outlined absolute left-4 top-1/2 -translate-y-1/2 text-outline text-2xl">search</span>
          <input 
            className="w-full bg-[#0F172A] border border-[#1E293B] rounded-xl py-3.5 pl-14 pr-4 font-body-md text-sm text-on-surface focus:outline-none focus:border-primary-container transition-all" 
            placeholder="Search documentation, tutorials, or FAQs..." 
            type="text"
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
          />
        </div>
      </section>

      {/* Categories Grid */}
      <section className="max-w-6xl mx-auto grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-stack-md">
        
        {/* Documentation */}
        <a 
          href="#docs"
          onClick={(e) => { e.preventDefault(); alert('Redirecting to full Documentation guides...'); }}
          className="glass-card p-6 rounded-xl flex flex-col hover:-translate-y-1 hover:shadow-lg transition-all duration-300 group relative overflow-hidden border border-transparent hover:border-primary/30"
        >
          <div className="absolute top-0 right-0 w-32 h-32 bg-primary/5 rounded-full blur-2xl -mr-10 -mt-10 transition-opacity group-hover:bg-primary/10"></div>
          <div className="w-12 h-12 rounded-lg bg-surface-container-high flex items-center justify-center mb-4 border border-white/5 text-primary">
            <span className="material-symbols-outlined text-2xl">menu_book</span>
          </div>
          <h3 className="font-headline-md text-base text-white font-semibold mb-2 group-hover:text-primary transition-colors">Documentation</h3>
          <p className="font-body-sm text-xs text-on-surface-variant flex-1 leading-relaxed">
            Detailed guides on using DocuMind AI's features, from data extraction to complex analysis workflows.
          </p>
          <div className="mt-4 flex items-center gap-2 text-primary font-label-md text-xs font-semibold">
            Browse Docs <span className="material-symbols-outlined text-sm group-hover:translate-x-1 transition-transform">arrow_forward</span>
          </div>
        </a>

        {/* API Reference */}
        <a 
          href="#api"
          onClick={(e) => { e.preventDefault(); alert('Redirecting to developer API Reference manual...'); }}
          className="glass-card p-6 rounded-xl flex flex-col hover:-translate-y-1 hover:shadow-lg transition-all duration-300 group relative overflow-hidden border border-transparent hover:border-secondary/30"
        >
          <div className="absolute top-0 right-0 w-32 h-32 bg-secondary-container/5 rounded-full blur-2xl -mr-10 -mt-10 transition-opacity group-hover:bg-secondary-container/10"></div>
          <div className="w-12 h-12 rounded-lg bg-surface-container-high flex items-center justify-center mb-4 border border-white/5 text-secondary">
            <span className="material-symbols-outlined text-2xl">api</span>
          </div>
          <h3 className="font-headline-md text-base text-white font-semibold mb-2 group-hover:text-secondary transition-colors">API Reference</h3>
          <p className="font-body-sm text-xs text-on-surface-variant flex-1 leading-relaxed">
            Integrate our intelligence engine into your own applications with comprehensive endpoint documentation.
          </p>
          <div className="mt-4 flex items-center gap-2 text-secondary font-label-md text-xs font-semibold">
            View API <span className="material-symbols-outlined text-sm group-hover:translate-x-1 transition-transform">arrow_forward</span>
          </div>
        </a>

        {/* Tutorials */}
        <a 
          href="#tutorials"
          onClick={(e) => { e.preventDefault(); alert('Redirecting to video Tutorial hub...'); }}
          className="glass-card p-6 rounded-xl flex flex-col hover:-translate-y-1 hover:shadow-lg transition-all duration-300 group relative overflow-hidden border border-transparent hover:border-tertiary/30"
        >
          <div className="absolute top-0 right-0 w-32 h-32 bg-tertiary/5 rounded-full blur-2xl -mr-10 -mt-10 transition-opacity group-hover:bg-tertiary/10"></div>
          <div className="w-12 h-12 rounded-lg bg-surface-container-high flex items-center justify-center mb-4 border border-white/5 text-tertiary">
            <span className="material-symbols-outlined text-2xl">play_circle</span>
          </div>
          <h3 className="font-headline-md text-base text-white font-semibold mb-2 group-hover:text-tertiary transition-colors">Tutorials</h3>
          <p className="font-body-sm text-xs text-on-surface-variant flex-1 leading-relaxed">
            Step-by-step video guides and walkthroughs to help you master advanced document processing techniques.
          </p>
          <div className="mt-4 flex items-center gap-2 text-tertiary font-label-md text-xs font-semibold">
            Watch Tutorials <span className="material-symbols-outlined text-sm group-hover:translate-x-1 transition-transform">arrow_forward</span>
          </div>
        </a>

        {/* FAQ */}
        <a 
          href="#faq"
          onClick={(e) => { e.preventDefault(); document.getElementById('faq-section').scrollIntoView({ behavior: 'smooth' }); }}
          className="glass-card p-6 rounded-xl flex flex-col hover:-translate-y-1 hover:shadow-lg transition-all duration-300 group relative overflow-hidden border border-transparent hover:border-primary/30"
        >
          <div className="absolute top-0 right-0 w-32 h-32 bg-inverse-primary/5 rounded-full blur-2xl -mr-10 -mt-10 transition-opacity group-hover:bg-inverse-primary/10"></div>
          <div className="w-12 h-12 rounded-lg bg-surface-container-high flex items-center justify-center mb-4 border border-white/5 text-inverse-primary">
            <span className="material-symbols-outlined text-2xl">quiz</span>
          </div>
          <h3 className="font-headline-md text-base text-white font-semibold mb-2 group-hover:text-inverse-primary transition-colors">FAQ</h3>
          <p className="font-body-sm text-xs text-on-surface-variant flex-1 leading-relaxed">
            Answers to common questions about billing, account management, and general platform usage.
          </p>
          <div className="mt-4 flex items-center gap-2 text-inverse-primary font-label-md text-xs font-semibold">
            Read FAQs <span className="material-symbols-outlined text-sm group-hover:translate-x-1 transition-transform">arrow_forward</span>
          </div>
        </a>
      </section>

      {/* Accordion FAQ Section */}
      <section id="faq-section" className="max-w-4xl mx-auto mt-10 mb-10 w-full flex flex-col gap-4">
        <h3 className="font-headline-md text-lg text-white font-semibold border-b border-white/10 pb-2">Frequently Asked Questions</h3>
        <div className="flex flex-col gap-3">
          {filteredFaqs.length === 0 ? (
            <p className="text-on-surface-variant text-sm py-4">No matching questions found.</p>
          ) : (
            filteredFaqs.map((faq, index) => (
              <div 
                key={index} 
                className="glass-card rounded-lg overflow-hidden border border-white/5 transition-all"
              >
                <button 
                  onClick={() => setOpenFaq(openFaq === index ? null : index)}
                  className="w-full flex justify-between items-center p-4 text-left font-body-md text-sm text-white font-semibold hover:bg-white/5 transition-colors cursor-pointer"
                >
                  <span>{faq.q}</span>
                  <span className={`material-symbols-outlined transition-transform text-outline-variant ${openFaq === index ? 'rotate-180' : ''}`}>
                    expand_more
                  </span>
                </button>
                {openFaq === index && (
                  <div className="p-4 bg-[#0F172A]/50 border-t border-white/5 text-on-surface-variant text-xs leading-relaxed animate-fadeIn">
                    {faq.a}
                  </div>
                )}
              </div>
            ))
          )}
        </div>
      </section>

      {/* Contact Support Banner */}
      <section className="max-w-4xl mx-auto w-full mt-6">
        <div className="glass-card p-6 rounded-2xl flex flex-col md:flex-row items-center justify-between gap-6 border border-white/15 relative overflow-hidden">
          <div className="absolute inset-0 bg-gradient-to-r from-primary-container to-secondary-container opacity-10"></div>
          <div className="relative z-10 flex-1 text-center md:text-left">
            <h3 className="font-headline-lg text-lg text-white font-bold mb-2">Need support? Contact our team</h3>
            <p className="font-body-md text-xs text-on-surface-variant leading-relaxed">
              Our engineers are standing by to help you solve complex integration issues.
            </p>
          </div>
          <div className="relative z-10">
            <button 
              onClick={() => alert('Support ticket system initialized...')}
              className="bg-gradient-to-r from-primary-container to-secondary-container text-white font-label-md text-xs font-semibold px-6 py-3 rounded-lg hover:shadow-[0_0_20px_rgba(79,70,229,0.6)] transition-all flex items-center gap-2 whitespace-nowrap cursor-pointer"
            >
              <span className="material-symbols-outlined text-lg">support_agent</span>
              Open Support Ticket
            </button>
          </div>
        </div>
      </section>
    </div>
  );
}
