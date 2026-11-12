// 양식 줄 꼴의 공개 표면. 이 폴더 밖에서는 여기서만 가져다 쓴다(app/guards/layers.test.ts 가 지킨다).
//   ui/        클래스 상수 다섯(묶음·줄·라벨·값·값 글). 글은 없다 — 라벨 글은 쓰는 쪽 문구 표에서
export {
  FORM_LABEL_CLASS,
  FORM_ROWS_CLASS,
  FORM_ROW_CLASS,
  FORM_VALUE_BODY_CLASS,
  FORM_VALUE_CLASS,
} from './ui/formRows.ts';
