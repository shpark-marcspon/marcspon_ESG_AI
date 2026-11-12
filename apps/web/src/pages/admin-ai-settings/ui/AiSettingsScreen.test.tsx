// @vitest-environment jsdom
// AD-02 AI 설정 껍데기(밴드 AD2 ②, 실서버 AD2R ③④, GW2R ④, 모듈 슬롯·prompt-model AD2W ①② — 디자인 판 AD-02_r3).
// 껍데기는 모듈을 모른다: 시험도 그린워싱을 가져오지 않고 슬롯 가짜(entities/ai-setting/api/testing.ts 의 fakeAiSettingModule)를 넘긴다.
//   자료: 저장 판 셋 13 v3 초안(「지어낸 판 셋」) · 12 v2 적용 중 · 11 v1 지난 버전(이름·만든 사람 없음), 기본 판(이름 「기본 설정」).
//   ① 틀: 제목(모듈 이름)·설명(r3)·띠·링크 없음·열 셋, 처음 고름(가장 새 초안 · initialVersion), 처음 구성은 프롬프트. 요청은 목록 + 고른 판 prompt-model 하나
//   ② 판 고름: 판마다 prompt-model 한 번(다시 고르면 0), 「v3 · 이름」, 목록 세대 셈·[더 보기]·StrictMode, prompt-model 불러오기·실패·쓸 수 없는 판
//   ③ 구성(r3 차례 — 서버 값 꼬리)·셋째 열 칸 고름·모델 카드·단계 카드·고정 값·모듈 줄
//   ④ 단추·불러오기·꼴 ⑥ 적용(확인 창 → port.apply, 끔·두 번 누름·실패)
//   ⑦ 판 초안·한 번 저장(AD2W ③): 모델 고침 → 저장 막대·편집중·「고침 n」, 저장 창 → port.create 한 번(본문 키·고친 칸만 바뀜·모델 다섯 칸),
//     두 번 누름·Enter, 끔 단추 셋(적용·저장·복제)은 눌러도 부름 0·창 0, 나가기 창(판 누름·라우터 leave), 되돌리기, 실패 갈래, 복제, 경로 바꿈
//   ⑧ 프롬프트 칸 고침(AD2W ④): 글·메모 → 「고친 것 n개」·칸 꼬리표·본문은 고친 칸만, 코드포인트 셈·빈 글(Python strip)·넘침 → 칸 빨강·저장 끔,
//     출력절 바뀜 경고, 거절 AI_PROMPT_* fields → 그 칸 빨강·칸 고름 「고칠 곳 있음」·창 줄, 저장 뒤 목록 다시 읽기 실패 → 정보 띠(cd 답)
//   옛 시험(그린워싱 가짜 서버로 판을 받음)의 짝은 밴드 AD2W 보고 「1-5 표」에 적었다.
import { StrictMode } from 'react';

import {
  act,
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
  within,
} from '@testing-library/react';
import { renderHook } from '@testing-library/react';

import { afterEach, beforeAll, describe, expect, it, vi } from 'vitest';

import {
  fakeAiSettingModule,
  fakePromptModel,
  fakeVersionRows,
} from '../../../entities/ai-setting/api/testing.ts';
import { fakeWidePromptModel } from '../../../entities/ai-setting/api/testing.ts';
import { AI_SETTING_TEXT } from '../../../entities/ai-setting/config/text.ts';
import type {
  PromptModelOutcome,
  VersionPageOutcome,
} from '../../../entities/ai-setting/model/index.ts';
import { draftOf } from '../../../entities/ai-setting/model/index.ts';
import type { ModuleDraftSlot } from '../../../entities/ai-setting/model/index.ts';
import { useSave } from '../hooks/index.ts';
import { AiSettingsScreen } from './AiSettingsScreen.tsx';

afterEach(cleanup);
vi.setConfig({ testTimeout: 15_000 });

beforeAll(() => {
  if (!('ResizeObserver' in globalThis))
    vi.stubGlobal(
      'ResizeObserver',
      class {
        observe() {}
        unobserve() {}
        disconnect() {}
      },
    );
});

const t = AI_SETTING_TEXT;

type Fake = ReturnType<typeof fakeAiSettingModule>;

function setup({
  initialVersion,
  fake = fakeAiSettingModule(),
}: { initialVersion?: string; fake?: Fake } = {}) {
  const view = render(
    <AiSettingsScreen
      modules={[fake.module]}
      initialVersion={initialVersion}
    />,
  );
  return { fake, view };
}

/** 처음 구성은 프롬프트 — 그 카드의 제목(「프롬프트 — 판 이름」)이 보이면 다 그렸다. */
const titled = (name: string) =>
  screen.findByRole('heading', { name: t.prompt.title(name) });
const ready = () => titled('v3');
const column = (name: string) => screen.getByRole('region', { name });
const choose = (columnName: string, label: string | RegExp) =>
  fireEvent.click(
    within(column(columnName)).getByRole('button', { name: label }),
  );
const pickVersion = (key: string) =>
  fireEvent.click(
    document.querySelector(`[data-version="${key}"]`)!.closest('button')!,
  );
const button = (name: string) => screen.getByRole('button', { name });
const card = (kind: string) =>
  document.querySelector(`[data-card="${kind}"]`) as HTMLElement;
const pressed = (name: string) =>
  within(column(name))
    .getAllByRole('button')
    .filter((node) => node.getAttribute('aria-pressed') === 'true')
    .map((node) => node.textContent);
const lines = (name: string) =>
  within(column(name))
    .getAllByRole('button')
    .map((node) => node.textContent);
const settle = () =>
  act(async () => {
    await new Promise((done) => setTimeout(done, 20));
  });
/** 끝나지 않은 답 하나(풀어 줄 때까지). */
function deferred<T>() {
  let resolve!: (value: T) => void;
  const promise = new Promise<T>((done) => (resolve = done));
  return { promise, resolve };
}

describe('AD-02 ① 틀', () => {
  it('제목(모듈 이름)·설명(r3)·띠 없음·링크 없음·열 셋, 처음은 가장 새 초안 v3 · 프롬프트. 요청은 목록 한 번 + v3 prompt-model 한 번', async () => {
    const { fake } = setup();
    await ready();
    expect(screen.getByRole('heading', { level: 2 }).textContent).toBe(
      t.title('지어낸 모듈'),
    );
    expect(screen.getByText(t.description)).toBeTruthy();
    expect(screen.queryByTestId('mock-band')).toBeNull();
    expect(screen.queryByRole('link')).toBeNull();
    expect(document.body.textContent).not.toContain('테스트 비교');
    // 머리 오른쪽 단추는 [이 버전 적용] 하나(제목 줄 안의 단추)
    const titleRow = screen.getByRole('heading', { level: 2 }).parentElement!
      .parentElement!;
    expect(
      [...titleRow.querySelectorAll('button, a')].map(
        (node) => node.textContent,
      ),
    ).toEqual([t.apply]);
    expect(fake.calls.map((call) => call.method)).toEqual([
      'list',
      'promptModel',
    ]);
    expect(fake.args('promptModel')).toEqual(['13']);
    expect(pressed(t.columns.version)).toEqual([
      'v3 · 지어낸 판 셋초안2026-10-19',
    ]);
    expect(pressed(t.columns.component)[0]).toContain('프롬프트');
    expect(
      within(column(t.columns.version))
        .getAllByRole('button', { pressed: false })
        .map((node) => node.textContent),
    ).toEqual([
      'v2 · 지어낸 판 둘적용 중2026-10-18',
      'v1지난 버전2026-10-17',
      `기본 설정${t.status.default}${t.defaultSum}`,
    ]);
    // 기본 판 줄 앞 구분선(디자인 D2).
    expect(
      document.querySelector('[data-version="default"]')!.closest('li')!
        .className,
    ).toContain('border-t');
    expect(
      document
        .querySelector('[data-screen="admin-ai-settings"]')!
        .getAttribute('data-module'),
    ).toBe('fake');
  });

  it('initialVersion 이 있으면 그 판(v1), 없는 번호면 가장 새 초안 — prompt-model 은 고른 판 하나', async () => {
    const { fake } = setup({ initialVersion: 'v1' });
    await titled('v1');
    expect(fake.args('promptModel')).toEqual(['11']);
    cleanup();
    const other = setup({ initialVersion: 'v9' });
    await titled('v3');
    expect(other.fake.args('promptModel')).toEqual(['13']);
  });

  it('저장 판이 없고 기본 판이 적용 중이면 기본 판 줄 하나 「적용 중」을 고른다(prompt-model 은 default)', async () => {
    const fake = fakeAiSettingModule({ rows: [], appliedDefault: true });
    setup({ fake });
    await titled('기본 설정');
    expect(fake.args('promptModel')).toEqual(['default']);
    expect(pressed(t.columns.version)).toEqual([
      `기본 설정${t.status.applied}${t.defaultSum}`,
    ]);
  });
});

describe('AD-02 적용 안내(모듈 applyNote — 밴드 RPW12)', () => {
  it('모듈이 applyNote 를 주면 제목 바로 아래 한 줄(12 · 회색) · 제목과 한 겹(gap-3)', async () => {
    const fake = fakeAiSettingModule();
    setup({
      fake: {
        ...fake,
        module: { ...fake.module, applyNote: '지어낸 적용 안내' },
      },
    });
    await ready();
    expect(screen.getAllByTestId('module-apply-note')).toHaveLength(1);
    const note = screen.getByTestId('module-apply-note');
    expect(note.textContent).toBe('지어낸 적용 안내');
    expect(note.className).toContain('text-style-pre-caption-03');
    expect(note.className).toContain('text-text-tertiary');
    const heading = screen.getByRole('heading', { level: 2 });
    expect(note.parentElement!.contains(heading)).toBe(true);
    expect(note.parentElement!.className).toContain('gap-3');
    expect(note.parentElement!.lastElementChild).toBe(note);
  });

  it('applyNote 가 없으면 줄 0', async () => {
    setup();
    await ready();
    expect(screen.queryByTestId('module-apply-note')).toBeNull();
  });
});

describe('AD-02 ② 판 고름 — 판마다 prompt-model 한 번', () => {
  it('v2 · v1 · 기본 판 · v3 을 차례로 고르면 판마다 한 번, 다시 골라도 0 — 카드 이름만 바뀐다', async () => {
    const { fake } = setup();
    await ready();
    for (const [key, name] of [
      ['12', 'v2'],
      ['11', 'v1'],
      ['default', '기본 설정'],
      ['13', 'v3'],
    ] as const) {
      pickVersion(key);
      await titled(name);
    }
    for (const component of [/^모델 설정/, /^고정 규칙/, /^프롬프트/]) {
      choose(t.columns.component, component);
      pickVersion('12');
      pickVersion('13');
    }
    await settle();
    expect(fake.args('promptModel')).toEqual(['13', '12', '11', 'default']);
    expect(fake.count('list')).toBe(1);
  });

  it('판 줄 이름: 「v3 · 이름」, 이름 없는 옛 판은 「v3」 꼴만(「v1 · 」 아님), 기본 판은 「기본 설정」, 긴 이름은 title 로 전체', async () => {
    const long = '가'.repeat(40);
    const [v3, v2, v1] = fakeVersionRows();
    const fake = fakeAiSettingModule({
      rows: [{ ...v3!, title: long }, v2!, v1!],
    });
    setup({ fake });
    await ready();
    const name = (key: string) =>
      document.querySelector(`[data-version="${key}"]`)!;
    expect(name('13').textContent).toBe(`v3 · ${long}`);
    expect(name('13').getAttribute('title')).toBe(`v3 · ${long}`);
    expect(name('13').className).toContain('truncate');
    expect(name('12').textContent).toBe('v2 · 지어낸 판 둘');
    expect(name('11').textContent).toBe('v1');
    expect(name('default').textContent).toBe('기본 설정');
  });

  it('목록 세대 셈: 모듈이 바뀌면 옛 모듈의 늦은 목록 답은 버린다', async () => {
    const old = fakeAiSettingModule();
    const late = deferred<VersionPageOutcome>();
    old.override.list = () => late.promise;
    const { view } = setup({ fake: old });
    const next = fakeAiSettingModule({ rows: [], appliedDefault: true });
    view.rerender(<AiSettingsScreen modules={[next.module]} />);
    await titled('기본 설정');
    await act(async () => {
      late.resolve({ kind: 'failed' });
      await new Promise((done) => setTimeout(done, 20));
    });
    expect(document.querySelector('[data-version="13"]')).toBeNull();
    expect(screen.queryByTestId('load-failure')).toBeNull();
    expect(old.count('promptModel')).toBe(0);
  });

  it('total 이 실린 수보다 많으면 판 열 끝 [더 보기] → list(offset = 실린 수), 줄을 이어 붙인다', async () => {
    const fake = fakeAiSettingModule({ pageSize: 2 });
    setup({ fake });
    await ready();
    expect(document.querySelector('[data-version="11"]')).toBeNull();
    fireEvent.click(button(t.more));
    await waitFor(() =>
      expect(document.querySelector('[data-version="11"]')).not.toBeNull(),
    );
    expect(screen.queryByRole('button', { name: t.more })).toBeNull();
    expect(fake.args('list')).toEqual([0, 2]);
  });

  it('StrictMode 에서도 처음 고른 판(v3) 하나가 그려지고 prompt-model 은 한 번', async () => {
    const fake = fakeAiSettingModule();
    render(
      <StrictMode>
        <AiSettingsScreen modules={[fake.module]} />
      </StrictMode>,
    );
    await ready();
    await settle();
    expect(fake.args('promptModel')).toEqual(['13']);
  });

  it('prompt-model 300ms 뒤 상세 자리 aria-busy, 실패 → 「AI 설정을 불러오지 못했어요」 + [다시 시도] → 다시 받아 그린다', async () => {
    const fake = fakeAiSettingModule();
    const slow = deferred<PromptModelOutcome>();
    fake.override.promptModel = [() => slow.promise];
    setup({ fake });
    await screen.findByTestId('detail-loading');
    expect(
      screen.getByTestId('detail-loading').getAttribute('aria-busy'),
    ).toBeNull();
    await waitFor(
      () =>
        expect(
          screen.getByTestId('detail-loading').getAttribute('aria-busy'),
        ).toBe('true'),
      { timeout: 1000 },
    );
    await act(async () => {
      slow.resolve({ kind: 'failed' });
      await new Promise((done) => setTimeout(done, 20));
    });
    const failure = await screen.findByTestId('detail-failure');
    expect(within(failure).getByText(t.failed)).toBeTruthy();
    fireEvent.click(within(failure).getByRole('button', { name: t.retry }));
    await ready();
    expect(fake.args('promptModel')).toEqual(['13', '13']);
  });

  it.each([
    ['없는 판(missing)', { kind: 'missing' } as const, 'failure'],
    [
      '쓸 수 없는 판(unusable)',
      { kind: 'unusable', message: '지어낸 서버 문장' } as const,
      'unusable',
    ],
  ])(
    '%s → 상세 자리에 실패 상자 또는 서버 문장 한 줄',
    async (_, outcome, shown) => {
      const fake = fakeAiSettingModule({ promptModel: () => outcome });
      setup({ fake });
      if (shown === 'failure')
        expect(await screen.findByTestId('detail-failure')).toBeTruthy();
      else
        expect((await screen.findByTestId('detail-unusable')).textContent).toBe(
          '지어낸 서버 문장',
        );
      expect(
        screen.queryByRole('heading', { name: t.prompt.title('v3') }),
      ).toBeNull();
    },
  );
});

