import React, { useRef, useState } from 'react';
import { 
  FileSearch, 
  RotateCcw, 
  Sparkles, 
  Building2, 
  Mail, 
  Globe, 
  MapPin, 
  Briefcase, 
  DollarSign, 
  FileText,
  AlertCircle,
  Upload,
  FileCheck2,
  X,
  CheckCircle2,
  Pencil,
} from 'lucide-react';
import LoadingState from '../components/LoadingState';
import api from '../services/api';

const SAMPLE_PRESETS = [
  {
    label: '1. Legitimate Internship',
    data: {
      job_title: 'Junior Software Engineer Intern',
      company_name: 'Acme Technologies Inc',
      recruiter_email: 'careers@acme-tech.org',
      company_website: 'https://acme-tech.org',
      location: 'San Francisco, CA (Hybrid)',
      employment_type: 'Full-time',
      salary: '$35 - $45 per hour',
      job_description: 'Acme Technologies is seeking a motivated Software Engineering Intern to join our cloud infrastructure team. You will collaborate with senior engineers to build scalable RESTful APIs, write unit and integration tests, and participate in daily agile standups. We offer competitive stipend, mentorship, and full health insurance.',
      requirements: 'Enrolled in Computer Science or related degree. Proficient in Python or TypeScript. Understanding of Git and basic web architectures.',
      benefits: 'Health insurance, 401(k) matching, transit stipend, flexible hours.'
    }
  },
  {
    label: '2. Payment Scam',
    data: {
      job_title: 'Executive Virtual Administrative Assistant',
      company_name: 'Global Peak Logistics',
      recruiter_email: 'recruiting.globalpeak@gmail.com',
      company_website: 'http://globalpeaklogistics-now.xyz',
      location: 'Remote / Work from home',
      employment_type: 'Full-time',
      salary: '$75 per hour ($150,000 / year)',
      job_description: 'URGENT HIRING! We need an immediate Virtual Assistant. No experience needed! Immediate start with high weekly payout. Note: candidates must send a mandatory $250 background verification registration fee and equipment insurance deposit via Wire Transfer, Zelle, or Bitcoin before dispatch of home-office Apple laptop.',
      requirements: 'Must have laptop and phone. Send wire transfer confirmation upon selection.',
      benefits: 'Immediate payment, bonuses, flexible working schedule.'
    }
  },
  {
    label: '3. Unrealistic Salary / Phishing',
    data: {
      job_title: 'Entry-Level Data Entry Clerk',
      company_name: 'Apex Fast Express',
      recruiter_email: 'hr-jobs-entry@yahoo.com',
      company_website: '',
      location: 'Work From Home (Anywhere)',
      employment_type: 'Part-time',
      salary: '$9,500 monthly ($114,000/yr for 10 hours/week)',
      job_description: 'Immediate position available! Guaranteed employment without technical interview. Earn $9,500 every month for simple copy paste work. Telegram interview required immediately. Please send photos of front and back of your driver license and Social Security Card to hr_manager_fast on Telegram.',
      requirements: 'No skills or experience required. Any age or background accepted.',
      benefits: 'Instant daily wire payouts.'
    }
  },
  {
    label: '4. Recruiter Domain Mismatch',
    data: {
      job_title: 'Senior Cloud Architect',
      company_name: 'Microsoft Corporation',
      recruiter_email: 'recruiter.alex.smith@free-hiring-portal.net',
      company_website: 'https://microsoft.com',
      location: 'Redmond, WA',
      employment_type: 'Full-time',
      salary: '$165,000 - $195,000',
      job_description: 'Join Microsoft Azure cloud architecture team. Designing resilient enterprise cloud deployments across multi-region data centers. You will work on Kubernetes containerization, automated CI/CD pipelines, and zero-trust security postures.',
      requirements: '7+ years cloud engineering experience, Azure Solutions Architect Expert certification preferred.',
      benefits: 'Comprehensive health coverage, 401(k), equity incentives.'
    }
  },
  {
    label: '5. Small Legitimate Business (Sparse Web Presence)',
    data: {
      job_title: 'Local Bakery Operations Lead',
      company_name: 'Sunrise Artisanal Breads',
      recruiter_email: 'owner@sunriselocalbreads.com',
      company_website: 'https://sunriselocalbreads.com',
      location: 'Austin, TX',
      employment_type: 'Full-time',
      salary: '$48,000 - $55,000 per year',
      job_description: 'Sunrise Artisanal Breads is a local family-owned bakery looking for an experienced head of operations to manage morning baking shifts, local wholesale supplier orders, and storefront inventory. We value craftsmanship, reliability, and teamwork.',
      requirements: '2+ years food service or bakery management experience. Food handler certification.',
      benefits: 'Paid time off, meal allowance, store discount.'
    }
  }
];

