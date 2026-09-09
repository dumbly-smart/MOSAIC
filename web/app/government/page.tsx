'use client';

import { OfficerWorkflow } from '../../components/officer-workflow';
import { MosaicApi } from '../../lib/mosaic-api';

const api = new MosaicApi(process.env.NEXT_PUBLIC_MOSAIC_API_URL ?? '');

export default function GovernmentPage() {
  return <main className="mx-auto max-w-4xl space-y-6"><header><p className="text-sm font-semibold text-blue-700">MOSAIC officer workspace</p><h1 className="text-3xl font-bold">Tender and bidder verification</h1><p className="text-slate-600">Upload synthetic local PDFs for officer-led review.</p></header><OfficerWorkflow api={api}/></main>;
}
