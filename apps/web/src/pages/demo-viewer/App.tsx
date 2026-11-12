// 뷰어 부품을 띄워 보는 화면. 자료(JSON) 하나를 골라 읽고, 검증하고, 뷰어에 넘긴다.
//
// 여기 있는 것은 부품이 아니라 「부품을 쓰는 쪽」의 예다. 다른 화면에서 쓸 때 따라 하면 되는 최소한이다:
//   1) 자료를 가져온다          → 지금은 정적 JSON 파일. 서버가 생기면 이 자리가 API 호출이 된다
//   2) parseViewerInput 으로 검증한다
//   3) useReviews 로 검토 상태를 들고, DocumentViewer 에 넘긴다
// 주소는 /dev/viewer(DEV·VITE_DEMOS 빌드에만 — src/app/router.tsx). 어느 자료를 볼지는 주소의 ?data= 로, 강조의 보기 방식은 ?mode= 로 고른다(outline | selected | fill).
// ?screen=compact 를 붙이면 같은 자료를 둘째 화면(src/pages/demo-viewer/CompactViewer.tsx)으로 띄운다. 화면을 갈아 끼워 보는 증명용이다.
//
// 조작이 놓인 자리: 보기 방식은 여기(띄워 보는 화면의 띠)에 있다. 셋을 견주어 보려고 둔 것이라 하나로 굳으면 사라진다.
// 범례(종류 켜고 끄기)와 「좁힌 자리로 보기」는 뷰어 부품 안(왼쪽 위)에 있다. 그 둘은 부품의 것이라 남는다.
import { useEffect, useState } from 'react';

import { appHref, appPath, withParams } from '../../shared/lib/address.ts';
import { NativeSelect } from '../../shared/ui/filter-select/index.ts';
import {
  DEFAULT_HIGHLIGHT_MODE,
  DocumentViewer,
  HIGHLIGHT_MODES,
  isHighlightMode,
  parseViewerInput,
  useReviews,
} from '../../widgets/doc-viewer/index.ts';
import type {
  HighlightMode,
  OpenPdf,
  ViewerInput,
} from '../../widgets/doc-viewer/index.ts';
import { openPdf } from '../../widgets/doc-viewer/pdfjs.ts';
import { CompactViewer } from './CompactViewer.tsx';

interface Dataset {
  file: string;
  title: string;
}

// 저장소에 든 예시 자료. PDF 는 코드로 만든 것이다(tools/prepare.ts).
const SAMPLES: Dataset[] = [
  { file: 'sample/compare.json', title: '예시: 두 문서 대조' },
  { file: 'sample/sentences.json', title: '예시: 문장 강조(가짜 자료)' },
];

/** sample/<이름>.json 또는 local/<이름>.json */
const DATA_FILE = /^(sample|local)\/[\w.-]+\.json$/;

type Loaded =
  | { state: 'loading' }
  | { state: 'ready'; input: ViewerInput }
  | { state: 'error'; errors: string[] };

