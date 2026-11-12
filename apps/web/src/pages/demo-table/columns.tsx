// 띄워 보는 화면이 쓰는 열 구성. 열은 표의 입력이다: 다른 화면은 다른 열을 넘기면 된다.
import {
  EMISSION_UNIT,
  STATUS_LABEL,
  currentCandidate,
  currentCategory,
  currentEmission,
  formatEmissionNumber,
  isRecalcFailed,
  isRecalcPending,
} from '../../widgets/review-table/index.ts';
import type { ReviewColumn } from '../../widgets/review-table/index.ts';

// 수량 열의 꼴. 배출량 열은 이것을 쓰지 않는다(배출량의 자리수는 formatEmissionNumber 한 곳에서 — sid:MARC-ENT-272).
const quantityNumber = new Intl.NumberFormat('ko', {
  maximumFractionDigits: 1,
});

export const DEMO_COLUMNS: ReviewColumn[] = [
  { id: 'itemName', header: '품목', value: (row) => row.raw.itemName ?? null },
  {
    id: 'quantity',
    header: '수량',
    width: 80,
    align: 'right',
    value: (row) => row.raw.quantity ?? null,
    render: (row) =>
      typeof row.raw.quantity === 'number' ?
        quantityNumber.format(row.raw.quantity)
      : (row.raw.quantity ?? '—'),
  },
  {
    id: 'unit',
    header: '단위',
    width: 56,
    value: (row) => row.raw.unit ?? null,
  },
  {
    id: 'category',
    header: '카테고리',
    width: 170,
    value: (row) => currentCategory(row),
    // 고친 값은 원본값과 같이 보인다.
    render: (row) =>
      row.edit?.category !== undefined ?
        `${row.ai.category ?? '없음'} → ${row.edit.category}`
      : (row.ai.category ?? '—'),
  },
  {
    id: 'factor',
    header: '배출계수(지금 후보)',
    value: (row) => currentCandidate(row)?.factorName ?? null,
  },
  {
    id: 'candidates',
    header: '후보',
    width: 48,
    align: 'right',
    value: (row) => row.ai.candidates.length,
  },
  {
    id: 'emission',
    header: `배출량(${EMISSION_UNIT})`,
    width: 130,
    align: 'right',
    value: (row) => currentEmission(row),
    render: (row) =>
      isRecalcPending(row) ? '재계산 대기'
      : isRecalcFailed(row) ? '계산 실패'
      : currentEmission(row) === null ? '—'
      : formatEmissionNumber(currentEmission(row)!),
  },
  {
    id: 'processing',
    header: '처리 상태',
    width: 88,
    value: (row) => row.processing ?? null,
  },
  {
    id: 'status',
    header: '검토 상태',
    width: 88,
    value: (row) => STATUS_LABEL[row.status],
  },
];
