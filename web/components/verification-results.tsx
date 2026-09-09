'use client';
import { asVerificationReport, VerificationRunResponse } from '../lib/mosaic-api';

export function VerificationResults({ run }: { run: VerificationRunResponse }) {
  const report = asVerificationReport(run.result);
  if (run.status === 'queued' || run.status === 'running') return <p role="status">Verification {run.status}…</p>;
  if (run.status === 'failed') return <p role="alert">Verification failed: {run.error_message ?? 'Review server logs.'}</p>;
  if (run.status === 'needs_manual_review') return <p role="status">Manual review required</p>;
  return <section className="space-y-4"><h2 className="text-xl font-bold">Verification results</h2><p>Score: {run.score ?? 'Not supplied'}</p><p>Risk: Not supplied by this run</p><p>Policy: {run.policy_version}</p>{report ? <><p>Advisory: {report.recommendation}</p>{report.results.map((item, index) => <article key={`${item.criterionId}-${index}`} className="rounded border p-3"><strong>{item.clause ?? item.criterionId ?? 'Finding'} — {item.status ?? 'unknown'}</strong><p>{item.reason ?? 'No explanation supplied.'}</p>{item.evidence?.sourceQuote ? <p>Evidence: {item.evidence.sourceQuote}</p> : null}{item.evidence?.documentId ? <p>Source: {item.evidence.documentId}{item.evidence.page ? `, page ${item.evidence.page}` : ''}</p> : null}</article>)}</> : <p>Result details are unavailable; review the run metadata and source documents.</p>}<p className="rounded bg-slate-900 p-4 text-white">MOSAIC provides decision support only. Final qualification, disqualification, and clarification decisions remain with a Procurement Officer. This is a local/mock-sandbox demonstration, not a live government-portal integration.</p></section>;
}