export function App() {
  const [datasets, setDatasets] = useState<Dataset[]>(SAMPLES);
  const [file, setFile] = useState(() => {
    const asked = new URLSearchParams(location.search).get('data');
    // 주소로 받은 값은 이 앱이 내주는 자료 파일의 꼴일 때만 쓴다(다른 곳의 주소를 열지 않는다).
    return asked && DATA_FILE.test(asked) ? asked : SAMPLES[0]!.file;
  });
  const [mode, setMode] = useState<HighlightMode>(() => {
    const asked = new URLSearchParams(location.search).get('mode');
    return isHighlightMode(asked) ? asked : DEFAULT_HIGHLIGHT_MODE;
  });
  const [loaded, setLoaded] = useState<Loaded>({ state: 'loading' });

  // 실제 자료를 붙였으면(apps/web/docs/doc-viewer.md 의 「실제 자료를 붙이는 법」) 그 목록이 local/index.json 에 있다. 없으면 예시만 보인다.
  useEffect(() => {
    fetch(appPath('local/index.json'))
      .then((response) => (response.ok ? response.json() : { datasets: [] }))
      .then((index: { datasets: Dataset[] }) =>
        setDatasets([...SAMPLES, ...index.datasets]),
      )
      .catch(() => undefined);
  }, []);

  useEffect(() => {
    let alive = true;
    setLoaded({ state: 'loading' });
    fetch(appPath(file))
      .then((response) => {
        if (!response.ok) throw new Error(`${file}: HTTP ${response.status}`);
        return response.json() as Promise<unknown>;
      })
      .then((raw) => {
        if (!alive) return;
        const parsed = parseViewerInput(raw);
        setLoaded(
          parsed.ok ?
            { state: 'ready', input: parsed.input }
          : { state: 'error', errors: parsed.errors },
        );
      })
      .catch(
        (error: unknown) =>
          alive && setLoaded({ state: 'error', errors: [String(error)] }),
      );
    return () => {
      alive = false;
    };
  }, [file]);

  // 자료와 보기 방식만 고쳐 쓴다. 주소의 다른 인자(?screen=compact 등)는 그대로 둔다. 기본 보기 방식은 주소에 적지 않는다.
  function writeAddress(nextFile: string, nextMode: HighlightMode) {
    history.replaceState(
      null,
      '',
      withParams(location.search, {
        data: nextFile,
        mode: nextMode === DEFAULT_HIGHLIGHT_MODE ? null : nextMode,
      }),
    );
  }
  function choose(next: string) {
    setFile(next);
    writeAddress(next, mode);
  }
  function chooseMode(next: HighlightMode) {
    setMode(next);
    writeAddress(file, next);
  }

  return (
    <div className="app">
      <header className="app-bar">
        <label>
          자료{' '}
          <NativeSelect
            value={file}
            onChange={(event) => choose(event.target.value)}
          >
            {datasets.map((dataset) => (
              <option key={dataset.file} value={dataset.file}>
                {dataset.title}
              </option>
            ))}
            {!datasets.some((dataset) => dataset.file === file) && (
              <option value={file}>{file}</option>
            )}
          </NativeSelect>
        </label>
        <span
          className="app-modes"
          role="radiogroup"
          aria-label="강조 보기 방식"
        >
          강조{' '}
          {HIGHLIGHT_MODES.map((entry) => (
            <label key={entry.mode}>
              <input
                type="radio"
                name="highlight-mode"
                value={entry.mode}
                checked={mode === entry.mode}
                onChange={() => chooseMode(entry.mode)}
              />
              {entry.label}
            </label>
          ))}
        </span>
        <span>검토 상태는 이 화면 안에만 있다. 새로 고치면 사라진다.</span>
        <a href={appPath('dev/table')}>검토 표</a>
      </header>
      <main className="app-main">
        {loaded.state === 'loading' && <p className="app-message">읽는 중…</p>}
        {loaded.state === 'error' && (
          <p className="app-message" role="alert">
            자료를 쓸 수 없다.{'\n'}
            {loaded.errors.slice(0, 20).join('\n')}
          </p>
        )}
        {/* key: 자료가 바뀌면 뷰어와 검토 상태를 통째로 새로 만든다. */}
        {loaded.state === 'ready' && (
          <Review key={file} input={loaded.input} mode={mode} />
        )}
      </main>
    </div>
  );
}

// 둘째 화면은 주소로만 고른다(조작 단추를 두지 않았다. 본 화면의 띠는 그대로다).
const Screen =
  new URLSearchParams(location.search).get('screen') === 'compact' ?
    CompactViewer
  : DocumentViewer;

/**
 * 자료 속 PDF 주소(`sample/sample-a.pdf`·`local/<id>.pdf` 꼴의 상대 주소)를 앱 뿌리(appHref) 기준으로 푼다(밴드 RT1).
 * 문서 기준으로 풀면 /dev/viewer 에서 /dev/sample/… 가 되어 SPA fallback 의 HTML 을 받는다. 자료 파일은 고치지 않는다.
 */
const openData: OpenPdf = (url) => openPdf(appHref(url));

function Review({ input, mode }: { input: ViewerInput; mode: HighlightMode }) {
  const reviews = useReviews(input.items);
  return (
    <Screen
      input={input}
      openPdf={openData}
      reviews={reviews.states}
      onReview={reviews.apply}
      highlightMode={mode}
    />
  );
}