describe('AD-02 ③ 구성·셋째 열·상세 카드(r3)', () => {
  it('구성 열은 r3 차례(모델 설정 · 프롬프트 · 모듈 줄 · 서버 고정 값 묶음 · 읽기 전용 규칙), 꼬리는 서버 값으로 셈', async () => {
    setup();
    await ready();
    expect(lines(t.columns.component)).toEqual([
      '모델 설정모든 단계에 하나',
      '프롬프트1단계 · 4칸',
      '지어낸 대상 단어준비 중',
      '파트3개 · 고정',
      '처리 값5개 · 고정',
      '고정 규칙읽기 전용',
    ]);
    expect(column(t.columns.component).textContent).not.toContain('판정 기준');
  });

  it('모델 꼬리: 단계마다 모델이 다르면 「<첫 모델> · 단계마다 다름」, 단계 둘이면 모델 카드도 단계마다 한 줄(단계 이름이 칸 이름 앞)', async () => {
    const two = fakePromptModel('v3');
    const second = {
      ...two.models[0]!,
      key: 'judge2',
      label: '지어낸 둘째 단계',
      model: {
        ...two.models[0]!.model,
        route: 'fake-think',
        models: two.models[0]!.routeChoices[1]!.models,
        temperature: null,
      },
    };
    const group2 = {
      ...two.promptGroups[0]!,
      key: 'judge2',
      label: '지어낸 둘째 단계',
      modelSlots: ['judge2'],
    };
    const fake = fakeAiSettingModule({
      promptModel: () => ({
        kind: 'ok',
        model: {
          ...two,
          models: [two.models[0]!, second],
          promptGroups: [two.promptGroups[0]!, group2],
        },
      }),
    });
    setup({ fake });
    await ready();
    expect(lines(t.columns.component)[0]).toBe(
      `모델 설정${t.components.modelMany('지어낸 미니')}`,
    );
    expect(lines(t.columns.component)[1]).toBe('프롬프트2단계 · 8칸');
    choose(t.columns.component, /^모델 설정/);
    const model = card('model');
    expect(model.querySelectorAll('[data-step]')).toHaveLength(2);
    expect(
      within(model).getByText('지어낸 둘째 단계 temperature'),
    ).toBeTruthy();
    expect(
      model.querySelector('[data-step="judge2"] [data-value="temperature"]')!
        .textContent,
    ).toBe('–');
  });

  it('모델 설정 카드(읽기 — editable.model 거짓): 모델 「지어낸 미니」 · temperature 0.2 · 출력 상한 2000, 웹검색 0, 고칠 칸 0', async () => {
    setup({
      fake: fakeAiSettingModule({
        modelNote: '지어낸 모델 곁 글',
        promptModel: (key) => ({
          kind: 'ok',
          model: fakePromptModel(key, {
            editable: { model: false, prompts: true },
          }),
        }),
      }),
    });
    await ready();
    choose(t.columns.component, /^모델 설정/);
    const model = card('model');
    expect(within(model).getByText('지어낸 모델 곁 글')).toBeTruthy();
    expect(
      [...model.querySelectorAll('[data-value]')].map(
        (node) => node.textContent,
      ),
    ).toEqual(['지어낸 미니', '0.2', '2000']);
    expect(model.querySelectorAll('input, select, textarea')).toHaveLength(0);
    expect(document.body.textContent).not.toMatch(/웹 ?검색/);
  });

  it('셋째 열 「단계 — 프롬프트」 = 칸 고름 넷(「1. 칸 이름」 — 서버 label), 누르면 그 칸의 단계 카드', async () => {
    setup();
    await ready();
    expect(lines(t.columns.category)).toEqual([
      '1. 지어낸 찾기',
      '2. 지어낸 판정',
      '3. 지어낸 고치기',
      '4. 지어낸 낮음 전용',
    ]);
    expect(pressed(t.columns.category)).toEqual(['1. 지어낸 찾기']);
    choose(t.columns.category, '2. 지어낸 판정');
    const slot = card('prompt-slot');
    expect(within(slot).getByRole('heading').textContent).toBe('지어낸 판정');
    expect(slot.textContent).toContain('eval');
    expect(
      (
        within(slot).getByRole('textbox', {
          name: '지어낸 판정 프롬프트',
        }) as HTMLTextAreaElement
      ).value,
    ).toBe(fakePromptModel('v3').promptGroups[0]!.prompts[1]!.text);
    // 다른 구성에서 칸을 누르면 프롬프트 구성으로
    choose(t.columns.component, /^모델 설정/);
    choose(t.columns.category, '3. 지어낸 고치기');
    expect(pressed(t.columns.component)[0]).toContain('프롬프트');
    expect(within(card('prompt-slot')).getByRole('heading').textContent).toBe(
      '지어낸 고치기',
    );
  });

  it('단계 카드(읽기 — editable.prompts 거짓): 글 전문·글자 수·출력절 안내·처음 글 그대로 줄·메모, 출력절이 없으면 경고 — 고칠 수 없다', async () => {
    const fake = fakeAiSettingModule({
      promptModel: (key) => ({
        kind: 'ok',
        model: fakePromptModel(key, {
          prompts: {
            detect: { text: '지어낸 고친 글 😀', memo: '지어낸 고친 메모' },
          },
          editable: { model: true, prompts: false },
        }),
      }),
    });
    setup({ fake });
    await ready();
    const slot = card('prompt-slot');
    const text = within(slot).getByRole('textbox', {
      name: '지어낸 찾기 프롬프트',
    }) as HTMLTextAreaElement;
    expect(text.value).toBe('지어낸 고친 글 😀');
    expect(text.readOnly).toBe(true);
    expect(within(slot).getByTestId('text-count').textContent).toBe(
      t.prompt.count(10, 8000),
    );
    expect(within(slot).getByTestId('output-lost').textContent).toBe(
      t.prompt.outputLost,
    );
    expect(slot.textContent).toContain(t.prompt.outputNote);
    expect(slot.textContent).not.toContain(t.prompt.untouched);
    expect(
      (
        within(slot).getByRole('textbox', {
          name: '지어낸 찾기 메모',
        }) as HTMLInputElement
      ).value,
    ).toBe('지어낸 고친 메모');
    choose(t.columns.category, '2. 지어낸 판정');
    const other = card('prompt-slot');
    expect(other.textContent).toContain(t.prompt.untouched);
    expect(within(other).queryByTestId('output-lost')).toBeNull();
  });

  it('프롬프트 카드 머리의 판 정보: 만든 때 · 만든 사람 · 메모, 이름 null → 「알 수 없는 사람」, 빈 메모 → 「–」, 기본 판은 없음', async () => {
    setup();
    await ready();
    expect(screen.getByTestId('created').textContent).toBe(
      '2026-10-19 11:40 · 지어낸 관리자',
    );
    expect(screen.getByTestId('memo').textContent).toBe('지어낸 메모 셋');
    pickVersion('11');
    await titled('v1');
    expect(screen.getByTestId('created').textContent).toBe(
      `2026-10-17 09:00 · ${t.unknownAuthor}`,
    );
    expect(screen.getByTestId('memo').textContent).toBe(t.emptyMemo);
    pickVersion('default');
    await titled('기본 설정');
    expect(screen.queryByTestId('version-meta')).toBeNull();
  });

  it('고정 값 묶음: 「파트 · 고정」 + 「고정 값이라 바꿀 수 없어요」 + 항목(값 없는 항목은 이름만, 배열은 「 · 」)', async () => {
    setup();
    await ready();
    choose(t.columns.component, /^파트/);
    expect(within(card('fixed')).getByRole('heading').textContent).toBe(
      '파트 · 고정',
    );
    expect(card('fixed').textContent).toContain(t.fixedNote);
    expect(
      [...card('fixed').querySelectorAll('li')].map((node) => node.textContent),
    ).toEqual(['지어낸 파트 가', '지어낸 파트 나', '지어낸 파트 다']);
    choose(t.columns.component, /^처리 값/);
    expect(
      [...card('fixed').querySelectorAll('li')].map((node) => node.textContent),
    ).toEqual([
      '지어낸 값 하나30',
      '지어낸 값 둘1200',
      '지어낸 값 셋Mid',
      '지어낸 값 넷High · Mid',
      '지어낸 값 다섯5',
    ]);
  });

  it('모듈 줄: 준비 중(pending) 카드 · 읽기 전용 줄 글(lines) 카드 — prompt-model 과 무관', async () => {
    const fake = fakeAiSettingModule({
      promptModel: () => ({ kind: 'failed' }),
    });
    setup({ fake });
    await screen.findByTestId('detail-failure');
    choose(t.columns.component, /^지어낸 대상 단어/);
    expect(card('pending').textContent).toBe(t.pending);
    choose(t.columns.component, /^고정 규칙/);
    const rules = screen.getByTestId('fixed-rules');
    expect(rules.textContent).toContain('고정 규칙 · 읽기 전용');
    expect(
      [...rules.querySelectorAll('li')].map((node) => node.textContent),
    ).toEqual(['지어낸 규칙 하나', '지어낸 규칙 둘']);
    expect(rules.textContent).toContain('지어낸 규칙 꼬리');
    // 시안 v148 꼴(GW3R C11·C12): 1px 점선 · 옅은 회색 바탕 · 16px 24px, 제목 600 14 primary + 자물쇠.
    expect(rules.className.split(/\s+/)).toEqual(
      expect.arrayContaining([
        'border-dashed',
        'border-border-secondary',
        'bg-support-grey-subtle',
        'px-6',
        'py-4',
      ]),
    );
    const head = rules.querySelector('h4')!;
    expect(head.className.split(/\s+/)).toEqual(
      expect.arrayContaining(['text-style-pre-body-04', 'text-text-primary']),
    );
    expect(head.querySelectorAll('svg')).toHaveLength(1);
  });
});

// 밴드 LK2(sid:MARC-ISSUE-346): 고정 항목 자물쇠 — 구성 열 고정 줄마다 14px, 고정 값 카드 h3 앞 16px, 고정 규칙 h4 는 그대로 하나.
describe('AD-02 고정 항목 자물쇠(LK2)', () => {
  const lockOf = (item: Element) => item.querySelectorAll('svg');

  it('구성 열: 고정 값 묶음·고정 규칙 줄마다 자물쇠 하나, 모델·프롬프트·대상 단어 줄은 0', async () => {
    setup();
    await ready();
    const items = within(column(t.columns.component)).getAllByRole('button');
    expect(items.map((item) => lockOf(item).length)).toEqual([
      0, 0, 0, 1, 1, 1,
    ]);
    for (const item of items.slice(3)) {
      const icon = lockOf(item)[0]!;
      expect(icon.getAttribute('aria-hidden')).toBe('true');
      expect(icon.getAttribute('class')!.split(/\s+/)).toEqual(
        expect.arrayContaining(['size-3.5', 'text-text-tertiary']),
      );
    }
  });

  it('고정 값 카드 h3 앞 자물쇠(size-4, aria-hidden) — 제목 글 그대로', async () => {
    setup();
    await ready();
    choose(t.columns.component, /^처리 값/);
    const head = within(card('fixed')).getByRole('heading', { level: 3 });
    expect(head.textContent).toBe('처리 값 · 고정');
    const icons = head.querySelectorAll('svg');
    expect(icons).toHaveLength(1);
    expect(head.firstElementChild).toBe(icons[0]!);
    expect(icons[0]!.getAttribute('aria-hidden')).toBe('true');
    expect(icons[0]!.getAttribute('class')!.split(/\s+/)).toEqual(
      expect.arrayContaining(['size-4', 'shrink-0', 'text-text-tertiary']),
    );
    expect(head.className.split(/\s+/)).toEqual(
      expect.arrayContaining(['flex', 'items-center', 'gap-2']),
    );
  });

  it('고정 규칙 카드: h4 자물쇠 그대로 하나', async () => {
    setup();
    await ready();
    choose(t.columns.component, /^고정 규칙/);
    const rules = screen.getByTestId('fixed-rules');
    expect(rules.querySelector('h4')!.querySelectorAll('svg')).toHaveLength(1);
  });
});

describe('AD-02 ④ 단추·불러오기·꼴', () => {
  it('[이 버전을 바탕으로 새 버전]은 판 읽기가 되면 켬(title — r3 곁 글), 쓸 수 없는 판이면 끔, [테스트 비교로] 링크 없음', async () => {
    setup({
      fake: fakeAiSettingModule({
        promptModel: (key) =>
          key === '12' ?
            { kind: 'unusable', message: '지어낸 쓸 수 없는 판 문장' }
          : { kind: 'ok', model: fakePromptModel(key) },
      }),
    });
    await ready();
    expect(button(t.newVersion).getAttribute('aria-disabled')).toBeNull();
    expect(button(t.newVersion).getAttribute('title')).toBe(t.newVersionNote);
    pickVersion('12');
    await screen.findByTestId('detail-unusable');
    expect(button(t.newVersion).getAttribute('aria-disabled')).toBe('true');
    expect(screen.queryByRole('link', { name: /테스트 비교/ })).toBeNull();
  });

  it('300ms 뒤 aria-busy, 목록 실패 → 「AI 설정을 불러오지 못했어요」 + [다시 시도] → 열 셋', async () => {
    const fake = fakeAiSettingModule();
    const slow = deferred<VersionPageOutcome>();
    fake.override.list = [() => slow.promise];
    vi.useFakeTimers();
    try {
      setup({ fake });
      expect(
        screen.getByTestId('loading').getAttribute('aria-busy'),
      ).toBeNull();
      await act(() => vi.advanceTimersByTimeAsync(300));
      expect(screen.getByTestId('loading').getAttribute('aria-busy')).toBe(
        'true',
      );
    } finally {
      vi.useRealTimers();
    }
    await act(async () => {
      slow.resolve({ kind: 'failed' });
      await new Promise((done) => setTimeout(done, 20));
    });
    const failure = await screen.findByTestId('load-failure');
    expect(within(failure).getByText(t.failed)).toBeTruthy();
    fireEvent.click(within(failure).getByRole('button', { name: t.retry }));
    await ready();
  });

  it('열 셋 상자는 1px grey-800 테두리·모서리 16, 열 머리는 가운데 14/700 primary·52px(DT1 C12·J1)', async () => {
    setup();
    await ready();
    const box = column(t.columns.version).parentElement!;
    expect(box.className).toContain('border-grey-800');
    expect(box.className).toMatch(/\bborder\b/);
    expect(box.className).toContain('rounded-dialog');
    for (const name of [
      t.columns.version,
      t.columns.component,
      t.columns.category,
    ]) {
      const head = within(column(name)).getByRole('heading', { level: 3 });
      expect(head.textContent).toBe(name);
      expect(head.className).toContain('text-center');
      expect(head.className).toContain('text-style-pre-body-04');
      expect(head.className).toContain('text-text-primary');
      expect(head.className).toContain('h-[52px]');
    }
  });
});

// ───────── 적용은 확인 창 → port.apply(서버 판은 바뀌지 않는다) ─────────

const versionButton = (key: string) =>
  document.querySelector(`[data-version="${key}"]`)!.closest('button')!;
const badgeOf = (key: string) =>
  versionButton(key).querySelector('[data-version] + *')!.textContent;
const applyButton = () => button(t.apply);
const a = t.applyDialog;

