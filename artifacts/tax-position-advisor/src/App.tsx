import { type FormEvent, type ReactNode, useEffect, useMemo, useState } from 'react';
import { QueryClient, QueryClientProvider, useQueryClient } from '@tanstack/react-query';
import { ErrorBoundary } from '@/components/error-boundary';
import { Toaster } from '@/components/ui/toaster';
import { TooltipProvider } from '@/components/ui/tooltip';
import NotFound from '@/pages/not-found';
import { Link, Route, Router as WouterRouter, Switch, useLocation } from 'wouter';
import {
  useAdminApproveIssue, useAdminCreateIssue, useAdminCreateMapping, useAdminDeleteMapping,
  useAdminLogin, useAdminLogout, useAdminSession,
  useAdminListIssues, useAdminListMappings, useAdminListSections, useAdminRejectIssue,
  useAdminUpdateIssue, useAdminUpdateMapping, useAdminUpdateSection,
  useGetSectionMappings, useListCirculars, useListIssues, useListSections, useSearchAuthorities,
  type Section, type SectionMapping, type SearchResult, type Issue, type Circular,
} from '@workspace/api-client-react';
import type { IssueInput, MappingInput, SectionUpdate, SearchInput } from '@workspace/api-client-react';
import {
  ArrowLeft, ArrowRight, Check, CircleAlert, ExternalLink, FileSearch, LockKeyhole,
  RefreshCw, Search, ShieldCheck, SlidersHorizontal,
} from 'lucide-react';

const queryClient = new QueryClient();
const DISCLAIMER = 'Preliminary indication only, based on user-provided facts and publicly available authorities. Not a certified advisory or a substitute for professional advice. A change in facts or law may change the conclusion. 31stFile accepts no liability for reliance on this output.';

function Shell({ children }: { children: ReactNode }) {
  const [path] = useLocation();
  return <div className="shell">
    <header className="topbar"><div className="topbar-inner">
      <Link href="/" className="nav-link" aria-label="31stFile home" data-testid="link-brand"><img className="brand-image" src="/assets/31stfile-logo-white.png" alt="31stFile" /></Link>
      <nav className="nav-links" aria-label="Main navigation">
        <Link data-testid="link-workflow" className={`nav-link ${path === '/' ? 'active' : ''}`} href="/">Advisor</Link>
        <Link data-testid="link-debug" className={`nav-link ${path === '/debug' ? 'active' : ''}`} href="/debug">Retrieved authorities</Link>
        <Link data-testid="link-admin" className={`nav-link ${path === '/admin' ? 'active' : ''}`} href="/admin">Curation</Link>
      </nav>
    </div></header>
    <main className="main-area">{children}</main>
    <footer className="footer"><div className="footer-inner"><span>31stFile · Tax Position Advisor</span><span>Preliminary research support for tax professionals</span></div></footer>
  </div>;
}

function LoadError({ message, retry }: { message: string; retry: () => void }) {
  return <div className="notice" role="status"><CircleAlert size={16} style={{ verticalAlign: 'middle', marginRight: 7 }} />{message} <button className="btn btn-outline" style={{ marginLeft: 12, minHeight: 32 }} onClick={retry} data-testid="button-retry">Retry</button></div>;
}
function readableError(error: unknown, fallback: string) {
  return error instanceof Error ? error.message : fallback;
}
function SkeletonBlock() { return <div className="card" aria-label="Loading"><div className="skeleton" style={{ width: '34%', marginBottom: 16 }} /><div className="skeleton" style={{ width: '84%', marginBottom: 10 }} /><div className="skeleton" style={{ width: '60%' }} /></div>; }
function SectionText({ section }: { section?: Section | SectionMapping['old_section'] | null }) {
  return section ? <>{section.number} — {section.title}</> : <>Not selected</>;
}
function StatusTag({ children, status = 'neutral' }: { children: ReactNode; status?: string }) {
  return <span className={`tag ${status === 'active' || status === 'good' || status === 'approved' ? 'status-green' : status === 'withdrawn' || status === 'superseded' || status === 'suggested' ? 'status-amber' : status === 'rejected' ? 'status-red' : ''}`}>{children}</span>;
}

function AuthorityResults({ result }: { result: SearchResult }) {
  return <>
    {!!result.warnings.length && <div style={{ display: 'grid', gap: 8, marginBottom: 18 }}>{result.warnings.map((warning, i) => <div className="notice" data-testid={`warning-result-${i}`} key={`${i}-${warning}`}>{warning}</div>)}</div>}
    <div className="result-grid">
      <section className="card" data-testid="panel-case-results">
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', gap: 12 }}><h2 style={{ margin: 0, fontSize: 17 }}>Cases</h2><span className="subtle">{result.cases.length} retrieved</span></div>
        {!result.cases.length ? <div className="placeholder-tile subtle" style={{ marginTop: 16 }}>No cases were returned for this search. This is not evidence that no relevant authority exists.</div> :
          result.cases.map((item) => <article className="authority-card" data-testid={`case-result-${item.doc_id}`} key={item.doc_id}>
            {item.source_url ? <a data-testid={`link-case-source-${item.doc_id}`} className="authority-title" href={item.source_url} target="_blank" rel="noreferrer">{item.title}<ExternalLink size={13} style={{ marginLeft: 6, verticalAlign: 'middle' }} /></a> : <div className="authority-title">{item.title}</div>}
            <div className="authority-meta"><span>{item.court || 'Court not provided'}</span>{item.bench && <span>{item.bench}</span>}<span>{item.date || 'Date not provided'}</span></div>
            <div className="authority-meta"><span>Cited sections: {item.cited_sections.length ? item.cited_sections.join(', ') : 'Not provided'}</span><StatusTag status={item.status || ''}>{item.status || 'Status not provided'}</StatusTag><span className="font-mono">{item.doctype}</span></div>
          </article>)}
      </section>
      <section className="card" data-testid="panel-circular-results">
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', gap: 12 }}><h2 style={{ margin: 0, fontSize: 17 }}>Circulars &amp; related materials</h2><span className="subtle">{result.circulars.length} retrieved</span></div>
        {!result.circulars.length ? <div className="placeholder-tile subtle" style={{ marginTop: 16 }}>No circulars or related materials were returned for this search.</div> :
          result.circulars.map((item) => <CircularCard key={item.id} item={item} />)}
      </section>
    </div>
    <div className="card" style={{ marginTop: 16 }}>
      <div className="eyebrow">Retrieval record</div>
      <p className="subtle" style={{ marginBottom: 0 }}>Kanoon calls: <span className="font-mono">{result.kanoon_calls}</span>{result.query_displays.length > 0 && <> · Searches: {result.query_displays.join(' · ')}</>}</p>
    </div>
    <div className="notice" style={{ marginTop: 18 }} data-testid="text-disclaimer">{DISCLAIMER}</div>
  </>;
}

