import { render, screen } from '@testing-library/react';
import { expect, test } from 'vitest';
import { VerificationResults } from './verification-results';

const run = { id:'r',case_id:'c',status:'completed' as const,policy_version:'p1',score:100,error_message:null,created_at:'2026-01-01T00:00:00Z',started_at:null,completed_at:null,result:{score:100,results:[{criterion_id:'C1',clause:'GST registration',status:'passed',reason:'Primary requirement met.',evidence:{source_quote:'GST certificate confirms registration',document_id:'bidder.pdf',page:1}}],review_required:false,clarification_required:false,unresolved_criteria:[],recommendation:'qualify' as const} };
test('renders evidence advisory and does not invent risk', () => {
  render(<VerificationResults run={run} />);
  expect(screen.getByText('Primary requirement met.')).toBeVisible();
  expect(screen.getByText(/Evidence: GST certificate confirms registration/)).toBeVisible();
  expect(screen.getByText('Advisory: qualify')).toBeVisible();
  expect(screen.getByText('Risk: Not supplied by this run')).toBeVisible();
});
