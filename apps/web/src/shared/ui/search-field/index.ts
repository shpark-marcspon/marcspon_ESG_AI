// 검색 칸의 공개 표면. 이 폴더 밖에서는 여기서만 가져다 쓴다(app/guards/layers.test.ts 가 지킨다).
// 키트 SearchInput 을 쓰던 화면은 이름 하나(SearchInput → SearchField)와 import 경로만 바꾸면 된다.
export { SearchField } from './ui/SearchField.tsx';
export type { SearchFieldProps } from './ui/SearchField.tsx';