const SUPPORTED_EXTENSIONS = ['pdf', 'png', 'jpg', 'jpeg', 'webp', 'docx', 'txt'];

function formatFileSize(size) {
  if (size < 1024) return `${size} B`;
  if (size < 1024 * 1024) return `${(size / 1024).toFixed(1)} KB`;
  return `${(size / (1024 * 1024)).toFixed(1)} MB`;
}

export default function AnalyzeJob({ onAnalysisComplete }) {
  const [formData, setFormData] = useState({
    job_title: '',
    company_name: '',
    recruiter_email: '',
    company_website: '',
    location: '',
    employment_type: 'Full-time',
    salary: '',
    job_description: '',
    requirements: '',
    benefits: ''
  });

  const [loading, setLoading] = useState(false);
  const [analysisMode, setAnalysisMode] = useState('job');
  const [error, setError] = useState(null);
  const [selectedFile, setSelectedFile] = useState(null);
  const [extraction, setExtraction] = useState(null);
  const [uploadStatus, setUploadStatus] = useState('idle');
  const [uploadProgress, setUploadProgress] = useState(0);
  const [uploadError, setUploadError] = useState('');
  const [draggingFile, setDraggingFile] = useState(false);
  const [documentSource, setDocumentSource] = useState(false);
  const fileInputRef = useRef(null);
  const descriptionRef = useRef(null);

  const handleChange = (e) => {
    const { name, value } = e.target;
    setFormData(prev => ({ ...prev, [name]: value }));
  };

  const handleClear = () => {
    setFormData({
      job_title: '',
      company_name: '',
      recruiter_email: '',
      company_website: '',
      location: '',
      employment_type: 'Full-time',
      salary: '',
      job_description: '',
      requirements: '',
      benefits: ''
    });
    setError(null);
    setSelectedFile(null);
    setExtraction(null);
    setUploadStatus('idle');
    setUploadProgress(0);
    setUploadError('');
    setDocumentSource(false);
  };

  const handleApplyPreset = (preset) => {
    setFormData(preset.data);
    setError(null);
    setSelectedFile(null);
    setExtraction(null);
    setUploadStatus('idle');
    setUploadProgress(0);
    setUploadError('');
    setDocumentSource(false);
  };

  const handleFile = async (file) => {
    if (!file) return;
    if (uploadStatus === 'uploading') return;
    const extension = file.name.split('.').pop()?.toLowerCase();
    if (!SUPPORTED_EXTENSIONS.includes(extension)) {
      setUploadError('Unsupported file type. Choose a PDF, image, DOCX, or TXT file.');
      return;
    }

    if (documentSource) {
      setFormData((previous) => ({ ...previous, job_description: '' }));
    }
    setDocumentSource(false);
    setSelectedFile({ name: file.name, size: file.size });
    setExtraction(null);
    setUploadStatus('uploading');
    setUploadProgress(0);
    setUploadError('');
    setError(null);

    try {
      const result = await api.extractDocument(file, setUploadProgress);
      if (!result.text?.trim()) {
        throw new Error('No readable text was found. Upload a clearer document or enter the job description manually.');
      }
      setExtraction(result);
      setDocumentSource(true);
      setUploadStatus('success');
      setFormData((previous) => ({
        ...previous,
        job_description: result.text,
      }));
      setUploadProgress(100);
    } catch (uploadFailure) {
      setUploadStatus('error');
      setUploadError(uploadFailure.message || 'Document extraction failed. Try another file or enter the description manually.');
    }
  };

  const handleFileInput = (event) => {
    const [file] = event.target.files || [];
    event.target.value = '';
    handleFile(file);
  };

  const handleRemoveFile = () => {
    setSelectedFile(null);
    setExtraction(null);
    setUploadStatus('idle');
    setUploadProgress(0);
    setUploadError('');
    setDocumentSource(false);
    if (documentSource) {
      setFormData((previous) => ({ ...previous, job_description: '' }));
    }
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (uploadStatus === 'uploading') {
      setError('Wait for document extraction to finish before starting analysis.');
      return;
    }
    if (!formData.job_description.trim()) {
      setError('Enter a job description or upload a document with readable text before analysis.');
      return;
    }
    if (!formData.job_title.trim() && !documentSource) {
      setError('Please provide a Job Title before analysis.');
      return;
    }

    setLoading(true);
    setError(null);

    try {
      const result = await api.analyzeJob({
        ...formData,
        analysis_mode: analysisMode,
        job_title: formData.job_title.trim() || 'Uploaded Job Advertisement',
        document_source: documentSource,
      });
      onAnalysisComplete(result);
    } catch (err) {
      setError(err.message || 'Analysis failed. Please check backend connection.');
    } finally {
      setLoading(false);
    }
  };

  if (loading) {
    return <LoadingState message="Analyzing recruitment signals..." />;
  }

  return (
    <div className="max-w-4xl mx-auto space-y-6">
      {/* Header card */}
      <div className="bg-shield-card border border-shield-border rounded-lg p-6">
        <div className="flex items-center gap-2 mb-2">
          <span className="text-xs uppercase font-mono px-2 py-0.5 rounded bg-cyan-950 text-cyan-400 border border-cyan-500/30">
            Multi-Signal Detection
          </span>
          <span className="text-xs text-slate-400">• Evidence Synthesis</span>
        </div>
        <h2 className="text-xl font-bold text-slate-100">Analyze Recruitment Offer</h2>
        <p className="text-xs text-slate-300 mt-1">
          Evaluate job, recruiter and company signals using multi-evidence AI.
          Our decoupled intelligence engine cross-checks linguistic fraud patterns, recruiter identity,
          domain DNS/MX health, and salary realism.
        </p>

        <fieldset className="mt-4 rounded border border-shield-border bg-shield-surface p-3">
          <legend className="px-1 text-[11px] font-mono uppercase tracking-wide text-slate-400">
            Analysis privacy
          </legend>
          <div className="flex flex-col gap-2 sm:flex-row">
            <label className="flex items-start gap-2 rounded p-2 text-xs text-slate-300">
              <input
                type="radio"
                name="analysis-mode"
                value="job"
                checked={analysisMode === 'job'}
                onChange={() => setAnalysisMode('job')}
                className="mt-0.5 accent-cyan-500"
              />
              <span>
                <span className="block font-semibold text-slate-100">Job analysis</span>
                Existing verification behavior runs as part of analysis.
              </span>
            </label>
            <label className="flex items-start gap-2 rounded p-2 text-xs text-slate-300">
              <input
                type="radio"
                name="analysis-mode"
                value="private_email"
                checked={analysisMode === 'private_email'}
                onChange={() => setAnalysisMode('private_email')}
                className="mt-0.5 accent-cyan-500"
              />
              <span>
                <span className="block font-semibold text-slate-100">Private email analysis</span>
                Runs locally first. No external verification occurs unless you approve selected checks afterward.
              </span>
            </label>
          </div>
        </fieldset>

        {/* Quick Test Presets */}
        <div className="mt-4 pt-4 border-t border-shield-border/60">
          <div className="text-[11px] font-mono uppercase text-slate-400 mb-2 flex items-center gap-1.5">
            <Sparkles className="w-3.5 h-3.5 text-cyan-400" />
            <span>Load Quick Test Cases:</span>
          </div>
          <div className="flex flex-wrap gap-2">
            {SAMPLE_PRESETS.map((preset, idx) => (
              <button
                key={idx}
                type="button"
                onClick={() => handleApplyPreset(preset)}
                disabled={uploadStatus === 'uploading'}
                className="px-2.5 py-1 rounded text-xs border border-shield-border bg-shield-surface hover:border-cyan-500/40 hover:text-cyan-300 text-slate-300 transition-all font-sans"
              >
                {preset.label}
              </button>
            ))}
          </div>
        </div>
      </div>

      <section
        className={`bg-shield-card border rounded-lg p-5 transition-colors ${
          draggingFile ? 'border-cyan-400 bg-cyan-950/20' : 'border-shield-border'
        }`}
        onDragEnter={(event) => {
          event.preventDefault();
          setDraggingFile(true);
        }}
        onDragOver={(event) => event.preventDefault()}
        onDragLeave={(event) => {
          if (!event.currentTarget.contains(event.relatedTarget)) setDraggingFile(false);
        }}
        onDrop={(event) => {
          event.preventDefault();
          setDraggingFile(false);
          handleFile(event.dataTransfer.files?.[0]);
        }}
        aria-label="Upload a job advertisement"
      >
        <input
          ref={fileInputRef}
          type="file"
          accept=".pdf,.png,.jpg,.jpeg,.webp,.docx,.txt"
          onChange={handleFileInput}
          className="sr-only"
          tabIndex={-1}
        />
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
          <div className="flex items-start gap-3">
            <div className="rounded-lg bg-cyan-950/60 p-2.5 text-cyan-300">
              <Upload className="w-5 h-5" />
            </div>
            <div>
              <h3 className="text-sm font-semibold text-slate-100">Upload a job advertisement</h3>
              <p className="text-xs text-slate-400 mt-1">
                Drop a file here or browse. PDF, PNG, JPG, WEBP, DOCX, and TXT · up to 10 MB.
              </p>
              <p className="text-[11px] text-slate-500 mt-1">
                Image and scanned PDF OCR runs locally. Uploaded file contents are not sent to external AI services.
              </p>
            </div>
          </div>
          <button
            type="button"
            onClick={() => fileInputRef.current?.click()}
            disabled={uploadStatus === 'uploading'}
            className="shrink-0 inline-flex items-center justify-center gap-2 rounded border border-cyan-500/40 bg-cyan-950/30 px-4 py-2 text-xs font-medium text-cyan-200 hover:bg-cyan-950/60 disabled:opacity-50"
          >
            <Upload className="w-3.5 h-3.5" />
            {selectedFile ? 'Replace file' : 'Browse files'}
          </button>
        </div>

        {selectedFile && (
          <div className="mt-4 rounded-lg border border-shield-border bg-shield-surface p-3">
            <div className="flex items-start justify-between gap-3">
              <div className="flex min-w-0 items-center gap-2.5">
                {uploadStatus === 'success'
                  ? <FileCheck2 className="w-4 h-4 shrink-0 text-emerald-400" />
                  : <FileText className="w-4 h-4 shrink-0 text-cyan-400" />}
                <div className="min-w-0">
                  <p className="truncate text-xs font-medium text-slate-200">{selectedFile.name}</p>
                  <p className="text-[11px] text-slate-500">{formatFileSize(selectedFile.size)}</p>
                </div>
              </div>
              <button
                type="button"
                onClick={handleRemoveFile}
                disabled={uploadStatus === 'uploading'}
                className="inline-flex shrink-0 items-center gap-1 rounded px-2 py-1 text-[11px] text-slate-400 hover:bg-rose-950/40 hover:text-rose-300"
                aria-label="Remove uploaded file and extracted text"
              >
                <X className="w-3.5 h-3.5" />
                Remove
              </button>
            </div>

            {uploadStatus === 'uploading' && (
              <div className="mt-3" aria-live="polite">
                <div className="mb-1 flex justify-between text-[11px] text-slate-400">
                  <span>Uploading and extracting text…</span>
                  <span>{uploadProgress}%</span>
                </div>
                <div
                  className="h-1.5 overflow-hidden rounded-full bg-slate-700"
                  role="progressbar"
                  aria-label="Document upload progress"
                  aria-valuemin={0}
                  aria-valuemax={100}
                  aria-valuenow={uploadProgress}
                >
                  <div
                    className="h-full rounded-full bg-cyan-400 transition-all"
                    style={{ width: `${uploadProgress}%` }}
                  />
                </div>
              </div>
            )}

            {uploadStatus === 'success' && extraction && (
              <div className="mt-3 border-t border-shield-border pt-3" aria-live="polite">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <p className="inline-flex items-center gap-1.5 text-xs text-emerald-300">
                    <CheckCircle2 className="w-3.5 h-3.5" />
                    Text extracted successfully
                  </p>
                  <button
                    type="button"
                    onClick={() => descriptionRef.current?.focus()}
                    className="inline-flex items-center gap-1.5 text-xs text-cyan-300 hover:text-cyan-200"
                  >
                    <Pencil className="w-3.5 h-3.5" />
                    Edit extracted text
                  </button>
                </div>
                <p className="mt-2 max-h-24 overflow-y-auto whitespace-pre-wrap break-words text-xs leading-relaxed text-slate-400">
                  {formData.job_description.slice(0, 700)}
                  {formData.job_description.length > 700 ? '…' : ''}
                </p>
                <p className="mt-2 text-[11px] text-slate-500">
                  {extraction.extraction_method.replaceAll('_', ' ')}
                  {extraction.ocr_pages?.length
                    ? ` · OCR on ${extraction.ocr_pages.length} page${extraction.ocr_pages.length === 1 ? '' : 's'}`
                    : ''}
                  {' · Review and edit the job description below before analysis.'}
                </p>
              </div>
            )}
          </div>
        )}

        {uploadError && (
          <div className="mt-3 flex items-start gap-2 rounded border border-rose-500/30 bg-rose-950/20 p-3 text-xs text-rose-300" role="alert">
            <AlertCircle className="mt-0.5 h-4 w-4 shrink-0" />
            <span>{uploadError}</span>
          </div>
        )}
      </section>

      {error && (
        <div className="bg-rose-950/30 border border-rose-500/40 rounded-lg p-4 flex items-start gap-3 text-xs text-rose-300">
          <AlertCircle className="w-4 h-4 text-rose-400 mt-0.5 shrink-0" />
          <span>{error}</span>
        </div>
      )}

      {/* Main Analysis Form */}
      <form onSubmit={handleSubmit} className="bg-shield-card border border-shield-border rounded-lg p-6 space-y-5">
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {/* Job Title */}
          <div>
            <label className="block text-xs font-semibold text-slate-300 mb-1.5 flex items-center gap-1.5">
              <Briefcase className="w-3.5 h-3.5 text-cyan-400" /> Job Title *
            </label>
            <input
              type="text"
              name="job_title"
              value={formData.job_title}
              onChange={handleChange}
              placeholder="e.g. Lead Cybersecurity Analyst"
              required={!documentSource}
              className="w-full bg-shield-surface border border-shield-border focus:border-cyan-500 rounded px-3 py-2 text-xs text-slate-100 placeholder-slate-500 outline-none"
            />
          </div>

          {/* Company Name */}
          <div>
            <label className="block text-xs font-semibold text-slate-300 mb-1.5 flex items-center gap-1.5">
              <Building2 className="w-3.5 h-3.5 text-cyan-400" /> Company Name
            </label>
            <input
              type="text"
              name="company_name"
              value={formData.company_name}
              onChange={handleChange}
              placeholder="e.g. CyberDefense Systems Ltd"
              className="w-full bg-shield-surface border border-shield-border focus:border-cyan-500 rounded px-3 py-2 text-xs text-slate-100 placeholder-slate-500 outline-none"
            />
          </div>

          {/* Recruiter Email */}
          <div>
            <label className="block text-xs font-semibold text-slate-300 mb-1.5 flex items-center gap-1.5">
              <Mail className="w-3.5 h-3.5 text-cyan-400" /> Recruiter Email
            </label>
            <input
              type="email"
              name="recruiter_email"
              value={formData.recruiter_email}
              onChange={handleChange}
              placeholder="e.g. talent@cyberdefensesystems.com"
              className="w-full bg-shield-surface border border-shield-border focus:border-cyan-500 rounded px-3 py-2 text-xs text-slate-100 placeholder-slate-500 outline-none"
            />
          </div>

          {/* Company Website */}
          <div>
            <label className="block text-xs font-semibold text-slate-300 mb-1.5 flex items-center gap-1.5">
              <Globe className="w-3.5 h-3.5 text-cyan-400" /> Company Website
            </label>
            <input
              type="text"
              name="company_website"
              value={formData.company_website}
              onChange={handleChange}
              placeholder="e.g. https://cyberdefensesystems.com"
              className="w-full bg-shield-surface border border-shield-border focus:border-cyan-500 rounded px-3 py-2 text-xs text-slate-100 placeholder-slate-500 outline-none"
            />
          </div>

          {/* Location */}
          <div>
            <label className="block text-xs font-semibold text-slate-300 mb-1.5 flex items-center gap-1.5">
              <MapPin className="w-3.5 h-3.5 text-cyan-400" /> Location
            </label>
            <input
              type="text"
              name="location"
              value={formData.location}
              onChange={handleChange}
              placeholder="e.g. Remote / New York, NY"
              className="w-full bg-shield-surface border border-shield-border focus:border-cyan-500 rounded px-3 py-2 text-xs text-slate-100 placeholder-slate-500 outline-none"
            />
          </div>

          {/* Employment Type & Salary */}
          <div className="grid grid-cols-2 gap-2">
            <div>
              <label className="block text-xs font-semibold text-slate-300 mb-1.5">Employment Type</label>
              <select
                name="employment_type"
                value={formData.employment_type}
                onChange={handleChange}
                className="w-full bg-shield-surface border border-shield-border focus:border-cyan-500 rounded px-3 py-2 text-xs text-slate-100 outline-none"
              >
                <option value="Full-time">Full-time</option>
                <option value="Part-time">Part-time</option>
                <option value="Contract">Contract</option>
                <option value="Internship">Internship</option>
                <option value="Temporary">Temporary</option>
              </select>
            </div>
            <div>
              <label className="block text-xs font-semibold text-slate-300 mb-1.5 flex items-center gap-1">
                <DollarSign className="w-3.5 h-3.5 text-cyan-400" /> Salary
              </label>
              <input
                type="text"
                name="salary"
                value={formData.salary}
                onChange={handleChange}
                placeholder="e.g. $120,000 / yr"
                className="w-full bg-shield-surface border border-shield-border focus:border-cyan-500 rounded px-3 py-2 text-xs text-slate-100 placeholder-slate-500 outline-none"
              />
            </div>
          </div>
        </div>

        {/* Job Description */}
        <div>
          <label className="block text-xs font-semibold text-slate-300 mb-1.5 flex items-center gap-1.5">
            <FileText className="w-3.5 h-3.5 text-cyan-400" /> Job Description *
          </label>
          <textarea
            ref={descriptionRef}
            name="job_description"
            rows={6}
            value={formData.job_description}
            onChange={handleChange}
            placeholder="Paste complete job description, duties, and recruitment correspondence..."
            required={!documentSource}
            className="w-full bg-shield-surface border border-shield-border focus:border-cyan-500 rounded p-3 text-xs text-slate-100 placeholder-slate-500 outline-none leading-relaxed"
          />
        </div>

        {/* Requirements & Benefits */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div>
            <label className="block text-xs font-semibold text-slate-300 mb-1.5">Requirements / Qualifications</label>
            <textarea
              name="requirements"
              rows={3}
              value={formData.requirements}
              onChange={handleChange}
              placeholder="e.g. 3+ years experience, Bachelor degree, skills..."
              className="w-full bg-shield-surface border border-shield-border focus:border-cyan-500 rounded p-3 text-xs text-slate-100 placeholder-slate-500 outline-none leading-relaxed"
            />
          </div>
          <div>
            <label className="block text-xs font-semibold text-slate-300 mb-1.5">Benefits & Compensation Perks</label>
            <textarea
              name="benefits"
              rows={3}
              value={formData.benefits}
              onChange={handleChange}
              placeholder="e.g. Health insurance, 401(k), paid time off..."
              className="w-full bg-shield-surface border border-shield-border focus:border-cyan-500 rounded p-3 text-xs text-slate-100 placeholder-slate-500 outline-none leading-relaxed"
            />
          </div>
        </div>

        {/* Buttons */}
        <div className="flex items-center justify-between pt-4 border-t border-shield-border">
          <button
            type="button"
            onClick={handleClear}
            disabled={uploadStatus === 'uploading'}
            className="inline-flex items-center gap-1.5 px-3.5 py-2 rounded text-xs font-medium text-slate-400 hover:text-slate-200 border border-shield-border hover:bg-shield-surface transition-colors"
          >
            <RotateCcw className="w-3.5 h-3.5" />
            <span>Clear Form</span>
          </button>

          <button
            type="submit"
            disabled={uploadStatus === 'uploading'}
            className="inline-flex items-center gap-2 px-5 py-2.5 rounded text-xs font-semibold bg-cyan-600 hover:bg-cyan-500 text-white transition-all shadow-sm"
          >
            <FileSearch className="w-4 h-4" />
            <span>{documentSource ? 'Analyze Job' : 'Analyze Recruitment Risk'}</span>
          </button>
        </div>
      </form>
    </div>
  );
}
