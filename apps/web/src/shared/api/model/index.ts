import type {
  components,
  paths,
} from '../../../../../api-py/generated/api.d.ts';

// 업무 로직의 공개 표면. client.ts 와 헤드리스 층은 여기서만 가져다 쓴다.
// 계약 타입(apps/api-py/generated/api.d.ts)도 여기서 다시 내보낸다. 화면은 그 파일을 직접 가져오지 않는다.
export * from './failure.ts';
export * from './keys.ts';

export type { components, paths };

/** 계약의 스키마 이름표. 예: `Schemas["CalcIn"]`. */
export type Schemas = components['schemas'];