describe('AD-02 ⑥ 적용 — 확인 창 → port.apply', () => {
  it('v3 [이 버전 적용] → 확인 창(제목·본문·[취소]·[적용]) → apply(13) 한 번 → 창 닫힘 → 목록 다시 → v3 「적용 중」·v2 「지난 버전」·알림, v3 의 [이 버전 적용]은 끔', async () => {
    const { fake } = setup();
    await ready();
    fireEvent.click(applyButton());
    const dialog = await screen.findByRole('dialog');
    expect(within(dialog).getByRole('heading').textContent).toBe(a.title('v3'));
    expect(dialog.textContent).toContain(a.body('v3', 'v2'));
    expect(fake.count('apply')).toBe(0);
    fireEvent.click(within(dialog).getByRole('button', { name: a.confirm }));
    await waitFor(() => expect(screen.queryByRole('dialog')).toBeNull());
    expect(fake.args('apply')).toEqual(['13']);
    await waitFor(() => expect(badgeOf('13')).toBe(t.status.applied));
    expect(badgeOf('12')).toBe(t.status.past);
    expect(fake.count('list')).toBe(2);
    expect(screen.getByTestId('notice').textContent).toBe(a.done('v3'));
    expect(applyButton().getAttribute('aria-disabled')).toBe('true');
    fireEvent.click(applyButton());
    expect(screen.queryByRole('dialog')).toBeNull();
    expect(fake.count('apply')).toBe(1);
  });

  it('기본 판 적용 → apply(null) → 기본 판 줄 「적용 중」, v2 「지난 버전」', async () => {
    const { fake } = setup();
    await ready();
    pickVersion('default');
    await titled('기본 설정');
    expect(badgeOf('default')).toBe(t.status.default);
    fireEvent.click(applyButton());
    const dialog = await screen.findByRole('dialog');
    expect(within(dialog).getByRole('heading').textContent).toBe(
      a.title(a.defaultName),
    );
    fireEvent.click(within(dialog).getByRole('button', { name: a.confirm }));
    await waitFor(() => expect(badgeOf('default')).toBe(t.status.applied));
    expect(fake.args('apply')).toEqual([null]);
    expect(badgeOf('12')).toBe(t.status.past);
    expect(applyButton().getAttribute('aria-disabled')).toBe('true');
  });

  it('이미 적용 중인 판(v2)은 [이 버전 적용] 끔 — 눌러도 창 0·apply 0', async () => {
    const { fake } = setup({ initialVersion: 'v2' });
    await titled('v2');
    expect(applyButton().getAttribute('aria-disabled')).toBe('true');
    fireEvent.click(applyButton());
    expect(screen.queryByRole('dialog')).toBeNull();
    expect(fake.count('apply')).toBe(0);
  });

  it('[적용] 두 번 누름 → apply 한 번', async () => {
    const fake = fakeAiSettingModule();
    const slow = deferred<{ kind: 'ok' }>();
    fake.override.apply = [() => slow.promise];
    setup({ fake });
    await ready();
    fireEvent.click(applyButton());
    const dialog = await screen.findByRole('dialog');
    const confirm = within(dialog).getByRole('button', { name: a.confirm });
    fireEvent.click(confirm);
    fireEvent.click(confirm);
    await settle();
    expect(fake.count('apply')).toBe(1);
    await act(async () => {
      slow.resolve({ kind: 'ok' });
      await new Promise((done) => setTimeout(done, 20));
    });
    await waitFor(() => expect(screen.queryByRole('dialog')).toBeNull());
  });

  it.each([
    ['실패 갈래', () => Promise.resolve({ kind: 'failed' as const })],
    ['던짐', () => Promise.reject(new TypeError('끊김'))],
  ])(
    '적용 실패(%s) → 창 안 빨강 줄, 창은 닫히지 않고 배지 그대로',
    async (_, answer) => {
      const fake = fakeAiSettingModule();
      fake.override.apply = answer;
      setup({ fake });
      await ready();
      fireEvent.click(applyButton());
      const dialog = await screen.findByRole('dialog');
      fireEvent.click(within(dialog).getByRole('button', { name: a.confirm }));
      expect(
        (await within(dialog).findByTestId('apply-failure')).textContent,
      ).toBe(a.failed);
      expect(screen.getByRole('dialog')).toBeTruthy();
      expect(badgeOf('13')).toBe(t.status.testing);
      fireEvent.click(within(dialog).getByRole('button', { name: a.cancel }));
      await waitFor(() => expect(screen.queryByRole('dialog')).toBeNull());
    },
  );

  it('[취소] 는 창만 닫는다(apply 0)', async () => {
    const { fake } = setup();
    await ready();
    fireEvent.click(applyButton());
    const dialog = await screen.findByRole('dialog');
    fireEvent.click(within(dialog).getByRole('button', { name: a.cancel }));
    await waitFor(() => expect(screen.queryByRole('dialog')).toBeNull());
    expect(fake.count('apply')).toBe(0);
  });

  it('끈 단추([새 버전] — 판 읽기 전)는 눌러도 부름 0', async () => {
    const fake = fakeAiSettingModule();
    const slow = deferred<PromptModelOutcome>();
    fake.override.promptModel = [() => slow.promise];
    setup({ fake });
    await screen.findByRole('heading', { name: t.title('지어낸 모듈') });
    await waitFor(() => expect(fake.count('promptModel')).toBe(1));
    const before = fake.calls.length;
    expect(button(t.newVersion).getAttribute('aria-disabled')).toBe('true');
    fireEvent.click(button(t.newVersion));
    await settle();
    expect(fake.calls.length).toBe(before);
    expect(screen.queryByRole('dialog')).toBeNull();
  });
});

describe('AD-02 ⑦ 판 초안·한 번 저장(AD2W ③)', () => {
  const s = t.save;
  const openModel = () => choose(t.columns.component, /^모델 설정/);
  const tokens = () =>
    screen.getByRole('textbox', { name: t.model.maxOutputTokens });
  const temperature = () =>
    screen.getByRole('textbox', { name: t.model.temperature });
  const route = () => screen.getByRole('combobox', { name: t.model.route });
  const type = (node: HTMLElement, value: string) =>
    fireEvent.change(node, { target: { value } });
  const saveBar = () => screen.queryByTestId('save-bar');
  const saveDialog = () => screen.getByTestId('save-dialog');
  const confirmSave = () =>
    within(saveDialog()).getByRole('button', { name: s.confirm });
  /**
   * v3 의 모델 출력 상한을 3000 으로(고친 것 1개). 처음 판은 initialVersion 으로 박는다 — 고르지 않은 채면 저장 뒤 처음 고름이
   * 가장 새 「초안」(새 판)으로 떨어져 「새 판 고름」을 빼도 초록이 된다(심은 파손 P11).
   */
  async function editTokens(fake?: Fake) {
    const view = setup({ initialVersion: 'v3', ...(fake ? { fake } : {}) });
    await ready();
    openModel();
    type(tokens(), '3000');
    return view;
  }
  /** 고른 판이 바뀌기를 기다린다(구성은 모델 설정 그대로 — 판 열의 고른 줄). */
  const shown = (name: string) =>
    waitFor(() => expect(pressed(t.columns.version)[0]).toContain(name));
  async function openSaveWith(title: string, memo = '') {
    fireEvent.click(button(t.saveBar.save));
    await screen.findByTestId('save-dialog');
    type(within(saveDialog()).getByRole('textbox', { name: s.name }), title);
    type(within(saveDialog()).getByRole('textbox', { name: s.memo }), memo);
  }

  it('모델 칸 고침 → 저장 막대 「고친 것 1개」 · 모델 줄 「고침 1」 · v3 줄 주황 테두리 + 날짜 꼬리 다음 「v3 바탕으로 고치는 중」 · [이 버전 적용] 끔 + 곁 글, 같은 값으로 되돌리면 0', async () => {
    await editTokens();
    expect(saveBar()!.textContent).toContain(t.saveBar.count(1));
    expect(saveBar()!.textContent).toBe(
      t.saveBar.count(1) + t.saveBar.revert + t.saveBar.save,
    );
    expect(lines(t.columns.component)[0]).toBe(
      t.components.model + t.components.edited(1),
    );
    const v3 = versionButton('13');
    expect(v3.getAttribute('data-editing')).toBe('true');
    expect(v3.querySelector('[data-edit-tag]')).toBeNull();
    expect(v3.textContent).toMatch(/2026-10-\d\d/);
    expect(v3.textContent).toContain(t.editingSum('v3'));
    expect(applyButton().getAttribute('aria-disabled')).toBe('true');
    expect(screen.getByTestId('apply-note').textContent).toBe(t.applyAfterSave);
    expect(screen.getByTestId('model-edited').textContent).toBe(
      t.prompt.edited,
    );
    type(tokens(), '2000');
    expect(saveBar()).toBeNull();
    expect(versionButton('13').getAttribute('data-editing')).toBeNull();
    expect(applyButton().getAttribute('aria-disabled')).toBeNull();
    expect(screen.queryByTestId('apply-note')).toBeNull();
  });

  it('구성을 옮겨도 초안은 남는다(프롬프트 → 모델 설정 다시 — 3000 그대로)', async () => {
    await editTokens();
    choose(t.columns.component, /^프롬프트/);
    expect(saveBar()).not.toBeNull();
    openModel();
    expect((tokens() as HTMLInputElement).value).toBe('3000');
  });

  it('[새 버전으로 저장] → 저장 창(r3 글·고친 것 「모델 설정」·번호 추정 v4) → 이름·메모 → [저장] = create 한 번(바탕 13, 본문 키 넷 · 모델 다섯 칸 · 칸 넷은 바탕 바이트) → 창 닫힘 → 목록 다시 → v4 고름·prompt-model 14 · 알림', async () => {
    const { fake } = await editTokens();
    fireEvent.click(button(t.saveBar.save));
    const dialog = await screen.findByTestId('save-dialog');
    expect(within(dialog).getByRole('heading').textContent).toBe(s.title);
    expect(dialog.textContent).toContain(
      s.body(t.baseName('v3', false), 1, 'v2'),
    );
    expect(within(dialog).getByTestId('save-changes').textContent).toBe(
      t.changed.model,
    );
    expect(within(dialog).getByTestId('save-number').textContent).toBe('v4');
    type(within(dialog).getByRole('textbox', { name: s.name }), '지어낸 새 판');
    type(
      within(dialog).getByRole('textbox', { name: s.memo }),
      '지어낸 판 메모',
    );
    fireEvent.click(confirmSave());
    await waitFor(() => expect(screen.queryByTestId('save-dialog')).toBeNull());
    expect(fake.count('create')).toBe(1);
    const [{ base, body }] = fake.args('create') as [
      { base: string; body: Record<string, unknown> },
    ];
    expect(base).toBe('13');
    expect(Object.keys(body)).toEqual([
      'title',
      'memo',
      'modelSettings',
      'prompts',
    ]);
    expect(body.title).toBe('지어낸 새 판');
    expect(body.memo).toBe('지어낸 판 메모');
    expect(body.modelSettings).toEqual({
      steps: [
        {
          key: 'judge',
          route: 'fake-mini',
          temperature: 0.2,
          maxOutputTokens: 3000,
          webSearch: false,
        },
      ],
    });
    const v3 = fakePromptModel('13').promptGroups[0]!.prompts;
    expect(body.prompts).toEqual({
      steps: [
        {
          key: 'judge',
          prompts: v3.map((one) => ({
            key: one.key,
            text: one.text,
            memo: one.memo,
          })),
        },
      ],
    });
    await shown('v4 · 지어낸 새 판');
    expect(fake.count('list')).toBe(2);
    expect(fake.args('promptModel')).toEqual(['13', '14']);
    expect(screen.getByTestId('notice').textContent).toBe(s.done('v4'));
    expect(saveBar()).toBeNull();
    expect(pressed(t.columns.version)[0]).toContain('v4 · 지어낸 새 판');
  });

  it.each([
    ['[저장] 두 번 누름', (node: HTMLElement) => node.click()],
    [
      '이름 칸 Enter 두 번',
      (node: HTMLElement) => fireEvent.submit(node.closest('form')!),
    ],
  ])('보내는 중 두 번(%s — 한 act 안) → create 한 번', async (_, press) => {
    const fake = fakeAiSettingModule();
    const slow = deferred<{ kind: 'failed' }>();
    fake.override.create = [() => slow.promise];
    await editTokens(fake);
    await openSaveWith('지어낸 새 판');
    const node = confirmSave();
    act(() => {
      press(node);
      press(node);
    });
    await settle();
    expect(fake.count('create')).toBe(1);
    await act(async () => {
      slow.resolve({ kind: 'failed' });
      await new Promise((done) => setTimeout(done, 20));
    });
    expect(screen.getByTestId('save-failure').textContent).toBe(s.failed);
  });

  it('끔 단추 셋: 고친 동안 [이 버전 적용]·[새 버전]과 이름 빈 [저장]은 눌러도 부름 0·창 0', async () => {
    const { fake } = await editTokens();
    const before = fake.calls.length;
    fireEvent.click(applyButton());
    fireEvent.click(button(t.newVersion));
    await settle();
    expect(screen.queryByRole('dialog')).toBeNull();
    expect(button(t.newVersion).getAttribute('aria-disabled')).toBe('true');
    fireEvent.click(button(t.saveBar.save));
    await screen.findByTestId('save-dialog');
    expect(screen.getByTestId('name-error').textContent).toBe(s.nameEmpty);
    expect(confirmSave().getAttribute('aria-disabled')).toBe('true');
    fireEvent.click(confirmSave());
    fireEvent.submit(confirmSave().closest('form')!);
    type(
      within(saveDialog()).getByRole('textbox', { name: s.name }),
      ' \u3000 ',
    );
    fireEvent.click(confirmSave());
    await settle();
    expect(fake.calls.length).toBe(before);
    expect(fake.count('apply')).toBe(0);
    expect(fake.count('create')).toBe(0);
  });

  it('이름은 서버 셈(41자 넘침 · 앞뒤 공백 뗀 뒤 40자는 됨), 메모 201자 넘침 → 칸 아래 줄·[저장] 끔', async () => {
    await editTokens();
    await openSaveWith('가'.repeat(41));
    expect(screen.getByTestId('name-error').textContent).toBe(s.nameOver);
    expect(confirmSave().getAttribute('aria-disabled')).toBe('true');
    type(
      within(saveDialog()).getByRole('textbox', { name: s.name }),
      ` ${'가'.repeat(40)} `,
    );
    expect(screen.queryByTestId('name-error')).toBeNull();
    expect(confirmSave().getAttribute('aria-disabled')).toBeNull();
    type(
      within(saveDialog()).getByRole('textbox', { name: s.memo }),
      '나'.repeat(201),
    );
    expect(screen.getByTestId('memo-error').textContent).toBe(s.memoOver);
    expect(confirmSave().getAttribute('aria-disabled')).toBe('true');
  });

  it.each([
    ['닿지 못함', { kind: 'failed' }, s.failed, 'save-failure'],
    [
      '모델 거절(AI_MODEL_ROUTE_UNAVAILABLE)',
      {
        kind: 'rejected',
        code: 'AI_MODEL_ROUTE_UNAVAILABLE',
        message: '지어낸 모델 문장',
        fields: {},
      },
      s.modelRefused('지어낸 모델 문장'),
      'save-failure',
    ],
    [
      '꼴 틀림 fields.title',
      {
        kind: 'rejected',
        code: 'VALIDATION_ERROR',
        message: '지어낸 꼴 문장',
        fields: { title: ['지어낸 이름 문장'] },
      },
      '지어낸 이름 문장',
      'name-error',
    ],
    [
      '꼴 틀림 fields.memo',
      {
        kind: 'rejected',
        code: 'VALIDATION_ERROR',
        message: '지어낸 꼴 문장',
        fields: { memo: ['지어낸 메모 문장'] },
      },
      '지어낸 메모 문장',
      'memo-error',
    ],
    [
      '모르는 거절',
      { kind: 'rejected', code: null, message: null, fields: {} },
      s.failed,
      'save-failure',
    ],
  ] as const)(
    '저장 실패(%s) → 창 안 줄, 창·적은 것 그대로, 목록 다시 0',
    async (_, outcome, text, testId) => {
      const fake = fakeAiSettingModule();
      fake.override.create = () => outcome;
      await editTokens(fake);
      await openSaveWith('지어낸 새 판', '지어낸 판 메모');
      fireEvent.click(confirmSave());
      expect((await screen.findByTestId(testId)).textContent).toBe(text);
      expect(
        (
          within(saveDialog()).getByRole('textbox', {
            name: s.name,
          }) as HTMLInputElement
        ).value,
      ).toBe('지어낸 새 판');
      expect(fake.count('list')).toBe(1);
      expect(saveBar()).not.toBeNull();
    },
  );

  it('저장이 던지면(어댑터 밖 실패) 일반 실패 줄', async () => {
    const fake = fakeAiSettingModule();
    fake.override.create = () => Promise.reject(new TypeError('끊김'));
    await editTokens(fake);
    await openSaveWith('지어낸 새 판');
    fireEvent.click(confirmSave());
    expect((await screen.findByTestId('save-failure')).textContent).toBe(
      s.failed,
    );
  });

  it('고친 채 다른 판(v2) 누름 → 나가기 창 → [취소] 그대로(v3·초안) / [나가기] v2·초안 비움', async () => {
    const { fake } = await editTokens();
    pickVersion('12');
    const dialog = await screen.findByTestId('leave-confirm');
    expect(within(dialog).getByRole('heading').textContent).toBe(t.leave.title);
    expect(dialog.textContent).toContain(t.leave.body);
    fireEvent.click(
      within(dialog).getByRole('button', { name: t.leave.cancel }),
    );
    await waitFor(() =>
      expect(screen.queryByTestId('leave-confirm')).toBeNull(),
    );
    expect(saveBar()).not.toBeNull();
    expect(pressed(t.columns.version)[0]).toContain('v3');
    expect(fake.args('promptModel')).toEqual(['13']);
    pickVersion('12');
    fireEvent.click(
      within(await screen.findByTestId('leave-confirm')).getByRole('button', {
        name: t.leave.confirm,
      }),
    );
    await shown('v2');
    expect(saveBar()).toBeNull();
    expect(fake.args('promptModel')).toEqual(['13', '12']);
  });

  it('[되돌리기] → 되돌리기 창(r3 ⑤) → [되돌리기] 초안 비움, [취소] 는 그대로', async () => {
    await editTokens();
    fireEvent.click(button(t.saveBar.revert));
    let dialog = await screen.findByTestId('revert-confirm');
    expect(within(dialog).getByRole('heading').textContent).toBe(
      t.revert.title(1),
    );
    expect(dialog.textContent).toContain(t.revert.body('v3'));
    fireEvent.click(
      within(dialog).getByRole('button', { name: t.revert.cancel }),
    );
    await waitFor(() =>
      expect(screen.queryByTestId('revert-confirm')).toBeNull(),
    );
    expect(saveBar()).not.toBeNull();
    fireEvent.click(button(t.saveBar.revert));
    dialog = await screen.findByTestId('revert-confirm');
    fireEvent.click(
      within(dialog).getByRole('button', { name: t.revert.confirm }),
    );
    await waitFor(() => expect(saveBar()).toBeNull());
    expect((tokens() as HTMLInputElement).value).toBe('2000');
  });

  it('라우터가 막은 이동(leave.pending) → 나가기 창 → [나가기] proceed · [취소] reset, 고친 것은 onDirtyChange 로 알린다', async () => {
    const fake = fakeAiSettingModule();
    const proceed = vi.fn();
    const reset = vi.fn();
    const onDirtyChange = vi.fn();
    const view = render(
      <AiSettingsScreen
        modules={[fake.module]}
        onDirtyChange={onDirtyChange}
      />,
    );
    await ready();
    openModel();
    type(tokens(), '3000');
    expect(onDirtyChange).toHaveBeenLastCalledWith(true);
    const again = (leave?: {
      pending: boolean;
      proceed(): void;
      reset(): void;
    }) =>
      view.rerender(
        <AiSettingsScreen
          modules={[fake.module]}
          onDirtyChange={onDirtyChange}
          leave={leave}
        />,
      );
    again({ pending: true, proceed, reset });
    fireEvent.click(
      within(await screen.findByTestId('leave-confirm')).getByRole('button', {
        name: t.leave.cancel,
      }),
    );
    expect(reset).toHaveBeenCalledTimes(1);
    expect(proceed).not.toHaveBeenCalled();
    again({ pending: false, proceed, reset });
    expect(screen.queryByTestId('leave-confirm')).toBeNull();
    again({ pending: true, proceed, reset });
    fireEvent.click(
      within(screen.getByTestId('leave-confirm')).getByRole('button', {
        name: t.leave.confirm,
      }),
    );
    expect(proceed).toHaveBeenCalledTimes(1);
    expect(onDirtyChange).toHaveBeenLastCalledWith(false);
  });

  it('복제: [이 버전을 바탕으로 새 버전] → 저장 창(복제 글 · 고친 것 줄 없음) → create 본문은 바탕 값 그대로', async () => {
    const { fake } = setup();
    await ready();
    fireEvent.click(button(t.newVersion));
    const dialog = await screen.findByTestId('save-dialog');
    expect(dialog.textContent).toContain(
      s.copyBody(t.baseName('v3', false), 'v2'),
    );
    expect(within(dialog).queryByTestId('save-changes')).toBeNull();
    type(within(dialog).getByRole('textbox', { name: s.name }), '지어낸 복제');
    fireEvent.click(confirmSave());
    await titled('v4');
    const [{ body }] = fake.args('create') as [
      { body: { modelSettings: { steps: { maxOutputTokens: number }[] } } },
    ];
    expect(body.modelSettings.steps[0]!.maxOutputTokens).toBe(2000);
  });

  it('기본 판 바탕 저장 창은 「기본 설정을 바탕으로」, create 바탕은 default', async () => {
    const { fake } = setup();
    await ready();
    pickVersion('default');
    await titled('기본 설정');
    fireEvent.click(button(t.newVersion));
    const dialog = await screen.findByTestId('save-dialog');
    expect(dialog.textContent).toContain(
      s.copyBody(t.baseName('기본 설정', true), 'v2'),
    );
    type(within(dialog).getByRole('textbox', { name: s.name }), '지어낸 복제');
    fireEvent.click(confirmSave());
    await titled('v4');
    expect((fake.args('create')[0] as { base: string }).base).toBe('default');
  });

  it('경로 바꿈: temperature 를 받지 않는 경로면 「–」(본문 null), 다시 받는 경로면 바탕 값, 범위 밖이면 칸 아래 줄 · 저장 막대 [저장] 끔', async () => {
    const { fake } = setup();
    await ready();
    openModel();
    fireEvent.change(route(), { target: { value: 'fake-think' } });
    expect(
      screen.queryByRole('textbox', { name: t.model.temperature }),
    ).toBeNull();
    expect(
      card('model').querySelector('[data-value="temperature"]')!.textContent,
    ).toBe(t.none);
    expect(saveBar()!.textContent).toContain(t.saveBar.count(1));
    fireEvent.change(route(), { target: { value: 'fake-mini' } });
    expect((temperature() as HTMLInputElement).value).toBe('0.2');
    expect(saveBar()).toBeNull();
    type(temperature(), '2.5');
    expect(screen.getByText(t.model.temperatureRange)).toBeTruthy();
    type(tokens(), '16001');
    expect(screen.getByText(t.model.maxOutputRange(16000))).toBeTruthy();
    const save = within(saveBar()!).getByRole('button', {
      name: t.saveBar.save,
    });
    expect(save.getAttribute('aria-disabled')).toBe('true');
    fireEvent.click(save);
    expect(screen.queryByTestId('save-dialog')).toBeNull();
    type(temperature(), '2');
    type(tokens(), '16000');
    fireEvent.change(route(), { target: { value: 'fake-think' } });
    await openSaveWith('지어낸 생각 판');
    fireEvent.click(confirmSave());
    await shown('v4');
    const [{ body }] = fake.args('create') as [
      { body: { modelSettings: { steps: Record<string, unknown>[] } } },
    ];
    expect(body.modelSettings.steps[0]).toEqual({
      key: 'judge',
      route: 'fake-think',
      temperature: null,
      maxOutputTokens: 16000,
      webSearch: false,
    });
  });

  // 밴드 IRA2 K3: 모듈 hideTemperature 가 참인 모델 칸은 temperature 줄 0 — 안 숨긴 칸은 그대로, 본문은 읽은 값(null) 그대로.
  it('hideTemperature: 숨긴 칸(judge2)은 temperature 줄 0(라벨·값·「–」) · 안 숨긴 칸(judge)은 그대로 고칠 칸 · 저장 본문 judge2 temperature null 그대로', async () => {
    const two = fakePromptModel('v3');
    const second = {
      ...two.models[0]!,
      key: 'judge2',
      label: '지어낸 둘째 단계',
      model: { ...two.models[0]!.model, temperature: null },
    };
    const group2 = {
      ...two.promptGroups[0]!,
      key: 'judge2',
      label: '지어낸 둘째 단계',
      modelSlots: ['judge2'],
    };
    const fake = fakeAiSettingModule({
      promptModel: () => ({
        kind: 'ok',
        model: {
          ...two,
          models: [two.models[0]!, second],
          promptGroups: [two.promptGroups[0]!, group2],
        },
      }),
    });
    // 가짜 모듈 줄에 선택 칸 하나만 더한다(그 밖은 가짜 그대로).
    render(
      <AiSettingsScreen
        modules={[
          { ...fake.module, hideTemperature: (slot) => slot === 'judge2' },
        ]}
        initialVersion="v3"
      />,
    );
    await ready();
    openModel();
    const model = card('model');
    const hidden = model.querySelector('[data-step="judge2"]')!;
    expect(hidden.textContent).not.toContain(t.model.temperature);
    expect(hidden.querySelector('[data-value="temperature"]')).toBeNull();
    expect(hidden.textContent).not.toContain(t.none);
    expect(
      [...hidden.querySelectorAll('dt')].map((dt) => dt.textContent),
    ).toEqual([
      `지어낸 둘째 단계 ${t.model.route}`,
      `지어낸 둘째 단계 ${t.model.maxOutputTokens}`,
      expect.any(String),
    ]);
    const kept = screen.getByRole('textbox', {
      name: `${two.models[0]!.label} ${t.model.temperature}`,
    }) as HTMLInputElement;
    expect(kept.value).toBe('0.2');
    type(kept, '0.4');
    await openSaveWith('지어낸 숨김 판');
    fireEvent.click(confirmSave());
    await shown('v4');
    const [{ body }] = fake.args('create') as [
      { body: { modelSettings: { steps: Record<string, unknown>[] } } },
    ];
    expect(body.modelSettings.steps.map((step) => step.temperature)).toEqual([
      0.4,
      null,
    ]);
  });

  it('판을 바꾸면 고른 칸은 첫 칸으로(검증 권고 R3)', async () => {
    setup();
    await ready();
    choose(t.columns.category, /^4\./);
    pickVersion('12');
    await titled('v2');
    expect(pressed(t.columns.category)).toEqual([
      t.prompt.slot(1, '지어낸 찾기'),
    ]);
  });
});

