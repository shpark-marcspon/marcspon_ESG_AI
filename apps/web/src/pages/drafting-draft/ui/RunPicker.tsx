// RP-04 실행 고르기(밴드 RPW1 ④ — 시안 v188 RP-04_r1 머리 「실행 n · <시각> · 지금」). 프로젝트의 실행 목록(RPS1 GET …/runs)을 읽는다.
// 못 읽었거나 지금 실행이 그 쪽에 없으면(오래된 실행) 숨긴다 — 고르기는 곁길이라 초안 보기를 막지 않는다.
import type { DraftingStore } from '../../../entities/drafting/api/index.ts';
import { DR_TEXT } from '../../../entities/drafting/config/text.ts';
import { useRuns } from '../../../entities/drafting/hooks/index.ts';
import { FilterSelect } from '../../../shared/ui/filter-select/index.ts';
import { runChoicesOf } from '../model/index.ts';

const words = DR_TEXT.run;

export interface RunPickerProps {
  store: DraftingStore;
  projectId: number;
  runId: number;
  onPick(runId: number): void;
}

export function RunPicker({ store, projectId, runId, onPick }: RunPickerProps) {
  const runs = useRuns(store, projectId);
  const choices =
    runs.status.state === 'ready' ?
      runChoicesOf(runs.status.value, runId)
    : null;
  if (choices === null) return null;
  return (
    <FilterSelect
      aria-label={words.picker}
      value={String(runId)}
      options={choices.map((choice) => ({
        value: String(choice.runId),
        label: words.pickerOption(choice.n, choice.at, choice.latest),
      }))}
      onChange={(value) => {
        if (Number(value) !== runId) onPick(Number(value));
      }}
    />
  );
}