function CircularCard({ item }: { item: Circular }) {
  return <article className="authority-card" data-testid={`circular-result-${item.id}`}>
    {item.source_url ? <a data-testid={`link-circular-source-${item.id}`} href={item.source_url} className="authority-title" target="_blank" rel="noreferrer">{item.type} {item.number || ''}<ExternalLink size={13} style={{ marginLeft: 6, verticalAlign: 'middle' }} /></a> : <div className="authority-title">{item.type} {item.number || ''}</div>}
    <div className="authority-meta"><span>{item.date || 'Date not provided'}</span><span>Act {item.act_year}</span><span>Section: {item.section_id || 'Not provided'}</span><StatusTag status={item.status}>{item.status}</StatusTag><StatusTag>{item.effect}</StatusTag></div>
    <p className="subtle">{item.summary}</p>
  </article>;
}

function AdvisorPage() {
  const [year, setYear] = useState<1961 | 2025>(1961);
  const [oldSectionId, setOldSectionId] = useState('');
  const [newSectionId, setNewSectionId] = useState('');
  const [issueId, setIssueId] = useState('');
  const [otherIssue, setOtherIssue] = useState('');
  const [facts, setFacts] = useState('');
  const [assessmentYear, setAssessmentYear] = useState('');
  const [manualIds, setManualIds] = useState<string[]>([]);
  const [manualOverride, setManualOverride] = useState(false);
  const [step, setStep] = useState(0);
  const [result, setResult] = useState<SearchResult | null>(() => {
    try { const stored = sessionStorage.getItem('tax-position-last-result'); return stored ? JSON.parse(stored) as SearchResult : null; } catch { return null; }
  });
  const oldSectionsQ = useListSections({ act: 1961 });
  const newSectionsQ = useListSections({ act: 2025 });
  const oldSections = oldSectionsQ.data ?? [];
  const newSections = newSectionsQ.data ?? [];
  const selectedId = year === 1961 ? oldSectionId : newSectionId;
  const mappingsQ = useGetSectionMappings({ section_id: selectedId || 'none' }, { query: { enabled: !!selectedId, queryKey: ['/api/mapping', { section_id: selectedId }] } });
  const issuesQ = useListIssues({ section_id: selectedId || 'none' }, { query: { enabled: !!selectedId, queryKey: ['/api/issues', { section_id: selectedId }] } });
  const circularsQ = useListCirculars({ section_id: selectedId || undefined, issue_id: issueId || undefined }, { query: { enabled: !!selectedId, queryKey: ['/api/circulars', { section_id: selectedId, issue_id: issueId }] } });
  const search = useSearchAuthorities();
  const sections = year === 1961 ? oldSections : newSections;
  const oldSection = oldSections.find(s => s.id === oldSectionId);
  const newSection = newSections.find(s => s.id === newSectionId);
  const mappingRows = mappingsQ.data ?? [];
  const counterpartList = useMemo(() => {
    if (!selectedId) return [];
    const seen = new Set<string>();
    return mappingRows.flatMap((m) => {
      const counterpart = year === 1961 ? m.new_section : m.old_section;
      if (!counterpart || seen.has(counterpart.id)) return [];
      seen.add(counterpart.id);
      return [{ section: counterpart, mapping: m }];
    });
  }, [mappingRows, selectedId, year]);
  useEffect(() => {
    if (!selectedId || mappingsQ.isLoading || mappingsQ.isError || counterpartList.length !== 1) return;
    const counterpartId = counterpartList[0].section.id;
    if (year === 1961 && newSectionId !== counterpartId) setNewSectionId(counterpartId);
    if (year === 2025 && oldSectionId !== counterpartId) setOldSectionId(counterpartId);
  }, [counterpartList, mappingsQ.isError, mappingsQ.isLoading, oldSectionId, newSectionId, selectedId, year]);
  const chosenIssue = (issuesQ.data ?? []).find(issue => issue.id === issueId);

  const selectSection = (id: string, act: 1961 | 2025) => {
    setYear(act);
    if (act === 1961) { setOldSectionId(id); setNewSectionId(''); }
    else { setNewSectionId(id); setOldSectionId(''); }
    setIssueId(''); setManualIds([]); setManualOverride(false);
  };
  const syncCounterpart = (id: string) => {
    const targetYear = year === 1961 ? 2025 : 1961;
    if (year === 1961) setNewSectionId(id); else setOldSectionId(id);
    setYear(targetYear);
    setIssueId('');
  };
  const submitSearch = () => {
    const sectionId = selectedId;
    if (!sectionId || facts.trim().length < 1 || (!issueId && !otherIssue.trim())) return;
    const input: SearchInput = { section_id: sectionId, issue_id: issueId || null, other_issue: !issueId ? otherIssue.trim() : null, facts: facts.trim(), assessment_year: assessmentYear.trim() || null, manual_section_ids: manualIds, manual_override: manualOverride };
    search.mutate({ data: input }, { onSuccess: (data) => { setResult(data); try { sessionStorage.setItem('tax-position-last-result', JSON.stringify(data)); } catch { /* storage may be unavailable */ } setStep(3); } });
  };
  const canContinue = step === 0 ? !!selectedId : step === 1 ? (!!issueId || !!otherIssue.trim()) : step === 2 ? facts.trim().length > 0 : true;
  const selectError = oldSectionsQ.isError || newSectionsQ.isError;

  return <div className="fade-in">
    <div className="eyebrow">Tax research · India</div>
    <h1 className="page-title">Tax position advisor</h1>
    <p className="lede">Explore relevant public authorities against anonymised facts. Begin with an Act section, then narrow the issue and retrieve materials for professional review.</p>
    <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', margin: '26px 0 20px' }} aria-label="Research workflow">
      {['Section', 'Issue', 'Facts', 'Result'].map((label, i) => <button data-testid={`step-${label.toLowerCase()}`} className={`step-pill ${step === i ? 'is-active' : i < step ? 'is-complete' : ''}`} key={label} onClick={() => { if (i <= step || (i === 1 && selectedId) || (i === 2 && selectedId && (issueId || otherIssue)) || (i === 3 && result)) setStep(i); }}><span className="step-num">{i < step ? <Check size={13} /> : `0${i + 1}`}</span>{label}</button>)}
    </div>
    {selectError && <LoadError message={readableError(oldSectionsQ.error || newSectionsQ.error, 'Section catalog could not be loaded. Confirm the research service is available, then retry.')} retry={() => { void oldSectionsQ.refetch(); void newSectionsQ.refetch(); }} />}
    {(oldSectionsQ.isLoading || newSectionsQ.isLoading) && step === 0 && <SkeletonBlock />}
    {!selectError && !(oldSectionsQ.isLoading || newSectionsQ.isLoading) && step === 0 && <section className="card fade-in">
      <div className="eyebrow">01 / Select the governing provision</div>
      <h2 style={{ margin: '7px 0 5px', fontSize: 19 }}>Choose a section under either Act</h2>
      <p className="subtle" style={{ marginTop: 0 }}>The official correspondence shown below is a research aid. It does not determine the applicable law.</p>
      <div className="section-grid" style={{ marginTop: 20 }}>
        {[1961, 2025].map((act) => {
          const actYear = act as 1961 | 2025;
          const list = act === 1961 ? oldSections : newSections;
          const selected = act === 1961 ? oldSectionId : newSectionId;
          return <div key={act}>
            <label className="field-label" htmlFor={`section-${act}`}>Income-tax Act, {act}</label>
            <select id={`section-${act}`} className="control" value={selected} onChange={e => selectSection(e.target.value, actYear)} data-testid={`select-act-${act}`}>
              <option value="">Select a section</option>{list.map(section => <option key={section.id} value={section.id}>{section.number} — {section.title}</option>)}
            </select>
            {act === year && selected && <p className="subtle" style={{ marginBottom: 0 }}>Current research section · {act}</p>}
          </div>;
        })}
      </div>
      {(oldSectionId || newSectionId) && <div style={{ marginTop: 24, borderTop: '1px solid #e5e8ee', paddingTop: 20 }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', gap: 12, alignItems: 'baseline', flexWrap: 'wrap' }}>
          <h3 style={{ fontSize: 15, margin: 0 }}>Section correspondence</h3><span className="subtle">Based on available curated mappings</span>
        </div>
        {mappingsQ.isLoading ? <div className="skeleton" style={{ marginTop: 14, width: '62%' }} /> : mappingsQ.isError ? <LoadError message={readableError(mappingsQ.error, 'Mappings are temporarily unavailable.')} retry={() => void mappingsQ.refetch()} /> : counterpartList.length === 0 ?
          <div className="placeholder-tile subtle" style={{ marginTop: 13 }} data-testid="text-no-corresponding-section">No corresponding section in the other Act</div> :
          <div style={{ display: 'grid', gap: 9, marginTop: 13 }}>{counterpartList.map(({ section, mapping }) => <button className="authority-card" style={{ textAlign: 'left', cursor: 'pointer', background: '#fff', width: '100%', margin: 0 }} key={`${mapping.id}-${section.id}`} onClick={() => syncCounterpart(section.id)} data-testid={`button-counterpart-${section.id}`}>
            <div style={{ display: 'flex', justifyContent: 'space-between', gap: 10, alignItems: 'center' }}><strong style={{ color: '#17306B', fontSize: 13 }}>{section.act_year} · {section.number} — {section.title}</strong><span className="tag">{mapping.relation.replaceAll('_', ' ')}</span></div>
            {mapping.notes && <div className="subtle" style={{ marginTop: 6 }}>{mapping.notes}</div>}
            {mapping.source_ref && <div className="subtle font-mono" style={{ marginTop: 4 }}>Source: {mapping.source_ref}</div>}
            <div style={{ display: 'flex', alignItems: 'center', gap: 6, color: '#17306B', fontSize: 11, fontWeight: 700, marginTop: 8 }}>Select counterpart <ArrowRight size={13} /></div>
          </button>)}</div>}
        <label style={{ display: 'flex', alignItems: 'center', gap: 9, marginTop: 14, fontSize: 12, color: '#354158', cursor: 'pointer' }}>
          <input type="checkbox" checked={manualOverride} onChange={e => { setManualOverride(e.target.checked); if (!e.target.checked) setManualIds([]); }} data-testid="checkbox-manual-override" /> I am manually overriding section correspondence
        </label>
        {manualOverride && <div style={{ marginTop: 12 }}>
          <label className="field-label" htmlFor="manual-counterpart">Add section from the other Act to this search</label>
          <select id="manual-counterpart" className="control" value="" onChange={e => { const id = e.target.value; if (id && !manualIds.includes(id)) setManualIds([...manualIds, id]); }} data-testid="select-manual-section"><option value="">Choose an additional section</option>{(year === 1961 ? newSections : oldSections).map(s => <option key={s.id} value={s.id}>{s.act_year} · {s.number} — {s.title}</option>)}</select>
          {manualIds.length > 0 && <div style={{ display: 'flex', gap: 7, flexWrap: 'wrap', marginTop: 10 }}>{manualIds.map(id => { const s = [...oldSections, ...newSections].find(x => x.id === id); return <button className="tag" key={id} onClick={() => setManualIds(manualIds.filter(x => x !== id))} data-testid={`button-remove-manual-${id}`}>{s ? `${s.act_year} § ${s.number}` : id} ×</button>; })}</div>}
        </div>}
      </div>}
      <div style={{ marginTop: 24, display: 'flex', justifyContent: 'flex-end' }}><button className="btn btn-primary" disabled={!selectedId} onClick={() => setStep(1)} data-testid="button-next-section">Continue to issue <ArrowRight size={15} /></button></div>
    </section>}
    {step === 1 && <section className="card fade-in">
      <div className="eyebrow">02 / Frame the question</div><h2 style={{ margin: '7px 0 5px', fontSize: 19 }}>What issue should the research address?</h2>
      <div className="notice" style={{ margin: '14px 0' }}><strong>Selected provision:</strong> <SectionText section={year === 1961 ? oldSection : newSection} /> · Income-tax Act, {year}</div>
      {issuesQ.isLoading ? <SkeletonBlock /> : issuesQ.isError ? <LoadError message={readableError(issuesQ.error, 'Curated issues could not be loaded. You can retry or use “Other / describe issue”.')} retry={() => void issuesQ.refetch()} /> : <div style={{ display: 'grid', gap: 8 }}>
        {(issuesQ.data ?? []).filter(issue => issue.status === 'approved').length === 0 && <div className="placeholder-tile subtle">No approved issue is configured for this section. Describe the issue below to continue.</div>}
        {(issuesQ.data ?? []).filter(issue => issue.status === 'approved').map(issue => <label key={issue.id} className="authority-card" style={{ margin: 0, display: 'flex', gap: 11, alignItems: 'flex-start', cursor: 'pointer' }}><input type="radio" name="issue" checked={issueId === issue.id} onChange={() => { setIssueId(issue.id); setOtherIssue(''); }} data-testid={`radio-issue-${issue.id}`} /><span><strong style={{ fontSize: 13 }}>{issue.name}</strong><span className="subtle" style={{ display: 'block' }}>Research tier {issue.tier}</span></span></label>)}
      </div>}
      <label className="authority-card" style={{ marginTop: 10, display: 'flex', gap: 11, alignItems: 'flex-start', cursor: 'pointer' }}><input type="radio" name="issue" checked={!issueId} onChange={() => setIssueId('')} data-testid="radio-other-issue" /><span style={{ flex: 1 }}><strong style={{ fontSize: 13 }}>Other / describe issue</strong>{!issueId && <input className="control" style={{ marginTop: 10 }} value={otherIssue} onChange={e => setOtherIssue(e.target.value)} placeholder="Describe the legal issue" data-testid="input-other-issue" />}</span></label>
      <div style={{ display: 'flex', gap: 10, justifyContent: 'space-between', marginTop: 22 }}><button className="btn btn-outline" onClick={() => setStep(0)} data-testid="button-back-issue"><ArrowLeft size={15} /> Back</button><button className="btn btn-primary" onClick={() => setStep(2)} disabled={!issueId && !otherIssue.trim()} data-testid="button-next-issue">Continue to facts <ArrowRight size={15} /></button></div>
    </section>}
    {step === 2 && <section className="card fade-in">
      <div className="eyebrow">03 / Add anonymised facts</div><h2 style={{ margin: '7px 0 5px', fontSize: 19 }}>Describe the facts that matter</h2>
      <div className="notice" style={{ margin: '16px 0' }}><strong>Please anonymise client names.</strong> Do not include names, PANs, addresses, account numbers, or other direct identifiers.</div>
      <div className="subtle" style={{ marginBottom: 14 }}><strong>Provision:</strong> <SectionText section={year === 1961 ? oldSection : newSection} /> · <strong>Issue:</strong> {chosenIssue?.name || otherIssue}</div>
      <label className="field-label" htmlFor="facts">Relevant facts</label><textarea id="facts" className="control" rows={8} maxLength={12000} value={facts} onChange={e => setFacts(e.target.value)} placeholder="Describe the transaction, relevant dates, parties by role, and the specific uncertainty. Keep names and identifying details out." data-testid="textarea-facts" />
      <div style={{ display: 'flex', justifyContent: 'space-between', gap: 10, marginTop: 6 }}><span className="subtle">Limit 12,000 characters · {facts.length} used</span><label className="subtle">Assessment year (optional)<input className="control" style={{ display: 'block', marginTop: 6, width: 200 }} value={assessmentYear} onChange={e => setAssessmentYear(e.target.value)} placeholder="e.g. 2025–26" data-testid="input-assessment-year" /></label></div>
      {circularsQ.isError && <p className="subtle" style={{ color: '#C0392B' }}>{readableError(circularsQ.error, 'Related circular records are not available right now; retrieval can still proceed.')}</p>}
      {!circularsQ.isError && !circularsQ.isLoading && <p className="subtle" data-testid="text-circular-precheck">{(circularsQ.data ?? []).length} related circular or instruction records currently listed for the selected section. Search results will show only materials actually retrieved.</p>}
      <div style={{ display: 'flex', gap: 10, justifyContent: 'space-between', marginTop: 22 }}><button className="btn btn-outline" onClick={() => setStep(1)} data-testid="button-back-facts"><ArrowLeft size={15} /> Back</button><button className="btn btn-primary" disabled={!facts.trim() || !selectedId || search.isPending} onClick={submitSearch} data-testid="button-search-authorities">{search.isPending ? 'Retrieving…' : <><Search size={15} /> Retrieve authorities</>}</button></div>
      {search.isPending && <div className="placeholder-tile" style={{ marginTop: 16 }} role="status" data-testid="status-retrieval-loading"><div className="eyebrow">Searching public authorities</div><div className="skeleton" style={{ width: '77%', marginTop: 12 }} /><div className="skeleton" style={{ width: '51%', marginTop: 9 }} /></div>}
       {search.isError && <div style={{ marginTop: 14 }}><LoadError message={readableError(search.error, 'Authority retrieval failed. No result has been inferred or substituted. Review your connection and retry.')} retry={submitSearch} /></div>}
    </section>}
    {step === 3 && <section className="fade-in">
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: 18, flexWrap: 'wrap', marginBottom: 20 }}>
        <div><div className="eyebrow">04 / Retrieved authorities</div><h2 className="page-title" style={{ fontSize: 29 }}>Research materials</h2><p className="subtle" style={{ margin: 0 }}>Retrieved authorities only. Evaluate relevance and current validity independently.</p></div>
        <button className="btn btn-outline" onClick={() => setStep(2)} data-testid="button-edit-search"><SlidersHorizontal size={15} /> Edit search facts</button>
      </div>
      {result ? <><div className="notice" style={{ marginBottom: 18 }}><strong>Search:</strong> <SectionText section={[...oldSections, ...newSections].find(s => s.id === (year === 1961 ? oldSectionId : newSectionId))} /> · {chosenIssue?.name || otherIssue}</div>
        <AuthorityResults result={result} />
        <div className="result-grid" style={{ marginTop: 16 }}>
          <div className="placeholder-tile"><div className="eyebrow">Position label</div><p className="subtle">Placeholder — no tax position conclusion is generated.</p></div>
          <div className="placeholder-tile"><div className="eyebrow">Strength index</div><p className="subtle">Placeholder — no strength score is calculated.</p></div>
          <div className="placeholder-tile"><div className="eyebrow">Draft note</div><p className="subtle">Placeholder — no advisory note is drafted.</p></div>
          <div className="placeholder-tile"><div className="eyebrow">Export</div><p className="subtle">Placeholder — export is not configured.</p></div>
        </div>
      </> : <div className="card"><div className="placeholder-tile subtle">No retrieved result is available in this session. Start a search from the facts step.</div><button className="btn btn-primary" style={{ marginTop: 16 }} onClick={() => setStep(2)} data-testid="button-return-facts">Return to facts</button></div>}
    </section>}
    <div style={{ marginTop: 24, display: 'flex', gap: 9, flexWrap: 'wrap' }}>
      <span className="tag"><ShieldCheck size={12} style={{ marginRight: 5 }} /> Preliminary research only</span>
      {selectedId && <span className="tag font-mono">Section {year === 1961 ? oldSection?.number : newSection?.number}</span>}
      {step === 1 && issueId && <span className="tag">{chosenIssue?.name}</span>}
    </div>
  </div>;
}