describe('AD-02 ⑧ 프롬프트 칸 고침(AD2W ④)', () => {
  const s = t.save;
  const p = t.prompt;
  const type = (node: HTMLElement, value: string) =>
    fireEvent.change(node, { target: { value } });
  const slotText = (label: string) =>
    within(card('prompt-slot')).getByRole('textbox', {
      name: `${label} ${p.text}`,
    }) as HTMLTextAreaElement;
  const slotMemo = (label: string) =>
    within(card('prompt-slot')).getByRole('textbox', {
      name: `${label} ${p.memo}`,
    }) as HTMLInputElement;
  const saveBar = () => screen.queryByTestId('save-bar');
  const saveDialog = () => screen.getByTestId('save-dialog');
  const confirmSave = () =>
    within(saveDialog()).getByRole('button', { name: s.confirm });
  /** v3 의 둘째 칸(지어낸 판정)을 고른다. */
  async function openEval(fake?: Fake) {
    const view = setup({ initialVersion: 'v3', ...(fake ? { fake } : {}) });
    await ready();
    choose(t.columns.category, p.slot(2, '지어낸 판정'));
    return view;
  }
  async function saveAs(title: string) {
    fireEvent.click(button(t.saveBar.save));
    await screen.findByTestId('save-dialog');
    type(within(saveDialog()).getByRole('textbox', { name: s.name }), title);
    fireEvent.click(confirmSave());
  }

  it('글·메모 고침 → 「고친 것 1개」(칸 하나) · 칸 꼬리표 「고침 · 저장 전」 · 머리 「v3 바탕 · 저장 전」 + 안내 줄(초안 있을 때만) · 프롬프트 줄 「고침 1」, 4바이트 글자도 하나로 셈', async () => {
    await openEval();
    expect(screen.queryByTestId('based-on')).toBeNull();
    expect(screen.queryByTestId('prompt-notice')).toBeNull();
    type(slotText('지어낸 판정'), '지어낸 고친 판정 글 😀');
    type(slotMemo('지어낸 판정'), '지어낸 고친 이유');
    expect(saveBar()!.textContent).toContain(t.saveBar.count(1));
    expect(screen.getByTestId('slot-edited').textContent).toBe(p.edited);
    expect(screen.getByTestId('based-on').textContent).toBe(p.basedOn('v3'));
    expect(screen.getByTestId('prompt-notice').textContent).toBe(
      p.notice('v2'),
    );
    expect(card('prompt-slot').textContent).not.toContain(p.untouched);
    expect(lines(t.columns.component)[1]).toBe(
      t.components.prompt + t.components.edited(1),
    );
    expect(screen.getByTestId('text-count').textContent).toBe(
      p.count(13, 8000),
    );
    expect(screen.getByTestId('memo-count').textContent).toBe(p.count(9, 500));
    // 출력절을 지운 글 → 그 자리에서 경고(막지 않음)
    expect(screen.getByTestId('output-lost').textContent).toBe(p.outputLost);
  });

  it('저장 본문: 고친 칸(둘째)만 고친 글·메모, 나머지 셋은 바탕 바이트 — 창의 고친 것 줄 「2. 지어낸 판정」', async () => {
    const { fake } = await openEval();
    type(slotText('지어낸 판정'), '지어낸 고친 판정 글');
    type(slotMemo('지어낸 판정'), '지어낸 고친 이유');
    fireEvent.click(button(t.saveBar.save));
    expect((await screen.findByTestId('save-changes')).textContent).toBe(
      p.slot(2, '지어낸 판정'),
    );
    type(within(saveDialog()).getByRole('textbox', { name: s.name }), '가');
    fireEvent.click(confirmSave());
    await waitFor(() => expect(fake.count('create')).toBe(1));
    const [{ body }] = fake.args('create') as [
      {
        body: {
          prompts: {
            steps: { prompts: { key: string; text: string; memo: string }[] }[];
          };
        };
      },
    ];
    const base = fakePromptModel('13').promptGroups[0]!.prompts;
    expect(body.prompts.steps[0]!.prompts).toEqual(
      base.map((one, index) =>
        index === 1 ?
          {
            key: one.key,
            text: '지어낸 고친 판정 글',
            memo: '지어낸 고친 이유',
          }
        : { key: one.key, text: one.text, memo: one.memo },
      ),
    );
  });

  it('메모 뒤 공백만 더함 = 고침 0(서버가 strip 뒤에 잰다), 글 뒤 공백 하나 = 고침 1', async () => {
    await openEval();
    const memo = slotMemo('지어낸 판정').value;
    type(slotMemo('지어낸 판정'), `${memo}  `);
    expect(saveBar()).toBeNull();
    type(slotText('지어낸 판정'), `${slotText('지어낸 판정').value} `);
    expect(saveBar()!.textContent).toContain(t.saveBar.count(1));
  });

  it.each([
    ['\\x1c·공백만 — 빈 글', '\u001c \n', p.empty],
    ['8001 코드포인트 — 넘침', '😀'.repeat(8001), p.over(8000)],
  ])(
    '글이 %s → 칸 빨강 줄 · 저장 막대 [저장] 끔(눌러도 창 0)',
    async (_, text, line) => {
      await openEval();
      type(slotText('지어낸 판정'), text);
      expect(screen.getByTestId('text-error').textContent).toBe(line);
      expect(slotText('지어낸 판정').getAttribute('aria-invalid')).toBe('true');
      const save = within(saveBar()!).getByRole('button', {
        name: t.saveBar.save,
      });
      expect(save.getAttribute('aria-disabled')).toBe('true');
      fireEvent.click(save);
      expect(screen.queryByTestId('save-dialog')).toBeNull();
    },
  );

  it('메모 strip 뒤 501 → 넘침(500 + 뒤 공백은 됨)', async () => {
    await openEval();
    type(slotMemo('지어낸 판정'), `${'가'.repeat(500)}   `);
    expect(screen.queryByTestId('memo-error')).toBeNull();
    type(slotMemo('지어낸 판정'), '가'.repeat(501));
    expect(screen.getByTestId('memo-error').textContent).toBe(p.over(500));
  });

  it('거절 AI_PROMPT_* 의 fields(prompts.steps.0.prompts.1.text) → 창 줄 「지어낸 판정 — 문장」 · 칸 고름 「확인 필요」 · 그 칸 빨강, 고치면 걷힘 · 모르는 경로는 창에 서버 문장', async () => {
    const fake = fakeAiSettingModule();
    fake.override.create = [
      () => ({
        kind: 'rejected',
        code: 'AI_PROMPT_TEXT_DUPLICATE',
        message: '지어낸 겹침 문장',
        fields: { 'prompts.steps.0.prompts.1.text': ['지어낸 칸 겹침 문장'] },
      }),
      () => ({
        kind: 'rejected',
        code: 'AI_PROMPT_TOTAL_SIZE',
        message: '지어낸 총 크기 문장',
        fields: { prompts: ['지어낸 총 크기 문장'] },
      }),
    ];
    await openEval(fake);
    type(slotText('지어낸 판정'), '지어낸 겹친 글');
    await saveAs('지어낸 새 판');
    expect((await screen.findByTestId('save-failure')).textContent).toBe(
      s.fieldRefused('지어낸 판정', '지어낸 칸 겹침 문장'),
    );
    const marks = [
      ...document.querySelectorAll('[data-testid="slot-refused"]'),
    ];
    expect(marks.map((node) => node.textContent)).toEqual([p.slotError]);
    expect(marks[0]!.closest('button')!.textContent).toContain('지어낸 판정');
    fireEvent.click(
      within(saveDialog()).getByRole('button', { name: s.cancel }),
    );
    await waitFor(() => expect(screen.queryByTestId('save-dialog')).toBeNull());
    expect(screen.getByTestId('text-error').textContent).toBe(
      '지어낸 칸 겹침 문장',
    );
    type(slotText('지어낸 판정'), '지어낸 다시 고친 글');
    expect(screen.queryByTestId('text-error')).toBeNull();
    expect(screen.queryByTestId('slot-refused')).toBeNull();
    await saveAs('지어낸 새 판');
    expect((await screen.findByTestId('save-failure')).textContent).toBe(
      '지어낸 총 크기 문장',
    );
    expect(screen.queryByTestId('slot-refused')).toBeNull();
  });

  it('T5(MS1W) 잠긴 동안(다시 저장 중) 프롬프트 칸 입력 → 고침 0 · 서버가 짚은 칸 오류 그대로(forgetRefused 안 부름)', async () => {
    const fake = fakeAiSettingModule();
    const held = deferred<{ kind: 'failed' }>();
    fake.override.create = [
      () => ({
        kind: 'rejected',
        code: 'AI_PROMPT_TEXT_DUPLICATE',
        message: '지어낸 겹침 문장',
        fields: { 'prompts.steps.0.prompts.1.text': ['지어낸 칸 겹침 문장'] },
      }),
      () => held.promise,
    ];
    await openEval(fake);
    type(slotText('지어낸 판정'), '지어낸 겹친 글');
    await saveAs('지어낸 새 판');
    await screen.findByTestId('save-failure');
    expect(screen.getByTestId('text-error').textContent).toBe(
      '지어낸 칸 겹침 문장',
    );
    fireEvent.click(confirmSave());
    await waitFor(() => expect(fake.count('create')).toBe(2));
    // 창이 떠 있어 바탕은 aria-hidden — 칸은 hidden 까지 찾는다
    const behind = () =>
      within(card('prompt-slot')).getByRole('textbox', {
        name: `지어낸 판정 ${p.text}`,
        hidden: true,
      }) as HTMLTextAreaElement;
    type(behind(), '지어낸 잠긴 동안 글');
    expect(behind().value).toBe('지어낸 겹친 글');
    expect(screen.getByTestId('text-error').textContent).toBe(
      '지어낸 칸 겹침 문장',
    );
    expect(screen.getAllByTestId('slot-refused')).toHaveLength(1);
    await act(async () => {
      held.resolve({ kind: 'failed' });
      await held.promise;
    });
  });

  it('editable.prompts 거짓이면 글·메모 칸은 읽기만', async () => {
    setup({
      fake: fakeAiSettingModule({
        promptModel: (key) => ({
          kind: 'ok',
          model: fakePromptModel(key, {
            editable: { model: true, prompts: false },
          }),
        }),
      }),
    });
    await ready();
    expect(slotText('지어낸 찾기').readOnly).toBe(true);
    expect(slotMemo('지어낸 찾기').readOnly).toBe(true);
  });

  it('cd 답: 저장은 됐는데 목록 다시 읽기만 실패 → 앞 목록 그대로 + 정보 띠 「v4 을 저장했어요. 버전 목록을 …」 + [다시 시도] → list 한 번 → v4 고름·평소 알림', async () => {
    const fake = fakeAiSettingModule();
    await openEval(fake);
    type(slotText('지어낸 판정'), '지어낸 고친 판정 글');
    fake.override.list = [() => ({ kind: 'failed' })];
    await saveAs('지어낸 새 판');
    const band = await screen.findByTestId('saved-band');
    expect(within(band).getByRole('status').textContent).toBe(
      s.listFailed('v4'),
    );
    expect(screen.queryByTestId('load-failure')).toBeNull();
    expect(document.querySelector('[data-version="14"]')).toBeNull();
    expect(pressed(t.columns.version)[0]).toContain('v3');
    expect(saveBar()).toBeNull();
    expect(fake.count('list')).toBe(2);
    fireEvent.click(within(band).getByRole('button', { name: t.retry }));
    await waitFor(() => expect(pressed(t.columns.version)[0]).toContain('v4'));
    expect(fake.count('list')).toBe(3);
    expect(screen.queryByTestId('saved-band')).toBeNull();
    expect(screen.getByTestId('notice').textContent).toBe(s.done('v4'));
  });
});

