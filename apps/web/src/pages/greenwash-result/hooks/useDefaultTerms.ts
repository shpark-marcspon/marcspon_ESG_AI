// 기본 단어 목록 훅(밴드 FW2 ③, GW-04 빈도의 「추가」 배지를 가를 때). 읽기 전·거절이면 null(밴드 LE1, sid:MARC-ENT-260 ④):
// 빈 목록으로 보면 추가 단어 줄이 모두 「추가」로 보여 틀린 정보가 된다 — 화면은 null 이면 「추가」 배지를 끈다(안내 없음).
import type { GreenwashStore } from '../../../entities/greenwash/api/index.ts';
import { useLoad } from '../../../shared/lib/useLoad.ts';

export function useDefaultTerms(
  store: GreenwashStore,
): readonly string[] | null {
  const { status } = useLoad([store], () => store.listDefaultTerms());
  return status.state === 'ready' ? status.data : null;
}