function DebugPage() {
  const [result, setResult] = useState<SearchResult | null>(() => {
    try { const stored = sessionStorage.getItem('tax-position-last-result'); return stored ? JSON.parse(stored) as SearchResult : null; } catch { return null; }
  });
  const [updated, setUpdated] = useState(false);
  useEffect(() => {
    const refresh = () => { try { const stored = sessionStorage.getItem('tax-position-last-result'); setResult(stored ? JSON.parse(stored) as SearchResult : null); setUpdated(true); } catch { setResult(null); } };
    window.addEventListener('storage', refresh); return () => window.removeEventListener('storage', refresh);
  }, []);
  const refresh = () => { try { const stored = sessionStorage.getItem('tax-position-last-result'); setResult(stored ? JSON.parse(stored) as SearchResult : null); setUpdated(true); } catch { setResult(null); } };
  return <div className="fade-in">
    <div className="eyebrow">Service diagnostics</div><h1 className="page-title">Retrieved authorities</h1>
    <p className="lede">A transparent view of the cases and circulars returned by your latest search in this browser session. This page contains no sample or demonstration records.</p>
    <div className="card" style={{ marginTop: 24, marginBottom: 16, display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 16, flexWrap: 'wrap' }}>
      <div><div style={{ fontWeight: 700, fontSize: 14 }}>Latest retrieval</div><div className="subtle">{result ? `${result.cases.length} cases · ${result.circulars.length} circulars · ${result.kanoon_calls} Kanoon calls` : 'No search result stored in this session.'}</div></div>
      <button className="btn btn-outline" onClick={refresh} data-testid="button-refresh-debug"><RefreshCw size={14} /> Refresh session view</button>
    </div>
    {updated && <div className="subtle" role="status">Session view refreshed.</div>}
    {result ? <AuthorityResults result={result} /> : <div className="card" data-testid="empty-debug">
      <div style={{ width: 42, height: 42, borderRadius: 10, background: '#edf3fc', display: 'grid', placeItems: 'center', color: '#17306B' }}><FileSearch size={20} /></div>
      <h2 style={{ fontSize: 17, marginBottom: 6 }}>Nothing retrieved yet</h2><p className="subtle">Run an authority search from the Advisor workflow. If the service has no seed material configured, the results page will say so rather than inventing authority.</p>
      <Link href="/" className="btn btn-primary" data-testid="link-start-research">Go to advisor <ArrowRight size={15} /></Link>
    </div>}
  </div>;
}