describe('AD-02 ⑨ 저장 흐름 경쟁(AD2S)', () => {
  // 처음 판은 initialVersion 으로 박는다(교훈 1절 — 고르지 않은 채면 처음 고름이 새 판을 가려 우회가 초록). 누름은 앞 상태가 그려진 뒤.
  const s = t.save;
  type Outcome = Awaited<ReturnType<Fake['module']['port']['create']>>;
  type Leave = { pending: boolean; proceed(): void; reset(): void };
  const leaveDialog = () => screen.queryByTestId('leave-confirm');
  const saveDialog = () => screen.queryByTestId('save-dialog');

  /** 그 표식이 한 번이라도 그려졌는지(끝까지 없음을 재려고 — 사이에 떴다 사라진 것도 잡는다). */
  function watch(testId: string) {
    const seen = { ever: false };
    const observer = new MutationObserver(() => {
      if (document.querySelector(`[data-testid="${testId}"]`)) seen.ever = true;
    });
    observer.observe(document.body, { childList: true, subtree: true });
    return { seen, stop: () => observer.disconnect() };
  }

  /** v3 를 박아 그리고 모델 출력 상한을 고친 뒤 저장 창에 이름을 넣고 [저장]. leave 는 rerender 로 넘긴다. */
  async function saveEdited(fake: Fake) {
    const proceed = vi.fn();
    const reset = vi.fn();
    const onDirtyChange = vi.fn();
    const draw = (leave?: Leave) => (
      <AiSettingsScreen
        modules={[fake.module]}
        initialVersion="v3"
        onDirtyChange={onDirtyChange}
        leave={leave}
      />
    );
    const view = render(draw());
    await ready();
    choose(t.columns.component, /^모델 설정/);
    fireEvent.change(
      screen.getByRole('textbox', { name: t.model.maxOutputTokens }),
      { target: { value: '3000' } },
    );
    fireEvent.click(
      await screen.findByRole('button', { name: t.saveBar.save }),
    );
    const dialog = await screen.findByTestId('save-dialog');
    fireEvent.change(within(dialog).getByRole('textbox', { name: s.name }), {
      target: { value: '지어낸 새 판' },
    });
    fireEvent.click(within(dialog).getByRole('button', { name: s.confirm }));
    await waitFor(() => expect(fake.count('create')).toBe(1));
    return {
      proceed,
      reset,
      onDirtyChange,
      /** 라우터가 이동을 막았다(뒤로가기 — leave.pending). */
      block: () => view.rerender(draw({ pending: true, proceed, reset })),
    };
  }

  it('U1 저장 중 막힌 이동 → 나가기 창 0 · proceed 0 → 저장 성공 → 막은 이동을 그대로 보냄(proceed 1) · 나가기 창 끝까지 0 · reset 0', async () => {
    const fake = fakeAiSettingModule();
    const held = deferred<Outcome>();
    const list = holdList(fake);
    fake.override.create = [() => held.promise];
    const leaveSeen = watch('leave-confirm');
    const screenNow = await saveEdited(fake);
    screenNow.block();
    await settle();
    expect(leaveDialog()).toBeNull();
    expect(screenNow.proceed).not.toHaveBeenCalled();
    expect(saveDialog()).not.toBeNull();
    // 저장 201 → 창 닫힘 · 초안 비움 — 목록을 다시 받는 동안도 저장 흐름이다(보내지 않는다)
    fake.override.list = [list.held];
    await act(async () => {
      held.resolve({ kind: 'ok', key: '14', number: 'v4' });
      await new Promise((done) => setTimeout(done, 20));
    });
    expect(saveDialog()).toBeNull();
    expect(screenNow.onDirtyChange).toHaveBeenLastCalledWith(false);
    expect(fake.count('list')).toBe(2);
    expect(screenNow.proceed).not.toHaveBeenCalled();
    await act(async () => {
      list.gate.resolve();
      await new Promise((done) => setTimeout(done, 20));
    });
    await waitFor(() => expect(screenNow.proceed).toHaveBeenCalledTimes(1));
    await settle();
    leaveSeen.stop();
    expect(leaveSeen.seen.ever).toBe(false);
    expect(leaveDialog()).toBeNull();
    expect(screenNow.proceed).toHaveBeenCalledTimes(1);
    expect(screenNow.reset).not.toHaveBeenCalled();
    expect(screenNow.onDirtyChange).toHaveBeenLastCalledWith(false);
    expect(fake.count('create')).toBe(1);
  });

  it.each<[string, Outcome]>([
    ['실패', { kind: 'failed' }],
    [
      '모델 거절',
      {
        kind: 'rejected',
        code: 'AI_MODEL_NOT_ALLOWED',
        message: '지어낸 모델 거절 문장',
        fields: {},
      },
    ],
  ])(
    'U2 저장 중 막힌 이동 → %s → 그때 나가기 창(proceed 0) → [나가기] proceed 1 · create 한 번',
    async (_, outcome) => {
      const fake = fakeAiSettingModule();
      const held = deferred<Outcome>();
      fake.override.create = [() => held.promise];
      const screenNow = await saveEdited(fake);
      screenNow.block();
      await settle();
      expect(leaveDialog()).toBeNull();
      await act(async () => {
        held.resolve(outcome);
        await new Promise((done) => setTimeout(done, 20));
      });
      const leave = await screen.findByTestId('leave-confirm');
      expect(screenNow.proceed).not.toHaveBeenCalled();
      expect(screen.getByTestId('save-failure')).toBeTruthy();
      fireEvent.click(
        within(leave).getByRole('button', { name: t.leave.confirm }),
      );
      expect(screenNow.proceed).toHaveBeenCalledTimes(1);
      await settle();
      expect(fake.count('create')).toBe(1);
      expect(screenNow.reset).not.toHaveBeenCalled();
    },
  );

  /** 다음 list 를 붙잡는다(풀면 가짜 자기 답 — 안쪽 부름도 list 하나로 셈). */
  function holdList(fake: Fake) {
    const gate = deferred<void>();
    const held = async () => {
      await gate.promise;
      return fake.module.port.list(0);
    };
    return { gate, held };
  }

  /** 저장 흐름이 도는 동안 네 단추: 요청 0 · 창 0 까지(aria 만으로 끝내지 않는다). */
  async function pressFour(fake: Fake, { apply = true } = {}) {
    const promptModels = fake.args('promptModel').length;
    fireEvent.click(button(t.more));
    pickVersion('12');
    if (apply) fireEvent.click(applyButton());
    fireEvent.click(button(t.newVersion));
    await settle();
    expect(fake.args('list')).not.toContain(2);
    expect(fake.args('promptModel').slice(promptModels)).not.toContain('12');
    expect(screen.queryByTestId('apply-confirm')).toBeNull();
    expect(fake.count('apply')).toBe(0);
    expect(saveDialog()).toBeNull();
  }

  it('U3 저장 201 뒤 목록 다시 받는 중 [더 보기]·v2 줄·[이 버전 적용]·[새 버전] → 요청 0·창 0 → 받으면 v4 고름 · 평소 알림 · 정보 띠 0', async () => {
    const fake = fakeAiSettingModule({ pageSize: 2 });
    const { gate, held } = holdList(fake);
    render(<AiSettingsScreen modules={[fake.module]} initialVersion="v3" />);
    await ready();
    expect(button(t.more)).toBeTruthy();
    choose(t.columns.component, /^모델 설정/);
    fireEvent.change(
      screen.getByRole('textbox', { name: t.model.maxOutputTokens }),
      { target: { value: '3000' } },
    );
    fake.override.list = [held];
    fireEvent.click(
      await screen.findByRole('button', { name: t.saveBar.save }),
    );
    const dialog = await screen.findByTestId('save-dialog');
    fireEvent.change(within(dialog).getByRole('textbox', { name: s.name }), {
      target: { value: '지어낸 새 판' },
    });
    fireEvent.click(within(dialog).getByRole('button', { name: s.confirm }));
    await waitFor(() => expect(saveDialog()).toBeNull());
    expect(fake.count('create')).toBe(1);
    expect(fake.count('list')).toBe(2);
    await pressFour(fake);
    await act(async () => {
      gate.resolve();
      await new Promise((done) => setTimeout(done, 20));
    });
    await waitFor(() => expect(pressed(t.columns.version)[0]).toContain('v4'));
    expect(screen.getByTestId('notice').textContent).toBe(s.done('v4'));
    expect(screen.queryByTestId('saved-band')).toBeNull();
    expect(fake.args('list')).toEqual([0, 0, 0]);
  });

  it('U5 저장 201 뒤 목록 받는 중 칸 고침은 받지 않는다(Q7 — sid:MARC-ISSUE-297 ①)', async () => {
    const fake = fakeAiSettingModule();
    const { gate, held } = holdList(fake);
    render(<AiSettingsScreen modules={[fake.module]} initialVersion="v3" />);
    await ready();
    choose(t.columns.component, /^모델 설정/);
    const tokens = () =>
      screen.getByRole('textbox', { name: t.model.maxOutputTokens });
    fireEvent.change(tokens(), { target: { value: '3000' } });
    fake.override.list = [held];
    fireEvent.click(
      await screen.findByRole('button', { name: t.saveBar.save }),
    );
    const dialog = await screen.findByTestId('save-dialog');
    fireEvent.change(within(dialog).getByRole('textbox', { name: s.name }), {
      target: { value: '지어낸 새 판' },
    });
    fireEvent.click(within(dialog).getByRole('button', { name: s.confirm }));
    await waitFor(() => expect(saveDialog()).toBeNull());
    expect(fake.count('list')).toBe(2);
    fireEvent.change(tokens(), { target: { value: '3100' } });
    await settle();
    expect(screen.queryByTestId('save-bar')).toBeNull();
    expect((tokens() as HTMLInputElement).value).toBe('2000');
    expect(saveDialog()).toBeNull();
    expect(fake.count('create')).toBe(1);
    await act(async () => {
      gate.resolve();
      await new Promise((done) => setTimeout(done, 20));
    });
    await waitFor(() => expect(pressed(t.columns.version)[0]).toContain('v4'));
    expect(fake.count('create')).toBe(1);
  });

  it('U4 정보 띠 [다시 시도]로 다시 받는 중 [더 보기]·v2 줄 → 요청 0 → 받으면 v4 고름 · 띠 0', async () => {
    const fake = fakeAiSettingModule({ pageSize: 2 });
    const { gate, held } = holdList(fake);
    render(<AiSettingsScreen modules={[fake.module]} initialVersion="v3" />);
    await ready();
    choose(t.columns.component, /^모델 설정/);
    fireEvent.change(
      screen.getByRole('textbox', { name: t.model.maxOutputTokens }),
      { target: { value: '3000' } },
    );
    fake.override.list = [() => ({ kind: 'failed' }), held];
    fireEvent.click(
      await screen.findByRole('button', { name: t.saveBar.save }),
    );
    const dialog = await screen.findByTestId('save-dialog');
    fireEvent.change(within(dialog).getByRole('textbox', { name: s.name }), {
      target: { value: '지어낸 새 판' },
    });
    fireEvent.click(within(dialog).getByRole('button', { name: s.confirm }));
    const band = await screen.findByTestId('saved-band');
    fireEvent.click(within(band).getByRole('button', { name: t.retry }));
    await waitFor(() => expect(fake.count('list')).toBe(3));
    const promptModels = fake.args('promptModel').length;
    fireEvent.click(button(t.more));
    pickVersion('12');
    await settle();
    expect(fake.args('list')).not.toContain(2);
    expect(fake.args('promptModel').slice(promptModels)).not.toContain('12');
    await act(async () => {
      gate.resolve();
      await new Promise((done) => setTimeout(done, 20));
    });
    await waitFor(() => expect(pressed(t.columns.version)[0]).toContain('v4'));
    expect(screen.queryByTestId('saved-band')).toBeNull();
    expect(screen.getByTestId('notice').textContent).toBe(s.done('v4'));
    expect(fake.args('list')).toEqual([0, 0, 0, 0]);
  });

  it('U6 새 판이 만들어지면 앞 알림을 걷는다 — 적용 알림 뒤 저장 → 목록 다시 읽기 실패 → 정보 띠만(알림 0 · 감독 처분 R2)', async () => {
    const fake = fakeAiSettingModule();
    render(<AiSettingsScreen modules={[fake.module]} initialVersion="v3" />);
    await ready();
    fireEvent.click(applyButton());
    const confirm = await screen.findByTestId('apply-confirm');
    fireEvent.click(within(confirm).getByRole('button', { name: a.confirm }));
    await waitFor(() =>
      expect(screen.getByTestId('notice').textContent).toBe(a.done('v3')),
    );
    choose(t.columns.component, /^모델 설정/);
    fireEvent.change(
      screen.getByRole('textbox', { name: t.model.maxOutputTokens }),
      { target: { value: '3000' } },
    );
    fake.override.list = [() => ({ kind: 'failed' })];
    fireEvent.click(
      await screen.findByRole('button', { name: t.saveBar.save }),
    );
    const dialog = await screen.findByTestId('save-dialog');
    fireEvent.change(within(dialog).getByRole('textbox', { name: s.name }), {
      target: { value: '지어낸 새 판' },
    });
    fireEvent.click(within(dialog).getByRole('button', { name: s.confirm }));
    await screen.findByTestId('saved-band');
    expect(fake.count('create')).toBe(1);
    expect(screen.queryByTestId('notice')).toBeNull();
  });
});

