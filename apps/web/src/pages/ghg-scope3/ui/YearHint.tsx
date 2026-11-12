// 빈 해 안내 띠(밴드 S3W3d ② — 값 파일 V4·덧, 처분 D2 (가)·D3·K4, sid:MARC-ENT-578). 기본 연도는 그대로 전년도이고 이 띠만 결과 있는 해를 알린다.
// 띄우는 때: 고른 해에 끝난 결과가 없고(실패만 있는 해 포함) 지켜보는 실행이 없을 때. 고른 해도 읽는다 — 그 해 마지막 실행이 실패여도 앞에 끝난 결과가 있을 수 있다.
// 잰 값은 GET …/years/{y} 의 baseRunId 다(port.latest 는 실행 20건 안만 보고 실패만 있는 해도 낸다). 읽기가 하나라도 실패하면 띠 없음 — 못 읽은 해가 더 최근일 수 있다.
import { useEffect, useState } from 'react';

import type { Scope3Port } from '../../../entities/ghg-scope3/api/index.ts';
import { S3_TEXT } from '../../../entities/ghg-scope3/config/text.ts';
import { Button } from '../../../shared/ui/button/index.ts';
import { PageInfo, PageInfoIcon } from '../../../shared/ui/page-info/index.ts';

const words = S3_TEXT.screen;

/** 결과 있는 가장 최근 해. active 가 아니거나 없거나 못 읽으면 null. 해가 바뀌면 늦은 답은 버린다. */
export function useLatestResultYear(
  port: Scope3Port,
  year: number,
  years: readonly number[],
  active: boolean,
) {
  const [found, setFound] = useState<{ from: number; to: number } | null>(null);
  useEffect(() => {
    setFound(null);
    if (!active) return;
    let stopped = false;
    void (async () => {
      const others = years.filter((one) => one !== year);
      const reads = await Promise.all(
        [year, ...others].map((one) => port.year(one)),
      );
      if (stopped) return;
      const states = reads.flatMap((read) =>
        read.kind === 'ok' ? [read.value] : [],
      );
      if (states.length !== reads.length) return;
      const withResult = states
        .filter((state) => state.baseRunId !== null)
        .map((state) => state.year);
      if (withResult.length === 0 || withResult.includes(year)) return;
      setFound({ from: year, to: Math.max(...withResult) });
    })();
    return () => {
      stopped = true;
    };
    // years 는 그 해 안에서 안 바뀐다(모델 yearsOf).
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [port, year, active]);
  return found !== null && found.from === year ? found.to : null;
}

export function YearHint({
  year,
  to,
  onGo,
}: {
  year: number;
  to: number;
  onGo(): void;
}) {
  return (
    <PageInfo
      role="status"
      icon={<PageInfoIcon />}
      data-testid="s3-year-hint"
      className="[&>div]:flex-1"
    >
      <div className="flex flex-wrap items-center justify-between gap-2">
        <span>{words.yearHint(year, to)}</span>
        <Button variant="outlineBlack" shape="round" size="sm" onClick={onGo}>
          {words.yearHintGo(to)}
        </Button>
      </div>
    </PageInfo>
  );
}