function AdminPage() {
  const [draftPassword, setDraftPassword] = useState('');
  const [tab, setTab] = useState<'sections' | 'mappings' | 'issues'>('sections');
  const [adminError, setAdminError] = useState('');
  const [sectionEdit, setSectionEdit] = useState<Section | null>(null);
  const [mappingEditId, setMappingEditId] = useState('');
  const [mappingOpen, setMappingOpen] = useState(false);
  const [mappingForm, setMappingForm] = useState<MappingInput>({ old_section_id: '', new_section_id: null, relation: 'one_to_one', notes: null, source_ref: null });
  const [issueEdit, setIssueEdit] = useState<Issue | null>(null);
  const [issueOpen, setIssueOpen] = useState(false);
  const [issueForm, setIssueForm] = useState<IssueInput>({ name: '', kanoon_keywords: [], tier: 1, status: 'curated', section_ids: [] });
  const sessionQ = useAdminSession({ query: { queryKey: ['/api/admin/session'], retry: false } });
  const authenticated = sessionQ.data?.authenticated === true;
  const queryConfig = { enabled: authenticated };
  const sectionsQ = useAdminListSections({ query: { ...queryConfig, queryKey: ['/api/admin/sections'] } });
  const mappingsQ = useAdminListMappings({ query: { ...queryConfig, queryKey: ['/api/admin/mappings'] } });
  const issuesQ = useAdminListIssues({ query: { ...queryConfig, queryKey: ['/api/admin/issues'] } });
  const loginMutation = useAdminLogin();
  const logoutMutation = useAdminLogout();
  const updateSection = useAdminUpdateSection();
  const createMapping = useAdminCreateMapping();
  const updateMapping = useAdminUpdateMapping();
  const deleteMapping = useAdminDeleteMapping();
  const createIssue = useAdminCreateIssue();
  const updateIssue = useAdminUpdateIssue();
  const approveIssue = useAdminApproveIssue();
  const rejectIssue = useAdminRejectIssue();
  const cache = useQueryClient();
  const refreshAdmin = () => {
    void cache.invalidateQueries({ queryKey: ['/api/admin/mappings'] });
    void cache.invalidateQueries({ queryKey: ['/api/admin/issues'] });
    void cache.invalidateQueries({ queryKey: ['/api/admin/sections'] });
  };
  const login = (e: FormEvent) => {
    e.preventDefault();
    if (!draftPassword.trim()) return;
    loginMutation.mutate({ data: { password: draftPassword } }, {
      onSuccess: () => {
        setDraftPassword('');
        setAdminError('');
        void cache.invalidateQueries({ queryKey: ['/api/admin/session'] });
      },
      onError,
    });
  };
  const logout = () => {
    logoutMutation.mutate(undefined, {
      onSuccess: () => {
        setAdminError('');
        setDraftPassword('');
        cache.removeQueries({ predicate: query => String(query.queryKey[0]).startsWith('/api/admin/') });
        void cache.invalidateQueries({ queryKey: ['/api/admin/session'] });
      },
      onError,
    });
  };
  const onError = (error: unknown) => { setAdminError(error instanceof Error ? error.message : 'Curation request failed. Verify the admin password and try again.'); };
  const submitSection = (e: FormEvent) => {
    e.preventDefault(); if (!sectionEdit) return;
    const body: SectionUpdate = { ...sectionEdit };
    updateSection.mutate({ data: body }, { onSuccess: refreshAdmin, onError });
  };
  const submitMapping = (e: FormEvent) => {
    e.preventDefault();
    const mappingReady = mappingForm.relation === 'new'
      ? !mappingForm.old_section_id && !!mappingForm.new_section_id
      : mappingForm.relation === 'omitted'
        ? !!mappingForm.old_section_id && !mappingForm.new_section_id
        : !!mappingForm.old_section_id && !!mappingForm.new_section_id;
    if (!mappingReady) return;
    const body = { ...mappingForm, old_section_id: mappingForm.old_section_id || null, new_section_id: mappingForm.new_section_id || null, notes: mappingForm.notes || null, source_ref: mappingForm.source_ref || null };
    const done = () => { setMappingEditId(''); setMappingOpen(false); setMappingForm({ old_section_id: '', new_section_id: null, relation: 'one_to_one', notes: null, source_ref: null }); refreshAdmin(); };
    if (mappingEditId) updateMapping.mutate({ mappingId: mappingEditId, data: body }, { onSuccess: done, onError });
    else createMapping.mutate({ data: body }, { onSuccess: done, onError });
  };
  const submitIssue = (e: FormEvent) => {
    e.preventDefault(); if (!issueForm.name.trim()) return;
    const body = { ...issueForm, name: issueForm.name.trim(), kanoon_keywords: issueForm.kanoon_keywords };
    const done = () => { setIssueEdit(null); setIssueOpen(false); setIssueForm({ name: '', kanoon_keywords: [], tier: 1, status: 'curated', section_ids: [] }); refreshAdmin(); };
    if (issueEdit) updateIssue.mutate({ issueId: issueEdit.id, data: body }, { onSuccess: done, onError });
    else createIssue.mutate({ data: body }, { onSuccess: done, onError });
  };
  const actSections = sectionsQ.data ?? [];

  return <div className="fade-in">
    <div className="eyebrow">Restricted workspace</div><h1 className="page-title">Curation console</h1><p className="lede">Manage provision records, Act correspondence, and research issues. Changes are sent to the configured admin service.</p>
    {sessionQ.isLoading ? <div style={{ marginTop: 24 }}><SkeletonBlock /></div> : !authenticated ? <form className="card" style={{ maxWidth: 480, marginTop: 24 }} onSubmit={login}>
      <div style={{ width: 42, height: 42, borderRadius: 10, background: '#edf3fc', color: '#17306B', display: 'grid', placeItems: 'center' }}><LockKeyhole size={19} /></div>
      <h2 style={{ fontSize: 18, marginBottom: 6 }}>Admin password required</h2><p className="subtle">The password is checked once by the server to start a short-lived, HTTP-only session. It is not retained in browser storage.</p>
      <label className="field-label" htmlFor="admin-password">Password</label><input type="password" autoComplete="current-password" className="control" id="admin-password" value={draftPassword} onChange={e => setDraftPassword(e.target.value)} data-testid="input-admin-password" />
      {sessionQ.isError && sessionQ.error.status !== 401 && <p className="subtle" style={{ color: '#C0392B' }} role="alert">{sessionQ.error.message}</p>}
      {adminError && <p className="subtle" style={{ color: '#C0392B' }} role="alert">{adminError}</p>}
      <button className="btn btn-primary" style={{ marginTop: 16 }} type="submit" disabled={loginMutation.isPending} data-testid="button-admin-login">{loginMutation.isPending ? 'Checking…' : 'Unlock curation'}</button>
    </form> : <>
      <div className="card" style={{ marginTop: 24, padding: 14, display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 12, flexWrap: 'wrap' }}>
        <div className="subtle"><ShieldCheck size={15} style={{ verticalAlign: 'middle', marginRight: 7 }} />Authenticated with a short-lived server session</div><button className="btn btn-outline" onClick={logout} disabled={logoutMutation.isPending} data-testid="button-admin-logout">Lock console</button>
      </div>
      {adminError && <div style={{ marginTop: 12 }}><LoadError message={adminError} retry={() => { setAdminError(''); refreshAdmin(); }} /></div>}
      <div style={{ display: 'flex', gap: 8, margin: '18px 0', flexWrap: 'wrap' }}>
        {(['sections', 'mappings', 'issues'] as const).map(item => <button key={item} className={`step-pill ${tab === item ? 'is-active' : ''}`} onClick={() => setTab(item)} data-testid={`tab-admin-${item}`}>{item === 'sections' ? 'Sections' : item === 'mappings' ? 'Mappings' : 'Issues'}</button>)}
      </div>
      {tab === 'sections' && <section className="card">
        <h2 style={{ marginTop: 0, fontSize: 18 }}>Sections</h2>
        {sectionsQ.isLoading ? <SkeletonBlock /> : sectionsQ.isError ? <LoadError message="Section records could not be loaded. Check the admin password and service configuration." retry={() => void sectionsQ.refetch()} /> : !actSections.length ? <div className="placeholder-tile subtle">No curated sections are configured.</div> :
          <div style={{ display: 'grid', gap: 8 }}>{actSections.map(s => <div key={s.id} className="authority-card" style={{ display: 'flex', justifyContent: 'space-between', gap: 12, alignItems: 'center' }} data-testid={`row-section-${s.id}`}>
            <span><span className="font-mono" style={{ fontSize: 12 }}>{s.act_year} § {s.number}</span><span style={{ display: 'block', fontSize: 13, marginTop: 3 }}>{s.title}</span></span><button className="btn btn-outline" onClick={() => setSectionEdit(s)} data-testid={`button-edit-section-${s.id}`}>Edit details</button>
          </div>)}</div>}
        {sectionEdit && <form onSubmit={submitSection} className="placeholder-tile" style={{ marginTop: 16, display: 'grid', gap: 11 }}>
          <div style={{ fontWeight: 700 }}>Update section record</div>
          <label className="field-label">Section number<input className="control" value={sectionEdit.number} onChange={e => setSectionEdit({ ...sectionEdit, number: e.target.value })} data-testid="input-section-number" /></label>
          <label className="field-label">Title<input className="control" value={sectionEdit.title} onChange={e => setSectionEdit({ ...sectionEdit, title: e.target.value })} data-testid="input-section-title" /></label>
          <label className="field-label">Text<textarea className="control" rows={4} value={sectionEdit.text || ''} onChange={e => setSectionEdit({ ...sectionEdit, text: e.target.value || null })} data-testid="textarea-section-text" /></label>
          <div style={{ display: 'flex', gap: 8 }}><button className="btn btn-primary" disabled={updateSection.isPending} data-testid="button-save-section">Save section</button><button type="button" className="btn btn-outline" onClick={() => setSectionEdit(null)} data-testid="button-cancel-section">Cancel</button></div>
        </form>}
      </section>}
      {tab === 'mappings' && <section className="card">
        <div style={{ display: 'flex', justifyContent: 'space-between', gap: 12, alignItems: 'center', flexWrap: 'wrap' }}><h2 style={{ margin: 0, fontSize: 18 }}>Section mappings</h2><button className="btn btn-primary" onClick={() => { setMappingEditId(''); setMappingOpen(true); setMappingForm({ old_section_id: '', new_section_id: null, relation: 'one_to_one', notes: null, source_ref: null }); }} data-testid="button-new-mapping">Add mapping</button></div>
        {mappingsQ.isLoading ? <div style={{ marginTop: 14 }}><SkeletonBlock /></div> : mappingsQ.isError ? <LoadError message="Section mappings could not be loaded." retry={() => void mappingsQ.refetch()} /> : !(mappingsQ.data ?? []).length ? <div className="placeholder-tile subtle" style={{ marginTop: 14 }}>No mappings are configured. Add only mappings supported by an authoritative source.</div> :
          <div style={{ display: 'grid', gap: 8, marginTop: 14 }}>{(mappingsQ.data ?? []).map(m => <div key={m.id} className="authority-card" data-testid={`row-mapping-${m.id}`}>
             <div style={{ display: 'flex', justifyContent: 'space-between', gap: 12, alignItems: 'flex-start' }}><div><strong>{m.old_section ? `${m.old_section.act_year} § ${m.old_section.number}` : 'Old section unavailable'}</strong> <ArrowRight size={13} /> <strong>{m.new_section ? `${m.new_section.act_year} § ${m.new_section.number}` : 'No counterpart'}</strong><div style={{ marginTop: 7 }}><span className="tag">{m.relation.replaceAll('_', ' ')}</span></div>{m.notes && <p className="subtle">{m.notes}</p>}{m.source_ref && <span className="font-mono subtle">{m.source_ref}</span>}</div>
             <div style={{ display: 'flex', gap: 6 }}><button className="btn btn-outline" onClick={() => { setMappingEditId(m.id); setMappingOpen(true); setMappingForm({ old_section_id: m.old_section_id, new_section_id: m.new_section_id, relation: m.relation, notes: m.notes, source_ref: m.source_ref }); }} data-testid={`button-edit-mapping-${m.id}`}>Edit</button><button className="btn btn-outline" style={{ color: '#C0392B', borderColor: '#C0392B' }} onClick={() => { if (window.confirm('Delete this section mapping?')) deleteMapping.mutate({ mappingId: m.id }, { onSuccess: refreshAdmin, onError }); }} data-testid={`button-delete-mapping-${m.id}`}>Delete</button></div>
            </div>
          </div>)}</div>}
        {mappingOpen && <form onSubmit={submitMapping} className="placeholder-tile" style={{ marginTop: 16, display: 'grid', gap: 10 }}>
          <strong>{mappingEditId ? 'Edit mapping' : 'Create mapping'}</strong>
          <label className="field-label">Income-tax Act, 1961 section<select className="control" value={mappingForm.old_section_id || ''} onChange={e => setMappingForm({ ...mappingForm, old_section_id: e.target.value })} data-testid="select-mapping-old"><option value="">No old section (new-only mapping)</option>{actSections.filter(s => s.act_year === 1961).map(s => <option key={s.id} value={s.id}>{s.number} — {s.title}</option>)}</select></label>
          <label className="field-label">Income-tax Act, 2025 section<select className="control" value={mappingForm.new_section_id || ''} onChange={e => setMappingForm({ ...mappingForm, new_section_id: e.target.value || null })} data-testid="select-mapping-new"><option value="">No 2025 counterpart</option>{actSections.filter(s => s.act_year === 2025).map(s => <option key={s.id} value={s.id}>{s.number} — {s.title}</option>)}</select></label>
          <label className="field-label">Relation<select className="control" value={mappingForm.relation} onChange={e => { const relation = e.target.value as MappingInput['relation']; setMappingForm({ ...mappingForm, relation, ...(relation === 'new' ? { old_section_id: '' } : relation === 'omitted' ? { new_section_id: null } : {}) }); }} data-testid="select-mapping-relation">{['one_to_one', 'one_to_many', 'many_to_one', 'merged', 'omitted', 'new'].map(r => <option key={r} value={r}>{r.replaceAll('_', ' ')}</option>)}</select></label>
          <label className="field-label">Notes<input className="control" value={mappingForm.notes || ''} onChange={e => setMappingForm({ ...mappingForm, notes: e.target.value || null })} data-testid="input-mapping-notes" /></label>
          <label className="field-label">Source reference<input className="control" value={mappingForm.source_ref || ''} onChange={e => setMappingForm({ ...mappingForm, source_ref: e.target.value || null })} data-testid="input-mapping-source" /></label>
          <div style={{ display: 'flex', gap: 8 }}><button className="btn btn-primary" disabled={!(mappingForm.relation === 'new' ? !mappingForm.old_section_id && !!mappingForm.new_section_id : mappingForm.relation === 'omitted' ? !!mappingForm.old_section_id && !mappingForm.new_section_id : !!mappingForm.old_section_id && !!mappingForm.new_section_id) || createMapping.isPending || updateMapping.isPending} data-testid="button-save-mapping">Save mapping</button><button type="button" className="btn btn-outline" onClick={() => { setMappingEditId(''); setMappingOpen(false); }} data-testid="button-cancel-mapping">Cancel</button></div>
        </form>}
      </section>}
      {tab === 'issues' && <section className="card">
        <div style={{ display: 'flex', justifyContent: 'space-between', gap: 12, alignItems: 'center', flexWrap: 'wrap' }}><h2 style={{ margin: 0, fontSize: 18 }}>Research issues</h2><button className="btn btn-primary" onClick={() => { setIssueEdit(null); setIssueOpen(true); setIssueForm({ name: '', kanoon_keywords: [], tier: 1, status: 'curated', section_ids: [] }); }} data-testid="button-new-issue">Add issue</button></div>
        {issuesQ.isLoading ? <div style={{ marginTop: 14 }}><SkeletonBlock /></div> : issuesQ.isError ? <LoadError message="Issue records could not be loaded." retry={() => void issuesQ.refetch()} /> : !(issuesQ.data ?? []).length ? <div className="placeholder-tile subtle" style={{ marginTop: 14 }}>No issues have been curated.</div> :
          <div style={{ display: 'grid', gap: 9, marginTop: 14 }}>{(issuesQ.data ?? []).map(issue => <article className="authority-card" key={issue.id} data-testid={`row-issue-${issue.id}`}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: 12 }}><div><strong>{issue.name}</strong><div className="authority-meta"><StatusTag status={issue.status}>{issue.status}</StatusTag><span>Tier {issue.tier}</span><span>{issue.section_ids.length} linked sections</span></div><div className="subtle">Keywords: {issue.kanoon_keywords.join(', ') || 'None'}</div></div>
            <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap', justifyContent: 'flex-end' }}><button className="btn btn-outline" onClick={() => { setIssueEdit(issue); setIssueOpen(true); setIssueForm({ name: issue.name, kanoon_keywords: issue.kanoon_keywords, tier: issue.tier, status: issue.status, section_ids: issue.section_ids }); }} data-testid={`button-edit-issue-${issue.id}`}>Edit</button>{issue.status !== 'approved' && issue.status !== 'rejected' && <button className="btn btn-outline" onClick={() => approveIssue.mutate({ issueId: issue.id }, { onSuccess: refreshAdmin, onError })} data-testid={`button-approve-issue-${issue.id}`}>Approve</button>}{issue.status !== 'rejected' && <button className="btn btn-outline" onClick={() => rejectIssue.mutate({ issueId: issue.id }, { onSuccess: refreshAdmin, onError })} data-testid={`button-reject-issue-${issue.id}`}>Reject</button>}</div></div>
          </article>)}</div>}
        {issueOpen && <form onSubmit={submitIssue} className="placeholder-tile" style={{ marginTop: 16, display: 'grid', gap: 10 }}>
          <strong>{issueEdit ? 'Edit issue' : 'Create issue'}</strong>
          <label className="field-label">Issue name<input className="control" value={issueForm.name} onChange={e => setIssueForm({ ...issueForm, name: e.target.value })} data-testid="input-issue-name" /></label>
          <label className="field-label">Kanoon keywords, comma separated<input className="control" value={issueForm.kanoon_keywords.join(', ')} onChange={e => setIssueForm({ ...issueForm, kanoon_keywords: e.target.value.split(',').map(x => x.trim()).filter(Boolean) })} data-testid="input-issue-keywords" /></label>
          <label className="field-label">Research tier<select className="control" value={issueForm.tier} onChange={e => setIssueForm({ ...issueForm, tier: Number(e.target.value) })} data-testid="select-issue-tier">{[1,2,3,4,5].map(n => <option key={n} value={n}>{n}</option>)}</select></label>
          <label className="field-label">Status<select className="control" value={issueForm.status} onChange={e => setIssueForm({ ...issueForm, status: e.target.value as IssueInput['status'] })} data-testid="select-issue-status">{['curated', 'suggested', 'approved', 'rejected'].map(v => <option value={v} key={v}>{v}</option>)}</select></label>
          <label className="field-label">Linked sections<select multiple className="control" value={issueForm.section_ids} onChange={e => setIssueForm({ ...issueForm, section_ids: Array.from(e.target.selectedOptions).map(o => o.value) })} data-testid="select-issue-sections">{actSections.map(s => <option key={s.id} value={s.id}>{s.act_year} § {s.number} — {s.title}</option>)}</select></label>
          <div style={{ display: 'flex', gap: 8 }}><button className="btn btn-primary" disabled={!issueForm.name.trim()} data-testid="button-save-issue">Save issue</button><button type="button" className="btn btn-outline" onClick={() => { setIssueEdit(null); setIssueOpen(false); }} data-testid="button-cancel-issue">Cancel</button></div>
        </form>}
      </section>}
    </>}
  </div>;
}

function Router() {
  return <RoutedErrorBoundary><Shell><Switch>
    <Route path="/" component={AdvisorPage} />
    <Route path="/debug" component={DebugPage} />
    <Route path="/admin" component={AdminPage} />
    <Route component={NotFound} />
  </Switch></Shell></RoutedErrorBoundary>;
}
function RoutedErrorBoundary({ children }: { children: ReactNode }) {
  const [location] = useLocation();
  return <ErrorBoundary resetKey={location}>{children}</ErrorBoundary>;
}
function App() {
  return <QueryClientProvider client={queryClient}><TooltipProvider><WouterRouter base={import.meta.env.BASE_URL.replace(/\/$/, '')}><Router /></WouterRouter><Toaster /></TooltipProvider></QueryClientProvider>;
}
export default App;