describe('AD-02 ⑩ 모델 칸·프롬프트 묶음(AP1W)', () => {
  // 넓은 가짜(fakeWidePromptModel): 모델 칸 셋(지어낸 칸 가·나·다 = translate_ceo·translate_other·review),
  // 묶음 다섯(지어낸 옮김 9 · 다듬기 1 · 살핌 1 · 검토 1 · 고침 2 — 칸 label 「지어낸 글 1~14」). 칸 key 는 칸의 기본 글(「지어낸 <key> 기본 글」)로 본다.
  const s = t.save;
  const wide = fakeWidePromptModel('13');
  const type = (node: HTMLElement, value: string) =>
    fireEvent.change(node, { target: { value } });
  const field = (slot: string, name: string) =>
    screen.getByRole('textbox', { name: `${slot} ${name}` });
  const saveBar = () => screen.queryByTestId('save-bar');
  const saveDialog = () => screen.getByTestId('save-dialog');
  const items = () =>
    [...column(t.columns.category).querySelectorAll('li')].map(
      (node) => node.textContent,
    );
  async function open(fake = fakeAiSettingModule({ wide: true })) {
    const view = setup({ initialVersion: 'v3', fake });
    await ready();
    return view;
  }
  const openModel = () => choose(t.columns.component, /^모델 설정/);
  const slotText = (label: string) =>
    within(card('prompt-slot')).getByRole('textbox', {
      name: `${label} ${t.prompt.text}`,
    }) as HTMLTextAreaElement;
  async function openSave(title: string) {
    fireEvent.click(button(t.saveBar.save));
    await screen.findByTestId('save-dialog');
    type(within(saveDialog()).getByRole('textbox', { name: s.name }), title);
  }
  const changedItems = () =>
    within(saveDialog())
      .queryAllByTestId('changed-item')
      .map((node) => node.textContent);

  it('W1 모델 카드: 줄 셋 = 칸 key 차례 · 줄마다 칸 이름 · 「<묶음들>에 쓰여요」(칸 0·1 = 옮김·다듬기·살핌·고침, 칸 2 = 검토) · 모듈 선언 없으면 곁 글 0', async () => {
    await open();
    openModel();
    const model = card('model');
    const rows = [...model.querySelectorAll('[data-step]')];
    expect(rows.map((row) => row.getAttribute('data-step'))).toEqual([
      'translate_ceo',
      'translate_other',
      'review',
    ]);
    expect(rows.map((row) => row.querySelector('dt')!.textContent)).toEqual([
      `지어낸 칸 가 ${t.model.route}`,
      `지어낸 칸 나 ${t.model.route}`,
      `지어낸 칸 다 ${t.model.route}`,
    ]);
    expect(
      rows.map(
        (row) => row.querySelector('[data-testid="model-uses"]')!.textContent,
      ),
    ).toEqual([
      '지어낸 옮김 · 지어낸 다듬기 · 지어낸 살핌 · 지어낸 고침에 쓰여요',
      '지어낸 옮김 · 지어낸 다듬기 · 지어낸 살핌 · 지어낸 고침에 쓰여요',
      '지어낸 검토에 쓰여요',
    ]);
    expect(model.textContent).not.toContain(
      '모든 단계에 같이 쓰여요 · 모델 하나로 네 프롬프트를 불러요',
    ); // AS3b K9: 옛 공통 곁 글 글자 그대로 — modelNote 를 선언하지 않은 모듈에는 곁 글이 없다
  });

  it('W2 셋째 열: 묶음 머리 다섯(「n. 묶음」 — data-group 차례, 눌러도 0) 아래 칸 이름(번호 없음) — 항목 19 차례 통째, 칸 이름을 누르면 그 칸(key)', async () => {
    const { fake } = await open();
    expect(items()).toEqual([
      t.prompt.slot(1, '지어낸 옮김'),
      ...[1, 2, 3, 4, 5, 6, 7, 8, 9].map((n) => `지어낸 글 ${n}`),
      t.prompt.slot(2, '지어낸 다듬기'),
      '지어낸 글 10',
      t.prompt.slot(3, '지어낸 살핌'),
      '지어낸 글 11',
      t.prompt.slot(4, '지어낸 검토'),
      '지어낸 글 12',
      t.prompt.slot(5, '지어낸 고침'),
      '지어낸 글 13',
      '지어낸 글 14',
    ]);
    const heads = [
      ...column(t.columns.category).querySelectorAll('[data-group]'),
    ];
    expect(heads.map((node) => node.getAttribute('data-group'))).toEqual([
      'translate',
      'polish',
      'editorial_qa',
      'review',
      'autofix',
    ]);
    expect(heads.every((node) => node.querySelector('button') === null)).toBe(
      true,
    );
    const calls = fake.calls.length;
    fireEvent.click(heads[3]!);
    expect(pressed(t.columns.category)).toEqual(['지어낸 글 1']);
    expect(fake.calls.length).toBe(calls);
    for (const [label, group, prompt, key] of [
      ['지어낸 글 12', 3, 0, 'review'],
      ['지어낸 글 11', 2, 0, 'editorial_qa'],
      ['지어낸 글 14', 4, 1, 'autofix_korean'],
    ] as const) {
      choose(t.columns.category, label);
      expect(pressed(t.columns.category)).toEqual([label]);
      expect(slotText(label).value).toBe(
        wide.promptGroups[group]!.prompts[prompt]!.text,
      );
      expect(slotText(label).value).toContain(`지어낸 ${key} 기본 글`);
    }
  });

  it('W3 칸 2 경로 둘째로 + 칸 1 출력 상한 + 묶음 4 칸 1(지어낸 글 14) 글 → 「고친 것 3개」 → 저장 본문은 그 셋만 · 창 「고친 것」 항목 셋(모델 칸 이름 · 묶음 순번)', async () => {
    const { fake } = await open();
    openModel();
    fireEvent.change(
      screen.getByRole('combobox', { name: `지어낸 칸 다 ${t.model.route}` }),
      { target: { value: 'fake-c2' } },
    );
    type(field('지어낸 칸 나', t.model.maxOutputTokens), '5000');
    choose(t.columns.category, '지어낸 글 14');
    type(slotText('지어낸 글 14'), '지어낸 고친 글');
    expect(saveBar()!.textContent).toContain(t.saveBar.count(3));
    await openSave('지어낸 새 판');
    expect(within(saveDialog()).getByTestId('save-changes').tagName).toBe('UL');
    expect(changedItems()).toEqual([
      t.changed.slotModel('지어낸 칸 나'),
      t.changed.slotModel('지어낸 칸 다'),
      t.changed.slotPrompt(5, '지어낸 고침', '지어낸 글 14'),
    ]);
    fireEvent.click(
      within(saveDialog()).getByRole('button', { name: s.confirm }),
    );
    await waitFor(() => expect(fake.count('create')).toBe(1));
    const [{ body }] = fake.args('create') as [
      {
        body: {
          modelSettings: { steps: Record<string, unknown>[] };
          prompts: { steps: { key: string; prompts: { text: string }[] }[] };
        };
      },
    ];
    const base = (index: number) => {
      const { model, key } = wide.models[index]!;
      return {
        key,
        route: model.route,
        temperature: model.temperature,
        maxOutputTokens: model.maxOutputTokens,
        webSearch: model.webSearch,
      };
    };
    expect(body.modelSettings.steps).toEqual([
      base(0),
      { ...base(1), maxOutputTokens: 5000 },
      { ...base(2), route: 'fake-c2' },
    ]);
    expect(
      body.prompts.steps.map((group) => group.prompts.map((one) => one.text)),
    ).toEqual(
      wide.promptGroups.map((group, g) =>
        group.prompts.map((one, p) =>
          g === 4 && p === 1 ? '지어낸 고친 글' : one.text,
        ),
      ),
    );
  });

  it('W4 거절 prompts.steps.1.prompts.0.text → 창 줄 「지어낸 글 10 — 문장」 · 「고칠 곳 있음」은 그 칸 줄에만', async () => {
    const fake = fakeAiSettingModule({ wide: true });
    fake.override.create = () => ({
      kind: 'rejected',
      code: 'AI_PROMPT_TEXT_DUPLICATE',
      message: '지어낸 겹침 문장',
      fields: { 'prompts.steps.1.prompts.0.text': ['지어낸 칸 겹침 문장'] },
    });
    await open(fake);
    choose(t.columns.category, '지어낸 글 10');
    type(slotText('지어낸 글 10'), '지어낸 겹친 글');
    await openSave('지어낸 새 판');
    fireEvent.click(
      within(saveDialog()).getByRole('button', { name: s.confirm }),
    );
    expect((await screen.findByTestId('save-failure')).textContent).toBe(
      s.fieldRefused('지어낸 글 10', '지어낸 칸 겹침 문장'),
    );
    const marks = [
      ...document.querySelectorAll('[data-testid="slot-refused"]'),
    ];
    expect(marks.map((node) => node.closest('button')!.textContent)).toEqual([
      `지어낸 글 10${t.prompt.slotError}`,
    ]);
  });

  it('W5 그린워싱 꼴(칸 하나·묶음 하나): 묶음 머리 0 · 쓰는 곳 0 · 줄 하나 · 곁 글 = 모듈 선언 · 셈 줄 0 · 저장 창 「고친 것」은 글 한 줄(목록 0)', async () => {
    await open(fakeAiSettingModule({ modelNote: '지어낸 곁 글' }));
    expect(column(t.columns.category).querySelector('[data-group]')).toBeNull();
    openModel();
    const model = card('model');
    expect(model.querySelectorAll('[data-step]')).toHaveLength(1);
    expect(model.querySelector('[data-testid="model-uses"]')).toBeNull();
    expect(model.querySelector('h4')!.nextElementSibling!.textContent).toBe(
      '지어낸 곁 글',
    );
    type(
      screen.getByRole('textbox', { name: t.model.maxOutputTokens }),
      '3000',
    );
    expect(saveBar()!.querySelectorAll('p')).toHaveLength(1);
    choose(t.columns.category, t.prompt.slot(2, '지어낸 판정'));
    type(slotText('지어낸 판정'), '지어낸 고친 글');
    await openSave('지어낸 새 판');
    const changed = within(saveDialog()).getByTestId('save-changes');
    expect(changed.tagName).toBe('P');
    expect(changed.textContent).toBe(
      [t.changed.model, t.prompt.slot(2, '지어낸 판정')].join(t.changed.join),
    );
    expect(changedItems()).toEqual([]);
  });

  it('W7 모델 칸 하나·묶음 다섯 → 목록 꼴(모델 항목 「모델 설정」, 프롬프트 「<묶음 순번>. <묶음> · <칸>」)', async () => {
    const one = {
      ...wide,
      models: [wide.models[0]!],
      promptGroups: wide.promptGroups.map((group) => ({
        ...group,
        modelSlots: ['translate_ceo'],
      })),
    };
    await open(
      fakeAiSettingModule({
        promptModel: () => ({ kind: 'ok', model: one }),
      }),
    );
    openModel();
    type(
      screen.getByRole('textbox', { name: t.model.maxOutputTokens }),
      '2500',
    );
    choose(t.columns.category, '지어낸 글 10');
    type(slotText('지어낸 글 10'), '지어낸 고친 글');
    await openSave('지어낸 새 판');
    expect(changedItems()).toEqual([
      t.changed.model,
      t.changed.slotPrompt(2, '지어낸 다듬기', '지어낸 글 10'),
    ]);
  });

  it('W6 모델 칸마다 1(Q4 (나)): 칸 0·칸 1 → 「고친 것 2개」 · 셈 줄 0, 칸 0 의 temperature·출력 상한 둘 → 1개, 되돌려 같으면 0', async () => {
    await open();
    openModel();
    type(field('지어낸 칸 가', t.model.maxOutputTokens), '2500');
    type(field('지어낸 칸 나', t.model.maxOutputTokens), '3500');
    expect(saveBar()!.textContent).toContain(t.saveBar.count(2));
    expect(saveBar()!.querySelectorAll('p')).toHaveLength(1);
    expect(lines(t.columns.component)[0]).toBe(
      t.components.model + t.components.edited(2),
    );
    type(field('지어낸 칸 나', t.model.maxOutputTokens), '3000');
    type(field('지어낸 칸 가', t.model.temperature), '0.9');
    expect(saveBar()!.textContent).toContain(t.saveBar.count(1));
    type(field('지어낸 칸 가', t.model.maxOutputTokens), '2000');
    type(field('지어낸 칸 가', t.model.temperature), '0.3');
    expect(saveBar()).toBeNull();
  });
});

describe('AD-02 ⑪ 모듈 초안 슬롯(AP1W)', () => {
  // 지어낸 슬롯: 바탕 몫 = 지어낸 낱말 목록(판마다 같은 둘), 초안 = 낱말 목록, count = 차이 수(빠진 것 + 더한 것), blocked = 빈 목록(목록이 아니면 막음),
  //   refusal = FAKE_DRAFT_* 만(fields 를 짚은 자리로). 카드는 낱말을 쉼표로 이은 글 칸 하나와 짚은 문장.
  const s = t.save;
  type Words = readonly string[];
  type Loaded = Awaited<ReturnType<ModuleDraftSlot['load']>>;
  const BASE: Words = ['지어낸 낱말 가', '지어낸 낱말 나'];
  const diff = (base: unknown, draft: unknown) => {
    const before = base as Words;
    const after = draft as Words;
    return (
      before.filter((one) => !after.includes(one)).length +
      after.filter((one) => !before.includes(one)).length
    );
  };
  function fakeSlot(load?: (version: string) => Promise<Loaded>) {
    const blocked = vi.fn(
      (draft: unknown) => !Array.isArray(draft) || draft.length === 0,
    );
    const slot: ModuleDraftSlot = {
      key: 'fake-draft',
      load: vi.fn((version: string): Promise<Loaded> =>
        load ? load(version) : Promise.resolve({ kind: 'ok', base: BASE }),
      ),
      count: diff,
      changed: (base, draft) => [`지어낸 낱말 고침 ${diff(base, draft)}`],
      blocked,
      sum: (base) => `지어낸 낱말 ${(base as Words).length}개`,
      refusal: (code, fields) =>
        code?.startsWith('FAKE_DRAFT_') ?
          {
            line: `지어낸 낱말 거절 — ${fields.words?.[0] ?? ''}`,
            refused: fields,
          }
        : null,
      render: ({ draft, readOnly, onChange, refused }) => (
        <div data-card="fake-draft">
          <input
            aria-label="지어낸 낱말"
            readOnly={readOnly}
            value={(draft as Words).join(',')}
            onChange={(event) =>
              onChange(
                event.target.value === '' ? [] : event.target.value.split(','),
              )
            }
          />
          {refused.words?.[0] !== undefined && (
            <p data-testid="fake-refused">{refused.words[0]}</p>
          )}
        </div>
      ),
    };
    return { slot, blocked, loads: slot.load as ReturnType<typeof vi.fn> };
  }
  async function open(
    slot = fakeSlot().slot,
    extra: Parameters<typeof fakeAiSettingModule>[0] = {},
  ) {
    const fake = fakeAiSettingModule({ draft: slot, ...extra });
    setup({ initialVersion: 'v3', fake });
    await ready();
    return fake;
  }
  const openDraft = () => choose(t.columns.component, /^지어낸 초안 몫/);
  const box = () =>
    screen.getByRole('textbox', { name: '지어낸 낱말' }) as HTMLInputElement;
  const words = (value: string) =>
    fireEvent.change(box(), { target: { value } });
  const tokens = () =>
    screen.getByRole('textbox', {
      name: t.model.maxOutputTokens,
    }) as HTMLInputElement;
  const draftTail = () =>
    within(column(t.columns.component))
      .getByRole('button', { name: /^지어낸 초안 몫/ })
      .textContent!.replace('지어낸 초안 몫', '');
  const saveBar = () => screen.queryByTestId('save-bar');
  /** 판 열에서 그 판이 골라졌다(고른 구성이 모듈 줄이면 프롬프트 제목이 없다). */
  const shown = (number: string) =>
    waitFor(() => expect(pressed(t.columns.version)[0]).toContain(number));
  async function save(title = '지어낸 새 판') {
    fireEvent.click(button(t.saveBar.save));
    const dialog = await screen.findByTestId('save-dialog');
    fireEvent.change(within(dialog).getByRole('textbox', { name: s.name }), {
      target: { value: title },
    });
    fireEvent.click(within(dialog).getByRole('button', { name: s.confirm }));
  }
  const moduleOf = (fake: Fake, n = 0) =>
    (fake.args('create')[n] as { module: unknown }).module;
  /** 다음 list 를 붙잡는다(풀면 가짜 자기 답). */
  function holdList(fake: Fake) {
    const gate = deferred<void>();
    fake.override.list = [
      async () => {
        await gate.promise;
        return fake.module.port.list(0);
      },
    ];
    return gate;
  }

  it('M1 모듈 고침 → 「고친 것 n개」에 더함 · 모듈만 고쳐도 저장 막대·편집중·나가기 창 · 구성 꼬리 「고침 n」 · 저장 창 「고친 것」 끝에 모듈 조각', async () => {
    await open();
    openDraft();
    expect(draftTail()).toBe('지어낸 낱말 2개');
    expect(saveBar()).toBeNull();
    words('지어낸 낱말 가');
    expect(saveBar()!.textContent).toContain(t.saveBar.count(1));
    expect(draftTail()).toBe(t.components.edited(1));
    choose(t.columns.component, /^모델 설정/);
    fireEvent.change(tokens(), { target: { value: '3000' } });
    expect(saveBar()!.textContent).toContain(t.saveBar.count(2));
    fireEvent.click(button(t.saveBar.save));
    const dialog = await screen.findByTestId('save-dialog');
    expect(within(dialog).getByTestId('save-changes').textContent).toBe(
      `${t.changed.model}${t.changed.join}지어낸 낱말 고침 1`,
    );
    fireEvent.click(within(dialog).getByRole('button', { name: s.cancel }));
    // 모델을 되돌려도 모듈만으로 고친 것이 남는다
    fireEvent.change(tokens(), { target: { value: '2000' } });
    expect(saveBar()!.textContent).toContain(t.saveBar.count(1));
    pickVersion('12');
    expect(await screen.findByTestId('leave-confirm')).toBeTruthy();
  });

  it('M2 [되돌리기] 뒤 모듈 초안 0 · 다른 판 [나가기] 뒤 원래 판으로 돌아와도 바탕 값', async () => {
    const one = fakeSlot();
    await open(one.slot);
    openDraft();
    words('지어낸 낱말 가,지어낸 낱말 다');
    fireEvent.click(button(t.saveBar.revert));
    const revert = await screen.findByTestId('revert-confirm');
    fireEvent.click(
      within(revert).getByRole('button', { name: t.revert.confirm }),
    );
    expect(box().value).toBe(BASE.join(','));
    expect(saveBar()).toBeNull();
    words('지어낸 낱말 다');
    pickVersion('12');
    const leave = await screen.findByTestId('leave-confirm');
    fireEvent.click(
      within(leave).getByRole('button', { name: t.leave.confirm }),
    );
    await shown('v2');
    pickVersion('13');
    await shown('v3');
    expect(box().value).toBe(BASE.join(','));
    expect(saveBar()).toBeNull();
    // 바탕 몫은 판 열쇠마다 한 번(돌아와도 다시 읽지 않는다)
    expect(one.loads.mock.calls.map((call) => call[0])).toEqual(['13', '12']);
  });

  it('M2 같은 판 열쇠에 남는 길: 저장 201 + 목록 다시 읽기 실패(정보 띠) 뒤 모듈 카드가 바탕 값', async () => {
    const fake = await open();
    openDraft();
    words('지어낸 낱말 다');
    fake.override.list = [() => ({ kind: 'failed' })];
    await save();
    await screen.findByTestId('saved-band');
    expect(fake.count('create')).toBe(1);
    expect(moduleOf(fake)).toEqual(['지어낸 낱말 다']);
    expect(box().value).toBe(BASE.join(','));
    expect(saveBar()).toBeNull();
  });

  it('M3 모듈을 되돌려 셈 0 → create 셋째 인자 null · 안 고친 모듈도 null · 고쳤으면 그 초안', async () => {
    const one = fakeSlot();
    const fake = await open(one.slot);
    openDraft();
    words('지어낸 낱말 다');
    words(BASE.join(','));
    one.blocked.mockClear();
    choose(t.columns.component, /^모델 설정/);
    fireEvent.change(tokens(), { target: { value: '3000' } });
    expect(saveBar()!.textContent).toContain(t.saveBar.count(1));
    await save();
    await waitFor(() => expect(fake.count('create')).toBe(1));
    expect(moduleOf(fake)).toBeNull();
    expect(one.blocked).not.toHaveBeenCalled();
  });

  it('M3 복제는 모듈 초안이 있어도 create(…, null) · 고친 저장은 그 초안(useSave 단위 — create spy)', async () => {
    const model = fakePromptModel('13');
    const create = vi.fn<Fake['module']['port']['create']>(async () => ({
      kind: 'ok',
      key: '14',
      number: 'v4',
    }));
    const port = { ...fakeAiSettingModule().module.port, create };
    const { result } = renderHook(() =>
      useSave({
        port,
        chosen: fakeVersionRows()[0],
        model,
        draft: {
          draft: draftOf(model),
          valid: true,
          moduleBody: ['지어낸 낱말 다'],
          clear: () => {},
          setLocked: () => {},
        },
        refreshKeep: async () => true,
        words: s,
        onCreated: () => {},
        onSaved: () => {},
      }),
    );
    for (const mode of ['copy', 'edit'] as const) {
      act(() => result.current.openSave(mode));
      act(() => result.current.setTitle('지어낸 새 판'));
      await act(() => result.current.submitSave());
    }
    expect(create.mock.calls.map((call) => call[2])).toEqual([
      null,
      ['지어낸 낱말 다'],
    ]);
  });

  it('M4 blocked(빈 목록) → 막대 [새 버전으로 저장] 눌러 창 0·create 0', async () => {
    const fake = await open();
    openDraft();
    words('');
    expect(saveBar()!.textContent).toContain(t.saveBar.count(2));
    fireEvent.click(button(t.saveBar.save));
    await settle();
    expect(screen.queryByTestId('save-dialog')).toBeNull();
    expect(fake.count('create')).toBe(0);
  });

  it('M4 useSave.canSave 는 draft.valid 를 받는다(단위)', () => {
    const model = fakePromptModel('13');
    const draw = (valid: boolean) =>
      renderHook(() =>
        useSave({
          port: fakeAiSettingModule().module.port,
          chosen: fakeVersionRows()[0],
          model,
          draft: {
            draft: draftOf(model),
            valid,
            moduleBody: null,
            clear: () => {},
            setLocked: () => {},
          },
          refreshKeep: async () => true,
          words: s,
          onCreated: () => {},
          onSaved: () => {},
        }),
      ).result;
    for (const valid of [false, true]) {
      const result = draw(valid);
      act(() => result.current.openSave('edit'));
      act(() => result.current.setTitle('지어낸 새 판'));
      expect(result.current.canSave).toBe(valid);
    }
  });

  it('M5 바탕 몫 읽는 중 → 꼬리 「준비 중」·스켈레톤 · 모델 고침 저장 됨(create(…, null), blocked 안 물음)', async () => {
    const held = deferred<Loaded>();
    const one = fakeSlot(() => held.promise);
    const fake = await open(one.slot);
    expect(draftTail()).toBe(t.pendingSum);
    openDraft();
    expect(screen.getByTestId('module-loading')).toBeTruthy();
    choose(t.columns.component, /^모델 설정/);
    fireEvent.change(tokens(), { target: { value: '3000' } });
    await save();
    await waitFor(() => expect(fake.count('create')).toBe(1));
    expect(moduleOf(fake)).toBeNull();
    expect(one.blocked).not.toHaveBeenCalled();
  });

  it('M5 바탕 몫 실패 → 꼬리 「다시 시도」·카드 실패 · 모델 고침 저장 됨 · [다시 시도] → 그 판 두 번째 읽음 · 같은 판 다시 고름 = 읽음 0', async () => {
    const answers: Loaded[] = [{ kind: 'failed' }];
    const one = fakeSlot(
      async () => answers.shift() ?? { kind: 'ok', base: BASE },
    );
    const fake = await open(one.slot);
    await waitFor(() => expect(draftTail()).toBe(t.retry));
    choose(t.columns.component, /^모델 설정/);
    fireEvent.change(tokens(), { target: { value: '3000' } });
    await save();
    await waitFor(() => expect(fake.count('create')).toBe(1));
    expect(moduleOf(fake)).toBeNull();
    expect(one.blocked).not.toHaveBeenCalled();
    await shown('v4');
    pickVersion('13');
    await shown('v3');
    openDraft();
    const failure = await screen.findByTestId('module-failure');
    fireEvent.click(within(failure).getByRole('button', { name: t.retry }));
    await waitFor(() => expect(box().value).toBe(BASE.join(',')));
    expect(one.loads.mock.calls.map((call) => call[0])).toEqual([
      '13',
      '14',
      '13',
    ]);
    pickVersion('12');
    await shown('v2');
    pickVersion('13');
    await shown('v3');
    await settle();
    expect(one.loads.mock.calls.map((call) => call[0])).toEqual([
      '13',
      '14',
      '13',
      '12',
    ]);
  });

  it('M6 prompt-model 실패 → 모듈 카드 읽기 전용', async () => {
    const fake = fakeAiSettingModule({
      draft: fakeSlot().slot,
      promptModel: () => ({ kind: 'failed' }),
    });
    setup({ initialVersion: 'v3', fake });
    await screen.findByTestId('detail-failure');
    openDraft();
    expect(box().readOnly).toBe(true);
    pickVersion('12');
    await shown('v2');
    expect(box().readOnly).toBe(true);
  });

  it('T1(MS1W) prompt-model 실패 → 모듈 카드 onChange 를 불러도 초안 0(저장 막대·나가기 창·create 0)', async () => {
    const fake = fakeAiSettingModule({
      draft: fakeSlot().slot,
      promptModel: () => ({ kind: 'failed' }),
    });
    setup({ initialVersion: 'v3', fake });
    await screen.findByTestId('detail-failure');
    openDraft();
    await waitFor(() => expect(box().value).toBe(BASE.join(',')));
    words('지어낸 낱말 가');
    await settle();
    expect(saveBar()).toBeNull();
    expect(box().value).toBe(BASE.join(','));
    expect(draftTail()).not.toBe(t.components.edited(1));
    pickVersion('12');
    await shown('v2');
    expect(screen.queryByTestId('leave-confirm')).toBeNull();
    expect(fake.count('create')).toBe(0);
  });

  it('T4(MS1W) 저장 창 「고친 것」 목록에 같은 글 둘 → 두 줄 다 그림 · React key 경고 0', async () => {
    const twice = {
      ...fakeSlot().slot,
      changed: () => ['지어낸 같은 글', '지어낸 같은 글'],
    };
    const errors = vi.spyOn(console, 'error').mockImplementation(() => {});
    try {
      await open(twice, { wide: true });
      openDraft();
      words('지어낸 낱말 가');
      fireEvent.click(button(t.saveBar.save));
      const dialog = await screen.findByTestId('save-dialog');
      expect(
        within(dialog)
          .getAllByTestId('changed-item')
          .map((node) => node.textContent),
      ).toEqual(['지어낸 같은 글', '지어낸 같은 글']);
      expect(
        errors.mock.calls.filter((call) =>
          call.some((one) => String(one).includes('same key')),
        ),
      ).toEqual([]);
    } finally {
      errors.mockRestore();
    }
  });

  it('M7 FAKE_DRAFT_X 거절 → 창 줄 = 모듈 line · 카드 짚은 문장 · 모듈 고침 → 걷힘 · 모듈도 null 이면 일반 실패 글', async () => {
    const fake = await open();
    openDraft();
    words('지어낸 낱말 다');
    fake.override.create = [
      () => ({
        kind: 'rejected',
        code: 'FAKE_DRAFT_X',
        message: '지어낸 서버 문장',
        fields: { words: ['지어낸 거절 문장'] },
      }),
      () => ({
        kind: 'rejected',
        code: 'SOMETHING_ELSE',
        message: '지어낸 서버 문장',
        fields: { words: ['지어낸 거절 문장'] },
      }),
    ];
    await save();
    await waitFor(() =>
      expect(screen.getByTestId('save-failure').textContent).toBe(
        '지어낸 낱말 거절 — 지어낸 거절 문장',
      ),
    );
    expect(screen.getByTestId('fake-refused').textContent).toBe(
      '지어낸 거절 문장',
    );
    fireEvent.click(
      within(screen.getByTestId('save-dialog')).getByRole('button', {
        name: s.cancel,
      }),
    );
    words('지어낸 낱말 라');
    expect(screen.queryByTestId('fake-refused')).toBeNull();
    await save();
    await waitFor(() =>
      expect(screen.getByTestId('save-failure').textContent).toBe(s.failed),
    );
    expect(screen.queryByTestId('fake-refused')).toBeNull();
    expect(fake.count('create')).toBe(2);
  });

  it('M8(Q7) 저장 201 뒤 목록 붙잡힘 → 틈의 모듈 고침은 받지 않음(바탕 값 그대로) → 풂 → 새 판 · 나가기 창 0', async () => {
    const fake = await open();
    openDraft();
    words('지어낸 낱말 다');
    const gate = holdList(fake);
    await save();
    await waitFor(() => expect(screen.queryByTestId('save-dialog')).toBeNull());
    expect(fake.count('list')).toBe(2);
    words('지어낸 낱말 라');
    await settle();
    expect(box().value).toBe(BASE.join(','));
    expect(saveBar()).toBeNull();
    await act(async () => {
      gate.resolve();
      await new Promise((done) => setTimeout(done, 20));
    });
    await shown('v4');
    pickVersion('13');
    await shown('v3');
    expect(screen.queryByTestId('leave-confirm')).toBeNull();
    expect(fake.count('create')).toBe(1);
  });

  it('M9(Q7) 목록 다시 읽기 실패 → 정보 띠 동안 칸·모듈 고침 0 · 다른 판 고름 → 그 판 칸 고침도 0(의도) → [다시 시도] 성공 → 새 판 · 초안 0 · 이후 고침 받음', async () => {
    const fake = await open();
    choose(t.columns.component, /^모델 설정/);
    fireEvent.change(tokens(), { target: { value: '3000' } });
    fake.override.list = [() => ({ kind: 'failed' })];
    await save();
    const band = await screen.findByTestId('saved-band');
    fireEvent.change(tokens(), { target: { value: '3100' } });
    openDraft();
    words('지어낸 낱말 라');
    await settle();
    expect(box().value).toBe(BASE.join(','));
    choose(t.columns.component, /^모델 설정/);
    expect(tokens().value).toBe('2000');
    expect(saveBar()).toBeNull();
    pickVersion('12');
    await shown('v2');
    choose(t.columns.component, /^모델 설정/);
    fireEvent.change(tokens(), { target: { value: '3200' } });
    await settle();
    expect(tokens().value).toBe('2000');
    expect(saveBar()).toBeNull();
    fireEvent.click(within(band).getByRole('button', { name: t.retry }));
    await shown('v4');
    expect(screen.queryByTestId('saved-band')).toBeNull();
    expect(saveBar()).toBeNull();
    choose(t.columns.component, /^모델 설정/);
    fireEvent.change(tokens(), { target: { value: '3300' } });
    expect(saveBar()!.textContent).toContain(t.saveBar.count(1));
  });
});

describe('AD-02 ⑫ 저장 막대 셈 줄 없음(338 A10 — 모든 모듈)', () => {
  const saveBar = () => screen.queryByTestId('save-bar');

  it('모델 칸 하나·여럿 모두 막대 글은 「고친 것 n개」와 단추 글뿐(셈 줄 0)', async () => {
    setup({ initialVersion: 'v3', fake: fakeAiSettingModule() });
    await ready();
    choose(t.columns.component, /^모델 설정/);
    fireEvent.change(
      screen.getByRole('textbox', { name: t.model.maxOutputTokens }),
      { target: { value: '3000' } },
    );
    expect(saveBar()!.textContent).toBe(
      t.saveBar.count(1) + t.saveBar.revert + t.saveBar.save,
    );
    cleanup();
    setup({ fake: fakeAiSettingModule({ wide: true }) });
    await ready();
    choose(t.columns.component, /^모델 설정/);
    fireEvent.change(
      screen.getByRole('textbox', {
        name: `지어낸 칸 가 ${t.model.maxOutputTokens}`,
      }),
      { target: { value: '2500' } },
    );
    expect(saveBar()!.textContent).toBe(
      t.saveBar.count(1) + t.saveBar.revert + t.saveBar.save,
    );
  });
});

describe('AD-02 ⑫ 모듈이 주는 처리 흐름 띠(AS3b ② K7)', () => {
  // 가짜 흐름: 받은 props 를 적고 칸마다 단추 하나(그린워싱 0 · entities/ai-setting/api/testing.ts 0줄).
  type Props = Parameters<NonNullable<Fake['module']['flow']>>[0];
  function withFlow(fake: Fake = fakeAiSettingModule()) {
    const seen: Props[] = [];
    const flow = (props: Props) => {
      seen.push(props);
      return (
        <div data-testid="fake-flow">
          {props.groups.flatMap((group, groupIndex) =>
            group.prompts.map((one, promptIndex) => (
              <button
                key={`${group.key}/${one.key}`}
                type="button"
                data-fake-node={one.key}
                onClick={() =>
                  props.onPick({ group: groupIndex, prompt: promptIndex })
                }
              >
                {one.label}
              </button>
            )),
          )}
        </div>
      );
    };
    return { fake: { ...fake, module: { ...fake.module, flow } }, seen };
  }
  const last = (seen: Props[]) => seen.at(-1)!;
  const promptCard = () => card('prompt-slot');
  const slotText = (label: string) =>
    within(promptCard()).queryByRole('textbox', {
      name: `${label} ${t.prompt.text}`,
    });

  it('flow 있으면 셋째 열 0 · 2열 · 띠가 프롬프트 상세 위, flow 없으면 셋째 열·3열 그대로', async () => {
    const { fake } = withFlow();
    setup({ initialVersion: 'v3', fake });
    await ready();
    expect(
      screen.queryByRole('region', { name: t.columns.category }),
    ).toBeNull();
    const grid = column(t.columns.component).parentElement!;
    expect(grid.className).toContain('grid-cols-2');
    const band = screen.getByTestId('fake-flow');
    expect(
      band.compareDocumentPosition(promptCard()) &
        Node.DOCUMENT_POSITION_FOLLOWING,
    ).toBeTruthy();
    cleanup();
    setup({ initialVersion: 'v3' });
    await ready();
    expect(column(t.columns.category)).toBeTruthy();
    expect(column(t.columns.component).parentElement!.className).toContain(
      'grid-cols-3',
    );
  });

  it('마디 누름 → 그 칸 상세 · 띠의 picked 가 그 칸 · 모델 구성이면 띠 0', async () => {
    const { fake, seen } = withFlow();
    setup({ initialVersion: 'v3', fake });
    await ready();
    expect(last(seen).picked).toEqual({ group: 0, prompt: 0 });
    fireEvent.click(document.querySelector('[data-fake-node="eval"]')!);
    expect(slotText('지어낸 판정')).toBeTruthy();
    expect(last(seen).picked).toEqual({ group: 0, prompt: 1 });
    expect(last(seen).groups[0]!.prompts.map((one) => one.key)).toEqual([
      'detect',
      'eval',
      'repair',
      'low_only',
    ]);
    // 밴드 TRA1(W3): 묶음 이름(서버 label)도 띠로 — 마디 = 묶음인 모듈이 쓴다.
    expect(last(seen).groups.map((one) => one.label)).toEqual([
      '지어낸 판정 단계',
    ]);
    choose(t.columns.component, /^모델 설정/);
    expect(screen.queryByTestId('fake-flow')).toBeNull();
  });

  it('고친 칸 → edited 에 그 칸 · AI_PROMPT_* 거절 → refused 에 그 칸', async () => {
    const { fake, seen } = withFlow();
    fake.override.create = [
      () => ({
        kind: 'rejected',
        code: 'AI_PROMPT_TEXT_DUPLICATE',
        message: '지어낸 겹침 문장',
        fields: { 'prompts.steps.0.prompts.1.text': ['지어낸 칸 겹침 문장'] },
      }),
    ];
    setup({ initialVersion: 'v3', fake });
    await ready();
    fireEvent.click(document.querySelector('[data-fake-node="eval"]')!);
    fireEvent.change(slotText('지어낸 판정')!, {
      target: { value: '지어낸 겹친 글' },
    });
    expect(last(seen).edited).toEqual([{ group: 0, prompt: 1 }]);
    expect(last(seen).refused).toEqual([]);
    fireEvent.click(button(t.saveBar.save));
    const dialog = await screen.findByTestId('save-dialog');
    fireEvent.change(
      within(dialog).getByRole('textbox', { name: t.save.name }),
      {
        target: { value: '지어낸 새 판' },
      },
    );
    fireEvent.click(
      within(dialog).getByRole('button', { name: t.save.confirm }),
    );
    await screen.findByTestId('save-failure');
    expect(last(seen).refused).toEqual([{ group: 0, prompt: 1 }]);
  });

  // 밴드 PF1(T3): 띠는 프롬프트 카드 안(같은 카드 요소의 자손 — 단계 줄 묶음 바로 앞) · 따로 카드 0 · inline 으로 부름 · 카드 안 간격 24.
  it('띠는 프롬프트 카드 안 단계 줄 앞 · inline 참 · 카드 gap-6, flow 없는 모듈은 카드 안 띠 0', async () => {
    const { fake, seen } = withFlow();
    setup({ initialVersion: 'v3', fake });
    await ready();
    const band = screen.getByTestId('fake-flow');
    expect(band.parentElement).toBe(card('prompt'));
    expect(promptCard().previousElementSibling).toBe(band);
    expect(band.closest('[data-card]')).toBe(card('prompt'));
    expect(last(seen).inline).toBe(true);
    expect(card('prompt').className.split(/\s+/)).toContain('gap-6');
    expect(card('prompt').className.split(/\s+/)).not.toContain('gap-4');
    fireEvent.click(document.querySelector('[data-fake-node="repair"]')!);
    expect(slotText('지어낸 고치기')).toBeTruthy();
    expect(last(seen).picked).toEqual({ group: 0, prompt: 2 });
    cleanup();
    setup({ initialVersion: 'v3' });
    await ready();
    expect(screen.queryByTestId('fake-flow')).toBeNull();
  });

  // 밴드 TRA2(D1): 모듈 firstSlot — 처음 펼침과 판 바꿈 때 그 칸, 사용자가 고른 칸은 판을 바꾸면 다시 모듈 첫 칸. 없으면 묶음 0 칸 0(위 시험).
  it('firstSlot 있으면 처음 칸 = 모듈이 준 칸 · 판 바꿈(pick) 때 다시 그 칸', async () => {
    const { fake, seen } = withFlow();
    const firstSlot = vi.fn((groups: Props['groups']) => ({
      group: 0,
      prompt: groups[0]!.prompts.findIndex((one) => one.key === 'repair'),
    }));
    setup({
      initialVersion: 'v3',
      fake: { ...fake, module: { ...fake.module, firstSlot } },
    });
    await ready();
    expect(last(seen).picked).toEqual({ group: 0, prompt: 2 });
    expect(slotText('지어낸 고치기')).toBeTruthy();
    expect(firstSlot.mock.calls[0]![0][0]!.key).toBe(last(seen).groups[0]!.key);
    fireEvent.click(document.querySelector('[data-fake-node="eval"]')!);
    expect(last(seen).picked).toEqual({ group: 0, prompt: 1 });
    pickVersion('12');
    await titled('v2');
    expect(last(seen).picked).toEqual({ group: 0, prompt: 2 });
    expect(slotText('지어낸 고치기')).toBeTruthy();
  });

  // 밴드 TRA2(D9·D10): 모듈 slotLabel·lowerKey — 없으면 「단계」·대문자(그린워싱 그대로).
  it('slotLabel 있으면 상세 첫 줄 라벨이 그 글 · lowerKey 면 KEY 알약 uppercase 0, 없으면 「단계」·uppercase', async () => {
    const fake = fakeAiSettingModule();
    setup({
      initialVersion: 'v3',
      fake: {
        ...fake,
        module: { ...fake.module, slotLabel: '지어낸 칸 라벨', lowerKey: true },
      },
    });
    await ready();
    const label = () => promptCard().querySelector('span.w-40')!.textContent;
    const keyLook = () =>
      within(promptCard()).getByTestId('slot-key').className.split(/\s+/);
    expect(label()).toBe('지어낸 칸 라벨');
    expect(keyLook()).not.toContain('uppercase');
    cleanup();
    setup({ initialVersion: 'v3' });
    await ready();
    expect(label()).toBe(t.prompt.stepLabel);
    expect(keyLook()).toContain('uppercase');
  });

  // 밴드 DVA2(K1): 모듈 promptNote — 그 칸 글이면 글 칸 아래 한 줄, null 이면 0. 없는 모듈(그린워싱·영문번역 꼴)은 늘 0.
  it('promptNote 있으면 (묶음 key, 칸 key) 로 물어 그 칸 아래 한 줄 · null 칸은 0 · promptNote 없는 모듈은 0', async () => {
    const fake = fakeAiSettingModule();
    const promptNote = vi.fn((group: string, prompt: string) =>
      prompt === 'eval' ? `지어낸 ${group} 자리 안내` : null,
    );
    setup({
      initialVersion: 'v3',
      fake: { ...fake, module: { ...fake.module, promptNote } },
    });
    await ready();
    expect(within(promptCard()).queryAllByTestId('prompt-note')).toHaveLength(
      0,
    );
    expect(promptNote).toHaveBeenLastCalledWith('judge', 'detect');
    choose(t.columns.category, /지어낸 판정$/);
    await waitFor(() =>
      expect(
        within(promptCard())
          .queryAllByTestId('prompt-note')
          .map((node) => node.textContent),
      ).toEqual(['지어낸 judge 자리 안내']),
    );
    cleanup();
    setup({ initialVersion: 'v3' });
    await ready();
    choose(t.columns.category, /지어낸 판정$/);
    await waitFor(() => expect(slotText('지어낸 판정')).toBeTruthy());
    expect(within(promptCard()).queryAllByTestId('prompt-note')).toHaveLength(
      0,
    );
  });

  // 밴드 DVA2(K2): 모듈 outputNote — ① outputSection null 이면 0(먼저) ② 모듈 글 ③ null 이면 공통 글(숨김 아님). 없는 모듈은 공통 글.
  it('outputNote 세 갈래: 모듈 글 칸 → 모듈 글 · null 칸 → 공통 글 · outputSection null 칸 → 0(모듈 글이 있어도) · outputNote 없는 모듈은 공통 글', async () => {
    const fake = fakeAiSettingModule({
      promptModel: (key) => {
        const model = fakePromptModel(key);
        return {
          kind: 'ok',
          model: {
            ...model,
            promptGroups: model.promptGroups.map((group) => ({
              ...group,
              prompts: group.prompts.map((one) =>
                one.key === 'low_only' ? { ...one, outputSection: null } : one,
              ),
            })),
          },
        };
      },
    });
    const outputNote = (_group: string, prompt: string) =>
      prompt === 'detect' || prompt === 'low_only' ?
        '지어낸 모듈 출력 안내'
      : null;
    setup({
      initialVersion: 'v3',
      fake: { ...fake, module: { ...fake.module, outputNote } },
    });
    await ready();
    const shown = () =>
      within(promptCard())
        .queryAllByTestId('output-note')
        .map((node) => node.textContent);
    expect(shown()).toEqual(['지어낸 모듈 출력 안내']);
    choose(t.columns.category, /지어낸 판정$/);
    await waitFor(() => expect(shown()).toEqual([t.prompt.outputNote]));
    choose(t.columns.category, /지어낸 낮음 전용$/);
    await waitFor(() => expect(slotText('지어낸 낮음 전용')).toBeTruthy());
    expect(shown()).toEqual([]);
    cleanup();
    setup({ initialVersion: 'v3' });
    await ready();
    expect(shown()).toEqual([t.prompt.outputNote]);
  });

  // 밴드 TRA2(D4): 출력절 안내 노란 줄은 그 칸에 outputSection 이 있을 때만(모든 모듈 공통 규칙).
  it('outputSection null 인 칸은 출력절 안내 0 · 있는 칸은 1', async () => {
    const fake = fakeAiSettingModule({
      promptModel: (key) => {
        const model = fakePromptModel(key);
        return {
          kind: 'ok',
          model: {
            ...model,
            promptGroups: model.promptGroups.map((group, groupIndex) => ({
              ...group,
              prompts: group.prompts.map((one, promptIndex) =>
                groupIndex === 0 && promptIndex === 0 ?
                  { ...one, outputSection: null }
                : one,
              ),
            })),
          },
        };
      },
    });
    setup({ initialVersion: 'v3', fake });
    await ready();
    expect(within(promptCard()).queryAllByTestId('output-note')).toHaveLength(
      0,
    );
    choose(t.columns.category, /지어낸 판정$/);
    await waitFor(() =>
      expect(within(promptCard()).queryAllByTestId('output-note')).toHaveLength(
        1,
      ),
    );
  });
});
